# Tested VPP revisions

The benchmark uses a frozen integration tree. Gerrit status may evolve, but
the patch sets below identify the code which produced the published data.

| Change | Tested revision | Role |
|---|---|---|
| [45505](https://gerrit.fd.io/r/c/vpp/+/45505) | PS49 `5c594cb70d5a11050d83d04dab6b7c74ab0cd419` | DV TX/WQE accounting foundation |
| [46155](https://gerrit.fd.io/r/c/vpp/+/46155) | PS14 `74b0d8cf33384bf0694dc8530ebfe54f6eb6e9ea` | verbs-port selection |
| [46465](https://gerrit.fd.io/r/c/vpp/+/46465) | PS8 `aa05d22c151516252fbb513a2a882f624326a5b8` | native mlx5 eMPW transmit path |
| [46506](https://gerrit.fd.io/r/c/vpp/+/46506) | PS6 `11a36654d5c34e9879347524a00c919298e3e868` | RX CQ doorbell byte order |
| [46539](https://gerrit.fd.io/r/c/vpp/+/46539) | PS1 `a4d1def8af97cd2e480b0764723dd9a9c9508b0e` | optional AF_XDP socket busy polling |
| [46540](https://gerrit.fd.io/r/c/vpp/+/46540) | PS2 `89f01516b8fe3b468b43caef458e31cb060d0360` | optional full-packet eMPW inline |
| [46547](https://gerrit.fd.io/r/c/vpp/+/46547) | PS1 `017311deddcbd19f3c0e82d5359544d73787ef71` | AF_XDP refill bound for a TX-only main socket |

The benchmark integration revision is
`83d45adb1b624d66ed09c90ba7e0f1484b89587e`, with source tree
`00e03df873befc01bb7fdfcc5f800b0a0ebc595f`. The changes were replayed on one
frozen parent, so the integration commit IDs can differ from Gerrit's review
commit IDs; the resulting source tree is the reproducibility boundary.

The tested RDMA inline datapath is byte-identical in
`src/plugins/rdma/output.c` to 46540 PS2. The AF_XDP plugin layers 46539 PS1 and
46547 PS1 on the same frozen base.

The AF_XDP measurements also use the public Linux mlx5e
[`v3 ownership-fix series`](https://lore.kernel.org/netdev/cover.1787347981.git.jtollet@cisco.com/).
The revised v4 fixes were later accepted into `netdev/net` as
[`e01620844c5c`](https://kernel.googlesource.com/pub/scm/linux/kernel/git/netdev/net/+/e01620844c5c88b6fcf819d171df8e3976a0e76f)
and
[`63811edf5125`](https://kernel.googlesource.com/pub/scm/linux/kernel/git/netdev/net/+/63811edf512584c946e5e96b100e9e280703bbb5).

## Post-publication evolution (September 4, 2026)

The published throughput and CPU figures remain historical measurements of
the frozen source tree above. They have not been relabelled as measurements of
later Gerrit patch sets.

The mlx5 RDMA-DV work was subsequently checked against the NVIDIA Adapter PRM
and tested by CSIT on multiple ConnectX generations and architectures. The
review series was simplified as follows:

- [46506](https://gerrit.fd.io/r/c/vpp/+/46506),
  [46547](https://gerrit.fd.io/r/c/vpp/+/46547),
  [46568](https://gerrit.fd.io/r/c/vpp/+/46568), and
  [46668](https://gerrit.fd.io/r/c/vpp/+/46668) are merged.
- 46540 was abandoned after its full-inline support was folded into 46465.
- The remaining RDMA-DV review chain is
  [46609](https://gerrit.fd.io/r/c/vpp/+/46609) PS7 →
  [46667](https://gerrit.fd.io/r/c/vpp/+/46667) PS5 →
  [46155](https://gerrit.fd.io/r/c/vpp/+/46155) PS19 →
  [46465](https://gerrit.fd.io/r/c/vpp/+/46465) PS16 →
  [45505](https://gerrit.fd.io/r/c/vpp/+/45505) PS55. At the date of this
  update, every open change in that chain has `Verified +1` and `Code-Review
  +1` from the CSIT reviewer.

Change 46539 also evolved after the benchmark. Its PS5 implementation actively
calls non-blocking `recvmsg()` when the AF_XDP RX queue is empty so the kernel
can enter `sk_busy_loop()`, and it simplifies the option semantics. The exact
busy-polling figures in the article were measured with PS1 and should therefore
be treated as historical until PS5 is benchmarked under the same conditions.
