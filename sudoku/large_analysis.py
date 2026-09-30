"""
large_analysis.py – Visualize large-scale benchmark results (9x9/16x16/25x25).

Generates 4 figures for the paper:
  figA_amo_comparison_bar.png   – AMO encoding comparison by grid size
  figB_amo_clause_reduction.png – Clause count reduction vs. Pairwise
  figC_size_scaling.png         – Solve time vs. grid size (n) per encoding
  figD_method_comparison.png    – SAT vs. CP vs. ILP across sizes
"""
from __future__ import annotations
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── Styling ───────────────────────────────────────────────────────────────────
AMO_COLORS = {
    "pairwise":   "#E53935",   # red
    "binary":     "#FB8C00",   # orange
    "commander":  "#43A047",   # green
    "product":    "#1E88E5",   # blue
    "sequential": "#8E24AA",   # purple
}
AMO_LABELS = {
    "pairwise":   "Pairwise",
    "binary":     "Binary (Log)",
    "commander":  "Commander",
    "product":    "Product",
    "sequential": "Sequential Counter",
}
SIZE_MARKERS = {9: "o", 16: "s", 25: "^"}

METHOD_COLORS = {
    "SAT":     "#2196F3",
    "CP":      "#4CAF50",
    "ILP":     "#FF9800",
}


# ── Data loading ──────────────────────────────────────────────────────────────

def load_large_results(path: str = "large_results.csv") -> list[dict]:
    results = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for k in ("time_median_s", "time_mean_s", "time_encode_s",
                      "time_solve_s", "num_base_vars", "num_aux_vars",
                      "num_clauses", "clues", "fill_pct", "n"):
                try:
                    row[k] = float(row[k]) if row[k] not in ("", "None") else None
                except (ValueError, KeyError):
                    pass
            results.append(row)
    return results


# ── Figure A: AMO Comparison Bar Chart ───────────────────────────────────────

def plot_amo_comparison_bar(results: list[dict], output_dir: Path) -> None:
    """
    Grouped bar chart: mean solve time per AMO encoding, one group per grid size.
    """
    amo_names = ["pairwise", "binary", "commander", "product", "sequential"]
    sizes     = [9, 16, 25]

    # Build: data[n][amo] = list of median times (ms)
    data = defaultdict(lambda: defaultdict(list))
    for r in results:
        if (r.get("method") == "SAT"
                and r.get("status") == "SAT"
                and r.get("amo_encoding") in amo_names
                and r.get("time_median_s") is not None):
            n   = int(r["n"])
            amo = r["amo_encoding"]
            data[n][amo].append(float(r["time_median_s"]) * 1000)

    fig, axes = plt.subplots(1, 3, figsize=(16, 5), sharey=False)

    for ax_idx, n in enumerate(sizes):
        ax = axes[ax_idx]
        means  = [np.mean(data[n].get(amo, [0])) for amo in amo_names]
        colors = [AMO_COLORS[a] for a in amo_names]
        labels = [AMO_LABELS[a] for a in amo_names]

        bars = ax.bar(range(len(amo_names)), means, color=colors,
                      edgecolor="white", linewidth=0.6, alpha=0.88)

        ax.set_title(f"{n}×{n} Sudoku", fontsize=12, fontweight="bold")
        ax.set_xticks(range(len(amo_names)))
        ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=9)
        ax.set_ylabel("Mean Time (ms)" if ax_idx == 0 else "")
        ax.grid(axis="y", linestyle="--", alpha=0.4)

        # Annotate values
        for bar, v in zip(bars, means):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() * 1.02,
                    f"{v:.1f}", ha="center", va="bottom", fontsize=8.5,
                    fontweight="bold")

        # Speedup vs. pairwise
        pairwise_mean = np.mean(data[n].get("pairwise", [1]))
        for i, (bar, v) in enumerate(zip(bars, means)):
            if amo_names[i] != "pairwise" and pairwise_mean > 0:
                speedup = pairwise_mean / v
                color_sp = "#2E7D32" if speedup > 1 else "#C62828"
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() * 0.55,
                        f"{speedup:.2f}×", ha="center", va="center",
                        fontsize=7, color="white", fontweight="bold")

    fig.suptitle("AMO Encoding Comparison – Mean Solve Time by Grid Size\n"
                 "(Cadical 1.9.5, median of 3 runs; annotation = speedup vs. Pairwise)",
                 fontsize=12, fontweight="bold")
    plt.tight_layout()
    out = output_dir / "figA_amo_comparison_bar.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[✓] Figure A → {out}")


