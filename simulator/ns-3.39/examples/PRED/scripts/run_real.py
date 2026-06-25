# 此脚本用于运行大型真实流量仿真
import os
import subprocess
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
import pathlib
import datetime
import time

TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
print(f"时间戳{TIMESTAMP}")
# self.AQM_DICT = {
#     "RED": 1,
#     "CoDel": 2,
#     "MATCP": 3,
#     "CEDM": 4,
#     "MBECN": 5,
#     "PRED": 6,
#     "IMCAQM": 7,
#     "FCS": 8,
#     "QLA": 9
# }
# NS3=/home/wk/Reverie-Platform/branch_zyx/WK_IMC-AQM/simulator/ns-3.39
#=======================配置面板=============================
# 获取当前脚本所在目录的绝对路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# 返回上一级
PRED_DIR = os.path.dirname(SCRIPT_DIR)
NS3_DIR = os.path.dirname(#ns-3.39
    os.path.dirname(#examples
        PRED_DIR
    )
)
print(f"PRED_DIR={PRED_DIR}\nNS3_DIR={NS3_DIR}")
output_file_postfix = ".txt"
# LSS场景
TASKS = []

#config目录格式：config/scene/场景/数据集/负载.txt
#fct目录格式：mix/场景/数据集/算法/fct-负载.txt
FCT_ROOT_DIR = "mix/"

UNIVERSAL_COUNTER=0
#===========================================================

#=========================仿真任务类=========================
class SimulationTask:
    def __init__(self, config_path, output_dir, aqm_algo, cc_algo, window_check, write_evaluation_log=True):
        self.config_path = config_path
        self.output_dir = output_dir
        self.aqm_algo = aqm_algo
        self.cc_algo = cc_algo
        self.window_check = window_check
        self.write_evaluation_log = write_evaluation_log  # 是否输出evaluation日志文件

    def run(self):
        # 构建 waf 命令（使用列表形式避免 shell 注入）
        cmd = ["./waf", "--run", f"PRED-evaluation --conf={self.config_path} --aqm_algorithm={self.aqm_algo} --algorithm={self.cc_algo} --window-check={self.window_check}"]
        if self.write_evaluation_log:
            log_file = os.path.join(self.output_dir, f"evaluation-{self.aqm_algo}-{self.cc_algo}-{TIMESTAMP}" + output_file_postfix)
            with open(log_file, "w") as f:
                result = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
        else:
            # 不输出 evaluation 日志文件，仅运行仿真
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return result.returncode == 0

# 简易任务
class EasyTask:
    def __init__(self, aqm_algo, cc_algo, dataset, config, output_dir, fct_file_dir, write_evaluation_log=True):
        self.aqm_algo = aqm_algo
        self.cc_algo = cc_algo
        self.dataset = dataset
        self.config = config
        self.output_dir = output_dir
        self.fct_file_dir = fct_file_dir
        self.write_evaluation_log = write_evaluation_log  # 是否输出evaluation日志文件
#===========================================================

