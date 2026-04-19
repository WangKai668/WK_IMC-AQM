ENABLE_QCN 1
USE_DYNAMIC_PFC_THRESHOLD 1

PACKET_PAYLOAD_SIZE 1000

TOPOLOGY_FILE examples/PRED/topology-PRED.txt
FLOW_FILE examples/PRED/websearch.txt
TRACE_FILE mix/trace.txt
TRACE_OUTPUT_FILE mix/mix.tr
FCT_OUTPUT_FILE mix/fct.txt
PFC_OUTPUT_FILE mix/pfc.txt

SIMULATOR_STOP_TIME 0.4

CC_MODE 1                       # DCQCN:1   DCTCP:8
ALPHA_RESUME_INTERVAL 1         # DCQCN：减速因子α每隔1us更新： 如果收到过cnp，升高α=(1-g)*α+g*1； 否则， 降低α=(1-g)*α；  ps：越高减速越狠，初始值q->mlx.m_alpha = 1;
                                # DCTCP：每RTT更新，α = (1-g)*α + g*frac;                                               ECN比例越高，减速越狠，初始值dctcp.m_alpha = 1;

RATE_DECREASE_INTERVAL 4        # DCQCN减速：每隔4us检查是否要降速： 如果收到过cnp，R=R*(1-α/2), 并重启加速计时器; 
CLAMP_TARGET_RATE 0
RP_TIMER 900                    # DCQCN加速：加速计时器，如果900us没收到cnp，就加速（先折半，再ai+折半， 再hai+折半）

EWMA_GAIN 0.00390625            # DCQCN/DCTCP：减速因子的加权参数，1/256 （更新极慢）

                                # DCTCP减速/加速：每RTT调速，如果CNP，乘性减速 R=R*(1-α/2)； 否则，线性加速 +1Gbps； 
FAST_RECOVERY_TIMES 1
RATE_AI 50Mb/s
RATE_HAI 100Mb/s
MIN_RATE 100Mb/s
DCTCP_RATE_AI 1000Mb/s

ERROR_RATE_PER_LINK 0.0000
L2_CHUNK_SIZE 4000
L2_ACK_INTERVAL 1
L2_BACK_TO_ZERO 0

HAS_WIN 1           # 开启窗口 
GLOBAL_T 1          # QP采用全局最大BDP
VAR_WIN 1           # 动态窗口
FAST_REACT 1
U_TARGET 0.95
MI_THRESH 5
INT_MULTI 1
MULTI_RATE 0
SAMPLE_FEEDBACK 0
PINT_LOG_BASE 1.05
PINT_PROB 1.0

RATE_BOUND 1

ACK_HIGH_PRIO 0

LINK_DOWN 0 0 0

ENABLE_TRACE 1

KMAX_MAP 3 25000000000 400 50000000000 800 100000000000 1600
KMIN_MAP 3 25000000000 100 50000000000 200 100000000000 400
PMAX_MAP 3 25000000000 0.2 50000000000 0.2 100000000000 0.2
BUFFER_SIZE 50
QLEN_MON_FILE mix/qlen.txt
QLEN_MON_START 2000000000
QLEN_MON_END 2010000000
