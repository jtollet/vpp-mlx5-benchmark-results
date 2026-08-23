#!/usr/bin/env python3
"""Generate the publication figures from qualified true64 rows and causal controls."""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

matplotlib.rcParams["svg.hashsalt"] = "vpp-mlx5-benchmark-results"


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "results.csv"
CX6_INLINE_DATA = ROOT / "data" / "cx6-inline-causal.csv"
CHARTS = ROOT / "charts"

HARDWARE = ["ConnectX-4", "ConnectX-5", "ConnectX-6 Dx", "BlueField-3"]
DRIVERS = ["RDMA-DV", "DPDK mlx5", "AF_XDP ZC"]
LABELS = {
    "RDMA-DV": "RDMA-DV",
    "DPDK mlx5": "DPDK mlx5",
    "AF_XDP ZC": "AF_XDP ZC (kernel work counted)",
}
COLORS = {
    "RDMA-DV": "#16857b",
    "DPDK mlx5": "#3f6fa0",
    "AF_XDP ZC": "#d96b47",
}
MARKERS = {"RDMA-DV": "o", "DPDK mlx5": "s", "AF_XDP ZC": "^"}
CX4_TRUE64_TG_CEILING_MPPS = 42.634
NUMERIC = {
    "workers",
    "extra_irq_cpus",
    "throughput_mpps",
    "dataplane_cycles_per_packet",
}


def load_rows() -> list[dict[str, object]]:
    with DATA.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        for field in NUMERIC:
            row[field] = float(row[field]) if row[field] else None
    return rows


def retained(rows):
    return [row for row in rows if row["status"] in {"final", "provisional"}]


def profile_for(driver: str) -> str:
    return "strict" if driver == "AF_XDP ZC" else "primary"


def series(rows, hardware: str, driver: str):
    profile = profile_for(driver)
    return sorted(
        (
            row
            for row in rows
            if row["hardware"] == hardware
            and row["driver"] == driver
            and row["profile"] == profile
        ),
        key=lambda row: row["workers"],
    )


def find(rows, hardware: str, driver: str, workers: int):
    matches = [
        row
        for row in series(rows, hardware, driver)
        if row["workers"] == float(workers)
    ]
    return matches[0] if matches else None


def save(fig, stem: str):
    CHARTS.mkdir(exist_ok=True)
    svg = CHARTS / f"{stem}.svg"
    fig.savefig(svg, bbox_inches="tight", metadata={"Date": None})
    # Matplotlib emits trailing spaces in path data.  Normalize generated
    # text so repository whitespace checks remain useful.
    svg.write_text(
        "\n".join(line.rstrip() for line in svg.read_text(encoding="utf-8").splitlines())
        + "\n",
        encoding="utf-8",
    )
    fig.savefig(CHARTS / f"{stem}.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def throughput_chart(rows):
    fig, axes = plt.subplots(2, 2, figsize=(12.8, 8.0), sharey=True)
    axes = axes.ravel()

    for ax, hardware in zip(axes, HARDWARE):
        for driver in DRIVERS:
            points = series(rows, hardware, driver)
            if not points:
                continue
            x = [row["workers"] for row in points]
            y = [row["throughput_mpps"] for row in points]
            ax.plot(
                x,
                y,
                color=COLORS[driver],
                marker=MARKERS[driver],
                linewidth=2.3,
                markersize=7,
                linestyle="--" if driver == "AF_XDP ZC" else "-",
                label=LABELS[driver],
            )
            for point, workers, value in zip(points, x, y):
                suffix = "+" if "source-limited" in point["qualification"] else ""
                value_label = (
                    f"{value:.0f}"
                    if hardware == "ConnectX-6 Dx"
                    and driver == "RDMA-DV"
                    and workers == 6
                    else f"{value:.1f}"
                )
                # Keep nearby low-rate series readable.  Native labels sit
                # above the marker, while DPDK and AF_XDP use two different
                # offsets below it.  This is especially important for CX4,
                # where the two poll-mode 3W lower bounds are effectively
                # identical.
                y_offset = -14 if driver == "DPDK mlx5" else -5 if driver == "AF_XDP ZC" else 8
                x_offset = -11 if driver == "RDMA-DV" else 11 if driver == "DPDK mlx5" else 0
                ax.annotate(
                    f"{value_label}{suffix}",
                    (workers, value),
                    xytext=(x_offset, y_offset),
                    textcoords="offset points",
                    ha="center",
                    va="top" if y_offset < 0 else "bottom",
                    fontsize=8,
                    color=COLORS[driver],
                )
        if hardware == "ConnectX-4":
            ax.axhline(
                CX4_TRUE64_TG_CEILING_MPPS,
                color="#555555",
                linewidth=1.5,
                linestyle=(0, (4, 3)),
                zorder=0,
            )
            ax.annotate(
                f"Measured traffic-generator ceiling (true64): {CX4_TRUE64_TG_CEILING_MPPS:.0f} Mpps",
                xy=(0.68, CX4_TRUE64_TG_CEILING_MPPS),
                xytext=(0, 7),
                textcoords="offset points",
                ha="left",
                va="bottom",
                fontsize=8.5,
                color="#444444",
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.82, "pad": 1.5},
            )
        ax.set_title(hardware, fontweight="bold")
        ax.set_xticks([1, 2, 3] if hardware == "ConnectX-4" else [1, 2, 4, 5, 6])
        ax.set_xlim(
            0.6,
            3.35 if hardware == "ConnectX-4" else 6.35,
        )
        ax.set_ylim(0, 150)
        ax.grid(alpha=0.25)
        ax.set_axisbelow(True)
        ax.set_xlabel("VPP workers")

    axes[0].set_ylabel("Successful physical TX (Mpps)")
    axes[2].set_ylabel("Successful physical TX (Mpps)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.945),
        ncol=3,
        frameon=False,
    )
    fig.suptitle(
        "True Ethernet64 L3 forwarding — tuned topology at each worker count",
        y=0.995,
        fontsize=14,
        fontweight="bold",
    )
    fig.text(
        0.5,
        -0.01,
        "+ source-limited lower bound; AF_XDP IRQ/NAPI is colocated on declared VPP CPUs\n"
        "CX6 RDMA-DV uses pointer segments at 1W and the disabled-by-default full-inline review path from 2W upward",
        ha="center",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.02, 1, 0.87))
    save(fig, "throughput-scaling")


