# -*- coding: utf-8 -*-
# 高速变换流RCF（Rapid Changing Flow）场景的拓扑文件和流量文件
# 配置：16 发送端 -> 1 交换机 -> 1 接收端，10 Gbps 链路，10 µs 延迟
# 流量时间窗口：
#   - 4 条流：0 ms → 80 ms（持续长流，包数极大）

import os
import random

# ==================== 生成流量 ====================
def generate_rcf_windows(
    long_flow: tuple,                 # (start_s, end_s, long_flow_count, 'long')
    burst_flow_options: list,         # 额外流数量的可选列表，例如 [4, 8, 16, 4]
    burst_count: int,                 # 要生成的突发窗口个数
    burst_duration_us: float = 10.0,
    min_gap_us: float = 10.0,
    max_gap_us: float = 50.0,
    start_offset_us: float = 0.0,
    total_duration_s: float = 0.08
):
    """
    生成 RCF 场景的 WINDOWS 列表：
        - 一个长流窗口（整个时间段）
        - 若干个短突发窗口，每个窗口的额外流数量从 burst_flow_options 中随机选取
        突发窗口内的总流数 = long_flow_count + 额外流数
    """
    windows = [long_flow]
    long_flow_count = long_flow[2]  # 长流数量（例如4）

    burst_dur_s = burst_duration_us / 1e6
    current_start_s = start_offset_us / 1e6

    for _ in range(burst_count):
        if current_start_s + burst_dur_s > total_duration_s:
            break
        # 从列表中随机选取一个额外流数
        extra_flows = random.choice(burst_flow_options)
        total_flows = long_flow_count + extra_flows  # 突发窗口内的总流数
        windows.append((
            current_start_s,
            current_start_s + burst_dur_s,
            total_flows,
            'window'
        ))
        # 随机间隔
        gap_s = random.uniform(min_gap_us, max_gap_us) / 1e6
        current_start_s += gap_s

    return windows

TEST_NAME = "RCF"
# ==================== 生成控制标志 ====================
ONLY_TOPOLOGY = False   # 是否仅生成拓扑文件
ONLY_FLOW = False        # 是否仅生成流量文件（不生成拓扑文件）

# ==================== 网络参数 ====================
BANDWIDTH = "10000000000.0"   # 10 Gbps = 1e10 bps
LINK_DELAY = "10us"            # 10 µs（与论文 §VI-C.1 一致）
ERROR_RATE = "0"

# 节点 ID 分配
NUM_SENDERS = 16
SWITCH_ID = NUM_SENDERS          # 16
RECEIVER_ID = NUM_SENDERS + 1    # 17

# ==================== 流量参数 ====================
PRIORITY = 3                     # 优先级
DST_PORT_BASE = 5000             # 目的端口起始值

# 计算具体数值
link_bps = float(BANDWIDTH)  # 1e10 bps
window_duration = 0.00001      # 10 us = 0.00001 s

# # 流量窗口定义: (起始时间(秒), 结束时间(秒), 流数量, 流类型)
# # 类型 'long' 表示持续长流，使用极大包数；'window' 表示窗口流，使用计算出的包数
# WINDOWS = [
#     (0.0, 0.08, 4, 'long'),      # 长流，持续 80 ms
#     # (0.02, 0.02+window_duration, 10, 'window'),  # 窗口流，2 ms 突发
#     # (0.06, 0.08, 4, 'window'),   # 窗口流，20 ms 窗口
# ]#在长基础流的基础上，额外加入若干个长度为10us的突发流，且每个突发流的开始时间间隔随机化（10~50us），形成高速变换流（Rapid Changing Flow）的场景
# ========== 使用示例 ==========
# 长流：0 ~ 80 ms，4 条长流
total_duration_s = 0.1
long_flow = (0.0, total_duration_s, 4, 'long')

# 生成 20 个突发窗口，每个窗口包含 10 条短流
WINDOWS = generate_rcf_windows(
    long_flow=long_flow,
    burst_flow_options=[4, 8, 16, 12],  # 突发窗口内的额外流数量选项
    burst_count=200,                 # 生成 2000 个突发窗口
    burst_duration_us=10,      # 每个突发窗口持续 10 μs
    min_gap_us=100,
    max_gap_us=500,
    start_offset_us=0.0,       # 第一个突发流从 0 时刻开始
    total_duration_s=total_duration_s
)

