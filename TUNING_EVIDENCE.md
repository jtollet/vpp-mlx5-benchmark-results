# Tuning evidence

This document keeps the selection evidence behind the article. Short screens
choose a configuration; only repeated 3×20-second cells populate the public
result matrix. Every retained frame is proven as 64.000 physical bytes at
source and DUT. Older PG `size 64` observations are 68-byte controls and never
select a true64 winner.

Queue fairness is `(max RXQ delta - min RXQ delta) / mean RXQ delta`; retained
multi-queue cells target less than 1%. CX6 AF_XDP 5W/6W explicitly disclose
1.8%/2.4% finite-hash/RETA quantization instead of hiding it. Queue count,
descriptor depth and offered load are screened independently per hardware and
datapath. “Maximum” means maximum forwarding under pressure, not zero-loss NDR.

## ConnectX-4

CX4 does not advertise eMPW, so native RDMA-DV uses legacy SEND. One- and
two-worker winners are q2/RXD2048/TXD2048. DPDK independently selects
q1/RXD1024/TXD2048 at one worker and q2/RXD1024/TXD2048 at two. At three
workers, RDMA-DV selects q3/RXD1024/TXD2048 and four QPs including an inactive
main QP. DPDK selects q3/RXD2048/TXD2048 and four TXQs including inactive
main TXQ0. Its retained hardware-detail snapshots identify No MPW with inline
and the `mlx5_tx_burst_sci` function: the requested `txq_inline_mpw=1` did not
select MPW, so the DPDK winner is classic SEND with inline.

| Path | 1W | 2W | 3W | 3W qualification |
|---|---:|---:|---:|---|
| RDMA-DV | 15.803 Mpps / 206.6 cpp | 28.983 / 225.3 | 42.166+ / 232.2 | q3; RXQ spread ≤0.159%; source-limited |
| DPDK, classic SEND + inline | 16.349 / 199.6 | 30.141 / 216.7 | 42.213+ / 231.9 | q3; TXQ0 inactive; RXQ spread ≤0.593%; source-limited |
| AF_XDP ZC; kernel counted | 3.768 / 865.6 | 8.151 / 800.4 | 11.162 / 876.7 | q3; W+1 private XSKs; no auxiliary CPU |

Each 3W winner is a three-window 3×20-second result with a restarted source.
The final source means
were 42.205 Mpps for RDMA-DV and 42.214 Mpps for DPDK; a synchronized true64
traffic-generator ceiling control reached 42.634 Mpps. Both DUT rates are
therefore source-limited lower bounds, and their cycles include idle polling
at the offered boundary.
All three RX queues are active and balanced. Native main TQ0 and DPDK TXQ0
remain inactive; the three worker QPs/TXQs exclusively carry the traffic.

The synchronized true64 traffic-generator ceiling control measured 42.634
Mpps source TX and 42.640 Mpps at the CX4 physical RX counter. A separate
true128 control reached 40.060 Gbit/s after wire overhead. Thus the source
reaches 40-Gbit/s line rate with larger frames but not the true64 packet rate
required to move the 3W lower bound. The controls used NVM 7.00, management
firmware 7.1, Linux i40e from the 6.8 kernel and DPDK 24.11.1; no firmware
update was performed during the benchmark.

Historical four-worker poll-mode runs remain diagnostic artifacts only and do
not feed the article table, public CSV or main charts. They also stopped at the
source boundary (42.821/42.818 Mpps for RDMA-DV/DPDK), so adding a fourth
worker did not establish either DUT ceiling. The comparable AF_XDP series uses
one RX queue per worker plus a private TX-only XSK for the main thread and
reaches 11.162 Mpps at 3W. IRQ/NAPI stays on main+worker CPUs; the 1.165% RXQ
spread is RETA/finite-flow quantization. A 4W result remains outside the CX4
headline matrix so every path is plotted only at one, two and three workers.

## ConnectX-5

### RDMA-DV

