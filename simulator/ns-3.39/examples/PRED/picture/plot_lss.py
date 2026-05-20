# 本脚本用于绘制LSS场景的图像
import os
from typing import List, Tuple
from dataclasses import dataclass
from tabulate import tabulate

#====================FCT类型====================
# flowsize 第五列
# fct 倒数第二列
@dataclass
class FCTEntry:
    flowsize:   float
    fct:        float

@dataclass
class FCTData:
    algo:       str
    load:       float
    entries:    list[FCTEntry]
    def print(self):
        print(f"Algo: {self.algo}, Load: {self.load}")
        headers = ["Flowsize", "FCT"]
        table = [[e.flowsize, e.fct] for e in self.entries]
        print(tabulate(table, headers=headers, floatfmt=".1f", tablefmt="simple"))
#=================================================
def read_fct_data(file_path: str) -> List[FCTEntry]:
    """读取FCT文件，返回(flowsize, fct)元组列表"""
    result = []
    with open(file_path, 'r') as f:
        for line in f:
            if not line.strip():
                continue
            parts = line.strip().split()
            if len(parts) >= 5:  # 确保至少有5列
                flowsize = float(parts[4])  # 第五列
                fct = float(parts[-2])      # 倒数第二列
                result.append(
                    FCTEntry(flowsize, fct)
                )
    return result

#====================DEBUG输出====================
def debug(var):
    import sys
    # 获取调用者的局部变量字典
    frame = sys._getframe(1)
    locals_dict = frame.f_locals
    # 查找变量名
    var_name = None
    for name, value in locals_dict.items():
        if value is var:
            var_name = name
            break
    if var_name is None:
        var_name = "<unknown>"
    print(f"{var_name}: {var}")
#=================================================

#==================浮点数range====================
def frange(start, stop, step, accuracy=1)->list:
    temp_list = []
    temp_list+=[start]
    while start < stop:
        start += step
        start = round(start, 1)
        temp_list.append(start)
    return temp_list
#=================================================

#=========================绘图============================
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
        """根据flowsize阈值过滤FCT条目"""
        return [
            e for e in entries
            if self.config.min_flowsize <= e.flowsize <= self.config.max_flowsize
        ]

    def get_filtered_data(self) -> List[FCTData]:
        """获取过滤后的FCT数据"""
        filtered_data = []
        for algo in self.config.algo_list:
            for load in self.config.load_list:
                load_str = f"{load:.1f}"
                file_path = f"{DUMP_ROOT_DIR}/{self.config.dataset}/{algo}/fct-{load_str}.txt"
                entries = read_fct_data(file_path)
                filtered_entries = self.filter_entries(entries)
                if filtered_entries:
                    filtered_data.append(
                        FCTData(algo=algo, load=load, entries=filtered_entries)
                    )
        return filtered_data
    def plot(self):
        """绘制FCT随负载变化的曲线图"""
        import matplotlib.pyplot as plt
        import numpy as np

        filtered_data = self.get_filtered_data()

        # 按算法分组
        algo_data = {}
        for data in filtered_data:
            if data.algo not in algo_data:
                algo_data[data.algo] = {}
            algo_data[data.algo][data.load] = data.entries

        # 计算每个算法在每个负载下的平均FCT
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

        # 保存图片
        if self.config.output_dir:
            os.makedirs(self.config.output_dir, exist_ok=True)
            save_path = os.path.join(self.config.output_dir, f'{self.config.dataset}_fct_vs_load.png')
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Figure saved to {save_path}")

        plt.show()
#=========================================================


SCENE_NAME = "LSS"

PARENT_DIR = os.path.dirname(os.path.abspath(__file__))
debug(PARENT_DIR)

# 获取当前PY文件路径父目录的父目录
PRED_DIR = os.path.dirname(PARENT_DIR)
debug(PRED_DIR)

DUMP_ROOT_DIR = PRED_DIR+"/dump/PRED/"+SCENE_NAME
debug(DUMP_ROOT_DIR)

# DATASET = "websearch"
DATASET = "datamining"

load_min = 0.1
load_max = 0.9
load_step = 0.1
LOADS = frange(load_min, load_max, load_step)
ALGS = ["PRED", "CoDel"]

FCT_PATHS=[]
FCT_ALGOS=[]
FCT_LOADS=[]
FCT_COUNTS=0
for algo in ALGS:
    for load in LOADS:
        FCT_ALGOS.append(algo)
        FCT_LOADS.append(load)
        FCT_COUNTS+=1
        load_str = f"{load:.1f}"
        temp_path = f"{DUMP_ROOT_DIR}/{DATASET}/{algo}/fct-{load_str}.txt"
        FCT_PATHS.append(temp_path)
        debug(temp_path)

debug(FCT_COUNTS)

# FCT_0 = read_fct_data(FCT_PATHS[0])
# for e in FCT_0:
#     print(f"{e.flowsize}: {e.fct}")

FCTS = []
for i in range(FCT_COUNTS):
    entries=read_fct_data(FCT_PATHS[i])
    d=FCTData(
            algo=FCT_ALGOS[i],
            load=FCT_LOADS[i],
            entries=entries
        )
    # d.print()
    FCTS.append(
        d
    )

IDENTIFIER="ECN"

# 绘制一张不设任何过滤的图
plotter = FCTPlotter(FCTPlotConfig(
    algo_list=ALGS,
    load_list=LOADS,
    dataset=DATASET,
    output_dir=PARENT_DIR + "/" + SCENE_NAME+"/"+IDENTIFIER + "/all"
))
plotter.plot()

# 绘制长度小于100K和大于1M的两张图
plotter_small = FCTPlotter(FCTPlotConfig(
    algo_list=ALGS,
    load_list=LOADS,
    dataset=DATASET,
    min_flowsize=0.0,
    max_flowsize=100000.0,
    output_dir=PARENT_DIR + "/" + SCENE_NAME+"/"+IDENTIFIER + "/small"
))
plotter_small.plot()

plotter_large = FCTPlotter(FCTPlotConfig(
    algo_list=ALGS,
    load_list=LOADS,
    dataset=DATASET,
    min_flowsize=1000000.0,
    max_flowsize=float('inf'),
    output_dir=PARENT_DIR + "/" + SCENE_NAME +"/"+IDENTIFIER +"/large"
))
plotter_large.plot()
