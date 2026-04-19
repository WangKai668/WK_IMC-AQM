# -*- coding: utf-8 -*-

import random

# 用于生成PRED所需拓扑

# 二打一拓扑
# 2个发送主机 -> 交换机 -> 1个接收主机

###############################################################################
# 第一行：node_num >> switch_num >> tors >> link_num
# 总结点数、交换机数、叶交换机数、链接数
###############################################################################

total_nodes = 4      # 3 hosts + 1 switch
switch_num = 1       # 1 switch
leaf_num = 1         # leaf switches (这里交换机就是叶交换机)
link_num = 3         # h1-sw, h2-sw, sw-h3 共3条链路

###############################################################################
# 第二行：switch_num
# 交换机ID
###############################################################################

###############################################################################
# 节点ID分配：
# 0: h1 (发送主机1)
# 1: h2 (发送主机2)
# 2: h3 (接收主机)
# 3: sw (交换机)
###############################################################################

file_topo='topology-2to1.txt'
# Write topology file
with open(file_topo, 'w') as f:
    # First line: 总节点数 交换机数 叶交换机数 链路数
    f.write(f"{total_nodes} {switch_num} {leaf_num} {link_num}\n")

    # Second line: 交换机ID (只有1个交换机，ID=3)
    f.write('3\n')

    # 链路配置: src dst bandwidth delay error_rate

    # h1 -> sw (发送主机1连接到交换机)
    f.write(f"0 3 10000000000.0 10us 0\n")  # 10Gbps, 10μs延迟

    # h2 -> sw (发送主机2连接到交换机)
    f.write(f"1 3 10000000000.0 10us 0\n")  # 10Gbps, 10μs延迟

    # sw -> h3 (交换机连接到接收主机)
    f.write(f"3 2 10000000000.0 10us 0\n")  # 10Gbps, 10μs延迟

print(f"拓扑文件 '{file_topo}' 已生成！")
print("节点ID:")
print("  0: h1 (发送主机1)")
print("  1: h2 (发送主机2)")
print("  2: h3 (接收主机)")
print("  3: sw (交换机)")

# 生成二打一的流量文件
# h1和h2同时向h3发送流量


file_flow='flow-2to1'
file_postfix=".txt"

flow_amount=2 #流量总条数

disable_congestion=False #是否关闭流量拥塞

flow_instance=0.01 #每个流的时间间隔

# flow_num=0 #自增 流量编号 #弃用###


# 流量格式：源 目的 优先级 目的端口 最大包数量 开始时间
src=0
srcs=[0,1]
direc=2
direc_port=5000
priority=3
pack_amount_per_flow=100000000 #原来是1000000
flow_start_time=0.1

file_flow+=f"-{flow_amount}" + file_postfix

with open(file_flow, 'w') as f:
    # 第一行：流量总数
    f.write(f"{flow_amount}\n")

    for i in range(flow_amount):
        f.write(f"{random.choice(srcs)} {direc} {priority} {direc_port + i} {pack_amount_per_flow} {flow_start_time + disable_congestion * i * flow_instance}\n")

    # h1 -> h3: 从时间0.1开始，发送10000个包

    # # h2 -> h3: 从时间0.1开始，发送10000个包
    # f.write("1 2 3 5001 10000 0.1\n")

print(f"流量文件 '{file_flow}' 已生成！")
print("h1(0) 和 h2(1) 同时向 h3(2) 发送流量")