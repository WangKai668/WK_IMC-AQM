# -*- coding: utf-8 -*-
# 高速变换流 RCF 场景的拓扑文件和流量文件
# 配置：
#   - 4 条贯穿长流 (发送机 0~3 → 接收机 17)
#   - 短突发流：发送机 4~15 随机选择，并发度可配置，每个流数据量可配置
#   - 链路 10 Gbps，10 µs 延迟
#   - 每个流使用唯一的 dst_port（自增）

import os
import random

# ==================== 全局配置参数 ====================
TEST_NAME = "RCF"
ONLY_TOPOLOGY = False       # 仅生成拓扑
ONLY_FLOW = True            # 仅生成流量

# ---------- 网络参数 ----------
BANDWIDTH_BPS = 10e9        # 10 Gbps
LINK_DELAY_US = 10          # 10 µs
ERROR_RATE = "0"

# 节点 ID 分配
NUM_SENDERS = 16            # 发送机 0~15
SWITCH_ID = NUM_SENDERS     # 16
RECEIVER_ID = NUM_SENDERS + 1   # 17

# ---------- 流量参数 ----------
PRIORITY = 3
DST_PORT_BASE = 5000        # 起始端口号，之后每个流自增

# 仿真总时长 (秒)
SIMULATION_DURATION_S = 0.02   # 20 ms

# 长流参数：4 条，源 0~3，包数极大（保证仿真期内发不完）
LONG_FLOW_SRCS = [0, 1, 2, 3]
LONG_FLOW_PACKETS = 10**12

# 短流参数
SHORT_FLOW_DATA_BYTES = 0.02 * 1024 * 1024   # 约 20.97 KB 每流
PKT_PAYLOAD_BYTES = 1000                     # 包负载字节数
SHORT_FLOW_PACKETS = (SHORT_FLOW_DATA_BYTES + PKT_PAYLOAD_BYTES - 1) // PKT_PAYLOAD_BYTES

# 突发流参数
BURST_CONCURRENCY_OPTIONS = [4, 8, 12]       # 可选并发度
MIN_GAP_US = 400                             # 突发间最小间隙 (µs)
MAX_GAP_US = 800                             # 突发间最大间隙 (µs)
FIRST_BURST_START_US = 0                     # 第一个突发开始时间 (µs)

AMPLIFIER = 1000

# 短流发送机池（ID 4 ~ 15）
SHORT_SENDER_POOL = list(range(4, NUM_SENDERS))   # [4,5,...,15]

# ==================== 辅助函数 ====================
def bytes_to_bits(bytes_val: float) -> float:
    return bytes_val * 8

def compute_burst_duration_us(concurrency: int) -> float:
    """
    计算一个突发窗口的持续时间 (微秒)
    公式: (总数据量 / 带宽) + 2 * 链路时延
    总数据量 = 并发流数 × 每条流的数据量 (字节)
    """
    total_bits = bytes_to_bits(SHORT_FLOW_DATA_BYTES * concurrency)
    tx_time_us = (total_bits / BANDWIDTH_BPS) * 1e6
    return tx_time_us + 2 * LINK_DELAY_US

# ==================== 生成拓扑文件 ====================
def generate_topology():
    sender_ids = list(range(NUM_SENDERS))
    link_count = NUM_SENDERS + 1   # 发送→交换 + 交换→接收
    total_nodes = NUM_SENDERS + 2  # 16发送 + 1交换 + 1接收 = 18

    bandwidth_str = f"{BANDWIDTH_BPS:.1f}"
    delay_str = f"{LINK_DELAY_US}us"

    with open(f"topology-{TEST_NAME}.txt", 'w') as f:
        f.write(f"{total_nodes} 1 1 {link_count}\n")
        f.write(f"{SWITCH_ID}\n")
        for src in sender_ids:
            f.write(f"{src} {SWITCH_ID} {bandwidth_str} {delay_str} {ERROR_RATE}\n")
        f.write(f"{SWITCH_ID} {RECEIVER_ID} {bandwidth_str} {delay_str} {ERROR_RATE}\n")

    print(f"✅ 拓扑文件已生成: topology-{TEST_NAME}.txt")
    print(f"   节点: {total_nodes} (发送端 {NUM_SENDERS}, 交换机 1, 接收端 1)")
    print(f"   链路带宽: {BANDWIDTH_BPS/1e9:.0f} Gbps, 延迟: {delay_str}")

# ==================== 生成流量文件 ====================
def generate_flow():
    flow_list = []                      # 存储 (src, dst, dport, packets, start)
    current_dport = DST_PORT_BASE       # 端口自增起始

    # ---- 1. 添加 4 条贯穿长流（使用唯一端口）----
    for src in LONG_FLOW_SRCS:
        flow_list.append((src, RECEIVER_ID, current_dport, LONG_FLOW_PACKETS, 0.0))
        current_dport += 1

    # ---- 2. 生成短突发流（每个流也分配唯一端口）----
    current_time_us = FIRST_BURST_START_US
    sim_duration_us = SIMULATION_DURATION_S * 1e6
    burst_index = 0
    random.seed(42)   # 可重现

    while current_time_us < sim_duration_us:
        concurrency = random.choice(BURST_CONCURRENCY_OPTIONS)
        if concurrency > len(SHORT_SENDER_POOL):
            print(f"⚠️ 警告: 并发数 {concurrency} 超过可用短流发送机数量 {len(SHORT_SENDER_POOL)}，跳过此突发")
            break
        selected_srcs = random.sample(SHORT_SENDER_POOL, concurrency)

        burst_dur_us = compute_burst_duration_us(concurrency)
        if current_time_us + burst_dur_us > sim_duration_us:
            print(f"⏹️ 仿真时间不足，停止生成新突发 (当前时间 {current_time_us:.1f} µs)")
            break

        start_sec = current_time_us / 1e6
        for src in selected_srcs:
            flow_list.append((src, RECEIVER_ID, current_dport, SHORT_FLOW_PACKETS*AMPLIFIER, start_sec))
            current_dport += 1

        current_time_us += burst_dur_us + random.uniform(MIN_GAP_US, MAX_GAP_US)
        burst_index += 1

    print(f"✅ 生成 {burst_index} 个突发窗口，共 {len(flow_list) - len(LONG_FLOW_SRCS)} 条短流")
    print(f"   使用的端口范围: {DST_PORT_BASE} ~ {current_dport-1}")

    # ---- 3. 写入流量文件 ----
    flow_file = f"flow-{TEST_NAME}-{NUM_SENDERS}to1.txt"
    with open(flow_file, 'w') as f:
        f.write(f"{len(flow_list)}\n")
        for src, dst, dport, packets, start in flow_list:
            f.write(f"{src} {dst} {PRIORITY} {dport} {int(packets)} {start:.10f}\n")

    print(f"✅ 流量文件已生成: {flow_file} (共 {len(flow_list)} 条流)")
    print(f"   - 长流: {len(LONG_FLOW_SRCS)} 条, 包数 = {LONG_FLOW_PACKETS}")
    print(f"   - 短流: 每条数据量 {SHORT_FLOW_DATA_BYTES//1024} KB, 包数 = {SHORT_FLOW_PACKETS*AMPLIFIER}")
    print(f"   - 突发并发选项: {BURST_CONCURRENCY_OPTIONS}, 间隙范围: {MIN_GAP_US}~{MAX_GAP_US} µs")

# ==================== 主程序 ====================
if __name__ == "__main__":
    if ONLY_TOPOLOGY:
        generate_topology()
    elif ONLY_FLOW:
        generate_flow()
    else:
        generate_topology()
        generate_flow()