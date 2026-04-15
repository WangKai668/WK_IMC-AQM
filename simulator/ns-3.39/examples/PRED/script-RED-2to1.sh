source config.sh
configFile=$NS3/examples/PRED/config-RED-2to1.txt
RES_DUMP=$NS3/examples/PRED/dump/RED-2to1

mkdir -p $RES_DUMP

algs=(0 1 2 3 4 5)

#RED的ccmode被设置为0
algNames=("dcqcn" "powerInt" "hpcc" "powerDelay" "timely" "dctcp" "red")
CCMODE=(1 3 3 3 7 8 1)

ALGO="red"
CC_MODE=1

# at the moment, power int and delay are called from hpcc ACK function separately and hence cc mode is still 3.

#--wien=true --delayWien=false

wien=false
delay=false

cd $NS3

# windowall=$1
# if [[ $windowall == "yes" ]];then
# 	nowindow="no"
# else
# 	if [[ $2 == "yes" ]];then
# 	nowindow="yes"
# 	windowall="no"
# 	fi
# fi

#这里就不用命令行传参数了，可能没什么用？
windowall="yes"
nowindow="no"

echo "WindowAll=$windowall NoWindowForAll=$nowindow"

######################################

# Topology and flows are specified in config file already, path to config file is also in .cc file. ToDo need to automate.

#####################################

# 下面是原来自带的多算法测试，修改为仅测试RED
# N=1
# for algorithm in ${algs[@]};do
# 	if [[ ${algNames[$algorithm]} == "powerInt" || ${algNames[$algorithm]} == "powerDelay" ]];then
# 		wien=true
# 	else
# 		wien=false
# 	fi

# 	if [[ ${algNames[$algorithm]} == "powerDelay" ]];then
# 		delay=true
# 	else
# 		delay=false
# 	fi

# 	if [[ ${algNames[$algorithm]} == "timely" || ${algNames[$algorithm]} == "dcqcn" ]];then
# 		window=0
# 	else
# 		window=1
# 	fi

	if [[ $windowall == "yes" ]];then
		window=1
	fi

	if [[ $nowindow == "yes" ]];then
		window=0
	fi

# 	sleep 5
# 	# Check how many cores are being used.
# 	while [[ $(ps aux|grep "powertcp-evaluation-burst-optimized"|wc -l) -gt 38 ]];do
# 		echo "Waiting for cpu cores.... $N-th experiment "
# 		sleep 60
# 	done


# 	echo "evaluation-${algNames[$algorithm]}.out $N"
# 	N=$(( $N+1 ))
# 	RESULT_FILE="$RES_DUMP/evaluation-${algNames[$algorithm]}.out"
# 	# echo "time ./waf --run "evaluation-fairness --algorithm=${CCMODE[$algorithm]} --wien=$wien --delayWien=$delay --windowCheck=$window""
# 	time ./waf --run "powertcp-evaluation-burst --conf=$configFile --algorithm=${CCMODE[$algorithm]} --wien=$wien --delayWien=$delay --windowCheck=$window" > $RESULT_FILE  2> $RESULT_FILE &
# done

N=1
# while [[ $(ps aux|grep "powertcp-evaluation-burst-optimized"|wc -l) -gt 38 ]];do
# 	echo "Waiting for cpu cores.... $N-th experiment "
# 	sleep 60
# done

START_TIME=$(date +%s)

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ThisTarget="RED-2to1"

echo "evaluation-${ThisTarget}-${TIMESTAMP}.out $N"
RESULT_FILE="$RES_DUMP/evaluation-${ThisTarget}-${TIMESTAMP}.out"
# echo "time ./waf --run "evaluation-fairness --algorithm=${CCMODE[$algorithm]} --wien=$wien --delayWien=$delay --windowCheck=$window""
time ./waf --run "${ThisTarget} --conf=$configFile --algorithm=${CC_MODE} --wien=$wien --delayWien=$delay --windowCheck=$window" > $RESULT_FILE  2> $RESULT_FILE &

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

#while [[ $(ps aux|grep "powertcp-evaluation-burst-optimized"|wc -l) -gt 1 ]];do
# while [[ $(ps aux|grep "${ThisTarget}-optimized"|wc -l) -gt 1 ]];do
# 	echo "Waiting for cpu cores.... $N-th experiment "
# 	sleep 5
# done


# echo "##################################"
# echo "#      FINISHED EXPERIMENTS      #"
# echo "##################################"