def cx6_inline_chart():
    with CX6_INLINE_DATA.open(newline="", encoding="utf-8") as stream:
        rows = [
            row
            for row in csv.DictReader(stream)
            if row["driver"] == "RDMA-DV" and row["measurement"] == "causal_screen"
        ]

    modes = [
        ("off", "completion", "Pointer to packet buffer", "#777777"),
        ("on", "immediate", "Full-packet inline", "#16857b"),
    ]
    workers = [4]
    x = np.arange(len(workers))
    width = 0.34
    fig, ax = plt.subplots(figsize=(7.6, 5.2))

    for index, (inline_state, release, label, color) in enumerate(modes):
        values = []
        for worker_count in workers:
            row = next(
                row
                for row in rows
                if int(row["workers"]) == worker_count
                and row["inline_state"] == inline_state
                and row["buffer_release"] == release
            )
            values.append(float(row["throughput_mpps"]))
        bars = ax.bar(x + (index - 0.5) * width, values, width, label=label, color=color)
        ax.bar_label(bars, labels=[f"{value:.1f}" for value in values], padding=3, fontsize=9)

    ax.set_xticks(x, ["4 workers"])
    ax.set_ylabel("Successful physical TX (Mpps)")
    ax.set_ylim(0, 158)
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="upper left")
    ax.set_title(
        "CX6 TX-only: packet reference versus full-packet inline",
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.01,
        "True Ethernet64, one raw QP per worker; matched 5-second causal screens",
        ha="center",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    save(fig, "cx6-inline-root-cause")


def cpu_chart(rows):
    fig, ax = plt.subplots(figsize=(10.2, 5.3))
    width = 0.24
    group_x = np.arange(len(HARDWARE))
    workers = 2

    for index, driver in enumerate(DRIVERS):
        values = []
        for hardware in HARDWARE:
            row = find(rows, hardware, driver, workers)
            values.append(row["dataplane_cycles_per_packet"] if row else np.nan)
        positions = group_x + (index - 1) * width
        bars = ax.bar(
            positions,
            values,
            width,
            color=COLORS[driver],
            hatch="//" if driver == "AF_XDP ZC" else None,
            label=LABELS[driver],
        )
        for bar, value in zip(bars, values):
            if np.isnan(value):
                continue
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value * 1.08,
                f"{value:.0f}",
                ha="center",
                va="bottom",
                fontsize=8,
                rotation=90,
            )
    ax.set_yscale("log")
    ax.set_ylim(70, 2600)
    ax.set_xticks(group_x, HARDWARE)
    ax.tick_params(axis="x", rotation=12)
    ax.grid(axis="y", which="both", alpha=0.25)
    ax.set_axisbelow(True)
    ax.set_ylabel("CPU cycles per successful packet\n(log scale; lower is better)")
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.93),
        ncol=3,
        frameon=False,
    )
    fig.suptitle(
        "Two workers — AF_XDP includes colocated IRQ/NAPI kernel work",
        y=0.99,
        fontsize=14,
        fontweight="bold",
    )
    fig.tight_layout(rect=(0.04, 0, 1, 0.84))
    save(fig, "cpu-budget")


def main():
    rows = retained(load_rows())
    throughput_chart(rows)
    cpu_chart(rows)
    cx6_inline_chart()


if __name__ == "__main__":
    main()
