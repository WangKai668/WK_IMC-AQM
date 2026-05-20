#include <iostream>
#include <fstream>
#include <cstring>
#include "ns3/packet.h"
#include "ns3/simulator.h"
#include "ns3/object-vector.h"
#include "ns3/uinteger.h"
#include "ns3/log.h"
#include "ns3/assert.h"
#include "ns3/global-value.h"
#include "ns3/boolean.h"
#include "ns3/simulator.h"
#include "ns3/random-variable.h"
#include "switch-mmu.h"

#include <ns3/seq-ts-header.h>
#include <ns3/udp-header.h>
#include <ns3/ipv4-header.h>
#include "ns3/ppp-header.h"
#include "ppp-header.h"
#include "qbb-header.h"
#include "cn-header.h"


#define LOSSLESS 0
#define LOSSY 1
#define DUMMY 2

# define DT 101
# define FAB 102
# define CS 103
# define IB 104
# define ABM 110
# define REVERIE 111

/*Active Queue Management Algorithms*/
#define RED 1
#define CoDel 2
#define MATCP 3
#define CEDM 4
#define MBECN 5
#define PRED 6
#define IMCAQM 7

#define E1e9 1000000000


NS_LOG_COMPONENT_DEFINE("SwitchMmu");
namespace ns3 {
TypeId SwitchMmu::GetTypeId(void) {
	static TypeId tid = TypeId("ns3::SwitchMmu")
	                    .SetParent<Object>()
	                    .AddConstructor<SwitchMmu>();
	return tid;
}

/*
We model the switch shared memory (purely based on our understanding and experience).
The switch has an on-chip buffer which has `bufferPool` size.
This buffer is shared across all port and queues in the switch.

`bufferPool` is further split into multiple pools at the ingress and egress.

It would be easier to understand from here on if you consider Ingress/Egress are merely just counters.
These are not separate buffer locations or chips...!

First, `ingressPool` (size) accounts for ingress buffering shared by both lossy and lossless traffic.
Additionally, there exists a headroom pool of size xoffTotal,
and each queue may use xoff[port][q] configurable amount at each port p and queue q.
When a queue at the ingress exceeds its ingress threshold, a PFC pause message is sent and
any incoming packets can use upto a maximum of xoff[port][q] headroom.

Second, at the egress, `egressPool[LOSSY]` (size) accounts for buffering lossy traffic at the egress and
similarly `egressPool[LOSSLESS]` for lossless traffic.
*/

//YRNK_ADD
//初始化static
double SwitchMmu::TFCS_FACTOR = 1.25;
double SwitchMmu::TQLA_FACTOR = 5.0;
double SwitchMmu::LAMBDA_MIN = 0.05;
// YRNK_ADD 默认启用PRED的QLA和FCS组件
bool SwitchMmu::EnableQLA = true;
bool SwitchMmu::EnableFCS = true;

SwitchMmu::SwitchMmu(void) {



	// SwitchMmu::initPredStatics();
	// 用于初始化！！！
	// Here we just initialize some default values.
	// The buffer can be configured using Set functions through the simulation file later.

	// Buffer model
	bufferModel = "sonic"; // currently SONiC buffer (based on our understanding) and "reverie" buffer model are supported. The bufferModel can be set using SetBufferModel function externally.

	// Buffer pools
	bufferPool = 24 * 1024 * 1024; // ASIC buffer size i.e, total shared buffer
	ingressPool = 18 * 1024 * 1024; // Size of ingress pool. Note: This is shared by both lossless and lossy traffic.
	egressPool[LOSSLESS] = 24 * 1024 * 1024; // Size of egress lossless pool. Lossless bypasses egress admission
	egressPool[LOSSY] = 14 * 1024 * 1024; // Size of egress lossy pool.
	sharedPool = 18 * 1024 * 1024; // For Reverie which maintains a single shared buffer pool, all lossless and lossy share this pool
	egressPoolAll = 24 * 1024 * 1024; // Not for now. For later use.
	xoffTotal = 0; //6 * 1024 * 1024; // Total headroom space in the shared buffer pool.
	// xoffTotal value is incremented when SetHeadroom function is used. So setting it to zero initially.
	// Note: This would mean that headroom must be set explicitly.
	totalIngressReserved = 0;
	totalIngressReservedUsed = 0;


	// aggregate run time
	// `totalUsed` IMPORTANT TO NOTE: THIS IS NOT bytes in the "ingress pool".
	// This is the total bytes USED in the switch buffer, which includes occupied buffer in reserved + headroom + ingresspool.
	totalUsed = 0;
	egressPoolUsed[LOSSLESS] = 0; // Total bytes USED in the egress lossless pool
	egressPoolUsed[LOSSY] = 0; // Total bytes USED in the egress lossy pool
	xoffTotalUsed = 0; // Total headroom bytes USED so far. Updated at runtime.
	sharedPoolUsed = 0; // For Reverie: total shared pool used buffer.
	// It is sometimes useful to keep track of total bytes used specifically from ingressPool. We don't need an additional variable.
	// This is equal to (totalUsed - xoffTotalUsed).

	Reveriegamma = 0.99;

	for (uint32_t port = 0; port < pCnt; port++) {
		for (uint32_t q = 0; q < qCnt; q++) {
			// buffer configuration.
			reserveIngress[port][q] = 0; // Per queue reserved buffer at ingress. IMPORTANT: reserve SHOULD BE SET EXPLICITLY in a simulation.
			reserveEgress[port][q] = 0; // per queue reserved buffer at egress. Not used at the moment. TODO.
			alphaEgress[port][q] = 1; // per queue alpha value used by Buffer Management/PFC Threshold at egress
			alphaIngress[port][q] = 1; // per queue alpha value used by Buffer Management/PFC Threshold at ingress
			xoff[port][q] = 0; // per queue headroom LIMIT at ingress. This can be changed using SetHeadroom. IMPORTANT: xoff SHOULD BE SET EXPLICITLY in a simulation.
			xon[port][q] = 1248; // For pfc resume. Can be changed using SetXon
			xon_offset[port][q] = 2496; // For pfc resume. Can be changed using SetXonOffset


			// per queue run time
			ingress_bytes[port][q] = 0; // total ingress bytes USED at each queue. This includes, bytes from reserved, ingress pool as well as any headroom.
			// MMU maintains paused state for all Ingress queues to keep track if a queue is currently pausing the peer (an egress queue on the other end of the link)
			// NOTE: QbbNetDevices (ports) maintain a separate paused state to keep track if an egress queue is paused or not. This can be found in qbb-net-device.cc
			paused[port][q] = 0; // a state (see above).
			egress_bytes[port][q] = 0; // Per queue egress bytes USED at each queue
			xoffUsed[port][q] = 0; // The headroom buffer USED by each queue.
			ingressLpf_bytes[port][q] = 0;
			egressLpf_bytes[port][q] = 0;

			////////////////////////////////////////////////////////////////////////////////////////////////////////
			//YRNK
			//////////初始化平均队列长度avgq
			////////////////////////////////////////////////////////////////////////////////////////////////////////
			avg_egress_bytes[port][q] = 0;
			//YRNK
			//初始化包数量数组
			egress_pkts[port][q] = 0;

			// ABM related variables
			congestedIngress[port][q] = 0; // This keeps track of the number of congested queues at the ingress
			congestedEgress[port][q] = 0; // This keeps track of the number of congested queues at the egress
			txBytesIngress[port][q] = 0; // used for calculating dequeue rates. counter for tx bytes of ingress queues
			txBytesEgress[port][q] = 0; // used for calculating dequeue rates. counter for tx bytes of egress queues
			dequeueRateIngress[port][q] = 1; // normalized dequeue rate of an ingress queue
			dequeueRateEgress[port][q]  = 1; // normalized dequeue rate of an egress queue
		}
	}

	for (uint32_t qIndex = 0; qIndex < qCnt; qIndex++) {
		NofPIngress[qIndex] = 0;
		NofPEgress[qIndex] = 0;
	}
	for (uint32_t portId = 0; portId < pCnt; portId++) {
		bandwidth[portId] = MyBandWidth_GBPS * 1e9;//25 * 1e9;
	}
	congestionIndicator = 20 * 1024;

	ingressAlg[LOSSLESS] = DT;
	ingressAlg[LOSSY] = DT;
	egressAlg[LOSSLESS] = DT;
	egressAlg[LOSSY] = DT;


	memset(ingress_bytes, 0, sizeof(ingress_bytes));
	memset(paused, 0, sizeof(paused));
	memset(egress_bytes, 0, sizeof(egress_bytes));
	//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
	/////////虽然不明白，但是我觉得这里也要对平均队长avgq进行一个memset
	//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
	memset(avg_egress_bytes, 0, sizeof(avg_egress_bytes));

	dequeueUpdatedOnce = 0; // For ABM, to trigger dequeue rate updates
	lpfUpdatedOnce = 0; // For Reverie, LPF updates
	updateIntervalNS = 25 * 1000; // default 25us update interval for dequeue rates
	alphaHigh = 1024; // default value to imitate a sky high threshold for all unscheduled packets
	portCount = pCnt; // default value is 257. This should be set to the real port count using SetPortCount function externally based on the simulation setup

	//Init AQM Parameters
	memset(codel_first_above_time, 0, sizeof(codel_first_above_time));
	memset(codel_drop_next, 0, sizeof(codel_drop_next));
	memset(codel_count, 0, sizeof(codel_count));
	memset(codel_lastcount, 0, sizeof(codel_lastcount));
	memset(codel_dropping, 0, sizeof(codel_dropping));

	memset(cedm_avg_s, 0, sizeof(cedm_avg_s));
	memset(cedm_qlast, 0, sizeof(cedm_qlast));
	memset(cedm_tlast, 0, sizeof(cedm_tlast));

	memset(matcp_avg_q, 0, sizeof(matcp_avg_q));
	memset(matcp_q_gradient, 0, sizeof(matcp_q_gradient));
	memset(matcp_qlast, 0, sizeof(matcp_qlast));

	memset(imc_period_cnt, 0, sizeof(imc_period_cnt));
}

void
SwitchMmu::SetBufferPool(uint64_t b) {
	bufferPool = b;
}

void
SwitchMmu::SetIngressPool(uint64_t b) {
	ingressPool = b;
}

void
SwitchMmu::SetSharedPool(uint64_t b) {
	sharedPool = b;
}

void
SwitchMmu::SetEgressPoolAll(uint64_t b) {
	egressPoolAll = b;
}

void
SwitchMmu::SetEgressLossyPool(uint64_t b) {
	egressPool[LOSSY] = b;
}

void
SwitchMmu::SetEgressLosslessPool(uint64_t b) {
	egressPool[LOSSLESS] = b;
}

void
SwitchMmu::SetReserved(uint64_t b, uint32_t port, uint32_t q, std::string inout) {
	if (inout == "ingress") {
		if (totalIngressReserved >= reserveIngress[port][q])
			totalIngressReserved -= reserveIngress[port][q];
		else
			totalIngressReserved = 0;
		reserveIngress[port][q] = b;
		totalIngressReserved += reserveIngress[port][q];
	}
	else if (inout == "egress") {
		std::cout << "setting reserved for egress is not supported. Exiting..!" << std::endl;
		exit(1);
		// reserveEgress[port][q] = b;
	}
}

void
SwitchMmu::SetReserved(uint64_t b, std::string inout) {
	if (inout == "ingress") {
		for (uint32_t port = 0; port < pCnt; port++) {
			for (uint32_t q = 0; q < qCnt ; q++) {
				if (totalIngressReserved >= reserveIngress[port][q])
					totalIngressReserved -= reserveIngress[port][q];
				else
					totalIngressReserved = 0;
				reserveIngress[port][q] = b;
				totalIngressReserved += reserveIngress[port][q];
			}
		}
	}
	else if (inout == "egress") {
		std::cout << "setting reserved for egress is not supported. Exiting..!" << std::endl;
		exit(1);
		// for (uint32_t port = 0; port < pCnt; port++) {
		// 	for (uint32_t q = 0; q < qCnt; q++) {
		// 		reserveEgress[port][q] = b;
		// 	}
		// }
	}
}

void
SwitchMmu::SetAlphaIngress(double value, uint32_t port, uint32_t q) {
	alphaIngress[port][q] = value;
}

void
SwitchMmu::SetAlphaIngress(double value) {
	for (uint32_t port = 0; port < pCnt; port++) {
		for (uint32_t q = 0; q < qCnt; q++) {
			alphaIngress[port][q] = value;
		}
	}
}

void
SwitchMmu::SetAlphaEgress(double value, uint32_t port, uint32_t q) {
	alphaEgress[port][q] = value;
}

void
SwitchMmu::SetAlphaEgress(double value) {
	for (uint32_t port = 0; port < pCnt; port++) {
		for (uint32_t q = 0; q < qCnt; q++) {
			alphaEgress[port][q] = value;
		}
	}
}


// This function allows for setting headroom per queue. When ever this is set, the xoffTotal (total headroom) is updated.
void
SwitchMmu::SetHeadroom(uint64_t b, uint32_t port, uint32_t q) {
	xoffTotal -= xoff[port][q];
	xoff[port][q] = b;
	xoffTotal += xoff[port][q];
}

// This function allows for setting headroom for all queues in oneshot. When ever this is set, the xoffTotal (total headroom) is updated.
void
SwitchMmu::SetHeadroom(uint64_t b) {
	for (uint32_t port = 0; port < pCnt; port++) {
		for (uint32_t q = 0; q < qCnt; q++) {
			xoffTotal -= xoff[port][q];
			xoff[port][q] = b;
			xoffTotal += xoff[port][q];
		}
	}
}

void
SwitchMmu::SetXon(uint64_t b, uint32_t port, uint32_t q) {
	xon[port][q] = b;
}
void
SwitchMmu::SetXon(uint64_t b) {
	for (uint32_t port = 0; port < pCnt; port++) {
		for (uint32_t q = 0; q < qCnt; q++) {
			xon[port][q] = b;
		}
	}
}

void
SwitchMmu::SetXonOffset(uint64_t b, uint32_t port, uint32_t q) {
	xon_offset[port][q] = b;
}
void
SwitchMmu::SetXonOffset(uint64_t b) {
	for (uint32_t port = 0; port < pCnt; port++) {
		for (uint32_t q = 0; q < qCnt; q++) {
			xon_offset[port][q] = b;
		}
	}
}

void
SwitchMmu::SetGamma(double value) {
	Reveriegamma = value;
}

void
SwitchMmu::SetIngressLossyAlg(uint32_t alg) {
	ingressAlg[LOSSY] = alg;
}

void
SwitchMmu::SetIngressLosslessAlg(uint32_t alg) {
	ingressAlg[LOSSLESS] = alg;
}

void
SwitchMmu::SetEgressLossyAlg(uint32_t alg) {
	egressAlg[LOSSY] = alg;
}

void
SwitchMmu::SetEgressLosslessAlg(uint32_t alg) {
	egressAlg[LOSSLESS] = alg;
}

uint64_t SwitchMmu::GetIngressReservedUsed() {
	return totalIngressReservedUsed;
}

uint64_t SwitchMmu::GetIngressReservedUsed(uint32_t port, uint32_t qIndex) {
	if (ingress_bytes[port][qIndex] > reserveIngress[port][qIndex]) {
		return reserveIngress[port][qIndex];
	}
	else {
		return ingress_bytes[port][qIndex];
	}
}

uint64_t SwitchMmu::GetIngressSharedUsed() {
	return (totalUsed - xoffTotalUsed - totalIngressReservedUsed);
}

// DT's threshold = Alpha x remaining.
// A sky high threshold for a queue can be emulated by setting the corresponding alpha to a large value. eg., UINT32_MAX
uint64_t SwitchMmu::DynamicThreshold(uint32_t port, uint32_t qIndex, std::string inout, uint32_t type) {
	if (inout == "ingress") {
		double remaining = 0;
		uint64_t ingressPoolSharedUsed = GetIngressSharedUsed(); // Total bytes used from the ingress "shared" pool specifically.
		uint64_t ingressSharedPool = ingressPool - totalIngressReserved;
		if (ingressSharedPool > ingressPoolSharedUsed) {
			uint64_t remaining = ingressSharedPool - ingressPoolSharedUsed;
			return std::min(uint64_t(alphaIngress[port][qIndex] * (remaining)), UINT64_MAX - 1024 * 1024);
		}
		else {
			// ingressPoolShared is full. There is no `remaining` buffer in ingressPoolShared.
			// DT's threshold returns zero in this case, but using if else just to avoid threshold computations even in the simple case.
			return 0;
		}
	}
	else if (inout == "egress") {
		// std::cout<<"DynamicThreshold--> "<<"egressPool[type]: "<<egressPool[type]<<" egressPoolUsed[type]: "<<egressPoolUsed[type]<<std::endl;
		double remaining = 0;
		if (egressPool[type] > egressPoolUsed[type]) {
			uint64_t remaining = egressPool[type] - egressPoolUsed[type];
			// UINT64_MAX - 1024*1024 is just a randomly chosen big value.
			// Just don't want to return UINT64_MAX value, sometimes causes overflow issues later.
			uint64_t threshold = std::min(uint64_t(alphaEgress[port][qIndex] * (remaining)), UINT64_MAX - 1024 * 1024);
			return threshold;
		}
		else {
			return 0;
		}
	}
}
void SwitchMmu::setCongested(uint32_t portId, uint32_t qIndex, std::string inout, double satLevel) {
	if (inout == "ingress") {
		// NofPIngress[qIndex] -= congestedIngress[portId][qIndex];
		// if (ingressLpf_bytes[portId][qIndex] > congestionIndicator){
		// 	NofPIngress[qIndex] += 1;
		// 	congestedIngress[portId][qIndex] = 1;
		// }
		// else{
		// 	congestedIngress[portId][qIndex] = 0;
		// }
		NofPIngress[qIndex] +=  satLevel - congestedIngress[portId][qIndex];
		congestedIngress[portId][qIndex] = satLevel;
	}
	else if (inout == "egress") {
		// NofPEgress[qIndex] -= congestedEgress[portId][qIndex];
		// if (egressLpf_bytes[portId][qIndex] > congestionIndicator){
		// 	NofPEgress[qIndex] += 1;
		// 	congestedEgress[portId][qIndex] = 1;
		// }
		// else{
		// 	congestedEgress[portId][qIndex] = 0;
		// }
		NofPEgress[qIndex] += satLevel - congestedEgress[portId][qIndex];
		congestedEgress[portId][qIndex] = satLevel;
	}
}
double SwitchMmu::GetNofP(std::string inout, uint32_t qIndex) {
	if (inout == "ingress") {
		if (NofPIngress[qIndex] < 1)
			return 1;
		else
			return NofPIngress[qIndex];
	}
	else if (inout == "egress") {
		if (NofPEgress[qIndex] < 1)
			return 1;
		else
			return NofPEgress[qIndex];
	}
	return 0;
}
double SwitchMmu::getDequeueRate(uint32_t port, uint32_t qIndex, std::string inout) {
	if (inout == "ingress") {
		return dequeueRateIngress[port][qIndex];
	}
	else if (inout == "egress") {
		return dequeueRateEgress[port][qIndex];
	}
	return 0;
}
void SwitchMmu::updateDequeueRates() {
	for (uint32_t i = 0; i < portCount; i++) {
		for (uint32_t j = 0; j < qCnt; j++) {
			// update ingress queues dequeue rates
			uint64_t temp = txBytesIngress[i][j];
			txBytesIngress[i][j] = 0;
			double temp1 = (1e9 * temp * 8.0 / updateIntervalNS) / (bandwidth[i]);
			if (ingress_bytes[i][j] > congestionIndicator && temp > 2 * 1024)
				dequeueRateIngress[i][j] = temp1;
			else
				dequeueRateIngress[i][j] = 1;
			// if (dequeueRateIngress[i][j] < 0.125) // min 1/8 considering 8 queues, with round-robin
			// 	dequeueRateIngress[i][j] = 0.125;

			//update egress queues dequeue rates
			temp = txBytesEgress[i][j];
			txBytesEgress[i][j] = 0;
			temp1 = (1e9 * temp * 8.0 / updateIntervalNS) / (bandwidth[i]);
			if (egress_bytes[i][j] > congestionIndicator && temp > 2 * 1024)
				dequeueRateEgress[i][j] = temp1;
			else
				dequeueRateEgress[i][j] = 1;
			// dequeueRateEgress[i][j] = 0.125 + (0.875)*(temp1*0.8 + dequeueRateEgress[i][j]*0.2);
			// dequeueRateEgress[i][j] = (1e9 * temp * 8.0 / updateIntervalNS) / (bandwidth[i]);
			// if (dequeueRateEgress[i][j] < 0.125) // min 1/8 considering 8 queues, with round-robin
			// 	dequeueRateEgress[i][j] = 0.125;
		}
	}
	dequeueUpdatedOnce = 1;
	Simulator::Schedule(NanoSeconds(updateIntervalNS), &SwitchMmu::updateDequeueRates, this);
}

uint64_t SwitchMmu::ActiveBufferManagement(uint32_t port, uint32_t qIndex, std::string inout, uint32_t type, uint32_t unsched) {
	if (!dequeueUpdatedOnce) {
		updateDequeueRates();
	}
	if (inout == "ingress") {
		double remaining = 0;
		uint64_t ingressPoolSharedUsed = GetIngressSharedUsed(); // Total bytes used from the ingress "shared" pool specifically.
		uint64_t ingressSharedPool = ingressPool - totalIngressReserved;
		double satLevel = double(ingress_bytes[port][qIndex]) / congestionIndicator;
		if (satLevel > 1) {
			satLevel = 1;
		}
		setCongested(port, qIndex, inout, satLevel);
		if (ingressSharedPool > ingressPoolSharedUsed) {
			uint64_t remaining = ingressSharedPool - ingressPoolSharedUsed;
			double alphaP = 1;
			if (unsched) {
				alphaP = alphaHigh;
			}
			else {
				alphaP = alphaIngress[port][qIndex];
			}
			uint64_t ABM_Threshold = alphaP * (remaining) * (1.0 / GetNofP(inout, qIndex)) * (getDequeueRate(port, qIndex, inout));
			// if (type == LOSSLESS)
			// 	std::cout << getDequeueRate(port, qIndex, inout) << " port " << port  << " qIndex " << qIndex << std::endl;
			return std::min(uint64_t(ABM_Threshold), UINT64_MAX - 1024 * 1024);
		}
		else {
			// ingressPoolShared is full. There is no `remaining` buffer in ingressPoolShared.
			// DT's threshold returns zero in this case, but using if else just to avoid threshold computations even in the simple case.
			return 0;
		}
	}
	else if (inout == "egress") {
		double remaining = 0;
		double satLevel = double(egress_bytes[port][qIndex]) / congestionIndicator;
		if (satLevel > 1) {
			satLevel = 1;
		}
		setCongested(port, qIndex, inout, satLevel);
		if (egressPool[type] > egressPoolUsed[type]) {
			uint64_t remaining = egressPool[type] - egressPoolUsed[type];
			// UINT64_MAX - 1024*1024 is just a randomly chosen big value.
			// Just don't want to return UINT64_MAX value, sometimes causes overflow issues later.
			double alphaP = 1;
			if (unsched) {
				alphaP = alphaHigh;
			}
			else {
				alphaP = alphaEgress[port][qIndex];
			}
			uint64_t ABM_Threshold = alphaP * (remaining) * (1.0 / GetNofP(inout, qIndex)) * (getDequeueRate(port, qIndex, inout));
			return std::min(ABM_Threshold, UINT64_MAX - 1024 * 1024);
		}
		else {
			return 0;
		}
	}
}

uint64_t SwitchMmu::FlowAwareBuffer(uint32_t port, uint32_t qIndex, std::string inout, uint32_t type, uint32_t unsched) {
	if (inout == "ingress") {
		double remaining = 0;
		uint64_t ingressPoolSharedUsed = GetIngressSharedUsed(); // Total bytes used from the ingress "shared" pool specifically.
		uint64_t ingressSharedPool = ingressPool - totalIngressReserved;
		if (ingressSharedPool > ingressPoolSharedUsed) {
			uint64_t remaining = ingressSharedPool - ingressPoolSharedUsed;
			double alphaP = 1;
			if (unsched) {
				alphaP = alphaHigh;
			}
			else {
				alphaP = alphaIngress[port][qIndex];
			}
			uint64_t FAB_Threshold = alphaP * (remaining);
			return std::min(uint64_t(FAB_Threshold), UINT64_MAX - 1024 * 1024);
		}
		else {
			// ingressPoolShared is full. There is no `remaining` buffer in ingressPoolShared.
			// DT's threshold returns zero in this case, but using if else just to avoid threshold computations even in the simple case.
			return 0;
		}
	}
	else if (inout == "egress") {
		double remaining = 0;
		if (egressPool[type] > egressPoolUsed[type]) {
			uint64_t remaining = egressPool[type] - egressPoolUsed[type];
			// UINT64_MAX - 1024*1024 is just a randomly chosen big value.
			// Just don't want to return UINT64_MAX value, sometimes causes overflow issues later.
			double alphaP = 1;
			if (unsched) {
				alphaP = alphaHigh;
			}
			else {
				alphaP = alphaEgress[port][qIndex];
			}
			uint64_t FAB_Threshold = alphaP * (remaining);
			return std::min(FAB_Threshold, UINT64_MAX - 1024 * 1024);
		}
		else {
			return 0;
		}
	}
}



uint64_t SwitchMmu::ReverieThreshold(uint32_t port, uint32_t qIndex, uint32_t type, uint32_t unsched) {
	if (type == LOSSLESS) {
		// double remaining = 0;
		double satLevel = double(ingressLpf_bytes[port][qIndex]) / congestionIndicator;
		if (satLevel > 1) {
			satLevel = 1;
		}
		setCongested(port, qIndex, "ingress", satLevel);

		// uint64_t ingressPoolSharedUsed = GetIngressSharedUsed(); // Total bytes used from the ingress "shared" pool specifically.
		// uint64_t ingressSharedPool = ingressPool - totalIngressReserved;
		// if (ingressSharedPool > ingressPoolSharedUsed) {
		// 	uint64_t remaining = ingressSharedPool - ingressPoolSharedUsed;
		// 	return std::min(uint64_t(alphaIngress[port][qIndex] * (remaining)), UINT64_MAX - 1024 * 1024);
		// }
		// else {
		// 	// ingressPoolShared is full. There is no `remaining` buffer in ingressPoolShared.
		// 	// DT's threshold returns zero in this case, but using if else just to avoid threshold computations even in the simple case.
		// 	return 0;
		// }
		uint64_t sharedusedbuffer = sharedPoolUsed; //GetIngressSharedUsed();
		uint64_t sharedbuffer = sharedPool; // ingressPool - totalIngressReserved;
		if (sharedbuffer > sharedusedbuffer ) {
			uint64_t remaining = sharedbuffer - sharedusedbuffer;
			double alphaP = alphaIngress[port][qIndex];
			uint64_t Reverie_Threshold = alphaP * (remaining) * (1.0 / GetNofP("ingress", qIndex)) ;//+ (ingress_bytes[port][qIndex] - ingressLpf_bytes[port][qIndex]);
			return std::min(uint64_t(Reverie_Threshold), UINT64_MAX - 1024 * 1024);
		}
		else {
			// SharedPool is full. There is no `remaining` buffer.
			// The threshold returns zero in this case, but using if else just to avoid threshold computations even in the simple case.
			return 0;
		}
	}
	else if (type == LOSSY) {
		// double remaining = 0;
		double satLevel = double(egressLpf_bytes[port][qIndex]) / congestionIndicator;
		if (satLevel > 1) {
			satLevel = 1;
		}
		setCongested(port, qIndex, "egress", satLevel);
		if (sharedPool > sharedPoolUsed) {
			uint64_t remaining = sharedPool - sharedPoolUsed;
			double alphaP = 1;
			if (unsched) {
				alphaP = alphaHigh;
			}
			else {
				alphaP = alphaEgress[port][qIndex];
			}
			uint64_t Reverie_Threshold = alphaP * (remaining) * (1.0 / GetNofP("egress", qIndex)); //* egress_bytes[port][qIndex]/egressLpf_bytes[port][qIndex];
			return std::min(uint64_t(Reverie_Threshold), UINT64_MAX - 1024 * 1024);
		}
		else {
			// SharedPool is full. There is no `remaining` buffer.
			// The threshold returns zero in this case, but using if else just to avoid threshold computations even in the simple case.
			return 0;
		}
	}
}

uint64_t SwitchMmu::Threshold(uint32_t port, uint32_t qIndex, std::string inout, uint32_t type, uint32_t unsched) {
	uint64_t thresh = 0;
	if (inout == "ingress") {
		switch (ingressAlg[type]) {
		case DT:
			thresh = DynamicThreshold(port, qIndex, inout, type);
			break;
		case ABM:
			thresh = ActiveBufferManagement(port, qIndex, inout, type, unsched);
			break;
		case FAB:
			thresh = FlowAwareBuffer(port, qIndex, inout, type, unsched);
			break;
		default:
			thresh = DynamicThreshold(port, qIndex, inout, type);
			break;
		}
	}
	else if (inout == "egress") {
		switch (egressAlg[type]) {
		case DT:
			thresh = DynamicThreshold(port, qIndex, inout, type);
			break;
		case ABM:
			thresh = ActiveBufferManagement(port, qIndex, inout, type, unsched);
			break;
		case FAB:
			thresh = FlowAwareBuffer(port, qIndex, inout, type, unsched);
			break;
		default:
			thresh = DynamicThreshold(port, qIndex, inout, type);
			break;
		}
	}
	return thresh;
}

bool SwitchMmu::CheckIngressAdmission(uint32_t port, uint32_t qIndex, uint32_t psize, uint32_t type, uint32_t unsched) {
	std::string model = bufferModel;
	if (model == "reverie") {
		// if (!lpfUpdatedOnce){
		// 	UpdateLpfCounters();
		// }
		switch (type) {
		case LOSSY:
			return true;
			break;
		case LOSSLESS:
			// if reserved is used up
			if ( ( (psize + ingress_bytes[port][qIndex] > reserveIngress[port][qIndex])
			        // AND if per queue headroom is used up.
			        && (psize + GetHdrmBytes(port, qIndex) > xoff[port][qIndex]) && GetHdrmBytes(port, qIndex) > 0 )
			        // or if the headroom pool is full
			        || (psize + xoffTotalUsed > xoffTotal && GetHdrmBytes(port, qIndex) > 0 )
			        // if the ingresspool+headroom is full. With DT, this condition is redundant.
			        // This is just to account for any badly configured buffer or buffer sharing if any.
			        || (psize + totalUsed > ingressPool + xoffTotal)
			        // if the switch buffer is full
			        || (psize + totalUsed > bufferPool)  ) {

				std::cout << "reverie: dropping lossless packet at ingress admission headroom " << GetHdrmBytes(port, qIndex) << " xoff " << xoff[port][qIndex] << " pktSize " << psize << " xoffTotalUsed " << xoffTotalUsed  << " totalUsed " <<  totalUsed << " ingresspool " << ingressPool << " threshold " << ReverieThreshold(port, qIndex, LOSSLESS, unsched) << " ingress_bytes " << ingressLpf_bytes[port][qIndex] << std::endl;
				return false;
			}
			else {
				return true;
			}
			break;
		default:
			std::cout << "unknown type came in to CheckIngressAdmission function! This is not expected. Abort!" << std::endl;
			exit(1);
		}
	}
	else if (model == "sonic") {
		switch (type) {
		case LOSSY:
			// if ingress bytes is greater than the ingress threshold
			if ( (psize + ingress_bytes[port][qIndex] > Threshold(port, qIndex, "ingress", type , unsched)
			        // AND if the reserved is usedup
			        && psize + ingress_bytes[port][qIndex] > reserveIngress[port][qIndex])
			        // if the ingress pool is full. With DT, this condition is redundant.
			        // This is just to account for any badly configured buffer or buffer sharing if any.
			        || (psize + (totalUsed - xoffTotalUsed) > ingressPool)
			        // or if the switch buffer is full
			        || (psize + totalUsed > bufferPool) )
			{
				return false;
			}
			else {
				return true;
			}
			break;
		case LOSSLESS:
			// if reserved is used up
			if ( ( (psize + ingress_bytes[port][qIndex] > reserveIngress[port][qIndex])
			        // AND if per queue headroom is used up.
			        && (psize + GetHdrmBytes(port, qIndex) > xoff[port][qIndex]) && GetHdrmBytes(port, qIndex) > 0 )
			        // or if the headroom pool is full
			        || (psize + xoffTotalUsed > xoffTotal && GetHdrmBytes(port, qIndex) > 0 )
			        // if the ingresspool+headroom is full. With DT, this condition is redundant.
			        // This is just to account for any badly configured buffer or buffer sharing if any.
			        || (psize + totalUsed > ingressPool + xoffTotal)
			        // if the switch buffer is full
			        || (psize + totalUsed > bufferPool)  )
			{
				std::cout << "dropping lossless packet at ingress admission headroom " << GetHdrmBytes(port, qIndex) << " xoff " << xoff[port][qIndex] << " pktSize " << psize << " xoffTotalUsed " << xoffTotalUsed << " totalUsed " <<  totalUsed << std::endl;
				return false;
			}
			else {
				return true;
			}
			break;
		default:
			std::cout << "unknown type came in to CheckIngressAdmission function! This is not expected. Abort!" << std::endl;
			exit(1);
		}
	}
	else {
		std::cout << "unknown bufferModel encountered in CheckIngressAdmission function! This is not expected. Abort!" << std::endl;
		exit(1);
	}
}


bool SwitchMmu::CheckEgressAdmission(uint32_t port, uint32_t qIndex, uint32_t psize, uint32_t type, uint32_t unsched) {
	std::string model = bufferModel;
	if (model == "reverie") {
		switch (type) {
		case LOSSLESS:
			return true;
			break;
		case LOSSY:
			// if the egress queue length is greater than the threshold
			if ( (psize + egressLpf_bytes[port][qIndex] > ReverieThreshold(port, qIndex, LOSSY, unsched)
			        // AND if the reserved is usedup. THiS IS NOT SUPPORTED AT THE MOMENT. NO reserved at the egress.
			        // && psize + egress_bytes[port][qIndex] > reserveEgress[port][qIndex]
			     )
			        // or if the egress pool is full
			        || (psize + sharedPoolUsed > sharedPool)
			        // or if the switch buffer is full
			        || (psize + totalUsed > bufferPool) )

			{
				return false;
			}
			else {
				return true;
			}
			break;
		default:
			std::cout << "unknown type came in to CheckIngressAdmission function! This is not expected. Abort!" << std::endl;
			exit(1);
		}
	}
	else if (model == "sonic") {
		switch (type) {
		case LOSSY:
			// if the egress queue length is greater than the threshold
			if ( (psize + egress_bytes[port][qIndex] > Threshold(port, qIndex, "egress", type, unsched)
			        // AND if the reserved is usedup. THiS IS NOT SUPPORTED AT THE MOMENT. NO reserved at the egress.
			        // && psize + egress_bytes[port][qIndex] > reserveEgress[port][qIndex]
			     )
			        // or if the egress pool is full
			        || (psize + egressPoolUsed[type] > egressPool[type])
			        // or if the switch buffer is full
			        || (psize + totalUsed > bufferPool) )
			{
				return false;
			}
			else {
				return true;
			}
			break;
		case LOSSLESS:
			// if threshold is exceeded
			if ( ( (psize + egress_bytes[port][qIndex] > Threshold(port, qIndex, "egress", type, unsched))
			        // AND reserved is used up. THiS IS NOT SUPPORTED AT THE MOMENT. NO reserved at the egress.
			        // && (psize + egress_bytes[port][qIndex] > reserveEgress[port][qIndex])
			     )
			        // or if the corresponding egress pool is used up
			        || (psize + egressPoolUsed[type] > egressPool[type])
			        // or if the switch buffer is full
			        || (psize + totalUsed > bufferPool) )
			{
				std::cout << "dropping lossless packet at egress admission port " << port << " qIndex " << qIndex << " egress_bytes " << egress_bytes[port][qIndex] << " threshold " << Threshold(port, qIndex, "egress", type, unsched)
				          << std::endl;
				return false;
			}
			else {
				return true;
			}
			break;
		default:
			std::cout << "unknown type came in to CheckEgressAdmission function! This is not expected. Abort!" << std::endl;
			exit(1);
		}
	}
	else {
		std::cout << "unknown bufferModel encountered in CheckIngressAdmission function! This is not expected. Abort!" << std::endl;
		exit(1);
	}
	return true;
}

void SwitchMmu::UpdateIngressAdmission(uint32_t port, uint32_t qIndex, uint32_t psize, uint32_t type, uint32_t unsched) {

	std::string model = bufferModel;

	// if (Threshold(port, qIndex, "ingress", LOSSLESS, unsched) != ReverieThreshold(port, qIndex, LOSSLESS, unsched)){
	// 	std::cout << "FUCK" << std::endl;
	// }
	// If else are simply unnecessary but its a safety check to avoid magic scenarios (if a packet vanishes in the buffer) where we
	// might assign negative value to unsigned intergers.
	if (totalIngressReservedUsed >= GetIngressReservedUsed(port, qIndex)) // removing the old reserved used (will be updated next)
		totalIngressReservedUsed -= GetIngressReservedUsed(port, qIndex);
	else
		totalIngressReservedUsed = 0;
	// NOTE: ingress_bytes simple counts total bytes occupied by port, qIndex,
	// This includes bytes from ingresspool as well as from headroom and also reserved. ingress_bytes[port][qIndex] - xoffUsed[port][qIndex] gives us the occupancy in ingressPool.
	// ingress_bytes[port][qIndex] - xoffUsed[port][qIndex] - GetIngressReservedUsed(port,qIndex) gives us the occupancy in ingress shared pool.
	ingress_bytes[port][qIndex] += psize;

	cumulatedIngresssBytes[port][qIndex] += psize;
	uint64_t timeDiff = Simulator::Now().GetNanoSeconds() - lastIngresssTime[port][qIndex];
    if (timeDiff >= RatePrintInterval) {
		// Bytes * 8 / ns = Gbps
		//YRNK输出信息
		std::cout << Simulator::Now().GetNanoSeconds() << " IngressRate: Port " << port << " qIndex " << qIndex
				<< " Rate(Gbps): " << cumulatedIngresssBytes[port][qIndex]* 8.0 / timeDiff << std::endl;
		cumulatedIngresssBytes[port][qIndex] = 0;
        lastIngresssTime[port][qIndex] = Simulator::Now().GetNanoSeconds();
    }

	totalUsed += psize; // IMPORTANT: totalUsed is only updated in the ingress. No need to update in egress. Avoid double counting.

	totalIngressReservedUsed += GetIngressReservedUsed(port, qIndex); // updating with the new reserved used.

	// Update the total headroom used.
	if (type == LOSSLESS) {
		sharedPoolUsed += psize;
		// uint64_t inst_ingress_shared_bytes = ingress_bytes[port][qIndex];//-xoffUsed[port][qIndex];
		// ingressLpf_bytes[port][qIndex] = Reveriegamma * ingressLpf_bytes[port][qIndex] + (1.0 - Reveriegamma) * (inst_ingress_shared_bytes);
		// if (ingress_bytes[port][qIndex] < ingressLpf_bytes[port][qIndex]) {
		// // if (1){
		// 	ingressLpf_bytes[port][qIndex] = ingress_bytes[port][qIndex];
		// }
		uint64_t threshold = 0;

		if (model=="sonic"){
			threshold = Threshold(port, qIndex, "ingress", LOSSLESS, unsched);
		}
		else if (model == "reverie"){
			threshold = ReverieThreshold(port, qIndex, LOSSLESS, unsched); // get the threshold
		}
		// First, remove the previously used headroom corresponding to queue: port, qIndex. This will be updated with current value next.
		xoffTotalUsed -= xoffUsed[port][qIndex];
		// Second, get currently used headroom by the queue: port, qIndex and update `xoffUsed[port][qIndex]`
		// if headroom is zero
		if (xoffUsed[port][qIndex] == 0) {
			// if ingress bytes of the queue exceeds threshold, start using headroom. pfc pause will be triggered by CheckShouldPause later.
			uint64_t temp = 0;
			if (model=="sonic"){
				temp = ingress_bytes[port][qIndex];
			}
			else if (model=="reverie"){
				temp = ingressLpf_bytes[port][qIndex];
			}
			if (temp > threshold) {
				// LOL: The commented part below was a HUGE mistake identified after debugging some of the lossless packets being dropped. It was a good lesson.
				// xoffUsed[port][qIndex] += ingress_bytes[port][qIndex] - threshold;
				xoffUsed[port][qIndex] += psize;
				sharedPoolUsed -= psize;
			}
		}
		// if we are already using headroom, any incoming packet must be added to headroom, UNTIL the queue drains and headroom becomes zero.
		else if (xoffUsed[port][qIndex] > 0) {
			xoffUsed[port][qIndex] += psize;
			sharedPoolUsed -= psize;
		}
		// Finally, update the total headroom used by adding (since we removed before) the latest value of xoffUsed (headroom used) by the queue
		xoffTotalUsed += xoffUsed[port][qIndex]; // add the current used headroom to total headroom
		// uint64_t inst_ingress_shared_bytes = ingress_bytes[port][qIndex]-xoffUsed[port][qIndex];
		// ingressLpf_bytes[port][qIndex] = Reveriegamma * ingressLpf_bytes [port][qIndex] + (1-Reveriegamma) * (inst_ingress_shared_bytes);
	}
}

void SwitchMmu::UpdateEgressAdmission(uint32_t port, uint32_t qIndex, uint32_t psize, uint32_t type) {
	//YRNK
	//新增包数量自增
	egress_pkts[port][qIndex] += 1;

	egress_bytes[port][qIndex] += psize;
	egressPoolUsed[type] += psize;
	if (type == LOSSY) {
		sharedPoolUsed += psize;
		// egressLpf_bytes[port][qIndex] = Reveriegamma * egressLpf_bytes[port][qIndex] + (1-Reveriegamma) * (egress_bytes[port][qIndex]);
	}

	cumulatedEgresssBytes[port][qIndex] += psize;
	uint64_t timeDiff = Simulator::Now().GetNanoSeconds() - lastEgresssTime[port][qIndex];
    if (timeDiff >= RatePrintInterval) {
		// Bytes * 8 / ns = Gbps
		std::cout << Simulator::Now().GetNanoSeconds() << " EgressRate: Port " << port << " qIndex " << qIndex
				<< " Rate(Gbps): " << cumulatedEgresssBytes[port][qIndex] * 8.0 / timeDiff << std::endl;
		cumulatedEgresssBytes[port][qIndex] = 0;
        lastEgresssTime[port][qIndex] = Simulator::Now().GetNanoSeconds();
    }
}

void SwitchMmu::RemoveFromIngressAdmission(uint32_t port, uint32_t qIndex, uint32_t psize, uint32_t type) {

	txBytesIngress[port][qIndex] += psize; // We assume that the packet will not be dropped after this step for any other reason.

	// If else are simply unnecessary but its a safety check to avoid magic scenarios (if a packet vanishes in the buffer) where we
	// might assign negative value to unsigned intergers.

	if (totalIngressReservedUsed >= GetIngressReservedUsed(port, qIndex)) // removing the old reserved used (will be updated next)
		totalIngressReservedUsed -= GetIngressReservedUsed(port, qIndex);
	else
		totalIngressReservedUsed = 0;

	if (ingress_bytes[port][qIndex] >= psize)
		ingress_bytes[port][qIndex] -= psize;
	else
		ingress_bytes[port][qIndex] = 0;

	if (totalUsed >= psize) // IMPORTANT: totalUsed is only updated in the ingress. No need to update in egress. Avoid double counting.
		totalUsed -= psize;
	else
		totalUsed = 0;

	totalIngressReservedUsed += GetIngressReservedUsed(port, qIndex); // updating with the new reserved used.

	// Update the total headroom used.
	if (type == LOSSLESS) {
		uint64_t inst_ingress_shared_bytes = ingress_bytes[port][qIndex];//-xoffUsed[port][qIndex];
		ingressLpf_bytes[port][qIndex] = Reveriegamma * ingressLpf_bytes[port][qIndex] + (1.0 - Reveriegamma) * (inst_ingress_shared_bytes);
		if (ingress_bytes[port][qIndex] < ingressLpf_bytes[port][qIndex]) {
			ingressLpf_bytes[port][qIndex] = ingress_bytes[port][qIndex];
		}
		// First, remove the previously used headroom corresponding to queue: port, qIndex. This will be updated with current value next.
		if (xoffTotalUsed >= xoffUsed[port][qIndex])
			xoffTotalUsed -= xoffUsed[port][qIndex];
		else
			xoffTotalUsed = 0;
		// Second, check whether we are currently using any headroom. If not, nothing to do here: headroom is zero.
		if (xoffUsed[port][qIndex] > 0) {
			// Depending on the value of headroom used, the following cases arise:
			// 1. A packet can be removed entirely from the headroom
			// 2. Headroom occupancy is already less than the packet size.
			// So the dequeued packet decrements some part of headroom (emptying it) and some from ingress pool.
			if (xoffUsed[port][qIndex] >= psize) {
				xoffUsed[port][qIndex] -= psize;
			}
			else {
				sharedPoolUsed -= psize - xoffUsed[port][qIndex];
				xoffUsed[port][qIndex] = 0;
			}
		}
		else {
			if (sharedPoolUsed >= psize)
				sharedPoolUsed -= psize;
			else
				sharedPoolUsed = 0;
		}
		xoffTotalUsed += xoffUsed[port][qIndex]; // add the current used headroom to total headroom
	}
}

// void SwitchMmu::UpdateLpfCounters(){
// 	for (uint32_t port = 0; port < portCount; port++){
// 		for (uint32_t qIndex=0;qIndex<qCnt;qIndex++){
// 			uint64_t inst_ingress_shared_bytes = ingress_bytes[port][qIndex];//-xoffUsed[port][qIndex];
// 			ingressLpf_bytes[port][qIndex] = Reveriegamma * ingressLpf_bytes[port][qIndex] + (1-Reveriegamma) * (inst_ingress_shared_bytes);

// 			egressLpf_bytes[port][qIndex] = Reveriegamma * egressLpf_bytes[port][qIndex] + (1-Reveriegamma) * (egress_bytes[port][qIndex]);
// 		}
// 	}
// 	lpfUpdatedOnce = 1;
// 	double delay = 1e9*1500*8/bandwidth[0];

// 	Simulator::Schedule(NanoSeconds(delay),&SwitchMmu::UpdateLpfCounters,this);
// }

void SwitchMmu::RemoveFromEgressAdmission(uint32_t port, uint32_t qIndex, uint32_t psize, uint32_t type) {
	//YRNK
	//新增包移除
	egress_pkts[port][qIndex] -= 1;


	txBytesEgress[port][qIndex] += psize; // We assume that the packet will not be dropped after this step for any other reason.

	if (egress_bytes[port][qIndex] >= psize)
		egress_bytes[port][qIndex] -= psize;
	else
		egress_bytes[port][qIndex] = 0;

	if (egressPoolUsed[type] >= psize)
		egressPoolUsed[type] -= psize;
	else
		egressPoolUsed[type] = 0;

	if (type == LOSSY) {
		if (sharedPoolUsed >= psize)
			sharedPoolUsed -= psize;
		else
			sharedPoolUsed = 0;

		egressLpf_bytes[port][qIndex] = Reveriegamma * egressLpf_bytes[port][qIndex] + (1.0 - Reveriegamma) * (egress_bytes[port][qIndex]);
		if (egress_bytes[port][qIndex] < egressLpf_bytes[port][qIndex]) {
			egressLpf_bytes[port][qIndex] = egress_bytes[port][qIndex];
		}
	}
}



uint64_t SwitchMmu::GetHdrmBytes(uint32_t port, uint32_t qIndex) {

	return xoffUsed[port][qIndex];
}

bool SwitchMmu::CheckShouldPause(uint32_t port, uint32_t qIndex) {
	return !paused[port][qIndex] && (GetHdrmBytes(port, qIndex) > 0);
}

bool SwitchMmu::CheckShouldResume(uint32_t port, uint32_t qIndex) {
	std::string model = bufferModel;
	if (!paused[port][qIndex])
		return false;
	if (model == "sonic") {
		return GetHdrmBytes(port, qIndex) == 0 && (ingress_bytes[port][qIndex] < xon[port][qIndex] || ingress_bytes[port][qIndex] + xon_offset[port][qIndex] <= Threshold(port, qIndex, "ingress", LOSSLESS, 0) );
	}
	else if (model == "reverie") {
		return GetHdrmBytes(port, qIndex) == 0 && (ingressLpf_bytes[port][qIndex] < xon[port][qIndex] || ingressLpf_bytes[port][qIndex] + xon_offset[port][qIndex] <= ReverieThreshold(port, qIndex, LOSSLESS, 0) );
	}
	// Minor detail: Threshold(port, qIndex, "ingress", LOSSLESS, 0) is used above where type=LOSSLESS and unsched=0; It is obvious that resume is triggered only for LOSSLESS queues.
	// Abound unsched=0: sending resume must be independent of arriving traffic and hence the threshold used is the default value and a prioritized value cannot be used here as is done for admission of priority packets in ABM.
}

void SwitchMmu::SetPause(uint32_t port, uint32_t qIndex) {
	paused[port][qIndex] = true;
}
void SwitchMmu::SetResume(uint32_t port, uint32_t qIndex) {
	paused[port][qIndex] = false;
}


void SwitchMmu::ConfigEcn(uint32_t port, uint32_t _kmin, uint32_t _kmax, double _pmax) {
	kmin[port] = _kmin * 1000;
	kmax[port] = _kmax * 1000;
	pmax[port] = _pmax;
}
void SwitchMmu::ConfigEcn(uint32_t port, double _kmin, double _kmax, double _pmax) {
	kmin[port] = _kmin * 1000;
	kmax[port] = _kmax * 1000;
	pmax[port] = _pmax;
}

void SwitchMmu::ConfigEcnCoDel(uint32_t port, uint32_t _target, uint64_t _interval){
	codel_target = _target; // 51200; 51.2us
	codel_interval = _interval; //1024000; 1024us
}

void SwitchMmu::ConfigEcnCEDM(uint32_t port, uint32_t _kmin, uint32_t _kmax, double _ewma) {
	cedm_kmin = _kmin;
	cedm_kmax = _kmax;
	cedm_ewma = _ewma;
}

void SwitchMmu::ConfigEcnMATCP(uint32_t port, uint32_t _kmin, uint32_t _ts){
	matcp_kmin = _kmin;
	matcp_ts = _ts;
}

void SwitchMmu::ConfigEcnIMCAQM(uint32_t port, uint32_t _kmin, uint32_t _kmax, uint32_t _jitter, double _ewma_fast, double _ewma_slow) {
	imc_kmin = _kmin;
	imc_kmax = _kmax;
	imc_steady_jitter = _jitter;
	imc_alpha_fast = _ewma_fast;	
	imc_alpha_slow = _ewma_slow;
}

void SwitchMmu::ConfigEcnPRED(
	//端口
   		uint32_t port,				//端口号，可能实际上并没有什么用处
	//FCS
		double tfcs_factor,			//TFCS相对于RTT的比例因子
		uint32_t fcs_bitmap_size,	//FCS位图大小
	//QLA
		//UF
		double tqla_factor,			//TQLA相对于RTT的比例因子
	    double beta,				//权重因子
		double q_left,				//映射函数左侧值
		double q_right,				//映射函数右侧值
		//DM
		double lambda_base,			//lambda初始值
		double lambda_delta,		//lambda调整器中单次调整大小
		//minK Adjuster
		uint32_t minK,				//minK初始值
		uint32_t mink_delta,		//minK调整器中单次调整大小
		double lambda_min,			//最小lambda值
	//PRED
    	uint32_t maxK//,				//K最大值，论文中设定500KB，实际运用于AQM_PRED方法中
	//其他
		// std::string link_delay
) {
	// std::cout<<"[PRED] ConfigEcnPRED ==> "<<
	// "    port: "<<port<<"\n"<<
	// "    tfcs_factor: "<<tfcs_factor<<"\n"<<
	// "    fcs_bitmap_size: "<<fcs_bitmap_size<<"\n"<<
	// "    tqla_factor: "<<tqla_factor<<"\n"<<
	// "    beta: "<<beta<<"\n"<<
	// "    q_left: "<<q_left<<"\n"<<
	// "    q_right: "<<q_right<<"\n"<<
	// "    lambda_base: "<<lambda_base<<"\n"<<
	// "    lambda_delta: "<<lambda_delta<<"\n"<<
	// "    minK: "<<minK<<"\n"<<
	// "    mink_delta: "<<mink_delta<<"\n"<<
	// "    lambda_min: "<<lambda_min<<"\n"<<
	// "    maxK: "<<maxK<<"\n"<<
	// // "    link_delay: "<<link_delay<<
	// "\n";
	//此处有优化的余地，会调用port次，实际一次就行
	//好吧，鉴于port并没有什么用，还是只会调用到一次的
	initPredStatics(tfcs_factor, tqla_factor, lambda_min); 
    
	for (uint32_t p=0;p<pCnt;++p){
		// TimeValue timevalue ;
		// timevalue.DeserializeFromString(link_delay,nullptr);
		// //采用RTT=2 * link_delay的设定，符合论文中RTT=2*propagation delay的设定
		// portRTTs[p] = 2 * timevalue.Get().GetNanoSeconds();
		for (uint32_t queue = 0; queue < qCnt; ++queue) {
			//配置QLA
			QlaState& qla = GetQlaState(p, queue);
			qla.lambda_base = lambda_base;
			qla.lambda_delta = lambda_delta;
			qla.minK = minK;
			qla.mink_delta = mink_delta;
			qla.maxK = maxK;
			qla.beta = beta;
			qla.q_left = q_left;
			qla.q_right = q_right;
			//配置FCS
			FcsState& fcs = GetFcsState(p, queue);
			fcs.initiate(fcs_bitmap_size); // 动态位图大小
		}
	}

	//YRNK
	//调用QLA计时器启动函数
	// 禁用，改为switch node中enqueue时判断是否未启用
	// StartAllQlaTimers();

    // //配置FCS
    // for (uint32_t queue = 0; queue < qCnt; ++queue) {
    //     FcsState& fcs = GetFcsState(port, queue);
    //     fcs.initiate(fcs_bitmap_size); // 动态位图大小
    //     // ... 其他FCS参数
    // }
}

bool SwitchMmu::ShouldSendCN(uint32_t ifindex, uint32_t qIndex, Ptr<Packet> p) {// AQM算法进行ECN标记判断
	bool MarkECN = 0;
	switch (aqmMode) {
		case RED:
			MarkECN = AQM_RED(ifindex, qIndex);
			break;
		case CoDel:
			MarkECN = AQM_CoDel(ifindex, qIndex);
			break;
		case MATCP:
			MarkECN = AQM_MATCP(ifindex, qIndex);
			break;
		case CEDM:
			MarkECN = AQM_CEDM(ifindex, qIndex, p);
			break;
		case MBECN:
			MarkECN = AQM_MBECN(ifindex, qIndex);
			break;	
		case PRED:
			MarkECN = AQM_PRED(ifindex, qIndex);
			break;	
		case IMCAQM:
			MarkECN = AQM_IMCAQM(ifindex, qIndex);
			break;	
		default:
			MarkECN = AQM_RED(ifindex, qIndex);
			break;
	}
	// if (MarkECN)
		std::cout << Simulator::Now().GetNanoSeconds() << " SwitchMMU:ShouldSendCN "
				<< " ifindex " << ifindex << " qIndex " << qIndex << "  AQM " << aqmMode
				<< " egress_bytes " << egress_bytes[ifindex][qIndex] << " ifMarked " << MarkECN
				<< std::endl;
    return MarkECN;
}

bool SwitchMmu::AQM_RED(uint32_t ifindex, uint32_t qIndex) {
	if (qIndex == 0)
		return false;
	// std::cout<<" debug "<<Simulator::Now().GetNanoSeconds()<<" SwitchMMU:AQM_RED "
	// 		 <<" ifindex "<<ifindex<<" qIndex "<<qIndex<<" egress_bytes "<<egress_bytes[ifindex][qIndex]<<" kmin "<<kmin[ifindex]<<" kmax "<<kmax[ifindex]<<" pmax "<<pmax[ifindex]<<std::endl;
	if (egress_bytes[ifindex][qIndex] > kmax[ifindex])
		return true;
	if (egress_bytes[ifindex][qIndex] > kmin[ifindex]) {
		//YRNK_ADD
		//添加点斜式的逻辑
		double p;
		if(Use_Point_Slope){
			//点斜式：p = lambda * (q - minK)
			p = Point_Slope_Lambda 
			 *
			 double(egress_bytes[ifindex][qIndex] - kmin[ifindex])
			 /
			 1000000;//缩放B到MB
			std::cout<<" debug "<<Simulator::Now().GetNanoSeconds()<<" SwitchMMU:AQM_RED Use_Point_Slope lambda "
			<<Point_Slope_Lambda<<" q "<<egress_bytes[ifindex][qIndex]<<" kmin "<<kmin[ifindex]<<" p "<<p<<std::endl;
		}else{
			p = pmax[ifindex] * double(egress_bytes[ifindex][qIndex] - kmin[ifindex]) / (kmax[ifindex] - kmin[ifindex]);
		}
		if (UniformVariable(0, 1).GetValue() < p)//概率内标记
			return true;
	}
	return false;
}

bool SwitchMmu::AQM_CoDel(uint32_t ifindex, uint32_t qIndex) {
	/* Cited From TCN （CoNext16） 用 RTT*λ 作为ECN标记阈值，停留时间>RTT*λ 就标记ECN
	Testbed
	For Codel, we experimentally determine its best setting (target = 51.2us, interval = 1024us) 
	since the recommendation setting (5ms and 100ms) in [23] is for Internet.
	Given  base RTT is ~250us, the standard ECN marking threshold is 32KB for ECN/RED and 256us for TCN. 

	NS2 Simulation
	144 leaf-spine topology  10Gbps  85.2usRTT
	65packets for ECN/RED；   78us for TCN；  
	*/
	
	// 估计Sojourn Time  // 采用瞬时队列大小和出口带宽来估算排队延迟(在ns3中，基本无误差)  egress_bytes * 8 (转为bits) * 1e9 (转为纳秒级速率) / 链路带宽
	double sojourn_time = (egress_bytes[ifindex][qIndex] * 8.0 * 1e9) / linkBw;

	// CoDel 状态评估  
	bool ok_to_mark = false;
	if (sojourn_time > codel_target){
		if (codel_first_above_time[ifindex][qIndex] == 0) { // 延迟刚刚超过 Target，开始倒计时一个 Interval
			codel_first_above_time[ifindex][qIndex] = Simulator::Now().GetNanoSeconds() + codel_interval;
		} else if (Simulator::Now().GetNanoSeconds() >= codel_first_above_time[ifindex][qIndex]) {
			// 延迟超过 Target 且已经持续了整整一个 Interval，确认网络拥塞
			ok_to_mark = true;
		}
	}else{
		codel_first_above_time[ifindex][qIndex] = 0; // 在一个Interval以内，只要延时跌落Target，就重置计时器
    }

	// CoDel 控制回路层 (决定是否打 ECN 标记)
	bool mark_ecn = false;
	if (codel_dropping[ifindex][qIndex]) { // 当前正处于拥塞标记状态
		if (!ok_to_mark) {// 拥塞缓解，退出标记状态
			codel_dropping[ifindex][qIndex] = false;
		} else if (Simulator::Now().GetNanoSeconds() >= codel_drop_next[ifindex][qIndex]) {
			// 间隔时间到了，执行 ECN 标记，并按照 1/sqrt(count) 缩短下一次标记的时间间隔
			mark_ecn = true;
			codel_count[ifindex][qIndex]++;
			codel_drop_next[ifindex][qIndex] = Simulator::Now().GetNanoSeconds() + codel_interval / std::sqrt(codel_count[ifindex][qIndex]);
		}
	} else { // 正常状态
		if (ok_to_mark) { // 刚进入确认拥塞状态，立刻标记首个包作为警告
			mark_ecn = true;
			codel_dropping[ifindex][qIndex] = true;
			uint32_t delta = codel_count[ifindex][qIndex] - codel_lastcount[ifindex][qIndex];
			codel_count[ifindex][qIndex] = 1;
			// 如果距离上次拥塞结束不足 16 个 Interval，则继承之前的计数
            if (delta > 1 && (Simulator::Now().GetNanoSeconds() - codel_drop_next[ifindex][qIndex] < 16 * codel_interval)) {
                codel_count[ifindex][qIndex] = delta;
            }
			codel_drop_next[ifindex][qIndex] = Simulator::Now().GetNanoSeconds() + codel_interval / std::sqrt(codel_count[ifindex][qIndex]);
			codel_lastcount[ifindex][qIndex] = codel_count[ifindex][qIndex];
		}
	}
	return mark_ecn;
}

bool SwitchMmu::AQM_MATCP(uint32_t ifindex, uint32_t qIndex) {
	if (qIndex == 0)
		return false;
	if (matcp_start_flag){
		Simulator::Schedule(NanoSeconds(matcp_ts), &SwitchMmu::MATCP_CALCULATE_SLOPE, this, ifindex, qIndex);
        matcp_start_flag = 0;
    }
	matcp_avg_q[ifindex][qIndex] = (1 - matcp_ewma) * matcp_avg_q[ifindex][qIndex] 
						      + matcp_ewma * egress_bytes[ifindex][qIndex]; // Eq(4)
	if (egress_bytes[ifindex][qIndex] > matcp_kmin)
		return true;

	///////////////////////////////////////////////////////////////////	
	// if (egress_bytes[ifindex][qIndex] > 200000)
	// 	return true;
	// if (egress_bytes[ifindex][qIndex] > 30000) {
	// 	double p = 0.2 * double(egress_bytes[ifindex][qIndex] - 30000) / (200000 - 30000);
	// 	if (UniformVariable(0, 1).GetValue() < p)//概率内标记
	// 		return true;
	// }
	// return false;
	///////////////////////////////////////////////////////////////////	

	// a MATCP switch also needs to mark packets with ECN if and only if 
	// the queue length is larger than the ECN threshold.
	return false;
}

uint32_t SwitchMmu::MATCP_GET_SLOPE(uint32_t ifindex, uint32_t qIndex){
    std::cout << " mmudebug: " << Simulator::Now().GetNanoSeconds() << " SwitchMMU:MATCP_GET_SLOPE "
              << " ifindex " << ifindex << " qIndex " << qIndex << " matcp_q_gradient "
              << matcp_q_gradient[ifindex][qIndex] << " linkBw " << linkBw << std::endl;
	return 8 * std::min(1.0, std::max(0.0, matcp_q_gradient[ifindex][qIndex] / linkBw)); // Eq(6)
}

void SwitchMmu::MATCP_CALCULATE_SLOPE(uint32_t ifindex, uint32_t qIndex){
	matcp_q_gradient[ifindex][qIndex] = (matcp_avg_q[ifindex][qIndex] - matcp_qlast[ifindex][qIndex]) * 1e9 * 8 / matcp_ts; // B/ns*1e9*8=bps
	matcp_qlast[ifindex][qIndex] = matcp_avg_q[ifindex][qIndex]; 	// Eq(3) no   Eq(8) yes
	std::cout<<" mmudebug: "<<Simulator::Now().GetNanoSeconds()<<" SwitchMMU:MATCP_CALCULATE_SLOPE "
			 <<" ifindex "<<ifindex<<" qIndex "<<qIndex<<" egress "<<egress_bytes[ifindex][qIndex]
			 <<" avg_q "<<matcp_avg_q[ifindex][qIndex]
			 <<" matcp_q_gradient "<<matcp_q_gradient[ifindex][qIndex]<<" linkBw "<<linkBw<<std::endl;
	Simulator::Schedule(NanoSeconds(matcp_ts), &SwitchMmu::MATCP_CALCULATE_SLOPE, this, ifindex, qIndex);
}


bool SwitchMmu::AQM_CEDM(uint32_t ifindex, uint32_t qIndex, Ptr<Packet> p) { //默认为出队时
	bool res = true; 
	// Bytes *8 * 1e9/ ns = bps
	double s_gradient = (double(egress_bytes[ifindex][qIndex]) - double(cedm_qlast[ifindex][qIndex])) *8 * 1e9/ double(Simulator::Now().GetNanoSeconds() - cedm_tlast[ifindex][qIndex] + 1); // avoid division by zero
	cedm_avg_s[ifindex][qIndex] = (1 - cedm_ewma) * cedm_avg_s[ifindex][qIndex] + cedm_ewma * s_gradient;

	std::cout << Simulator::Now().GetNanoSeconds() << " CEDM: Port " << ifindex << " qIndex " << qIndex<< " s_gradient " << s_gradient << " cedm_avg_s " << cedm_avg_s[ifindex][qIndex] 
			<<" egress_bytes "<< egress_bytes[ifindex][qIndex] <<" qlast "<< cedm_qlast[ifindex][qIndex] << " tlast "<< cedm_tlast[ifindex][qIndex]
			<< std::endl;

	PppHeader ppp;
	Ipv4Header h;
	p->RemoveHeader(ppp);
	p->RemoveHeader(h);
	Ipv4Header::EcnType ecnType = h.GetEcn();
	if (ecnType == Ipv4Header::EcnType::ECN_CE)
		res = true; 
	else
		res = false; 
	if(ecnType == Ipv4Header::EcnType::ECN_CE && egress_bytes[ifindex][qIndex] < cedm_kmax) // 被标记ECN 且 队列<kmax
		if(egress_bytes[ifindex][qIndex] < cedm_kmin || cedm_avg_s[ifindex][qIndex] < 0){  // 队列<kmin  或  梯度<0
			h.SetEcn((Ipv4Header::EcnType)0x00);
			res = false;
        }	
	p->AddHeader(h);
	p->AddHeader(ppp);

	cedm_tlast[ifindex][qIndex] = Simulator::Now().GetNanoSeconds();
	cedm_qlast[ifindex][qIndex] = egress_bytes[ifindex][qIndex];
	return res;
}

void SwitchMmu::AQM_CEDM_ENQUEUE(uint32_t ifIndex, uint32_t qIndex, Ptr<Packet> p){
	if(egress_bytes[ifIndex][qIndex] > cedm_kmax || (cedm_avg_s[ifIndex][qIndex] > 0 && egress_bytes[ifIndex][qIndex] > cedm_kmin)){
        PppHeader ppp;
		Ipv4Header h;
		p->RemoveHeader(ppp);
		p->RemoveHeader(h);
		h.SetEcn(Ipv4Header::EcnType::ECN_CE); // ECN_NotECT = 0x00,  ECN_ECT1 = 0x01,  ECN_ECT0 = 0x02, ECN_CE = 0x03
		p->AddHeader(h);
		p->AddHeader(ppp);	
	}
}

bool SwitchMmu::AQM_MBECN(uint32_t ifindex, uint32_t qIndex) {
	return false;
}

bool SwitchMmu::AQM_IMCAQM(uint32_t ifindex, uint32_t qIndex) {
	if (qIndex == 0) return false;
	// 第一次有包进来时，启动该队列的状态机调度器
    if (!imc_period_cnt[ifindex][qIndex]) {
        imc_period_cnt[ifindex][qIndex]++;
        Simulator::Schedule(NanoSeconds(maxRtt), &SwitchMmu::IMCAQM_PeriodControl, this, ifindex, qIndex);
    }
    ImcAqmState state = imc_aqm_state[ifindex][qIndex];
    // Steady 和 Burst 使用 K_min 进行降速，Recover 使用 K_max 排空
    if (state == ImcAqmState::IMC_STEADY || state == ImcAqmState::IMC_BURST) {
        if (egress_bytes[ifindex][qIndex] > imc_kmin) return true;
    } else if (state == ImcAqmState::IMC_RECOVER) {
        if (egress_bytes[ifindex][qIndex] > imc_kmax) return true;
    }
    return false;
}

void SwitchMmu::IMCAQM_PeriodControl(uint32_t port, uint32_t qIndex) {
    uint64_t Q_t = egress_bytes[port][qIndex];
	uint64_t DT_t = Threshold(port, qIndex, "egress", LOSSLESS, 0);
	uint64_t Fn_t = imc_kmin; // 简化计算，暂时以K_min作为稳态目标队列长度  TODO：：后续需统计流数N，并计算对应的稳态目标队列长度 f(N)
	
	if (imc_period_cnt[port][qIndex] == 1) { // 首周期初始化
		imc_aqm_state[port][qIndex] = ImcAqmState::IMC_STEADY;
		imc_T_t[port][qIndex] = maxRtt;
		imc_dt_last[port][qIndex] = DT_t;
		imc_q_last[port][qIndex] = Q_t;
		imc_fn_last[port][qIndex] = Fn_t;
		imc_r_ewma[port][qIndex] = Q_t * 8 * 1e9 / maxRtt + linkBw; // B *8 *1e9 / ns = bps
		imc_qhat[port][qIndex] = Q_t;
        imc_period_cnt[port][qIndex]++;
        Simulator::Schedule(NanoSeconds(maxRtt), &SwitchMmu::IMCAQM_PeriodControl, this, port, qIndex);
		return;
	}
	// --------------------------------------------------------------------
    // ------------------- 模块 1: Burst Distinguish  ---------------------
	// --------------------------------------------------------------------
	uint64_t Dt_last = imc_dt_last[port][qIndex];
	uint64_t Q_last = imc_q_last[port][qIndex];
	uint64_t Fn_last = imc_fn_last[port][qIndex];
	uint64_t T_t = imc_T_t[port][qIndex];
	uint64_t Qhat_t = imc_qhat[port][qIndex];

    uint64_t Error_t = Q_t > Qhat_t ? Q_t - Qhat_t : 0;
    uint64_t Safe_t = 0;
	if (Dt_last > Q_last && Q_last < imc_kmax)
		// Safe_t = (Dt_last - Q_last) * (1 - (double)Q_last / Fn_last);
		Safe_t = (Dt_last - Q_last) * (1 - (double)Q_last / imc_kmax);


    ImcPortState port_type = ImcPortState::IMC_NP; 
    if (Error_t > imc_steady_jitter && Error_t <= Safe_t) {
        port_type = ImcPortState::IMC_BP; // BP
    } else if (Error_t + Q_last > Dt_last ) {
        port_type = ImcPortState::IMC_DP; // DP
    }

	if (port == 1){
	std::cout<<"-------------------------AQM_IMCAQM (KB, Gbps, ns)------------------------------------------"<<std::endl;
	
	std::cout<<Simulator::Now().GetNanoSeconds()<<" SwitchMMU:IMCAQM_PeriodControl_1_burstDistinguish "<<" ifindex "<<port<<" qIndex "<<qIndex <<" period: "<<imc_period_cnt[port][qIndex]
			<<" Q_t(KB) "<<Q_t/1e3<<" Qhat_t "<<Qhat_t/1e3<<" Error_t "<<Error_t/1e3
			 <<" Dt_last "<<Dt_last/1e3<<" Q_last "<<Q_last/1e3<<" Fn_last "<<Fn_last/1e3<<" Safe_t "<<Safe_t/1e3 <<" Safe_max "<<(Dt_last - Q_last)/1e3
			 <<" port_type "<<(port_type == ImcPortState::IMC_BP ? "BP" : (port_type == ImcPortState::IMC_DP ? "DP" : "NP"))
			 <<std::endl;
	}
	// --------------------------------------------------------------------
    // ------------------- 模块 2: State Switching  -----------------------
	// --------------------------------------------------------------------
    ImcAqmState Aqm_state = imc_aqm_state[port][qIndex];
    ImcAqmState Aqm_state_new = Aqm_state;
	double R_t = std::max(0.0, (Q_t*1.0 - Q_last) * 8 * E1e9  / T_t + linkBw);  //B*8*1e9/ns=bps

    // 按照有限状态机 (FSM) 进行转移
	{
		if (Aqm_state == ImcAqmState::IMC_STEADY) {
			switch (port_type) {
				case ImcPortState::IMC_BP:
					Aqm_state_new = ImcAqmState::IMC_BURST;
					break;
			}
		} else if (Aqm_state == ImcAqmState::IMC_BURST) {
			switch (port_type) {
				case ImcPortState::IMC_NP:
					if (R_t < linkBw)
						Aqm_state_new = ImcAqmState::IMC_RECOVER;
					break;
				case ImcPortState::IMC_DP:
					Aqm_state_new = ImcAqmState::IMC_STEADY;
					break;
			}
		} else if (Aqm_state == ImcAqmState::IMC_RECOVER) {
			switch (port_type) {
				case ImcPortState::IMC_BP:
					Aqm_state_new = ImcAqmState::IMC_BURST;
					break;
				case ImcPortState::IMC_DP:
					Aqm_state_new = ImcAqmState::IMC_STEADY;
					break;
				case ImcPortState::IMC_NP:
					if (Q_t <= Fn_t && R_t > linkBw) 
						Aqm_state_new = ImcAqmState::IMC_STEADY;
					if (Q_t <= Fn_t && R_t <= linkBw) 
						Aqm_state_new = ImcAqmState::IMC_RECOVER;
					if (Q_t > Fn_t && R_t > linkBw) 
						Aqm_state_new = ImcAqmState::IMC_BURST;
					if (Q_t > Fn_t && R_t <= linkBw) 
						Aqm_state_new = ImcAqmState::IMC_RECOVER;
					break;
			}
		}
	}
    // 计算下一个周期的周期长度 T_{t+1}
    uint64_t T_next;
	switch (Aqm_state_new) {
		case ImcAqmState::IMC_STEADY:
			T_next = maxRtt;
			break;
		case ImcAqmState::IMC_BURST:
			T_next = maxRtt / 2;
			break;
		case ImcAqmState::IMC_RECOVER:
			if (linkBw > imc_r_ewma[port][qIndex] && Q_t > Fn_t) {  // B * 8 * 1e9 / bps = ns
				T_next = std::min(maxRtt, (Q_t - Fn_t) * 8 * E1e9 / (linkBw - imc_r_ewma[port][qIndex]));
			} else {
				T_next = maxRtt; // 兜底
			}
			break;
	}
	if (port == 1){
	std::cout<<Simulator::Now().GetNanoSeconds()<<" SwitchMMU:IMCAQM_PeriodControl_2_stateSwitching "
			<<" Aqm_state "<<(Aqm_state == ImcAqmState::IMC_STEADY ? "STEADY" : (Aqm_state == ImcAqmState::IMC_BURST ? "BURST" : "RECOVER"))
			<<" =>>new: "<<(Aqm_state_new == ImcAqmState::IMC_STEADY ? "STEADY" : (Aqm_state_new == ImcAqmState::IMC_BURST ? "BURST" : "RECOVER"))
			<<"    T_next "<<T_next<<std::endl;
	}
	// --------------------------------------------------------------------
    // ------------------ 模块 3: Switch Port Model  ----------------------
	// --------------------------------------------------------------------
	// Rate Model:  (Long-term Injection rate)
	// double R_t = std::max(0.0, (Q_t*1.0 - Q_last) * 8 * E1e9  / T_t + linkBw);  //B*8*1e9/ns=bps
	if (port_type != ImcPortState::IMC_BP) {  // 只有在非 Burst 时更新 R_ewma
		if (R_t < imc_r_ewma[port][qIndex]) { // 快减 慢加  减少突发干扰
			imc_r_ewma[port][qIndex] = (1.0 - imc_alpha_fast) * imc_r_ewma[port][qIndex] + imc_alpha_fast * R_t;
		} else {
			imc_r_ewma[port][qIndex] = (1.0 - imc_alpha_slow) * imc_r_ewma[port][qIndex] + imc_alpha_slow * R_t;
		}
	}
	// Queue Model: (Estimate the queue evolution)   bps * ns / 1e9 / 8 = Bytes
	if ( Q_t + (imc_r_ewma[port][qIndex] * 1.0 - linkBw) * T_next / E1e9 / 8 > 0 ){
		imc_qhat[port][qIndex] = Q_t + (imc_r_ewma[port][qIndex]*1.0 - linkBw) * T_next / E1e9 / 8; //bps*ns/1e9/8=B
	}else{
		imc_qhat[port][qIndex] = 0; //bps*ns/1e9/8=B
	}

	if (port == 1){
		std::cout<<Simulator::Now().GetNanoSeconds()<<" SwitchMMU:IMCAQM_PeriodControl_3_switchPortModel "
			<<" R_t(Gbps) "<<R_t/1e9<<" T_t "<<T_t<<" imc_r_ewma(Gbps) "<<imc_r_ewma[port][qIndex]/1e9<<" Qhat_t(KB) "<<imc_qhat[port][qIndex]/1e3<<std::endl;
	}
	
    // 保存当前状态留作下次计算
	imc_aqm_state[port][qIndex] = Aqm_state_new;
	imc_T_t[port][qIndex] = T_next;
    imc_dt_last[port][qIndex] = DT_t;
    imc_q_last[port][qIndex] = Q_t;
    imc_fn_last[port][qIndex] = Fn_t;

    // 递归调度下一次状态机更新
    Simulator::Schedule(NanoSeconds(T_next), &SwitchMmu::IMCAQM_PeriodControl, this, port, qIndex);
}


bool SwitchMmu::AQM_PRED(uint32_t ifindex, uint32_t qIndex){
	if (qIndex == 0)
		return false;
	// double avgq = avg_egress_bytes[ifindex][qIndex];

	double Q = egress_pkts[ifindex][qIndex];//数据包数量，统一规则
	QlaState& qla = GetQlaState(ifindex,qIndex);
	FcsState& fcs = GetFcsState(ifindex,qIndex);
	double KMAX = qla.maxK;//kmax[ifindex];
	double KMIN = qla.minK;//kmin[ifindex];

	if (Q > KMAX){//大于上阈直接丢包
		// count[ifindex][qIndex]=0;
		std::cout<<Simulator::Now().GetNanoSeconds()<<" AQM_PRED[port:"<<ifindex<<"][queue:"<<qIndex<<"] Q>MAXK Mark 1 "<<std::endl;
		return true;
	}else if (Q > KMIN) {//上下阈间概率丢包
		// count[ifindex][qIndex]++;

		//基础概率公式
		/*
			计算丢包概率
			Pmark=Pmax*(AVGq-MinTh)/(MaxTh-MinTh)
		*/
		/*
			两点式中
			Pmark=lambda*(q-mink)
			q：输出队列长度
		*/
		double fn = fcs.getFn();
		double pmark = 
			fn*
			qla.lambda_current * 
			(Q - KMIN)//包为单位，包~1KB
			/1000;//YRNK: 缩放，我不知道对不对
			//KB转MB缩放1e3
		//此处使用lambda_current而非lambda_base，前者为QLA模块当前采用的实际lambda
		std::cout<<Simulator::Now().GetNanoSeconds()<<" AQM_PRED[port:"<<ifindex<<"][queue:"<<qIndex<<"] Q>MINK Pmark: "<<pmark
		<<" F_N: "<<fn
		<<" lambda_current: "<<qla.lambda_current
		<<" slope: "<<fn*qla.lambda_current//斜率，即为F(N)*lambda_current
		<<" Q: "<<Q<<" KMIN: "<<KMIN<<" Q_MINUS_KMIN: "<<Q-KMIN<<std::endl;
		//避免概率超出正常范围
		if (pmark < 0.0) pmark = 0.0;
		if (pmark > 1.0) pmark = 1.0;

		std::cout<<Simulator::Now().GetNanoSeconds()<<" Mark? ";
		if (UniformVariable(0, 1).GetValue() < pmark){//概率内丢包
			// count[ifindex][qIndex]=0;
			std::cout<<" AQM_PRED[port:"<<ifindex<<"][queue:"<<qIndex<<"] Mark 1 "<<std::endl;
			return true;
		}else{
			std::cout<<" AQM_PRED[port:"<<ifindex<<"][queue:"<<qIndex<<"] Mark 0 "<<std::endl;
			return false;
		}
	}else{//小于下阈不丢包
		// count[ifindex][qIndex]=0;
		std::cout<<Simulator::Now().GetNanoSeconds()<<" AQM_PRED[port:"<<ifindex<<"][queue:"<<qIndex<<"] Q<MINK Mark 0 "<<std::endl;
		return false;
	}
}

/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// YRNK_METHOD
// 更新平均队列长度
/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
void SwitchMmu::UpdateAvgQueue(uint32_t ifindex, uint32_t qIndex) {
        if (qIndex == 0) return;

        uint32_t current_qlen = egress_bytes[ifindex][qIndex];

        // EWMA公式：avg = (1 - wq) * avg + wq * current_qlen
        double old_avg = avg_egress_bytes[ifindex][qIndex];
        avg_egress_bytes[ifindex][qIndex] =
            (1.0 - wq[ifindex]) * old_avg + wq[ifindex] * current_qlen;

        // 防止avg太小导致下溢出【AI说是可选？？】
        if (avg_egress_bytes[ifindex][qIndex] < 1.0) {
            avg_egress_bytes[ifindex][qIndex] = 1.0;
        }
}

/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// YRNK_METHOD
// 获取平均队列长度
/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
double SwitchMmu::GetAvgQueueLength(uint32_t ifindex, uint32_t qIndex) {
	return avg_egress_bytes[ifindex][qIndex];
}

/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// YRNK_METHOD
// 获取瞬时队列长度
/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
uint32_t SwitchMmu::GetCurrentQueueLength(uint32_t ifindex, uint32_t qIndex) {
	return egress_bytes[ifindex][qIndex];
}

/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// YRNK_METHOD
// 初始化RED算法的参数
/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
void SwitchMmu::InitRed(uint32_t port) {
	for (uint32_t q = 0; q < qCnt; q++) {
		avg_egress_bytes[port][q] = 0.0;
		count[port][q] = 0;
	}
	wq[port] = 0.002;  // 默认权重
}



void SwitchMmu::ConfigEcnNew(uint32_t port, uint32_t _kmin, uint32_t _kmax, double _pmax, double _wq = 0.002) {
	kmin[port] = _kmin * 1000;
	kmax[port] = _kmax * 1000;
	pmax[port] = _pmax;

	/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
	// YRNK_ADD
	// 以下为针对RED算法的新增配置
	/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

	wq[port] = _wq;

	// 初始化平均队列长度
	InitRed(port);
}


/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// YRNK_ADD
/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

// YRNK_METHOD
//懒加载方式更新FCS状态
void SwitchMmu::UpdateFcsStats(uint32_t port, uint32_t queue, uint32_t fingerprint,uint64_t now_ns){
	if(!EnableFCS){//如果未启用QLA
		return;
	}
	
	auto& fcs = GetFcsState(port,queue);
	double Tfcs_ns = GetTFCS(
		// GetPortRTT_ns(port)
		maxRtt
	);

	// 如果重置时间为零，说明第一次开始
	if(fcs.last_reset_ns==0){
		fcs.last_reset_ns = now_ns;
	}

	double timeDistance = now_ns - fcs.last_reset_ns;

	if (timeDistance > Tfcs_ns) {//间隔超过一周期？
		//计算超过周期数
		uint32_t passedCycles = timeDistance/Tfcs_ns;//直接除法计算

		fcs.interval_seq += passedCycles;

        fcs.last_reset_ns = now_ns;
        // fcs.n_last = fcs.n_current;
		if(passedCycles>1){
			//跳过多个周期，那么这几个周期的n current都是0，因为没有流量，直接nlast=0
			fcs.n_last=0;		
		}else if(passedCycles==1){
			//过了一个周期
			fcs.n_last=fcs.n_current;
		}

		//计算f(N)
		fcs.CalcFn();

		fcs.n_current = 0;	

        //位图清零
		std::fill(fcs.bitmap.begin(), fcs.bitmap.end(), 0ULL);
    }

	//正常新流检测（如果有包到达）
    uint32_t sid = fingerprint & ((1 << fcs.INDEX_SIZE) - 1);//对2^INDEX_SIZE取余数，得到位图id

	//怎么存哈希

    uint64_t hold = fcs.bitmap[sid];//获取当前sid槽位的值
    fcs.bitmap[sid] = fingerprint;//先写入
    if (fingerprint != hold) {//不一致判定为新流量
        fcs.n_current++;
    }
	//此处不考虑哈希冲突的解决

	std::cout<<now_ns<<" PRED->FCS[port:"<<port<<"][queue:"<<queue<<"]: "//<<std::endl;//流数（应该是fcs）
	/*std::cout*/<<"	Tfcs: "<<Tfcs_ns
	<<" N: "<<fcs.n_current<<std::endl;
}

// YRNK_METHOD
//更新QLA，时间驱动
void SwitchMmu::UpdateQlaStatsDrivenByTime(
	uint32_t port, 
	uint32_t queue, /*uint32_t pktSize, uint32_t curQlenPkts, */
	uint64_t now_ns/*, uint64_t rtt_ns*/){
	if(!EnableQLA){//如果未启用QLA
		return;
	}


	auto& qla = GetQlaState(port,queue);
	double Tqla_ns = GetTQLA(
		// GetPortRTT_ns(port)
		maxRtt
	);
	Time Tqla_time = NanoSeconds(Tqla_ns);
	double utility;

	//第一次开始时
	if(qla.phase_start_ns == 0){
		qla.InitFirstStart(now_ns);
		Simulator::Schedule(
				Tqla_time, 
				&SwitchMmu::UpdateQlaStatsDrivenByTime, 
				this,
				port,
				queue, 
				Simulator::Now().GetNanoSeconds()+Tqla_ns
		);
		return;//直接返回，等待下一个周期
	}

	// double cycleTimeDistance = now_ns - qla.phase_start_ns;
	// while(cycleTimeDistance >= Tqla_ns){
		//距离周期开始时间超过一个周期
		qla.phase_start_ns += Tqla_ns;//启动时间推进一个周期
		//计算效用值
		if (qla.phase_qlen_cnt > 0) {
			utility=qla.UtilityFunction(
					qla.getAvgThroughputByTqlaNs(Tqla_ns),
					bandwidth[port],
					qla.getAvgQ()
				);
			qla.setUtility(
				utility
			);
		}else{
			//输出日志
			// std::cout<<now_ns<<" [ATTENTION][PRED]: qla.phase_qlen_cnt <= 0, utility calculation was canceled."<<std::endl;
			// std::cout<<"tqla_ns "<<Tqla_ns<<" cycleTimeDistance "<<cycleTimeDistance<<std::endl;
		}

		qla.doPhaseWork(
			GetFcsState(port,queue)
		);

	// 	cycleTimeDistance = now_ns - qla.phase_start_ns;
	// }

	std::cout<<now_ns<<" PRED->QLA[port:"<<port<<"][queue:"<<queue<<"]: "//<<std::endl;//lambda，效用值，流数（应该是fcs）
	/*std::cout*/<<"	Tqla: "<<Tqla_ns
	<<" lambda_current: "<<qla.lambda_current
	<<" lambda_base: "<<qla.lambda_base
	<<" mink: "<<qla.minK
	<<" maxk: "<<qla.maxK
	<<" utility: "<<utility
	<<std::endl;

	Simulator::Schedule(
		Tqla_time,
		&SwitchMmu::UpdateQlaStatsDrivenByTime, 
		this,
		port,
		queue, 
		Simulator::Now().GetNanoSeconds()+Tqla_ns
		);
}

// 每包到达时调用，仅累加统计量，不做周期判断
void SwitchMmu::RecordQlaPacketStats(uint32_t port, uint32_t queue,
                                  /*uint32_t pktSize,*/ uint32_t curQlenPkts) {
	if(!EnableQLA){//如果未启用QLA
		return;
	}

    auto& qla = GetQlaState(port, queue);
    // qla.phase_tx_bytes += pktSize;
    qla.phase_qlen_sum += curQlenPkts;
    qla.phase_qlen_cnt++;
}

// QLA出队字节数统计
void SwitchMmu::RecordQlaDequeueBytes(uint32_t port, uint32_t queue, uint32_t pktSize) {
	if(!EnableQLA){//如果未启用QLA
		return;
	}
	
	auto& qla = GetQlaState(port, queue);
	qla.phase_tx_bytes += pktSize;
}

void SwitchMmu::StartAllQlaTimers() {
	if(!EnableQLA){//如果未启用QLA
		return;
	}

    for (uint32_t port = 0; port < pCnt; ++port) {
        for (uint32_t queue = 0; queue < qCnt; ++queue) {
            Simulator::Schedule(
                NanoSeconds(GetTQLA(
					// GetPortRTT_ns(port)
					maxRtt
				)),
                &SwitchMmu::UpdateQlaStatsDrivenByTime,
                this,
                port,
                queue,
                Simulator::Now().GetNanoSeconds()
            );
        }
    }
}

void SwitchMmu::StartQlaTimerOfPort(uint32_t port){
	if(!EnableQLA){//如果未启用QLA
		return;
	}

	std::cout<<"StartQlaTimerOfPort "<<port<<std::endl;
	for (uint32_t queue = 0; queue < qCnt; ++queue) {
		Simulator::Schedule(
			NanoSeconds(GetTQLA(
				// GetPortRTT_ns(port)
				maxRtt
			)),
			&SwitchMmu::UpdateQlaStatsDrivenByTime,
			this,
			port,
			queue,
			Simulator::Now().GetNanoSeconds()
		);
	}
}

void SwitchMmu::StartQlaTimer(uint32_t port, uint32_t queue){
	if(!EnableQLA){//如果未启用QLA
		return;
	}

	std::cout<<"StartQlaTimer "<<port<<" "<<queue<<std::endl;
	Simulator::Schedule(
		NanoSeconds(GetTQLA(
			// GetPortRTT_ns(port)
			maxRtt
		)),
		&SwitchMmu::UpdateQlaStatsDrivenByTime,
		this,
		port,
		queue,
		Simulator::Now().GetNanoSeconds()
	);
}

// // YRNK_METHOD
// //已禁用
// //更新QLA
// void SwitchMmu::UpdateQlaStats(uint32_t port, uint32_t queue, uint32_t pktSize, uint32_t curQlenPkts, uint64_t now_ns/*, uint64_t rtt_ns*/){
// 	auto& qla = GetQlaState(port,queue);
// 	double Tqla_ns = GetTQLA(
// 		GetPortRTT_ns(port)
// 	);

// 		//第一次开始时
// 	if(qla.phase_start_ns == 0){
// 		qla.InitFirstStart(now_ns);
//         // qla.lambda_base = qla.lambda_base;
// 	}

// 	// double updateTimeDistance = now_ns - qla.last_update_ns;
// 	// if(updateTimeDistance >= Tqla_ns){
// 	// 	//距离上次更新超过qla周期，或者说一个相位，就直接重置当前QLA循环
// 	// 	qla.phase_start_ns = now_ns;
// 	// 	qla.last_update_ns = now_ns;
// 	// 	return;
// 	// }

// 	double cycleTimeDistance = now_ns - qla.phase_start_ns;
// 	while(cycleTimeDistance >= Tqla_ns){
// 		//距离周期开始时间超过一个周期
// 		qla.phase_start_ns += Tqla_ns;//启动时间推进一个周期
// 		//计算效用值
// 		if (qla.phase_qlen_cnt > 0) {
// 			qla.setUtility(
// 				qla.UtilityFunction(
// 					qla.getAvgThroughputByTqlaNs(Tqla_ns),
// 					bandwidth[port],
// 					qla.getAvgQ()
// 				)
// 			);
// 		}else{
// 			//输出日志
// 			// std::cout<<"[ATTENTION][PRED]: qla.phase_qlen_cnt <= 0, utility calculation was canceled."<<std::endl;
// 		}

// 		/*
// 			执行相位操作：
// 				相位自增
// 				如果相位为0，则启用决策器进行AI操作，同时从fcs获取fn进行MD操作
// 				操作相位对应的lambda加减
// 				自动管理lambda溢出问题：
// 					调用mink调整器
// 				清理相位信息
// 		*/
// 		qla.doPhaseWork(
// 			GetFcsState(port,queue)
// 		);

// 		cycleTimeDistance = now_ns - qla.phase_start_ns;
// 	}

// 	//数据的更新
// 	qla.phase_tx_bytes += pktSize;
//     qla.phase_qlen_sum += curQlenPkts;
//     qla.phase_qlen_cnt++;

// 	// qla.IncreasePhase();

// 	//上次更新时间
// 	qla.last_update_ns = now_ns;
// }

}
