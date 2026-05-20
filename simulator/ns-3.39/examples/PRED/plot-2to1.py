import re
import argparse
import matplotlib.pyplot as plt

def parse_args():
    p = argparse.ArgumentParser(description="Plot IMC-AQM logs (2to1)")
    p.add_argument("--alg", default="RED", help="Algorithm name, e.g., RED/PIE/CoDel (default: RED)")
    p.add_argument("--dump-dir", default="dump_2to1", help="Directory containing log and outputs (default: dump_2to1)")
    p.add_argument("--low-cut-ms", type=float, default=0, help="Low cut threshold in milliseconds (default: 0)")
    p.add_argument("--high-cut-ms", type=float, default=float('inf'), help="High cut threshold in milliseconds (default: inf)")
    p.add_argument("--step", type=int, default=100, help="Sampling step for plotting (default: 100)")
    p.add_argument("--master-id", default="17", help="Master node ID for queue length parsing (default: 17, means 16 to 1)")   
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

#不稳定区域截断
#把low_cut毫秒以下的内容截断，不包含low_cut本身
# low_cut = 0#不截断
low_cut = 10#截断10ms
high_cut = 15#截断15ms以上
# high_cut = float('inf')#不截断

#采样间隔
step = 100
#主机id
# master_id = "17"#16打1
master_id = "21"#20打1

# 命令行优先级高于内部配置
low_cut = args.low_cut_ms
high_cut = args.high_cut_ms
step = args.step
master_id = args.master_id

# SID="0b000201" #默认发送端口
SID="0b000101"

#----------------是否截断不稳定区域----------------
cut_ecn = True
cut_rate = True
cut_alpha = True
cut_queue = True
cut_actual = True
#-------------------------------------------------

# 解析日志文件
with open(log_file, "r") as file:
    for line in file:
        # 匹配 ECN 标记
        ecn_match = re.search(r"(\d+) SwitchMMU:ShouldSendCN .* ifMarked 1", line)
        if ecn_match:
            if cut_ecn:
                time_temp = int(ecn_match.group(1)) / 1e6  # 转换时间单位 ns -> ms
                if time_temp >= low_cut and time_temp <= high_cut:  # 截断不稳定的区域
                    time_ecn.append(time_temp)  # 转换时间单位 ns -> ms
            else:
                time_ecn.append(int(ecn_match.group(1)) / 1e6)  # 转换时间单位 ns -> ms

        # 匹配发送速率变化
        rate_match = re.search(r"(\d+) (DCTCP|DCQCN)-rate-(increase|decrease) "+SID+r" .* (\d+\.\d+)->(\d+\.\d+)", line)
        if rate_match:
            if cut_rate:
                time_temp = int(rate_match.group(1)) / 1e6  # 转换时间单位 ns -> ms
                if time_temp >= low_cut and time_temp <= high_cut:  # 截断不稳定的区域
                    time_rate.append(time_temp)  # 转换时间单位 ns -> ms
                    rate_values.append(float(rate_match.group(5)))  # 使用目标速率
            else:
                time_rate.append(int(rate_match.group(1)) / 1e6)  # 转换时间单位 ns -> ms
                rate_values.append(float(rate_match.group(5)))  # 使用目标速率

        # 匹配 alpha 值变化
        alpha_match = re.search(r"(\d+) (DCTCP|DCQCN)-alpha "+SID+r" .* (\d+\.\d+)->(\d+\.\d+)", line)
        if alpha_match:
            if cut_alpha:
                time_temp = int(alpha_match.group(1)) / 1e6  # 转换时间单位 ns -> ms
                if time_temp >= low_cut and time_temp <= high_cut:  # 截断不稳定的区域
                    time_alpha.append(time_temp)  # 转换时间单位 ns -> ms
                    alpha_values.append(float(alpha_match.group(4)))
            else:
                time_alpha.append(int(alpha_match.group(1)) / 1e6)  # 转换时间单位 ns -> ms
                alpha_values.append(float(alpha_match.group(4)))

        # 匹配队列长度变化  来自master_id（接收机）
        queue_match = re.search(r"(\d+) SwitchMMU:ShouldSendCN  ifindex "+master_id+r" .* egress_bytes (\d+)", line)
        if queue_match:
            if cut_queue:
                time_temp = int(queue_match.group(1)) / 1e6  # 转换时间单位 ns -> ms
                if time_temp >= low_cut and time_temp <= high_cut:  # 截断不稳定的区域
                    time_queue.append(time_temp)  # 转换时间单位 ns -> ms
                    queue_lengths.append(int(queue_match.group(2)) / 1024)  # 转换单位 bytes -> KB
            else:
                time_queue.append(int(queue_match.group(1)) / 1e6)  # 转换时间单位 ns -> ms
                queue_lengths.append(int(queue_match.group(2)) / 1024)  # 转换单位 bytes -> KB

        # 匹配实际发送速率
        actual_match = re.search(r"(\d+) ActualSendingRate:  node: 2 Rate\(Gbps\): (\d+\.\d+)", line)
        if actual_match:
            if cut_actual:
                time_temp = int(actual_match.group(1)) / 1e6  # 转换时间单位 ns -> ms
                if time_temp >= low_cut and time_temp <= high_cut:  # 截断不稳定的区域
                    time_actual.append(time_temp)  # 转换时间单位 ns -> ms
                    actual_rate.append(float(actual_match.group(2)))
            else:
                time_actual.append(int(actual_match.group(1)) / 1e6)  # ns -> ms
                actual_rate.append(float(actual_match.group(2)))

