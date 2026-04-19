#ifndef SWITCH_MMU_H
#define SWITCH_MMU_H

#include <unordered_map>
#include <ns3/node.h>

/////////////////////////////////////////////////////////////////////
#include <vector>
#include <map>

#include "ns3/nstime.h"

#define INIT_SIZE 10 //bit map初始化尺寸，1<<INIT_SIZE（默认10），即为2^10
#define TFCS_FACTOR 1.25 //论文原文采用TFCS=1.25*RTT
#define TQLA_FACTOR 5 //论文原文采用TQLA=5*RTT
#define LAMBDA_MIN 0.05//λ取值（0~正无穷），设置最小取值，原文采用0.05
/////////////////////////////////////////////////////////////////////

namespace ns3 {

class Packet;

class SwitchMmu: public Object {
private:

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
/////////////////////////////////////////////////PRIVATE添加开始//////////////////////////////////////////////////////////////////
/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


	// FCS 模块的状态
	class FcsState {
	public:
		static const uint32_t INDEX_SIZE = INIT_SIZE;// 位图初始化大小
		uint64_t last_reset_ns;      // 上次窗口重置时间
		uint32_t n_current;          // 当前窗口新流计数
		uint32_t n_last;             // 上一个窗口新流计数
		uint32_t interval_seq;       // 窗口序号
		std::vector<uint64_t> bitmap; // 指纹位图（大小 2^IndexSize）

		FcsState() : last_reset_ns(0), n_current(0), n_last(0), interval_seq(0) {
			initiate();
		}
		FcsState(int length) : last_reset_ns(0), n_current(0), n_last(0), interval_seq(0) {
			initiate(length);
		}

		public:
			void initiate(){
				bitmap.resize(1 << INDEX_SIZE, 0); // 默认 1024 槽位
			}
			void initiate(int length){
				bitmap.resize(1 << length, 0); // 默认 1024 槽位
			}
	};

	// QLA 模块的状态
	class QlaState {
	public:
		static const uint32_t
			SHOULD_ADD_DELTA=1,		 //应该加Δλ
			SHOULD_REDUCE_DELTA=-1,  //应该减Δλ
			SHOULD_MAINTAIN=0;		 //应该保持不变

		double
			beta,					 //β，用于效用函数，论文取0.4
			q_left, 				 //映射函数左值qleft，小于等于qleft取1
			q_right, 				 //映射函数右值qleft，此时phi取0
			q_left_phi;				 //映射函数左值qleft所对应的另一个值，不取，用于计算

		double lambda_base;          // 当前 λ_QLA
		double lambda_current;		 // 每个相位实时使用的λ值
		double lambda_delta;		 // 四个周期中，λ_QLA的变化量Δλ
		uint32_t minK;               // 当前 minK（包数）
		uint32_t mink_delta;		 // ΔminK的值，默认5（论文）
		uint32_t maxK;               // 固定大阈值（如 500 包）

		// A/B 测试相关
		int test_phase;              // 0..3
		uint64_t phase_start_ns;     // 当前测试阶段开始时间
		uint64_t phase_tx_bytes;     // 本阶段发送字节数
		uint32_t phase_qlen_sum;     // 本阶段队列长度采样和
		uint32_t phase_qlen_cnt;     // 本阶段采样次数
		uint64_t last_update_ns;	 // 上次更新时间
		double phase_utils[4];       // 存储四个阶段的效用值

		QlaState() : lambda_base(0.1),lambda_delta(0.025), minK(10),mink_delta(5), maxK(500),
					test_phase(0), phase_start_ns(0),
					phase_tx_bytes(0), phase_qlen_sum(0), phase_qlen_cnt(0),last_update_ns(0) {
			initiate();
			initStatic();
		}

		void initStatic(){
			q_left=15;//原文取15个数据包
			q_right=200;//原文没说。。。。假设为200
			q_left_phi=1;//原文也没说。。。。假设为1
			beta=0.4;//原文取0.4
		}

		public:
			void initiate(){
				for (int i=0; i<4; ++i) phase_utils[i] = 0;
			}
			void IncreasePhase(){
				test_phase++;
				test_phase%=4;
			}

			//我愿称之为UtilityJudgement
			uint32_t UtilityJudgement(){
				if(
					phase_utils[0]>phase_utils[1]&&
					phase_utils[3]>phase_utils[2]
				){
					return SHOULD_ADD_DELTA;//说明应该加delta
				}

				if(
					phase_utils[0]<phase_utils[1]&&
					phase_utils[3]<phase_utils[2]
				){
					return SHOULD_REDUCE_DELTA;//说明应该减delta
				}

				return SHOULD_MAINTAIN;//说明应该保持lambda不变
			}

