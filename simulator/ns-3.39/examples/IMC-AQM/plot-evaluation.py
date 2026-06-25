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
    p.add_argument("--dump", default="dump_2to1_burst", help="Directory containing log and outputs (default: dump_2to1)")
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

    # IMCAQM extra series
    time_qhat, qhat_kb = [], []
    time_error, error_kb = [], []          # <-- add: Error_t series (KB)
    time_state, state_values = [], []  # STEADY=1, BURST=2, RECOVER=3
    

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

                        # -------- IMCAQM parsing (only when plotting IMCAQM) --------
            if alg == "IMCAQM":
                # period1 line: grab Qhat_t
                # Example:
                # 2217207 SwitchMMU:IMCAQM_PeriodControl_1_burstDistinguish ... Qhat_t 38.529 ...
                m_p1 = re.search(
                    r"(\d+)\s+SwitchMMU:IMCAQM_PeriodControl_1_burstDistinguish\b.*\bQhat_t\s+([0-9]+(?:\.[0-9]+)?)\b.*\bError_t\s+([0-9]+(?:\.[0-9]+)?)\b",
                    line,
                )
                if m_p1:
                    t_ms = int(m_p1.group(1)) / 1e6
                    time_qhat.append(t_ms)
                    qhat_kb.append(float(m_p1.group(2)))    # already KB in log
                    time_error.append(t_ms)
                    error_kb.append(float(m_p1.group(3)))   # already KB in log
                    continue

                # period2 line: grab new state after "=>>new:"
                # Example:
                # 2217207 SwitchMMU:IMCAQM_PeriodControl_2_stateSwitching  Aqm_state BURST =>>new: BURST    T_next 2040
                m_state = re.search(
                    r"(\d+)\s+SwitchMMU:IMCAQM_PeriodControl_2_stateSwitching\b.*=>>new:\s+(STEADY|BURST|RECOVER)\b",
                    line,
                )
                if m_state:
                    state_str = m_state.group(2)
                    state_map = {"STEADY": 1, "BURST": 2, "RECOVER": 3}
                    time_state.append(int(m_state.group(1)) / 1e6)
                    state_values.append(state_map[state_str])
                    continue

    # 图1：ECN + rate + alpha
    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax1.set_xlabel("Time (ms)")
    # ax1.set_xlim(0,12)
    # ax1.set_ylim(18,22)
    ax1.set_ylabel("Send Rate (Gbps)", color="blue")
    if time_rate:
        ax1.plot(time_rate, rate_values, marker="o", linestyle="-", color="blue", label="Send Rate (Gbps)")
    if time_actual:
        ax1.plot(time_actual, actual_rate, linestyle="-", color="red", linewidth=1.8, label="Actual Sending Rate (Gbps)")
    if time_ecn:
        ax1.plot(time_ecn, [20]*len(time_ecn), '|', color="black", markersize=15, markeredgewidth=1.5, alpha=0.5, label="CNP Received")
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
    fig2, axq = plt.subplots(figsize=(12, 6))
    if time_queue:
        axq.plot(time_queue, queue_lengths, marker="o", linestyle="-", color="orange", label="Queue Length (KB)")
    
    if alg == "IMCAQM":
        # Qhat_t overlay on y1
        if time_qhat:
            axq.plot(time_qhat, qhat_kb, marker=".", linestyle="--", color="purple", linewidth=1.5, label="Qhat_t (KB)")

        # Error_t overlay on y1
        if time_error:
            axq.plot(time_error, error_kb, marker="x", linestyle=":", color="brown", linewidth=1.3, label="Error_t (KB)")

    axq.set_xlabel("Time (ms)")
    axq.set_ylabel("Queue Length (KB)")
    # axq.set_ylim(0, 500)
    # axq.set_xlim(0, 12)
    axq.set_title(f"({alg}) Switch Port Queue Length Over Time")

     # State on y2 (STEADY=1, BURST=2, RECOVER=3)
    if alg == "IMCAQM" and time_state:
        axq2 = axq.twinx()
        axq2.plot(time_state, state_values, marker="o", linestyle="-", color="steelblue", linewidth=1.2, label="IMCAQM State")
        axq2.set_ylabel("IMCAQM State (1=STEADY, 2=BURST, 3=RECOVER)")
        axq2.set_yticks([1, 2, 3])
        axq2.set_ylim(0.5, 3.5)

        # merge legends from both axes
        h1, l1 = axq.get_legend_handles_labels()
        h2, l2 = axq2.get_legend_handles_labels()
        if l1 or l2:
            uniq = dict(zip(l1 + l2, h1 + h2))
            axq.legend(uniq.values(), uniq.keys(), loc="upper right")
    else:
        axq.legend(loc="upper right")

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