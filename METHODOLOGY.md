# Methodology

## Scope and publication rule

The benchmark measures VPP forwarding of 64-byte IPv4/UDP Ethernet frames on
ConnectX-4, ConnectX-5, ConnectX-6 Dx and BlueField-3 through:

- native VPP RDMA in mlx5 Direct Verbs (`DV`) mode;
- VPP's DPDK plugin with the mlx5 PMD;
- VPP's AF_XDP plugin in forced native zero-copy mode.

AF_XDP is scoped to the discrete ConnectX adapters. It is not measured on
BlueField-3, without implying that the interface is unsupported there.
CX4 poll-mode paths are qualified at one, two and three workers; the 3W rows
are source-limited. CX5 and BF3 RDMA-DV/DPDK are qualified at one, two, four,
five and six workers. CX5 AF_XDP is qualified at one, two, four, five and six.
ConnectX-6 DPDK is qualified at one, two, four, five and six workers. Native RDMA-DV is
qualified at one, two, four, five and six workers in the headline profile; the
old two-to-six-worker pointer-data-segment plateau is retained separately as a
control. Native uses an inactive main-thread QP and one active thread-local QP
per worker. DPDK uses an inactive main-thread TXQ, one explicitly assigned TXQ
per worker, controlled inline state and weighted-RETA balance. ConnectX-6
AF_XDP is qualified at one, two, four, five and six workers in the strict
all-in CPU layout.

Only rows repeated on the frozen exact VPP tree may have numeric values in the
public result matrix. Missing or withdrawn cells are never filled from an
older run or interpreted as zero throughput. AF_XDP measurements are complete
for the exact submitted-but-unmerged kernel fix; upstream applicability keeps
a separate provenance caveat until that fix is accepted.

This is a best-found-configuration study, not a controlled NIC-generation
shoot-out. ConnectX-4 uses a Skylake Xeon Gold 6146, ConnectX-5 a Cascade Lake
Xeon Gold 6248R, ConnectX-6 Dx a Sapphire Rapids host with PCIe 4, and
BlueField-3 its embedded Arm cores. Mpps describes each complete platform.

## Workload

- Frames are 64 bytes including FCS at the MAC counter. VPP PG creates a
  60-byte buffer and the NIC appends the four-byte FCS.
- Each retained window must show
  `tx_bytes_phy / tx_packets_phy = 64.000` independently at both source and
  DUT. The DUT ratio proves forwarded frame size; the source ratio proves the
  offered traffic itself is true Ethernet64.
- The DUT performs a same-physical-port L3 hairpin: IPv4 lookup, TTL decrement,
  checksum update, adjacency rewrite and physical retransmission.
- This is neither a receive-only workload nor a two-port patch.
- One to six physical VPP worker cores are used where the platform and source
  provide headroom. SMT siblings are avoided. The
  always-present VPP main thread uses another core and is measured separately.
- Within a platform, generator hardware, software and balanced-flow
  construction are unchanged across DUT paths.
- Offered load is swept around each path's knee and retained above the measured
  DUT rate; it is not fixed to one common overload value.
- Per-queue and per-worker deltas prove that all configured queues are active.
  Aggregate load per worker is the primary fairness boundary when one worker
  polls several RX queues; individual-queue spread is retained and disclosed
  separately so finite source-flow quantization cannot be mistaken for worker
  imbalance.

## Placement evidence per cell

Placement is a measured or explicitly code-proven part of a cell. Every
retained cell must archive and publish, in anonymized form:

- the VPP main thread, its logical CPU and NUMA locality, separately from all
  dataplane workers;
- each worker's VPP thread index, logical CPU, physical-core/SMT status and
  NUMA locality;
- every RX queue mapped through `RXQ -> worker -> VPP thread -> CPU`, including
  the resulting number of queues polled by each worker;
- every transmit resource mapped through `TXQ or QP -> producer VPP thread ->
  worker/main -> CPU`, plus whether the resource is dedicated or shared;
- for AF_XDP, the XSK corresponding to each RX queue and proof that its
  effective IRQ/NAPI CPU is the owning VPP worker CPU;
- per-queue and per-worker packet deltas used to quantify balance.

The evidence set includes `show threads`, `show rx-placement` and the driver's
hardware-detail TX ownership before and after each window, along with NUMA and
effective IRQ-affinity snapshots where applicable. Older native artifacts do
not expose numeric QPN/CQN identifiers; in those cells the ledger states that
limitation and relies only on the plugin's one-thread-local-QP construction,
never on an invented numeric identifier or an unmeasured main-QP counter.
Queue numbering is not assumed to follow worker numbering, and multiple RX
queues per worker are allowed when they win the independent screen.

The native driver allocates one thread-local transmit QP for every VPP thread,
including the main thread. For DPDK, a retained configuration must likewise
provide enough TX queues for the main thread plus one dedicated queue per
forwarding worker, then prove the actual mapping. A shared flag is recorded
even when the main thread sends no packets in the forwarding graph.

Missing placement evidence is written literally as `not_recorded`. Such a
cell can document an observation or rejected control, but it cannot support a
final scaling or root-cause claim. `data/configurations.csv` is the canonical
per-cell placement ledger.

