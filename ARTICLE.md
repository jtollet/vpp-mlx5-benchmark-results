# What RDMA-DV buys VPP on NVIDIA ConnectX and BlueField

> **Code provenance.** The ConnectX-6 one-to-six-worker series is qualified.
> Full-packet inline remains a disabled-by-default review change with an
> explicit on/off policy.

*True 64-byte IPv4 forwarding shows a lean native fast path, why one eMPW
representation changed CX6 from a 53-Mpps plateau to 124.6 Mpps, and the real CPU price of
AF_XDP zero-copy.*

There are three credible ways to connect VPP to an NVIDIA mlx5 device. The
native RDMA plugin accesses mlx5 queues through Direct Verbs (DV), the DPDK
plugin uses the mlx5 PMD, and the AF_XDP plugin uses Linux zero-copy sockets.
They all avoid a conventional kernel socket datapath, but they do not perform
the same work.

The short version is deliberately direct: **RDMA-DV is the most CPU-efficient
VPP path on ConnectX-5 and BlueField-3, the fastest single-worker path on CX5,
CX6 and BF3, and—once both stacks use complete-packet eMPW inline—the fastest
qualified path at every retained CX6 worker count.** On CX5, native forwarding beats tuned
DPDK by 28%, 25% and 10% with one, two and four workers. On BF3 it leads by
39%, 29% and 31%. On CX6 the tuned native series reaches 60.9, 109.0, 124.6
and 122.9 Mpps at two, four, five and six workers, ahead of matched DPDK by
2.7%, 7.1%, 8.4% and 4.8%.

The counterexamples keep that conclusion honest. DPDK is 3.5--4.0% faster on
CX4, which lacks eMPW, and forcing inline is harmful on BF3 and on the CX6
single-worker screen. The useful result is not “inline everything.” It is that
DV provides an exceptionally lean datapath, while the transmit representation
must follow actual pressure and hardware behavior.

## What was measured

The DUT receives an IPv4/UDP frame and routes it back through the **same
physical port**. Every successful packet performs IPv4 lookup, TTL decrement,
checksum update, adjacency rewrite and physical retransmission. This is not an
RDMA endpoint workload, an RX-only loop or a two-port wire.

NIC counters confirm that every retained result uses 64-byte Ethernet frames.

Throughput is the DUT's successful physical TX delta. It is not VPP's TX
attempt counter. Finals are three independent 20-second windows. Main and
worker threads use distinct physical cores; SMT siblings are excluded. RXQ
and TXQ/QP ownership is captured for every cell, and multi-queue results must
remain within 1% balance.

The word *maximum* matters. Several points deliberately overload the DUT to
prove source headroom, so `rx-miss`, RX discard or TX backpressure can advance.
They are maximum forwarding rate (MRR), not zero-loss NDR. A `+` below marks a
source-limited lower bound. CPU cost is aggregate dataplane cycles divided by
successful physical TX packets. The separate VPP main core is disclosed in
the CSV. For AF_XDP, CPU-wide counters on the declared main and worker CPUs
include colocated IRQ/NAPI and kernel XSK work; no auxiliary packet-service
CPU is allowed in the retained matrix.

