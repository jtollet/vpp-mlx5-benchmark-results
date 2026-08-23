# VPP review-code provenance

Live Gerrit state for the active datapath changes was checked on
**2026-08-23 12:40 CEST**. Dependency changes 45505 and 46155 were last checked
on **2026-08-20 21:34 CEST**. Live review state and frozen benchmark revisions
are deliberately separate: a newer patch set or later merge does not change
which source tree produced the measurements.

## Open reviews

| Change | Current live patch set / revision | Live status | Frozen tested patch set | Role in this benchmark |
|---|---|---|---:|---|
| [46465](https://gerrit.fd.io/r/c/vpp/+/46465) | PS9 `85d127f91c87ed3c3ba4cf389951815c7e54f6fb` | `NEW`; Verified +1; Code-Review 0 | PS8 | Native mlx5 eMPW transmit path; material on capable CX5/CX6/BF3 hardware. CX4 falls back automatically. |
| [46539](https://gerrit.fd.io/r/c/vpp/+/46539) | PS1 `a4d1def8af97cd2e480b0764723dd9a9c9508b0e` | `NEW`; Verified +1; Code-Review 0 | PS1 | Optional AF_XDP socket busy polling; off by default and retained only on CX6. |
| [46540](https://gerrit.fd.io/r/c/vpp/+/46540) | PS2 `89f01516b8fe3b468b43caef458e31cb060d0360` | `NEW`; Verified +1; Code-Review 0 | PS2 datapath | Device-wide explicit eMPW full-packet inline ON/OFF policy. |
| [46547](https://gerrit.fd.io/r/c/vpp/+/46547) | PS1 `017311deddcbd19f3c0e82d5359544d73787ef71` | `NEW`; required GHA passed; VPP CI running; Code-Review 0 | PS1 | Bounds AF_XDP input refill to real RX queues when a private main TX-only XSK is present. |

Changes 45505 PS49 and 46155 PS14 are frozen dependency revisions: the former
provides the DV TX/WQE-accounting foundation and the latter corrects verbs-port
selection. Neither is credited with the measured inline or AF_XDP gains.

Changes 46465, 46539, 46540 and 46547 have zero unresolved comments. The first
three are Verified +1 and wait for reviewer scoring. Change 46547 was newly
submitted from the tested three-line fix; its required workflow passed and the
full VPP workflow was still running at the timestamp above.

For 46465 PS9, one rerun was started after the preceding run failed only in
unrelated session/TAP and broad NAT/QUIC/IPsec tests; no RDMA/eMPW path was
exercised by those failures. The rerun completed successfully across builds,
ARM, HST release/debug and all six make-test variants, producing Verified +1.
The 2026-08-22 REST snapshot reports zero unresolved comments and no active
Code-Review -1; the review is waiting for a positive reviewer score.

## Merged after the benchmark freeze

| Change | Merged revision | Frozen tested revision | Role in this benchmark |
|---|---|---|---|
| [46506](https://gerrit.fd.io/r/c/vpp/+/46506) | PS8 `3214ba59e30db82689f3795300502650b85c18f4` (Code-Review +2, Verified +1) | PS6 `11a36654d5c34e9879347524a00c919298e3e868` | Correct big-endian encoding of the mlx5 RX CQ doorbell record; present in the frozen tree and measured performance-neutral. |

## Frozen tested revisions

| Change | Gerrit revision commit |
|---|---|
| 45505 PS49 | `5c594cb70d5a11050d83d04dab6b7c74ab0cd419` |
| 46155 PS14 | `74b0d8cf33384bf0694dc8530ebfe54f6eb6e9ea` |
| 46465 PS8 | `aa05d22c151516252fbb513a2a882f624326a5b8` |
| 46506 PS6 | `11a36654d5c34e9879347524a00c919298e3e868` |
| 46539 PS1 | `a4d1def8af97cd2e480b0764723dd9a9c9508b0e` |
| 46540 PS2 | `89f01516b8fe3b468b43caef458e31cb060d0360` |
| 46547 PS1 | `017311deddcbd19f3c0e82d5359544d73787ef71` |

The benchmark integration revision is
`83d45adb1b624d66ed09c90ba7e0f1484b89587e`, with source tree
`00e03df873befc01bb7fdfcc5f800b0a0ebc595f`. The integration commit IDs can
differ from Gerrit's review commit IDs because the series was replayed on one
frozen parent; the source tree is the reproducibility boundary.

The final AF_XDP plugin layers 46539 PS1 and the exact 46547 PS1 three-line
fix on that frozen base. The tested RDMA inline datapath is byte-identical in
`src/plugins/rdma/output.c` to 46540 PS2; PS2 additionally rejects an invalid
setup request when eMPW is unavailable.

This distinction prevents three attribution errors:

- a dependency or correctness change is not automatically a performance gain;
- eMPW gains are attributed only where runtime capability is active;
- later Gerrit merge status does not rewrite which code produced the data.

The AF_XDP patch in `patches/` is a Linux mlx5 submission, not a VPP change.
Its public review state is documented separately in `KNOWN_ISSUES.md`.
