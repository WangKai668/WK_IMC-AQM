import argparse
import re
import os
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict

def parse_args():
    """解析命令行参数（所有帮助信息均已中文化）"""
    p = argparse.ArgumentParser(description="绘制不同负载下各算法的平均流完成时间（FCT），支持按流量长度分组")
    p.add_argument("--load-levels", required=True, help="负载级别列表，逗号分隔，例如 '0.1,0.3,0.5,0.7,0.9'")
    p.add_argument("--algorithms", required=True, help="算法名称列表，逗号分隔，例如 'RED,CoDel,PRED'")
    p.add_argument("--colors", default=None, help="每个算法的颜色，逗号分隔，例如 'red,blue,green'。若不指定则自动循环")
    p.add_argument("--labels", default=None, help="每个算法的图例标签，逗号分隔（可选，默认使用算法名）")
    p.add_argument("--fct-dir", default=".", help="存放FCT文件的目录")
    p.add_argument("--fct-pattern", default="fct-{alg}-{load}.txt",
                   help="FCT文件名模板，{alg}和{load}会被替换。例如 'fct-{alg}-l{load}.txt'")
    p.add_argument("--size-col", type=int, default=2, help="流量大小所在的列号（从1开始计数）。默认第2列")
    p.add_argument("--fct-col", type=int, default=-2, help="FCT值所在的列号（负数表示从末尾倒数）。默认-2（倒数第二列）")
    p.add_argument("--length-ranges", required=True,
                   help="流量长度分组范围，格式 '名称:最小值-最大值,名称:最小值-最大值,...'，"
                        "单位支持 B/KB/MB/GB，例如 'short:0-100KB,medium:100KB-1MB,long:1MB-100MB'")
    p.add_argument("--output-dir", default=".", help="输出图片的目录")
    p.add_argument("--xlabel", default="负载级别", help="X轴标签")
    p.add_argument("--ylabel", default="平均流完成时间 (ms)", help="Y轴标签")
    p.add_argument("--title-prefix", default="FCT vs 负载", help="图片标题前缀")
    return p.parse_args()

def parse_size_range(range_str):
    """
    将形如 '0-100KB' 或 '1MB-10MB' 的范围字符串转换为 (最小字节数, 最大字节数)
    """
    if '-' not in range_str:
        raise ValueError(f"范围格式错误（缺少 '-'）：{range_str}")
    low_str, high_str = range_str.split('-', 1)
    
    def to_bytes(s):
        s = s.strip().upper()
        if s.endswith('KB'):
            return float(s[:-2]) * 1024
        elif s.endswith('MB'):
            return float(s[:-2]) * 1024 * 1024
        elif s.endswith('GB'):
            return float(s[:-2]) * 1024 * 1024 * 1024
        elif s.endswith('B'):
            return float(s[:-1])
        else:
            return float(s)  # 默认视为字节
    low = to_bytes(low_str)
    high = to_bytes(high_str)
    return low, high

def parse_length_ranges(ranges_str):
    """
    解析 --length-ranges 参数，返回字典 {名称: (最小字节数, 最大字节数)}
    """
    ranges = {}
    for item in ranges_str.split(','):
        if ':' not in item:
            raise ValueError(f"分组格式错误（缺少 ':'）：{item}")
        name, spec = item.split(':', 1)
        low, high = parse_size_range(spec)
        ranges[name.strip()] = (low, high)
    return ranges

def read_fct_file(filepath, size_col, fct_col):
    """
    读取FCT文件，返回两个列表：flow_sizes（字节）和 fct_values（浮点数）
    假定文件以空白符分隔各列，列号从1开始计数
    """
    sizes = []
    fcts = []
    if not os.path.exists(filepath):
        print(f"警告：文件不存在 - {filepath}")
        return sizes, fcts
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            try:
                size_idx = size_col - 1   # 转换为0索引
                fct_idx = fct_col if fct_col >= 0 else len(parts) + fct_col
                size = float(parts[size_idx])
                fct = float(parts[fct_idx])
                sizes.append(size)
                fcts.append(fct)
            except (IndexError, ValueError) as e:
                print(f"跳过格式错误的行：{line} ({e})")
                continue
    return sizes, fcts

