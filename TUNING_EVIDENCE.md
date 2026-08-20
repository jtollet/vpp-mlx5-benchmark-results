# Tuning evidence

This document keeps the selection evidence behind the article. Short screens
choose a configuration; only repeated 3×20-second cells populate the public
result matrix. Every retained frame is proven as 64.000 physical bytes at
source and DUT. Older PG `size 64` observations are 68-byte controls and never
select a true64 winner.

Queue fairness is `(max RXQ delta - min RXQ delta) / mean RXQ delta`; retained
multi-queue cells must remain below 1%. Queue count, descriptor depth and
offered load are screened independently per hardware and datapath. “Maximum”
means maximum forwarding under pressure, not zero-loss NDR.

## ConnectX-4

CX4 does not advertise eMPW, so native RDMA-DV uses legacy SEND. One- and
two-worker winners are q2/RXD2048/TXD2048. DPDK independently selects
q1/RXD1024/TXD2048 at one worker and q2/RXD1024/TXD2048 at two. At three
workers, RDMA-DV selects q3/RXD1024/TXD2048 and four QPs including an inactive
main QP. DPDK selects q3/RXD2048/TXD2048 and four TXQs including inactive
main TXQ0.

| Path | 1W | 2W | 3W | 3W qualification |
|---|---:|---:|---:|---|
| RDMA-DV | 15.803 Mpps / 206.6 cpp | 28.983 / 225.3 | 42.166+ / 232.2 | q3; RXQ spread ≤0.159%; source-limited |
| DPDK | 16.349 / 199.6 | 30.141 / 216.7 | 42.213+ / 231.9 | q3; TXQ0 inactive; RXQ spread ≤0.593%; source-limited |
| AF_XDP maximum | 6.139 / 1160.4 | 11.752 / 1210.9 | — | not measured at 3W |

Each 3W winner is a fresh-source 3×20-second result. The final source means
were 42.205 Mpps for RDMA-DV and 42.214 Mpps for DPDK; a synchronized source
revalidation reached 42.634 Mpps. Both DUT rates are therefore source-limited
lower bounds, and their cycles include idle polling at the offered boundary.
All three RX queues are active and balanced. Native main TQ0 and DPDK TXQ0
remain inactive; the three worker QPs/TXQs exclusively carry the traffic.

The synchronized direct-PF revalidation measured 42.634 Mpps source TX and
42.640 Mpps at the CX4 physical RX counter. A separate true128 control reached
40.060 Gbit/s after wire overhead. Thus the source reaches 40-Gbit/s line rate
with larger frames but not the true64 packet rate required to move the 3W
lower bound. The controls used NVM 7.00, management firmware 7.1, Linux i40e
from the 6.8 kernel and DPDK 24.11.1; no firmware update was performed during
the benchmark.

Historical four-worker runs remain diagnostic artifacts only and do not feed
the article table, public CSV or main charts. They also stopped at the source
boundary (42.821/42.818 Mpps for RDMA-DV/DPDK), so adding a fourth worker did
not establish either DUT ceiling. A separate four-XSK AF_XDP experiment is
likewise excluded from the headline matrix; no three-worker AF_XDP final was
run, and no four-worker result is substituted for it.

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

Every XSK independently proves native zero-copy. Strict rows colocate IRQ/NAPI
and count the full worker CPU; maximum rows count separate kernel CPUs.

| Layout | 1W | 2W | 4W | 4W rings |
|---|---:|---:|---:|---|
| strict | 4.992 | 9.485 | 9.698 Mpps | RX4096/TX1024 |
| maximum | 6.416 | 12.437 | 14.021 Mpps | RX4096/TX1024; four IRQ CPUs |

At 4W, q4 is balanced below 0.54% strict and 0.02% maximum; q8 is rejected.
RX4096/TX1024 and RX512/TX4096 both help short screens. The combined
RX4096/TX4096 configuration falls to 13.22/13.87/13.90 Mpps over 3×20 seconds.
Buffers from 524k to 2M, coalescing 0/0 to 32 usec/512 frames and the legacy
syscall lock do not yield a monotonic sustained gain. Deeper rings delay
pressure; they do not raise service rate.

The 4W maximum uses four workers plus four IRQ CPUs and costs about 1692
all-in cycles per successful packet. Input/L3/TX vectors fall relative to 2W,
while userspace plus kernel cost rises. This—not an inactive queue—explains
the weak 2W→4W AF_XDP scaling.

## ConnectX-6 Dx

