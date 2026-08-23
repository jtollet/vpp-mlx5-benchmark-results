# Tested review-code revisions

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
