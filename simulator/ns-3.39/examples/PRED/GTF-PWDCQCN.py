# -*- coding: utf-8 -*-
# 生成 PRED with DCQCN 场景的拓扑文件和流量文件
# 论文配置：20 发送端 -> 1 交换机 -> 1 接收端，40 Gbps 链路，2 µs 延迟

import os

# ==================== 生成控制标志 ====================
ONLY_TOPOLOGY = False  # 是否仅生成拓扑文件（不生成流量文件）
ONLY_FLOW = True      # 是否仅生成流量文件（不生成拓扑文件）


# ==================== 流量参数 ====================
FLOW_PARAMS = {
    "flow_count": 20,           # 流数量（每条发送端一条流）
    "priority": 3,              # 优先级（RDMA 常用值）
    "dst_port_base": 5000,      # 目的端口起始值
    "max_packets": 10000000000,   # 每个流最大包数（足够大）
                                # 100M
                                # 加两个零,10G
    "start_time": "0"    # 所有流同时启动
}

# ==================== 拓扑参数 ====================
TOPOLOGY_PARAMS = {
    "total_nodes": 22,          # 20 发送 + 1 接收 + 1 交换机 = 22
    "switch_num": 1,            # 交换机数量
    "leaf_num": 1,              # 叶交换机数量（此处视为 1）
    "link_num": 21,             # 链路数：20 条（发送->交换机） + 1 条（交换机->接收）
    "switch_id": 20,            # 交换机的节点 ID
    "sender_ids": list(range(0, FLOW_PARAMS['flow_count'])),   # 发送端 ID: 0~flow_count-1
    "receiver_id": 21,          # 接收端 ID: 21
    "bandwidth": "40000000000.0",   # 40 Gbps = 4e10 bps 
                                    # = 40 Mbps
    "link_delay": "2us",        # 传播延迟 2 微秒
    "error_rate": "0"           # 无丢包
}


def generate_topology(file_path, params):
    """生成拓扑文件"""
    try:
        with open(file_path, 'w') as f:
            # 第一行：节点数 交换机数 叶交换机数 链路数
            f.write(f"{params['total_nodes']} {params['switch_num']} "
                    f"{params['leaf_num']} {params['link_num']}\n")
            # 第二行：交换机 ID（可以空格分隔，这里单独一行）
            f.write(f"{params['switch_id']}\n")
            # 发送端到交换机的链路
            for src in params['sender_ids']:
                f.write(f"{src} {params['switch_id']} {params['bandwidth']} "
                        f"{params['link_delay']} {params['error_rate']}\n")
            # 交换机到接收端的链路
            f.write(f"{params['switch_id']} {params['receiver_id']} {params['bandwidth']} "
                    f"{params['link_delay']} {params['error_rate']}\n")
        print(f"✅ 拓扑文件已生成: {file_path}")
        print(f"   - 节点: {params['total_nodes']} (发送端 {len(params['sender_ids'])}, "
              f"接收端 1, 交换机 {params['switch_num']})")
        print(f"   - 链路带宽: {float(params['bandwidth'])/1e9:.0f} Gbps, 延迟: {params['link_delay']}")
        return True
    except Exception as e:
        print(f"❌ 生成拓扑文件失败: {e}")
        return False

def generate_flow(file_path, topo_params, flow_params):
    """生成流量文件"""
    try:
        with open(file_path, 'w') as f:
            f.write(f"{flow_params['flow_count']}\n")
            for idx, src in enumerate(topo_params['sender_ids']):
                dst_port = flow_params['dst_port_base'] + idx
                f.write(f"{src} {topo_params['receiver_id']} {flow_params['priority']} "
                        f"{dst_port} {flow_params['max_packets']} {flow_params['start_time']}\n")
        print(f"✅ 流量文件已生成: {file_path}")
        print(f"   - 流数量: {flow_params['flow_count']}, 所有流同时启动于 {flow_params['start_time']} s")
        return True
    except Exception as e:
        print(f"❌ 生成流量文件失败: {e}")
        return False

# if __name__ == "__main__":
#     # 生成拓扑文件
#     topo_file = "topology-PWDCQCN.txt"
#     if generate_topology(topo_file, TOPOLOGY_PARAMS):
#         # 生成流量文件
#         flow_file = f"flow-PWDCQCN-{FLOW_PARAMS['flow_count']}t1.txt"
#         generate_flow(flow_file, TOPOLOGY_PARAMS, FLOW_PARAMS)

if __name__ == "__main__":
    # 处理标志冲突：如果同时为 True，此处视为两者都生成（可改为报错或优先拓扑）
    if ONLY_TOPOLOGY and ONLY_FLOW:
        print("⚠️ 警告: ONLY_TOPOLOGY 和 ONLY_FLOW 同时为 True，将同时生成拓扑文件和流量文件")
    if ONLY_TOPOLOGY:
        # 仅生成拓扑文件
        topo_file = "topology-PWDCQCN.txt"
        generate_topology(topo_file, TOPOLOGY_PARAMS)
    elif ONLY_FLOW:
        # 仅生成流量文件（需要拓扑参数中的发送端信息，但不需要拓扑文件本身）
        flow_file = f"flow-PWDCQCN-{FLOW_PARAMS['flow_count']}t1.txt"
        generate_flow(flow_file, TOPOLOGY_PARAMS, FLOW_PARAMS)
    else:
        # 两者都生成
        topo_file = "topology-PWDCQCN.txt"
        if generate_topology(topo_file, TOPOLOGY_PARAMS):
            flow_file = f"flow-PWDCQCN-{FLOW_PARAMS['flow_count']}t1.txt"
            generate_flow(flow_file, TOPOLOGY_PARAMS, FLOW_PARAMS)