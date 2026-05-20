# -*- coding: utf-8 -*-

"""
1) Large Scale Simulations: To complement our testbed
experiments, we evaluate PRED on a larger-scale spine-leaf
topology with realistic workloads.
Setup: We simulate a 128-host leaf-spine topology with
8 spine and 8 leaf switches. Each leaf is connected to 16
servers via 10 Gbps links. The spine and leaf switches are
also connected via 10 Gbps links. The latency of the link is
10 µs. We use ECMP for load balancing. We generate traffic
based on two realistic workloads in production: WebSearch
[3] and DataMining [39]. Each sender sends messages in a
Poisson flow, and the target loads for the fixed receiver range
from 10% to 90%. K in ECN is 70 packets. The instantaneous
marking threshold for ECNSharp is 80 µs, the persistent target
threshold is 10 µs and the persistent interval is 150 µs. For
CoDel, we set the interval to be 150 µs and the target to be
10 µs. The results are shown in Figure 16, 17 and 18. All
results have been normalized to FCT achieved by PRED
"""
# 生成论文中的 128 主机叶脊拓扑
# 8 个脊交换机 (Spine), 8 个叶交换机 (Leaf)
# 每个叶交换机连接 16 台服务器
# 所有链路：10 Gbps, 10 µs 延迟

# 节点 ID 分配：
# 主机: 0 ~ 127
# 叶交换机: 128 ~ 135 (共 8 个)
# 脊交换机: 136 ~ 143 (共 8 个)

# host_count = 128
# leaf_count = 8
# spine_count = 8
# host_num_per_lead = 16

host_count = 6
leaf_count = 2
spine_count = 2
host_num_per_lead = 3

# SCENE_NAME = "LSS"

SCENE_NAME = "LSSe"

total_switches = leaf_count + spine_count
total_nodes = host_count + total_switches


# 链路数：
# 叶-脊：leaf_count * spine_count = 8*8 = 64
# 主机-叶：leaf_count * 16 = 8*16 = 128
link_num = leaf_count * spine_count + host_count

leaf_start_id = host_count               # 128
spine_start_id = host_count + leaf_count # 136

# 链路参数
bandwidth = "10000000000.0"   # 10 Gbps
link_delay = "10us"
error_rate = "0"

# 生成拓扑文件
file_topo = f"topology-{SCENE_NAME}.txt"
with open(file_topo, 'w') as f:
    # 第一行：总节点数 交换机总数 叶交换机数 链路数
    f.write(f"{total_nodes} {total_switches} {leaf_count} {link_num}\n")
    
    # 第二行及之后：所有交换机 ID（每行一个，或空格分隔。为清晰起见，每行一个）
    for sw_id in range(leaf_start_id, leaf_start_id + total_switches):
        f.write(f"{sw_id}\n")
    
    # 主机-叶链路
    for leaf_idx in range(leaf_count):
        leaf_id = leaf_start_id + leaf_idx
        for host_idx in range(leaf_idx * host_num_per_lead, (leaf_idx + 1) * host_num_per_lead):
            f.write(f"{host_idx} {leaf_id} {bandwidth} {link_delay} {error_rate}\n")
    
    # 叶-脊链路（全互联）
    for leaf_idx in range(leaf_count):
        leaf_id = leaf_start_id + leaf_idx
        for spine_idx in range(spine_count):
            spine_id = spine_start_id + spine_idx
            f.write(f"{leaf_id} {spine_id} {bandwidth} {link_delay} {error_rate}\n")

print(f"拓扑文件 '{file_topo}' 已生成！")
print(f"总节点数: {total_nodes} (主机 {host_count}, 叶交换机 {leaf_count}, 脊交换机 {spine_count})")
print(f"链路总数: {link_num}")