print(f"ecn_match count: {len(time_ecn)}, first: {time_ecn[0] if time_ecn else 'None'}, values: {time_ecn[:5] if time_ecn else 'None'}")
print(f"rate_match count: {len(time_rate)}, first: {time_rate[0] if time_rate else 'None'}, values: {rate_values[:5] if rate_values else 'None'}")
print(f"alpha_match count: {len(time_alpha)}, first: {time_alpha[0] if time_alpha else 'None'}, values: {alpha_values[:5] if alpha_values else 'None'}")
print(f"queue_match count: {len(time_queue)}, first: {time_queue[0] if time_queue else 'None'}, values: {queue_lengths[:5] if queue_lengths else 'None'}")
print(f"actual_match count: {len(time_actual)}, first: {time_actual[0] if time_actual else 'None'}, values: {actual_rate[:5] if actual_rate else 'None'}")

# 绘制第一个图：ECN 标记、发送速率和 alpha 值
fig, ax1 = plt.subplots(figsize=(12, 6))

ax1.set_xlabel("Time (ms)")
ax1.set_ylabel("Send Rate (Gbps)", color="blue")
# 实现间隔性采样，此处不采用
# ax1.plot(time_rate[::step], rate_values[::step], marker="o", linestyle="-", color="blue", label="Send Rate (Gbps)")
ax1.plot(time_rate, rate_values, marker="o", linestyle="-", color="blue", label="Send Rate (Gbps)")
ax1.tick_params(axis="y", labelcolor="blue")
# 实现间隔性采样，此处不采用
# ax1.plot(time_actual[::step], actual_rate[::step], linestyle="-", color="red", linewidth=1.8, label="Actual Sending Rate (Gbps)")
ax1.plot(time_actual, actual_rate, linestyle="-", color="red", linewidth=1.8, label="Actual Sending Rate (Gbps)")

ax1.plot(time_ecn, [0]*len(time_ecn), '|', color="black", markersize=15, markeredgewidth=1.5, alpha=0.5, label="CNP Received")

handles, labels = ax1.get_legend_handles_labels()
unique_labels = dict(zip(labels, handles))
ax1.legend(unique_labels.values(), unique_labels.keys())

ax2 = ax1.twinx()
ax2.set_ylabel("Alpha Value", color="green")
# 实现间隔性采样，此处不采用
# ax2.plot(time_alpha[::step], alpha_values[::step], marker="o", linestyle="-", color="green", label="Alpha Value")
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
# 实现间隔性采样
plt.plot(time_queue[::step], queue_lengths[::step], marker="o", linestyle="-", color="orange", label="Queue Length (KB)")
# plt.plot(time_queue, queue_lengths, marker="o", linestyle="-", color="orange", label="Queue Length (KB)")
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