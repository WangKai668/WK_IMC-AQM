# 用于生成具体场景的单个/多个config配置
import os
import sys
import random
import heapq
import math
from optparse import OptionParser
#=======================配置面板=============================
# LSS场景
output_file_postfix=".txt"
output_file_prefix="config-"
output_prefix="./scene/"        # 输出文件的前缀路径，默认为当前目录
scene_name="LSS"                # 场景名称，默认为"LSS"
#config/scene/场景/数据集/负载.txt

#===========================================================

config_basic = {
    "ENABLE_QCN":                   1,
    "USE_DYNAMIC_PFC_THRESHOLD":    1,

    "PACKET_PAYLOAD_SIZE":          1000,

    "TRACE_FILE":                   "mix/trace.txt",
    # FLOW_FILE examples/PRED/.traffic_gen/traffic/traffic_datamining_n128_l0.900000_b1e+10_t0s.txt
    "TRACE_OUTPUT_FILE":            "mix/mix.tr",
    "FCT_OUTPUT_FILE":              "mix/fct.txt",
    "PFC_OUTPUT_FILE":              "mix/pfc.txt",

    "SIMULATOR_STOP_TIME":          0.01,#10ms

    # CC_MODE 6
    # ALPHA_RESUME_INTERVAL 1
    # RATE_DECREASE_INTERVAL 4
    # CLAMP_TARGET_RATE 0
    # RP_TIMER 900
    # #DCTCP的g参数，改为1/16，0.0625，之前是0.00390625
    # #改成1/8呢？
    # EWMA_GAIN 0.0625
    # FAST_RECOVERY_TIMES 1
    # RATE_AI 50Mb/s
    # RATE_HAI 100Mb/s
    # MIN_RATE 100Mb/s
    # DCTCP_RATE_AI 1000Mb/s

    "ERROR_RATE_PER_LINK":          0.0000,
    "L2_CHUNK_SIZE":                4000,
    "L2_ACK_INTERVAL":              1,
    "L2_BACK_TO_ZERO":              0,
    "HAS_WIN":                      1,
    "GLOBAL_T":                     1,
    "VAR_WIN":                      1,
    "FAST_REACT":                   1,
    "U_TARGET":                     0.95,
    "MI_THRESH":                    5,
    "INT_MULTI":                    1,
    "MULTI_RATE":                   0,
    "SAMPLE_FEEDBACK":              0,
    "PINT_LOG_BASE":                1.05,
    "PINT_PROB":                    1.0,
    "RATE_BOUND":                   1,
    "ACK_HIGH_PRIO":                0,
    "LINK_DOWN":                    [0, 0, 0],
    "ENABLE_TRACE":                 1,

    "KMAX_MAP":                     500,
    #kmin初始设置为10，这里因为队列长度一直是10480
    #必须设置一个可以让lambda=2和0.2
    #在丢包队列上有区分度的kmin，采用10.479（KB）
    "KMIN_MAP":                     10.479,
    "PMAX_MAP":                     1,
    "BUFFER_SIZE":                  4,
    "QLEN_MON_FILE":                "mix/qlen.txt",
    "QLEN_MON_START":               2000000000,
    "QLEN_MON_END":                 2010000000
}

config_CC = {
    "CC_MODE":                      6,
    "ALPHA_RESUME_INTERVAL":        1,
    "RATE_DECREASE_INTERVAL":       4,
    "CLAMP_TARGET_RATE":            0,
    "RP_TIMER":                    900,
    # DCTCP的g参数，改为1/16，0.0625，之前是0.00390625
    # 改成1/8呢？
    "EWMA_GAIN":                   0.0625,
    "FAST_RECOVERY_TIMES":          1,
    "RATE_AI":                     "50Mb/s",     # 50Mb/s
    "RATE_HAI":                    "100Mb/s",    # 100Mb/s
    "MIN_RATE":                    "100Mb/s",    # 100Mb/s
    "DCTCP_RATE_AI":               "1000Mb/s"   # 1000Mb/s
}

config_flow_file = {
    "FLOW_FILE": "examples/PRED/.traffic_gen/traffic/traffic_datamining_n128_l0.900000_b1e+10_t0s.txt"
}

config_pred_basic = {
    #PRED核心参数
        #FCS
    "TFCS_FACTOR":          1.25,
    "FCS_BITMAP_SIZE":      10,
        #QLA:UF
    "TQLA_FACTOR":          5,
    "BETA":                 0.4,
    "Q_LEFT":               15,
    "Q_RIGHT":              500,
        #QLA:DM
        ##LAMBDA_BASE默认是0.65
    "LAMBDA_BASE":          0.65,
    "LAMBDA_DELTA":         0.025,
        #QLA:minKAdjuster
    "MINK":                 10,
    "MINK_DELTA":           5,
    "LAMBDA_MIN":           0.05,
        #PRED
    "MAXK":                 500
}