			//执行决策器
			void DecisionMaker(){
				uint32_t decision = UtilityJudgement();
					switch (decision){
						case SHOULD_ADD_DELTA:
							lambda_base += lambda_delta;
							break;
						case SHOULD_REDUCE_DELTA:
							lambda_base -= lambda_delta;
							break;
						case SHOULD_MAINTAIN:
							/*
							保持不变，不操作
							*/
							break;
						default:
							break;
					}
			}

			//执行相位
			void doPhaseWork(){
				IncreasePhase();//相位自增，从上一个切换到当前

				if(test_phase==0){//如果是0相位，那么要么是第一次开始，要么是上个周期结束
					DecisionMaker();
				}

				if(test_phase==0||test_phase==3){//0,3 +delta
					lambda_current = lambda_base + lambda_delta;
				}else{//1,2 -delta
					lambda_current = lambda_base - lambda_delta;
				}

				LambdaOverflowManager();//包含了MinkAdjuster

				//具体到red参数的调整呢？？
			}

			void LambdaOverflowManager(){
				if(lambda_current<=LAMBDA_MIN){
					lambda_current=LAMBDA_MIN;
					MinkAdjuster();
					// return;
				}
			}

			//MinK调整器
			void MinkAdjuster(){
				minK+=mink_delta;
			}


			//首次启动的初始化
			void InitFirstStart(uint64_t now_ns){
				phase_start_ns=now_ns;
			}

			//φ映射函数
			double Phi(double q_avg){//传入平均队列长度
				if(q_avg<=q_left){
					return 1;
				}

				if(q_avg>=q_right){
					return 0;
				}

				/*
				y=k(x-q_right)
				q_left_phi=k(q_left-q_right)
				k=q_left_phi/(q_left-q_right)
				*/
				double k=q_left_phi/(q_left-q_right);
				double ans=k*(q_avg-q_right);
				return ans;
			}

			//效用函数
			double UtilityFunction(double throughput_avg,double bandwidth,double q_avg){
				/*
				β*(当前TQLA平均吞吐率/链路带宽)-(1-β)*φ(平均队列长度)
				*/
				double ans=
					beta*(throughput_avg/bandwidth)-
					(1-beta)*Phi(q_avg);

				return ans;
			}
	};

	// PRED 算法的状态
	class PredState{
		public:
			FcsState fcsState;
			QlaState qlaState;
	};

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
/////////////////////////////////////////////////PRIVATE添加结束//////////////////////////////////////////////////////////////////
/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

public:
	static const uint32_t pCnt = 257;	// Number of ports used
	static const uint32_t qCnt = 8;	// Number of queues/priorities used

	static TypeId GetTypeId (void);

	SwitchMmu(void);

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
/////////////////////////////////////////////////PUBLIC添加开始///////////////////////////////////////////////////////////////////
/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


	///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
	//RED算法相关函数声明
	double GetAvgQueueLength(uint32_t ifindex, uint32_t qIndex);
	uint32_t GetCurrentQueueLength(uint32_t ifindex, uint32_t qIndex);
	void UpdateAvgQueue(uint32_t ifindex, uint32_t qIndex);
	void InitRed(uint32_t port);

	PredState predStates[pCnt][qCnt];

	//单位是纳秒（ns）
	double portRTTs[pCnt];


	PredState& GetPredState(uint32_t port, uint32_t queue) {
        return predStates[port][queue];
    }

	FcsState& GetFcsState(uint32_t port, uint32_t queue) {
        return GetPredState(port,queue).fcsState;
    }

	QlaState& GetQlaState(uint32_t port, uint32_t queue) {
        return GetPredState(port,queue).qlaState;
    }

	//存储端口（链路）的rtt
	void SetPortRTT(uint32_t port,double rtt){
		portRTTs[port]=rtt;
	}

	//获取端口（链路）的rtt
	double GetPortRTT_ns(uint32_t port){
		return portRTTs[port];
	}

	//用RTT计算TFCS
	double GetTFCS(uint32_t rtt){
		return TFCS_FACTOR*rtt;
	}

	//用RTT和自定义参数计算TFCS
	double GetTFCS(uint32_t rtt,uint32_t customFactor){
		return customFactor*rtt;
	}

	//用RTT计算TQLA
	double GetTQLA(uint32_t rtt){
		return TQLA_FACTOR*rtt;
	}

	//用RTT和自定义参数计算TQLA
	double GetTQLA(uint32_t rtt,uint32_t customFactor){
		return customFactor*rtt;
	}

	//用ns3的time类型转换delay_str为纳秒时间
	double ParseDelayToNanoseconds(const std::string& delay_str) {
		Time t = Time(delay_str);          // 自动解析
		return (double)(t.GetNanoSeconds());
	}

	//传入link_delay字符串，转换为以纳秒为单位的RTT，默认RTT=2*link_delay
	double CalcRTT_ns(std::string link_delay){
		// 例如：std::string link_delay = "10us";
		double delay_ns = ParseDelayToNanoseconds(link_delay);
		double RTT=2*delay_ns;
		return RTT;
	}

