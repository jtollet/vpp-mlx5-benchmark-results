# Methodology

## Scope and publication rule

The benchmark measures VPP forwarding of 64-byte IPv4/UDP Ethernet frames on
ConnectX-4, ConnectX-5, ConnectX-6 Dx and BlueField-3 through:

- native VPP RDMA in mlx5 Direct Verbs (`DV`) mode;
- VPP's DPDK plugin with the mlx5 PMD;
- VPP's AF_XDP plugin in forced native zero-copy mode.

AF_XDP is scoped to the discrete ConnectX adapters. It is not measured on
BlueField-3, without implying that the interface is unsupported there.
ConnectX-6 RDMA-DV and DPDK are qualified from one through six workers. Native
uses an inactive main-thread QP and one active thread-local QP per worker;
DPDK uses an inactive main-thread TXQ, explicitly assigned worker TXQs and
weighted-RETA balance. ConnectX-6 AF_XDP is qualified at one and two workers
in strict and maximum CPU layouts.

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
- Per-queue and per-worker deltas prove that all configured queues are active
  and that traffic balance stays within the acceptance threshold.

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
- for AF_XDP, the XSK corresponding to each RX queue and the effective
  IRQ/NAPI CPU for both strict and maximum profiles;
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
Short screens select queue count, rings, buffers, coalescing and offered load;
they are never substituted for the final mean.

Older exploratory campaigns used VPP PG `size 64`, meaning 64 bytes before
FCS. Physical counters show 68.000 bytes per MAC frame. Those observations may
be retained only as explicitly labelled 68-byte controls; they cannot populate
the true-Ethernet64 result matrix or select a winner without re-screening.

PAUSE and PFC are disabled during retained windows, and physical PAUSE deltas
must remain zero. Physical/driver errors, RX discards, XSK ring-full events and
TX-slot pressure are retained in the qualification. AF_XDP `maximum` values
are peak forwarding points under offered overload, not formal zero-loss NDR,
and IRQ/NAPI may use separately counted CPUs. `strict` keeps that work inside
the worker CPU budget. The CX4 strict rows are deliberately clean controls at
one common source rate, not maximum-throughput or scaling claims; the CX5
strict rows were swept around their own knees.

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

- `dataplane_*`: VPP worker CPUs for RDMA-DV/DPDK; for strict AF_XDP these are
  CPU-wide counters which already include colocated IRQ/NAPI kernel work;
- AF_XDP maximum adds explicitly counted dedicated IRQ/NAPI CPUs to the
  dataplane scope and records their count in `extra_irq_cpus`;
- `main_*`: the separate VPP main core;
- `system_*`: dataplane plus main where the source retained all components.

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

ConnectX-4 does not advertise enhanced MPW and therefore exercises native
legacy SEND. The retained ConnectX-5, ConnectX-6 Dx and BlueField-3 native
rows exercise eMPW.

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
attempted as part of the measurement. CX4 AF_XDP is retained only at one and
two workers.

AF_XDP is forced with `XDP_ZEROCOPY`, and the kernel
`XDP_OPTIONS_ZEROCOPY` flag is checked independently on every socket. The
AF_XDP rows use the exact mlx5 patch submitted to `netdev` as
`[PATCH net v2]`, Message-ID
`<20260820151558.11015-1-jtollet@cisco.com>`. The v1 review thread is
`<20260819151320.64178-1-jtollet@cisco.com>`. They are not claims about an
unmodified upstream kernel.

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