config_LSS = {
    "TOPOLOGY_FILE":        "examples/PRED/topology-LSS.txt",

    "SIMULATOR_STOP_TIME":  0.05,#跑50ms

    # LSS场景链路时延10us，链路带宽10Gbps
    "LINK_DELAY":           "10us",
    "MY_BANDWIDTH_GBPS":    10,

    #仅启用接收端port模拟：不开启
    "ONLY_RECEIVER_PORT":   0,
    #接收端portid
    "RECEIVER_PORT_ID":     17,
}
#------------------------组装Config的类----------------------
class ConfigComposer:
    # 初始化接收一个基本配置字典
    def __init__(self, config_init):
        self.config = config_init

    # 添加或更新配置项
    def insert_or_update_config(self, key, value):
        if key in self.config:
            # print(f"🔄 更新配置项 '{key}' 的值: {self.config[key]} -> {value}")
            self.config[key] = value
        else:
            # print(f"⚠️ 配置项 '{key}' 不存在于config中，进行添加。")
            self.config[key] = value 
    
    # 插入新config字典（覆盖原有的key）
    def add_config_dict(self, new_config):
        for key, value in new_config.items():
            self.insert_or_update_config(key, value)
        
    def compose(self):
        # 将basic_config和cc_config合并成一个完整的配置字典
        config_dict = self.config.copy()
        return config_dict
#------------------------------------------------------------
#-----------------------生成配置文件的类----------------------
class ConfigWriter:
    def __init__(self, config_dict):
        self.config_dict = config_dict

    def write_config(self, output_path):
        #如果不存在，就创建
        if not os.path.exists(os.path.dirname(output_path)):
            os.makedirs(os.path.dirname(output_path))
        # 将配置字典写入文件
        with open(output_path, 'w') as f:
            for key, value in self.config_dict.items():
                # 如果值是列表，则将其转换为字符串
                if isinstance(value, list):
                    value_str = ' '.join(map(str, value))
                # 否则直接转换为字符串
                else:
                    value_str = str(value)
                f.write(f"{key} {value_str}\n")
        print(f"✅ 配置文件已生成: {output_path}")

#------------------------------------------------------------

#-----------------------处理不同场景的类----------------------
class SceneHandler:
    def __init__(self, scene_name):
        self.scene_name = scene_name

    def frange(self, start, stop, step, accuracy=1)->list:
        temp_list = []
        temp_list+=[start]
        while start < stop:
            start += step
            start = round(start, 1)
            temp_list.append(start)
        return temp_list
    # def frange(self, start, stop, step)->list:
    #     temp_list = []
    #     temp_list+=[start]
    #     while start <= stop:
    #         start += step
    #         temp_list.append(start)
    #     return temp_list

    def process_config(self):
        config_dict = {}
        config_composer = None
        config_writer = None
        #config/scene/场景/数据集/负载.txt
        output_path_prefix = output_prefix+options.scene+"/";#config/scene/场景
        output_path = "";

        if self.scene_name == "LSS":
            print(f"生成{self.scene_name}配置中")
            # LSS场景包含多个负载点，调整相关参数
            loads = self.frange(0.1, 0.9, 0.1)#先硬编码了吧
            print(f"负载点: {loads}")
            cdfs = ["datamining","websearch"] # 先硬编码了吧

            for cdf in cdfs:
                # output_path = output_path_prefix+cdf+"/";#config/scene/场景/数据集
                for load in loads:
                    # #精确到小数点后一位
                    load = round(load, 1)
                    print(f"    负载: {load}")

                    output_path = output_path_prefix+cdf+"/" + str(load) + output_file_postfix;#config/scene/场景/数据集/负载.txt

                    config_flow_file = {
                        "FLOW_FILE": f"examples/PRED/.traffic_gen/traffic/{self.scene_name}/{cdf}/{load}.txt"
                    }
                    # fct_config = {
                    #     "FCT_OUTPUT_FILE" : f"mix/{self.scene_name}/{cdf}/fct-{load}.txt"
                    # }
                    config_composer = ConfigComposer(config_basic)
                    config_composer.add_config_dict(config_CC)
                    config_composer.add_config_dict(config_pred_basic)
                    config_composer.add_config_dict(config_LSS)
                    config_composer.add_config_dict(config_flow_file)
                    config_dict = config_composer.compose()

                    config_writer = ConfigWriter(config_dict)
                    config_writer.write_config(output_path)
                print(f"        已生成{self.scene_name}配置到 {output_path}")

            print(f"✅ 场景 '{self.scene_name}' 的配置已处理。")
        else:
            print(f"⚠️ 场景 '{self.scene_name}' 未定义，使用基本配置。")
            config_dict = config_basic.copy()
#------------------------------------------------------------
#***************************主函数***************************
if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("--scene", dest = "scene", help = "the scene name", default = scene_name)
    options,args = parser.parse_args()
    if options.scene:
        scene_name = options.scene

    scene_handler = SceneHandler(scene_name)
    scene_handler.process_config()
#***********************************************************
