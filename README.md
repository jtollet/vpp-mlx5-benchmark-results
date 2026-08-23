# VPP on NVIDIA ConnectX and BlueField: anonymized benchmark data

> **Status: qualified review-code dataset.** The ConnectX-6 root cause and
> 1/2/4/5/6-worker series are qualified. Full-inline native code remains a
> disabled-by-default review change; the tested adaptive policy was rejected
> and only explicit OFF/ON results are retained.

This repository accompanies the article **“Three VPP datapaths for NVIDIA
ConnectX and BlueField at 64 bytes.”** It archives a tuned comparison
of VPP native RDMA-DV, VPP/DPDK mlx5 and VPP/AF_XDP native zero-copy for true
64-byte-Ethernet same-port IPv4 forwarding with one to six workers.

## Data status

All numeric cells were repeated on the frozen exact VPP review tree. RDMA-DV
and DPDK have qualified one- and two-worker rows on all four platforms.
ConnectX-4 RDMA-DV and DPDK are qualified at one, two and three workers; both
three-worker points are source-limited lower bounds. ConnectX-4 AF_XDP is
qualified through three workers. ConnectX-5 and BlueField-3 RDMA-DV/DPDK are
qualified at one, two, four, five and six workers. ConnectX-6 DPDK is qualified
at one, two, four, five and six workers
with inline state controlled independently of TXQ count. ConnectX-6 native is
qualified at one, two, four, five and six workers; full inline is selected from
two workers upward, while the old two-to-six-worker pointer plateau is retained
as a separate control profile. AF_XDP is qualified at 1/2/3 workers on CX4,
1/2/4/5/6 on CX5 and CX6, and is not measured on BlueField-3 by
study scope.

AF_XDP measurements are complete for the cyclic-RQ fix carried unchanged into
the submitted mlx5 `[PATCH net v3 0/2]` series. Applying them to an upstream
kernel remains provisional while that series is under review; this is a
code-provenance caveat, not unfinished measurement.

## Contents

- [`ARTICLE.md`](ARTICLE.md): publication-ready article.
- [`METHODOLOGY.md`](METHODOLOGY.md): workload, qualification and CPU accounting.
- [`TUNING_EVIDENCE.md`](TUNING_EVIDENCE.md): exact-stack parameter screens.
- [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md): submitted AF_XDP fix and native eMPW status.
- [`VPP_CHANGES.md`](VPP_CHANGES.md): exact tested revisions and live Gerrit state.
- [`patches/mlx5-af-xdp-partial-refill-double-release-fix.patch`](patches/mlx5-af-xdp-partial-refill-double-release-fix.patch):
  exact v2 cyclic patch used for AF_XDP A/B and carried unchanged as v3 patch 1.
- [`data/results.csv`](data/results.csv): throughput, CPU scopes and qualification labels.
- [`data/cx6-inline-causal.csv`](data/cx6-inline-causal.csv): matched TX-only
  pointer/inline root-cause screens for native RDMA-DV and DPDK.
- [`data/bf3-inline-controls.csv`](data/bf3-inline-controls.csv): matched BF3
  evidence showing why fixed always-on inline is not a universal policy.
- [`data/cx6-300b-cpu.csv`](data/cx6-300b-cpu.csv): separate CX6 two-worker
  300-byte throughput and whole-CPU cost control.
- [`data/configurations.csv`](data/configurations.csv): retained tuning and
  scope state, including main/worker CPU and NUMA placement, RXQ-to-worker mapping,
  TXQ/QP producer ownership, sharing and balance evidence.
- [`data/platforms.csv`](data/platforms.csv): public platform descriptions.
- [`scripts/plot_results.py`](scripts/plot_results.py): reproducible figures which
  exclude unmeasured rows and keep short causal screens separate from finals.
- [`charts/`](charts): SVG and PNG figures generated from the CSV.

## Reading the data correctly

- Mpps is successful physical DUT TX, not a software-attempt counter.
- VPP PG creates 60 bytes before FCS; retained source and DUT counters must
  both prove exactly 64.000 physical bytes per packet. Older PG `size 64`
  observations are 68-byte MAC-frame controls and are excluded.
- Finals are normally means of three 20-second windows; the CSV throughput SD
  is the population standard deviation of those repetitions.
- AF_XDP values are peak forwarding under offered overload, not formal
  zero-loss NDR; shortage and ring-pressure counters are retained.
- Retained AF_XDP comparisons keep IRQ/NAPI inside the declared worker CPU
  budget and include that kernel work in CPU-wide counters.
- AF_XDP runs with additional IRQ/NAPI CPUs are diagnostic ceilings only and
  are excluded from result tables, scaling graphs and driver comparisons.
- The required, lightly loaded VPP main core is recorded separately.
- Two-worker cycles/instructions aggregate both workers before division by
  successful physical packets.
- Cross-generation Mpps are complete-platform results, not a NIC-only comparison.
- Placement is explicit per cell. `not_recorded` means the evidence is absent;
  it is never replaced with an assumed queue-to-thread mapping.

## Reproduce the figures

```bash
python3 -m pip install matplotlib numpy
python3 scripts/plot_results.py
```

## Privacy

No raw lab log is published. The curated package contains no lab hostname or
login, IP address, MAC address, PCI BDF, serial number, internal URL, internal
path or topology identifier. Public authorship/review emails occur only in the
exact submitted kernel patch and are intentionally retained as patch metadata.

Run the identifier check before publication:

```bash
python3 scripts/check_data.py
python3 scripts/check_anonymization.py
```

## License

Text, data and figures are licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