#========================仿真处理器类========================
class AQMSimulationRunner:
    # DO_FCT_OUTPUT=1 #是
    # # DO_FCT_OUTPUT=0 #否
    # FCT_DIR=$NS3/mix/fct.txt
    # FCT_OUTPUT=$RES_DUMP/fct_output
    def __init__(self, config_path_root, output_dir_root, 
        enable_fct_output=True,fct_root_dir=None,fct_output=None, max_workers=4):
        # 多线程最大工作线程数（默认为4，视系统资源调整）
        self.max_workers = max_workers

        # 启用FCT输出（默认为True）
        self.enable_fct_output = enable_fct_output
        self.fct_root_dir = fct_root_dir
        self.fct_output = fct_output

        # 配置根目录
        self.config_path_root = config_path_root

        # 输出根目录，每个算法的输出目录为 output_dir_root/算法名
        self.output_dir_root = output_dir_root

        self.cc_algo = "DCTCP"  # 默认使用DCTCP
        # 算法：AQM_MODE
        self.AQM_DICT = {
            "RED": 1,
            "CoDel": 2,
            "MATCP": 3,
            "CEDM": 4,
            "MBECN": 5,
            "PRED": 6,
            "IMCAQM": 7,
            "FCS": 8,
            "QLA": 9
        }
        # CC算法：CC_MODE
        self.CC_DICT = {
            "DCTCP": 8,
            "DCQCN": 1
        }
        # CC算法：启用窗口检查
        self.WINDOW_DICT = {
            "DCTCP": 1,
            "DCQCN": 0
        }

        self.do_identifier_for_LSS = False
    
    def enable_identifier_for_LSS(self):
        self.do_identifier_for_LSS = True
    
    def get_identifier_for_LSS(self, config_path):
        # 从 config_path 中提取数据集和负载信息，构建唯一标识符
        # 假设 config_path 格式为 .../config/scene/LSS/数据集/负载.txt
        parts = pathlib.Path(config_path).parts#config_path.split(os.sep)
        try:
            idx = parts.index("LSS")
            dataset = parts[idx + 1]
            load = parts[idx + 2].replace(".txt", "")
            identifier = f"{load}"
            print(f"[获取LSS标识] 获取到{config_path}中的identifier: {identifier}")
            return identifier
        except (ValueError, IndexError):
            print(f"[获取LSS标识] 无法从路径 {config_path} 提取 LSS 标识符，使用默认标识符")
            return "LSS_default"

    def run_aqm_simulation_by_easytasks(
        self,
        tasks
            # :list[EasyTask]
        ):
        """
        并行运行多个仿真任务
        :param tasks: EasyTask 对象列表
        :return: True 全部成功，否则 False
        """
        if not tasks:
            print("没有任务可执行")
            return False

        # 汇总参数
        aqm_algos=[]
        cc_algos=[]
        datasets=[]
        configs=[]
        output_dirs=[]
        fct_file_dirs=[]
        write_evaluation_logs=[]
        for task in tasks:
            aqm_algos.append(task.aqm_algo)
            cc_algos.append(task.cc_algo)
            datasets.append(task.dataset)
            configs.append(task.config)
            output_dirs.append(task.output_dir)
            fct_file_dirs.append(task.fct_file_dir)
            write_evaluation_logs.append(task.write_evaluation_log)
        # 执行仿真
        self.run_aqm_simulation(aqm_algos, cc_algos,datasets, configs, output_dirs, fct_file_dirs, write_evaluation_logs)

    def run_aqm_simulation(self,aqm_algos:list,cc_algos:list,datasets:list,configs:list,output_dirs:list,fct_file_dirs:list,write_evaluation_logs:list=None):
        """
        并行运行多个AQM算法的仿真
        :param aqm_algos:  算法名称列表
        :param cc_algos:   CC算法名称列表
        :param configs:     配置文件路径列表，长度需与 aqm_algos 相同；若为 None，则所有算法使用 self.config_path
        :param output_dirs: 输出目录列表，长度需与 aqm_algos 相同；若为 None，则所有算法使用 self.output_dir
        :param fct_file_dirs: 输出目录列表，长度需与 aqm_algos 相同；若为 None，则所有算法使用 self.output_dir
        :param write_evaluation_logs: 每个任务是否输出evaluation日志文件，长度需与 aqm_algos 相同；为None时全部默认为True
        :return:            True 全部成功，否则 False
        """
        if len(configs) != len(aqm_algos):
            raise ValueError("configs 长度必须与 aqm_algos 相同")
            return False
        if len(output_dirs) != len(aqm_algos):
            raise ValueError("output_dirs 长度必须与 aqm_algos 相同")
            return False
        
        # 如果 write_evaluation_logs 为 None，则全部默认为 True
        if write_evaluation_logs is None:
            write_evaluation_logs = [True] * len(aqm_algos)
        
        simulation_start_time = time.time()

        # 准备任务列表
        tasks = []
        for algo, cc_algo, dataset, cfg, out_dir, fct_file_dir, write_log in zip(aqm_algos, cc_algos, datasets, configs, output_dirs, fct_file_dirs, write_evaluation_logs):
            if algo not in self.AQM_DICT:
                print(f"[运行AQM仿真] 未知算法: {algo}，跳过...")
                continue
            # 确保输出目录存在
            os.makedirs(out_dir, exist_ok=True)
            print(f"[运行AQM仿真] 创建OUT_DIR-->{out_dir}")

            # 提取标识符
            identifier = None
            if self.do_identifier_for_LSS:
                identifier = self.get_identifier_for_LSS(cfg)

            # 构建 waf 命令（使用列表形式避免 shell 注入）
            # 默认使用8：DCTCP和1：窗口检查
            run_arg = (f"PRED-evaluation "
                        f"--conf={cfg} "
                        f"--aqm_algorithm={self.AQM_DICT[algo]} "
                        f"--algorithm={self.CC_DICT.get(cc_algo, 8)} "
                        f"--windowCheck={self.WINDOW_DICT.get(cc_algo, 1)} "\
                        f"--fct_output_file_real={fct_file_dir}")
            
            # 创建fct文件所在目录（只创建父目录，fct_file_dir本身是txt文件路径）
            fct_full_path = os.path.join(NS3_DIR, fct_file_dir)
            fct_parent_dir = os.path.dirname(fct_full_path)
            os.makedirs(fct_parent_dir, exist_ok=True)
            print(f"[运行AQM仿真] 创建FCT父目录-->{fct_parent_dir}")

            print(f"[运行AQM仿真] 准备指令：{run_arg}")
            # fct输出路径：mix/场景/

            cmd = ["./waf", "--run", run_arg]
            # 输出日志文件（放在各自输出目录中）
            log_file = os.path.join(out_dir, f"evaluation-{algo}-{cc_algo}-{TIMESTAMP}"+output_file_postfix)
            
            tasks.append((algo, cmd, log_file, identifier, fct_full_path, dataset, write_log))

        if not tasks:
            print("[运行AQM仿真] 没有有效的任务可执行")
            return False

        # # 定义单个仿真执行函数
        # def run_one(algo, cmd, log_file, identifier=None):
        #     print(f"[{algo}] 开始运行，日志 -> {log_file}")
        #     with open(log_file, "w") as f:
        #         result = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
        #     if result.returncode == 0:
        #         print(f"[{algo}] 仿真执行成功！")
        #         if self.enable_fct_output:
        #             # 复制FCT输出（假设每个算法的FCT输出文件名包含算法名，且不冲突）
        #             if self.fct_root_dir and self.fct_output:
        #                 fct_file_name = "fct"
        #                 if identifier!=None:
        #                     fct_file_name +="-"+str(identifier)
        #                 # fct源文件地址
        #                 fct_origin_path = os.path.join(self.fct_root_dir, algo+"/"+fct_file_name+".txt")
        #                 # fct目的地址
        #                 fct_output_path = os.path.join(self.fct_output, algo+"/"+fct_file_name+".txt")
                        
        #                 shutil.copy2(fct_origin_path, fct_output_path)
        #                 print(f"[{algo}] FCT输出已复制到 {fct_output_path}")
        #         return True, algo
        #     else:
        #         print(f"[{algo}] 仿真执行失败，退出码: {result.returncode}")
        #         return False, algo
                # 定义单个仿真执行函数（增加计时和定时输出）
        def run_one(algo, cmd, log_file, identifier, fct_full_path, dataset, write_log):
            # 引用全局变量
            global UNIVERSAL_COUNTER

            start_time = time.time()

            UNIVERSAL_COUNTER+=1
            counter = UNIVERSAL_COUNTER
            
            # 先cd到NS3_DIR目录
            original_dir = os.getcwd()
            os.chdir(NS3_DIR)

            if write_log:
                print(f"[运行AQM仿真：run_one] [{algo}-{counter}] 开始运行，启用 evaluation 日志输出 -> {log_file}")
                # 使用 Popen 以便非阻塞检查
                with open(log_file, "w") as f:
                    proc = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT)
                    # 定时输出运行时长（每 10 秒）
                    interval = 10  # 秒
                    while True:
                        ret = proc.poll()
                        if ret is not None:
                            # 进程已结束
                            break
                        elapsed = int(time.time() - start_time)
                        print(f"[{algo}-{counter}] 已运行 {elapsed} 秒...")
                        time.sleep(interval)
                    
                    # 最终等待确保子进程完全结束（实际上 poll 已结束）
                    proc.wait()
                    result_code = proc.returncode
            else:
                print(f"[运行AQM仿真：run_one] [{algo}-{counter}] 开始运行，禁用 evaluation 日志输出")
                # 使用 Popen 以便非阻塞检查（输出到 DEVNULL）
                proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                # 定时输出运行时长（每 10 秒）
                interval = 10  # 秒
                while True:
                    ret = proc.poll()
                    if ret is not None:
                        # 进程已结束
                        break
                    elapsed = int(time.time() - start_time)
                    print(f"[{algo}-{counter}] 已运行 {elapsed} 秒...")
                    time.sleep(interval)
                
                # 最终等待确保子进程完全结束（实际上 poll 已结束）
                proc.wait()
                result_code = proc.returncode
            
            end_time = time.time()
            total_time = end_time - start_time
            print(f"[运行AQM仿真：run_one] [{algo}-{counter}] 仿真完成，总耗时 {total_time:.2f} 秒，退出码 {result_code}")

            if result_code == 0:
                print(f"[运行AQM仿真：run_one] [{algo}-{counter}] 仿真执行成功！")
                if self.enable_fct_output:
                    # 复制FCT输出（假设每个算法的FCT输出文件名包含算法名，且不冲突）
                    if self.fct_root_dir and self.fct_output:
                        fct_file_name = "fct"
                        if identifier!=None:
                            fct_file_name +="-"+str(identifier)
                        #fct目录格式：mix/场景/数据集/算法/fct-负载.txt
                        # fct源文件地址
                        fct_origin_path = fct_full_path
                        # fct目的地址
                        fct_output_path = os.path.join(self.fct_output, dataset+"/"+algo+"/"+fct_file_name+".txt")
                        
                        os.makedirs(os.path.dirname(fct_output_path), exist_ok=True)
                        print(f"[运行AQM仿真：run_one] 创建：{os.path.dirname(fct_output_path)}")

                        print(f"[运行AQM仿真：run_one] fct_origin_path: {fct_origin_path}\n    fct_output_path: {fct_output_path}")

                        shutil.copy2(fct_origin_path, fct_output_path)
                        print(f"[运行AQM仿真：run_one] [{algo}-{counter}] FCT输出已复制到 {fct_output_path}")
                return True, algo
            else:
                print(f"[{algo}-{counter}] 仿真执行失败，退出码: {result_code}")
                return False, algo

        # 使用线程池并发执行
        success_all = True
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_algo = {executor.submit(run_one, algo, cmd, log, identifier, fct_full_path, dataset, write_log): algo for algo, cmd, log, identifier, fct_full_path, dataset, write_log in tasks}
            for future in as_completed(future_to_algo):
                success, algo = future.result()
                if not success:
                    success_all = False

        print(f"[运行AQM仿真] 仿真执行完毕！耗时：{time.time()-simulation_start_time}")
        return success_all
