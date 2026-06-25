# 本脚本用于绘制LSS场景的图像
import os
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from tabulate import tabulate
import matplotlib.pyplot as plt
import numpy as np

# 设置中文字体（避免方框乱码）
# 方案一：使用系统常见中文字体（优先 SimHei/黑体，适用于 Windows/Linux/macOS）
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'WenQuanYi Zen Hei', 'Noto Sans CJK SC', 'Arial Unicode MS']
# 解决负号显示为方块的问题
plt.rcParams['axes.unicode_minus'] = False

# 可选：设置字体大小
plt.rcParams['font.size'] = 20

# ==================== FCT类型 ====================
@dataclass
class FCTEntry:
    flowsize: float
    fct: float

@dataclass
class FCTData:
    algo: str
    load: float
    entries: List[FCTEntry]
    
    def print(self):
        print(f"Algo: {self.algo}, Load: {self.load}")
        headers = ["Flowsize", "FCT"]
        table = [[e.flowsize, e.fct] for e in self.entries]
        print(tabulate(table, headers=headers, floatfmt=".1f", tablefmt="simple"))

# ==================== 读取FCT数据 ====================
def read_fct_data(file_path: str) -> List[FCTEntry]:
    result = []
    with open(file_path, 'r') as f:
        for line in f:
            if not line.strip():
                continue
            parts = line.strip().split()
            if len(parts) >= 5:
                flowsize = float(parts[4])
                fct = float(parts[-2])
                result.append(FCTEntry(flowsize, fct))
    return result

# ==================== DEBUG输出 ====================
def debug(var):
    import sys
    frame = sys._getframe(1)
    locals_dict = frame.f_locals
    var_name = None
    for name, value in locals_dict.items():
        if value is var:
            var_name = name
            break
    if var_name is None:
        var_name = "<unknown>"
    print(f"{var_name}: {var}")

# ==================== 浮点数range ====================
def frange(start, stop, step, accuracy=1) -> list:
    temp_list = []
    temp_list.append(start)
    while start < stop:
        start += step
        start = round(start, 1)
        temp_list.append(start)
    return temp_list

# ==================== 绝对平均FCT绘图（原有功能） ====================
@dataclass
class FCTPlotConfig:
    algo_list: List[str] = None
    load_list: List[float] = None
    dataset: str = "websearch"
    min_flowsize: float = 0.0
    max_flowsize: float = float('inf')
    output_dir: str = ""

    def __post_init__(self):
        if self.algo_list is None:
            self.algo_list = ALGS
        if self.load_list is None:
            self.load_list = LOADS

class FCTPlotter:
    def __init__(self, config: FCTPlotConfig):
        self.config = config

    def filter_entries(self, entries: List[FCTEntry]) -> List[FCTEntry]:
        return [e for e in entries if self.config.min_flowsize <= e.flowsize <= self.config.max_flowsize]

    def get_filtered_data(self) -> List[FCTData]:
        filtered_data = []
        for algo in self.config.algo_list:
            for load in self.config.load_list:
                load_str = f"{load:.1f}"
                file_path = f"{DUMP_ROOT_DIR}/{self.config.dataset}/{algo}/fct-{load_str}.txt"
                entries = read_fct_data(file_path)
                filtered_entries = self.filter_entries(entries)
                if filtered_entries:
                    filtered_data.append(FCTData(algo=algo, load=load, entries=filtered_entries))
        return filtered_data

    def plot(self):
        filtered_data = self.get_filtered_data()
        algo_data = {}
        for data in filtered_data:
            if data.algo not in algo_data:
                algo_data[data.algo] = {}
            algo_data[data.algo][data.load] = data.entries

        fig, ax = plt.subplots(figsize=(10, 6))
        for algo, load_entries in algo_data.items():
            loads = sorted(load_entries.keys())
            avg_fcts = []
            for load in loads:
                entries = load_entries[load]
                if entries:
                    avg_fct = np.mean([e.fct for e in entries])
                    avg_fcts.append(avg_fct)
                else:
                    avg_fcts.append(0)
            ax.plot(loads, avg_fcts, marker='o', label=algo)

        ax.set_xlabel('Load')
        ax.set_ylabel('Average FCT')
        ax.set_title(f'FCT vs Load - {self.config.dataset}')
        ax.legend()
        ax.grid(True, linestyle='--', alpha=0.7)

        if self.config.output_dir:
            os.makedirs(self.config.output_dir, exist_ok=True)
            save_path = os.path.join(self.config.output_dir, f'{self.config.dataset}_fct_vs_load.png')
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Figure saved to {save_path}")
        plt.show()

