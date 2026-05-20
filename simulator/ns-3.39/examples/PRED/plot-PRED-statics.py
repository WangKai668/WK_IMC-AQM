import re
from typing import Dict, Any, List, Tuple, Callable, Optional, Union
import matplotlib.pyplot as plt
import argparse
import os

def parse_args():
    p = argparse.ArgumentParser(description="Plot IMC-AQM logs (2to1)")
    p.add_argument("--alg", default="RED", help="Algorithm name, e.g., RED/PIE/CoDel (default: RED)")
    p.add_argument("--dump-dir", default="dump_2to1", help="Directory containing log and outputs (default: dump_2to1)")
    p.add_argument("--low-cut-ms", type=float, default=0, help="Low cut threshold in milliseconds (default: 0)")
    p.add_argument("--high-cut-ms", type=float, default=float('inf'), help="High cut threshold in milliseconds (default: inf)")
    p.add_argument("--step", type=int, default=100, help="Sampling step for plotting (default: 100)")
    p.add_argument("--master-id", default="17", help="Master node ID for queue length parsing (default: 17, means 16 to 1)")
    p.add_argument("--queue", default="3", help="Queue number for parsing (default: 3)")
    return p.parse_args()

args = parse_args()

#  根目录
dump_dir = args.dump_dir
# 文件路径（可被 --log 覆盖）
log_file = f"{args.dump_dir}/evaluation-{args.alg}.out"


# ===================== 各种参数 =======================
low_cut_ms = 0 #低切毫秒数
high_cut_ms = float('inf') #高切毫秒数
step = 1       #步长采样，每隔 step 条保留一条
port = 17      #接收端端口号，也基本上是接收端主机编号
queue = 3      #接收端队列号，也基本上是流量的优先级 

# 命令行优先级更高
low_cut_ms = args.low_cut_ms
high_cut_ms = args.high_cut_ms
step = args.step
port = int(args.master_id)  # master_id 就是接收端主机编号，也即端口号
queue = int(args.queue)     # 队列号（优先级）

print(f"算法: {args.alg}")
print(f"日志目录: {args.dump_dir}")
print(f"低切时间: {args.low_cut_ms} ms")
print(f"高切时间: {args.high_cut_ms} ms")
print(f"采样步长: {args.step}")
print(f"主节点ID: {args.master_id}")
print(f"队列号: {args.queue}")

# ===================== 解析器基类 =====================
class BaseLogParser:
    def __init__(self, prefix_pattern: re.Pattern, fields_config: List[Tuple[str, str, Callable]]):
        self.prefix_pattern = prefix_pattern
        self.fields_config = fields_config
        self.full_pattern = self._build_pattern()
        self.compiled_re = re.compile(self.full_pattern)

    def _build_pattern(self) -> str:
        field_parts = []
        for name, pattern, _ in self.fields_config:
            part = rf"{name}:\s+(?P<{name}>{pattern})"
            field_parts.append(part)
        fields_re = r"\s+".join(field_parts)
        return self.prefix_pattern.pattern + fields_re

    def parse_line(self, line: str) -> Optional[Dict[str, Any]]:
        match = self.compiled_re.match(line.strip())
        if not match:
            return None
        result = match.groupdict()
        # 转换前缀字段（时间戳、port、queue）为 int
        for key in ["timestamp", "port", "queue"]:
            if key in result:
                result[key] = int(result[key])
        # 转换可配置字段
        for name, _, converter in self.fields_config:
            if name in result:
                result[name] = converter(result[name])
        return result

# ===================== QLA 解析器 =====================
class QLALogParser(BaseLogParser):
    def __init__(self):
        prefix = re.compile(
            r'^(?P<timestamp>\d+)\s+PRED->QLA\[port:(?P<port>\d+)\]\[queue:(?P<queue>\d+)\]:\s+'
        )
        fields = [
            ("Tqla",           r"\d+",      int),
            ("lambda_current", r"[\d.]+",   float),
            ("lambda_base",    r"[\d.]+",   float),
            ("mink",           r"\d+",      int),
            ("maxk",           r"\d+",      int),
            ("utility",        r"[\d.]+",   float),
        ]
        super().__init__(prefix, fields)

# ===================== FCS 解析器 =====================
class FCSLogParser(BaseLogParser):
    def __init__(self):
        prefix = re.compile(
            r'^(?P<timestamp>\d+)\s+PRED->FCS\[port:(?P<port>\d+)\]\[queue:(?P<queue>\d+)\]:\s+'
        )
        fields = [
            ("Tfcs", r"\d+", int),
            ("N",    r"\d+", int),
        ]
        super().__init__(prefix, fields)

