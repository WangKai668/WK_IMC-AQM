
# ns3-datacenter

**V1.0 Release**

We extend ns-3.39 to support some of the recent advancements in the datacenter context.
- Various datacenter congestion control algorithms including PowerTCP over both TCP/IP and RDMA stacks can be used simulataneously. 
- The switch MMU is based on SONIC buffer model (purely based on our understanding only). The switch MMU can also be configured based on Reverie model. 
- Support for several Buffer Management algorithms including ABM, Reverie and Credence.
- Integration with pybind11 enables interesting applications such as obtaining predictions from a scikit-learn trained model (see Credence examples).

Previous versions of the repository can be found here: [Releases](https://github.com/inet-tub/ns3-datacenter/releases/)

Many additions to the source code are based on prior work: [ns3-rdma](https://github.com/bobzhuyb/ns3-rdma) and [HPCC](https://github.com/alibaba-edu/High-Precision-Congestion-Control). Please consider citing the following papers if you use this repository in your research.


# Configure and Build

In the following, `$REPO` = path to the root directory of this repository. Change $REPO accordingly.

**Configure ns3:**

```bash
cd $REPO/simulator/ns-3.39/
./configure.sh
```
**Build:**

```bash
cd $REPO/simulator/ns-3.39/
./waf
```


# Important Files

[`simulator/ns-3.39/src/point-to-point/model/qbb-net-device.cc`](https://github.com/inet-tub/ns3-datacenter/tree/master/simulator/ns-3.39/src/point-to-point/model/qbb-net-device.cc): This file is modified such that it can send and receive both RDMA and TCP/IP traffic. Note: only bulk-send-application and packet-sink should be used for TCP/IP traffic for correctness. Some examples on how to launch RDMA traffic can be found in [`simulator/ns-3.39/examples/PowerTCP`](https://github.com/inet-tub/ns3-datacenter/tree/master/simulator/ns-3.39/examples/PowerTCP) folder.

[`simulator/ns-3.39/src/point-to-point/model/rdma-hw.cc`](https://github.com/inet-tub/ns3-datacenter/tree/master/simulator/ns-3.39/src/point-to-point/model/rdma-hw.cc): The entire file is almost same as the one in HPCC simulator.

[`simulator/ns-3.39/src/point-to-point/model/switch-node.cc`](https://github.com/inet-tub/ns3-datacenter/tree/master/simulator/ns-3.39/src/point-to-point/model/switch-node.cc): This file is also modified to support both RDMA and TCP/IP traffic. Minor change in INT, for PowerTCP, RXBytes is appended instead of TxBytes. This is since $\lambda(t)=\mu(t)+\dot{q}(t) $ i.e., RxRate is TxRate + Queue gradient where $\lambda(t)$ is required for PowerTCP to calculate power.

[`simulator/ns-3.39/src/point-to-point/model/switch-mmu.cc`](https://github.com/inet-tub/ns3-datacenter/tree/master/simulator/ns-3.39/src/point-to-point/model/switch-mmu.cc): This file has the core logic for buffer management. Currently, we only support Dynamic Thresholds (DT) and Active Buffer Management (ABM). Note: The SIGCOMM version of ABM paper uses the implementation in traffic control layer (see below).

[`simulator/ns-3.39/src/traffic-control/model/gen-queue-disc.cc`](https://github.com/inet-tub/ns3-datacenter/tree/master/simulator/ns-3.39/src/traffic-control/model/gen-queue-disc.cc): This file contains various buffer management algorithms at the traffic-control layer. It can only be used in the TCP/IP stack. Note: This is what we used for ABM in the paper.

[`simulator/ns-3.39/src/internet/model/tcp-advanced.cc`](https://github.com/inet-tub/ns3-datacenter/tree/master/simulator/ns-3.39/src/internet/model/tcp-advanced.cc): This file contains various datacenter congestion control algorithms including PowerTCP implemented in the TCP/IP stack. This is what we used for ABM in the paper.