## Throughput and qualification

Throughput is successful physical DUT TX packets divided by the same timed
interval used for CPU counters. VPP's software TX counter is not used because
it may include unsuccessful attempts under overload.

Final values are normally the mean of three independent 20-second windows.
`throughput_sd_mpps` is their population standard deviation. Short screens
select queue count, rings, buffers, coalescing and offered load; they are never
substituted for the final mean.

Older exploratory campaigns used VPP PG `size 64`, meaning 64 bytes before
FCS. Physical counters show 68.000 bytes per MAC frame. Those observations may
be retained only as explicitly labelled 68-byte controls; they cannot populate
the true-Ethernet64 result matrix or select a winner without re-screening.

PAUSE and PFC are disabled during retained windows, and physical PAUSE deltas
must remain zero. Physical/driver errors, RX discards, XSK ring-full events and
TX-slot pressure are retained in the qualification. Every retained AF_XDP
comparison keeps IRQ/NAPI work inside the declared worker CPU budget. Runs
using separate IRQ/NAPI CPUs are diagnostic throughput ceilings only: they are
excluded from the result matrix, scaling graphs and cross-driver comparisons.

### Receive-loss counter domains

For DPDK results, `rx-miss` (also exposed by some PMD views as
`rx_missed_errors`) is a PMD/NIC counter for frames hardware could not deliver
to an RX queue because no receive descriptor was available. Such a frame never
enters the VPP graph. It must not be described as, or silently combined with:

- a VPP graph drop, which occurs after successful delivery to VPP;
- a VPP/driver TX no-free, no-slot or drop event;
- `rx_prio*_buf_discard` or another physical ingress-congestion counter;
- `rx_out_of_buffer`, a separately exposed receive-buffer-starvation view whose
  possible overlap with `rx-miss` must be checked for that counter provider;
- RSS imbalance, which describes distribution across queues rather than loss;
- a CPU cache miss, which is an unrelated microarchitectural event.

A retained run with nonzero `rx-miss` can be labelled a saturated maximum or
MRR: it demonstrates that the source offered traffic beyond the receive path's
accepted rate. It can never be labelled NDR or strict zero-loss. The canonical
throughput remains successful physical DUT TX. The raw `rx-miss` delta and its
rate over the same window are reported separately; counters from PMD, NIC,
VPP and physical-priority domains are not added unless their definitions and
non-overlap have been established. This prevents double-counting counters
which may observe different stages—or overlapping views—of the same pressure.

The CX6 DPDK scaling rows are maximum/MRR results. Nonzero `rx-miss` proves
offered-load headroom but disqualifies NDR; its counter domain remains separate
from successful physical TX.

## CPU accounting

The CSV distinguishes three scopes:

- `dataplane_*`: CPU-wide counters for the declared VPP worker CPUs; for
  AF_XDP they include all colocated IRQ/NAPI kernel work;
- `main_*`: the separate VPP main core;
- `system_*`: dataplane plus main where the source retained all components.

Retained rows always have `extra_irq_cpus=0`. The separately pinned main
thread is common to all compared drivers and is disclosed independently; no
other CPU may service the retained dataplane. IRQ-affinity and per-CPU
softirq deltas are checked so that an AF_XDP run which migrates work outside
the declared worker set is rejected.

The final CX6 boundary was also checked with device-filtered tracepoints and
kprobes for NAPI, cyclic RX refill, XSK batch allocation, TX completion and
`xsk_tx_completed()`. All packet-path events stayed on the declared worker
CPUs. The deferred pool-release work item was absent during the measurement;
it is a socket-teardown path rather than per-packet descriptor recycling.

For two workers, cycles or instructions per packet is the sum of both worker
counters divided by successful physical TX packets, not one worker's value.
The main cost is never silently folded into that number.

Because workers poll continuously,
`cycles/packet * packets/second = counted cycles/second` is an accounting
identity. It includes empty polling and stalls and is not, by itself, proof of
useful saturation.

## Software provenance

The frozen VPP integration revision is
`83d45adb1b624d66ed09c90ba7e0f1484b89587e`, tree
`00e03df873befc01bb7fdfcc5f800b0a0ebc595f`. It contains the exact review
revisions listed in [`VPP_CHANGES.md`](VPP_CHANGES.md), including the native
eMPW path and RX CQ doorbell byte-order fix. The build uses DPDK 26.03 and
rdma-core 62.0.

The CX6 2W/5W/6W full-inline results use one local integration whose output
path is byte-identical to Gerrit 46540 PS2 (plugin SHA-256
`5aebb732f1e5ca5997bbf75f3ad67f4d5572dfa85796c0e38f366de264622249`).
The 4W causal/final artifact uses the earlier isolated prototype implementing
the same complete-packet copy and immediate buffer release. The feature
defaults off. A per-TXQ adaptive follow-up measured posted-minus-completed
backlog independently, but its hysteresis oscillated and regressed throughput;
it was rejected and no adaptive mode is used for a retained result.

