source config.sh

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
        # 16t1
        # ENABLE_DCQCN="1"
        # evaluation="MV"
    
    # 2to1
        # evaluation="2to1"
        # USE_ALGO="RED"
        # ENABLE_DCQCN="1"

    # LSS
        # evaluation="LSS"
        # # specifier="websearch" #websearch
        # # # specifier="datamining" #datamining
        # # specifier2="l0.9" #Workload = 0.9

    # LLF 长持续流量
        # master_id是5
        # 使用DCQCN
            ENABLE_DCQCN="1"
            specifier="DCQCN"
        #使用DCTCP
            # ENABLE_DCQCN="0"
            # specifier="DCTCP"
        evaluation="LLF"
    
    # SBF 短突发流量
        # master_id是15
        # 使用DCQCN
            # ENABLE_DCQCN="1"
            # specifier2="DCQCN"
        # 使用DCTCP
            # ENABLE_DCQCN="0"
            # specifier2="DCTCP"
        # evaluation="SBF"

    # RCF 高速变化流量
        # master_id是17
        # 使用DCQCN
            # ENABLE_DCQCN="1"
            # specifier="DCQCN"
        # 使用DCTCP
            # ENABLE_DCQCN="0"
            # specifier="DCTCP"

        # USE_ALGO="RED"
        # evaluation="RCF"

    # SIF Sustain+Incast Flow 持续+突发流量场景
        # master_id是65
        # 使用DCQCN
            # ENABLE_DCQCN="1"
            # specifier="DCQCN"
        # 使用DCTCP
            # ENABLE_DCQCN="0"
            # specifier="DCTCP"
        # 具体流量
            # specifier2="N4_burst0"
            # specifier2="N4_burst2_small_large"
            # specifier2="N20_burst0"
            # specifier2="N20_burst2_small_large"

            # specifier2="N10_burst0"
        # USE_ALGO="RED"
        # evaluation="SIF"

# PRED算法Config
    if [ "$USE_ALGO" = "PRED" ]; then
        echo "使用PRED"
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
        echo "$configFile"
    elif [ "$USE_ALGO" = "RED" ]; then
        echo "使用RED"
        algs=(0)
        if [ -n "$lambda" ]; then
            configFile="$NS3/examples/PRED/config-RED-L${lambda}-${evaluation}-${specifier}.txt"
        else
            configFile="$NS3/examples/PRED/config-RED-${evaluation}.txt"
        fi
                if [ -n "$specifier" ]; then
            if [ -n "$specifier2" ]; then
                configFile="$NS3/examples/PRED/config-RED-${evaluation}-${specifier}-${specifier2}.txt"
            else
                configFile="$NS3/examples/PRED/config-RED-${evaluation}-${specifier}.txt"
            fi
        else
            configFile="$NS3/examples/PRED/config-RED-${evaluation}.txt"
        fi
        echo "$configFile"
    fi

    #########################################################特殊测试
    ########用codel试试呢
    # algs=(1)
    # echo "强行使用codel"

    # algs=(0)
    # echo "强行使用RED"

    # configFile="$NS3/examples/PRED/config-PRED-LSS-2to1.txt"
    #################################################################

    # 正常PRED，无specifier
        # configFile=$NS3/examples/PRED/config-PRED-${evaluation}.txt
    # 含specifier的PRED配置
        # configFile=$NS3/examples/PRED/config-PRED-${evaluation}-${specifier}.txt
    # LSS场景特供双specifier配置
        # configFile=$NS3/examples/PRED/config-PRED-${evaluation}-${specifier}-${specifier2}.txt

# RED算法Config
    # 正常RED，无lambda无specifier
        # configFile=$NS3/examples/PRED/config-RED-${evaluation}.txt
    # 这是RED点斜式
        # lambda=0.2
        # # lambda=2
        # configFile=$NS3/examples/PRED/config-RED-L${lambda}-${evaluation}-${specifier}.txt

# 结果输出路径
    RES_DUMP=$NS3/examples/PRED/dump/PRED/${evaluation}${specifier:+/$specifier}${specifier2:+/$specifier2}

#是否包含FCT输出
    DO_FCT_OUTPUT=1 #是
    # DO_FCT_OUTPUT=0 #否
    FCT_DIR=$NS3/mix/fct.txt
    FCT_OUTPUT=$RES_DUMP/fct_output
#######################################################################################

mkdir -p $RES_DUMP
# mkdir -p $FCT_OUTPUT #已移动至后续内容

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
# ccNames="dctcp"
# CCMODE=8
# window=1
#############################

#######################################################################################
#配置要测试的算法
# algs=(0 1 2 3 4 5 6)
    # 这个是PRED
        # algs=(5)
    #这个是RED
        # algs=(0)

aqmNames=("RED" "CoDel" "MATCP" "CEDM" "MBECN" "PRED" "IMCAQM")
aqmModes=(1 2 3 4 5 6 7)
#######################################################################################

cd $NS3

TIMESTAMP=$(date +%Y%m%d_%H%M%S) #当前时间