# 计算窗口流所需的包数（确保在窗口内可以发完）
# 假设：同时发送的窗口流数量为 N_conc，链路带宽 B bps，包负载大小 pkt_size 字节
# 窗口长度 T_window 秒。为了让所有窗口流在窗口内近乎完成，每个流应发送的数据量 <= (B / N_conc) * T_window
# 我们取安全系数 0.8，并转换为包数。
def compute_window_flow_packets(window_duration_sec, concurrent_flows, link_bps, pkt_payload_bytes=1000):
    # 每个流平均可分带宽 (bps)
    per_flow_bps = link_bps / concurrent_flows
    # 每个流在窗口内可发送的字节数（安全系数 0.8）
    bytes_per_flow = per_flow_bps * window_duration_sec * 0.8 / 8   # 转换为字节
    packets_per_flow = int(bytes_per_flow / pkt_payload_bytes) + 1
    return packets_per_flow

# 窗口流流量乘数
amplifier = 1000
# 第一个窗口流（10 条并发）的包数
pkt_window_10 = amplifier*compute_window_flow_packets(window_duration, 10, link_bps)
# 第二个窗口流（4 条并发）的包数
pkt_window_4 = amplifier*compute_window_flow_packets(window_duration, 4, link_bps)

# 长流包数：极大值（保证仿真期间不会发完）
LONG_FLOW_PACKETS = 1_000_000_000_000   # 10^11，再加个零，10^12


# ==================== 生成拓扑文件 ====================
def generate_topology():
    sender_ids = list(range(NUM_SENDERS))
    link_count = NUM_SENDERS + 1   # 发送->交换机 + 交换机->接收
    total_nodes = NUM_SENDERS + 2  # 16发送+1交换机+1接收=18

    with open(f"topology-{TEST_NAME}.txt", 'w') as f:
        f.write(f"{total_nodes} 1 1 {link_count}\n")
        f.write(f"{SWITCH_ID}\n")
        for src in sender_ids:
            f.write(f"{src} {SWITCH_ID} {BANDWIDTH} {LINK_DELAY} {ERROR_RATE}\n")
        f.write(f"{SWITCH_ID} {RECEIVER_ID} {BANDWIDTH} {LINK_DELAY} {ERROR_RATE}\n")
    print(f"✅ 拓扑文件已生成: topology-{TEST_NAME}.txt")
    print(f"   节点: {total_nodes} (发送端 {NUM_SENDERS}, 交换机 1, 接收端 1)")
    print(f"   链路带宽: {float(BANDWIDTH)/1e9:.0f} Gbps, 延迟: {LINK_DELAY}")

# ==================== 生成流量文件 ====================
def generate_flow():
    flow_entries = []   # 存储 (src, dst, dport, packets, start)
    sender_counter = 0  # 按顺序分配发送端 ID

    for start, end, count, ftype in WINDOWS:
        for i in range(count):
            src = sender_counter % NUM_SENDERS
            sender_counter += 1
            dport = DST_PORT_BASE + src
            if ftype == 'long':
                packets = LONG_FLOW_PACKETS
            else:  # 'window'
                # 根据窗口内并发数量决定包数
                if count == 10:
                    packets = pkt_window_10
                else:
                    packets = pkt_window_4
            flow_entries.append((src, RECEIVER_ID, dport, packets, f"{start:.10f}"))

    # 写入流量文件
    with open(f"flow-{TEST_NAME}-{NUM_SENDERS}to1.txt", 'w') as f:
        f.write(f"{len(flow_entries)}\n")
        for src, dst, dport, packets, start in flow_entries:
            f.write(f"{src} {dst} {PRIORITY} {dport} {packets} {start}\n")

    print(f"✅ 流量文件已生成: flow-{TEST_NAME}-{NUM_SENDERS}to1.txt (共 {len(flow_entries)} 条流)")
    print(f"   - 长流 ({[c for (_,_,c,t) in WINDOWS if t=='long'][0]} 条): 包数 = {LONG_FLOW_PACKETS}")
    # print(f"   - 10 流窗口 (20-40 ms): 包数 = {pkt_window_10}")
    # print(f"   - 4 流窗口 (60-80 ms): 包数 = {pkt_window_4}")

# ==================== 主程序 ====================
if __name__ == "__main__":
    if ONLY_TOPOLOGY:
        generate_topology()
    elif ONLY_FLOW:
        generate_flow()
    else:
        generate_topology()
        generate_flow()