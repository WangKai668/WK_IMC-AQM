# -*- coding: utf-8 -*-
# SIF (Sustain+Incast Flow) 场景的拓扑文件和流量文件
# 支持多种配置：背景流数量、多个 incast 突发阶段
# 拓扑：64 发送机 (0~63) -> 交换机 (64) -> 接收机 (65)
# 链路：10 Gbps，10 µs 延迟

import os
from typing import Dict, Any, List

# ==================== 全局配置参数 ====================
TEST_NAME = "SIF"
ONLY_TOPOLOGY = False
ONLY_FLOW = False

# ---------- 网络参数 ----------
BANDWIDTH_BPS_DCTCP = 10e9        # 10 Gbps
LINK_DELAY_US_DCTCP = 10          # 10 µs

BANDWIDTH_BPS_DCQCN = 40e9        # 40 Gbps
LINK_DELAY_US_DCQCN = 5           # 5 µs

ERROR_RATE = "0"

NUM_SENDERS = 64
SWITCH_ID = NUM_SENDERS
RECEIVER_ID = NUM_SENDERS + 1

# ---------- 流量参数 ----------
PRIORITY = 3
DST_PORT_BASE = 5000

LONG_FLOW_PACKETS = 10**12
PKT_PAYLOAD_BYTES = 1000

BURST_SIZE_1RTT = 5*1e4#4*10us[rtt] * 10Gbps = 40/1e6[us->s] * 10Gbps = 4*1e-4 Gbps
                    #= 4/8[b->B] * 1e-4 * 1e9(K3 M6 G9)=0.5*1e5=5*1e4
                    # 约等于50KB

AMPLIFIER  = 1e3*10

def bytes_to_bits(b: float) -> float:
    return b * 8

def compute_incast_duration_us(concurrency: int, bytes_per_flow: int) -> float:
    total_bits = bytes_to_bits(bytes_per_flow * concurrency)
    tx_time_us = (total_bits / BANDWIDTH_BPS_DCTCP) * 1e6
    return tx_time_us + 2 * LINK_DELAY_US_DCTCP

# ==================== 流量配置 ====================
CONFIGURATIONS = {
    "N4_burst0": {
        "background": {"N": 4, "size_bytes": None},
        "stages": []
    },
    "N4_burst2_small_large": {
        "background": {"N": 4, "size_bytes": None},
        "stages": [
            {"wait_us": 4000, "incast": {"N": 2, "size_bytes": BURST_SIZE_1RTT}},
            {"wait_us": 4000, "incast": {"N": 10, "size_bytes": BURST_SIZE_1RTT}}
        ]
    },
    "N20_burst0": {
        "background": {"N": 20, "size_bytes": None},
        "stages": []
    },
    "N20_burst2_small_large": {
        "background": {"N": 20, "size_bytes": None},
        "stages": [
            {"wait_us": 4000, "incast": {"N": 2, "size_bytes": BURST_SIZE_1RTT}},
            {"wait_us": 4000, "incast": {"N": 10, "size_bytes": BURST_SIZE_1RTT}}
        ]
    },
    "N10_burst0": {
        "background": {"N": 10, "size_bytes": None},
        "stages": []
    }
}

SELECTED_CONFIG = "N4_burst2_small_large"

# ==================== 生成拓扑 ====================
def generate_topology_for_DCTCP():
    sender_ids = list(range(NUM_SENDERS))
    link_count = NUM_SENDERS + 1
    total_nodes = NUM_SENDERS + 2
    bandwidth_str = f"{BANDWIDTH_BPS_DCTCP:.1f}"
    delay_str = f"{LINK_DELAY_US_DCTCP}us"

    with open(f"topology-{TEST_NAME}-DCTCP.txt", 'w') as f:
        f.write(f"{total_nodes} 1 1 {link_count}\n")
        f.write(f"{SWITCH_ID}\n")
        for src in sender_ids:
            f.write(f"{src} {SWITCH_ID} {bandwidth_str} {delay_str} {ERROR_RATE}\n")
        f.write(f"{SWITCH_ID} {RECEIVER_ID} {bandwidth_str} {delay_str} {ERROR_RATE}\n")

    print(f"✅ 拓扑文件已生成: topology-{TEST_NAME}-DCTCP.txt")

