source config.sh
configFile=$NS3/examples/PRED/config-PRED-2to1.txt
RES_DUMP=$NS3/examples/PRED/dump/PRED-2to1

mkdir $RES_DUMP

# ccNames="dcqcn"
# CCMODE=1
# window=0
ccNames="pred"
CCMODE=6
window=1

# algs=(0 1 2 3 4 5 6)
algs=(5)
aqmNames=("RED" "CoDel" "MATCP" "CEDM" "MBECN" "PRED" "IMCAQM")
aqmModes=(1 2 3 4 5 6 7)

cd $NS3

TIMESTAMP=$(date +%Y%m%d_%H%M%S)

for algorithm in ${algs[@]};do
	echo "evaluation-${aqmNames[$algorithm]}-${TIMESTAMP}.out"
	RESULT_FILE="$RES_DUMP/evaluation-${aqmNames[$algorithm]}-${TIMESTAMP}.out"
	time ./waf --run "PRED-2to1 --conf=$configFile  --windowCheck=$window --algorithm=${aqmModes[$algorithm]}" > $RESULT_FILE  2> $RESULT_FILE &
	# time ./waf --run "${ThisTarget} --conf=$configFile --algorithm=${CC_MODE} --wien=$wien --delayWien=$delay --windowCheck=$window" > $RESULT_FILE  2> $RESULT_FILE &

done

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

echo ""
echo "##################################"
echo "#     仿真已完成                 #"
echo "##################################"
echo "开始时间: $(date -d @$START_TIME '+%Y-%m-%d %H:%M:%S')"
echo "结束时间: $(date -d @$END_TIME '+%Y-%m-%d %H:%M:%S')"
echo "总运行时间: $TOTAL_TIME_FORMATTED"