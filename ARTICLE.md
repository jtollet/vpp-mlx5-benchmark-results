# Optimizing VPP Packet Forwarding on NVIDIA ConnectX NICs and BlueField DPUs

*A tuned RDMA-DV, DPDK and AF_XDP comparison from ConnectX-4 to ConnectX-6 Dx
and BlueField-3.*

NVIDIA ConnectX adapters — still widely known by the Mellanox name — are
common in routers, clouds and storage systems, while BlueField extends the
same lineage into SmartNICs and DPUs. Their prominence has accelerated with
AI infrastructure: GPU clusters need high-bandwidth, low-latency network and
storage fabrics, and DPUs can move infrastructure work away from expensive
host CPU cores
([NVIDIA BlueField-3 platform guide](https://networking-docs.nvidia.com/bf3dpu/introduction)).

This article does **not** benchmark an AI collective, a RoCE endpoint or a
storage endpoint. Its workload is packet forwarding: a small-packet IPv4
datapath representative of routers, gateways and infrastructure services that
surround those endpoints. Using this hardware efficiently from VPP presents a
less obvious choice. The same NIC or DPU port can be driven through VPP's
native RDMA plugin, through the DPDK mlx5 PMD, or through Linux AF_XDP.

All three are valid engineering choices. They differ in integration model,
tuning controls and CPU accounting. This study asks a practical question:
**what is the best 64-byte L3 forwarding performance we can obtain from each
combination after tuning it for its hardware, with one and two VPP workers?**

The answer is not a single universal configuration. Queue count, descriptor
depth, CQE compression, buffer geometry and TX batching all interact with the
NIC generation and CPU. Defaults were only starting points.

## Three paths to the same NIC

**Native RDMA-DV** uses VPP buffers and the mlx5 direct-verbs interface exposed
by rdma-core. It is the shortest of the three software paths considered here.
Despite the plugin name, the test carries ordinary Ethernet/IP traffic through
a raw-packet QP; it is not an RDMA or RoCE endpoint benchmark.

**VPP/DPDK** uses VPP's DPDK plugin and the mature mlx5 poll-mode driver. It
offers a broad, portable device framework and a rich set of mlx5 controls:
vector receive, CQE compression, MPRQ, inline thresholds, enhanced MPW and
mbuf fast-free among them.

**VPP/AF_XDP** uses Linux XDP sockets and the kernel mlx5 driver. Native
zero-copy avoids copying frame payload between the NIC and userspace, but the
kernel still performs NAPI, ring and ownership work. That kernel CPU time must
be measured; counting only the VPP worker makes AF_XDP look artificially
cheap. The Linux documentation describes the XSK RX/TX/UMEM model and the
flag used to verify native zero-copy
([Linux AF_XDP documentation](https://docs.kernel.org/networking/af_xdp.html)).

VPP exposes all three as plugins. Its current feature list describes AF_XDP as
experimental, while the native RDMA driver is a production feature
([VPP supported features](https://docs.fd.io/vpp/25.06/aboutvpp/featurelist.html)).

## A best-found-configuration study

The DUT workload is deliberately small and demanding: 64-byte IPv4/UDP
frames, real IPv4 lookup, TTL decrement, checksum update, adjacency rewrite
and physical retransmission. An external packet generator supplied more
traffic than the DUT could forward. Within each hardware platform, the same
generator, flows and offered load were used for every driver.

Each retained value is normally the mean of three 20-second windows.
Throughput comes from the NIC's successful physical TX counter, not VPP's
software TX-attempt counter. PAUSE/PFC remained disabled, all configured RX
queues were proven active, and RSS balance was checked from per-queue and
per-worker deltas.

The platforms were chosen to represent where these NICs are commonly found:

- ConnectX-4 and ConnectX-5 ran on the same Intel Xeon Gold 6146 Skylake CPU,
  making their results the closest generational comparison in the set.
- ConnectX-6 Dx ran on a newer Xeon Platinum 8562Y+ Sapphire Rapids host with
  PCIe 4, so the modern NIC was not paired with an obviously obsolete CPU.
- BlueField-3 ran VPP on its embedded Arm Cortex-A78AE cores. It represents
  on-DPU execution, not a head-to-head host CPU comparison.

This distinction matters: Mpps describes a complete platform. Cycles per
packet is the better metric for comparing software efficiency across CPUs.

![Tuned throughput with one and two workers](https://raw.githubusercontent.com/jtollet/vpp-mlx5-benchmark-results/main/charts/throughput-scaling.png)

## Results

The table below uses the same CPU budget for each driver: one or two dataplane
CPUs. These labels count VPP workers, not the always-present VPP main thread;
the main thread was measured separately. For AF_XDP, mlx5 IRQ/NAPI is
colocated with the VPP workers and included in the cycles column. A separate
maximum-AF control is discussed below. For readability, throughput is rounded
to 0.1 Mpps and cycles per packet to the nearest cycle; the public CSV retains
the measured precision.

| Hardware | Driver | 1 worker Mpps / cycles-pkt | 2 workers Mpps / cycles-pkt | 1→2 scaling |
|---|---|---:|---:|---:|
| ConnectX-4 | RDMA-DV | 16.1 / 205 | 30.0 / 219 | 1.9× |
|  | DPDK mlx5 | **16.4 / 201** | **30.4 / 216** | 1.9× |
|  | AF_XDP ZC, strict | 3.0 / 1,099 | 3.8 / 1,747 | 1.3× |
| ConnectX-5 | RDMA-DV + eMPW | **23.7 / 131** | **43.5 / 142** | 1.8× |
|  | DPDK mlx5 | 18.2 / 170 | 35.6 / 173 | 2.0× |
|  | AF_XDP ZC, strict | 4.8 / 646 | 9.0 / 689 | 1.9× |
| ConnectX-6 Dx | RDMA-DV + eMPW | **46.3 / 89** | 47.6 / 171 | 1.0× |
|  | DPDK mlx5 | 36.9 / 111 | **47.7 / 171** | 1.3× |
|  | AF_XDP ZC, strict | 9.0 / 455 | 13.1 / 625 | 1.5× |
| BlueField-3 | RDMA-DV + eMPW | **14.6 / 136** | **26.9 / 149** | 1.8× |
|  | DPDK mlx5 | 10.3 / 193 | 21.2 / 189 | 2.1× |

AF_XDP was scoped to the discrete ConnectX adapters and was not measured on
BlueField-3. That is a study-scope decision, not a claim that AF_XDP zero-copy
is impossible on the DPU. A publishable BlueField result would require the
same independent checks used on the host NICs: proof that every XSK is
actually in zero-copy mode, inclusion of IRQ/NAPI CPU consumption, and
validation of the candidate mlx5 ownership fix on that kernel and driver.

The cycles/packet values above cover the dataplane workers. For strict AF_XDP
they include kernel work on those CPUs. VPP also has a main core: at two
workers it added roughly 0.7–4.7 cycles per packet to RDMA/DPDK depending on
the platform. It was lightly loaded, but it is not hidden from the public
dataset. In every two-worker row, cycles per packet is the sum of the two
worker counters divided by successful physical TX packets; it is not a
per-worker value.

The comparison is intentionally factual rather than a verdict against a
framework. Tuned DPDK is the fastest path on ConnectX-4 and is effectively
tied with native RDMA on ConnectX-6 Dx at two workers. Native RDMA leads on
ConnectX-5 and BlueField-3. On the CX6 two-worker run, DPDK's 0.3% higher raw
mean retained a small PMD RX-miss rate; the native 47.6 Mpps point was clean.

### Why the paths differ

The instruction counters give the strongest driver-level evidence. With two
workers on CX5, native RDMA executes 332 instructions per successful packet
versus 457 for tuned DPDK, a 27% reduction. On BlueField-3 the figures are 350
versus 459, a 24% reduction. Both DPDK runs were confirmed on vector RX and
the `mlx5_tx_burst_sc_empw` enhanced-MPW transmit function, while native eMPW
was active too. This is therefore not an eMPW-versus-legacy-SEND comparison.

The VPP source explains why an instruction delta is plausible. The DPDK input
node converts PMD-provided `rte_mbuf` metadata into `vlib_buffer_t` metadata,
and its output node prepares mbuf state before entering the generic ethdev/PMD
path. The native plugin receives directly into VPP buffers and consumes CQEs
or writes WQEs without that framework boundary
([DPDK input](https://github.com/FDio/vpp/blob/master/src/plugins/dpdk/device/node.c),
[DPDK output](https://github.com/FDio/vpp/blob/master/src/plugins/dpdk/device/device.c),
[native RX](https://github.com/FDio/vpp/blob/master/src/plugins/rdma/input.c),
[native TX](https://github.com/FDio/vpp/blob/master/src/plugins/rdma/output.c)).
This is an architectural explanation, not a claim that every extra instruction
has been individually assigned to DPDK.

The counterexamples are equally important. DPDK wins CX4 because its mature
CX4 vector/MPW path slightly outperforms native legacy SEND. On CX6 with two
workers, the stacks converge near 47.6 Mpps and 171 aggregate worker cycles
per successful packet. That number is a symptom of the missing scaling, not
its cause: both poll-mode workers keep running while the successful packet
rate barely changes. A CX6 one-worker profile
assigned about 34.6% of CPU samples to generic IPv4 lookup/rewrite, compared
with 14.4% to native RX, 10.1% to eMPW preparation and 6.7% to TX
completion/free. Those numbers bound how much a driver-only optimization can
improve this particular graph.

AF_XDP can trade more CPUs for more throughput. With two VPP workers and two
additional IRQ/NAPI CPUs it reached 11.7, 11.8 and 21.0 Mpps on CX4, CX5
and CX6 respectively. Its all-dataplane cost was approximately 1,229, 1,127
and 767 cycles per packet before the small main-thread addition. Those rows
are useful maximums, but they are not the same CPU budget as two poll-mode
workers.

![Scaling from one to two workers](https://raw.githubusercontent.com/jtollet/vpp-mlx5-benchmark-results/main/charts/worker-scaling.png)

## How to interpret cycles per packet

Cycles per packet is the counted worker cycles divided by successfully
forwarded physical packets:

```text
cycles/packet × packets/second = counted worker cycles/second
```

For a poll-mode worker this identity must be handled carefully. The worker
continues spinning when a queue is empty, so reconstructing its clock rate is
an accounting check, not by itself proof of useful saturation. Cycles per
packet includes productive graph work, empty polling, stalls and retries. It
becomes explanatory only when combined with offered load, physical losses,
queue balance and vector sizes.

Under ideal two-worker scaling, the available worker cycles double, useful
cycles per packet stay roughly constant and throughput nearly doubles. The
VPP main thread remains an additional core even when lightly loaded, so its
cost is reported separately rather than folded into either worker.

![Counted poll-mode CPU cycles per second reconstructed from cycles and Mpps](https://raw.githubusercontent.com/jtollet/vpp-mlx5-benchmark-results/main/charts/cpu-budget.png)

The CX6 is the interesting exception in the scaling chart. One native worker
forwards 46.3 Mpps at 89 counted cycles per packet with roughly 60 Mpps
offered. Two balanced workers should therefore approach twice that rate if
they retain the same batching efficiency. Instead, they forward only 47.6
Mpps and the aggregate counter reports 171 worker cycles per successful
packet. The second worker's cycle budget is being consumed without a
corresponding increase in successful forwarding. The main thread adds only
about 0.7 cycle per packet, making the all-in value about 172 cycles per
packet; it consumes less than 1% of its 4.1 GHz core and does not explain the
plateau.

The physical link is not the explanation. The active CX6 port negotiated
100 Gb/s full duplex, so receive and transmit do not share one 100 Gb/s
budget. A minimum Ethernet frame occupies 84 bytes of link time: 64 bytes
including the frame check sequence, plus 8 bytes of preamble and start-frame
delimiter and a 12-byte inter-packet gap.
The resulting per-direction ceiling is about 149 Mpps. Forwarding 47.6 Mpps
therefore consumes only about 32 Gb/s of serialized link capacity in each
direction. As an independent hardware control, NVIDIA's DPDK 25.03 report
reaches 148.8 Mpps at zero loss on one 100 Gb/s ConnectX-6 Dx port using 12
L3-forwarding cores. That is not a software comparison with our VPP test, but
it confirms that neither the port nor the NIC has an inherent 48-Mpps limit
([NVIDIA DPDK 25.03 performance report](https://fast.dpdk.org/doc/perf/DPDK_25_03_NVIDIA_NIC_performance_report.pdf)).

Nor is the injector the limit. During overloaded controls the DUT's physical
counter received 87–99 Mpps while VPP forwarded 46–51 Mpps; the excess became
RX-buffer discards because the worker could not drain it. All four RX queues
advanced with an approximately equal share. Measured PCIe ingress was only
3.3 GiB/s on the negotiated PCIe Gen4 x16 link, and PAUSE remained zero.

The artifacts show where much of that efficiency goes. With one native worker,
one `rdma-input` invocation collects about 1,013 packets across four queues and
the downstream L3 vectors are approximately 256 packets. With two workers and
the same total of four balanced queues, each worker receives only about 3.5
packets per `rdma-input` call and its L3 vectors average about 67 packets. The
two-worker DPDK result shows the same downstream effect: roughly 12 packets per
input call and 69-packet L3 vectors. Fixed polling and graph-dispatch work is
therefore amortized over much smaller batches.

This measured batching collapse accounts for a substantial part of why the
extra worker cycles do not translate into proportional L3 throughput. It is
not evidence of a shared TX queue: each worker has its own TX queue/QP, packet
and cycle balance is within 1%, and lock sampling is negligible. The profile
does not assign every lost cycle to one instruction, so the result should be
described as a VPP polling/batching and graph-scheduling limit in this setup,
rather than as a fully isolated CX6 hardware defect.

Overload screens did briefly reach roughly 51–52 Mpps physical TX, but only
with RX loss or `no free tx slots`; they were excluded from the clean sustained
results. Those TX-slot events establish a second boundary in the current
descriptor/completion lifecycle under overload, but do not prove whether its
root is completion cadence, doorbell batching or another TX scheduling detail.
The reported approximately 48 Mpps is therefore the clean point for this VPP
L3 graph and queue schedule, not the physical-link or ConnectX-6 hardware
limit.

## What was tuned

The full sweep is published with the data, but several lessons generalize:

- **Native mode was explicit.** The plugin also provides a generic
  libibverbs (`ibv`) compatibility path and an automatic selection mode. As
  this is a peak-performance study of mlx5 hardware, every native result used
  `mode dv`; the article does not compare DV with IBV.
- **Queue count is not worker count.** CX6 native needed four RX queues for
  one worker and four for two workers. CX5 and BlueField generally preferred
  one queue per worker. More queues can improve batching, or waste cycles
  polling short and empty CQs.
- **Descriptor depth is generation-specific.** The winners range from RXD
  256 to 4096 and TXD 256 to 8192. Making every ring larger was frequently
  slower.
- **CQE compression is not universally “on”.** It helped several cases and
  the CX6 `AGGRESSIVE` firmware policy improved the native path, but the best
  two-worker CX5 DPDK result disabled PMD CQE compression.
- **Buffer geometry matters.** Pool size and data size changed cache footprint
  and descriptor pressure. BlueField-3 preferred 1600-byte data buffers;
  CX6 native preferred 1664.
- **RSS must match the traffic.** Explicit `ipv4-udp` selection and a
  Toeplitz-balanced flow population fixed misleading multi-queue results.
- **TX queue ownership matters.** Where necessary, we allocated a separate TX
  queue to main and one unshared queue per worker.
- **DPDK-specific controls matter.** Vector RX, MPRQ, inline threshold,
  enhanced MPW and mbuf fast-free were A/B tested. Fast-free helped CX5/BF3
  but was slower on CX4. The official mlx5 guide likewise treats CQE
  compression, NUMA placement and inline parameters as empirical tuning
  choices ([DPDK mlx5 guide](https://doc.dpdk.org/guides/nics/mlx5.html)).
- **AF_XDP is a two-sided datapath.** XSK ring sizes, UMEM size, syscall lock,
  coalescing and IRQ placement were all relevant. Deep rings and more buffers
  did not monotonically improve its overload behavior.

Representative A/B values, including the DPDK vector/scalar, CQE-compression,
MPRQ and fast-free controls, are available in
[`TUNING_EVIDENCE.md`](https://github.com/jtollet/vpp-mlx5-benchmark-results/blob/main/TUNING_EVIDENCE.md).
This is why the results are
described as “best found in the documented sweep,” rather than as defaults or
as a mathematically proven global optimum.

## Two issues uncovered by the work

First, sustained AF_XDP zero-copy overload exposed evidence consistent with
an mlx5 buffer ownership/recycling bug after the XSK RX ring returned
`-ENOBUFS`. A standalone libxsk reproducer showed the same pattern without
VPP. A minimal candidate fix eliminated corruption across heavy stress on
two kernel branches and multiple ConnectX generations. Kernel maintainer
review is still pending, so every AF_XDP number here uses the candidate fix
and is labelled accordingly; this is not an upstream bug-fix claim.

Second, the native RDMA driver needed eMPW to use the newer transmit hardware
efficiently. The proposed VPP change packs compatible packets into one WQE,
while falling back safely to the existing SEND path for incompatible packets. ConnectX-5,
ConnectX-6 Dx and BlueField-3 exercise that path; ConnectX-4 advertises no
enhanced-MPW capability and remains on legacy SEND. The implementation is
currently under review as
[VPP change 46465](https://gerrit.fd.io/r/c/vpp/+/46465), so the results are a
preview of review code rather than a released-version claim.

For completeness, the tested VPP review chain contains four public changes:

- [45505](https://gerrit.fd.io/r/c/vpp/+/45505): the parent TX/WQE-accounting
  change on which the eMPW series is based; its offload feature is not
  exercised by UDP64.
- [46155](https://gerrit.fd.io/r/c/vpp/+/46155): correct verbs-port selection,
  a setup/correctness fix rather than a dataplane optimization.
- [46465](https://gerrit.fd.io/r/c/vpp/+/46465): eMPW, material to the native
  CX5/CX6/BF3 results.
- [46506](https://gerrit.fd.io/r/c/vpp/+/46506): RX CQ doorbell byte order,
  independently validated but absent from the retained figures and measured
  as performance-neutral.

## Takeaways

There is no single “mlx5 tuning profile.” The best settings differ by NIC,
CPU, driver and worker count. The durable method is to measure physical
throughput, verify queue balance, count every CPU that participates, and sweep
the small set of controls that alter batching and memory traffic.

Native RDMA-DV has a real efficiency advantage on ConnectX-5 and BlueField-3
in this workload, while tuned DPDK remains highly competitive and wins some
platform points. AF_XDP offers a Linux-native integration model, but its
kernel work must be included and its current mlx5 zero-copy ownership issue
must be resolved before these experimental results can be generalized.

Most importantly, cycles per packet must be read together with batching and
loss counters. For a saturated poll-mode thread, reducing useful work per
packet can translate into more throughput; for an under-filled or stalled
poller, the same counter also includes cycles which produced no packet. More
effective workers require balanced queues *and* useful vectors, not merely a
second spinning core or a larger descriptor ring.

The complete anonymized data, winning configurations, methodology and chart
source are available at
[github.com/jtollet/vpp-mlx5-benchmark-results](https://github.com/jtollet/vpp-mlx5-benchmark-results).

## Glossary

- **AF_XDP:** Linux address family for high-speed packet I/O between an XDP
  program and user space through XSK sockets.
- **CQ / CQE:** Completion queue / completion queue entry. The NIC uses CQEs
  to report completed receive and transmit work; CQE compression represents
  several receive completions compactly.
- **ConnectX (CX4, CX5, CX6):** NVIDIA/Mellanox ConnectX NIC generations used
  in this study. CX6 refers here to ConnectX-6 Dx.
- **Cycles per packet:** Counted worker CPU cycles divided by successfully
  forwarded packets. It includes empty polling and stalls; multiplying it by
  packet rate reconstructs the counted CPU budget, not proof of saturation.
- **DPDK:** Data Plane Development Kit, a user-space packet-processing
  framework used by VPP through its DPDK plugin.
- **DPU / BlueField-3 (BF3):** A data processing unit combining Arm CPU cores
  with ConnectX networking hardware. This study runs VPP on the integrated
  BlueField-3 CPU.
- **DUT:** Device under test—the system receiving and forwarding the measured
  traffic.
- **eMPW:** Enhanced multi-packet WQE, an mlx5 transmit mechanism that packs
  several compatible packets into one work request.
- **IBV / DV:** The native VPP plugin's two datapaths. IBV uses the generic
  libibverbs interface as a compatibility path; DV uses mlx5 Direct Verbs.
  An `auto` setting selects between them. All native results in this article
  explicitly use DV.
- **IRQ / NAPI:** The Linux interrupt and network-polling mechanisms that
  perform part of the AF_XDP receive work.
- **L3 forwarding:** IP-layer forwarding. In this test VPP performs IPv4
  lookup and rewrite, including the normal TTL update.
- **Mpps:** Millions of packets per second, measured here from physical NIC
  counters.
- **MPRQ:** Multi-packet receive queue, a DPDK mlx5 receive mode in which one
  receive buffer can hold multiple packets.
- **mbuf fast-free:** A DPDK transmit offload allowing the driver to reclaim
  eligible packet buffers with fewer per-buffer checks.
- **NUMA:** Non-uniform memory access. Keeping workers, NIC queues and memory
  on the same NUMA node avoids remote-memory overhead.
- **PAUSE / PFC:** Ethernet flow-control mechanisms. Their counters were
  checked so that flow control could not be mistaken for datapath capacity.
- **PMD:** Poll-mode driver—the DPDK driver continuously polling NIC queues
  from user space.
- **RDMA-DV:** The DV mode of VPP's native RDMA plugin, giving it direct access
  to mlx5 queue and descriptor formats through rdma-core.
- **RSS / Toeplitz:** Receive-side scaling and its commonly used hash. RSS
  distributes flows over RX queues; balanced input tuples were verified in
  every multi-queue result.
- **RX / TX; RXD / TXD:** Receive / transmit; RXD and TXD are the configured
  receive- and transmit-descriptor ring depths.
- **UDP64:** UDP traffic carried in minimum-size 64-byte Ethernet frames,
  including the frame check sequence.
- **UMEM:** The packet-buffer memory region shared by an AF_XDP application
  and the kernel.
- **VPP:** Vector Packet Processing, FD.io's graph-based user-space network
  dataplane.
- **Vector:** A batch of packets processed together by a VPP graph node. Larger
  useful vectors amortize polling, dispatch and function-call overhead.
- **Worker:** A VPP dataplane thread. VPP also has a low-utilization main
  thread, accounted for separately where relevant.
- **WQE:** Work queue element, the descriptor submitted to an mlx5 hardware
  queue.
- **XDP / XSK / ZC:** eXpress Data Path; AF_XDP socket; zero-copy mode. In ZC
  mode packet buffers are transferred between mlx5, the kernel and user space
  without copying packet contents.
