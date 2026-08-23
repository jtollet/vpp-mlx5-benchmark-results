#!/usr/bin/env python3
"""Generate the publication figures from qualified true64 rows and causal controls."""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


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
    fig.savefig(svg, bbox_inches="tight")
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
            for workers, value in zip(x, y):
                suffix = "+" if hardware == "ConnectX-4" and workers == 3 and driver != "AF_XDP ZC" else ""
                # Keep nearby low-rate series readable.  Native labels sit
                # above the marker, while DPDK and AF_XDP use two different
                # offsets below it.  This is especially important for CX4,
                # where the two poll-mode 3W lower bounds are effectively
                # identical.
                y_offset = -14 if driver == "DPDK mlx5" else -5 if driver == "AF_XDP ZC" else 8
                x_offset = -11 if driver == "RDMA-DV" else 11 if driver == "DPDK mlx5" else 0
                ax.annotate(
                    f"{value:.1f}{suffix}",
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
                f"Measured traffic-generator ceiling (true64): {CX4_TRUE64_TG_CEILING_MPPS:.1f} Mpps",
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
            3.35 if hardware == "ConnectX-4" else 6.35 if hardware == "ConnectX-6 Dx" else 4.35,
        )
        ax.set_ylim(0, 132)
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
        "+ source-limited lower bound (CX4 3W poll-mode); AF_XDP IRQ/NAPI is colocated on declared VPP CPUs\n"
        "CX6 RDMA-DV uses pointer segments at 1W and the disabled-by-default full-inline prototype from 2W upward",
        ha="center",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.02, 1, 0.87))
    save(fig, "throughput-scaling")


def advantage_chart(rows):
    fig, ax = plt.subplots(figsize=(11.5, 5.4))
    group_x = np.arange(len(HARDWARE))
    scales = [
        ("1 worker", lambda _hardware: 1),
        ("2 workers", lambda _hardware: 2),
        ("scale-out (CX4 3W; others 4W)", lambda hardware: 3 if hardware == "ConnectX-4" else 4),
    ]
    width = 0.22
    worker_colors = ["#174f46", "#16857b", "#6bb8ad"]

    for index, ((scale_label, workers_for), color) in enumerate(zip(scales, worker_colors)):
        values = []
        for hardware in HARDWARE:
            workers = workers_for(hardware)
            if hardware == "ConnectX-4" and index == 2:
                # Both 3W paths forward the offered source boundary, so their
                # tiny observed delta is not a DUT performance comparison.
                values.append(np.nan)
                continue
            rdma = find(rows, hardware, "RDMA-DV", workers)
            dpdk = find(rows, hardware, "DPDK mlx5", workers)
            if rdma and dpdk:
                values.append(100.0 * (rdma["throughput_mpps"] / dpdk["throughput_mpps"] - 1.0))
            else:
                values.append(np.nan)
        positions = group_x + (index - 1) * width
        bars = ax.bar(positions, values, width, color=color, label=scale_label)
        for hardware, bar, value in zip(HARDWARE, bars, values):
            if np.isnan(value):
                continue
            offset = 0.8 if value >= 0 else -1.0
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value + offset,
                f"{value:+.1f}%",
                ha="center",
                va="bottom" if value >= 0 else "top",
                fontsize=8,
            )

    ax.axhline(0, color="#333333", linewidth=1)
    ax.text(
        group_x[0] + width,
        2.0,
        "3W source-limited\n(no delta claim)",
        ha="center",
        va="bottom",
        fontsize=8,
        color=worker_colors[2],
    )
    ax.set_ylabel("RDMA-DV throughput advantage over DPDK")
    ax.set_xticks(group_x, HARDWARE)
    ax.set_ylim(-15, 44)
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, ncol=3, loc="upper center")
    ax.set_title(
        "With matched eMPW inline, native DV leads at 4W on every capable platform",
        fontweight="bold",
    )
    fig.text(0.5, 0.005, "CX4 3W is omitted from the delta because both paths are source-limited", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    save(fig, "worker-scaling")


def cx6_inline_chart():
    with CX6_INLINE_DATA.open(newline="", encoding="utf-8") as stream:
        rows = [
            row
            for row in csv.DictReader(stream)
            if row["driver"] == "RDMA-DV" and row["measurement"] == "causal_screen"
        ]

    modes = [
        ("off", "completion", "Pointer data segment", "#777777"),
        ("on", "completion", "Full inline, retain buffer", "#55a79f"),
        ("on", "immediate", "Full inline, immediate free", "#16857b"),
    ]
    workers = [2, 4]
    x = np.arange(len(workers))
    width = 0.25
    fig, ax = plt.subplots(figsize=(9.6, 5.4))

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
        bars = ax.bar(x + (index - 1) * width, values, width, label=label, color=color)
        ax.bar_label(bars, labels=[f"{value:.1f}" for value in values], padding=3, fontsize=9)

    ax.set_xticks(x, ["2 workers", "4 workers"])
    ax.set_ylabel("Successful physical TX (Mpps)")
    ax.set_ylim(0, 158)
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="upper left")
    ax.set_title(
        "CX6 TX-only: full-packet eMPW inline removes the pointer-DMA ceiling",
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.01,
        "True Ethernet64, one raw QP per worker; single matched 5-second causal screens",
        ha="center",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    save(fig, "cx6-inline-root-cause")


def cpu_chart(rows):
    fig, axes = plt.subplots(1, 2, figsize=(13.0, 5.3), sharey=True)
    width = 0.24
    group_x = np.arange(len(HARDWARE))

    for ax, workers in zip(axes, (1, 2)):
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
        ax.set_title(f"{workers} worker{'s' if workers > 1 else ''}", fontweight="bold")

    axes[0].set_ylabel("Dataplane cycles per successful packet (log scale; lower is better)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.93),
        ncol=3,
        frameon=False,
    )
    fig.suptitle(
        "All dataplane CPUs counted — AF_XDP includes colocated IRQ/NAPI kernel work",
        y=0.99,
        fontsize=14,
        fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.84))
    save(fig, "cpu-budget")


def main():
    rows = retained(load_rows())
    throughput_chart(rows)
    advantage_chart(rows)
    cpu_chart(rows)
    cx6_inline_chart()


if __name__ == "__main__":
    main()
