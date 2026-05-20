# -*- coding: utf-8 -*-

# 生成 18-to-1 (18 个发送端到 1 个接收端) 的拓扑文件和流量文件
# 参考文献：论文 "Revisiting Random Early Detection Tuning" 中 Observation 2 实验
# 参数：所有链路 10 Gbps，传播延迟 2 us（RTT ≈ 4 us + 发送时延）
# 拓扑：18 个发送主机 (ID 0..17)，1 个接收主机 (ID 18)，1 台交换机 (ID 19)

import random

# ===== 拓扑文件配置 =====
total_nodes = 20      # 18 发送 + 1 接收 + 1 交换机 = 20
switch_num = 1        # 1 台交换机
leaf_num = 1          # 叶交换机数（这里就是交换机本身）
link_num = 19         # 18 条发送端->交换机 + 1 条交换机->接收端

switch_id = 19        # 交换机 ID
sender_ids = list(range(0, 18))   # 发送端 ID: 0~17
receiver_id = 18                  # 接收端 ID: 18

# 链路参数（论文：10 Gbps, 2µs 传播延迟）
bandwidth = "10000000000.0"   # 10 Gbps
link_delay = "2us"
error_rate = "0"

file_topo = "topology-18to1.txt"
with open(file_topo, 'w') as f:
    # 第一行：总节点数 交换机数 叶交换机数 链路数
    f.write(f"{total_nodes} {switch_num} {leaf_num} {link_num}\n")
    # 第二行：交换机 ID
    f.write(f"{switch_id}\n")
    # 发送端到交换机的链路 (18 条)
    for src in sender_ids:
        f.write(f"{src} {switch_id} {bandwidth} {link_delay} {error_rate}\n")
    # 交换机到接收端的链路 (1 条)
    f.write(f"{switch_id} {receiver_id} {bandwidth} {link_delay} {error_rate}\n")

print(f"拓扑文件 '{file_topo}' 已生成！")
print(f"  总节点: {total_nodes} (发送端 {len(sender_ids)}, 接收端 1, 交换机 1)")
print(f"  链路带宽: {bandwidth} bps, 延迟: {link_delay}")


# ===== 流量文件配置 =====
flow_amount = 18      # 18 条流，每条从一个发送端到接收端
priority = 3          # 优先级（与你的示例一致）
dst_port_base = 5000  # 目的端口起始
max_packet_count = 100000000  # 最大包数（足够大）
start_time = 0.0      # 同时启动（为了测试并发拥塞）

file_flow = f"flow-18to1.txt"
with open(file_flow, 'w') as f:
    f.write(f"{flow_amount}\n")
    # 为每个发送端生成一条流，目的端口递增
    for i, src in enumerate(sender_ids):
        dst_port = dst_port_base + i
        f.write(f"{src} {receiver_id} {priority} {dst_port} {max_packet_count} {start_time}\n")

print(f"流量文件 '{file_flow}' 已生成！")
print(f"  总流数: {flow_amount}")
print(f"  所有流同时从发送端 0-17 发往接收端 18，启动时间 {start_time} s")

# # -*- coding: utf-8 -*-

# import random

# # 用于生成PRED所需拓扑

# # 二打一拓扑
# # 2个发送主机 -> 交换机 -> 1个接收主机

# ###############################################################################
# # 第一行：node_num >> switch_num >> tors >> link_num
# # 总结点数、交换机数、叶交换机数、链接数
# ###############################################################################

# total_nodes = 4      # 3 hosts + 1 switch
# switch_num = 1       # 1 switch
# leaf_num = 1         # leaf switches (这里交换机就是叶交换机)
# link_num = 3         # h1-sw, h2-sw, sw-h3 共3条链路

# ###############################################################################
# # 第二行：switch_num
# # 交换机ID
# ###############################################################################

# ###############################################################################
# # 节点ID分配：
# # 0: h1 (发送主机1)
# # 1: h2 (发送主机2)
# # 2: h3 (接收主机)
# # 3: sw (交换机)
# ###############################################################################

# file_topo='topology-2to1.txt'
# # Write topology file
# with open(file_topo, 'w') as f:
#     # First line: 总节点数 交换机数 叶交换机数 链路数
#     f.write(f"{total_nodes} {switch_num} {leaf_num} {link_num}\n")

#     # Second line: 交换机ID (只有1个交换机，ID=3)
#     f.write('3\n')

#     # 链路配置: src dst bandwidth delay error_rate

#     # h1 -> sw (发送主机1连接到交换机)
#     f.write(f"0 3 10000000000.0 10us 0\n")  # 10Gbps, 10μs延迟

#     # h2 -> sw (发送主机2连接到交换机)
#     f.write(f"1 3 10000000000.0 10us 0\n")  # 10Gbps, 10μs延迟

#     # sw -> h3 (交换机连接到接收主机)
#     f.write(f"3 2 10000000000.0 10us 0\n")  # 10Gbps, 10μs延迟

# print(f"拓扑文件 '{file_topo}' 已生成！")
# print("节点ID:")
# print("  0: h1 (发送主机1)")
# print("  1: h2 (发送主机2)")
# print("  2: h3 (接收主机)")
# print("  3: sw (交换机)")

# # 生成二打一的流量文件
# # h1和h2同时向h3发送流量


# file_flow='flow-2to1'
# file_postfix=".txt"

# flow_amount=8 #流量总条数

# disable_congestion=False #是否关闭流量拥塞

# flow_instance=0.01 #每个流的时间间隔

# # flow_num=0 #自增 流量编号 #弃用###


# # 流量格式：源 目的 优先级 目的端口 最大包数量 开始时间
# src=0
# srcs=[0,1]
# direc=2
# direc_port=5000
# priority=3
# pack_amount_per_flow=100000000 #原来是1000000
# flow_start_time=0.001

# file_flow+=f"-{flow_amount}" + file_postfix

# with open(file_flow, 'w') as f:
#     # 第一行：流量总数
#     f.write(f"{flow_amount}\n")

#     for i in range(flow_amount):
#         f.write(f"{random.choice(srcs)} {direc} {priority} {direc_port + i} {pack_amount_per_flow} {flow_start_time + disable_congestion * i * flow_instance}\n")

#     # h1 -> h3: 从时间0.001开始，发送10000个包

#     # # h2 -> h3: 从时间0.001开始，发送10000个包
#     # f.write("1 2 3 5001 10000 0.001\n")

# print(f"流量文件 '{file_flow}' 已生成！")
# print("h1(0) 和 h2(1) 同时向 h3(2) 发送流量")