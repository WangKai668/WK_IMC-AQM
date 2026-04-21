import re
import argparse
import glob
import os
import matplotlib.pyplot as plt

# 遍历所有算法（dump 目录里存在的 evaluation-*.out）：
# python3 plot-evaluation.py --dump dump_2to1
# 只画一个：
# python3 plot-evaluation.py --dump dump_2to1 --alg RED


def parse_args():
    p = argparse.ArgumentParser(description="Plot IMC-AQM logs")
    p.add_argument("--alg", default=None, help="Algorithm name (e.g., RED/CoDel). If omitted, plot all found in dump dir.")
    p.add_argument("--dump", default="dump_2to1", help="Directory containing log and outputs (default: dump_2to1)")
    return p.parse_args()

args = parse_args()

def parse_and_plot_one(alg: str, dump_dir: str) -> bool:
    log_file = f"{dump_dir}/evaluation-{alg}.out"
    if not os.path.exists(log_file):
        print(f"[skip] log not found: {log_file}")
        return False

    time_ecn = []
    time_rate, rate_values = [], []
    time_actual, actual_rate = [], []
    time_alpha, alpha_values = [], []
    time_queue, queue_lengths = [], []

    with open(log_file, "r") as file:
        for line in file:
            ecn_match = re.search(r"(\d+) SwitchMMU:ShouldSendCN .* ifMarked 1", line)
            if ecn_match:
                time_ecn.append(int(ecn_match.group(1)) / 1e6)

            rate_match = re.search(r"(\d+) (DCTCP|DCQCN)-rate-(increase|decrease) 0b000201 .* (\d+\.\d+)->(\d+\.\d+)", line)
            if rate_match:
                time_rate.append(int(rate_match.group(1)) / 1e6)
                rate_values.append(float(rate_match.group(5)))

            alpha_match = re.search(r"(\d+) (DCTCP|DCQCN)-alpha 0b000201 .* (\d+\.\d+)->(\d+\.\d+)", line)
            if alpha_match:
                time_alpha.append(int(alpha_match.group(1)) / 1e6)
                alpha_values.append(float(alpha_match.group(4)))

            queue_match = re.search(r"(\d+) SwitchMMU:ShouldSendCN  ifindex 1 .* egress_bytes (\d+)", line)
            if queue_match:
                time_queue.append(int(queue_match.group(1)) / 1e6)
                queue_lengths.append(int(queue_match.group(2)) / 1024)

            actual_match = re.search(r"(\d+) ActualSendingRate:  node: 2 Rate\(Gbps\): (\d+\.\d+)", line)
            if actual_match:
                time_actual.append(int(actual_match.group(1)) / 1e6)
                actual_rate.append(float(actual_match.group(2)))

    # 图1：ECN + rate + alpha
    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax1.set_xlabel("Time (ms)")
    ax1.set_ylabel("Send Rate (Gbps)", color="blue")
    if time_rate:
        ax1.plot(time_rate, rate_values, marker="o", linestyle="-", color="blue", label="Send Rate (Gbps)")
    if time_actual:
        ax1.plot(time_actual, actual_rate, linestyle="-", color="red", linewidth=1.8, label="Actual Sending Rate (Gbps)")
    if time_ecn:
        ax1.plot(time_ecn, [0]*len(time_ecn), '|', color="black", markersize=15, markeredgewidth=1.5, alpha=0.5, label="CNP Received")
    ax1.tick_params(axis="y", labelcolor="blue")

    handles, labels = ax1.get_legend_handles_labels()
    if labels:
        unique_labels = dict(zip(labels, handles))
        ax1.legend(unique_labels.values(), unique_labels.keys())

    ax2 = ax1.twinx()
    ax2.set_ylabel("Alpha Value", color="green")
    if time_alpha:
        ax2.plot(time_alpha, alpha_values, marker="o", linestyle="-", color="green", label="Alpha Value")
    ax2.tick_params(axis="y", labelcolor="green")

    fig.suptitle(f"({alg}) ECN Marked, Send Rate, and Alpha Value Over Time")
    fig.tight_layout()

    output_file_1 = f"{dump_dir}/output_ecn_rate_alpha-{alg}.png"
    plt.savefig(output_file_1, dpi=300)
    print(f"[ok] saved: {output_file_1}")
    plt.close(fig)

    # 图2：队列长度
    fig2 = plt.figure(figsize=(12, 6))
    if time_queue:
        plt.plot(time_queue, queue_lengths, marker="o", linestyle="-", color="orange", label="Queue Length (KB)")
    plt.xlabel("Time (ms)")
    plt.ylabel("Queue Length (KB)")
    plt.title(f"({alg}) Switch Port Queue Length Over Time")
    plt.legend()

    output_file_2 = f"{dump_dir}/output_queue_length-{alg}.png"
    plt.savefig(output_file_2, dpi=300)
    print(f"[ok] saved: {output_file_2}")
    plt.close(fig2)

    return True

def discover_algs(dump_dir: str):
    paths = glob.glob(os.path.join(dump_dir, "evaluation-*.out"))
    algs = []
    for pth in sorted(paths):
        base = os.path.basename(pth)
        # evaluation-XXX.out
        m = re.match(r"evaluation-(.+)\.out$", base)
        if m:
            algs.append(m.group(1))
    return algs

if args.alg:
    parse_and_plot_one(args.alg, args.dump)
else:
    algs = discover_algs(args.dump)
    if not algs:
        print(f"[error] no logs found: {args.dump}/evaluation-*.out")
        raise SystemExit(2)

    for alg in algs:
        parse_and_plot_one(alg, args.dump)