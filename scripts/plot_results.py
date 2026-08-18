#!/usr/bin/env python3
"""Generate the publication charts from the anonymized CSV data."""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "results.csv"
CHARTS = ROOT / "charts"

HARDWARE = ["ConnectX-4", "ConnectX-5", "ConnectX-6 Dx", "BlueField-3"]
DRIVERS = ["RDMA-DV", "DPDK mlx5", "AF_XDP ZC"]
COLORS = {"RDMA-DV": "#2a9d8f", "DPDK mlx5": "#457b9d", "AF_XDP ZC": "#e76f51"}


def load_rows():
    with DATA.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        for field in (
            "workers",
            "extra_irq_cpus",
            "rx_queues",
            "throughput_mpps",
            "dataplane_cycles_per_packet",
        ):
            row[field] = float(row[field])
    return rows


def primary_rows(rows):
    return [row for row in rows if row["profile"] in {"primary", "strict"}]


def save(fig, stem):
    CHARTS.mkdir(exist_ok=True)
    fig.savefig(CHARTS / f"{stem}.svg", bbox_inches="tight")
    fig.savefig(CHARTS / f"{stem}.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def throughput_chart(rows):
    rows = primary_rows(rows)
    fig, axes = plt.subplots(1, 4, figsize=(15.5, 4.2), sharey=False)
    width = 0.24
    x = np.array([0, 1])
    for ax, hardware in zip(axes, HARDWARE):
        subset = [row for row in rows if row["hardware"] == hardware]
        for offset, driver in zip((-width, 0, width), DRIVERS):
            values = []
            for workers in (1, 2):
                match = [
                    row for row in subset
                    if row["driver"] == driver and row["workers"] == workers
                ]
                values.append(match[0]["throughput_mpps"] if match else np.nan)
            bars = ax.bar(x + offset, values, width, color=COLORS[driver], label=driver)
            for bar, value in zip(bars, values):
                if not np.isnan(value):
                    ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:.1f}",
                            ha="center", va="bottom", fontsize=7, rotation=90)
        ax.set_title(hardware)
        ax.set_xticks(x, ["1 worker", "2 workers"])
        ax.grid(axis="y", alpha=0.25)
        ax.set_axisbelow(True)
        if hardware == "BlueField-3":
            ax.text(0.5, 0.06, "AF_XDP out of scope", transform=ax.transAxes,
                    ha="center", fontsize=8, color=COLORS["AF_XDP ZC"])
    axes[0].set_ylabel("Physical TX throughput (Mpps)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.01),
               ncol=3, frameon=False)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    save(fig, "throughput-scaling")


def scaling_chart(rows):
    rows = primary_rows(rows)
    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    group_x = np.arange(len(HARDWARE))
    width = 0.24
    for offset, driver in zip((-width, 0, width), DRIVERS):
        values = []
        for hardware in HARDWARE:
            one = [row for row in rows if row["hardware"] == hardware and row["driver"] == driver and row["workers"] == 1]
            two = [row for row in rows if row["hardware"] == hardware and row["driver"] == driver and row["workers"] == 2]
            values.append(two[0]["throughput_mpps"] / one[0]["throughput_mpps"] if one and two else np.nan)
        bars = ax.bar(group_x + offset, values, width, color=COLORS[driver], label=driver)
        for bar, value in zip(bars, values):
            if not np.isnan(value):
                ax.text(bar.get_x() + bar.get_width() / 2, value + 0.025, f"{value:.2f}x",
                        ha="center", va="bottom", fontsize=8, rotation=90)
    ax.axhline(2.0, color="#444444", linestyle="--", linewidth=1, label="ideal 2x")
    ax.set_ylim(0, 2.25)
    ax.set_ylabel("Two-worker / one-worker throughput")
    ax.set_xticks(group_x, HARDWARE)
    ax.set_title("Scaling depends on where the one-worker bottleneck sits")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(ncol=4, frameon=False, loc="upper center")
    fig.tight_layout()
    save(fig, "worker-scaling")


def cpu_budget_chart(rows):
    rows = primary_rows(rows)
    fig, axes = plt.subplots(1, 4, figsize=(15.5, 4.2), sharey=False)
    width = 0.24
    x = np.array([0, 1])
    for ax, hardware in zip(axes, HARDWARE):
        subset = [row for row in rows if row["hardware"] == hardware]
        for offset, driver in zip((-width, 0, width), DRIVERS):
            values = []
            for workers in (1, 2):
                match = [
                    row for row in subset
                    if row["driver"] == driver and row["workers"] == workers
                ]
                if match:
                    row = match[0]
                    values.append(row["throughput_mpps"] * row["dataplane_cycles_per_packet"] / 1000.0)
                else:
                    values.append(np.nan)
            bars = ax.bar(x + offset, values, width, color=COLORS[driver], label=driver)
            for bar, value in zip(bars, values):
                if not np.isnan(value):
                    ax.text(bar.get_x() + bar.get_width() / 2, value,
                            f"{value:.2f}", ha="center", va="bottom",
                            fontsize=7, rotation=90)
        ax.set_title(hardware)
        ax.set_xticks(x, ["1 worker", "2 workers"])
        ax.grid(axis="y", alpha=0.25)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("Accounted dataplane CPU budget (GHz)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.01),
               ncol=3, frameon=False)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    save(fig, "cpu-budget")


def main():
    rows = load_rows()
    throughput_chart(rows)
    scaling_chart(rows)
    cpu_budget_chart(rows)


if __name__ == "__main__":
    main()
