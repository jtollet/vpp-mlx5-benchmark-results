# Methodology

## Scope

The benchmark measures VPP IPv4 forwarding of 64-byte Ethernet frames using
three Linux-facing device paths on NVIDIA/Mellanox hardware:

- the native VPP RDMA driver in direct-verbs (`DV`) mode;
- the VPP DPDK plugin with the mlx5 PMD;
- the VPP AF_XDP plugin in forced native zero-copy mode.

ConnectX-4, ConnectX-5, ConnectX-6 Dx and BlueField-3 were tested. AF_XDP on
BlueField-3 was intentionally excluded.

This is a best-found-configuration study, not a generational NIC shoot-out.
ConnectX-4 and ConnectX-5 use the same Skylake CPU family. ConnectX-6 Dx uses
a newer Sapphire Rapids host and PCIe 4. BlueField-3 runs VPP on its embedded
Arm cores. Raw Mpps therefore describe each complete platform; cycles per
packet provide the more useful software-efficiency comparison.

## Workload

- 64-byte IPv4/UDP Ethernet frames, including FCS on the wire.
- Same-port L3 forwarding: IPv4 lookup, TTL decrement, checksum update,
  adjacency rewrite and physical retransmission.
- One or two VPP dataplane workers. The always-present VPP main thread is
  measured separately when the source record retained its counters.
- An external, overprovisioned generator. Within a platform, generator
  hardware, software, flow set and offered load are held constant across DUT
  drivers.
- Multiple UDP flows selected so every configured RX queue was active. RSS
  and worker balance were verified from per-queue and per-thread deltas.

GSO/TSO was not used. It changes the workload to TCP segmentation and did not
improve the generator used for the comparable UDP64 matrix.

## Measurement

The retained values are normally the mean of three independent 20-second
windows. Short overload screens were used to select parameters but were not
substituted for final means.

Throughput is the successful physical DUT TX packet delta over the same timed
window as CPU counters. VPP's software TX counter was not used because it can
include unsuccessful transmit attempts under overload.

PAUSE and PFC were disabled during retained measurements. Physical PAUSE
deltas were required to remain zero. Hardware/driver errors, RX discards,
XSK ring-full events and TX-slot failures were collected and used to label a
point as a maximum or a clean fixed-rate control. A maximum must not be read
as a formal NDR result.

Cycles and instructions were collected with Linux perf:

- RDMA-DV and DPDK dataplane cost is the sum of the worker threads.
- For strict AF_XDP, IRQ/NAPI executes on the same CPU or CPUs as the VPP
  workers, so CPU-wide counters include both userspace and kernel work.
- AF_XDP maximum-PPS controls use separate IRQ/NAPI CPUs; their kernel cost is
  added to the VPP worker cost rather than hidden.
- The VPP main thread is shown separately. It is lightly loaded, but it still
  exists and is not described as a dataplane worker.

## Software

The final native-driver tree corresponds to a VPP 26.10 development snapshot
with DPDK 26.03 and rdma-core 62.0. Native eMPW results use the change under
review as [VPP 46465](https://gerrit.fd.io/r/c/vpp/+/46465), plus its published
dependencies. ConnectX-4 does not expose enhanced MPW and therefore exercises
the legacy SEND path.

AF_XDP results use forced `XDP_ZEROCOPY`; every retained socket reported the
kernel `XDP_OPTIONS_ZEROCOPY` flag. They also use a temporary candidate mlx5
ownership fix described in `KNOWN_ISSUES.md`. These numbers are not a claim
about an unmodified upstream kernel.

## Parameter search

The following dimensions were screened independently for each hardware and
driver combination:

- RX queue count and explicit queue-to-worker placement;
- TX queue count and whether a queue was shared;
- RX and TX descriptor depth;
- VPP buffer pool size and data size;
- RSS protocol selector, Toeplitz flow population and measured balance;
- cyclic versus striding RQ, DPDK MPRQ and multi-segment handling;
- CQE compression, including the ConnectX-6 firmware policy;
- legacy SEND, enhanced MPW, inline threshold and TX MPW controls;
- DPDK vector/scalar RX and mbuf fast-free;
- AF_XDP XSK rings, UMEM size, syscall lock, MAC reuse, coalescing and
  IRQ/NAPI placement;
- NUMA locality, physical-core/SMT placement and CPU frequency;
- offered load, flow count, MTU and flow-control state.

The winners are in `data/configurations.csv`. “Best” means the best retained
point in this documented search, not proof of a global optimum for every
firmware, CPU, VPP graph or traffic mix.

## Anonymization

This public package contains only aggregate measurements and generic hardware
descriptions. It deliberately excludes hostnames, usernames, IP subnets,
MAC addresses, PCI BDFs, serial numbers, internal URLs, remote filesystem
paths and raw logs.