# ==================== 新增：归一化FCT绘图（相对于基准算法） ====================
@dataclass
class NormalizedFCTPlotConfig:
    baseline_algo: str               # 基准算法名称，如 "PRED"
    other_algos: List[str]           # 其他算法列表
    load_list: List[float]           # 负载列表
    dataset: str = "websearch"
    min_flowsize: float = 0.0
    max_flowsize: float = float('inf')
    output_dir: str = ""
    # 线条样式：可以为每个算法指定颜色、线型、标记等
    line_styles: Optional[Dict[str, Dict]] = None   # 例如 {"DCQCN": {"color": "red", "linestyle": "--", "marker": "s"}}

class NormalizedFCTPlotter:
    def __init__(self, config: NormalizedFCTPlotConfig):
        self.config = config

    def _get_avg_fct_per_load(self, algo: str) -> Dict[float, float]:
        """返回该算法在各负载下的平均FCT（基于flowsize过滤后的条目）"""
        avg_dict = {}
        for load in self.config.load_list:
            load_str = f"{load:.1f}"
            file_path = f"{DUMP_ROOT_DIR}/{self.config.dataset}/{algo}/fct-{load_str}.txt"
            entries = read_fct_data(file_path)
            # 应用flowsize过滤
            filtered = [e for e in entries if self.config.min_flowsize <= e.flowsize <= self.config.max_flowsize]
            if filtered:
                avg_fct = np.mean([e.fct for e in filtered])
                avg_dict[load] = avg_fct
            else:
                avg_dict[load] = None   # 无数据，后续跳过
        return avg_dict

    def plot(self):
        # 获取基准算法的平均FCT
        baseline_avg = self._get_avg_fct_per_load(self.config.baseline_algo)
        # 获取其他算法的平均FCT，并计算倍数
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # 默认样式
        default_styles = {
            "color": None,      # 自动颜色
            "linestyle": "-",
            "marker": "o",
            "linewidth": 2,
        }
        
        for algo in self.config.other_algos:
            algo_avg = self._get_avg_fct_per_load(algo)
            loads = []
            ratios = []
            for load in self.config.load_list:
                base = baseline_avg.get(load)
                other = algo_avg.get(load)
                if base is not None and other is not None and base > 0:
                    loads.append(load)
                    ratios.append(other / base)
            if not loads:
                print(f"警告: 算法 {algo} 没有有效数据与基准 {self.config.baseline_algo} 对比")
                continue
            
            # 获取该算法的线条样式
            style = default_styles.copy()
            if self.config.line_styles and algo in self.config.line_styles:
                style.update(self.config.line_styles[algo])
            
            ax.plot(loads, ratios,
                    color=style["color"],
                    linestyle=style["linestyle"],
                    marker=style["marker"],
                    linewidth=style["linewidth"],
                    label=f"{algo}")#/{self.config.baseline_algo}
        
        # 绘制基准线 y=1
        ax.axhline(y=1, color='black', linestyle=':', linewidth=1, alpha=0.7, label=f'基准：{self.config.baseline_algo} (1.0)')
        
        ax.set_xlabel('负载')
        ax.set_ylabel('归一化FCT')
        title = f'不同算法在不同负载下的归一化FCT图(基准: {self.config.baseline_algo}) - {self.config.dataset}'
        if self.config.min_flowsize > 0 or self.config.max_flowsize < float('inf'):
            title += f'\n流量大小范围：[{self.config.min_flowsize}, {self.config.max_flowsize}]'
        ax.set_title(title)
        ax.legend()
        ax.grid(True, linestyle='--', alpha=0.7)

        ax.set_ylim(0.8,4)#YRNK: YLIM设置
        
        
        if self.config.output_dir:
            os.makedirs(self.config.output_dir, exist_ok=True)
            # 构造文件名
            fname = f"{self.config.dataset}_normalized_{self.config.baseline_algo}"
            if self.config.min_flowsize > 0:
                fname += f"_over{self.config.min_flowsize:.0f}"
            if self.config.max_flowsize < float('inf'):
                fname += f"_below{self.config.max_flowsize:.0f}"
            fname += ".png"
            save_path = os.path.join(self.config.output_dir, fname)
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Normalized figure saved to {save_path}")

        plt.show()

