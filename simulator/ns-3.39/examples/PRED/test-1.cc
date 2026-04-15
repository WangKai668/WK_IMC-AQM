#undef PGO_TRAINING
#define PATH_TO_PGO_CONFIG "path_to_pgo_config"

#include <iostream>
#include <fstream>
#include <unordered_map>
#include <time.h>
#include "ns3/core-module.h"
#include "ns3/qbb-helper.h"
#include "ns3/point-to-point-helper.h"
#include "ns3/applications-module.h"
#include "ns3/internet-module.h"
#include "ns3/global-route-manager.h"
#include "ns3/ipv4-static-routing-helper.h"
#include "ns3/packet.h"
#include "ns3/error-model.h"
#include <ns3/rdma.h>
#include <ns3/rdma-client.h>
#include <ns3/rdma-client-helper.h>
#include <ns3/rdma-driver.h>
#include <ns3/sim-setting.h>

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// 将原switch-node.h切换为我所更改的p2p模型的头文件
// #include <ns3/switch-node.h>
#include "/home/wk/Reverie-Platform/ns3-datacenter/simulator/ns-3.39/src/point-to-point/model/switch-node.h"
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

#include <cmath>
#include <fstream>
#include <iostream>
#include <iomanip>
#include <map>
#include <ctime>
#include <set>
#include <string>
#include <unordered_map>
#include <stdlib.h>
#include <unistd.h>
#include <vector>

extern "C"
{
#include "cdf.h"
}

using namespace ns3;
using namespace std;

// 简单的测试回调
void TestEnqueueCallback(uint32_t port, uint32_t queue, Ptr<Packet> p) {
    std::cout << Simulator::Now().GetSeconds()
              << " Enqueue: port=" << port
              << ", queue=" << queue
              << ", size=" << p->GetSize()
              << std::endl;
}

// 在主函数中设置回调
int main() {
    // ... 创建网络拓扑 ...

    // 获取交换机节点
    Ptr<SwitchNode> switchNode = CreateObject<SwitchNode>();

    // 设置入队回调
    switchNode->SetEnqueueCallback(MakeCallback(&TestEnqueueCallback));

    Simulator::Run();
    Simulator::Destroy();
}