#include "ns3/ipv4.h"
#include "ns3/packet.h"
#include "ns3/ipv4-header.h"
#include "ns3/pause-header.h"
#include "ns3/interface-tag.h"
#include "ns3/boolean.h"
#include "ns3/uinteger.h"
#include "ns3/double.h"
#include "my-switch-node.h"
#include "qbb-net-device.h"
#include "ppp-header.h"
#include "ns3/int-header.h"
#include "ns3/simulator.h"
#include <cmath>
#include "ns3/tcp-header.h"
#include "ns3/udp-header.h"
#include "ns3/custom-priority-tag.h"
#include "ns3/feedback-tag.h"
#include "ns3/unsched-tag.h"

namespace ns3 {

// 获取MySwitchNode的元信息
TypeId MySwitchNode::GetTypeId (void)
{
	static TypeId tid = TypeId ("ns3::MySwitchNode")  // 类名
	                    .SetParent<Node> ()  // 父类
	                    .AddConstructor<MySwitchNode> ()  // 构造函数
                        // 添加属性
                        // 是否启用ECN，默认false，通过m_ecnEnabled访问
	                    .AddAttribute("EcnEnabled",
	                                  "Enable ECN marking.",
	                                  BooleanValue(false),
	                                  MakeBooleanAccessor(&MySwitchNode::m_ecnEnabled),
	                                  MakeBooleanChecker())
                        // 拥塞控制模式
	                    .AddAttribute("CcMode",
	                                  "CC mode.",
	                                  UintegerValue(0),
	                                  MakeUintegerAccessor(&MySwitchNode::m_ccMode),
	                                  MakeUintegerChecker<uint32_t>())
                        // 是否为 ACK/NACK 设置高优先级
	                    .AddAttribute("AckHighPrio",
	                                  "Set high priority for ACK/NACK or not",
	                                  UintegerValue(0),
	                                  MakeUintegerAccessor(&MySwitchNode::m_ackHighPrio),
	                                  MakeUintegerChecker<uint32_t>())
                        // 网络的最大往返时间
	                    .AddAttribute("MaxRtt",
	                                  "Max Rtt of the network",
	                                  UintegerValue(9000),
	                                  MakeUintegerAccessor(&MySwitchNode::m_maxRtt),
	                                  MakeUintegerChecker<uint32_t>())
                        // ​指示是否启用电源管理功能
	                    .AddAttribute("PowerEnabled",
	                                  "Inserts Rxbytes instead of Txbytes in INT header",
	                                  BooleanValue(false),
	                                  MakeBooleanAccessor(&MySwitchNode::PowerEnabled),
	                                  MakeBooleanChecker())
						// 斜率更新权值
	                    .AddAttribute("OmegaS",
	                                  "Slope update weight",
	                                  DoubleValue(0.129),
	                                  MakeDoubleAccessor(&MySwitchNode::omega_s),
	                                  MakeDoubleChecker<double>())
	                    ;
	return tid;
}

// 构造函数
MySwitchNode::MySwitchNode() {
    // m_id是唯一标识，保证节点种子唯一
	m_ecmpSeed = m_id;
    // 表示这是交换机节点
	m_node_type = 1;
    // 初始化为MySwitchMmu对象
	m_mmu = CreateObject<MySwitchMmu>();
    // 遍历初始化m_bytes
	for (uint32_t i = 0; i < pCnt; i++)
		for (uint32_t j = 0; j < pCnt; j++)
			for (uint32_t k = 0; k < qCnt; k++)
				m_bytes[i][j][k] = 0;
	for (uint32_t i = 0; i < pCnt; i++)
		m_txBytes[i] = 0;
	for (uint32_t i = 0; i < pCnt; i++)
		m_lastPktSize[i] = m_lastPktTs[i] = 0;
	for (uint32_t i = 0; i < pCnt; i++)
		m_u[i] = 0;
}

int MySwitchNode::GetOutDev(Ptr<const Packet> p, CustomHeader &ch) {
	// look up entries
    // 复制传入的数据包 p，以避免修改原始数据包
	Ptr<Packet> cp = p->Copy();
    // 依次移除并解析 PPP（Point-to-Point Protocol）头部和 IPv4 头部
	PppHeader ph; cp->RemoveHeader(ph);
	Ipv4Header ih; cp->RemoveHeader(ih);
    // 在成员变量路由表中查找与数据包目的地址匹配的条目
	auto entry = m_rtTable.find(ih.GetDestination().Get());

	// no matching entry
    // 找不到返回-1
	if (entry == m_rtTable.end())
		return -1;

	// entry found
    // 提取对应的下一跳端口列表
	auto &nexthops = entry->second;

	// pick one next hop based on hash
    // ECMP负载均衡，构建一个包含源地址、目的地址和协议相关端口信息的缓冲区 buf
	union {
		uint8_t u8[4 + 4 + 2 + 2];
		uint32_t u32[3];
	} buf;
	buf.u32[0] = ih.GetSource().Get();
	buf.u32[1] = ih.GetDestination().Get();
	if (ih.GetProtocol() == 0x6) {
		TcpHeader th; cp->PeekHeader(th);
		buf.u32[2] = th.GetSourcePort() | ((uint32_t)th.GetDestinationPort() << 16);
	}
	else if (ch.l3Prot == 0x11) {
		buf.u32[2] = ch.udp.sport | ((uint32_t)ch.udp.dport << 16);
	}
	else if (ch.l3Prot == 0xFC || ch.l3Prot == 0xFD)
		buf.u32[2] = ch.ack.sport | ((uint32_t)ch.ack.dport << 16);

    // 计算哈希值
	uint32_t idx = EcmpHash(buf.u8, 12, m_ecmpSeed) % nexthops.size();
	// if (nexthops.size()>1){ std::cout << "selected " << idx << std::endl; }
	return nexthops[idx];
}

// 检查某个交换机端口的特定队列是否应该暂停（流控），如果需要，则发送 PFC（Priority Flow Control，优先级流控）帧来暂停流量传输
void MySwitchNode::CheckAndSendPfc(uint32_t inDev, uint32_t qIndex) {
	Ptr<QbbNetDevice> device = DynamicCast<QbbNetDevice>(m_devices[inDev]);
	if (m_mmu->CheckShouldPause(inDev, qIndex)) {
		device->SendPfc(qIndex, 0);
		// std::cout << "sending PFC" << std::endl;
		m_mmu->SetPause(inDev, qIndex);
	}
}

// 检测到交换机端口的特定队列需要恢复数据传输时，发送优先级流控（PFC，Priority Flow Control）恢复帧
void MySwitchNode::CheckAndSendResume(uint32_t inDev, uint32_t qIndex) {
	Ptr<QbbNetDevice> device = DynamicCast<QbbNetDevice>(m_devices[inDev]);
	if (m_mmu->CheckShouldResume(inDev, qIndex)) {
		device->SendPfc(qIndex, 1);
		m_mmu->SetResume(inDev, qIndex);
	}
}

// 将数据包发送到适当的输出设备（端口）
void MySwitchNode::SendToDev(Ptr<Packet>p, CustomHeader &ch) {
	// 获取输出设备下标
    int idx = GetOutDev(p, ch);
    // 找到输出设备的情况
	if (idx >= 0) {
        // 断言设备链路是活的
		NS_ASSERT_MSG(m_devices[idx]->IsLinkUp(), "The routing table look up should return link that is up");

		// determine the qIndex
        // 数据包应被发送到的队列索引
		uint32_t qIndex=0;
		MyPriorityTag priotag;
		// IMPORTANT: MyPriorityTag should only be attached by lossy traffic. This tag indicates the qIndex but also indicates that it is "lossy". Never attach MyPriorityTag on lossless traffic.
		// 尝试从数据包中提取 MyPriorityTag 标签（仅适用于有损流量）。如果找到该标签，则使用其指定的优先级作为 qIndex
        bool found = p->PeekPacketTag(priotag);

		// UnSchedTag is used by ABM. End-hosts explicitly tag packets of the first BDP so that ABM then prioritizes these packets in the buffer allocation.
        // 检查数据包是否包含 UnSchedTag 标签（用于 ABM）。如果存在，则获取其值，表示未调度的流量
		uint32_t unsched = 0;
		UnSchedTag tag;
		bool foundunSched = p->PeekPacketTag (tag);
		if (foundunSched) {
			unsched = tag.GetValue();
		}

		InterfaceTag t1;
		p->PeekPacketTag(t1);
		uint32_t inDev1 = t1.GetPortId();

		// std::cout << "协议类型：" << ch.l3Prot << std::endl;

        // 根据数据包的协议类型和 m_ackHighPrio 设置，确定 qIndex 的最终值
		// 如果是 QCN（0xFF）、PFC（0xFE）或 NACK（0xFD 或 0xFC）协议，且 m_ackHighPrio 设置为真，则将 qIndex 设为最高优先级 0
        if (ch.l3Prot == 0xFF || ch.l3Prot == 0xFE || (m_ackHighPrio && (ch.l3Prot == 0xFD || ch.l3Prot == 0xFC))) { //QCN or PFC or NACK, go highest priority
			qIndex = 0;
			// if(inDev1 == 1){
			// 	std::cout << "QCN or PFC or NACK, go highest priority" << std::endl;
			// }
		}
        // 如果找到了 MyPriorityTag，则使用其指定的优先级
		else if (found) {
			qIndex = priotag.GetPriority();
			// if(inDev1 == 1){
			// 	std::cout << "using queue " << qIndex << std::endl;
			// }
		}
        // 否则，根据协议类型设置 qIndex：对于 TCP（0x06）协议，设为 1；对于其他协议，使用 ch.udp.pg 的值
		else {
			qIndex = (ch.l3Prot == 0x06 ? 1 : ch.udp.pg); // For TCP/IP if the stack did not attach MyPriorityTag, put to queue 1.
			// if(inDev1 == 1){
			// 	std::cout << "else, use queue " << qIndex << std::endl;
			// }
		}
		// std::cout << "qIndex: " << qIndex << std::endl;
		// admission control
        // 入队控制
        // 从数据包中提取 InterfaceTag，获取输入设备的索引 inDev
		InterfaceTag t;
		p->PeekPacketTag(t);
		uint32_t inDev = t.GetPortId();
        // 如果 qIndex 不是最高优先级（0），则执行入队控制
		if (qIndex != 0) { //not highest priority
			// IMPORTANT: MyPriorityTag should only be attached by lossy traffic. This tag indicates the qIndex but also indicates that it is "lossy". Never attach MyPriorityTag on lossless traffic.
			// 调用 m_mmu->CheckIngressAdmission 和 m_mmu->CheckEgressAdmission，检查输入和输出设备在指定队列和数据包大小下，是否允许入队
            if (m_mmu->CheckIngressAdmission(inDev, qIndex, p->GetSize(), found,unsched) && m_mmu->CheckEgressAdmission(idx, qIndex, p->GetSize(), found,unsched)) {			// Admission control
                // 如果通过检查，则更新入队状态，调用 m_mmu->UpdateIngressAdmission 和 m_mmu->UpdateEgressAdmission
				m_mmu->UpdateIngressAdmission(inDev, qIndex, p->GetSize(), found, unsched);
				m_mmu->UpdateEgressAdmission(idx, qIndex, p->GetSize(), found);
				// if(idx >= 17){
				// 	std::cout << "idx: " << idx << ", qIndex: " << qIndex << ", p->GetSize(): " << p->GetSize() << std::endl;
				// }
			} else {
                // 如果未通过检查，则直接返回，丢弃数据包
				return; // Drop
			}
            // 调用 CheckAndSendPfc(inDev, qIndex)，检查是否需要发送 PFC（Priority Flow Control）帧，以通知发送方暂停发送
			CheckAndSendPfc(inDev, qIndex);
		}
        // 更新 m_bytes[inDev][idx][qIndex]，记录从输入设备到输出设备在特定队列上的字节数
		m_bytes[inDev][idx][qIndex] += p->GetSize();
        // 调用 m_devices[idx]->SwitchSend(qIndex, p, ch)，通过指定的输出设备和队列发送数据包
		m_devices[idx]->SwitchSend(qIndex, p, ch);

		// 计算瞬时斜率
		// 获取前一次时间戳和队列长度
		Time prev_t = m_prevTsEnq[idx][qIndex];
		uint32_t prev_qlen = m_prevQlenEnq[idx][qIndex];
		double s;

		// std::cout << "UpdateSlope: [" << ifIndex << ", " << qIndex << "], prev_t = " << prev_t << ", prev_qlen = " << prev_qlen << ", t = " << t << std::endl;
		// 避免除以0
		if (Simulator::Now() == prev_t) {
			s = m_avgSlopeEnq[idx][qIndex];
		}
		else {
			Ptr<QbbNetDevice> dev = DynamicCast<QbbNetDevice>(m_devices[idx]);
			uint32_t qlen = dev->GetQueue()->GetNBytesTotal(); // queue length at dequeue
			Time now = Simulator::Now();
			// std::cout << "qlen: "<< qlen <<  ", prev_qlen: " << prev_qlen <<std::endl;
			s = static_cast<double>(static_cast<double>(static_cast<int64_t>(qlen) - static_cast<int64_t>(prev_qlen)) / (now - prev_t).ToDouble(Time::Unit::NS));
			m_prevQlenEnq[idx][qIndex] = qlen;
			m_prevTsEnq[idx][qIndex] = now;
			m_avgSlopeEnq[idx][qIndex] = s;
			// if(s != 0){
			// 	std::cout << "s: " << s << std::endl;
			// }
		}
		// std::cout << "qlen - prev_qlen = " << qlen - prev_qlen << ", (t - prev_t).ToDouble(Time::Unit::S) = " << (t - prev_t).ToDouble(Time::Unit::S) << std::endl;
		// 入队策略(看看idx是否==ifIndex)
		// if(s < 0) std::cout << "s: " << s << std::endl;
		// std::cout << "Enqueue: " <<"idx: " << idx << ", qIndex: " << qIndex << std::endl;
		m_mmu->EnqueueScheme(idx, qIndex, p, m_avgSlope[idx][qIndex], s);
        // 更新输出设备的接收字节总数 totalBytesRcvd
		DynamicCast<QbbNetDevice>(m_devices[idx])->totalBytesRcvd += p->GetSize(); // Attention: this is the egress port's total received packets. Not the ingress port.
	} else
		std::cout << "outdev not found! Dropped. This should not happen. Debugging required!" << std::endl;
	return; // Drop
}

uint32_t MySwitchNode::EcmpHash(const uint8_t* key, size_t len, uint32_t seed) {
	uint32_t h = seed;
	if (len > 3) {
		const uint32_t* key_x4 = (const uint32_t*) key;
		size_t i = len >> 2;
		do {
			uint32_t k = *key_x4++;
			k *= 0xcc9e2d51;
			k = (k << 15) | (k >> 17);
			k *= 0x1b873593;
			h ^= k;
			h = (h << 13) | (h >> 19);
			h += (h << 2) + 0xe6546b64;
		} while (--i);
		key = (const uint8_t*) key_x4;
	}
	if (len & 3) {
		size_t i = len & 3;
		uint32_t k = 0;
		key = &key[i - 1];
		do {
			k <<= 8;
			k |= *key--;
		} while (--i);
		k *= 0xcc9e2d51;
		k = (k << 15) | (k >> 17);
		k *= 0x1b873593;
		h ^= k;
	}
	h ^= len;
	h ^= h >> 16;
	h *= 0x85ebca6b;
	h ^= h >> 13;
	h *= 0xc2b2ae35;
	h ^= h >> 16;
	return h;
}

void MySwitchNode::SetEcmpSeed(uint32_t seed) {
	m_ecmpSeed = seed;
}

void MySwitchNode::AddTableEntry(Ipv4Address &dstAddr, uint32_t intf_idx) {
	uint32_t dip = dstAddr.Get();
	m_rtTable[dip].push_back(intf_idx);
}

void MySwitchNode::ClearTable() {
	m_rtTable.clear();
}

// 路由追踪函数
void MySwitchNode::TraceRouting(Ptr<const Packet> packet, uint32_t inDev, uint32_t outDev, Ipv4Address source, Ipv4Address destination) {
    // 获取当前时间
    double now = Simulator::Now().GetSeconds();
    
    // 获取数据包大小
    uint32_t size = packet->GetSize();
    
    // 获取当前节点ID
    uint32_t nodeId = GetId();
    
    // 输出路由信息
    std::cout << "[" << now << "s] Routing Trace: "
              << "Source=" << source << " -> "
              << "Destination=" << destination << " | "
              << "CurrentNode=" << nodeId << "(Switch) | "
              << "InPort=" << inDev << " -> "
              << "OutPort=" << outDev << " | "
              << "PacketSize=" << size << " bytes" << std::endl;
}

// 修改 SwitchReceiveFromDevice 函数
bool MySwitchNode::SwitchReceiveFromDevice(Ptr<NetDevice> device, Ptr<Packet> packet, CustomHeader &ch) {
    // // 获取输入设备索引
    // uint32_t inDev = device->GetIfIndex();
    
    // // 获取源地址和目的地址
    // Ipv4Address source = Ipv4Address(ch.sip);
    // Ipv4Address destination = Ipv4Address(ch.dip);
    
    // // 获取输出设备索引
    // int outDev = GetOutDev(packet, ch);
    
    // // 添加路由追踪
    // TraceRouting(packet, inDev, outDev, source, destination);
    
    // 发送数据包
    SendToDev(packet, ch);
    return true;
}

// 出队操作
// ifIndex：端口下标
// qIndex：队列下标
// p：数据包
void MySwitchNode::SwitchNotifyDequeue(uint32_t ifIndex, uint32_t qIndex, Ptr<Packet> p) {
	// 通过 p->PeekPacketTag(t) 获取数据包的接口标签（InterfaceTag），以确定数据包是从哪个入接口（inDev）进入交换机的
    InterfaceTag t;
	p->PeekPacketTag(t);
    
    // 获取数据包的优先级标签（MyPriorityTag）
	MyPriorityTag priotag;
	bool found = p->PeekPacketTag(priotag);

    // 如果数据包不属于最高优先级队列（即 qIndex != 0），则执行以下操作
	if (qIndex != 0) {
        // 更新流量控制信息：​调用 m_mmu->RemoveFromIngressAdmission 和 m_mmu->RemoveFromEgressAdmission，更新交换机的流量控制状态，移除相应的入队和出队信息
		uint32_t inDev = t.GetPortId();
		m_mmu->RemoveFromIngressAdmission(inDev, qIndex, p->GetSize(), found);
		m_mmu->RemoveFromEgressAdmission(ifIndex, qIndex, p->GetSize(), found);
		// 减少对应队列的字节计数，反映出队操作
        m_bytes[inDev][ifIndex][qIndex] -= p->GetSize();
		// ​如果显式拥塞通知（ECN）功能启用
        if (m_ecnEnabled) {
			// 更新平均斜率
			UpdateSlope(ifIndex, qIndex, Simulator::Now());
			// std::cout << "UpdateSlope: [" << ifIndex << ", " << qIndex << "], avg_s = " << m_avgSlope[ifIndex][qIndex] << std::endl;
			// 执行出队算法
			// std::cout << "Dequeue: " <<"idx: " << ifIndex << ", qIndex: " << qIndex << std::endl;
			m_mmu->DequeueScheme(ifIndex, qIndex, p, m_avgSlope[ifIndex][qIndex]);
			// std::cout << "Dequeue Done." << std::endl;
		}
		//CheckAndSendPfc(inDev, qIndex);
        // 调用 CheckAndSendResume，向入接口发送恢复信号，指示可以继续发送数据
		CheckAndSendResume(inDev, qIndex);
		// std::cout << "CheckAndSendResume Done." << std::endl;
	}
	if (1) {
        // 获取数据包的缓冲区指针，以便直接访问数据内容
		uint8_t* buf = p->GetBuffer();
        // 检查数据包是否为 UDP 数据包。通过计算 PPP 头部的静态大小，加上 9 个字节的位置，检查该位置的值是否为 0x11（即 UDP 协议的标识符）
		if (buf[PppHeader::GetStaticSize() + 9] == 0x11) { // udp packet
			// 定位并获取 INT 头部的位置
            IntHeader *ih = (IntHeader*)&buf[PppHeader::GetStaticSize() + 20 + 8 + 6]; // ppp, ip, udp, SeqTs, INT
			// 根据 ifIndex 获取对应的网络设备实例
            Ptr<QbbNetDevice> dev = DynamicCast<QbbNetDevice>(m_devices[ifIndex]);
			// 判断拥塞控制模式
            if (m_ccMode == 3) { // HPCC or PowerTCP-INT
				// 是否启用Power模式
                if (!PowerEnabled)
                    // 将当前时间步、发送字节数、队列总字节数和数据速率推送到 INT 头部
					ih->PushHop(Simulator::Now().GetTimeStep(), m_txBytes[ifIndex], dev->GetQueue()->GetNBytesTotal(), dev->GetDataRate().GetBitRate());
				else
                    // 将接收字节数、队列总字节数和数据速率推送到 INT 头部
					ih->PushHop(Simulator::Now().GetTimeStep(), dev->GetQueue()->GetNBytesRxTotal(), dev->GetQueue()->GetNBytesTotal(), dev->GetDataRate().GetBitRate());
				// ih->PushHop(Simulator::Now().GetTimeStep(), m_txBytes[ifIndex], dev->GetQueue()->GetNBytesTotal(), dev->GetDataRate().GetBitRate());
			} else if (m_ccMode == 10) { // HPCC-PINT
				uint64_t t = Simulator::Now().GetTimeStep();
				// 计算当前时间步与上一个数据包时间戳之间的时间差（dt）
                uint64_t dt = t - m_lastPktTs[ifIndex];
				// 并进行最大 RTT（往返时间）限制
                if (dt > m_maxRtt)
					dt = m_maxRtt;
                // 获取链路带宽（B）和队列长度（qlen）
				uint64_t B = dev->GetDataRate().GetBitRate() / 8; //Bps
				uint64_t qlen = dev->GetQueue()->GetNBytesTotal();
				double newU;

				/**************************
				 * approximate calc
				 *************************/
                // 使用近似计算方法，基于 dt、qlen、B 和最大 RTT，计算新的利用率（newU）
				int b = 20, m = 16, l = 20; // see log2apprx's paremeters
				int sft = logres_shift(b, l);
				double fct = 1 << sft; // (multiplication factor corresponding to sft)
				double log_T = log2(m_maxRtt) * fct; // log2(T)*fct
				double log_B = log2(B) * fct; // log2(B)*fct
				double log_1e9 = log2(1e9) * fct; // log2(1e9)*fct
				double qterm = 0;
				double byteTerm = 0;
				double uTerm = 0;
				if ((qlen >> 8) > 0) {
					int log_dt = log2apprx(dt, b, m, l); // ~log2(dt)*fct
					int log_qlen = log2apprx(qlen >> 8, b, m, l); // ~log2(qlen / 256)*fct
					qterm = pow(2, (
					                log_dt + log_qlen + log_1e9 - log_B - 2 * log_T
					            ) / fct
					           ) * 256;
					// 2^((log2(dt)*fct+log2(qlen/256)*fct+log2(1e9)*fct-log2(B)*fct-2*log2(T)*fct)/fct)*256 ~= dt*qlen*1e9/(B*T^2)
				}
				if (m_lastPktSize[ifIndex] > 0) {
					int byte = m_lastPktSize[ifIndex];
					int log_byte = log2apprx(byte, b, m, l);
					byteTerm = pow(2, (
					                   log_byte + log_1e9 - log_B - log_T
					               ) / fct
					              );
					// 2^((log2(byte)*fct+log2(1e9)*fct-log2(B)*fct-log2(T)*fct)/fct) ~= byte*1e9 / (B*T)
				}
				if (m_maxRtt > dt && m_u[ifIndex] > 0) {
					int log_T_dt = log2apprx(m_maxRtt - dt, b, m, l); // ~log2(T-dt)*fct
					int log_u = log2apprx(int(round(m_u[ifIndex] * 8192)), b, m, l); // ~log2(u*512)*fct
					uTerm = pow(2, (
					                log_T_dt + log_u - log_T
					            ) / fct
					           ) / 8192;
					// 2^((log2(T-dt)*fct+log2(u*512)*fct-log2(T)*fct)/fct)/512 = (T-dt)*u/T
				}
				newU = qterm + byteTerm + uTerm;

#if 0
				/**************************
				 * accurate calc
				 *************************/
				double weight_ewma = double(dt) / m_maxRtt;
				double u;
				if (m_lastPktSize[ifIndex] == 0)
					u = 0;
				else {
					double txRate = m_lastPktSize[ifIndex] / double(dt); // B/ns
					u = (qlen / m_maxRtt + txRate) * 1e9 / B;
				}
				newU = m_u[ifIndex] * (1 - weight_ewma) + u * weight_ewma;
				printf(" %lf\n", newU);
#endif

				/************************
				 * update PINT header
				 ***********************/
                // 更新 INT 头部中的功率字段，以反映新的利用率
				uint16_t power = Pint::encode_u(newU);
				if (power > ih->GetPower())
					ih->SetPower(power);

				m_u[ifIndex] = newU;
			}
		}
		else {
            // 如果数据包包含反馈标签，则更新其中的队列长度、时间戳、带宽、发送字节数等信息，并增加跳数
			FeedbackTag Int;
			bool found;
			found = p->PeekPacketTag(Int);
			if (found) {
				Ptr<QbbNetDevice> dev = DynamicCast<QbbNetDevice>(m_devices[ifIndex]);
				Int.setTelemetryQlenDeq(Int.getHopCount(), dev->GetQueue()->GetNBytesTotal()); // queue length at dequeue
				Int.setTelemetryTsDeq(Int.getHopCount(), Simulator::Now().GetNanoSeconds()); // timestamp at dequeue
				Int.setTelemetryBw(Int.getHopCount(), dev->GetDataRate().GetBitRate());
				Int.setTelemetryTxBytes(Int.getHopCount(), m_txBytes[ifIndex]);
				Int.incrementHopCount(); // Incrementing hop count at Dequeue. Don't do this at enqueue.
				p->ReplacePacketTag(Int); // replacing the tag with new values
				// std::cout << "found " << Int.getHopCount() << std::endl;
			}
		}
	}
    // 更新发送字节数、上一个数据包的大小和时间戳
	m_txBytes[ifIndex] += p->GetSize();
	m_lastPktSize[ifIndex] = p->GetSize();
	m_lastPktTs[ifIndex] = Simulator::Now().GetTimeStep();
}

void MySwitchNode::UpdateSlope(uint32_t ifIndex, uint32_t qIndex, Time t) {
    // 获取前一次时间戳和队列长度
    Time prev_t = m_prevTs[ifIndex][qIndex];
    uint32_t prev_qlen = m_prevQlen[ifIndex][qIndex];
    // 避免除以0
    if (t == prev_t) return;
	Ptr<QbbNetDevice> dev = DynamicCast<QbbNetDevice>(m_devices[ifIndex]);
	uint32_t qlen = dev->GetQueue()->GetNBytesTotal(); 
    // 计算瞬时斜率 s
    double s = static_cast<double>(static_cast<double>(static_cast<int64_t>(qlen) - static_cast<int64_t>(prev_qlen)) / 
																				(t - prev_t).ToDouble(Time::Unit::NS));
    // 更新平均斜率 avg_s
    double avg_s = m_avgSlope[ifIndex][qIndex];
    avg_s = (1.0f - omega_s) * avg_s + omega_s * s;
    // 存回平均斜率
    m_avgSlope[ifIndex][qIndex] = avg_s;
    // 更新保存的时间戳和队列长度
    m_prevTs[ifIndex][qIndex] = t;
    m_prevQlen[ifIndex][qIndex] = qlen;
}


int MySwitchNode::logres_shift(int b, int l) {
	static int data[] = {0, 0, 1, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5};
	return l - data[b];
}

int MySwitchNode::log2apprx(int x, int b, int m, int l) {
	int x0 = x;
	int msb = int(log2(x)) + 1;
	if (msb > m) {
		x = (x >> (msb - m) << (msb - m));
#if 0
		x += + (1 << (msb - m - 1));
#else
		int mask = (1 << (msb - m)) - 1;
		if ((x0 & mask) > (rand() & mask))
			x += 1 << (msb - m);
#endif
	}
	return int(log2(x) * (1 << logres_shift(b, l)));
}

} /* namespace ns3 */