![True64 throughput across workers](https://raw.githubusercontent.com/jtollet/vpp-mlx5-benchmark-results/main/charts/throughput-scaling.png)

## The result matrix

The compact table reports `Mpps / dataplane cycles per packet`. Every AF_XDP
row uses `W` RX queues and `W+1` private TX/XSK queues: one per worker and one
for the main thread. IRQ/NAPI is colocated on those same declared CPUs.

| Platform | Datapath | 1 worker | 2 workers | Scale-out point |
|---|---|---:|---:|---:|
| ConnectX-4 | RDMA-DV, legacy SEND | 15.8 / 207 | 29.0 / 225 | 3W: 42.2+ / 232 |
|  | DPDK mlx5, classic SEND + inline | 16.3 / 200 | 30.1 / 217 | 3W: 42.2+ / 232 |
|  | AF_XDP ZC, all-in workers | 3.8 / 866 | 8.2 / 800 | 3W: 11.2 / 877 |
| ConnectX-5 | RDMA-DV + eMPW | **24.3 / 127** | **45.4 / 136** | 4W: **60.6 / 203** |
|  | DPDK mlx5 | 19.0 / 163 | 36.4 / 170 | 4W: 55.1 / 224 |
|  | AF_XDP ZC, all-in workers | 5.4 / 567 | 10.1 / 609 | 4W: 13.8 / 891 |
| ConnectX-6 Dx | RDMA-DV + eMPW | **45.4 / 90** | **60.9 / 134** | 4W inline prototype: **109.0 / 150** |
|  | DPDK mlx5, controlled inline | 34.8 / 117 | 59.3 / 138 | 4W: 101.8 / 160 |
|  | AF_XDP ZC, all-in workers | 10.6 / 382 | 21.3 / 381 | 4W: 40.9 / 396 |
| BlueField-3 | RDMA-DV + eMPW | **14.2 / 140** | **27.2 / 147** | 4W: **55.3 / 144** |
|  | DPDK mlx5 | 10.3 / 195 | 21.0 / 190 | 4W: 42.2 / 189 |

CX4 reaches the traffic source at three workers. The measured true64
traffic-generator ceiling was 42.63 Mpps, while the three final windows
offered a mean 42.21 Mpps and the DUT retransmitted 42.17 Mpps with RDMA-DV
and 42.21 Mpps with DPDK. Both 3W values are therefore lower bounds; they do
not prove that either DUT path stops there. This source limit does **not**
apply to the two-worker points: the generator offered about 42.8 Mpps while
the CX4 physically retransmitted 28.98 Mpps with RDMA-DV and 30.14 Mpps with
DPDK.
The comparable CX4 AF_XDP series reaches 3.77, 8.15 and 11.16 Mpps with one,
two and three workers. It uses no auxiliary IRQ core. The 3W input spread is
1.165%, consistent with RETA and finite-flow quantization; the TX-only main
queue receives no RSS traffic.
AF_XDP was not measured on BF3 by study scope; this is not a capability claim.

## Why RDMA-DV is the compelling default

The native plugin receives directly into VPP buffers and consumes mlx5 CQEs
without crossing the ethdev/`rte_mbuf` boundary. On adapters that advertise
enhanced Multi-Packet WQE (eMPW), it groups compatible packets into TX WQEs
and falls back safely to ordinary SEND when required. CX5, CX6 and BF3 use
eMPW; CX4 lacks the capability and therefore exercises legacy SEND.
The DPDK PMD likewise selected its No-MPW classic SEND path with inline on
every retained CX4 final; the archived burst function is
`mlx5_tx_burst_sci`. The requested `txq_inline_mpw=1` devarg did not make the
runtime path MPW.

The payoff is visible in both dimensions that matter. On CX5, RDMA-DV's
throughput advantage over DPDK is 28.1%, 24.8% and 10.1% from one to four
workers, while worker cycles per packet are lower by 21.9%, 19.9% and 9.2%.
On BF3, native forwards 38.5%, 29.4% and 31.0% more packets with 27.8%, 22.7%
and 23.7% fewer worker cycles at one, two and four workers. On CX6, native is
ahead at every retained worker count; at one worker it delivers 30.4% more
packets and uses about 23% fewer worker cycles.

CX4 is the useful counterexample. Without eMPW, tuned DPDK is 3.5% and 4.0%
faster at one and two workers. At three workers the source limit hides any DUT
difference: both paths forward essentially the full offered load at about 232
worker cycles per successful packet. CX6 is the more revealing case: its
native pointer control reaches only 52.8 Mpps at two workers, below DPDK's
59.3. Once both drivers use the same inline representation, native reaches
60.9 Mpps at two workers and leads 109.0 to 101.8 at four, while costing 150
rather than 160 worker cycles per packet at four. The defensible conclusion is
therefore not “DV always wins.” It is stronger and more useful:
**when the hardware exposes the batching capability, DV gives VPP an
unusually efficient fast path without needing an ethdev abstraction layer.**

![RDMA-DV advantage over DPDK](https://raw.githubusercontent.com/jtollet/vpp-mlx5-benchmark-results/main/charts/worker-scaling.png)

## ConnectX-6: the 53-Mpps mystery was in the WQE

The original native curve looked suspicious: 45.37 Mpps with one worker,
52.81 with two, then 53.23, 53.45 and 53.01 with four, five and six. RX queues
were balanced, every worker owned a dedicated raw QP, the main QP was idle and
the source had headroom. More QPs, deeper SQs, fewer requested CQEs, UAR
placement, firmware policy and larger buffer pools did not move the plateau.
The rising CPU cost described the symptom exactly, but did not explain it:

```text
2 × 90.15 / 154.93 = 1.164
52.81 / 45.37      = 1.164
```

The decisive experiment removed RX, RSS, lookup and graph dispatch. In the
old native eMPW path, every 60-byte packet remained in a VPP buffer and the WQE
contained an address/lkey/length data segment. The NIC therefore fetched each
packet through a separate DMA-read/service operation. The prototype instead
copies the complete packet into the eMPW WQE, using the same representation as
the DPDK mlx5 inline burst.

At four workers, that one boundary moves TX-only throughput from 68.868 Mpps
with pointer data segments to 140.816 Mpps with full inline while retaining
buffers until completion. Releasing a buffer immediately after the SQ copy
raises it only another 3.6%, to **145.862 Mpps**. The main gain is therefore
the elimination of per-packet external reads, not buffer lifetime. The result
is 98.0% of the 148.81-Mpps Ethernet64 packet-rate ceiling.

![CX6 eMPW inline root cause](https://raw.githubusercontent.com/jtollet/vpp-mlx5-benchmark-results/main/charts/cx6-inline-root-cause.png)

This does not claim that aggregate PCIe byte bandwidth was exhausted. It
localizes the limit to the transaction/service cost of pointer data segments:
the same card, link, QPs, UARs and workers transmit twice as many packets when
the bytes are already in the posted WQE.

The full L3 finals keep one dedicated QP per worker and an inactive main QP.
At 2W, the measured warm-up pairs one queue from each RSS rate class on each
worker: q0/q2 on W0 and q1/q3 on W1. The 4W map is q0/q4, q1/q5, q2/q6 and
q3/q7. The 5W winner uses four queues per worker (q0/q5/q10/q15 on W0 and the
same cyclic pattern through W4); 6W returns to q12, q0/q6 through q5/q11.
The small 5W-to-6W dip is a qualification trade-off, not an unexplained
dispatch collapse: faster q18/q24 six-worker screens reached about 138.5 Mpps
but exceeded the 1% individual-RXQ fairness limit and were excluded.

The qualified means are **60.893, 109.049, 124.564 and 122.867 Mpps** at two,
four, five and six workers. Maximum individual RXQ spread is 0.136%, 0.083%,
0.992% and 0.461%, respectively. The 5W and 6W cells request one CQE every 32
doorbells and use an 8192-entry ownership ring; 2W and 4W retain the default
cadence. These are MRR results, not NDR. The 4W priority-buffer ingress discard
rate averages 25.77 Mpps and TX no-free 0.45 Mpps; the other pressure domains
remain identified in the CSV. A separate 4W clean control follows the source
at 91.282 Mpps with both counters at zero.

### Why the earlier DPDK queue explanation was wrong

The old DPDK A/B appeared to show that two TXQs per worker beat one. It had a
hidden variable. On non-BlueField mlx5, the PMD's default complete-packet
inline threshold is eight total TX queues. VPP provisions an additional main
TXQ, so four workers with one TXQ each create five total queues and stay below
the threshold; two per worker create nine and cross it. Queue count had
silently selected pointer versus inline WQEs.

The corrected A/B forces inline independently of queue count. With inline
off, one versus two TXQs per worker gives 68.440 versus 68.777 Mpps TX-only;
with inline on it gives 125.006 versus 112.738. In L3 q8, one versus two gives
109.108 versus 108.288 Mpps in the matched screen. More TXQs are neutral or
harmful once representation is held constant.

The corrected DPDK finals therefore use one exclusive TXQ per worker, an idle
main TXQ and explicit inline from two workers upward: 34.800, 59.308, 101.838,
114.891 and 117.260 Mpps at one, two, four, five and six workers. Native is
ahead at all five points: 45.370, 60.893, 109.049, 124.564 and 122.867 Mpps.
Testpmd's
111.3-Mpps four-core control remains useful evidence of hardware headroom,
but it no longer supports a “more queues are faster” conclusion.

### Fixed inline is evidence, not the production policy

Always-on inline is not universally beneficial. It hurts the CX6 one-worker
screen, and a matched BF3 control at four workers falls from 49.321 Mpps with
pointer data segments to 44.096 with inline-and-retain and 43.094 with inline
plus immediate free. Those BF3 numbers are three 12-second controls at a fixed
50-Mpps offer, not replacements for the headline 3×20 final.

The production question is therefore when to select the representation. A
per-TXQ adaptive prototype measured posted-minus-completed packets independently
on every queue, but the 10/128 hysteresis crossed roughly 250,000 times per TXQ
in six seconds on CX6 and reduced 4W/q4 forwarding to 49.2 Mpps. It is rejected.
The retained interface is deliberately simpler and device-wide:
`tx-empw-inline off` or `tx-empw-inline on [max-size N]`. It defaults to OFF;
ON defaults to 60 bytes, the VPP-buffer length of a physical Ethernet-64
packet, and releases a buffer immediately after copying the complete packet
into the SQ. OFF preserves the baseline fast path; ON is selected for the
qualified CX6 2W-and-higher cells.
No adaptive result appears in this article or its CSV.

## AF_XDP: zero-copy is not zero CPU

AF_XDP avoids payload copies, but mlx5 IRQ/NAPI, XSK refill/completion rings
and VPP still consume CPU. Counting only the VPP workers would make the result
look much better than the machine-level cost. The retained comparison therefore
counts CPU-wide cycles on exactly the VPP main and worker cores, with every
mlx5 completion IRQ pinned to the thread that owns its queue. No auxiliary
IRQ, NAPI or recycling core is added to AF_XDP's budget.

That stricter topology changes the headline. CX6 AF_XDP scales from 10.60 to
21.27, 40.91, 50.38 and 60.58 Mpps at one, two, four, five and six workers.
Its worker-CPU cost remains about 382--401 cycles per successful packet,
including kernel execution on those CPUs. CX5 moves from 5.43 to 10.11 and
then 13.85 Mpps at four workers; CX4 reaches 3.77, 8.15 and 11.16 Mpps at
one, two and three workers. These are much more honest numbers than a layout
which quietly adds one IRQ CPU per queue.

The cost is hidden only if one reads VPP graph counters as whole-machine
counters. The CX4 decomposition attributes roughly 682, 662 and 671 cycles
per packet to kernel execution at one, two and three workers: 75--81% of the
decomposed CPU budget even though every cycle is charged to a declared CPU.
RDMA-DV and DPDK poll their queues directly from VPP threads and do not carry
this second kernel datapath.

A separate device-filtered 4W trace verifies the accounting boundary rather
than assuming it from affinity alone. Every observed NAPI poll, cyclic RX
refill, batched XSK allocation, TX completion poll and `xsk_tx_completed()`
call ran on worker CPUs 21--24. Some work executed as `ksoftirqd` or a bound
`kworker`, but never outside those same CPUs, so the CPU-wide counters include
it. `xp_release_deferred()` remained absent: that asynchronous work item
destroys a pool after its last reference disappears; it is not a per-packet
descriptor recycler. The traced window is a placement proof only and is not
used as a throughput point.

Linux does offer ways to trade interrupts for polling. `SO_PREFER_BUSY_POLL`
was added by commit
[`7fd3253a7de6`](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=7fd3253a7de6a317a0683f83739479fb880bffc8)
for Linux 5.11 and works with NAPI defer and timeout controls documented in
the [kernel NAPI guide](https://docs.kernel.org/networking/napi.html). The VPP
AF_XDP candidate exposes `SO_BUSY_POLL`, `SO_PREFER_BUSY_POLL` and
`SO_BUSY_POLL_BUDGET` as optional per-device settings. They remain off by
default. The retained CX6 rows use 50 us, prefer mode and budget 16; CX4 and
CX5 keep socket busy polling off because their measured A/Bs did not benefit.

### What socket busy polling changes

`SO_BUSY_POLL` lets a non-blocking XSK receive call drive its NAPI context for
a bounded time instead of waiting for the next completion interrupt.
`SO_PREFER_BUSY_POLL` asks the kernel to prefer that ownership model, while
`SO_BUSY_POLL_BUDGET` limits the work of one NAPI callback. It removes wakeup
and interrupt overhead; it does **not** remove mlx5e, XDP, XSK or NAPI work.

An isolated CX6 control used four workers, four XSKs and identical offered
load. IRQ/NAPI was colocated with the owning worker and the table counts all
CPU cycles, including time spent in the kernel. This diagnostic predates the
private `W+1` main TX queue and is used only for the causal A/B, not as a
headline throughput row:

| 4W / 4Q control | Physical TX | All-in cycles / TX packet | Completion IRQs / 8 s |
|---|---:|---:|---:|
| Socket busy poll off | 32.084 Mpps | 508.9 | 3,666,819 |
| 10 us, prefer, budget 64 + NAPI IRQ defer | **40.057 Mpps** | **404.3** | **16** |

That is 24.9% more forwarding and 20.6% fewer all-in cycles per successful
packet. The qualification matters: socket busy polling alone, with the
netdevice NAPI controls left at zero, reached 34.691 Mpps (+8.1%) and reduced
interrupts by only 21%. The full result also used
`gro_flush_timeout=20000 ns` and `napi_defer_hard_irqs=8`; those are
netdevice-wide controls and are deliberately not hidden inside the VPP
interface option. The socket-only VPP support is under review in
[Gerrit 46539](https://gerrit.fd.io/r/c/vpp/+/46539).

The result is not portable as a magic constant. With the corrected `W+1`
topology, 50 us / prefer / budget 16 reduced CX4 3W throughput from 11.27 to
8.38 Mpps (-25.7%) and was 1.18% slower in the CX5 4W short A/B. It is kept
only for CX6. `gro_flush_timeout=20000 ns` and `napi_defer_hard_irqs=8` are
per-netdevice controls applied outside VPP, not socket options.

This is also why AF_XDP CPU accounting cannot stop at VPP's thread counters.
With classic delivery, mlx5 NAPI may execute on additional IRQ CPUs; with
socket busy polling, the VPP worker enters the kernel and performs that work
there. Either way those cycles sit outside the VPP graph even when they share
the worker CPU. RDMA-DV and DPDK instead poll the device from the VPP workers,
so their measured forwarding budget consists of the VPP main and worker
threads, without separate kernel packet-service cores. Busy polling changes
where and when AF_XDP's kernel cost is paid; it does not make that cost free.

A separate budget sweep also showed why VPP's 256-packet frame size is not a
sound default for the kernel NAPI budget. The optimum moved with load and
platform; the qualified CX6 campaign retained 16, while omitting the explicit
budget from the VPP option uses 64. The feature itself remains off by default.

The newer
[`c18d4b190a46`](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=c18d4b190a46651726c9a952667c74d2deb33c28)
threaded-busy-poll mode can leave interrupts unarmed and pin NAPI to a kernel
thread, but it moves the work to a dedicated kernel CPU rather than making it
free. Any future AF_XDP comparison must count that kthread just as explicitly
as any other packet-service CPU.

These are maximum-under-pressure results, not NDR. `RX_FULL`, allocation
shortages and `no free TX slots` identify where overload is absorbed. They do
not mean the retained RSS mapping is unfair: every active socket reports
native `zc:1`, and invalid descriptors, WQE errors, PAUSE and physical frame
errors remain zero. CX6 RXQ spread is below 0.5% through 4W; the 1.8% and 2.4%
5W/6W values are the measured distribution of the finite hash population
across a quantized RETA, not worker or IRQ migration.

### A queue-boundary bug exposed by `W+1`

The fair topology also exposed a small pre-existing VPP bug. AF_XDP sizes its
RX and TX queue vectors to the greater configured count. The refill helper
iterated over the whole RX vector, so with `W` RX and `W+1` TX queues it tried
to poll the main thread's TX-only XSK and logged `Bad file descriptor`.
[Gerrit 46547](https://gerrit.fd.io/r/c/vpp/+/46547) changes only the refill
bound to `ad->rxq_num`. The corrected plugin was used for every new CX4, CX5
and CX6 row; no retained hardware snapshot contains that error.

![All-in cycles per successful packet](https://raw.githubusercontent.com/jtollet/vpp-mlx5-benchmark-results/main/charts/cpu-budget.png)

## The mlx5 kernel ownership bugs found by the benchmark

Heavy `RX_FULL` testing exposed a silent mlx5 cyclic-RQ ownership bug. After a
failed XDP redirect, a partial batched refill could leave an old XSK buffer
pointer in a missing WQE. If the buffer was reallocated elsewhere, a later
retry could release the live buffer and publish the same UMEM frame twice.
There was no kernel warning or splat; the standalone checker detected the
ownership violation.

Daniel Borkmann proposed marking the driver-side release with
`MLX5E_WQE_FRAG_SKIP_RELEASE`. The flag is cleared when a replacement buffer
is assigned, making refill retries idempotent. On stock code, the reproducer
stopped after 2.85 million packets with 64 ownership/double-publication
errors. The one-file fix completed 356.9 million packets and 571,405 genuine
ring-full events with zero ownership or data error. An A/B proved that this
fix alone was sufficient; an earlier VPP-side candidate was not required.

The public sequence starts with the
[`v1 netdev thread`](https://lore.kernel.org/netdev/20260819151320.64178-1-jtollet@cisco.com/).
Dragos Tatulea requested a shorter, reordered changelog and explicit
confirmation that the failure is silent, then supplied his `Reviewed-by` for
the cyclic-RQ fix. Those edits appeared in
[`v2`](https://lore.kernel.org/netdev/20260820151558.11015-1-jtollet@cisco.com/),
whose cyclic patch is archived byte-for-byte
[`here`](patches/mlx5-af-xdp-partial-refill-double-release-fix.patch).

Sashiko then identified the analogous retry hazard in the MPWQE/striding path.
The candidate was not posted on inspection alone: an injected three-failure
A/B showed stock freeing the same 16 XSK pointers three times, while the fix
freed them once, made retries no-ops and cleared the bitmap after successful
allocation. The resulting
[`[PATCH net v3 0/2]`](https://lore.kernel.org/netdev/cover.1787347981.git.jtollet@cisco.com/)
keeps the reviewed cyclic fix as patch 1 and adds the validated MPWQE fix as
patch 2. The cyclic patch has the same stable patch-id as v2, so the AF_XDP
performance rows remain an exact A/B for that code. Applying either result to
an upstream kernel remains provisional until the series is accepted. The kernel's
[AF_XDP documentation](https://docs.kernel.org/networking/af_xdp.html)
provides the underlying ring and zero-copy model.

## What tuning did—and did not—change

Queue count mattered more than raw ring size. CX5 4W retained q4 for all three
paths; q8/q16 were slower or failed the 1% fairness threshold. Doubling native
TXD reduced `no free` events but changed throughput only 0.22%. DPDK TXD1024
reduced failures but gained only 0.16%. AF_XDP's one-sided deep rings helped
short screens, while the deep/deep combination regressed over 20 seconds.
Descriptors are buffering, not a substitute for service rate.

CX6 firmware `BALANCED` versus `AGGRESSIVE` produced a real batching change
but less than 0.5% throughput difference in the matched true64 4W A/B. An
older 68-byte control even showed `AGGRESSIVE` filling 256-packet vectors while
losing 5.3% throughput. Vector size is evidence about batching, not a direct
performance guarantee.

Finally, `rx-miss` is a receive-capacity counter, not a CPU cache miss. It
means the NIC/PMD could not deliver a frame into an available RX descriptor;
the packet never entered VPP. It must be reported separately from VPP graph
drops, TX no-free events, priority-buffer discards and potentially overlapping
`rx_out_of_buffer` counters. Any retained row with nonzero `rx-miss` is MRR,
never NDR.

## Takeaways

1. **RDMA-DV is the strongest efficiency result.** On eMPW-capable CX5, CX6
   and BF3 it delivers more work per core than the alternatives at low worker
   counts, often by a wide margin.
2. **WQE representation can overturn a stack comparison.** The apparent CX6
   TXQ-count gain was DPDK's inline threshold in disguise. At fixed inline
   state, one exclusive TXQ per worker wins or ties.
3. **The CX6 scaling root cause is pointer-segment service, not dispatch.**
   Full-packet eMPW inline raises native 4W TX-only from 68.9 to 145.9 Mpps and
   sustained L3 to 109.0 Mpps at 4W and 124.6 Mpps at 5W. The tested adaptive
   hysteresis oscillates and is rejected; the published cells use explicit ON/OFF.
4. **AF_XDP's kernel work must be counted.** Zero-copy is valuable, but in this
   forwarding workload it costs far more all-in CPU and achieves less
   throughput than RDMA-DV.
5. **Pressure counters define the claim.** Maximum forwarding, source-limited
   lower bounds and zero-loss NDR are different results and stay labelled as
   such.

The exact result CSV, the
[`CX6 inline causal A/B`](data/cx6-inline-causal.csv), the
[`BF3 inline controls`](data/bf3-inline-controls.csv), placement ledger,
methodology, tuning evidence, submitted kernel patch and figure sources are
available in the companion repository.
The frozen VPP tree includes the merged RX CQ doorbell fix and the reviewed
changes tracked in [`VPP_CHANGES.md`](VPP_CHANGES.md); the native eMPW change
remains review code in [Gerrit 46465](https://gerrit.fd.io/r/c/vpp/+/46465),
with optional AF_XDP busy polling in
[46539](https://gerrit.fd.io/r/c/vpp/+/46539) and the `W+1` refill fix in
[46547](https://gerrit.fd.io/r/c/vpp/+/46547).

## Glossary

- **AF_XDP / XSK / ZC:** Linux XDP socket interface / socket / native zero-copy.
- **CQ / CQE:** completion queue / completion entry.
- **DPDK / PMD:** Data Plane Development Kit / poll-mode driver.
- **eMPW / WQE:** enhanced multi-packet / ordinary work queue element.
- **IBV / DV:** generic libibverbs / mlx5 Direct Verbs native paths.
- **IRQ / NAPI:** Linux interrupt and network-polling work counted for AF_XDP.
- **L3 hairpin:** IPv4 forwarding back through the same physical DUT port.
- **MRR / NDR:** maximum forwarding rate / zero-loss no-drop rate.
- **Mpps:** millions of successful physical TX packets per second.