Native uses cyclic RQ, eMPW, `mode dv` and `no-multi-seg`.

| Workers | Winner | Physical TX | Worker cpp | RXQ spread |
|---:|---|---:|---:|---:|
| 1 | q1 RXD1024/TXD512 | 24.310 | 127.237 | n/a |
| 2 | q2 RXD512/TXD512 | 45.389 | 135.840 | <1% |
| 4 | q4 RXD256/TXD1024 | 60.620 | 203.355 | 0.095–0.163% |

At 4W, q8 and q16 reach 56.91 and 55.31 Mpps; q16 is rejected at 1.78%
spread. Doubling TXD to 2048 reduces `no free tx slots` about 12% but changes
TX only +0.22%. RXD512 drops TX to 58.77 Mpps. Ring depth changes queueing
headroom, not the sustainable service rate.

### DPDK mlx5

DPDK uses vector RX, enhanced MPW, fast-free, CQE compression disabled and an
inactive main TXQ plus private worker TXQs.

| Workers | Winner | Physical TX | Worker cpp | RXQ spread |
|---:|---|---:|---:|---:|
| 1 | q1 RXD1024/TXD1024; TXQ2 | 18.980 | 162.973 | n/a |
| 2 | q2 RXD1024/TXD512; TXQ3 | 36.374 | 169.512 | 0.63–0.67% |
| 4 | q4 RXD1024/TXD512; TXQ5 | 55.063 | 223.877 | 0.015–0.025% |

The 4W screen crosses q4/q8/q16 with one, two and four TXQs per worker. q4
with one wins. q8/q16 either lose throughput or exceed 1% fairness. RXD
1024/2048/4096 produces 58.09/57.25/56.41 Mpps in matched short windows.
TXD1024 reduces TX failures but gains only 0.16%. Extra queues and descriptors
do not lift the CX5 4W plateau.

### AF_XDP zero-copy

Every XSK independently proves native zero-copy. The final topology has `W`
RX queues and `W+1` private TX/XSK queues, with the extra queue and its IRQ on
the main thread. IRQ/NAPI for each active RX queue is colocated on its worker;
CPU-wide counters include that kernel work.

| Workers | Physical TX | Worker-CPU cpp | Main-CPU cpp | RXQ spread |
|---:|---:|---:|---:|---:|
| 1 | 5.434 Mpps | 566.8 | 66.0 | n/a |
| 2 | 10.112 | 609.3 | 34.8 | ≤0.006% |
| 4 | 13.846 | 890.6 | 25.1 | ≤0.009% |

RX4096/TX1024 is retained. Buffers from 524k to 2M, coalescing screens and the
legacy syscall lock did not yield a monotonic sustained gain. Socket busy
polling was 1.18% slower in the corrected 4W short A/B and remains off. Deeper
rings delay pressure; they do not raise service rate. The 2W→4W plateau is a
service limit, not an inactive or unfair queue.

## ConnectX-6 Dx

### Native RDMA-DV

The one-worker row retains the pointer-data-segment path. The old two-to-six-
worker pointer controls established the 53-Mpps plateau; explicit full inline
now supplies the headline profile from two workers upward:

| Workers / RXQ | TX representation | Physical TX | Worker cpp / ipp | Status |
|---|---|---:|---:|---|
| 1 / 4 | pointer | 45.370 Mpps | 90.153 / 316.801 | clean final; inline screen is lower |
| 2 / 4 | full inline + immediate free | **60.893** | **134.211 / 445.618** | MRR; measured warm-up placement; RXQ spread ≤0.136% |
| 4 / 8 | full inline + immediate free | **109.049** | **149.917 / 496.182** | canonical MRR, 3×20 s |
| 5 / 20 | full inline + immediate free | **124.564** | **164.023 / 576.816** | CQE32/ring8192; RXQ spread ≤0.992% |
| 6 / 12 | full inline + immediate free | **122.867** | **199.526 / 725.189** | CQE32/ring8192; RXQ spread ≤0.461% |
| 2 / 4 | pointer | 52.814 | 154.925 / 562.506 | historical control |
| 4 / 8 | pointer | 53.233 | 307.075 / 1242.695 | historical control |
| 5 / 10 | pointer | 53.445 | 382.337 / 1584.736 | historical control |
| 6 / 12 | pointer | 53.005 | 462.563 / 1958.660 | historical control |

