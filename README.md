# VPP on NVIDIA/Mellanox NICs: anonymized benchmark data

This repository accompanies the article **“Optimizing VPP Packet Forwarding
on NVIDIA ConnectX NICs and BlueField DPUs.”** It contains the curated,
anonymized results behind a tuned comparison of:

- VPP native RDMA-DV;
- VPP with the DPDK mlx5 PMD;
- VPP with AF_XDP native zero-copy.

The hardware set is ConnectX-4, ConnectX-5, ConnectX-6 Dx and BlueField-3.
The workload is 64-byte IPv4/UDP L3 forwarding with one and two VPP workers.

## Contents

- [`ARTICLE.md`](ARTICLE.md): Medium-ready article.
- [`METHODOLOGY.md`](METHODOLOGY.md): workload, accounting and parameter search.
- [`TUNING_EVIDENCE.md`](TUNING_EVIDENCE.md): representative A/B screens, including non-default DPDK tuning.
- [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md): AF_XDP candidate fix and native eMPW status.
- [`VPP_CHANGES.md`](VPP_CHANGES.md): every VPP Gerrit change in the tested review chain and its actual relevance.
- [`patches/mlx5-af-xdp-rx-full-ownership-candidate.patch`](patches/mlx5-af-xdp-rx-full-ownership-candidate.patch):
  exact diagnostic RFC candidate used for the AF_XDP stress validation.
- [`data/results.csv`](data/results.csv): throughput and CPU cost.
- [`data/configurations.csv`](data/configurations.csv): best-found tuning per combination.
- [`data/platforms.csv`](data/platforms.csv): public platform descriptions.
- [`scripts/plot_results.py`](scripts/plot_results.py): reproducible figures.
- [`charts/`](charts): SVG and PNG publication figures.

## Reproduce the figures

```bash
python3 -m pip install matplotlib numpy
python3 scripts/plot_results.py
```

## Reading the data correctly

- Mpps is successful physical DUT transmit throughput, not a software-attempt
  counter.
- Results are normally means of three 20-second windows.
- `maximum` does not mean formal zero-loss NDR.
- The AF_XDP `strict` profile keeps IRQ/NAPI inside the same dataplane CPU
  budget as the VPP workers. The AF_XDP `maximum` profile uses additional
  IRQ/NAPI CPUs and includes their cycles/instructions in the published cost.
- A lightly loaded VPP main core exists in every configuration and is recorded
  separately where exact counters were retained.
- In two-worker rows, dataplane cycles/instructions per packet aggregate both
  workers. The main-thread counters remain separate.
- Cross-generation Mpps are complete-platform results, not a controlled NIC-only
  comparison; see the CPU rationale in the methodology.

## Privacy

No raw lab logs are published. The repository has been constructed from a
small allow-list of aggregate fields and contains no lab hostname, username,
IP address, MAC address, PCI address, serial number, internal URL or internal
path.

## License

Text, data and figures are licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
