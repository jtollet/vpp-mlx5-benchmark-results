# What RDMA-DV buys VPP on NVIDIA ConnectX and BlueField

> **Investigation draft — do not publish or cite.** The ConnectX-6 native
> RDMA-DV scale-out result is under active requalification. Its current
> plateau is treated as a benchmark/dispatch symptom, not as representative
> hardware or datapath performance.

*True 64-byte IPv4 forwarding shows a lean native fast path, a queue-scaling
lesson on ConnectX-6, and the real CPU price of AF_XDP zero-copy.*

There are three credible ways to connect VPP to an NVIDIA mlx5 device. The
native RDMA plugin accesses mlx5 queues through Direct Verbs (DV), the DPDK
plugin uses the mlx5 PMD, and the AF_XDP plugin uses Linux zero-copy sockets.
They all avoid a conventional kernel socket datapath, but they do not perform
the same work.

The short version of this study is deliberately direct: **RDMA-DV is the most
CPU-efficient VPP path on ConnectX-5 and BlueField-3, and it is the fastest
single-worker path on ConnectX-5, ConnectX-6 and BlueField-3.** On CX5,
native forwarding beats the tuned DPDK path by 28%, 25% and 10% with one, two
and four workers. On BF3 it leads by 39%, 29% and 31% with one, two and four
embedded Arm workers. Its advantage is not universal: DPDK is slightly faster on CX4, and
a carefully mapped multi-TXQ DPDK configuration scales far beyond the current
native implementation on CX6.

That exception is important. It turns the result from a product claim into an
engineering result: DV removes useful work, but a lean datapath still needs a
queue implementation that scales.

## What was measured

The DUT receives an IPv4/UDP frame and routes it back through the **same
physical port**. Every successful packet performs IPv4 lookup, TTL decrement,
checksum update, adjacency rewrite and physical retransmission. This is not an
RDMA endpoint workload, an RX-only loop or a two-port wire.

Every retained run proves the frame size from NIC counters. The generator
provides 60 bytes and the NIC appends the four-byte FCS; source and DUT both
report exactly 64.000 physical bytes per packet. Earlier experiments using VPP
PG `size 64` actually produced 68-byte MAC frames and are excluded from the
result matrix.

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

| Platform | Datapath | 1 worker | 2 workers | 4 workers |
|---|---|---:|---:|---:|
| ConnectX-4 | RDMA-DV, legacy SEND | 15.8 / 207 | 29.0 / 225 | 42.8+ / 305 |
|  | DPDK mlx5 | 16.3 / 200 | 30.1 / 217 | 42.8+ / 305 |
|  | AF_XDP ZC maximum | 6.1 / 1,160 +1 IRQ | 11.8 / 1,211 +2 IRQ | 20.0 / 1,417 +4 IRQ |
| ConnectX-5 | RDMA-DV + eMPW | **24.3 / 127** | **45.4 / 136** | **60.6 / 203** |
|  | DPDK mlx5 | 19.0 / 163 | 36.4 / 170 | 55.1 / 224 |
|  | AF_XDP ZC maximum | 6.4 / 1,042 +1 IRQ | 12.4 / 1,071 +2 IRQ | 14.0 / 1,688 +4 IRQ |
| ConnectX-6 Dx | RDMA-DV + eMPW | **45.4 / 90** | 52.8 / 155 | 53.2 / 307 |
|  | DPDK mlx5, tuned TXQ mapping | 34.8 / 117 | **55.0 / 149** | **101.2 / 162** |
|  | AF_XDP ZC maximum | 17.8 / 758 +4 IRQ | 33.4 / 619 +4 IRQ | — |
| BlueField-3 | RDMA-DV + eMPW | **14.2 / 140** | **27.2 / 147** | **55.3 / 144** |
|  | DPDK mlx5 | 10.3 / 195 | 21.0 / 190 | 42.2 / 189 |

CX4's four-worker generator stopped at 42.8 Mpps, so its equal RDMA/DPDK
values are lower bounds. They do not prove that either DUT path stops there.
An isolated XL710 physical-function control reproduced a 42.676-Mpps true64
ceiling, while true128 reached 40.060 Gbit/s on the wire. The source can fill
the 40-Gbit/s link with larger frames; its small-packet rate is the constraint.
This source limit does **not** apply to the two-worker points: the generator
offered 42.78--42.80 Mpps while the CX4 physically retransmitted 28.98 Mpps
with RDMA-DV and 30.14 Mpps with DPDK. Those are measured DUT forwarding
rates with substantial source headroom; only the four-worker poll-mode points
carry the `+` lower-bound marker.
AF_XDP was not measured on BF3 by study scope; this is not a capability claim.

## Why RDMA-DV is the compelling default

The native plugin receives directly into VPP buffers and consumes mlx5 CQEs
without crossing the ethdev/`rte_mbuf` boundary. On adapters that advertise
enhanced Multi-Packet WQE (eMPW), it groups compatible packets into TX WQEs
and falls back safely to ordinary SEND when required. CX5, CX6 and BF3 use
eMPW; CX4 lacks the capability and therefore exercises legacy SEND.

