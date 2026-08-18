# Tuning evidence

This file records representative parameter-selection evidence behind the
winner table. Values in this file are short screens unless explicitly marked
as a three-run final. They select configurations; they are not mixed into the
published final means.

## DPDK was not left at defaults

All DPDK finals used DPDK 26.03's mlx5 PMD. Runtime inspection confirmed the
intended vector receive and enhanced-MPW transmit functions on capable
hardware. `no-rx-cksum` was not enabled: removing RX checksum processing was
not assumed to be a performance optimization.

Representative screens:

| Platform | Dimension | Observed physical TX (Mpps) | Decision |
|---|---|---:|---|
| CX4, 1 worker | RX queues 1 / 2 / 4 | 16.383 / 15.410 / 13.787 | q1 |
| CX4, 2 workers | RX queues 2 / 4 / 8 | 30.410 / ~28.57 / ~24.81 | q2 |
| CX4, 2 workers | mbuf fast-free | reproducibly slower when enabled | disabled |
| CX5, 1 worker | RX queues 1 / 2 / 4 | 18.221 / 16.492 / 15.738 | q1 |
| CX5, 1 worker | RXD/TXD candidates | 256/512, 512/512, 1024/512, 1024/1024, 2048/1024, 1024/2048 | 1024/1024 final |
| CX5, 2 workers | CQE compression on / off | 31.38 / 36.26 | off |
| CX5, 2 workers | vector RX off | 27.39 | keep vector RX |
| CX5, 2 workers | MPRQ | 33.82 | keep cyclic/vector winner |
| CX5, 2 workers | fast-free off / winner on | 34.10 / 36.26 | on |
| CX5, 2 workers | RX queues 2 / 4 / 8 | 36.26 / 33.41 / 28.07 | q2 |
| CX6, 1 worker | RX queues 1 / 2 / 4 | 32.964 / 36.925 / 32.982 | q2 |
| CX6, 2 workers | RX queues 2 / 4 / 8 / 16 | 50.29 / 50.85 / 50.43 / 46.52 | q4 |
| CX6, 2 workers | CQE compression off | 47.41 | keep compression on |
| CX6, 2 workers | scalar RX / MPRQ | 43.74 / 42.83 | keep vector cyclic RX |
| BF3, 1 worker | RX queues 1 / 2 / 4 | 10.404 / 7.962 / 6.278 | q1 |
| BF3, 2 workers | RX queues 2 / 4 / 8 | 21.496 / 16.296 / 12.797 | q2 |
| BF3, 2 workers | CQE compression off / on | 20.589 / 21.859 | on |
| BF3, 2 workers | vector RX off / on | 18.878 / 21.859 | on |
| BF3, 2 workers | fast-free off / on | 21.074 / 21.859 | on |
| BF3, 2 workers | data size 2048 / 1600 | 21.496 / 21.859 | 1600 |

The CX5 two-worker result is a useful warning against universal mlx5 advice:
CQE compression was beneficial elsewhere but disabling it was clearly better
in that exact queue/CPU configuration.

## Native RDMA-DV

Representative native controls include:

- CX4 capability probing rejected enhanced MPW and selected legacy SEND; this
  is a hardware fallback, not a command-line disable.
- CX5 two-worker screens measured about 43.19 Mpps with eMPW versus 24.64
  Mpps with eMPW disabled. Striding and the legacy multisegment path were also
  slower in that 64-byte workload.
- CX6 one-worker q2/q4/q8 with explicit UDP RSS measured 46.263 / 46.389 /
  44.001 Mpps in the queue screen. RXD 512 beat 256 and 1024 for q4.
- BF3 two-worker q2/q4/q8 measured 27.291 / 23.070 / 13.736 Mpps. With q2,
  1600-byte data buffers beat 2048-byte buffers, and a one-million-buffer pool
  won the short screen.
- Mixed eMPW-compatible, ordinary SEND and TSO sequences were validated
  separately. A compatible run after an incompatible packet starts a new
  eMPW session; the fallback does not permanently disable batching.

## AF_XDP

AF_XDP was forced to native zero-copy, and `zc:1` was verified per socket.
The search covered XSK rings, NIC rings, UMEM/VPP buffer count, data size,
syscall lock, coalescing, RSS, queue count and IRQ/NAPI placement.

Two distinct results are deliberately retained:

- `strict`: IRQ/NAPI shares the one or two dataplane CPUs with VPP;
- `maximum`: IRQ/NAPI uses one or two extra physical CPUs and its CPU cost is
  added to the VPP worker cost.

More memory was not a general cure for overload collapse. On CX5 two-worker
screens, 262k/524k/1M buffers produced about 11.42/11.74/11.48 Mpps at the
same knee, and XSK RX depths 1024/2048/4096/8192 likewise had a finite optimum.
On CX4, two million buffers regressed and introduced RX_FULL events. Queue
count was also strongly non-monotonic because every XSK adds polling and ring
management to a fixed worker budget.

## Interpretation boundary

These sweeps support “best found in the documented search.” They do not prove
a global optimum for every firmware, VPP graph, packet size or traffic mix.
The raw screening runs are not published because they contain lab identifiers;
the aggregate values above were transcribed through an anonymization allow-list.
