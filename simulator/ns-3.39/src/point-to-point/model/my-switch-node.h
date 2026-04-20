#ifndef MY_SWITCH_NODE_H
#define MY_SWITCH_NODE_H

#include <unordered_map>
#include <ns3/node.h>
#include "qbb-net-device.h"
#include "my-switch-mmu.h"
#include "pint.h"

namespace ns3 {

class Packet;

class MySwitchNode : public Node{
    // 端口数量
	static const uint32_t pCnt = 257;	// Number of ports used
    // 每个端口的队列数量
	static const uint32_t qCnt = 8;	// Number of queues/priorities used
    // 用于ECMP（等价多路径）哈希计算的种子值
	uint32_t m_ecmpSeed;
    // ​路由表，将 IP 地址映射到可能的 ECMP 端口（设备索引）
	std::unordered_map<uint32_t, std::vector<int> > m_rtTable; // map from ip address (u32) to possible ECMP port (index of dev)

    // 三维数组，记录从输入设备到输出设备在特定队列中的字节数，用于 PFC（优先级流控）监控
	// monitor of PFC
	uint32_t m_bytes[pCnt][pCnt][qCnt]; // m_bytes[inDev][outDev][qidx] is the bytes from inDev enqueued for outDev at qidx
	// ​数组，记录每个端口传输的字节数
	uint64_t m_txBytes[pCnt]; // counter of tx bytes

    // 每个端口上次发送的数据包大小和时间戳
	uint32_t m_lastPktSize[pCnt];
	uint64_t m_lastPktTs[pCnt]; // ns
    // 用于存储每个端口的利用率或其他相关指标
	double m_u[pCnt];

	// 斜率更新时间点
	Time m_prevTs[pCnt][qCnt];
	// 瞬时斜率
	uint32_t m_prevQlen[pCnt][qCnt];
	// 平均斜率
	int64_t m_avgSlope[pCnt][qCnt];  
	// 斜率更新权值  Bps
	double omega_s;

	// 入队时的斜率
	Time m_prevTsEnq[pCnt][qCnt];
	uint32_t m_prevQlenEnq[pCnt][qCnt];
	int64_t m_avgSlopeEnq[pCnt][qCnt];  


protected:
    // 指示是否启用 ECN（显式拥塞通知）  
	bool m_ecnEnabled;
    // 拥塞控制模式
	uint32_t m_ccMode;
    // 最大往返时间（RTT）
	uint64_t m_maxRtt;
    // 用于设置 ACK/NACK 的高优先级
	uint32_t m_ackHighPrio; // set high priority for ACK/NACK
    // ​指示是否启用电源管理功能
	// vamsi
	bool PowerEnabled;

private:
    // 路由追踪函数
    void TraceRouting(Ptr<const Packet> packet, uint32_t inDev, uint32_t outDev, Ipv4Address source, Ipv4Address destination);
    // 根据数据包和自定义头部信息，确定输出设备 
	int GetOutDev(Ptr<const Packet>, CustomHeader &ch);
    // 将数据包发送到指定设备
	void SendToDev(Ptr<Packet>p, CustomHeader &ch);
    // 进行 ECMP 哈希计算的静态函数
	static uint32_t EcmpHash(const uint8_t* key, size_t len, uint32_t seed);
	void CheckAndSendPfc(uint32_t inDev, uint32_t qIndex);
    // 用于检查并发送 PFC 和恢复帧
	void CheckAndSendResume(uint32_t inDev, uint32_t qIndex);
public:
    // 指向 MySwitchMmu 的智能指针，用于管理交换机的内存管理单元（MMU）
	Ptr<MySwitchMmu> m_mmu;

	static TypeId GetTypeId (void);
	MySwitchNode();
    // 设置 ECMP 哈希的种子值
	void SetEcmpSeed(uint32_t seed);
    // 添加和清除路由表项
	void AddTableEntry(Ipv4Address &dstAddr, uint32_t intf_idx);
	void ClearTable();
    // ​处理从设备接收的数据包
	bool SwitchReceiveFromDevice(Ptr<NetDevice> device, Ptr<Packet> packet, CustomHeader &ch);
    // 通知队列的数据包出队事件
	void SwitchNotifyDequeue(uint32_t ifIndex, uint32_t qIndex, Ptr<Packet> p);
	// 更新平均斜率
	void UpdateSlope(uint32_t ifIndex, uint32_t qIndex, Time t);

	// for approximate calc in PINT
	int logres_shift(int b, int l);
	int log2apprx(int x, int b, int m, int l); // given x of at most b bits, use most significant m bits of x, calc the result in l bits
};

} /* namespace ns3 */

#endif /* MY_SWITCH_NODE_H */