#===========================================================

def frange(start, stop, step, accuracy=1)->list:
    temp_list = []
    temp_list+=[start]
    while start < stop:
        start += step
        start = round(start, 1)
        temp_list.append(start)
    return temp_list


#--------------------------配置任务--------------------------
# self.AQM_DICT = {
#     "RED": 1,
#     "CoDel": 2,
#     "MATCP": 3,
#     "CEDM": 4,
#     "MBECN": 5,
#     "PRED": 6,
#     "IMCAQM": 7,
#     "FCS": 8,
#     "QLA": 9
# }
ENDL="\n"
#config目录格式：config/scene/场景/数据集/负载.txt
#fct目录格式：mix/场景/数据集/算法/fct-负载.txt
SCENE_NAME = "LSS"

# DATASET = "websearch"
# DATASET = "datamining"
# DATASET = "memcached"
# DATASET = "fbhdp"
# DATASET = "googlerpc"
DATASET = "alistorage"

# WRITE_LOG = True
WRITE_LOG = False

# CC_ALGO = "DCTCP"
CC_ALGO = "DCQCN"

load_min = 0.1
load_max = 0.9
# load_max = 0.1 #只跑一个看看

load_step = 0.1
LOADS = frange(load_min, load_max, load_step)
ALGS = [
    "PRED", 
    "CoDel", 
    "RED"
    ]

