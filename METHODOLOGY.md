# Methodology

## Scope

The benchmark compares three VPP datapaths for same-port IPv4 forwarding of
physical 64-byte Ethernet frames:

- native VPP RDMA in mlx5 Direct Verbs (`DV`) mode;
- VPP's DPDK plugin with the mlx5 PMD;
- VPP's AF_XDP plugin in forced native zero-copy mode.

ConnectX-4, ConnectX-5 and ConnectX-6 Dx exercise all three paths. BlueField-3
exercises RDMA-DV and DPDK; AF_XDP is outside the study scope on that platform.
The CPU and microarchitecture of each complete platform are recorded in
[`data/platforms.csv`](data/platforms.csv). Results across NIC generations are
therefore platform results, not a controlled NIC-only comparison.

Each driver is independently tuned for its best qualified configuration. The
search covers queue count, descriptor depth, buffer count, RSS distribution,
NUMA and CPU placement, receive mode, transmit batching, inline policy and the
applicable AF_XDP kernel controls. “Best” means best found in this search, not
proof of a global optimum for every workload or software version.

## Workload and throughput

- The DUT routes IPv4/UDP traffic back through the same physical port. Every
  successful packet crosses IPv4 lookup, TTL decrement, checksum update,
  adjacency rewrite and physical retransmission.
- The generator supplies 60 bytes and the NIC appends the four-byte FCS. Source
  and DUT counters must independently report exactly 64 physical bytes per
  packet.
- Final values are normally the mean of three independent 20-second windows.
- Throughput is successful physical DUT TX, not VPP's software TX-attempt
  counter.
- Offered load is set above the measured DUT rate. Saturated points are maximum
  forwarding rate (MRR), not zero-loss NDR. A source-limited point is explicitly
  marked as a lower bound.
- PAUSE/PFC is disabled. Physical errors, discards, RX shortages, XSK ring
  pressure and TX backpressure are retained in the qualification field rather
  than folded into throughput.

For DPDK, `rx-miss` identifies traffic the NIC could not deliver because an RX
descriptor was unavailable. It is distinct from VPP graph drops, TX pressure,
RSS imbalance and CPU cache misses. A nonzero value is acceptable for an MRR
point but not for an NDR claim.

## CPU and queue accounting

Workers run on distinct physical cores without SMT siblings. The VPP main
thread uses another core and is reported separately. Dataplane cycles per
packet are the sum of CPU-wide counters on all declared worker CPUs divided by
successful physical TX packets.

For AF_XDP, mlx5 IRQ, NAPI, XDP and XSK work is colocated on those same declared
CPUs and is included in the CPU totals. Retained rows use no auxiliary IRQ,
NAPI, busy-poll or recycling CPU. Affinity, per-CPU softirq counters and a
device-filtered trace validate this accounting boundary.

Queue ownership is part of every retained cell:

- native RDMA-DV provisions one thread-local QP per VPP thread, including an
  inactive main-thread QP;
- DPDK provisions an inactive main TXQ plus one exclusive TXQ per worker;
- AF_XDP uses one RX socket per active RX queue and an additional private
  TX-only socket for the main thread.

The RXQ-to-worker relation, transmit ownership, queue depths, NUMA relation and
measured fairness are published in
[`data/configurations.csv`](data/configurations.csv). A row lacking placement
evidence cannot be used as a final scaling result.

## mlx5 transmit modes

ConnectX-5, ConnectX-6 Dx and BlueField-3 expose enhanced Multi-Packet WQEs
(eMPW). ConnectX-4 does not and uses legacy SEND. Native full-packet eMPW inline
is disabled by default and controlled device-wide with a size limit. The
qualified CX6 cells from two workers upward enable it for packets up to 60
bytes; BF3 retains pointer data segments because forced inline regresses there.

The matched CX6 TX-only pointer/inline controls are in
[`data/cx6-inline-causal.csv`](data/cx6-inline-causal.csv). The BF3 controls
which demonstrate that inline is not a universal policy are in
[`data/bf3-inline-controls.csv`](data/bf3-inline-controls.csv).

Descriptor depth is tuned rather than maximized. RXD128 is retained where it
improves CX4/CX5, while RXD64 controls are rejected. CX6 firmware `BALANCED`
and `AGGRESSIVE` change batching but differ by less than 0.5% in matched
throughput.

## Data and qualification

[`data/results.csv`](data/results.csv) is the canonical throughput and CPU
dataset. Each row records driver, profile, worker count, throughput, CPU scope,
repeat count and qualification. Missing or withdrawn cells are not interpreted
as zero. [`scripts/check_data.py`](scripts/check_data.py) verifies row identity,
placement, accounting and the numerical claims used by the article.

The figures are generated only from qualified rows and the explicit causal
controls. They can be reproduced with:

```bash
python3 -m pip install matplotlib numpy
python3 scripts/plot_results.py
```

## Software provenance

The frozen VPP integration revision is
`83d45adb1b624d66ed09c90ba7e0f1484b89587e`, with source tree
`00e03df873befc01bb7fdfcc5f800b0a0ebc595f`. It uses DPDK 26.03 and rdma-core
62.0. The public VPP reviews are linked from the published article.

AF_XDP results use the submitted mlx5e ownership fix. The public
[`netdev v3 series`](https://lore.kernel.org/netdev/cover.1787347981.git.jtollet@cisco.com/)
covers cyclic-RQ and MPWQE refill retries. These measurements describe the
tested patched kernel and remain provisional until the fix is upstream.

## Privacy

The repository contains curated aggregate data only. It excludes raw lab logs,
hostnames, login names, IP and MAC addresses, PCI addresses, serial numbers,
internal URLs, remote paths and topology identifiers. Public project links and
public patch authorship embedded in the netdev URL are intentionally retained.
[`scripts/check_anonymization.py`](scripts/check_anonymization.py) enforces this
boundary.