	//获取端口-队列的IntervalSeq
	uint32_t GetIntervalSeq(uint32_t port, uint32_t queue) const {
        return predStates[port][queue].fcsState.interval_seq;
    }

	//更新端口-队列的IntervalSeq，增加increment，默认为1
	void IncreaseIntervalSeq(uint32_t port, uint32_t queue, uint32_t increment=1) {
        predStates[port][queue].fcsState.interval_seq+=increment;
    }

	//更新端口-队列的FCS状态
	void UpdateFcsStats(uint32_t port, uint32_t queue, uint32_t fingerprint,uint64_t now_ns);

	//更新端口-队列的QLA状态
	void UpdateQlaStats(uint32_t port, uint32_t queue, uint32_t pktSize, uint32_t curQlenPkts, uint64_t now_ns, uint64_t rtt_ns);

/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
/////////////////////////////////////////////////PUBLIC添加结束//////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


	bool CheckIngressAdmission(uint32_t port, uint32_t qIndex, uint32_t psize, uint32_t type, uint32_t unsched);
	bool CheckEgressAdmission(uint32_t port, uint32_t qIndex, uint32_t psize, uint32_t type, uint32_t unsched);
	void UpdateIngressAdmission(uint32_t port, uint32_t qIndex, uint32_t psize, uint32_t type, uint32_t unsched);
	void UpdateEgressAdmission(uint32_t port, uint32_t qIndex, uint32_t psize, uint32_t type);
	void RemoveFromIngressAdmission(uint32_t port, uint32_t qIndex, uint32_t psize, uint32_t type);
	void RemoveFromEgressAdmission(uint32_t port, uint32_t qIndex, uint32_t psize, uint32_t type);

	bool CheckShouldPause(uint32_t port, uint32_t qIndex);
	bool CheckShouldResume(uint32_t port, uint32_t qIndex);
	void SetPause(uint32_t port, uint32_t qIndex);
	void SetResume(uint32_t port, uint32_t qIndex);

	void SetBufferModel(std::string model){bufferModel = model;}

	void SetBufferPool(uint64_t b);

	void SetIngressPool(uint64_t b);

	void SetSharedPool(uint64_t b);

	void SetEgressPoolAll(uint64_t b);

	void SetEgressLossyPool(uint64_t b);

	void SetEgressLosslessPool(uint64_t b);

	void SetReserved(uint64_t b, uint32_t port, uint32_t q, std::string inout);
	void SetReserved(uint64_t b, std::string inout);

	void SetAlphaIngress(double value, uint32_t port, uint32_t q);
	void SetAlphaIngress(double value);

	void SetAlphaEgress(double value, uint32_t port, uint32_t q);
	void SetAlphaEgress(double value);

	void SetHeadroom(uint64_t b, uint32_t port, uint32_t q);
	void SetHeadroom(uint64_t b);

	void SetXon(uint64_t b, uint32_t port, uint32_t q);
	void SetXon(uint64_t b);

	void SetXonOffset(uint64_t b, uint32_t port, uint32_t q);
	void SetXonOffset(uint64_t b);

	void SetIngressLossyAlg(uint32_t alg);

	void SetIngressLosslessAlg(uint32_t alg);

	void SetEgressLossyAlg(uint32_t alg);

	void SetEgressLosslessAlg(uint32_t alg);

	void SetGamma(double value);

	uint64_t Threshold(uint32_t port, uint32_t qIndex, std::string inout, uint32_t type, uint32_t alphaPrio);

	uint64_t DynamicThreshold(uint32_t port, uint32_t qIndex, std::string inout, uint32_t type);

	uint64_t GetHdrmBytes(uint32_t port, uint32_t qIndex);

	uint64_t GetIngressReservedUsed();

	uint64_t GetIngressReservedUsed(uint32_t port, uint32_t qIndex);

	uint64_t GetIngressSharedUsed();

	void setCongested(uint32_t portId, uint32_t qIndex, std::string inout, double satLevel);

	double GetNofP(std::string inout, uint32_t qIndex);

	double getDequeueRate(uint32_t port, uint32_t qIndex, std::string inout);

	void updateDequeueRates();

	uint64_t ActiveBufferManagement(uint32_t port, uint32_t qIndex, std::string inout, uint32_t type, uint32_t unsched);

	uint64_t FlowAwareBuffer(uint32_t port, uint32_t qIndex, std::string inout, uint32_t type, uint32_t unsched);

	void SetABMalphaHigh(double alpha){alphaHigh = alpha;};

	void SetABMdequeueUpdateNS(double time){updateIntervalNS = time;}

	void SetPortCount(uint32_t pc){portCount = pc;}

