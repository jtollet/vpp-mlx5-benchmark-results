#!/usr/bin/env python3
"""Validate and atomically ingest the CX5/CX6 DPDK requalification manifest."""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import subprocess
import sys
import tempfile
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "data" / "results.csv"
CONFIGURATIONS = ROOT / "data" / "configurations.csv"
ARTICLE = ROOT / "ARTICLE.md"
EXPECTED_VPP_COMMIT = "83d45adb1b624d66ed09c90ba7e0f1484b89587e"
EXPECTED_VPP_TREE = "00e03df873befc01bb7fdfcc5f800b0a0ebc595f"
EXPECTED_CELLS = {
    ("ConnectX-5", 1),
    ("ConnectX-5", 2),
    ("ConnectX-6 Dx", 1),
    ("ConnectX-6 Dx", 2),
}
EXPECTED_CPUS = {
    "ConnectX-5": "Intel Xeon Gold 6248R",
    "ConnectX-6 Dx": "Intel Xeon Platinum 8562Y+",
}
RESULT_NUMBERS = (
    "throughput_mpps",
    "dataplane_cycles_per_packet",
    "dataplane_instructions_per_packet",
    "main_cycles_per_packet",
    "main_instructions_per_packet",
    "system_cycles_per_packet",
    "system_instructions_per_packet",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or []), list(reader)


