# Three VPP datapaths for NVIDIA ConnectX and BlueField at 64 bytes

> **Code provenance.** Some retained rows use disabled-by-default review code.
> Exact revisions and the status of every affected result are published with
> the dataset.

*A best-found-configuration comparison of native RDMA-DV, DPDK mlx5 and
AF_XDP zero-copy for same-port IPv4 forwarding.*

VPP has three practical high-performance options for NVIDIA ConnectX adapters
and BlueField DPUs. The native RDMA plugin accesses mlx5 queues through Direct
Verbs (DV), the DPDK plugin uses the mlx5 PMD, and the AF_XDP plugin uses Linux
zero-copy sockets. This study tunes queue count, descriptor depth, placement
and applicable driver controls independently for each option, then reports
the best qualified results found with physical 64-byte Ethernet frames.

The resulting curves show a consistent native-versus-kernel difference:
**RDMA-DV is faster than AF_XDP at every matched worker count on every measured
adapter.** It forwards 2.3 to 4.6 times as many packets, while AF_XDP consumes 2.3 to
4.5 times as many dataplane-CPU cycles per successful packet. Those cycles
are not estimated: IRQ, NAPI, XDP and XSK work is counted on the same declared
CPUs as VPP.

DPDK is the useful second control because it also polls the NIC from VPP.
Across CX5, CX6 and BF3, RDMA-DV leads tuned DPDK in 14 of 15 paired cells;
the sole exception is CX5 at six workers, by 1.5%. CX4 is effectively a draw.
The underlying transmit mechanisms are examined only after the results.

## What was measured

The DUT routes IPv4/UDP traffic back through the same physical port. Each
packet therefore crosses the complete VPP L3 forwarding path. NIC counters
confirm that all retained results use physical 64-byte Ethernet frames.

| Platform | DUT CPU | Microarchitecture (year) |
|---|---|---|
| ConnectX-4 | Intel Xeon Gold 6146 | Skylake-SP (2017) |
| ConnectX-5 | Intel Xeon Gold 6248R | Cascade Lake Refresh (2020) |
| ConnectX-6 Dx | Intel Xeon Platinum 8562Y+ | Emerald Rapids (2023) |
| BlueField-3 | Integrated Arm Cortex-A78AE | Cortex-A78AE / Armv8.2-A (2020) |

Finals are three independent 20-second windows. Throughput is the DUT's
successful physical TX delta. Main and worker threads use distinct physical
cores, without SMT siblings, and queue ownership and fairness are recorded.

Overloaded points are maximum forwarding rate (MRR), not zero-loss NDR; a `+`
marks a source-limited lower bound. CPU cost is measured CPU cycles divided by
successful physical TX packets. For AF_XDP this includes IRQ, NAPI, XDP and
XSK work on the declared CPUs; no auxiliary packet-service CPU is used.

