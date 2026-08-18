# Optimizing VPP Packet Forwarding on NVIDIA ConnectX NICs and BlueField DPUs

*A tuned RDMA-DV, DPDK and AF_XDP comparison from ConnectX-4 to ConnectX-6 Dx
and BlueField-3.*

NVIDIA ConnectX adapters — still widely known by the Mellanox name — are
common in routers, clouds and storage systems, while BlueField extends the
same lineage into SmartNICs and DPUs. Their prominence has accelerated with
AI infrastructure: GPU clusters need high-bandwidth, low-latency network and
storage fabrics, and DPUs can move infrastructure work away from expensive
host CPU cores.

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
For ConnectX-5 and newer hardware, our test tree adds enhanced Multi-Packet
WQE (eMPW), grouping compatible packets into one transmit work queue element.
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
CPUs. For AF_XDP, mlx5 IRQ/NAPI is colocated with the VPP workers and included
in the cycles column. A separate maximum-AF control is discussed below.

| Hardware | Driver | 1 worker Mpps / cycles-pkt | 2 workers Mpps / cycles-pkt | 1→2 scaling |
|---|---|---:|---:|---:|
| ConnectX-4 | RDMA-DV | 16.07 / 204.8 | 29.97 / 218.9 | 1.86× |
|  | DPDK mlx5 | **16.37 / 201.1** | **30.41 / 215.8** | 1.86× |
|  | AF_XDP ZC, strict | 3.00 / 1098.9 | 3.76 / 1746.5 | 1.25× |
| ConnectX-5 | RDMA-DV + eMPW | **23.67 / 130.7** | **43.53 / 141.7** | 1.84× |
|  | DPDK mlx5 | 18.22 / 169.8 | 35.58 / 173.3 | 1.95× |
|  | AF_XDP ZC, strict | 4.79 / 646.3 | 8.95 / 688.7 | 1.87× |
| ConnectX-6 Dx | RDMA-DV + eMPW | **46.27 / 88.6** | 47.58 / 171.4 | 1.03× |
|  | DPDK mlx5 | 36.93 / 111.0 | **47.72 / 171.0** | 1.29× |
|  | AF_XDP ZC, strict | 9.01 / 454.9 | 13.12 / 624.9 | 1.46× |
| BlueField-3 | RDMA-DV + eMPW | **14.64 / 136.4** | **26.93 / 148.6** | 1.84× |
|  | DPDK mlx5 | 10.33 / 193.2 | 21.21 / 188.7 | 2.05× |

The cycles/packet values above cover the dataplane workers. For strict AF_XDP
they include kernel work on those CPUs. VPP also has a main core: at two
workers it added roughly 0.7–4.7 cycles per packet to RDMA/DPDK depending on
the platform. It was lightly loaded, but it is not hidden from the public
dataset.

The comparison is intentionally factual rather than a verdict against a
framework. Tuned DPDK is the fastest path on ConnectX-4 and is effectively
tied with native RDMA on ConnectX-6 Dx at two workers. Native RDMA leads on
ConnectX-5 and BlueField-3. On the CX6 two-worker run, DPDK's 0.29% higher raw
mean retained a small PMD RX-miss rate; the native 47.58 Mpps point was clean.

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
per packet: generic VPP graph work and multi-CQ polling dominate enough to
erase the native advantage seen with one worker. A CX6 one-worker profile
assigned about 34.6% of CPU samples to generic IPv4 lookup/rewrite, compared
with 14.4% to native RX, 10.1% to eMPW preparation and 6.7% to TX
completion/free. Those numbers bound how much a driver-only optimization can
improve this particular graph.

AF_XDP can trade more CPUs for more throughput. With two VPP workers and two
additional IRQ/NAPI CPUs it reached 11.66, 11.81 and 20.95 Mpps on CX4, CX5
and CX6 respectively. Its all-dataplane cost was approximately 1,229, 1,127
and 767 cycles per packet before the small main-thread addition. Those rows
are useful maximums, but they are not the same CPU budget as two poll-mode
workers.

![Scaling from one to two workers](https://raw.githubusercontent.com/jtollet/vpp-mlx5-benchmark-results/main/charts/worker-scaling.png)

## Why cycles per packet predict throughput

Once a worker is saturated, a simple identity becomes extremely useful:

```text
cycles/packet × packets/second ≈ cycles/second available from the worker CPU
```

For example, the CX5 native result is 130.657 cycles/packet × 23.674 Mpps,
or about 3.09 billion cycles/second — the observed worker frequency. The CX6
result is 88.620 × 46.269 Mpps, or about 4.10 GHz. With two workers, the same
calculation reconstructs the sum of their cycle budgets.

This is both a sanity check and a performance model. If the worker remains the
bottleneck, reducing cycles per packet translates almost linearly into more
packets per second. If Mpps stops scaling while CPU capacity remains, another
resource has taken over.

![Measured CPU budget reconstructed from cycles and Mpps](https://raw.githubusercontent.com/jtollet/vpp-mlx5-benchmark-results/main/charts/cpu-budget.png)

The CX6 is the interesting exception in the scaling chart. One native worker
already forwards 46.27 Mpps; two workers reach only 47.58 Mpps. We verified
that the generator could deliver substantially more UDP64 traffic, that RSS
was balanced, and that PCIe Gen4 x16 bandwidth was far from saturated. The
one-worker profile showed a CPU execution ceiling spread across IPv4 lookup,
rewrite, Ethernet/IP input and RDMA RX/TX preparation. With two workers, more
queues also create more short/empty-CQ polling and dispatch work. This is not
a 220-Mpps card-limit measurement: it is the ceiling of this single-port VPP
L3 graph and CPU configuration.

## What was tuned

The full sweep is published with the data, but several lessons generalize:

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

Most importantly, cycles per packet connects the tuning work to an observable
limit. When `cycles/packet × Mpps` reconstructs the CPU frequency, the path to
more throughput is code efficiency or more effective workers — not a larger
descriptor ring chosen in isolation.

The complete anonymized data, winning configurations, methodology and chart
source are available at
[github.com/jtollet/vpp-mlx5-benchmark-results](https://github.com/jtollet/vpp-mlx5-benchmark-results).
