# VPP on NVIDIA ConnectX and BlueField

Companion data for the FD.io/VPP article
[“Three VPP datapaths for NVIDIA ConnectX and BlueField”](https://medium.com/fd-io-vpp/three-vpp-datapaths-for-nvidia-connectx-and-bluefield-309c0124019d).

The study compares tuned VPP native RDMA-DV, DPDK mlx5 and AF_XDP native
zero-copy for same-port IPv4 forwarding of physical 64-byte Ethernet frames.
It covers ConnectX-4, ConnectX-5, ConnectX-6 Dx and BlueField-3 with one to six
workers where the platform and traffic source provide headroom.

Some retained rows use disabled-by-default review code. Their review status and
public links are documented in the published article.

## Contents

- [`METHODOLOGY.md`](METHODOLOGY.md): workload, qualification, placement and CPU
  accounting.
- [`data/results.csv`](data/results.csv): throughput, CPU scopes and
  qualification labels.
- [`data/configurations.csv`](data/configurations.csv): queue ownership,
  descriptor depths, CPU placement and fairness for every retained cell.
- [`data/platforms.csv`](data/platforms.csv): public platform descriptions.
- [`data/cx6-inline-causal.csv`](data/cx6-inline-causal.csv): matched CX6
  pointer/full-inline controls.
- [`data/bf3-inline-controls.csv`](data/bf3-inline-controls.csv): BF3 evidence
  showing why full-packet inline is not a universal policy.
- [`charts/`](charts): the three figures used by the article in PNG and SVG.
- [`scripts/`](scripts): figure generation plus data and anonymization audits.

## Reading the data

- Mpps is successful physical DUT TX, not a software-attempt counter.
- Final values are normally means of three independent 20-second windows.
- A `source-limited` result is a lower bound on DUT capacity.
- AF_XDP CPU values include colocated IRQ/NAPI/XDP/XSK kernel work and use no
  auxiliary packet-service CPU.
- Cross-generation values describe each complete CPU/NIC platform; they are
  not a controlled NIC-only comparison.
- Queue and CPU placement are explicit in `data/configurations.csv` rather than
  inferred from requested queue counts.

## Reproduce and audit

```bash
python3 -m pip install matplotlib numpy
python3 scripts/plot_results.py
python3 scripts/check_data.py
python3 scripts/check_anonymization.py
```

The public package contains no raw lab logs, hostnames, login names, IP or MAC
addresses, PCI addresses, serial numbers, internal URLs, paths or topology
identifiers. Public Gerrit, GitHub, Medium and netdev links are intentionally
retained.

## License

Text, data and figures are licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
