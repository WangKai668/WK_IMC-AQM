source config.sh
# 用法：
#   ./script-evaluation.sh 2to1
# scenario="2to1_burst"
scenario="10to1_burst"
# scenario="10to1"
# scenario="2to1"

configFile="$NS3/examples/IMC-AQM/config-${scenario}.txt"
RES_DUMP="$NS3/examples/IMC-AQM/dump_${scenario}"

mkdir $RES_DUMP

# algs=(0 1 2 3 6)  # 4MBECN没实现   5PRED还没实现完

algs=(0)
# algs=(6)
aqmNames=("RED" "CoDel" "MATCP" "CEDM" "MBECN" "PRED" "IMCAQM")
aqmModes=(1 2 3 4 5 6 7)

cd $NS3

for algorithm in ${algs[@]};do
	echo "evaluation-${aqmNames[$algorithm]}.out"
	RESULT_FILE="$RES_DUMP/evaluation-${aqmNames[$algorithm]}.out"
	if [[ "${aqmNames[$algorithm]}" == "MATCP" ]]; then
        ccNames="dctcp"
        CCMODE=8
        window=1
    else
		ccNames="dcqcn"
		CCMODE=1
		window=0
	fi
	time ./waf --run "aqm-evaluation --conf=$configFile --algorithm=$CCMODE  --windowCheck=$window --aqm_algorithm=${aqmModes[$algorithm]}" > $RESULT_FILE  2> $RESULT_FILE &
	# time ./waf --run "${ThisTarget} --conf=$configFile --algorithm=${CC_MODE} --wien=$wien --delayWien=$delay --windowCheck=$window" > $RESULT_FILE  2> $RESULT_FILE &
	sleep 2
done

echo "##################################"
echo "#      FINISHED EXPERIMENTS      #"
echo "##################################"