All workers in the pointer controls are busy near 4.1 GHz. RXQ spread stays
below 0.43%, every worker QP is active and dedicated, and the main QP is
inactive. The following controls do **not** move the pointer ceiling:

- one, two or four independently owned TX QPs per worker;
- one CQE request every 1–32 eMPW doorbells;
- 2k–16k outstanding-buffer rings;
- q2/q4/q8 receive fan-out with balanced RSS;
- `BALANCED` versus `AGGRESSIVE` firmware policy;
- dedicated BF/UAR resources, larger descriptors or additional source rate.

The decisive TX-only A/B changes only packet representation. At four workers,
pointer / inline-retained / inline-immediate-free produces 68.868 / 140.816 /
145.862 Mpps. Thus external per-packet buffer reads—not RX dispatch, QP count
or CQE cadence—are the primary cause. Immediate free adds 3.6% over retained
inline and is secondary.

The L3 series sustains 60.893/109.049/124.564/122.867 Mpps at 2W/4W/5W/6W.
The 5W winner uses q20, four RX queues per worker; q12 is retained at 6W because
its individual RXQ spread is 0.461%, while faster q18/q24 screens exceeded the
strict per-RXQ fairness threshold. Priority-buffer and software-pressure
counters make these MRR rather than NDR. A separate 4W 91.282-Mpps control has
zero in both domains.

The per-TXQ adaptive follow-up is a negative result: 10/128 backlog hysteresis
oscillated roughly 250,000 times per TXQ in six seconds and reduced CX6 4W/q4
to 49.2 Mpps. The retained prototype therefore exposes only explicit OFF or
full-inline/immediate-free ON; adaptive figures are excluded.

### DPDK scale-out

The canonical true64 finals use RXD512/TXD2048, a separate main core, inactive
main TXQ0, one exclusive TXQ per worker, weighted RETA and AGGRESSIVE firmware.
Inline is explicitly off at 1W and explicitly on from 2W upward.

| Workers | RXQ | TXQ/worker | Total TXQ | Physical TX | Worker cpp | Spread |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2 | 1 | 2 | 34.800 | 117.4 | 0.95% |
| 2 | 2 | 1 | 3 | 59.308 | 137.8 | 0.062% |
| 4 | 8 | 1 | 5 | 101.838 | 160.5 | 0.233% |
| 5 | 10 | 1 | 6 | 114.891 | 177.8 | 0.035% |
| 6 | 12 | 1 | 7 | 117.260 | 208.9 | 0.094% |

The historical queue-count A/B was confounded by mlx5's default eight-total-
TXQ inline threshold: four workers plus the main used five queues at p1 and
nine at p2. The new crossed A/B forces representation explicitly. At four
workers TX-only, p1/p2 gives 68.440/68.777 Mpps with inline off and
125.006/112.738 with inline on. In L3 q8 it gives 109.108/108.288 with inline
on. Extra TXQs do not increase service rate once inline state is fixed.

Two RX queues per worker do remain useful at four workers and above. The
source supplies about 133.4 Mpps while the six-worker final reaches 117.260.
Testpmd's 111.30-Mpps four-core result still establishes hardware headroom,
but is not evidence that VPP needs more than one TXQ per worker.

### AF_XDP

CX6 retains RX/TX2048 with 1M VPP buffers and the same `W` RX / `W+1` private
TX/XSK ownership used on CX4/CX5. Every socket reports `zc:1`; IRQ/NAPI is
colocated and counted. The selected socket policy is 50 usec busy poll,
prefer mode and budget 16, together with the separately applied 20-usec NAPI
timeout and defer count 8.

