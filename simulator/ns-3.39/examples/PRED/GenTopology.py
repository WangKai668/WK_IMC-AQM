# -*- coding: utf-8 -*-

# 用于生成PRED所需拓扑

# 仿真128主机叶脊拓扑，8个脊交换机、8个叶交换机；
# 每个叶交换机通过10 Gbps链路连接16台服务器，脊交换机与叶交换机之间也采用10 Gbps链路；
# 链路延迟10µs；
# 采用ECMP进行负载均衡

###############################################################################
# 第一行：node_num >> switch_num >> tors >> link_num
# 总结点数、交换机数、叶交换机数、链接数
###############################################################################

total_nodes = 144  # 128 servers + 16 switches
switch_num = 16    # 8 leaf + 8 spine
leaf_num = 8       # leaf switches
link_num = 192     # 128 server-leaf links + 64 leaf-spine links

###############################################################################
# 第二行：switch_num
# 交换机ID
###############################################################################

# Switch IDs: 128 to 143
switch_ids = list(range(128, 128 + switch_num))

# Server IDs: 0 to 127
server_ids = list(range(0, 128))

# Leaf switch IDs: 128 to 135
leaf_ids = list(range(128, 128 + leaf_num))

# Spine switch IDs: 136 to 143
spine_ids = list(range(128 + leaf_num, 128 + switch_num))

###############################################################################
# 后续：src >> dst >> data_rate >> link_delay >> error_rate
# 源、目的、传输速率、链路时延、错误率
# RTT=2*link_delay吗？？
###############################################################################

# Write topology file
with open('topology_PRED.txt', 'w') as f:
    # First line
    f.write(f"{total_nodes} {switch_num} {leaf_num} {link_num}\n")

    # Second line: switch IDs
    f.write(' '.join(map(str, switch_ids)) + '\n')

    # Server-leaf links: each server connects to one leaf switch, 16 servers per leaf
    for i, server in enumerate(server_ids):
        leaf = leaf_ids[i // 16]  # 16 servers per leaf
        # Format: src dst bandwidth delay error_rate
        # Bandwidth: 10Gbps = 10^10 bps, delay: 10us, error_rate: 0
        f.write(f"{server} {leaf} 10000000000.0 10us 0\n")

    # Leaf-spine links: full connection between leaf and spine
    for leaf in leaf_ids:
        for spine in spine_ids:
            f.write(f"{leaf} {spine} 10000000000.0 10us 0\n")