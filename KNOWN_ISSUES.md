# Known issues and review code

## AF_XDP legacy cyclic-RQ partial refill

Sustained mlx5 AF_XDP zero-copy overload reproduced a double publication of
one UMEM frame. The standalone libxsk trace isolated the sequence to legacy
cyclic-RQ partial refill:

1. an XDP redirect fails because the userspace RX ring is full and XSK releases
   the buffer;
2. mlx5 later visits that cyclic WQE and releases its buffer before refill;
3. if the batched refill succeeds only partially, the missing WQE retains a
   stale pointer;
4. the buffer can be allocated to another WQE before a later retry releases it
   again through that stale pointer.

The submitted fix marks the fragment as released after the first driver-side
free. The flag is cleared when a replacement buffer is installed, so a later
retry cannot release a live reallocated buffer.

### Controlled A/B

On ConnectX-5 with Linux 7.1.5, the traced stock driver stopped after 2,854,914
packets with 4,542 real RX-ring-full events and 64 ownership/double-publication
errors. With the submitted one-file fix alone, the stress processed 356,904,225
packets and 571,405 RX-ring-full events with no ownership or data error.

The fix-only VPP controls reported native zero-copy on every XSK and showed no
material regression versus the earlier diagnostic workaround. Those controls
used the earlier 68-byte MAC-frame convention and were not reused as final
performance data. Separate true-Ethernet64 requalification completed on
ConnectX-4, ConnectX-5 and ConnectX-6 with three 20-second windows per retained profile,
64.000-byte physical proof at source and DUT, zero-copy proof per XSK and
all-in kernel/userspace CPU accounting. The measurements are final for that
exact build; their applicability to an upstream kernel remains provisional
while review is open.

### Upstream state

The fix was suggested by Daniel Borkmann after review of the reproducer. The
public review history is:

- v1 and Dragos Tatulea's changelog review:
  [`<20260819151320.64178-1-jtollet@cisco.com>`](https://lore.kernel.org/netdev/20260819151320.64178-1-jtollet@cisco.com/)
- submitted `[PATCH net v2]` with Dragos' `Reviewed-by`:
  [`<20260820151558.11015-1-jtollet@cisco.com>`](https://lore.kernel.org/netdev/20260820151558.11015-1-jtollet@cisco.com/)
- archived patch:
  [`patches/mlx5-af-xdp-partial-refill-double-release-fix.patch`](patches/mlx5-af-xdp-partial-refill-double-release-fix.patch)

It remains under upstream review at the time of writing. Dragos requested a
shorter reordered problem statement and explicit confirmation that the silent
failure produces no warning or splat; he requested no code change. The v2
implements those nits and adds his `Reviewed-by`. AF_XDP rows are therefore
labelled “with submitted fix”; they are not claims about an unmodified or
already-fixed upstream kernel. The diagnosis is scoped
to the reproduced legacy cyclic-RQ path and does not automatically generalize
to striding RQ, multi-buffer traffic or unrelated drivers.

## Native enhanced Multi-Packet WQE

The native VPP RDMA-DV test tree adds an enhanced Multi-Packet WQE path for
hardware which advertises that capability. Compatible packets are grouped in
one session. An incompatible packet closes the current session and uses the
existing SEND fallback; a following compatible run may open a new eMPW
session.

ConnectX-5, ConnectX-6 Dx and BlueField-3 advertise eMPW. ConnectX-4 does not
and automatically remains on legacy SEND. The implementation is VPP Gerrit
change 46465 and is review code, not yet a released-version feature. Exact
status and tested revisions are recorded in [`VPP_CHANGES.md`](VPP_CHANGES.md).