def compute_average_fct_per_range(sizes, fcts, ranges):
    """
    对于每个流量长度范围，计算落在该范围内的流的平均FCT
    返回字典 {范围名: 平均FCT}，若无流则值为nan
    """
    avg_fct = {}
    for name, (low, high) in ranges.items():
        values = [fct for sz, fct in zip(sizes, fcts) if low <= sz <= high]
        if values:
            avg_fct[name] = np.mean(values)
        else:
            avg_fct[name] = np.nan
    return avg_fct

def main():
    args = parse_args()

    # 解析负载级别并排序
    load_levels = [float(x.strip()) for x in args.load_levels.split(',')]
    load_levels.sort()
    load_strs = [str(l) for l in load_levels]

    # 解析算法列表
    algorithms = [x.strip() for x in args.algorithms.split(',')]
    n_algs = len(algorithms)

    # 颜色与标签
    if args.colors:
        colors = [x.strip() for x in args.colors.split(',')]
        if len(colors) != n_algs:
            raise ValueError("颜色的数量必须与算法数量相同")
    else:
        # 使用matplotlib默认颜色循环
        colors = plt.rcParams['axes.prop_cycle'].by_key()['color'][:n_algs]
    if args.labels:
        labels = [x.strip() for x in args.labels.split(',')]
        if len(labels) != n_algs:
            raise ValueError("标签的数量必须与算法数量相同")
    else:
        labels = algorithms

    # 解析长度分组范围
    ranges = parse_length_ranges(args.length_ranges)
    range_names = list(ranges.keys())

    # 数据结构：data[算法][负载级别][范围名] = 平均FCT
    data = {alg: {load: {} for load in load_levels} for alg in algorithms}

    # 读取所有FCT文件
    for alg in algorithms:
        for load in load_levels:
            # 根据模板构造文件名
            fname = args.fct_pattern.format(alg=alg, load=load)
            fpath = os.path.join(args.fct_dir, fname)
            sizes, fcts = read_fct_file(fpath, args.size_col, args.fct_col)
            if not sizes:
                print(f"算法 {alg} 在负载 {load} 下无有效数据（文件 {fpath}）")
            avg_per_range = compute_average_fct_per_range(sizes, fcts, ranges)
            for rname in range_names:
                data[alg][load][rname] = avg_per_range.get(rname, np.nan)

    # 为每个长度范围分别绘图
    os.makedirs(args.output_dir, exist_ok=True)
    for rname in range_names:
        plt.figure(figsize=(10, 6))
        for alg, color, label in zip(algorithms, colors, labels):
            y_vals = [data[alg][load][rname] for load in load_levels]
            # 过滤掉nan值
            valid_loads = [load for load, y in zip(load_levels, y_vals) if not np.isnan(y)]
            valid_y = [y for y in y_vals if not np.isnan(y)]
            if valid_loads:
                plt.plot(valid_loads, valid_y, marker='o', linestyle='-', color=color, label=label, linewidth=2)
        plt.xlabel(args.xlabel)
        plt.ylabel(args.ylabel)
        plt.title(f"{args.title_prefix} - {rname} 长度范围")
        plt.legend()
        plt.grid(True, linestyle='--', alpha=0.6)
        # 如果负载级别跨越多个数量级，可取消下面注释以使用对数X轴
        # if min(load_levels) > 0 and max(load_levels)/min(load_levels) > 10:
        #     plt.xscale('log')
        outfile = os.path.join(args.output_dir, f"fct_vs_load_{rname}.png")
        plt.savefig(outfile, dpi=300, bbox_inches='tight')
        print(f"图片已保存至 {outfile}")
        plt.close()

if __name__ == "__main__":
    main()