# ==================== PRED 解析器 =====================
class PREDLogParser(BaseLogParser):
    """解析 AQM_PRED 日志（Q>MINK 相关指标）"""
    def __init__(self):
        prefix = re.compile(
            r'^(?P<timestamp>\d+)\s+AQM_PRED\[port:(?P<port>\d+)\]\[queue:(?P<queue>\d+)\]\s+Q>MINK\s+'
        )
        # 字段配置：名称、正则模式、类型转换函数
        fields = [
            ("Pmark",         r"[\d.]+",   float),   # 标记概率
            ("F_N",           r"[\d.]+",   float),   # F(N)
            ("lambda_current",r"[\d.]+",   float),   # 当前 lambda
            ("slope",         r"[\d.]+",   float),   # 斜率 = F(N)*lambda_current
            ("Q",             r"[\d.]+",   float),   # 当前队列长度
            ("KMIN",          r"[\d.]+",   float),   # 最小阈值
            ("Q_MINUS_KMIN",        r"[\d.]+",   float),   # Q - KMIN
        ]
        super().__init__(prefix, fields)

# ===================== 日志读取与处理 =====================
def parse_log_file(
    file_path: str,
    low_cut_ms: int = 0,
    high_cut_ms: float = float('inf'),
    step: int = 1,
    port: Optional[Union[int, List[int]]] = None,
    queue: Optional[Union[int, List[int]]] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    读取日志文件，解析 QLA 和 FCS 记录，应用低切、步长采样，并按 port/queue 过滤。

    参数:
        file_path: 日志文件路径
        low_cut_ms: 低切时间（毫秒）。只保留 timestamp >= (max_timestamp - low_cut_ms) 的记录。
        high_cut_ms: 高切时间（毫秒）。只保留 timestamp <= (min_timestamp + high_cut_ms) 的记录。
        step: 步长采样，每隔 step 条保留一条（在低切之后的数据上采样）。
        port: 过滤条件，指定 port（整数或整数列表）。为 None 表示不过滤。
        queue: 过滤条件，指定 queue（整数或整数列表）。为 None 表示不过滤。

    返回:
        (qla_records, fcs_records, pred_records)
    """
    qla_parser = QLALogParser()
    fcs_parser = FCSLogParser()
    pred_parser = PREDLogParser()

    all_qla: List[Dict[str, Any]] = []
    all_fcs: List[Dict[str, Any]] = []
    all_pred: List[Dict[str, Any]] = []

    # 读取全部合法记录，同时记录最大时间戳
    max_ts = 0
    min_ts = float('inf')
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            #解析QLA
            parsed = qla_parser.parse_line(line)
            if parsed:
                all_qla.append(parsed)
                max_ts = max(max_ts, parsed['timestamp'])
                min_ts = min(min_ts, parsed['timestamp'])
                continue

            #解析FCS
            parsed = fcs_parser.parse_line(line)
            if parsed:
                all_fcs.append(parsed)
                max_ts = max(max_ts, parsed['timestamp'])
                min_ts = min(min_ts, parsed['timestamp'])

            #解析PRED
            parsed = pred_parser.parse_line(line)
            if parsed:
                all_pred.append(parsed)
                max_ts = max(max_ts, parsed['timestamp'])
                min_ts = min(min_ts, parsed['timestamp'])

    # 过滤条件函数：根据 port 和 queue 筛选
    def match_port_queue(record: Dict[str, Any]) -> bool:
        if port is not None:
            p = record['port']
            if isinstance(port, int):
                if p != port:
                    return False
            else:  # list
                if p not in port:
                    return False
        if queue is not None:
            q = record['queue']
            if isinstance(queue, int):
                if q != queue:
                    return False
            else:
                if q not in queue:
                    return False
        return True

    # 低切阈值
    # threshold = max_ts - low_cut_ms*1e6 if low_cut_ms > 0 else 0
    # threshold_max = min_ts + high_cut_ms*1e6 if high_cut_ms < float('inf') else float('inf')
    # 修改后
    threshold = low_cut_ms*1e6 if low_cut_ms > 0 else -float('inf')   # 或者 0 也可以，但推荐 -inf
    threshold_max = high_cut_ms*1e6 if high_cut_ms < float('inf') else float('inf')

    print(f"[parser-match]低切{threshold}")
    print(f"[parser-match]高切{threshold_max}")

    # 过滤 + 步长采样
    def filter_and_sample(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # 先按时间和 port/queue 过滤
        filtered = [
            r for r in records
            if r['timestamp'] >= threshold and r['timestamp'] <= threshold_max and match_port_queue(r)
        ]
        # 再按步长采样
        return filtered[::step]

    qla_filtered = filter_and_sample(all_qla)
    fcs_filtered = filter_and_sample(all_fcs)
    pred_filtered = filter_and_sample(all_pred)

    return qla_filtered, fcs_filtered, pred_filtered

# ===================== 绘图函数 =====================
import matplotlib.pyplot as plt
from typing import List, Dict, Any, Union, Optional

def plot_log_time_series(
    data: List[Dict[str, Any]],
    fields: Union[str, List[str]],
    colors: Optional[List[str]] = None,
    labels: Optional[List[str]] = None,
    title: str = "",
    xlabel: str = "Time (ms)",
    ylabel: str = "Value",
    start_time_ms: Optional[float] = None,
    figsize: tuple = (12, 6),
    save_path: Optional[str] = None,   # 新增：保存图像的文件路径，如 "output.png"
    pic_name: Optional[str] = None,     # 新增：图像文件名（不含路径），如 "qla_metrics.png"
    show: bool = True                  # 是否在保存后显示图像
):
    """
    从日志数据中提取指定字段，按时间戳绘图，并支持保存图像。
    
    参数:
        data: parse_log_file 返回的列表（如 qla_data 或 fcs_data）
        fields: 要绘制的字段名（字符串或字符串列表）
        colors: 线条颜色列表
        labels: 图例标签列表
        title, xlabel, ylabel: 图表文字
        start_time_ms: 基准时间（毫秒），为 None 时使用数据最小时间戳
        figsize: 图形大小
        save_path: 保存图像的文件路径（如 "figures/trend.png"），若为 None 则不保存
        show: 是否显示图像（若保存后不显示可设为 False）
    """
    if not data:
        print("警告：数据为空，无法绘图")
        return

    # 确保 fields 为列表
    if isinstance(fields, str):
        fields = [fields]
    n_lines = len(fields)

    # 颜色处理
    if colors is None:
        colors = [f"C{i}" for i in range(n_lines)]
    else:
        colors = colors[:n_lines]

    # 标签处理
    if labels is None:
        labels = fields
    else:
        labels = labels[:n_lines]

    # 提取时间戳（纳秒）转换为毫秒
    timestamps_ns = [rec['timestamp'] for rec in data]
    timestamps_ms = [t / 1_000_000.0 for t in timestamps_ns]

    # 相对时间处理
    # if start_time_ms is None:
    #     start_time_ms = min(timestamps_ms)
    # rel_time_ms = [t - start_time_ms for t in timestamps_ms]
    # 修改
    if start_time_ms is not None:
        rel_time_ms = [t - start_time_ms for t in timestamps_ms]
    else:
        rel_time_ms = timestamps_ms  # 直接使用绝对时间，不做偏移

    # 绘图
    plt.figure(figsize=figsize)
    for i, field in enumerate(fields):
        values = [rec.get(field) for rec in data]
        # 过滤无效值
        valid_pairs = [(rel, val) for rel, val in zip(rel_time_ms, values) if val is not None]
        if not valid_pairs:
            continue
        x_vals, y_vals = zip(*valid_pairs)
        plt.plot(x_vals, y_vals, color=colors[i], label=labels[i], linewidth=1.5)

    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()

    # 保存图像
    if save_path:
        if pic_name:
            save_path = f"{save_path}/{pic_name}"
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"图像已保存至: {save_path}")

    # 显示或关闭
    if show:
        plt.show()
    else:
        plt.close()

def plot_dual_axis_time_series(
    data: List[Dict[str, Any]],
    field_left: str,
    field_right: str,
    color_left: str = "blue",
    color_right: str = "red",
    label_left: str = None,
    label_right: str = None,
    title: str = "",
    xlabel: str = "Time (ms)",
    ylabel_left: str = None,
    ylabel_right: str = None,
    start_time_ms: Optional[float] = None,
    figsize: tuple = (12, 6),
    output_dir: Optional[str] = None,
    filename: Optional[str] = None,
    show: bool = True
):
    """
    绘制双Y轴时间序列（左轴 field_left，右轴 field_right）。
    """
    if not data:
        print("警告：数据为空，无法绘图")
        return

    # 时间处理
    timestamps_ns = [rec['timestamp'] for rec in data]
    timestamps_ms = [t / 1_000_000.0 for t in timestamps_ns]

    # if start_time_ms is None:
    #     start_time_ms = min(timestamps_ms)
    # rel_time_ms = [t - start_time_ms for t in timestamps_ms]
    # 修改
    if start_time_ms is not None:
        rel_time_ms = [t - start_time_ms for t in timestamps_ms]
    else:
        rel_time_ms = timestamps_ms  # 直接使用绝对时间，不做偏移

    # 提取左右轴数据
    values_left = [rec.get(field_left) for rec in data]
    values_right = [rec.get(field_right) for rec in data]

    # 过滤 None
    valid_data = [(rt, vl, vr) for rt, vl, vr in zip(rel_time_ms, values_left, values_right)
                  if vl is not None and vr is not None]
    if not valid_data:
        print("错误：有效数据点不足")
        return
    x_vals, y_left, y_right = zip(*valid_data)

    # 创建图形和左轴
    fig, ax1 = plt.subplots(figsize=figsize)
    ax1.plot(x_vals, y_left, color=color_left, linewidth=1.5,
             label=label_left if label_left else field_left)
    ax1.set_xlabel(xlabel)
    ax1.set_ylabel(ylabel_left if ylabel_left else field_left, color=color_left)
    ax1.tick_params(axis='y', labelcolor=color_left)

    # 右轴
    ax2 = ax1.twinx()
    ax2.plot(x_vals, y_right, color=color_right, linewidth=1.5,
             label=label_right if label_right else field_right)
    ax2.set_ylabel(ylabel_right if ylabel_right else field_right, color=color_right)
    ax2.tick_params(axis='y', labelcolor=color_right)

    # 合并图例
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='best')

    plt.title(title)
    plt.grid(True, linestyle='--', alpha=0.3)
    fig.tight_layout()

    # 保存
    if output_dir and filename:
        os.makedirs(output_dir, exist_ok=True)
        save_path = os.path.join(output_dir, filename)
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"图像已保存至: {save_path}")

    if show:
        plt.show()
    else:
        plt.close()

# ===================== 主逻辑 =====================
def main():
    """示例：演示如何调用解析函数（可按 port/queue 过滤）"""
    # 示例：只读取 port=17, queue=3 的数据，忽略最近 5 秒之前的数据，步长为 2
    qla_data, fcs_data, pred_data = parse_log_file(
        log_file,
        low_cut_ms=low_cut_ms,
        high_cut_ms=high_cut_ms,
        step=step,
        port=port,
        queue=queue
    )

    print(f"QLA 有效记录数: {len(qla_data)}")
    if qla_data:
        print("QLA 第一条:", qla_data[0])

    print(f"FCS 有效记录数: {len(fcs_data)}")
    if fcs_data:
        print("FCS 第一条:", fcs_data[0])

    print(f"PRED 有效记录数: {len(pred_data)}")
    if pred_data:
        print("PRED 第一条:", pred_data[0])

    # 假设已经通过 parse_log_file 获得了 qla_data 和 fcs_data
    # qla_data, fcs_data = parse_log_file("log.txt", low_cut_ms=5000, step=2, port=17, queue=3)

    # 示例：绘制 QLA 数据的 lambda_base 和 utility 两条线，自定义颜色
    # 绘制并保存 QLA 曲线（保存为 PNG，不显示）
    # plot_log_time_series(
    #     data=qla_data,
    #     fields=["lambda_base", "utility"],
    #     colors=["darkorange", "purple"],
    #     labels=["Base Lambda", "Utility"],
    #     title=f"QLA Metrics over Time (Port {port}, Queue {queue})",
    #     save_path=dump_dir,   # 保存到当前目录
    #     pic_name="qla_metrics.png",  # 指定文件名
    #     show=False                     # 只在后台保存，不弹出窗口
    # )

    plot_dual_axis_time_series(
        data=qla_data,
        field_left="lambda_base",
        field_right="utility",
        color_left="darkorange",
        color_right="purple",
        label_left="Base Lambda",
        label_right="Utility",
        title=f"QLA Metrics over Time (Port {port}, Queue {queue})",
        output_dir=dump_dir,
        filename=f"qla_dual_axis_{args.alg}.png",
        show=False
    )

    plot_dual_axis_time_series(
        data=pred_data,
        field_left="Pmark",
        field_right="slope",
        color_left="darkorange",
        color_right="purple",
        label_left="Mark Probability",
        label_right="Slope (F(N)*lambda_current)",
        title=f"PRED Metrics over Time (Port {port}, Queue {queue})",
        output_dir=dump_dir,
        filename=f"pred_dual_axis_{args.alg}.png",
        show=False
    )
    

    # 绘制 FCS 曲线，保存并显示
    plot_log_time_series(
        data=fcs_data,
        fields="N",
        colors=["green"],
        title=f"FCS Metrics over Time (Port {port}, Queue {queue})",
        save_path=dump_dir,   # 保存到当前目录
        pic_name=f"fcs_metrics_{args.alg}.png",  # 指定文件名
        show=False
    )

if __name__ == "__main__":
    main()