# ==================== 全局配置（与原有保持一致） ====================
SCENE_NAME = "LSS"
PARENT_DIR = os.path.dirname(os.path.abspath(__file__))
debug(PARENT_DIR)

PRED_DIR = os.path.dirname(PARENT_DIR)
debug(PRED_DIR)

DUMP_ROOT_DIR = PRED_DIR + "/dump/PRED/" + SCENE_NAME
debug(DUMP_ROOT_DIR)

# DATASET = "websearch"
# DATASET = "datamining"   # 可改为 "websearch"
# DATASET = "memcached"
# DATASET = "fbhdp"
# DATASET = "googlerpc"
DATASET = "alistorage"

load_min = 0.1
load_max = 0.9
load_step = 0.1
LOADS = frange(load_min, load_max, load_step)
ALGS = [
    "PRED", 
    "CoDel", 
    "RED"
    ]   # 可根据需要增加其他算法

# ==================== 原有绘图（绝对平均FCT） ====================
IDENTIFIER = "ECN"

# 绘制不设过滤的全量图
plotter_all = FCTPlotter(FCTPlotConfig(
    algo_list=ALGS,
    load_list=LOADS,
    dataset=DATASET,
    output_dir=PARENT_DIR + "/" + SCENE_NAME + "/" + IDENTIFIER + "/all"
))
plotter_all.plot()

# 绘制 small 流（<100KB）
plotter_small = FCTPlotter(FCTPlotConfig(
    algo_list=ALGS,
    load_list=LOADS,
    dataset=DATASET,
    min_flowsize=0.0,
    max_flowsize=100000.0,
    output_dir=PARENT_DIR + "/" + SCENE_NAME + "/" + IDENTIFIER + "/small"
))
plotter_small.plot()

# 绘制 large 流（>1MB）
plotter_large = FCTPlotter(FCTPlotConfig(
    algo_list=ALGS,
    load_list=LOADS,
    dataset=DATASET,
    min_flowsize=1000000.0,
    max_flowsize=float('inf'),
    output_dir=PARENT_DIR + "/" + SCENE_NAME + "/" + IDENTIFIER + "/large"
))
plotter_large.plot()

# ==================== 新增：归一化FCT绘图（以PRED为基准） ====================
# 定义线条样式（可选）
line_styles = {
    "CoDel": {"color": "red", "linestyle": "--", "marker": "s", "linewidth": 2},
    # 可扩展其他算法，如 "DCQCN": {"color": "green", "linestyle": "-.", "marker": "^"}
}

# 1. 全量流归一化
norm_config_all = NormalizedFCTPlotConfig(
    baseline_algo="PRED",
    other_algos=[a for a in ALGS if a != "PRED"],   # 除了PRED本身之外的其他算法
    load_list=LOADS,
    dataset=DATASET,
    min_flowsize=0.0,
    max_flowsize=float('inf'),
    output_dir=PARENT_DIR + "/" + SCENE_NAME + "/" + IDENTIFIER + "/normalized",
    line_styles=line_styles
)
norm_plotter_all = NormalizedFCTPlotter(norm_config_all)
norm_plotter_all.plot()

# 2. small流归一化
norm_config_small = NormalizedFCTPlotConfig(
    baseline_algo="PRED",
    other_algos=[a for a in ALGS if a != "PRED"],
    load_list=LOADS,
    dataset=DATASET,
    min_flowsize=0.0,
    max_flowsize=100000.0,
    output_dir=PARENT_DIR + "/" + SCENE_NAME + "/" + IDENTIFIER + "/normalized",
    line_styles=line_styles
)
norm_plotter_small = NormalizedFCTPlotter(norm_config_small)
norm_plotter_small.plot()

# 3. large流归一化
norm_config_large = NormalizedFCTPlotConfig(
    baseline_algo="PRED",
    other_algos=[a for a in ALGS if a != "PRED"],
    load_list=LOADS,
    dataset=DATASET,
    min_flowsize=1000000.0,
    max_flowsize=float('inf'),
    output_dir=PARENT_DIR + "/" + SCENE_NAME + "/" + IDENTIFIER + "/normalized",
    line_styles=line_styles
)
norm_plotter_large = NormalizedFCTPlotter(norm_config_large)
norm_plotter_large.plot()