for algorithm in ${algs[@]};do
    # 结果文件名
        if [ -n "$lambda" ]; then
            POST_FIX=${aqmNames[$algorithm]}-L${lambda}-${TIMESTAMP}
        else
             POST_FIX=${aqmNames[$algorithm]}-${TIMESTAMP}
        fi
        # 无lambda
        # POST_FIX=${aqmNames[$algorithm]}-${TIMESTAMP}
        # 有lambda
        # POST_FIX=${aqmNames[$algorithm]}-L${lambda}-${TIMESTAMP}

    RESULT_FILE="${RES_DUMP}/evaluation-${POST_FIX}.out"

    #########################################################特殊测试
    # RESULT_FILE="${RES_DUMP}/evaluation-SPECIAL-PRED-LSS-2to1-${TIMESTAMP}.out"
    # POST_FIX="SPECIAL-PRED-LSS-2to1-${TIMESTAMP}"
    #################################################################

    echo "正在执行${POST_FIX}"
                                                        #无lambda
                                                            # echo "evaluation-${aqmNames[$algorithm]}-${TIMESTAMP}.out"
                                                            # RESULT_FILE="$RES_DUMP/evaluation-${aqmNames[$algorithm]}-${TIMESTAMP}.out"
                                                        #有lambda
                                                            # echo "evaluation-${aqmNames[$algorithm]}-L${lambda}-${TIMESTAMP}.out"
                                                            # RESULT_FILE="$RES_DUMP/evaluation-${aqmNames[$algorithm]}-L${lambda}-${TIMESTAMP}.out"
    #执行仿真
	time ./waf --run "PRED-evaluation --conf=$configFile --algorithm=$CCMODE  --windowCheck=$window --aqm_algorithm=${aqmModes[$algorithm]}" > $RESULT_FILE  2> $RESULT_FILE &
	# time ./waf --run "${ThisTarget} --conf=$configFile --algorithm=${CC_MODE} --wien=$wien --delayWien=$delay --windowCheck=$window" > $RESULT_FILE  2> $RESULT_FILE &

done

#后续是仿真进行时间的输出，25秒输出一次
START_TIME=$(date +%s)

WAF_PID=$!

echo "仿真进程 PID: $WAF_PID"

# 初始化计数器
WAIT_COUNT=0

# 监控进程状态并定期输出时间
while kill -0 $WAF_PID 2>/dev/null; do
    # 每5秒输出一次当前时间
    if (( WAIT_COUNT % 5 == 0 )); then  # 每5次循环（25秒）输出一次
        CURRENT_TIME=$(date +"%Y-%m-%d %H:%M:%S")
        ELAPSED=$(( $(date +%s) - START_TIME ))

        # 格式化为时分秒
        ELAPSED_FORMATTED=$(printf "%02d:%02d:%02d" $((ELAPSED/3600)) $((ELAPSED%3600/60)) $((ELAPSED%60)))

        echo "等待中... 当前时间: $CURRENT_TIME, 已运行: $ELAPSED_FORMATTED"

        # 每60秒额外输出更详细的信息
        if (( ELAPSED % 60 == 0 )) && (( ELAPSED > 0 )); then
            echo "已运行 $((ELAPSED/60)) 分钟..."
        fi
    fi

    WAIT_COUNT=$((WAIT_COUNT + 1))
    sleep 5  # 每5秒检查一次
done

# 等待进程完全退出，确保获取正确的退出状态
wait $WAF_PID
EXIT_STATUS=$?

# 记录结束时间
END_TIME=$(date +%s)
TOTAL_TIME=$(( END_TIME - START_TIME ))
TOTAL_TIME_FORMATTED=$(printf "%02d:%02d:%02d" $((TOTAL_TIME/3600)) $((TOTAL_TIME%3600/60)) $((TOTAL_TIME%60)))

# 如果需要输出FCT，则从FCT_DIR复制到FCT_OUTPUT
if [ $DO_FCT_OUTPUT -eq 1 ]; then
    mkdir -p $FCT_OUTPUT
    cp $FCT_DIR $FCT_OUTPUT/fct-${aqmNames[$algorithm]}-${TIMESTAMP}.txt
    echo "FCT输出已复制到: $FCT_OUTPUT"
fi

echo ""
echo "##################################"
echo "#     仿真已完成                 #"
echo "##################################"
echo "开始时间: $(date -d @$START_TIME '+%Y-%m-%d %H:%M:%S')"
echo "结束时间: $(date -d @$END_TIME '+%Y-%m-%d %H:%M:%S')"
echo "总运行时间: $TOTAL_TIME_FORMATTED"


# 绘图
cd $NS3/examples/PRED/

DUMP_DIR=dump/PRED/${evaluation}${specifier:+/$specifier}${specifier2:+/$specifier2}

LOW_CUT=0
HIGH_CUT=3999 #单位ms，10分钟
# HIGH_CUT=10 #单位ms，10ms
# HIGH_CUT=5 #单位ms，5ms

# STEP=100
# STEP=10
STEP=1

# MASTER_ID=17 # 16打1
# MASTER_ID=21 # 20打1
MASTER_ID=5 # 4打1
# MASTER_ID=3 # 2打1
# MASTER_ID=15 # 14打1
# MASTER_ID=65 #64打1

# Y_LIM=-1 #不启用
# Y_LIM=100
Y_LIM=50
# Y_LIM=200

echo "正在绘制图表plot-2to1..."
bash1="python3 plot-2to1.py --low-cut-ms ${LOW_CUT} --high-cut-ms ${HIGH_CUT} --step ${STEP} --master-id ${MASTER_ID} --dump-dir ${DUMP_DIR} --alg ${POST_FIX} --queue-ylim ${Y_LIM}"
echo $bash1
time $bash1
echo "绘制完毕"

echo "正在绘制图表plot-PRED-statics..."
bash2="python3 plot-PRED-statics.py --low-cut-ms ${LOW_CUT} --high-cut-ms ${HIGH_CUT} --step ${STEP} --master-id ${MASTER_ID} --dump-dir ${DUMP_DIR} --alg ${POST_FIX}"
echo $bash2
time $bash2
echo "绘制完毕"