The CX4 1W/2W and CX5 4W/5W/6W native descriptor requalifications add only an
experimental setup-time change which accepts power-of-two RX rings from 128
entries instead of tying the minimum to `VLIB_FRAME_SIZE` (256). Refill remains
bounded by `min(VLIB_FRAME_SIZE, ring_space)` and CQ polling cannot return more
entries than the CQ contains. RXD64 controls were rejected. The public rows
remain provisional until that independent validation change is reviewed.

ConnectX-4 does not advertise enhanced MPW and therefore exercises native
legacy SEND. The retained ConnectX-5, ConnectX-6 Dx and BlueField-3 native
rows exercise eMPW.

ConnectX-4 DPDK hardware-detail snapshots report `No MPW + ... + INLINE` and
the `mlx5_tx_burst_sci` burst function. Its retained DPDK rows therefore use
classic SEND with inline, not MPW; `txq_inline_mpw=1` was requested in the
devargs but was not the selected runtime transmit path.

Retained firmware is 12.26.4012 on ConnectX-4, 16.25.8000 on ConnectX-5,
22.41.1000 on ConnectX-6 Dx and 32.49.1014 on BlueField-3. The CX6 global
CQE-compression policy remains `AGGRESSIVE` for both paths; it is not changed
between cells.

The separate ConnectX-4 traffic source uses an Intel XL710 with NVM 7.00,
management firmware 7.1, the Linux 6.8 i40e driver and DPDK 24.11.1. A
direct-PF control proves 40-Gbit/s wire rate at true128. The synchronized
true64 traffic-generator ceiling control for the retained three-worker
campaign reached 42.634 Mpps; the final source means were 42.205 Mpps for
RDMA-DV and 42.214 Mpps for DPDK. This 42.2--42.6-Mpps provenance is why the
CX4 3W poll-mode values are marked as lower bounds; no firmware update was
attempted as part of the measurement. CX4 AF_XDP is retained through three
workers with IRQ/NAPI colocated on those workers and a private TX-only XSK on
the main thread; it uses no additional packet-service core.

AF_XDP is forced with `XDP_ZEROCOPY`, and the kernel
`XDP_OPTIONS_ZEROCOPY` flag is checked independently on every socket. The
AF_XDP rows use the cyclic-RQ fix submitted to `netdev` as `[PATCH net v2]`,
Message-ID `<20260820151558.11015-1-jtollet@cisco.com>`, and carried unchanged
as patch 1 of the submitted
[`[PATCH net v3 0/2]`](https://lore.kernel.org/netdev/cover.1787347981.git.jtollet@cisco.com/)
series. V3 adds the separately validated analogous MPWQE retry fix. The v1
review thread is `<20260819151320.64178-1-jtollet@cisco.com>`. These rows are
not claims about an unmodified upstream kernel.

The archived v2 patch has SHA-256
`066ec4397dbfab3f6cfd0ca3832b5dafb5aef4d9238bb8ad1923854fb7a9ceb1`.
The final ConnectX-5 AF_XDP runs loaded the fix-only mlx5 module with SHA-256
`47c26e47a131a428812c7f2ddcea863eeb00d827a13182ccb5b8f1f1ddb88a37`
and source version `2ED3DC341CCEF2DB5EF31E5`.

The ConnectX-4 AF_XDP rows use the same one-file fix on its distribution
kernel. The loaded module has SHA-256
`3b37f23734a53750fcab1d92257fa7639c3c039e3d784bfee674f214a74fe28d`
and source version `B3E49A83D4B7857FE12932F`.

## Parameter search

The following dimensions are screened independently for every
hardware/path/worker combination:

- RX queue count and explicit queue-to-worker placement;
- TX queue count and shared versus unshared ownership;
- RX/TX descriptor depth;
- VPP buffer count and data-area size;
- RSS selector, Toeplitz flow population and measured queue balance;
- cyclic/striding receive queues and multi-packet receive modes;
- CQE compression and applicable firmware policy;
- transmit batching, inline threshold and enhanced-MPW controls;
- DPDK vector/scalar RX and mbuf fast-free;
- AF_XDP per-XSK RX/TX/fill/completion rings, UMEM size, wakeup locking,
  coalescing and IRQ/NAPI placement;
- NUMA locality, physical-core placement, SMT and CPU frequency;
- offered load, flow count, MTU and flow-control state.

The final winner is accepted only after the chosen queue count is re-created
with the full placement evidence above. In particular, `workers + 1` is the
minimum transmit-resource count for a DPDK cell because the VPP main thread is
also provisioned; the observed TXQ mapping, rather than the requested count,
is authoritative.

The native plugin also has a generic libibverbs compatibility path and an
automatic selection mode. Peak native results explicitly use `mode dv`; IBV is
not part of the benchmark.

Winners and the explicit out-of-scope cell are in `data/configurations.csv`. “Best”
means best found in the documented search, not proof of a global optimum for
every firmware, CPU, graph or traffic mix.

## Anonymization

The public package contains only aggregate measurements and generic hardware
descriptions. It excludes lab hostnames/logins, addresses, MACs, PCI BDFs,
serial numbers, internal URLs, topology names, remote paths and raw logs. The
public authorship/review metadata in the exact submitted kernel patch is the
only intentional email exception.
