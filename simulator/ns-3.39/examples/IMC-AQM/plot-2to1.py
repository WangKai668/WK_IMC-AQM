import re
import argparse
import matplotlib.pyplot as plt

def parse_args():
    p = argparse.ArgumentParser(description="Plot IMC-AQM logs (2to1)")
    p.add_argument("--alg", default="RED", help="Algorithm name, e.g., RED/PIE/CoDel (default: RED)")
    p.add_argument("--dump-dir", default="dump_2to1", help="Directory containing log and outputs (default: dump_2to1)")
    return p.parse_args()

args = parse_args()

# 文件路径（可被 --log 覆盖）
log_file = f"{args.dump_dir}/evaluation-{args.alg}.out"

# 初始化数据存储
time_ecn = []

# qp发送速率
time_rate = []
rate_values = []

# 实际发送速率
time_actual = []
actual_rate = []

# qp alpha值
time_alpha = []
alpha_values = []

# 交换机端口队列长度
time_queue = []
queue_lengths = []

# 解析日志文件
with open(log_file, "r") as file:
    for line in file:
        # 匹配 ECN 标记
        ecn_match = re.search(r"(\d+) SwitchMMU:ShouldSendCN .* ifMarked 1", line)
        if ecn_match:
            time_ecn.append(int(ecn_match.group(1)) / 1e6)  # 转换时间单位 ns -> ms

        # 匹配发送速率变化
        rate_match = re.search(r"(\d+) (DCTCP|DCQCN)-rate-(increase|decrease) 0b000201 .* (\d+\.\d+)->(\d+\.\d+)", line)
        if rate_match:
            time_rate.append(int(rate_match.group(1)) / 1e6)  # 转换时间单位 ns -> ms
            rate_values.append(float(rate_match.group(5)))  # 使用目标速率

        # 匹配 alpha 值变化
        alpha_match = re.search(r"(\d+) (DCTCP|DCQCN)-alpha 0b000201 .* (\d+\.\d+)->(\d+\.\d+)", line)
        if alpha_match:
            time_alpha.append(int(alpha_match.group(1)) / 1e6)  # 转换时间单位 ns -> ms
            alpha_values.append(float(alpha_match.group(4)))

        # 匹配队列长度变化
        queue_match = re.search(r"(\d+) SwitchMMU:ShouldSendCN  ifindex 1 .* egress_bytes (\d+)", line)
        if queue_match:
            time_queue.append(int(queue_match.group(1)) / 1e6)  # 转换时间单位 ns -> ms
            queue_lengths.append(int(queue_match.group(2)) / 1024)  # 转换单位 bytes -> KB

        # 匹配实际发送速率
        actual_match = re.search(r"(\d+) ActualSendingRate:  node: 2 Rate\(Gbps\): (\d+\.\d+)", line)
        if actual_match:
            time_actual.append(int(actual_match.group(1)) / 1e6)  # ns -> ms
            actual_rate.append(float(actual_match.group(2)))

# 绘制第一个图：ECN 标记、发送速率和 alpha 值
fig, ax1 = plt.subplots(figsize=(12, 6))

ax1.set_xlabel("Time (ms)")
ax1.set_ylabel("Send Rate (Gbps)", color="blue")
ax1.plot(time_rate, rate_values, marker="o", linestyle="-", color="blue", label="Send Rate (Gbps)")
ax1.tick_params(axis="y", labelcolor="blue")
ax1.plot(time_actual, actual_rate, linestyle="-", color="red", linewidth=1.8, label="Actual Sending Rate (Gbps)")

ax1.plot(time_ecn, [0]*len(time_ecn), '|', color="black", markersize=15, markeredgewidth=1.5, alpha=0.5, label="CNP Received")

handles, labels = ax1.get_legend_handles_labels()
unique_labels = dict(zip(labels, handles))
ax1.legend(unique_labels.values(), unique_labels.keys())

ax2 = ax1.twinx()
ax2.set_ylabel("Alpha Value", color="green")
ax2.plot(time_alpha, alpha_values, marker="o", linestyle="-", color="green", label="Alpha Value")
ax2.tick_params(axis="y", labelcolor="green")

fig.suptitle(f"({args.alg}) ECN Marked, Send Rate, and Alpha Value Over Time")
fig.tight_layout()

# 保存第一个图
output_file_1 = f"{args.dump_dir}/output_ecn_rate_alpha-{args.alg}.png"
plt.savefig(output_file_1, dpi=300)
print(f"Plot saved to {output_file_1}")
plt.show()

# 绘制第二个图：交换机端口队列长度
plt.figure(figsize=(12, 6))
plt.plot(time_queue, queue_lengths, marker="o", linestyle="-", color="orange", label="Queue Length (KB)")
plt.xlabel("Time (ms)")
plt.ylabel("Queue Length (KB)")
plt.title(f"({args.alg}) Switch Port Queue Length Over Time")
plt.legend()

output_file_2 = f"{args.dump_dir}/output_queue_length-{args.alg}.png"
plt.savefig(output_file_2, dpi=300)
print(f"Plot saved to {output_file_2}")
plt.show()

# 保存统计数据到文件
output_prefix = f"{args.dump_dir}/evaluation-{args.alg}"

with open(f"{output_prefix}-time_ecn.txt", "w") as f:
    for t in time_ecn:
        f.write(f"{t}\n")

with open(f"{output_prefix}-time_rate.txt", "w") as f:
    for t, rate in zip(time_rate, rate_values):
        f.write(f"{t},{rate}\n")

with open(f"{output_prefix}-time_alpha.txt", "w") as f:
    for t, alpha in zip(time_alpha, alpha_values):
        f.write(f"{t},{alpha}\n")

with open(f"{output_prefix}-time_queue.txt", "w") as f:
    for t, length in zip(time_queue, queue_lengths):
        f.write(f"{t},{length}\n")

print(f"All statistics have been saved to files with prefix '{output_prefix}'.")