def csv_text(fields: list[str], rows: list[dict[str, str]]) -> str:
    with tempfile.TemporaryFile(mode="w+", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        stream.seek(0)
        return stream.read()


def result_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return row["hardware"], row["driver"], row["profile"], row["workers"]


def manifest_key(cell: dict) -> tuple[str, int]:
    return cell["hardware"], int(cell["workers"])


def value_list(proof: dict, name: str) -> list[float]:
    values = proof.get(name)
    require(isinstance(values, list) and len(values) == 3, f"{name}: need three windows")
    return [float(value) for value in values]


def placement_text(cell: dict) -> dict[str, str]:
    workers = int(cell["workers"])
    placement = cell["placement"]
    main = placement["main"]
    worker_rows = placement["workers"]
    rx_rows = placement["rx_queues"]
    tx_rows = placement["tx_resources"]

    require(len(worker_rows) == workers, "worker placement count mismatch")
    workers_by_id = {int(row["worker"]): row for row in worker_rows}
    require(set(workers_by_id) == set(range(workers)), "worker IDs must be contiguous")
    for row in worker_rows:
        require(not bool(row.get("smt_sibling", True)), "SMT sibling worker is not accepted")
        require(row["numa"] == main["numa"], "main/worker NUMA mismatch")

    expected_rxq = int(cell["configuration"]["rx_queues"])
    require(len(rx_rows) == expected_rxq, "RXQ placement count mismatch")
    rx_counts = {worker: 0 for worker in workers_by_id}
    for row in rx_rows:
        worker = int(row["worker"])
        require(worker in workers_by_id, "RXQ references unknown worker")
        expected = workers_by_id[worker]
        require(int(row["thread"]) == int(expected["thread"]), "RXQ thread mismatch")
        require(int(row["cpu"]) == int(expected["cpu"]), "RXQ CPU mismatch")
        require(row["numa"] == expected["numa"], "RXQ NUMA mismatch")
        rx_counts[worker] += 1

    producers = {"main", *(f"worker{worker}" for worker in range(workers))}
    require(len(tx_rows) >= workers + 1, "fewer than workers+1 TX resources")
    require(len({row["resource"] for row in tx_rows}) == len(tx_rows), "duplicate TX resource")
    require({row["producer"] for row in tx_rows} == producers, "TX producer set mismatch")
    require(all(not bool(row.get("shared", True)) for row in tx_rows), "shared TX resource")
    for row in tx_rows:
        producer = row["producer"]
        expected = main if producer == "main" else workers_by_id[int(producer.removeprefix("worker"))]
        require(int(row["thread"]) == int(expected["thread"]), "TX thread mismatch")
        require(int(row["cpu"]) == int(expected["cpu"]), "TX CPU mismatch")
        require(row["numa"] == expected["numa"], "TX NUMA mismatch")

    main_text = f"thread{main['thread']}/CPU{main['cpu']}"
    worker_text = "; ".join(
        f"worker{worker}=thread{row['thread']}/CPU{row['cpu']}"
        for worker, row in sorted(workers_by_id.items())
    )
    rx_count_text = "; ".join(
        f"worker{worker}={count}" for worker, count in sorted(rx_counts.items())
    )
    rx_text = "; ".join(
        f"q{row['queue']}->worker{row['worker']}/thread{row['thread']}/CPU{row['cpu']}"
        for row in sorted(rx_rows, key=lambda item: int(item["queue"]))
    )
    tx_text = "; ".join(
        f"{row['resource']}->{row['producer']}/thread{row['thread']}/CPU{row['cpu']}"
        for row in sorted(tx_rows, key=lambda item: item["resource"])
    )
    return {
        "main_thread_cpu": main_text,
        "worker_thread_cpus": worker_text,
        "numa_locality": f"main/workers/RXQ/TXQ local on NUMA {main['numa']}",
        "rxq_per_worker": rx_count_text,
        "rxq_to_worker_thread_cpu": rx_text,
        "txq_qp_to_producer_worker_cpu": tx_text,
        "txq_qp_ownership": "dedicated/non-shared",
        "balance_evidence": placement["balance_evidence"],
        "placement_limitations": placement.get("limitations", "none"),
    }


def validate_cell(cell: dict) -> tuple[dict[str, str], dict[str, str]]:
    hardware, workers = manifest_key(cell)
    require(cell.get("cpu") == EXPECTED_CPUS[hardware], f"{hardware}/{workers}: CPU")
    require(cell.get("driver") == "DPDK mlx5", f"{hardware}/{workers}: driver")
    require(cell.get("profile") == "primary", f"{hardware}/{workers}: profile")
    require(cell.get("status") == "final", f"{hardware}/{workers}: status")
    runs = [float(value) for value in cell["runs_mpps"]]
    require(len(runs) == 3 and all(value > 0 for value in runs), "need three positive Mpps runs")
    require(int(cell["window_seconds"]) == 20, "windows must be 20 seconds")
    proof = cell["proof"]
    for field in ("source_frame_bytes", "dut_frame_bytes"):
        require(all(abs(value - 64.0) < 0.0005 for value in value_list(proof, field)), field)
    for field in (
        "pause_deltas",
        "physical_error_deltas",
        "physical_tx_discard_deltas",
        "tx_completion_error_deltas",
        "rx_out_of_buffer_deltas",
        "vpp_error_deltas",
    ):
        require(all(value == 0 for value in value_list(proof, field)), field)
    rx_discards = value_list(proof, "physical_rx_discard_deltas")
    require(all(value >= 0 for value in rx_discards), "invalid physical RX discard delta")
    offered = value_list(proof, "offered_rx_mpps")
    require(all(source > forwarded for source, forwarded in zip(offered, runs)), "no offered-load headroom")
    spread = value_list(proof, "rx_queue_spread_pct")
    require(all(0 <= value <= 1.0 for value in spread), "RXQ spread exceeds one percent")
    worker_spread = value_list(proof, "worker_spread_pct")
    require(all(0 <= value <= 1.0 for value in worker_spread), "worker spread exceeds one percent")
    require(proof["classification"] in {"maximum_under_overload", "highest_clean_not_ndr"}, "classification")

    config = cell["configuration"]
    for field in ("rx_queues", "nic_rxd", "nic_txd", "buffers", "data_size"):
        require(int(config[field]) > 0, f"invalid configuration {field}")
    placement = placement_text(cell)
    throughput = statistics.mean(runs)
    throughput_sd = statistics.pstdev(runs)
    dataplane_cycles = float(cell["dataplane_cycles_per_packet"])
    dataplane_instructions = float(cell["dataplane_instructions_per_packet"])
    main_cycles = float(cell["main_cycles_per_packet"])
    main_instructions = float(cell["main_instructions_per_packet"])
    system_cycles = float(
        cell.get("system_cycles_per_packet", dataplane_cycles + main_cycles)
    )
    system_instructions = float(
        cell.get(
            "system_instructions_per_packet",
            dataplane_instructions + main_instructions,
        )
    )
    require(dataplane_cycles > 0 and dataplane_instructions > 0, "invalid dataplane counters")
    require(main_cycles >= 0 and main_instructions >= 0, "invalid main counters")
    require(abs(system_cycles - dataplane_cycles - main_cycles) < 0.002, "system cycle accounting")
    require(
        abs(system_instructions - dataplane_instructions - main_instructions) < 0.002,
        "system instruction accounting",
    )

    result = {
        "hardware": hardware,
        "cpu": cell["cpu"],
        "driver": "DPDK mlx5",
        "profile": "primary",
        "status": "final",
        "provisional": "false",
        "workers": str(workers),
        "extra_irq_cpus": "0",
        "rx_queues": str(config["rx_queues"]),
        "throughput_mpps": f"{throughput:.6f}",
        "dataplane_cycles_per_packet": f"{dataplane_cycles:.3f}",
        "dataplane_instructions_per_packet": f"{dataplane_instructions:.3f}",
        "main_cycles_per_packet": f"{main_cycles:.3f}",
        "main_instructions_per_packet": f"{main_instructions:.3f}",
        "system_cycles_per_packet": f"{system_cycles:.3f}",
        "system_instructions_per_packet": f"{system_instructions:.3f}",
        "repeats": "3",
        "window_seconds": "20",
        "throughput_sd_mpps": f"{throughput_sd:.6f}",
        "qualification": (
            f"true Ethernet64 {proof['classification'].replace('_', ' ')}; source and DUT "
            "bytes/packet 64.000; zero PAUSE/TX discard/physical/VPP errors; "
            + ("RX overload/discards disclosed; " if any(rx_discards) else "zero RX discard; ")
            + "balanced RX queues; main/worker/RXQ/TXQ placement proven"
        ),
    }
    configuration = {
        "hardware": hardware,
        "driver": "DPDK mlx5",
        "profile": "primary",
        "status": "final",
        "workers": str(workers),
        "rx_queues": str(config["rx_queues"]),
        "nic_rxd": str(config["nic_rxd"]),
        "nic_txd": str(config["nic_txd"]),
        "xsk_rxd": "",
        "xsk_txd": "",
        "buffers": str(config["buffers"]),
        "data_size": str(config["data_size"]),
        "rx_mode": config.get("rx_mode", ""),
        "tx_mode": config["tx_mode"],
        **placement,
        "important_options": config["important_options"],
    }
    require("not_recorded" not in " ".join(placement.values()), "incomplete final placement")
    return result, configuration


def replace_rows(rows: list[dict[str, str]], replacements: dict[tuple, dict[str, str]]) -> None:
    seen = set()
    for index, row in enumerate(rows):
        cell = result_key(row)
        if cell in replacements:
            rows[index] = replacements[cell]
            seen.add(cell)
    require(seen == set(replacements), "CSV target row missing")


def display_cell(row: dict[str, str]) -> str:
    status = row["status"]
    if status == "pending_exact_stack":
        return "pending"
    if status == "pending_requalification":
        return "pending requalification"
    if status == "not_measured":
        return "not measured"
    rounded_mpps = Decimal(row["throughput_mpps"]).quantize(Decimal("0.1"), ROUND_HALF_UP)
    rounded_cycles = Decimal(row["dataplane_cycles_per_packet"]).quantize(
        Decimal("1"), ROUND_HALF_UP
    )
    rounded_main = Decimal(row["main_cycles_per_packet"]).quantize(
        Decimal("0.1"), ROUND_HALF_UP
    )
    display = f"**{rounded_mpps:.1f} / {rounded_cycles:,.0f} / {rounded_main:.1f}**"
    extra_irq_cpus = int(row["extra_irq_cpus"] or 0)
    if extra_irq_cpus:
        suffix = "CPU" if extra_irq_cpus == 1 else "CPUs"
        display += f" (+{extra_irq_cpus} IRQ {suffix})"
    return display


def render_result_table(rows: list[dict[str, str]]) -> str:
    by_key = {result_key(row): row for row in rows}
    hardware = ("ConnectX-4", "ConnectX-5", "ConnectX-6 Dx", "BlueField-3")
    paths = (
        ("RDMA-DV", "primary"),
        ("DPDK mlx5", "primary"),
        ("AF_XDP ZC", "maximum"),
    )
    lines = [
        "| Hardware | Path | 1 worker: Mpps / dataplane cycles-pkt / main cycles-pkt | 2 workers: Mpps / dataplane cycles-pkt / main cycles-pkt | 1→2 |",
        "|---|---|---:|---:|---:|",
    ]
    for hw in hardware:
        first = True
        for driver, profile in paths:
            if hw == "BlueField-3" and driver == "AF_XDP ZC":
                continue
            if driver == "AF_XDP ZC" and (hw, driver, profile, "1") not in by_key:
                profile = "strict"
            one = by_key[(hw, driver, profile, "1")]
            two = by_key[(hw, driver, profile, "2")]
            label = driver
            if driver == "RDMA-DV":
                label += ", legacy SEND" if hw == "ConnectX-4" else " + eMPW"
            elif driver == "AF_XDP ZC":
                if one["status"] == "final" and two["status"] == "final":
                    label += " maximum, submitted fix"
            scale = "—"
            if one["throughput_mpps"] and two["throughput_mpps"]:
                scale = f"{float(two['throughput_mpps']) / float(one['throughput_mpps']):.1f}×"
            lines.append(
                f"| {hw if first else ''} | {label} | {display_cell(one)} | "
                f"{display_cell(two)} | {scale} |"
            )
            first = False
    return "\n".join(lines)


def replace_block(text: str, name: str, body: str) -> str:
    begin = f"<!-- BEGIN GENERATED {name} -->"
    end = f"<!-- END GENERATED {name} -->"
    require(text.count(begin) == 1 and text.count(end) == 1, f"article marker {name}")
    prefix, remainder = text.split(begin, 1)
    _, suffix = remainder.split(end, 1)
    return f"{prefix}{begin}\n{body.strip()}\n{end}{suffix}"


def atomic_write(path: Path, content: str) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as stream:
        stream.write(content)
        temporary = Path(stream.name)
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--apply", action="store_true", help="write validated data and article")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    require(manifest["vpp_commit"] == EXPECTED_VPP_COMMIT, "VPP commit mismatch")
    require(manifest["vpp_tree"] == EXPECTED_VPP_TREE, "VPP tree mismatch")
    cell_set = {manifest_key(cell) for cell in manifest["cells"]}
    require(len(cell_set) == len(manifest["cells"]), "duplicate manifest cell")
    require(bool(cell_set) and cell_set <= EXPECTED_CELLS, "unexpected cell")
    for hardware in {hardware for hardware, _ in cell_set}:
        require(
            {(hardware, 1), (hardware, 2)} <= cell_set,
            f"{hardware}: ingest 1W and 2W together",
        )

    result_replacements = {}
    configuration_replacements = {}
    for cell in manifest["cells"]:
        result, configuration = validate_cell(cell)
        cell_key = (result["hardware"], result["driver"], result["profile"], result["workers"])
        result_replacements[cell_key] = result
        configuration_replacements[cell_key] = configuration

    result_fields, result_rows = read_csv(RESULTS)
    configuration_fields, configuration_rows = read_csv(CONFIGURATIONS)
    replace_rows(result_rows, result_replacements)
    replace_rows(configuration_rows, configuration_replacements)
    article = ARTICLE.read_text(encoding="utf-8")
    article = replace_block(article, "RESULT TABLE", render_result_table(result_rows))
    conclusions = manifest.get("article_conclusions", {})
    if conclusions.get("cx6_scaling_status") == "final":
        article = replace_block(article, "CX6 SCALING", conclusions["cx6_scaling_markdown"])
    if conclusions.get("firmware_status") == "final":
        article = replace_block(article, "FIRMWARE CONCLUSION", conclusions["firmware_markdown"])

    for cell, result in sorted(result_replacements.items()):
        print(
            f"validated {cell[0]} {cell[3]}W: {result['throughput_mpps']} Mpps, "
            f"{result['dataplane_cycles_per_packet']} dataplane cycles/pkt"
        )
    if not args.apply:
        print("dry run only; pass --apply after report review")
        return

    originals = {
        RESULTS: RESULTS.read_text(encoding="utf-8"),
        CONFIGURATIONS: CONFIGURATIONS.read_text(encoding="utf-8"),
        ARTICLE: ARTICLE.read_text(encoding="utf-8"),
    }
    try:
        atomic_write(RESULTS, csv_text(result_fields, result_rows))
        atomic_write(CONFIGURATIONS, csv_text(configuration_fields, configuration_rows))
        atomic_write(ARTICLE, article)
        subprocess.run([sys.executable, ROOT / "scripts/check_data.py"], check=True)
        subprocess.run([sys.executable, ROOT / "scripts/check_anonymization.py"], check=True)
        with tempfile.TemporaryDirectory(prefix="vpp-mlx5-mpl-") as cache:
            environment = os.environ.copy()
            environment["MPLCONFIGDIR"] = cache
            subprocess.run(
                [sys.executable, ROOT / "scripts/plot_results.py"],
                check=True,
                env=environment,
            )
    except Exception:
        for path, content in originals.items():
            atomic_write(path, content)
        raise
    print("requalification applied; CSV, article, checks and charts updated")


if __name__ == "__main__":
    main()
