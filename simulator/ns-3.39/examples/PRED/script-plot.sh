#!/bin/bash

# --- 硬编码默认参数 ---
DEFAULT_DUMP_DIR=dump/PRED/${evaluation}${specifier:+/$specifier}${specifier2:+/$specifier2}
DEFAULT_POST_FIX="PRED-20260520_121134"
DEFAULT_MASTER_ID=17
DEFAULT_LOW_CUT=0
DEFAULT_HIGH_CUT=3999
DEFAULT_STEP=10

# --- 读取命令行参数，覆盖硬编码 ---
DUMP_DIR=${1:-$DEFAULT_DUMP_DIR}
POST_FIX=${2:-$DEFAULT_POST_FIX}
MASTER_ID=${3:-$DEFAULT_MASTER_ID}
LOW_CUT=${4:-$DEFAULT_LOW_CUT}
HIGH_CUT=${5:-$DEFAULT_HIGH_CUT}
STEP=${6:-$DEFAULT_STEP}

source config.sh
cd $NS3/examples/PRED/

if [ $# -ge 7 ]; then
    Y_LIM=${7}
    echo "第7个参数存在：$Y_LIM"
    echo "正在绘制图表plot-2to1..."
    time python3 plot-2to1.py --low-cut-ms ${LOW_CUT} --high-cut-ms ${HIGH_CUT} --step ${STEP} --master-id ${MASTER_ID} --dump-dir ${DUMP_DIR} --alg ${POST_FIX} --queue-ylim ${Y_LIM}
    echo "绘制完毕"
else
    echo "第7个参数不存在"
    echo "正在绘制图表plot-2to1..."
    time python3 plot-2to1.py --low-cut-ms ${LOW_CUT} --high-cut-ms ${HIGH_CUT} --step ${STEP} --master-id ${MASTER_ID} --dump-dir ${DUMP_DIR} --alg ${POST_FIX}
    echo "绘制完毕"
fi

# echo "正在绘制图表plot-2to1..."
# time python3 plot-2to1.py --low-cut-ms ${LOW_CUT} --high-cut-ms ${HIGH_CUT} --step ${STEP} --master-id ${MASTER_ID} --dump-dir ${DUMP_DIR} --alg ${POST_FIX}
# echo "绘制完毕"

echo "正在绘制图表plot-PRED-statics..."
time python3 plot-PRED-statics.py --low-cut-ms ${LOW_CUT} --high-cut-ms ${HIGH_CUT} --step ${STEP} --master-id ${MASTER_ID} --dump-dir ${DUMP_DIR} --alg ${POST_FIX}
echo "绘制完毕"