	uint64_t ReverieThreshold(uint32_t port, uint32_t qIndex, uint32_t type, uint32_t unsched);

	void UpdateLpfCounters();


	// config
	uint32_t node_id;
	uint32_t kmin[pCnt], kmax[pCnt];
	double pmax[pCnt];

	// Buffer model
	std::string bufferModel;

	// Buffer pools
	uint64_t bufferPool;
	uint64_t ingressPool ;
	uint64_t egressPool[2];
	uint64_t egressPoolAll;
	uint64_t sharedPool;
	uint64_t xoffTotal;
	uint64_t totalIngressReserved;

	// aggregate run time
	uint64_t totalUsed;
	uint64_t egressPoolUsed[2];
	uint64_t xoffTotalUsed;
	uint64_t totalIngressReservedUsed;
	uint64_t sharedPoolUsed;


	// buffer configuration.
	uint64_t reserveIngress[pCnt][qCnt];
	uint64_t reserveEgress[pCnt][qCnt];
	double 	 alphaEgress[pCnt][qCnt];
	double 	 alphaIngress[pCnt][qCnt];
	uint64_t xoff[pCnt][qCnt];
	uint64_t xon[pCnt][qCnt];
	uint64_t xon_offset[pCnt][qCnt];

	// per queue run time
	uint64_t ingress_bytes[pCnt][qCnt];
	uint64_t hdrm_bytes[pCnt][qCnt];
	uint32_t paused[pCnt][qCnt];
	uint64_t egress_bytes[pCnt][qCnt];
	uint64_t xoffUsed[pCnt][qCnt];
	uint64_t ingressLpf_bytes[pCnt][qCnt];
	uint64_t egressLpf_bytes[pCnt][qCnt];

	// used for calculating ingress rates and egress rates 
	uint64_t cumulatedIngresssBytes[pCnt][qCnt]; // Track bytes transmitted per port
	uint64_t lastIngresssTime[pCnt][qCnt]; // Track last update time per port
	uint64_t cumulatedEgresssBytes[pCnt][qCnt]; // Track bytes transmitted per port
	uint64_t lastEgresssTime[pCnt][qCnt]; // Track last update time per port
    uint64_t RatePrintInterval = 20000; // Print rate at the interval of 20us

    ///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
	// 用于RED算法的平均队列长度
	uint64_t avg_egress_bytes[pCnt][qCnt];// 平均队列长度数组（每个端口，每个队列）

    // RED权重参数（通常设为0.002）
    double wq[pCnt];

    // // 计数用于避免连续丢包
    uint32_t count[pCnt][qCnt]; // 启用
	
	/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
	// 此处新增double _wq = 0.002，原函数：void ConfigEcn(uint32_t port, uint32_t _kmin, uint32_t _kmax, double _pmax);
	/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
	void ConfigEcnNew(uint32_t port, uint32_t _kmin, uint32_t _kmax, double _pmax, double _wq /*= 0.002*/);

	///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

	/*********************************************************************************************************************/
	uint32_t aqmMode; 
	void SetAqmMode(uint32_t mode) { aqmMode = mode; }
	bool ShouldSendCN(uint32_t ifindex, uint32_t qIndex);
    bool AQM_RED(uint32_t ifindex, uint32_t qIndex);
    bool AQM_CoDel(uint32_t ifindex, uint32_t qIndex);
    bool AQM_MATCP(uint32_t ifindex, uint32_t qIndex);
    bool AQM_CEDM(uint32_t ifindex, uint32_t qIndex);
    bool AQM_MBECN(uint32_t ifindex, uint32_t qIndex);
    bool AQM_PRED(uint32_t ifindex, uint32_t qIndex);
	bool AQM_IMCAQM(uint32_t ifindex, uint32_t qIndex);


	void ConfigEcn(uint32_t port, uint32_t _kmin, uint32_t _kmax, double _pmax);

    /*********************************************************************************************************************/

	// Buffer Sharing algorithm
	uint32_t ingressAlg[2];
	uint32_t egressAlg[2];

	// ABM realted variables
	double NofPIngress[qCnt];
	double NofPEgress[qCnt];
	double congestedIngress[pCnt][qCnt];
	double congestedEgress[pCnt][qCnt];
	double dequeueRateIngress[pCnt][qCnt];
	double dequeueRateEgress[pCnt][qCnt];
	uint64_t txBytesIngress[pCnt][qCnt];
	uint64_t txBytesEgress[pCnt][qCnt];
	uint64_t bandwidth[pCnt];
	uint32_t congestionIndicator;
	double alphaHigh;
	double updateIntervalNS;
	uint32_t dequeueUpdatedOnce;
	uint32_t portCount;

	double Reveriegamma;
	uint32_t lpfUpdatedOnce;

};

} /* namespace ns3 */

#endif /* SWITCH_MMU_H */

