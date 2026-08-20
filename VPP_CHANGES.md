# VPP review-code provenance

Live Gerrit state checked on **2026-08-20 21:34 CEST**. Live review state and
the frozen benchmark revisions are deliberately separate: a newer patch set or
later merge does not change which source tree produced the measurements.

## Open reviews

| Change | Current live patch set / revision | Live status | Frozen tested patch set | Role in this benchmark |
|---|---|---|---:|---|
| [45505](https://gerrit.fd.io/r/c/vpp/+/45505) | PS49 `5c594cb70d5a11050d83d04dab6b7c74ab0cd419` | `NEW`; Verified +1 | PS49 | DV TX/WQE-accounting foundation. Its added offload feature is not exercised by UDP64. |
| [46155](https://gerrit.fd.io/r/c/vpp/+/46155) | PS15 `8f86a60fadb6cb1d9a6488846f5b364054296eb3` | `NEW`; Verified +1 | PS14 | Correct verbs-port selection for QP/flow creation; setup/correctness, not a dataplane speed claim. |
| [46465](https://gerrit.fd.io/r/c/vpp/+/46465) | PS9 `85d127f91c87ed3c3ba4cf389951815c7e54f6fb` | `NEW`; Verified +1 | PS8 | Native mlx5 eMPW transmit path; material on capable CX5/CX6/BF3 hardware. CX4 falls back automatically. |

The current PS15 and PS9 revisions were **not** used for these results. Their
live CI score is reported for transparency, not transferred backward to the
frozen tested patch sets.

All four changes have zero active discussion threads when thread state is
evaluated from the last comment in each chain. Changes 45505, 46155 and 46465
are waiting for reviewer scoring rather than CI or an author response; no
additional `recheck` is justified.

For 46465 PS9, one rerun was started after the preceding run failed only in
unrelated session/TAP and broad NAT/QUIC/IPsec tests; no RDMA/eMPW path was
exercised by those failures. The rerun completed successfully across builds,
ARM, HST release/debug and all six make-test variants, producing Verified +1.

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

The benchmark integration revision is
`83d45adb1b624d66ed09c90ba7e0f1484b89587e`, with source tree
`00e03df873befc01bb7fdfcc5f800b0a0ebc595f`. The integration commit IDs can
differ from Gerrit's review commit IDs because the series was replayed on one
frozen parent; the source tree is the reproducibility boundary.

This distinction prevents three attribution errors:

- a dependency or correctness change is not automatically a performance gain;
- eMPW gains are attributed only where runtime capability is active;
- later Gerrit merge status does not rewrite which code produced the data.

The AF_XDP patch in `patches/` is a Linux mlx5 submission, not a VPP change.
Its public review state is documented separately in `KNOWN_ISSUES.md`.