![True64 throughput across workers](https://raw.githubusercontent.com/jtollet/vpp-mlx5-benchmark-results/50ba36b/charts/throughput-scaling.png)

## What the curves say

The throughput figure carries every retained value, so it is the result
matrix. Across matched cells, RDMA-DV is 3.4--4.4 times faster than AF_XDP
on CX4, 4.4--4.6 times faster on CX5, and 2.3--4.3 times faster on CX6.
AF_XDP was not measured on BF3 by study scope; this is not a capability claim.

DPDK remains fully visible in the same figure. BF3 is the strongest native-
versus-DPDK result: RDMA-DV leads by 38.5%, 29.4%, 31.0%, 16.4% and 22.8% at
one, two, four, five and six workers. CX6 also favors native at every retained
count. The CX5 6W reversal is deliberately left visible: DPDK leads there by
1.5%.

The CPU view uses two workers. For AF_XDP the bars include all kernel execution
on the colocated IRQ/NAPI CPUs. Native needs 134--218 cycles per packet against
381--800 for AF_XDP.

![All-in cycles per successful packet](https://raw.githubusercontent.com/jtollet/vpp-mlx5-benchmark-results/285433e/charts/cpu-budget.png)

Two limits matter when reading the throughput curve. CX4 reaches its measured
43-Mpps traffic-generator ceiling at three poll-mode workers, so those two
points are lower bounds. CX6 RDMA-DV at six workers is likewise source-limited
at 137 Mpps. Neither boundary applies to the AF_XDP points.

## What separates the three datapaths

The native plugin receives directly into VPP buffers and consumes mlx5 CQEs
from the VPP worker. It avoids both the kernel XDP/XSK machinery used by
AF_XDP and the ethdev/`rte_mbuf` boundary used by DPDK. On CX5, CX6 and BF3 it
also groups compatible packets into enhanced Multi-Packet WQEs (eMPW); CX4 is
the legacy-SEND control.

BF3 makes the architectural benefit particularly clear. Native pointer eMPW
is faster than the tuned DPDK PMD at every retained worker count even though
forced full-packet inline hurts native BF3. The win is therefore not created
by choosing a favorable copy policy: the shorter DV path itself matters.

CX4 keeps the comparison honest. Without eMPW, RDMA-DV and DPDK are within
0.6% at one and two workers and both hit the source at three. CX6 is the
opposite control: once both paths use complete-packet eMPW inline, native
overtakes DPDK and continues scaling. **When the hardware exposes the batching
capability, DV gives VPP an unusually efficient fast path without requiring
an ethdev abstraction layer.**

## ConnectX-6: pointer eMPW versus full-packet inline

eMPW groups several small packets in one WQE. Without full-packet inline, each
entry contains an address, key and length; the NIC must then fetch the packet
from its VPP buffer. With full-packet inline, VPP copies the packet bytes into
the WQE and the separate DMA read is avoided.

In the matched four-worker TX-only control, the referenced-buffer form reaches
68.9 Mpps and full-packet inline reaches 145.9 Mpps, or 98% of the Ethernet64
packet-rate ceiling. Retaining the VPP buffer until completion or releasing it
after the copy changes the result only slightly; that distinction is therefore
kept in the data but omitted from the graph.

![CX6 eMPW inline root cause](https://raw.githubusercontent.com/jtollet/vpp-mlx5-benchmark-results/50ba36b/charts/cx6-inline-root-cause.png)

The full L3 tests use one dedicated QP per worker, an inactive main QP and
balanced RX placement. With the corrected placement, RDMA-DV reaches **61,
109, 127 and 137 Mpps** at two, four, five and six workers. The six-worker
point is source-limited. Full-packet inline is enabled from two workers upward;
the exact queue maps, fairness and pressure counters remain in the dataset.

### Full-packet inline remains optional

Full-packet inline improves CX6 small-packet scaling but regresses BF3, so it
remains disabled by default. A device-wide option enables it up to a configured
packet size; the CX6 results from two workers upward use a 60-byte limit. An
unstable adaptive prototype was tested and rejected.

## AF_XDP: zero-copy is not zero CPU

AF_XDP avoids payload copies, but mlx5 IRQ/NAPI, XSK refill/completion rings
and VPP still consume CPU. Counting only the VPP workers would make the result
look much better than the machine-level cost. The retained comparison therefore
counts CPU-wide cycles on exactly the VPP main and worker cores, with every
mlx5 completion IRQ pinned to the thread that owns its queue. No auxiliary
IRQ, NAPI or recycling core is added to AF_XDP's budget.

That stricter topology is slower than RDMA-DV in every matched cell, as the
throughput graph shows. It is also a fairer result than a layout which quietly
adds one IRQ CPU per queue.

On CX4, kernel execution accounts for 75--81% of AF_XDP's measured CPU budget.
RDMA-DV and DPDK poll the queues directly from VPP and avoid this second kernel
datapath.

A device-filtered trace confirms that all observed AF_XDP kernel work ran on
the four declared worker CPUs and is included in the CPU totals.

### What socket busy polling changes

`SO_BUSY_POLL` lets an XSK receive call poll NAPI for a bounded time.
`SO_PREFER_BUSY_POLL` favors that path and `SO_BUSY_POLL_BUDGET` limits one
poll. The following matched CX6 diagnostic counts all CPU cycles, including
kernel work on the four declared workers:

| 4W / 4Q control | Physical TX | All-in cycles / TX packet | Completion IRQs / 8 s |
|---|---:|---:|---:|
| Socket busy poll off | 32 Mpps | 509 | 3.7 million |
| 10 us, prefer, budget 64 + NAPI IRQ defer | **40 Mpps** | **404** | **16** |

On CX6, socket busy polling combined with NAPI IRQ defer raises forwarding
from 32 to 40 Mpps and lowers CPU cost from 509 to 404 cycles per packet.
CX4 is neutral and CX5 shows no gain, so the option remains disabled by
default. It changes where kernel work runs but does not remove it; all cycles
remain counted. Support is under review in
[Gerrit 46539](https://gerrit.fd.io/r/c/vpp/+/46539).

## This study uncovered an mlx5 AF_XDP kernel bug

While producing these results, `RX_FULL` stress uncovered a silent mlx5e
buffer-ownership bug. After a partial XSK refill, a WQE could retain a stale
pointer and release the same UMEM frame twice. Both cyclic and MPWQE receive
paths were affected, without producing a kernel warning.

The proposed fixes make buffer release safe across refill retries. The cyclic
reproducer failed after 2.9 million packets on the stock kernel, then processed
356.9 million without an ownership error after the fix; an injected-failure
test also validated the MPWQE change. The two-patch
[`v3 series`](https://lore.kernel.org/netdev/cover.1787347981.git.jtollet@cisco.com/)
is currently under review on `netdev` and is not yet upstream.

## What tuning did—and did not—change

Descriptor depth must be tuned rather than maximized. Allowing RXD128 raises
native CX5 throughput to 62 Mpps at four workers and 65 Mpps at five; CX4 also
reaches near parity with DPDK at that depth, while RXD64 regresses.

On CX6, `BALANCED` and `AGGRESSIVE` change batching behavior but differ by less
than 0.5% in matched throughput. Larger vectors therefore do not necessarily
mean higher packet rate.

## Takeaways

1. **RDMA-DV is the strongest efficiency result.** It leads 14 of 15 paired
   eMPW-capable cells; the one exception is CX5 6W at -1.5% throughput.
2. **eMPW is a structural datapath choice, not a minor tuning option.** By
   packing several small packets into one WQE, it changes TX efficiency and
   scaling on CX5, CX6 and BF3; CX4's legacy SEND path is the counterexample.
3. **AF_XDP's kernel work must be counted.** Zero-copy is valuable, but in this
   forwarding workload it costs far more all-in CPU and achieves less
   throughput than RDMA-DV.
4. **Pressure counters define the claim.** Maximum forwarding, source-limited
   lower bounds and zero-loss NDR are different results and stay labelled as
   such.

The exact result CSV, the [`CX6 inline causal A/B`](data/cx6-inline-causal.csv), the
[`BF3 inline controls`](data/bf3-inline-controls.csv), placement ledger,
methodology, tuning evidence, submitted kernel patch and figure sources are
available in the companion repository.
The frozen VPP tree includes the merged RX CQ doorbell fix and the reviewed
changes tracked in [`VPP_CHANGES.md`](VPP_CHANGES.md); the native eMPW change
remains review code in [Gerrit 46465](https://gerrit.fd.io/r/c/vpp/+/46465),
with full-packet inline in [46540](https://gerrit.fd.io/r/c/vpp/+/46540),
optional AF_XDP busy polling in
[46539](https://gerrit.fd.io/r/c/vpp/+/46539) and the `W+1` refill fix in
[46547](https://gerrit.fd.io/r/c/vpp/+/46547).

## Glossary

- **AF_XDP / XSK / ZC:** Linux XDP socket interface / one XDP socket / native
  zero-copy mode.
- **CQ / CQE:** hardware completion queue / one completion entry.
- **DPDK / PMD:** Data Plane Development Kit / poll-mode device driver.
- **eMPW / WQE:** enhanced multi-packet work-queue format / one NIC work-queue
  element.
- **IBV / DV / RDMA-DV:** generic libibverbs interface / mlx5 Direct Verbs /
  VPP's native DV datapath.
- **Inline:** packet bytes copied into the TX WQE instead of referenced through
  a separate DMA address.
- **IRQ / NAPI:** Linux interrupt and network-polling work counted for AF_XDP.
- **Mpps:** millions of successful physical TX packets per second.
- **MRR / NDR:** maximum forwarding rate under pressure / zero-loss no-drop
  rate.
- **QP / RQ / SQ:** queue pair / receive queue / send queue.
- **RSS / RETA:** receive-side hash steering / its indirection table.
- **RXD / TXD:** configured receive / transmit descriptor depth.