# # 补偿未能输出的部分
# load_min = 0.4
# load_max = 0.9
# load_step = 0.1
# LOADS = frange(load_min, load_max, load_step)
# ALGS = ["PRED"]

print(f"负载：{LOADS}")
print(f"算法：{ALGS}")

task_num=0
# 生成系列任务
for load in LOADS:
    load_str = f"{load:.1f}"
    for algo in ALGS:
        task_num+=1
        TASKS.append(
            EasyTask(
                aqm_algo=algo,
                cc_algo=CC_ALGO,
                dataset=DATASET,
                config=os.path.join(PRED_DIR, f"config/scene/{SCENE_NAME}/{DATASET}/{load_str}.txt"),
                output_dir=os.path.join(PRED_DIR, f"dump/PRED/{SCENE_NAME}/{DATASET}/{algo}"),
                fct_file_dir=os.path.join(FCT_ROOT_DIR, f"{SCENE_NAME}/{DATASET}/{algo}/fct-{load_str}.txt"),
                write_evaluation_log=WRITE_LOG
            )
        )
        print(
            f"添加任务【{task_num}】: "+ENDL+
            f"  aqm_algo={algo}, "+ENDL+
            f"  cc_algo=DCTCP, "+ENDL+
            f"  dataset={DATASET}, "+ENDL+
            f"  config={os.path.join(PRED_DIR, f'config/scene/{SCENE_NAME}/{DATASET}/{load_str}.txt')}, "+ENDL+
            f"  output_dir={os.path.join(PRED_DIR, f'dump/PRED/{SCENE_NAME}/{DATASET}/{algo}')}, "+ENDL+
            f"  fct_file_dir={os.path.join(FCT_ROOT_DIR, f'{SCENE_NAME}/{DATASET}/{algo}/fct-{load_str}.txt')}"
        )