The payoff is visible in both dimensions that matter. On CX5, RDMA-DV's
throughput advantage over DPDK is 28.1%, 24.8% and 10.1% from one to four
workers, while worker cycles per packet are lower by 21.9%, 19.9% and 9.2%.
On BF3, native forwards 38.5%, 29.4% and 31.0% more packets with 27.8%, 22.7%
and 23.7% fewer worker cycles at one, two and four workers. On CX6 at one worker, native delivers 30.4% more packets
and uses about 23% fewer worker cycles.

CX4 is the useful counterexample. Without eMPW, tuned DPDK is 3.5% and 4.0%
faster at one and two workers. At four workers the source limit hides any DUT
difference. CX6 is the other kind of counterexample: at two workers, tuned
DPDK reaches 55.0 Mpps and 149 cycles per packet versus RDMA-DV at 52.8 Mpps
and 155 cycles, before the multi-TXQ gap widens further. The defensible
conclusion is therefore not “DV always wins.” It is stronger and more useful:
**when the hardware exposes the batching capability, DV gives VPP an
unusually efficient low-core fast path.**

![RDMA-DV advantage over DPDK](https://raw.githubusercontent.com/jtollet/vpp-mlx5-benchmark-results/main/charts/worker-scaling.png)

## ConnectX-6: efficiency first, queues for scale

The original CX6 native result looked suspicious: 45.37 Mpps with one worker,
but only 52.81 Mpps with two. The queues were active and balanced. Both workers
ran at 4.1 GHz. Yet native cost rose from 90 to 155 cycles and from 317 to 563
instructions per successful packet. The CPU-budget identity predicts the
measured scaling exactly:

```text
2 × 90.15 / 154.93 = 1.164
52.81 / 45.37      = 1.164
```

The longer scale-out series removes any remaining ambiguity: four, five and
six workers forward 53.23, 53.45 and 53.01 Mpps. Their aggregate worker cost
rises to 307, 382 and 463 cycles per successful packet while the rate stays
flat. Each worker owns two balanced RX queues and a dedicated QP; the main QP
is present but records no traffic. The source provides 6.5--10.4% headroom.
These are maximum-under-pressure points with software `no-free` events, not
NDR, but they establish the native plateau independently of source or RSS.

This was not a CX6, PCIe or generator ceiling. With explicit ownership and a
weighted RETA, VPP/DPDK reached 34.8, 55.0, 101.2, 113.0 and 115.6 Mpps with
one, two, four, five and six workers. The six-worker source delivered 133.4
Mpps. Testpmd independently reached 111.3 Mpps with four cores and sixteen
queue pairs.

The key DPDK A/B held four workers, RX queues, rings, graph and offered traffic
constant. One TXQ per worker produced 53.0 Mpps; two produced 93.3; four
produced 93.9. Queue zero belonged to the main thread and transmitted no
packet. Two exclusive TXQs per worker unlocked almost all the gain. With six
workers, two RXQs per worker also beat one RXQ per worker: 115.6 versus about
102 Mpps.

Native did not respond the same way. One, two and four independently owned raw
QPs per worker stayed near 53 Mpps. Reducing requested TX CQEs by 32x lowered
instructions but not throughput. Expanding the outstanding-buffer ring from
2k to 16k entries did not move the ceiling. RSS, UAR sharing, SQ depth,
frequency, firmware policy, link and source headroom were separately excluded.

The remaining native limitation is localized to extra per-packet work in the
multi-worker raw-QP/eMPW implementation, but not yet to one source line.
Smaller batches accompany the plateau; they are an observation, not a proven
initiating cause. That is the honest boundary: RDMA-DV is the best one-worker
path on CX6, while DPDK's mature multi-queue machinery currently wins
scale-out by nearly 2x at four workers.

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

The public sequence is documented in the
[`v1 netdev thread`](https://lore.kernel.org/netdev/20260819151320.64178-1-jtollet@cisco.com/).
Dragos Tatulea requested a shorter, reordered changelog and explicit
confirmation that the failure is silent, then supplied his `Reviewed-by`.
The resulting
[`[PATCH net v2]`](https://lore.kernel.org/netdev/20260820151558.11015-1-jtollet@cisco.com/)
contains those changes and is archived byte-for-byte
[`here`](patches/mlx5-af-xdp-partial-refill-double-release-fix.patch). The
measurements are complete for that exact build; applying them to an upstream
kernel remains provisional until the fix is accepted. The kernel's
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
2. **Queue topology can overturn a stack comparison.** CX6 DPDK needed more
   than one exclusive TXQ per worker before its scaling appeared; testpmd was
   not comparable until RX/TX pairs per core matched.
3. **Native CX6 scaling is unfinished engineering, not a hardware ceiling.**
   The gap is localized to multi-worker raw-QP/eMPW service work, with several
   plausible single causes already excluded.
4. **AF_XDP's kernel work must be counted.** Zero-copy is valuable, but in this
   forwarding workload it costs far more all-in CPU and achieves less
   throughput than RDMA-DV.
5. **Pressure counters define the claim.** Maximum forwarding, source-limited
   lower bounds and zero-loss NDR are different results and stay labelled as
   such.

The exact CSV, placement ledger, methodology, tuning evidence, submitted
kernel patch and figure sources are available in the companion repository.
The frozen VPP tree includes the merged RX CQ doorbell fix and the reviewed
changes tracked in [`VPP_CHANGES.md`](VPP_CHANGES.md); the native eMPW change
is currently CI-verified in [Gerrit 46465](https://gerrit.fd.io/r/c/vpp/+/46465).

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
