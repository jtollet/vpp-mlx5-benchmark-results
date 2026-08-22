# What RDMA-DV buys VPP on NVIDIA ConnectX and BlueField

> **Engineering draft.** The ConnectX-6 root cause is reproduced and the
> corrected one-to-six-worker series is qualified. Full-packet inline remains
> a disabled-by-default benchmark prototype with an explicit on/off policy.

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
the CSV; AF_XDP maximum also includes every dedicated IRQ/NAPI CPU.

![True64 throughput across workers](https://raw.githubusercontent.com/jtollet/vpp-mlx5-benchmark-results/main/charts/throughput-scaling.png)

## The result matrix

The compact table reports `Mpps / dataplane cycles per packet`. AF_XDP uses
its maximum layout; `+N IRQ` records additional kernel dataplane CPUs. A dash
means that topology was outside the retained final matrix, not zero throughput.

| Platform | Datapath | 1 worker | 2 workers | Scale-out point |
|---|---|---:|---:|---:|
| ConnectX-4 | RDMA-DV, legacy SEND | 15.8 / 207 | 29.0 / 225 | 3W: 42.2+ / 232 |
|  | DPDK mlx5, classic SEND + inline | 16.3 / 200 | 30.1 / 217 | 3W: 42.2+ / 232 |
|  | AF_XDP ZC maximum | 6.1 / 1,160 +1 IRQ | 11.8 / 1,211 +2 IRQ | 3W: 17.1 / 1,250 +3 IRQ |
| ConnectX-5 | RDMA-DV + eMPW | **24.3 / 127** | **45.4 / 136** | 4W: **60.6 / 203** |
|  | DPDK mlx5 | 19.0 / 163 | 36.4 / 170 | 4W: 55.1 / 224 |
|  | AF_XDP ZC maximum | 6.4 / 1,042 +1 IRQ | 12.4 / 1,071 +2 IRQ | 4W: 14.0 / 1,688 +4 IRQ |
| ConnectX-6 Dx | RDMA-DV + eMPW | **45.4 / 90** | **60.9 / 134** | 4W inline prototype: **109.0 / 150** |
|  | DPDK mlx5, controlled inline | 34.8 / 117 | 59.3 / 138 | 4W: 101.8 / 160 |
|  | AF_XDP ZC maximum | 17.8 / 758 +4 IRQ | 33.4 / 619 +4 IRQ | — |
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
The CX4 AF_XDP three-worker maximum reaches 17.07 Mpps with three separately
counted IRQ/NAPI cores. Its three XSKs are balanced within 0.006%; unlike the
poll-mode rows, it is DUT-limited rather than source-limited.
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
look much better than the machine-level cost.

The contrast is stark. CX6 RDMA-DV forwards 45.4 Mpps with one poll-mode
worker plus the light main core. AF_XDP's maximum one-worker layout reaches
17.8 Mpps while using that worker, the main core and **four separate IRQ/NAPI
cores**. At two workers it reaches 33.4 Mpps with seven physical CPUs in the
dataplane-plus-main budget. On CX5, four-worker RDMA-DV reaches 60.6 Mpps;
AF_XDP reaches 14.0 Mpps with four workers plus four IRQ CPUs, and its all-in
cost rises to roughly 1,692 cycles per successful packet.

Strict AF_XDP controls colocate IRQ/NAPI with workers and count the full CPU.
They prove that the maximum rows are not an accounting trick, but they also
show the service limit: CX5 strict throughput moves from 5.0 to 9.5 to only
9.7 Mpps across one, two and four workers. Deeper XSK rings absorb short
bursts; the long 3×20-second run does not sustain the apparent screen gain.
CX4 maximum scales more cleanly from 6.1 to 11.8 to 17.1 Mpps at one, two and
three workers, but it consumes the same number of additional IRQ/NAPI cores.

Linux does offer ways to trade interrupts for polling. `SO_PREFER_BUSY_POLL`
was added by commit
[`7fd3253a7de6`](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=7fd3253a7de6a317a0683f83739479fb880bffc8)
for Linux 5.11 and works with NAPI defer and timeout controls documented in
the [kernel NAPI guide](https://docs.kernel.org/networking/napi.html). The VPP
AF_XDP plugin used for the headline matrix does not request
`SO_PREFER_BUSY_POLL`, `SO_BUSY_POLL` or epoll `EPIOCSPARAMS`; those results
therefore exercise the classic mlx5 IRQ/NAPI service path.

A later isolated 4W/4Q prototype control compared socket busy-poll budgets 64,
128 and 256 with three 12-second windows each. Mean forwarding was 36.849,
37.435 and 37.182 Mpps respectively. The 1.6% numerical lead of 128 over 64
was smaller than run-to-run dispersion, while 256 was 0.7% below 128 and had
slightly worse queue fairness. This does not justify tying the kernel budget
to VPP's 256-packet frame size: the feature remains off by default, 64 is the
omitted-budget value when explicitly enabled, and 128 is only a candidate for
a longer revalidation.

The newer
[`c18d4b190a46`](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=c18d4b190a46651726c9a952667c74d2deb33c28)
threaded-busy-poll mode can leave interrupts unarmed and pin NAPI to a kernel
thread, but it moves the work to a dedicated kernel CPU rather than making it
free. Any future AF_XDP comparison must count that kthread just as explicitly
as the IRQ/NAPI CPUs here.

These are maximum-under-pressure results, not NDR. `RX_FULL`, allocation
shortages and `no free TX slots` identify where overload is absorbed. They do
not mean the retained RSS mapping is unfair: physical/RSS input is balanced
below 1%, every active socket reports native `zc:1`, and invalid descriptors,
WQE errors, PAUSE and physical frame errors remain zero.

![All-in cycles per successful packet](https://raw.githubusercontent.com/jtollet/vpp-mlx5-benchmark-results/main/charts/cpu-budget.png)

## The AF_XDP bug found by the benchmark

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
remains review code in [Gerrit 46465](https://gerrit.fd.io/r/c/vpp/+/46465).

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