def generate_topology_for_DCQCN():
    sender_ids = list(range(NUM_SENDERS))
    link_count = NUM_SENDERS + 1
    total_nodes = NUM_SENDERS + 2
    bandwidth_str = f"{BANDWIDTH_BPS_DCQCN:.1f}"
    delay_str = f"{LINK_DELAY_US_DCQCN}us"

    with open(f"topology-{TEST_NAME}-DCQCN.txt", 'w') as f:
        f.write(f"{total_nodes} 1 1 {link_count}\n")
        f.write(f"{SWITCH_ID}\n")
        for src in sender_ids:
            f.write(f"{src} {SWITCH_ID} {bandwidth_str} {delay_str} {ERROR_RATE}\n")
        f.write(f"{SWITCH_ID} {RECEIVER_ID} {bandwidth_str} {delay_str} {ERROR_RATE}\n")

    print(f"✅ 拓扑文件已生成: topology-{TEST_NAME}-DCQCN.txt")

# ==================== 生成流量 ====================
def generate_flow(config: Dict[str, Any], config_name: str):
    flow_list = []
    current_dport = DST_PORT_BASE

    bg_cfg = config["background"]
    bg_N = bg_cfg["N"]
    bg_size_bytes = bg_cfg["size_bytes"]

    # 背景流
    if bg_size_bytes is None:
        bg_packets = LONG_FLOW_PACKETS
    else:
        bg_packets = (bg_size_bytes + PKT_PAYLOAD_BYTES - 1) // PKT_PAYLOAD_BYTES

    for src in range(bg_N):
        flow_list.append((src, RECEIVER_ID, current_dport, bg_packets, 0.0))
        current_dport += 1

    stages = config.get("stages", [])
    if not stages:
        total_duration_us = 20 * 1000   # 无突发时默认20ms
    else:
        prev_end_time_us = 0.0
        incast_start_id = max(bg_N, 4)   # 保证从4开始
        for stage in stages:
            wait_us = stage["wait_us"]
            incast_cfg = stage["incast"]
            incast_N = incast_cfg["N"]
            incast_bytes = incast_cfg["size_bytes"]

            start_us = prev_end_time_us + wait_us
            duration_us = compute_incast_duration_us(incast_N, incast_bytes)
            start_sec = start_us / 1e6

            if incast_start_id + incast_N - 1 >= NUM_SENDERS:
                print(f"⚠️ incast 源不足，跳过剩余阶段")
                break
            src_list = list(range(incast_start_id, incast_start_id + incast_N))
            incast_start_id += incast_N

            incast_packets = (incast_bytes + PKT_PAYLOAD_BYTES - 1) // PKT_PAYLOAD_BYTES
            for src in src_list:
                flow_list.append((src, RECEIVER_ID, current_dport, incast_packets*AMPLIFIER, start_sec))
                current_dport += 1

            prev_end_time_us = start_us + duration_us

        total_duration_us = prev_end_time_us + 1000   # 余量1ms

    total_duration_s = total_duration_us / 1e6
    print(f"仿真总时长: {total_duration_s:.3f} s")

    flow_file = f"flow-{TEST_NAME}-{config_name}.txt"
    with open(flow_file, 'w') as f:
        f.write(f"{len(flow_list)}\n")
        for src, dst, dport, packets, start in flow_list:
            f.write(f"{src} {dst} {PRIORITY} {dport} {int(packets)} {start:.10f}\n")

    print(f"✅ 流量文件已生成: {flow_file} (共 {len(flow_list)} 条流)")

# ==================== 主程序 ====================
if __name__ == "__main__":
    if ONLY_TOPOLOGY:
        generate_topology_for_DCTCP()
        generate_topology_for_DCQCN()
    elif ONLY_FLOW:
        if SELECTED_CONFIG not in CONFIGURATIONS:
            print(f"错误：配置 '{SELECTED_CONFIG}' 不存在")
        else:
            generate_flow(CONFIGURATIONS[SELECTED_CONFIG], SELECTED_CONFIG)
    else:
        generate_topology_for_DCTCP()
        generate_topology_for_DCQCN()
        # generate_flow(CONFIGURATIONS[SELECTED_CONFIG], SELECTED_CONFIG)
        for flow in CONFIGURATIONS.keys():
            generate_flow(CONFIGURATIONS[flow],flow)