# ── Figure B: Clause count reduction ─────────────────────────────────────────

def plot_clause_reduction(results: list[dict], output_dir: Path) -> None:
    """
    Grouped bar chart: number of clauses per encoding per grid size.
    Annotates reduction % relative to Pairwise.
    """
    amo_names = ["pairwise", "binary", "commander", "product", "sequential"]
    sizes     = [9, 16, 25]

    # Build: clauses[n][amo] = first seen clause count
    clauses_data = {}
    aux_data     = {}
    for r in results:
        if (r.get("method") == "SAT"
                and r.get("status") == "SAT"
                and r.get("amo_encoding") in amo_names
                and r.get("num_clauses") is not None):
            n   = int(r["n"])
            amo = r["amo_encoding"]
            key = (n, amo)
            if key not in clauses_data:
                clauses_data[key] = float(r["num_clauses"])
                aux_data[key]     = float(r.get("num_aux_vars") or 0)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Left: Clause count
    ax = axes[0]
    x = np.arange(len(sizes))
    width = 0.8 / len(amo_names)

    for i, amo in enumerate(amo_names):
        counts = [clauses_data.get((n, amo), 0) / 1000 for n in sizes]  # in thousands
        offset = (i - len(amo_names) / 2 + 0.5) * width
        bars = ax.bar(x + offset, counts, width * 0.9,
                      color=AMO_COLORS[amo], label=AMO_LABELS[amo],
                      edgecolor="white", alpha=0.88)

    ax.set_xticks(x)
    ax.set_xticklabels([f"{n}×{n}" for n in sizes], fontsize=11)
    ax.set_ylabel("Number of Clauses (×1000)", fontsize=10)
    ax.set_title("Clause Count per AMO Encoding", fontsize=11, fontweight="bold")
    ax.set_yscale("log")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend(fontsize=8.5, loc="upper left")

    # Right: Reduction % relative to Pairwise
    ax2 = axes[1]
    for i, amo in enumerate(amo_names):
        if amo == "pairwise":
            continue
        reductions = []
        for n in sizes:
            base = clauses_data.get((n, "pairwise"), None)
            val  = clauses_data.get((n, amo), None)
            if base and val and base > 0:
                reductions.append((base - val) / base * 100)
            else:
                reductions.append(0)
        ax2.plot(sizes, reductions, marker="o", linewidth=2,
                 color=AMO_COLORS[amo], label=AMO_LABELS[amo], markersize=7)
        for nx, rx in zip(sizes, reductions):
            ax2.annotate(f"{rx:.1f}%", (nx, rx), textcoords="offset points",
                         xytext=(4, 4), fontsize=8, color=AMO_COLORS[amo])

    ax2.set_xticks(sizes)
    ax2.set_xticklabels([f"{n}×{n}" for n in sizes], fontsize=11)
    ax2.set_ylabel("Clause Reduction vs. Pairwise (%)", fontsize=10)
    ax2.set_title("Clause Count Reduction Relative to Pairwise", fontsize=11, fontweight="bold")
    ax2.grid(True, linestyle="--", alpha=0.35)
    ax2.legend(fontsize=8.5)
    ax2.set_ylim(0, 75)

    fig.suptitle("CNF Formula Size: AMO Encoding Comparison",
                 fontsize=12, fontweight="bold")
    plt.tight_layout()
    out = output_dir / "figB_amo_clause_reduction.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[✓] Figure B → {out}")


# ── Figure C: Solve time scaling with grid size ───────────────────────────────

def plot_size_scaling(results: list[dict], output_dir: Path) -> None:
    """
    Line chart: mean solve time (ms) vs. grid size n² for each AMO encoding.
    """
    amo_names = ["pairwise", "binary", "commander", "product", "sequential"]
    sizes     = [9, 16, 25]

    data = defaultdict(lambda: defaultdict(list))
    for r in results:
        if (r.get("method") == "SAT"
                and r.get("status") == "SAT"
                and r.get("amo_encoding") in amo_names
                and r.get("time_median_s") is not None):
            n   = int(r["n"])
            amo = r["amo_encoding"]
            data[amo][n].append(float(r["time_median_s"]) * 1000)

    fig, ax = plt.subplots(figsize=(10, 6))

    for amo in amo_names:
        means = [np.mean(data[amo].get(n, [0])) for n in sizes]
        ax.plot(sizes, means, marker="o", linewidth=2.2,
                color=AMO_COLORS[amo], label=AMO_LABELS[amo], markersize=8)
        for nx, mx in zip(sizes, means):
            ax.annotate(f"{mx:.0f}ms", (nx, mx),
                        textcoords="offset points", xytext=(5, 3),
                        fontsize=8, color=AMO_COLORS[amo])

    ax.set_xticks(sizes)
    ax.set_xticklabels([f"{n}×{n}\n(n={n})" for n in sizes], fontsize=10)
    ax.set_ylabel("Mean Solve Time (ms)", fontsize=11)
    ax.set_xlabel("Grid Size", fontsize=11)
    ax.set_yscale("log")
    ax.set_title("Solve Time Scaling with Grid Size – AMO Encoding Comparison\n"
                 "(SAT backend: Cadical 1.9.5, Pairwise encoding)",
                 fontsize=11, fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.35)
    ax.legend(fontsize=10, loc="upper left")

    plt.tight_layout()
    out = output_dir / "figC_size_scaling.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[✓] Figure C → {out}")


