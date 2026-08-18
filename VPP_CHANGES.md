# VPP changes under review

Status captured on 2026-08-18. All four changes were public and still under
review when this package was published.

| Gerrit change | Purpose | Relevance to the published matrix |
|---|---|---|
| [45505](https://gerrit.fd.io/r/c/vpp/+/45505) | DV TX/WQE-accounting foundation | Parent of the eMPW series. Its offload feature is not exercised by UDP64 and no result is attributed to it. |
| [46155](https://gerrit.fd.io/r/c/vpp/+/46155) | Select the correct verbs port for QP and flow creation | Required for robust multi-port/BlueField device selection. It is a setup fix, not a dataplane optimization. |
| [46465](https://gerrit.fd.io/r/c/vpp/+/46465) | Native mlx5 enhanced Multi-Packet WQE transmit path | Material to the optimized RDMA-DV results on ConnectX-5, ConnectX-6 Dx and BlueField-3. ConnectX-4 fails the capability probe and automatically uses legacy SEND. |
| [46506](https://gerrit.fd.io/r/c/vpp/+/46506) | Encode the mlx5 RX CQ doorbell record in big-endian order | Validated independently across all platforms. It had no measurable performance effect and was not present in the retained performance figures. |

This distinction is intentional. A patch can be a correctness improvement or
a dependency without being the cause of a performance delta. The article
attributes the measured native TX gain to eMPW only where the runtime
capability was active.

The AF_XDP candidate in `patches/` is a Linux mlx5 patch, not a VPP change.
It had not been posted for public kernel review at the time of publication.
