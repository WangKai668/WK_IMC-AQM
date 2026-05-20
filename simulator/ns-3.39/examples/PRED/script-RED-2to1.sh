source config.sh
configFile=$NS3/examples/PRED/config-PRED-2to1.txt
RES_DUMP=$NS3/examples/PRED/dump_2to1

mkdir $RES_DUMP

# ccNames="dcqcn"
# CCMODE=1
# window=0
ccNames="dctcp"
CCMODE=8
window=1

# algs=(0 1 2 3 4 5 6)
algs=(5)
aqmNames=("RED" "CoDel" "MATCP" "CEDM" "MBECN" "PRED" "IMCAQM")
aqmModes=(1 2 3 4 5 6 7)

cd $NS3

for algorithm in ${algs[@]};do
	echo "evaluation-${aqmNames[$algorithm]}.out"
	RESULT_FILE="$RES_DUMP/evaluation-${aqmNames[$algorithm]}.out"
	time ./waf --run "aqm-evaluation --conf=$configFile --algorithm=$CCMODE  --windowCheck=$window --aqm_algorithm=${aqmModes[$algorithm]}" > $RESULT_FILE  2> $RESULT_FILE &
	# time ./waf --run "${ThisTarget} --conf=$configFile --algorithm=${CC_MODE} --wien=$wien --delayWien=$delay --windowCheck=$window" > $RESULT_FILE  2> $RESULT_FILE &

done

echo "##################################"
echo "#      FINISHED EXPERIMENTS      #"
echo "##################################"
