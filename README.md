# VPP on NVIDIA ConnectX and BlueField: anonymized benchmark data

> **Status: investigation draft. Do not publish or cite the article yet.**
> ConnectX-6 native RDMA-DV dispatch and queue scaling are being requalified;
> the current scale-out values are retained only as diagnostic observations.

This repository accompanies the draft article **“What RDMA-DV buys VPP on
NVIDIA ConnectX and BlueField.”** It archives a tuned comparison
of VPP native RDMA-DV, VPP/DPDK mlx5 and VPP/AF_XDP native zero-copy for true
64-byte-Ethernet same-port IPv4 forwarding with one to six workers.

## Data status

All numeric cells were repeated on the frozen exact VPP review tree. RDMA-DV
and DPDK have qualified one- and two-worker rows on all four platforms.
Four-worker rows are complete on ConnectX-4, ConnectX-5 and BlueField-3. Both ConnectX-6
RDMA-DV and DPDK are qualified from one through six workers, with explicit
main/worker QP or TXQ ownership and balanced RX placement. ConnectX-4
four-worker poll-mode rows are explicitly source-limited lower bounds.
BlueField-3 four-worker RDMA-DV and DPDK cells are qualified. AF_XDP is complete on the three discrete
ConnectX adapters and not measured on BlueField-3 by study scope.

AF_XDP measurements are complete for the submitted mlx5 `[PATCH net v2]`
build. Applying them to an upstream kernel remains provisional while that fix
is under review; this is a code-provenance caveat, not unfinished measurement.

## Contents

- [`ARTICLE.md`](ARTICLE.md): Medium-ready article draft.
- [`METHODOLOGY.md`](METHODOLOGY.md): workload, qualification and CPU accounting.
- [`TUNING_EVIDENCE.md`](TUNING_EVIDENCE.md): exact-stack parameter screens.
- [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md): submitted AF_XDP fix and native eMPW status.
- [`VPP_CHANGES.md`](VPP_CHANGES.md): exact tested revisions and live Gerrit state.
- [`patches/mlx5-af-xdp-partial-refill-double-release-fix.patch`](patches/mlx5-af-xdp-partial-refill-double-release-fix.patch):
  exact `[PATCH net v2]` submission used for AF_XDP A/B and performance requalification.
- [`data/results.csv`](data/results.csv): throughput, CPU scopes and qualification labels.
- [`data/configurations.csv`](data/configurations.csv): retained tuning and
  scope state, including main/worker CPU and NUMA placement, RXQ-to-worker mapping,
  TXQ/QP producer ownership, sharing and balance evidence.
- [`data/platforms.csv`](data/platforms.csv): public platform descriptions.
- [`scripts/plot_results.py`](scripts/plot_results.py): reproducible figures which
  exclude unmeasured rows.
- [`charts/`](charts): SVG and PNG figures generated from the CSV.

## Reading the data correctly

- Mpps is successful physical DUT TX, not a software-attempt counter.
- VPP PG creates 60 bytes before FCS; retained source and DUT counters must
  both prove exactly 64.000 physical bytes per packet. Older PG `size 64`
  observations are 68-byte MAC-frame controls and are excluded.
- Finals are normally means of three 20-second windows.
- AF_XDP values are peak forwarding under offered overload, not formal
  zero-loss NDR; shortage and ring-pressure counters are retained.
- AF_XDP `strict` keeps IRQ/NAPI inside the worker CPU budget and includes that
  kernel work in CPU-wide counters.
- AF_XDP `maximum` uses additional IRQ/NAPI CPUs; their count and cost are
  explicit and must not be compared as one-/two-core scaling.
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