# ── Figure D: SAT vs CP vs ILP comparison ────────────────────────────────────

def plot_method_comparison(results: list[dict], output_dir: Path) -> None:
    """
    Bar chart: compare best-SAT (Product/Commander), CP-SAT, and ILP across sizes.
    """
    sizes = [9, 16]

    # Best SAT = Product encoding
    best_sat_amo = "product"

    data = defaultdict(lambda: defaultdict(list))
    for r in results:
        if r.get("status") != "SAT" or r.get("time_median_s") is None:
            continue
        n = int(r["n"])
        method = r.get("method", "")
        amo    = r.get("amo_encoding", "N/A")

        if method == "SAT" and amo == best_sat_amo:
            data[n]["SAT-Product"].append(float(r["time_median_s"]) * 1000)
        elif method == "SAT" and amo == "pairwise":
            data[n]["SAT-Pairwise"].append(float(r["time_median_s"]) * 1000)
        elif method == "CP":
            data[n]["CP-SAT"].append(float(r["time_median_s"]) * 1000)
        elif method == "ILP":
            data[n]["ILP"].append(float(r["time_median_s"]) * 1000)

    solvers_order = ["SAT-Pairwise", "SAT-Product", "CP-SAT", "ILP"]
    solver_colors = {
        "SAT-Pairwise": "#90CAF9",
        "SAT-Product":  "#1565C0",
        "CP-SAT":       "#4CAF50",
        "ILP":          "#FF9800",
    }

    fig, axes = plt.subplots(1, len(sizes), figsize=(12, 5), sharey=False)

    for ax_idx, n in enumerate(sizes):
        ax = axes[ax_idx]
        means  = [np.mean(data[n].get(s, [0])) for s in solvers_order]
        colors = [solver_colors[s] for s in solvers_order]

        bars = ax.bar(range(len(solvers_order)), means, color=colors,
                      edgecolor="white", linewidth=0.6, alpha=0.9)
        ax.set_title(f"{n}×{n} Sudoku", fontsize=12, fontweight="bold")
        ax.set_xticks(range(len(solvers_order)))
        ax.set_xticklabels(solvers_order, rotation=20, ha="right", fontsize=9)
        ax.set_ylabel("Mean Time (ms)" if ax_idx == 0 else "")
        ax.grid(axis="y", linestyle="--", alpha=0.4)

        for bar, v in zip(bars, means):
            if v > 0:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() * 1.02,
                        f"{v:.1f}ms", ha="center", va="bottom",
                        fontsize=9, fontweight="bold")

    # Legend
    patches = [mpatches.Patch(color=solver_colors[s], label=s) for s in solvers_order]
    fig.legend(handles=patches, loc="upper right", fontsize=9,
               bbox_to_anchor=(1.0, 1.0))

    fig.suptitle("SAT vs. CP vs. ILP/MIP – Method Comparison by Grid Size",
                 fontsize=12, fontweight="bold")
    plt.tight_layout()
    out = output_dir / "figD_method_comparison.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[✓] Figure D → {out}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--input",  default="large_results.csv")
    p.add_argument("--output", default=".")
    args = p.parse_args()

    if not Path(args.input).exists():
        print(f"[!] {args.input} not found – run large_benchmark.py first.")
        return

    results = load_large_results(args.input)
    print(f"[✓] Loaded {len(results)} rows from {args.input}")

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n[→] Generating large-scale figures...")
    plot_amo_comparison_bar(results, output_dir)
    plot_clause_reduction(results, output_dir)
    plot_size_scaling(results, output_dir)
    plot_method_comparison(results, output_dir)
    print("\n[✓] All large-scale figures generated.")


if __name__ == "__main__":
    main()
