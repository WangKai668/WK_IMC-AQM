source config.sh
# 本脚本用于大型真实流量仿真
#("RED" "CoDel" "MATCP" "CEDM" "MBECN" "PRED" "IMCAQM" "FCS" "QLA")
#   0      1       2      3       4      5       6      7       8 
#######################################################################################
ENABLE_DCQCN="0"
USE_ALGO="PRED"
#配置具体的仿真内容
    # PWDCQCN
        # ENABLE_DCQCN="1"
        # evaluation="PWDCQCN"
        # specifier="20t1" #20打1
        # # specifier="2t1" #2打1
        # 这是RED点斜式
            # USE_ALGO="RED"
            # lambda=0.2
            # # lambda=2

    # MV
        # evaluation="MV"

    # LSS
        # evaluation="LSS"
        # specifier="websearch" #websearch
        # # specifier="datamining" #datamining
        # specifier2="l0.9" #Workload = 0.9

    # LLF 长持续流量
        #使用DCQCN
            # ENABLE_DCQCN="1"
            # specifier2="DCQCN"
        #使用DCTCP
            # ENABLE_DCQCN="0"
            # specifier2="DCTCP"
        # evaluation="LLF"
    
    # SBF 短突发流量
        ENABLE_DCQCN="1" # 可选
        evaluation="SBF"

    # RCF 高速变化流量
        # evaluation="RCF"


# PRED算法Config
    if [ "$USE_ALGO" = "PRED" ]; then
        algs=(5)
        if [ -n "$specifier" ]; then
            if [ -n "$specifier2" ]; then
                configFile="$NS3/examples/PRED/config-PRED-${evaluation}-${specifier}-${specifier2}.txt"
            else
                configFile="$NS3/examples/PRED/config-PRED-${evaluation}-${specifier}.txt"
            fi
        else
            configFile="$NS3/examples/PRED/config-PRED-${evaluation}.txt"
        fi
    elif [ "$USE_ALGO" = "RED" ]; then
        algs=(0)
        if [ -n "$lambda" ]; then
            configFile="$NS3/examples/PRED/config-RED-L${lambda}-${evaluation}-${specifier}.txt"
        else
            configFile="$NS3/examples/PRED/config-RED-${evaluation}.txt"
        fi
    fi

# 结果输出路径
    RES_DUMP=$NS3/examples/PRED/dump/PRED/${evaluation}${specifier:+/$specifier}${specifier2:+/$specifier2}

#是否包含FCT输出
    DO_FCT_OUTPUT=1 #是
    # DO_FCT_OUTPUT=0 #否
    FCT_DIR=$NS3/mix/fct.txt
    FCT_OUTPUT=$RES_DUMP/fct_output
#######################################################################################

mkdir -p $RES_DUMP

#############################
#配置使用DCQCN还是DCTCP
if [ "$ENABLE_DCQCN" = "1" ]; then
    ccNames="dcqcn"
    CCMODE=1
    window=0
    echo "使用DCQCN算法进行仿真..."
else
    ccNames="dctcp"
    CCMODE=8
    window=1
    echo "使用DCTCP算法进行仿真..."
fi
#############################

#######################################################################################
#配置要测试的算法（支持多个，例如 algs=(0 1 2 3 4 5 6)）
# 当前根据 USE_ALGO 仅设单个，可手动改为多个以并行
algs=(5)   # 可改为 (0 1 2 3 4 5 6) 并行运行所有算法

aqmNames=("RED" "CoDel" "MATCP" "CEDM" "MBECN" "PRED" "IMCAQM")
aqmModes=(1 2 3 4 5 6 7)
#######################################################################################

cd $NS3

TIMESTAMP=$(date +%Y%m%d_%H%M%S) #当前时间

# ==================== 并行执行仿真 ====================
pids=()          # 存储后台进程PID
post_fixes=()    # 存储每个算法对应的 POST_FIX（用于后续绘图）

for algorithm in ${algs[@]}; do
    # 生成 POST_FIX 和 RESULT_FILE
    if [ -n "$lambda" ]; then
        POST_FIX=${aqmNames[$algorithm]}-L${lambda}-${TIMESTAMP}
    else
        POST_FIX=${aqmNames[$algorithm]}-${TIMESTAMP}
    fi
    RESULT_FILE="${RES_DUMP}/evaluation-${POST_FIX}.out"

    # 启动子shell后台进程，包含仿真执行和FCT复制
    (
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始运行 $POST_FIX ..."
        time ./waf --run "PRED-evaluation --conf=$configFile --algorithm=$CCMODE --windowCheck=$window --aqm_algorithm=${aqmModes[$algorithm]}" > $RESULT_FILE 2>&1
        exit_code=$?
        
        # 如果需要复制FCT，每个算法独立进行（文件名已含算法名，不会冲突）
        if [ $DO_FCT_OUTPUT -eq 1 ]; then
            mkdir -p $FCT_OUTPUT
            cp $FCT_DIR $FCT_OUTPUT/fct-${aqmNames[$algorithm]}-${TIMESTAMP}.txt 2>/dev/null
            echo "FCT输出已复制到: $FCT_OUTPUT/fct-${aqmNames[$algorithm]}-${TIMESTAMP}.txt"
        fi
        
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 完成 $POST_FIX , 退出码 $exit_code"
    ) &
    
    pid=$!
    pids+=($pid)
    post_fixes+=("$POST_FIX")
    echo "已启动 $POST_FIX (PID: $pid)"
done

# 等待所有后台仿真进程完成
echo "等待所有仿真完成..."
for i in "${!pids[@]}"; do
    wait ${pids[$i]}
    echo "进程 ${pids[$i]} (${post_fixes[$i]}) 已结束"
done

echo "所有仿真已完成，开始绘图..."

# ==================== 为每个算法分别绘图 ====================
cd $NS3/examples/PRED/

DRUMP_DIR=dump/PRED/${evaluation}${specifier:+/$specifier}${specifier2:+/$specifier2}

LOW_CUT=0
HIGH_CUT=399   # 单位ms，10分钟
STEP=100
MASTER_ID=5    # 根据实际情况修改

for i in "${!algs[@]}"; do
    POST_FIX="${post_fixes[$i]}"
    echo "正在为 ${POST_FIX} 绘制图表 plot-2to1 ..."
    time python3 plot-2to1.py --low-cut-ms ${LOW_CUT} --high-cut-ms ${HIGH_CUT} --step ${STEP} --master-id ${MASTER_ID} --dump-dir ${DRUMP_DIR} --alg ${POST_FIX}
    
    echo "正在为 ${POST_FIX} 绘制图表 plot-PRED-statics ..."
    time python3 plot-PRED-statics.py --low-cut-ms ${LOW_CUT} --high-cut-ms ${HIGH_CUT} --step ${STEP} --master-id ${MASTER_ID} --dump-dir ${DRUMP_DIR} --alg ${POST_FIX}
done

echo "全部绘图完成！"