| Workers | Physical TX | Worker-CPU cpp | RXQ spread |
|---:|---:|---:|---:|
| 1 | 10.598 Mpps | 382.3 | n/a |
| 2 | 21.275 | 380.5 | ≤0.408% |
| 4 | 40.905 | 396.1 | ≤0.326% |
| 5 | 50.375 | 401.8 | ≤1.816% |
| 6 | 60.578 | 401.0 | ≤2.401% |

The 5W/6W spreads come from the finite hash population and RETA quantization.
A device-filtered 4W trace observed NAPI, refill and TX-completion work only
on worker CPUs 21--24; the asynchronous pool-destroy work item was absent.
Ring-full, allocation and TX shortage counters are disclosed because these
are MRR points, not NDR.

### Firmware policy

In the matched true64 4W control, `BALANCED`/`AGGRESSIVE` produce 86.89/86.81
Mpps for DPDK and 49.62/49.85 for native: less than 0.5% throughput change.
Batching nevertheless changes sharply: DPDK input averages about 60.5 versus
12.2 packets/call and native input about 8.6 versus 2.0. Firmware policy changes
software behavior, but it does not explain the native ceiling in this A/B.

## BlueField-3

BF3 runs VPP on embedded Arm Cortex-A78AE cores. Native uses striding RQ and
eMPW; DPDK uses vector NEON RX, enhanced MPW and fast-free.

| Path | 1W Mpps / cpp | 2W Mpps / cpp | 4W Mpps / cpp | 2W→4W |
|---|---:|---:|---:|---:|
| RDMA-DV | 14.202 / 140.5 | 27.211 / 146.6 | 55.349 / 144.2 | 2.034x |
| DPDK | 10.252 / 194.6 | 21.035 / 189.6 | 42.239 / 189.0 | 2.008x |

At 1W/2W/4W, RDMA-DV forwards 38.5%/29.4%/31.0% more packets and uses
27.8%/22.7%/23.7% fewer worker cycles. The 4W winners use q4. Native retains
RXD256/TXD2048 and one QP per worker; DPDK retains RXD256/TXD512, an inactive
main TXQ and one exclusive TXQ per worker. q8, neighboring rings and a second
DPDK TXQ per worker were lower or imbalanced. All retained RXQ spreads remain
below 1%. Native is a maximum under RX pressure and DPDK is a counter-clean
near-knee point with a 0.20% RX-to-TX gap; neither is NDR. BF3 AF_XDP is outside
scope.

A matched fixed-offer follow-up shows why the CX6 inline prototype cannot be
made unconditional. Across three 12-second windows at a 50-Mpps offer, native
pointer / inline-retained / inline-immediate-free reaches 49.321 / 44.096 /
43.094 Mpps. Worker cost rises from 161.4 to 180.5 and 184.8 cycles per
successful packet. These controls are archived in
[`data/bf3-inline-controls.csv`](data/bf3-inline-controls.csv); their shorter
window means they inform policy but do not replace the headline 3×20 finals.

## Kernel and VPP review provenance

All AF_XDP performance rows use only the submitted mlx5 cyclic-RQ ownership
fix. The v1 discussion and Dragos Tatulea review are in the
[`netdev` thread](https://lore.kernel.org/netdev/20260819151320.64178-1-jtollet@cisco.com/);
the cyclic fix is carried unchanged into
[`[PATCH net v3 0/2]`](https://lore.kernel.org/netdev/cover.1787347981.git.jtollet@cisco.com/),
whose second patch covers the separately validated MPWQE retry path.
No performance number claims an unmodified upstream kernel.

The exact VPP tree and live Gerrit state are recorded in `VPP_CHANGES.md`.
Change 46506 is merged; 45505, 46155 and 46465 have CI Verified +1 at the
article freeze point.
