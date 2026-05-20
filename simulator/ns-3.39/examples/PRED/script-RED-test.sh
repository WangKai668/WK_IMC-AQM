source config.sh
configFile=$NS3/examples/PRED/config-RED.txt
RES_DUMP=$NS3/examples/PRED/dump/RED-test

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

windowall=$1
if [[ $windowall == "yes" ]];then
	nowindow="no"
else
	if [[ $2 == "yes" ]];then
	nowindow="yes"
	windowall="no"
	fi
fi
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

TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "evaluation-red-${TIMESTAMP}.out $N"
RESULT_FILE="$RES_DUMP/evaluation-red-${TIMESTAMP}.out"
# echo "time ./waf --run "evaluation-fairness --algorithm=${CCMODE[$algorithm]} --wien=$wien --delayWien=$delay --windowCheck=$window""
time ./waf --run "RED --conf=$configFile --algorithm=${CC_MODE} --wien=$wien --delayWien=$delay --windowCheck=$window" > $RESULT_FILE  2> $RESULT_FILE &



#while [[ $(ps aux|grep "powertcp-evaluation-burst-optimized"|wc -l) -gt 1 ]];do
while [[ $(ps aux|grep "RED-optimized"|wc -l) -gt 1 ]];do
	echo "Waiting for cpu cores.... $N-th experiment "
	sleep 5
done


echo "##################################"
echo "#      FINISHED EXPERIMENTS      #"
echo "##################################"
