#!/usr/bin/env python3
"""Validate result/configuration identity, status, accounting and placement."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "data" / "results.csv"
CONFIGURATIONS = ROOT / "data" / "configurations.csv"
ARTICLE = ROOT / "ARTICLE.md"
CX6_INLINE = ROOT / "data" / "cx6-inline-causal.csv"
BF3_INLINE = ROOT / "data" / "bf3-inline-controls.csv"
FINAL_STATUSES = {"final", "provisional"}
PENDING_STATUSES = {"pending_exact_stack", "pending_requalification", "not_measured"}
MEASUREMENTS = {
    "throughput_mpps",
    "dataplane_cycles_per_packet",
    "dataplane_instructions_per_packet",
    "main_cycles_per_packet",
    "main_instructions_per_packet",
    "system_cycles_per_packet",
    "system_instructions_per_packet",
}
PLACEMENT = {
    "main_thread_cpu",
    "worker_thread_cpus",
    "numa_locality",
    "rxq_per_worker",
    "rxq_to_worker_thread_cpu",
    "txq_qp_to_producer_worker_cpu",
    "txq_qp_ownership",
    "balance_evidence",
    "placement_limitations",
}


def read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return row["hardware"], row["driver"], row["profile"], row["workers"]


def check_article_matrix(
    result_by_key: dict[tuple[str, str, str, str], dict[str, str]],
) -> None:
    """Keep the compact, hand-edited article table synchronized with the CSV."""

    text = ARTICLE.read_text(encoding="utf-8")
    start = text.index("| Platform | Datapath | 1 worker | 2 workers | Scale-out point |")
    end = text.index("\n\n", start)
    lines = [line for line in text[start:end].splitlines()[2:] if line.startswith("|")]
    matrix: dict[tuple[str, str], list[str]] = {}
    current_hardware = ""
    for line in lines:
        columns = [column.strip() for column in line.strip("|").split("|")]
        if columns[0]:
            current_hardware = columns[0]
        label = columns[1]
        driver = (
            "RDMA-DV"
            if label.startswith("RDMA-DV")
            else "DPDK mlx5"
            if label.startswith("DPDK mlx5")
            else "AF_XDP ZC"
        )
        matrix[(current_hardware, driver)] = columns[2:5]

    for (hardware, driver), cells in matrix.items():
        profile = "maximum" if driver == "AF_XDP ZC" else "primary"
        scale_workers = 3 if hardware == "ConnectX-4" else 4
        for index, workers in enumerate((1, 2, scale_workers)):
            result = result_by_key.get((hardware, driver, profile, str(workers)))
            cell = cells[index]
            if not result or result["status"] not in FINAL_STATUSES:
                assert cell == "—", (
                    f"article should show missing cell as dash: {hardware}/{driver}/{workers}"
                )
                continue
            mpps = f"{float(result['throughput_mpps']):.1f}"
            if hardware == "ConnectX-4" and workers == 3 and driver != "AF_XDP ZC":
                mpps += "+"
            cpp = f"{float(result['dataplane_cycles_per_packet']):,.0f}"
            assert f"{mpps} / {cpp}" in cell, (
                f"article/CSV mismatch: {hardware}/{driver}/{workers}"
            )


def check_inline_controls() -> None:
    """Guard the causal values and keep prototypes out of adaptive claims."""

    cx6 = read(CX6_INLINE)
    observed = {
        (row["driver"], row["workers"], row["inline_state"], row["buffer_release"]):
        float(row["throughput_mpps"])
        for row in cx6
    }
    expected = {
        ("RDMA-DV", "4", "off", "completion"): 68.868372,
        ("RDMA-DV", "4", "on", "completion"): 140.816453,
        ("RDMA-DV", "4", "on", "immediate"): 145.862425,
        ("DPDK mlx5", "4", "off", "completion"): 68.439863,
        ("DPDK mlx5", "4", "on", "immediate"): 125.005641,
    }
    for cell, value in expected.items():
        assert abs(observed[cell] - value) < 0.000001, f"CX6 causal mismatch: {cell}"

    bf3 = read(BF3_INLINE)
    assert len(bf3) == 3, "unexpected BF3 inline-control count"
    assert all(row["repeats"] == "3" and row["window_seconds"] == "12" for row in bf3)
    assert [round(float(row["throughput_mpps"]), 6) for row in bf3] == [
        49.320811,
        44.095969,
        43.094256,
    ]

    article = ARTICLE.read_text(encoding="utf-8")
    assert "No adaptive result appears in this article or its CSV." in article


def main() -> None:
    results = read(RESULTS)
    configurations = read(CONFIGURATIONS)
    result_by_key = {key(row): row for row in results}
    configuration_by_key = {key(row): row for row in configurations}

    assert len(result_by_key) == len(results), "duplicate result key"
    assert len(configuration_by_key) == len(configurations), "duplicate configuration key"
    assert result_by_key.keys() == configuration_by_key.keys(), "result/configuration key mismatch"

    for cell, result in result_by_key.items():
        configuration = configuration_by_key[cell]
        status = result["status"]
        assert status == configuration["status"], f"status mismatch: {cell}"
        assert status in FINAL_STATUSES | PENDING_STATUSES, f"unknown status: {cell}"

        if status in FINAL_STATUSES:
            assert result["throughput_mpps"], f"missing throughput: {cell}"
            assert result["dataplane_cycles_per_packet"], f"missing dataplane cycles: {cell}"
            assert all(configuration[field] for field in PLACEMENT), f"missing placement field: {cell}"
            assert "not_recorded" not in " ".join(
                configuration[field] for field in PLACEMENT
            ), f"unresolved final placement: {cell}"
            assert result["repeats"] == "3", f"unexpected repeat count: {cell}"
            assert result["window_seconds"] == "20", f"unexpected final window: {cell}"
            assert "true Ethernet64" in result["qualification"], f"missing true64 proof: {cell}"
            assert "true Ethernet64" in configuration["important_options"], (
                f"missing true64 configuration: {cell}"
            )
            for suffix in ("cycles_per_packet", "instructions_per_packet"):
                dataplane = result[f"dataplane_{suffix}"]
                main = result[f"main_{suffix}"]
                system = result[f"system_{suffix}"]
                assert bool(main) == bool(system), f"partial main/system accounting: {cell}"
                if main:
                    assert dataplane, f"system accounting without dataplane: {cell}"
                    assert abs(float(dataplane) + float(main) - float(system)) < 0.002, cell
        else:
            assert not any(result[field] for field in MEASUREMENTS), f"numeric pending cell: {cell}"

    for cell, configuration in configuration_by_key.items():
        hardware, driver, _profile, workers = cell
        if configuration["status"] not in FINAL_STATUSES:
            continue
        if driver in {"RDMA-DV", "DPDK mlx5"}:
            tx_mapping = configuration["txq_qp_to_producer_worker_cpu"]
            assert "main" in tx_mapping, f"missing main TX resource: {cell}"
            for worker in range(int(workers)):
                assert f"worker{worker}" in tx_mapping, f"missing worker TX resource: {cell}"

        if hardware == "ConnectX-6 Dx" and driver == "DPDK mlx5":
            assert configuration["buffers"] == "262144", f"wrong CX6 DPDK pool: {cell}"

    assert not any(
        result["hardware"] == "ConnectX-4" and result["workers"] == "4"
        for result in results
    ), "CX4 4W must stay outside the public headline dataset"

    for driver in ("RDMA-DV", "DPDK mlx5"):
        cell = "ConnectX-4", driver, "primary", "3"
        assert "source-limited" in result_by_key[cell]["qualification"], cell

    check_article_matrix(result_by_key)
    check_inline_controls()

    print(
        f"Data audit passed: {len(results)} matched cells; final true64, 3x20, "
        "accounting, placement and article-matrix guards valid; pending cells contain no "
        "measurements."
    )


if __name__ == "__main__":
    main()