### Native RDMA-DV

The one- and two-worker rows are the retained clean finals. The four-to-six
worker rows are controlled maximum-under-pressure finals with source headroom;
all use native eMPW, no-striding and no-multi-seg:

| Workers / RXQ | Physical TX | Worker cpp / ipp | Input / L3 / TX vectors |
|---|---:|---:|---:|
| 1 / 4 | 45.370 Mpps | 90.153 / 316.801 | 279 / 214 / 251 |
| 2 / 4 | 52.814 | 154.925 / 562.506 | 34 / 70 / 73 |
| 4 / 8 | 53.233 | 307.075 / 1242.695 | 32 / 62 / 61 |
| 5 / 10 | 53.445 | 382.337 / 1584.736 | 31 / 63 / 60 |
| 6 / 12 | 53.005 | 462.563 / 1958.660 | 33 / 62 / 58 |

All workers are busy near 4.1 GHz. RXQ spread stays below 0.43% through six
workers, every worker QP is active and dedicated, and the main QP is inactive.
Aggregate work per successful packet rises with worker count while throughput
stays around 53 Mpps. The following causal controls do **not** move the native
ceiling:

- one, two or four independently owned TX QPs per worker;
- one CQE request every 1–32 eMPW doorbells;
- 2k–16k outstanding-buffer rings;
- q2/q4/q8 receive fan-out with balanced RSS;
- `BALANCED` versus `AGGRESSIVE` firmware policy;
- dedicated BF/UAR resources, larger descriptors or additional source rate.

The remaining gap is localized to added work inside the multi-worker
raw-QP/eMPW implementation. Smaller batches are observed at the same time, but
are not yet proven to initiate the extra work. The gap is not assigned to one
source line.

### DPDK scale-out

The canonical true64 finals use RXD512/TXD2048, a separate main core, inactive
main TXQ0, exclusive worker TXQs, weighted RETA and AGGRESSIVE firmware.

| Workers | RXQ | TXQ/worker | Total TXQ | Physical TX | Worker cpp | Spread |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2 | 1 | 2 | 34.800 | 117.4 | 0.95% |
| 2 | 2 | 4 | 9 | 54.998 | 148.6 | 0.14% |
| 4 | 8 | 2 | 9 | 101.198 | 161.5 | 0.28% |
| 5 | 10 | 2 | 11 | 113.048 | 180.7 | 0.10% |
| 6 | 12 | 2 | 13 | 115.625 | 212.0 | 0.12% |

At four fixed workers and q4, changing only TXQ/worker from one to two to four
raises TX from 53.03 to 93.28 to 93.87 Mpps. This proves a TXQ service effect.
At six workers, q12 (two RXQ/worker) beats q6 (one RXQ/worker), about 115.6
versus 102.2 Mpps. The source supplies 133.432 Mpps during the 6W final.

Testpmd confirms the queue-topology effect: q4/q8/q16 on four cores produces
48.42/93.49/111.30 Mpps as each core moves from one to two to four RX/TX queue
pairs. The original 53-versus-116 comparison was invalid because VPP had one
active TXQ per worker while testpmd had four pairs per core.

### AF_XDP

CX6 uses four active XSKs for the maximum rows and for strict 2W. Rings are
8192/8192 with 1M VPP buffers. Every socket reports `zc:1`.

| Layout | 1W | 2W | Dataplane CPU budget at 2W |
|---|---:|---:|---|
| strict | 8.482 | 15.616 Mpps | two worker CPUs including colocated IRQ/NAPI |
| maximum | 17.797 | 33.367 Mpps | two workers plus four IRQ/NAPI CPUs |

Physical/RSS input spread remains below 0.029%. Ring-full, allocation and TX
shortage counters are disclosed because these are MRR points, not NDR.

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

## Kernel and VPP review provenance

All AF_XDP performance rows use only the submitted mlx5 cyclic-RQ ownership
fix. The v1 discussion and Dragos Tatulea review are in the
[`netdev` thread](https://lore.kernel.org/netdev/20260819151320.64178-1-jtollet@cisco.com/);
the revised submission is
[`[PATCH net v2]`](https://lore.kernel.org/netdev/20260820151558.11015-1-jtollet@cisco.com/).
No performance number claims an unmodified upstream kernel.

The exact VPP tree and live Gerrit state are recorded in `VPP_CHANGES.md`.
Change 46506 is merged; 45505, 46155 and 46465 have CI Verified +1 at the
article freeze point.
