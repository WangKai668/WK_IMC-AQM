# ==================== 流量参数 ====================
FLOW_PARAMS = {
    "flow_count": 2,           # 流数量（每条发送端一条流）
    "priority": 3,              # 优先级（RDMA 常用值）
    "dst_port_base": 5000,      # 目的端口起始值
    "max_packets": 100000000,   # 每个流最大包数（足够大）
                                # 100M
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