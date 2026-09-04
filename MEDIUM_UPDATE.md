# Medium article update — September 4, 2026

Article: [Three VPP datapaths for NVIDIA ConnectX and BlueField](https://medium.com/fd-io-vpp/three-vpp-datapaths-for-nvidia-connectx-and-bluefield-309c0124019d)

Apply these edits in place instead of appending the complete update after the
glossary:

1. Insert the dated update immediately before “This work produced the
   following patches”.
2. Replace the old four-item VPP patch paragraph and list.
3. Replace the final sentence which says that the mlx5e series is still under
   review.

The rest of the article, including its architecture, methodology, data tables,
charts and historical performance values, remains unchanged.

## 1. Insert before “This work produced the following patches”

### Update — September 4, 2026

The architecture, methodology, and performance figures below remain valid as
measurements of the frozen source tree used for this article. Since publication,
the mlx5 RDMA-DV series has been checked against the NVIDIA Adapter PRM, tested
by CSIT across several ConnectX generations on x86 and Arm, and simplified for
review.

The RX CQ doorbell fix (46506), AF_XDP refill fix (46547), zero SEND immediate
field fix (46568), and auxiliary mlx5 device support (46668) are now merged.
Full-packet inline change 46540 was folded into the eMPW change 46465. The
remaining RDMA-DV chain is 46609 → 46667 → 46155 → 46465 → 45505; all five
changes currently have Verified +1 and a Code-Review +1 from the CSIT reviewer.

The Linux mlx5e AF_XDP ownership fixes also progressed after publication. The
v4 cyclic-RQ and MPWQE fixes were accepted into `netdev/net` as
[`e01620844c5c`](https://kernel.googlesource.com/pub/scm/linux/kernel/git/netdev/net/+/e01620844c5c88b6fcf819d171df8e3976a0e76f)
and
[`63811edf5125`](https://kernel.googlesource.com/pub/scm/linux/kernel/git/netdev/net/+/63811edf512584c946e5e96b100e9e280703bbb5).

One reproducibility caveat applies to the AF_XDP busy-polling section: its
published figures were measured with 46539 PS1. The current PS5 actively calls
non-blocking `recvmsg()` when the RX queue is empty so the kernel can enter
`sk_busy_loop()`, and its option semantics have changed. The published values
should be read as historical PS1 results until PS5 is benchmarked under the
same conditions.

The exact benchmark revisions and current review mapping are maintained in the
[companion revision ledger](https://github.com/jtollet/vpp-mlx5-benchmark-results/blob/main/VPP_CHANGES.md).

## 2. Replace the old VPP patch paragraph and list with

This work produced VPP changes in three groups:

- RDMA-DV correctness and compatibility: [46506](https://gerrit.fd.io/r/c/vpp/+/46506), [46568](https://gerrit.fd.io/r/c/vpp/+/46568), [46609](https://gerrit.fd.io/r/c/vpp/+/46609), [46667](https://gerrit.fd.io/r/c/vpp/+/46667), [46155](https://gerrit.fd.io/r/c/vpp/+/46155), and [46668](https://gerrit.fd.io/r/c/vpp/+/46668).
- RDMA-DV performance and TSO: [46465](https://gerrit.fd.io/r/c/vpp/+/46465) and [45505](https://gerrit.fd.io/r/c/vpp/+/45505).
- AF_XDP busy polling and refill correctness: [46539](https://gerrit.fd.io/r/c/vpp/+/46539) and [46547](https://gerrit.fd.io/r/c/vpp/+/46547).

The benchmark numbers remain tied to the tested patch sets listed in the
companion revision ledger, not automatically to each change's latest patch set.

## 3. Replace the final sentence of the mlx5 AF_XDP kernel-bug section with

The benchmark used the public
[`v3 series`](https://lore.kernel.org/netdev/cover.1787347981.git.jtollet@cisco.com/).
Its revised v4 successor has since been accepted into `netdev/net` as the
[cyclic-RQ fix](https://kernel.googlesource.com/pub/scm/linux/kernel/git/netdev/net/+/e01620844c5c88b6fcf819d171df8e3976a0e76f)
and the
[MPWQE fix](https://kernel.googlesource.com/pub/scm/linux/kernel/git/netdev/net/+/63811edf512584c946e5e96b100e9e280703bbb5).