print(f"任务总数：{task_num}")

# print(f"TASKS: {TASKS}")
#-----------------------------------------------------------

#***************************主函数***************************
def main():
    """
    主函数：配置仿真参数并调用 AQMSimulationRunner 执行仿真
    """
    # ==================== 配置参数 ====================
    # 配置根目录（config/scene/场景/数据集/负载.txt）
    CONFIG_ROOT = os.path.join(PRED_DIR, "config")

    # 输出根目录（dump/PRED/场景）
    OUTPUT_ROOT = os.path.join(PRED_DIR, "dump", "PRED")

    # FCT 输出根目录
    FCT_ROOT_DIR = os.path.join(PRED_DIR, "mix")

    # FCT 输出目标目录
    FCT_OUTPUT_DIR = os.path.join(OUTPUT_ROOT, SCENE_NAME)

    # 最大并行线程数
    MAX_WORKERS = task_num

    # ==================== 创建仿真运行器 ====================
    print
    runner = AQMSimulationRunner(
        config_path_root=CONFIG_ROOT,
        output_dir_root=OUTPUT_ROOT,
        enable_fct_output=True,
        fct_root_dir=FCT_ROOT_DIR,
        fct_output=FCT_OUTPUT_DIR,
        max_workers=MAX_WORKERS
    )

    runner.enable_identifier_for_LSS()

    # ==================== 准备仿真任务 ====================
    # 示例：使用已有的 TASKS 列表（已在全局定义）
    if TASKS:
        print(f"开始执行 {len(TASKS)} 个仿真任务...")
        runner.run_aqm_simulation_by_easytasks(TASKS)
    else:
        # 手动构建任务示例
        # manual_tasks = [
        #     EasyTask(
        #         aqm_algo="PRED",
        #         cc_algo="DCTCP",
        #         config=os.path.join(PRED_DIR, f"config/config-PRED-{SCENE_NAME}.txt"),
        #         output_dir=os.path.join(PRED_DIR, f"dump/PRED/{SCENE_NAME}"),
        #         fct_file_dir=os.path.join(FCT_ROOT_DIR, f"{SCENE_NAME}/PRED/fct-0.1.txt")#有问题的
        #     )
        # ]
        print(f"不是哥们你任务呢...")
        # runner.run_aqm_simulation_by_easytasks(manual_tasks)

    print("所有仿真任务执行完毕！")


if __name__ == "__main__":
    print("main!")
    main()
#***********************************************************