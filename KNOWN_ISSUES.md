# Known issues and experimental changes

## AF_XDP zero-copy ownership under RX-ring-full pressure

During saturation, unmodified mlx5 zero-copy runs produced corrupted packet
content in a pattern correlated with AF_XDP RX-ring-full handling. A
standalone libxsk reproducer and driver trace showed evidence consistent with
a buffer ownership/recycling race after `__xsk_rcv_zc()` returned `-ENOBUFS`.

A minimal candidate mlx5 ownership change removed the symptom in the tested
stress cases:

- on ConnectX-5 with Linux 7.1.5, 356.8 million packets and 496 thousand
  RX-full events completed with no ownership/data error in the standalone
  test;
- on ConnectX-4 with Linux 6.8.0-110, each of two sockets experienced
  126.2–126.5 million RX-ring-full events in 20 seconds without a malformed
  packet or data-integrity error after the change;
- retained ConnectX-4/5/6 VPP sockets explicitly reported native zero-copy.

This evidence is not presented as an accepted upstream diagnosis. Kernel
maintainer review is still pending. The public performance rows therefore say
“AF_XDP ZC with candidate fix”, not “stock upstream AF_XDP”.

The exact diagnostic candidate used for this reasoning is published as
[`patches/mlx5-af-xdp-rx-full-ownership-candidate.patch`](patches/mlx5-af-xdp-rx-full-ownership-candidate.patch).
It is intentionally labelled RFC and must not be treated as an upstream fix.

## Native enhanced Multi-Packet WQE

The native VPP RDMA-DV path originally used one legacy SEND WQE per packet on
these tests. [VPP change 46465](https://gerrit.fd.io/r/c/vpp/+/46465) adds an
enhanced Multi-Packet WQE path for hardware which advertises the capability.
Compatible packets are grouped into one eMPW session. An incompatible packet
flushes the current session and is sent through the existing fallback path; a
following compatible run can start a new eMPW session.

ConnectX-5, ConnectX-6 Dx and BlueField-3 exercise eMPW. ConnectX-4 does not
advertise the capability and automatically remains on legacy SEND. The
performance data was collected from review code, not from a released VPP
version, and the article labels it accordingly.
