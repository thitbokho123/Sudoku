"""
analysis.py – Analyze and visualize Sudoku solver benchmark results.

Generates comparison charts:
  1. Bar chart: average time per solver
  2. Grouped bar chart: by difficulty level
  3. Heatmap: solve time (solver × puzzle)
  4. Line plot: time scaling by difficulty
  5. Bar chart: detailed SAT solver comparison by difficulty

Usage:
  python analysis.py                   # reads results.csv (default)
  python analysis.py --input my.csv    # specify input file
  python analysis.py --no-plot         # text report only
"""

from __future__ import annotations
import argparse
import csv
from collections import defaultdict
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")   # non-interactive backend (no display needed)
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    print("[!] matplotlib/numpy not installed – text report only.")


# ── Colour palette ────────────────────────────────────────────────────────────
METHOD_COLORS = {
    "SAT":     "#2196F3",   # blue
    "CP":      "#4CAF50",   # green
    "ILP/MIP": "#FF9800",   # orange
}

DIFFICULTY_ORDER = ["Easy", "Medium", "Hard", "Expert"]


# ── Data loading ──────────────────────────────────────────────────────────────

def load_results(path: str) -> list[dict]:
    """Load benchmark results from CSV file."""
    results = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for key in ("time_median_s", "time_mean_s", "time_min_s",
                        "num_vars", "num_clauses", "clues"):
                try:
                    row[key] = float(row[key]) if row[key] not in ("", "None") else None
                except (ValueError, KeyError):
                    pass
            results.append(row)
    return results


def get_difficulty(puzzle_name: str) -> str:
    name = puzzle_name.lower()
    for level in ("easy", "medium", "hard", "expert"):
        if level in name:
            return level.capitalize()
    return "Unknown"


# ── Aggregation helpers ───────────────────────────────────────────────────────

def aggregate_by_solver(results: list[dict]) -> dict:
    """Group results by (solver, method)."""
    data = defaultdict(list)
    for r in results:
        if r.get("status") == "SAT" and r.get("time_median_s") is not None:
            key = (r["solver"], r["method"])
            data[key].append(float(r["time_median_s"]))
    return data


def aggregate_by_difficulty(results: list[dict]) -> dict:
    """Group results by (solver, method, difficulty)."""
    data = defaultdict(lambda: defaultdict(list))
    for r in results:
        if r.get("status") == "SAT" and r.get("time_median_s") is not None:
            key  = (r["solver"], r["method"])
            diff = get_difficulty(r["puzzle"])
            data[key][diff].append(float(r["time_median_s"]))
    return data


# ── Figure 1: Overall bar chart ───────────────────────────────────────────────

def plot_overall_bar(results: list[dict], output_dir: Path) -> None:
    """Bar chart of mean solve time per solver (all puzzles, log scale)."""
    data = aggregate_by_solver(results)
    if not data:
        return

    labels  = []
    means   = []
    medians = []
    colors  = []

    for (solver, method), times in sorted(data.items(), key=lambda x: sum(x[1]) / len(x[1])):
        labels.append(solver.replace(" (OR-Tools via PuLP)", "\n(via PuLP)"))
        means.append(sum(times) / len(times) * 1000)           # ms
        medians.append(sorted(times)[len(times) // 2] * 1000)  # median ms
        colors.append(METHOD_COLORS.get(method, "#9E9E9E"))

    fig, ax = plt.subplots(figsize=(14, 6))
    x = range(len(labels))
    ax.bar(x, means, color=colors, alpha=0.85, edgecolor="white", linewidth=0.5)
    ax.scatter(x, medians, color="black", s=30, zorder=5, marker="D", label="Median")

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8.5)
    ax.set_ylabel("Time (ms)", fontsize=11)
    ax.set_title(
        "Sudoku Solver Performance – Mean Solve Time (12 puzzles × 3 runs)",
        fontsize=12, fontweight="bold",
    )
    ax.set_yscale("log")
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    patches = [mpatches.Patch(color=c, label=m) for m, c in METHOD_COLORS.items()]
    ax.legend(
        handles=patches + [plt.scatter([], [], c="black", marker="D", s=30, label="Median")],
        loc="upper left", fontsize=9,
    )

    plt.tight_layout()
    out = output_dir / "fig1_overall_bar.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[✓] Figure 1 → {out}")


# ── Figure 2: Grouped bar chart by difficulty ─────────────────────────────────

def plot_difficulty_grouped(results: list[dict], output_dir: Path) -> None:
    """Grouped bar chart showing mean time by difficulty level per solver."""
    data = aggregate_by_difficulty(results)
    if not data:
        return

    solver_keys = sorted(data.keys(), key=lambda k: sum(sum(v) for v in data[k].values()))
    n_solvers = len(solver_keys)
    n_diff    = len(DIFFICULTY_ORDER)

    fig, ax = plt.subplots(figsize=(16, 6))
    width   = 0.8 / n_solvers
    x       = np.arange(n_diff)

    for i, (solver, method) in enumerate(solver_keys):
        means = [
            (sum(data[(solver, method)].get(d, [0])) /
             max(len(data[(solver, method)].get(d, [1])), 1)) * 1000
            for d in DIFFICULTY_ORDER
        ]
        offset = (i - n_solvers / 2 + 0.5) * width
        color  = METHOD_COLORS.get(method, "#9E9E9E")
        label  = solver.replace(" (OR-Tools via PuLP)", "")
        ax.bar(x + offset, means, width * 0.9, label=label,
               color=color, alpha=min(0.7 + i * 0.03, 0.99), edgecolor="white")

    ax.set_xticks(x)
    ax.set_xticklabels(DIFFICULTY_ORDER, fontsize=11)
    ax.set_ylabel("Mean Time (ms)", fontsize=11)
    ax.set_title("Solver Performance by Difficulty Level – SAT / CP / ILP",
                 fontsize=12, fontweight="bold")
    ax.set_yscale("log")
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    ax.legend(bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=7.5)

    plt.tight_layout()
    out = output_dir / "fig2_difficulty_grouped.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[✓] Figure 2 → {out}")


# ── Figure 3: Heatmap (solver × puzzle) ──────────────────────────────────────

def plot_heatmap(results: list[dict], output_dir: Path) -> None:
    """Heatmap of solve time (ms) across all solver–puzzle pairs."""
    puzzles = []
    seen = set()
    for r in results:
        p = r["puzzle"]
        if p not in seen:
            puzzles.append(p)
            seen.add(p)

    solvers = []
    seen = set()
    for r in results:
        s = (r["solver"], r["method"])
        if s not in seen:
            solvers.append(s)
            seen.add(s)

    lookup = {}
    for r in results:
        if r.get("time_median_s") is not None:
            lookup[(r["puzzle"], r["solver"], r["method"])] = float(r["time_median_s"]) * 1000

    matrix = np.zeros((len(solvers), len(puzzles)))
    for i, (solver, method) in enumerate(solvers):
        for j, puzzle in enumerate(puzzles):
            matrix[i, j] = lookup.get((puzzle, solver, method), 0)

    fig, ax = plt.subplots(figsize=(14, 8))
    import matplotlib.colors as mcolors
    im = ax.imshow(
        matrix, aspect="auto",
        norm=mcolors.LogNorm(vmin=max(matrix.min(), 0.1), vmax=matrix.max()),
        cmap="YlOrRd",
    )
    plt.colorbar(im, ax=ax, label="Solve Time (ms)")

    ax.set_xticks(range(len(puzzles)))
    ax.set_xticklabels(puzzles, rotation=45, ha="right", fontsize=9)
    ax.set_yticks(range(len(solvers)))
    solver_labels = [
        f"[{m}] {s.replace(' (OR-Tools via PuLP)', '')}"
        for s, m in solvers
    ]
    ax.set_yticklabels(solver_labels, fontsize=9)

    for i in range(len(solvers)):
        for j in range(len(puzzles)):
            v = matrix[i, j]
            ax.text(j, i, f"{v:.1f}", ha="center", va="center",
                    fontsize=6.5, color="black" if v < 50 else "white")

    ax.set_title("Solve Time Heatmap (ms) – Solver × Puzzle",
                 fontsize=12, fontweight="bold")
    plt.tight_layout()
    out = output_dir / "fig3_heatmap.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[✓] Figure 3 → {out}")


# ── Figure 4: Line plot – time vs difficulty ──────────────────────────────────

def plot_scaling(results: list[dict], output_dir: Path) -> None:
    """Line plot showing how solve time scales with difficulty level."""
    data = aggregate_by_difficulty(results)

    fig, ax = plt.subplots(figsize=(10, 6))
    diff_x = list(range(len(DIFFICULTY_ORDER)))

    for (solver, method), diff_data in sorted(data.items()):
        y = [
            (sum(diff_data.get(d, [0])) / max(len(diff_data.get(d, [1])), 1)) * 1000
            for d in DIFFICULTY_ORDER
        ]
        color     = METHOD_COLORS.get(method, "#9E9E9E")
        linestyle = {"SAT": "-", "CP": "--", "ILP/MIP": "-."}[method]
        label     = solver.replace(" (OR-Tools via PuLP)", "").replace("CPSAT ", "")
        ax.plot(diff_x, y, marker="o", linestyle=linestyle,
                color=color, alpha=0.85, linewidth=1.8,
                label=label, markersize=5)

    ax.set_xticks(diff_x)
    ax.set_xticklabels(DIFFICULTY_ORDER, fontsize=11)
    ax.set_ylabel("Mean Time (ms)", fontsize=11)
    ax.set_yscale("log")
    ax.set_title("Solve Time Scaling by Difficulty Level",
                 fontsize=12, fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.35)
    ax.legend(bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=7.5)

    plt.tight_layout()
    out = output_dir / "fig4_scaling.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[✓] Figure 4 → {out}")


# ── Figure 5: SAT solver detail comparison ────────────────────────────────────

def plot_sat_comparison(results: list[dict], output_dir: Path) -> None:
    """Detailed comparison of SAT solvers grouped by difficulty level."""
    sat_results = [
        r for r in results
        if r.get("method") == "SAT"
        and r.get("status") == "SAT"
        and r.get("time_median_s") is not None
    ]
    if not sat_results:
        return

    by_solver_diff = defaultdict(lambda: defaultdict(list))
    for r in sat_results:
        diff = get_difficulty(r["puzzle"])
        by_solver_diff[r["solver"]][diff].append(float(r["time_median_s"]) * 1000)

    solvers = sorted(
        by_solver_diff.keys(),
        key=lambda s: sum(sum(v) for v in by_solver_diff[s].values()),
    )

    PALETTE = [
        "#1565C0", "#0288D1", "#00838F", "#2E7D32",
        "#558B2F", "#F9A825", "#E65100", "#B71C1C",
    ]

    fig, axes = plt.subplots(1, 4, figsize=(16, 5), sharey=False)

    for ax_idx, diff in enumerate(DIFFICULTY_ORDER):
        ax = axes[ax_idx]
        vals = [
            sum(by_solver_diff[s].get(diff, [0])) /
            max(len(by_solver_diff[s].get(diff, [1])), 1)
            for s in solvers
        ]
        bars = ax.bar(range(len(solvers)), vals,
                      color=PALETTE[:len(solvers)],
                      edgecolor="white", linewidth=0.5)
        ax.set_title(diff, fontsize=11, fontweight="bold")
        ax.set_xticks(range(len(solvers)))
        ax.set_xticklabels(
            [s.replace("Glucose ", "G").replace("Cadical ", "C")
              .replace("CryptoMiniSAT", "CMS").replace("MiniSAT 2.2", "MiniSAT")
              .replace("Kissat 4.0.4", "Kissat").replace("OR-Tools CP-SAT", "CP-SAT")
             for s in solvers],
            rotation=45, ha="right", fontsize=8,
        )
        ax.set_ylabel("Time (ms)" if ax_idx == 0 else "")
        ax.grid(axis="y", linestyle="--", alpha=0.4)

        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.0002,
                    f"{v:.2f}", ha="center", va="bottom", fontsize=7)

    fig.suptitle("Detailed SAT Solver Comparison (PySAT) by Difficulty Level",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    out = output_dir / "fig5_sat_comparison.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[✓] Figure 5 → {out}")


# ── Text report ───────────────────────────────────────────────────────────────

def print_text_report(results: list[dict]) -> None:
    """Print a formatted text analysis report."""
    print()
    print("=" * 90)
    print(" SUDOKU SOLVER BENCHMARK – ANALYSIS REPORT")
    print("=" * 90)

    data = aggregate_by_solver(results)
    if not data:
        print("No data found.")
        return

    ranking = sorted(
        [(solver, method, ts) for (solver, method), ts in data.items()],
        key=lambda x: sum(x[2]) / len(x[2]),
    )

    print(f"\n{'Rank':<5} {'Solver':<35} {'Method':<10} "
          f"{'Mean(ms)':<12} {'Median(ms)':<12} {'Min(ms)':<10}")
    print("-" * 90)
    for rank, (solver, method, times) in enumerate(ranking, 1):
        mean_ms   = sum(times) / len(times) * 1000
        sorted_ts = sorted(times)
        med_ms    = sorted_ts[len(sorted_ts) // 2] * 1000
        min_ms    = min(times) * 1000
        print(f"{rank:<5} {solver:<35} {method:<10} "
              f"{mean_ms:<12.4f} {med_ms:<12.4f} {min_ms:<10.4f}")

    # Group by method
    print("\n--- Summary by Method ---")
    method_times = defaultdict(list)
    for solver, method, times in ranking:
        method_times[method].extend(times)

    for method, times in sorted(method_times.items()):
        mean_ms = sum(times) / len(times) * 1000
        print(f"  {method:<12}: Mean={mean_ms:.4f}ms  n={len(times)}")

    print("\n--- Key Observations ---")
    fastest = ranking[0]
    slowest = ranking[-1]
    print(f"  Fastest: {fastest[0]} ({fastest[1]}) – "
          f"{sum(fastest[2]) / len(fastest[2]) * 1000:.3f}ms avg")
    print(f"  Slowest: {slowest[0]} ({slowest[1]}) – "
          f"{sum(slowest[2]) / len(slowest[2]) * 1000:.3f}ms avg")

    sat_times = [t for s, m, ts in ranking if m == "SAT"     for t in ts]
    cp_times  = [t for s, m, ts in ranking if m == "CP"      for t in ts]
    ilp_times = [t for s, m, ts in ranking if m == "ILP/MIP" for t in ts]

    if sat_times and ilp_times:
        ratio = (sum(ilp_times) / len(ilp_times)) / (sum(sat_times) / len(sat_times))
        print(f"\n  ILP/MIP is {ratio:.1f}× slower than SAT on average")
    if sat_times and cp_times:
        ratio2 = (sum(cp_times) / len(cp_times)) / (sum(sat_times) / len(sat_times))
        cmp = "faster" if ratio2 < 1 else "slower"
        print(f"  CP is {abs(ratio2):.2f}× {cmp} than SAT on average")


# ── Entry point ───────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Analyze and visualize Sudoku benchmark results."
    )
    p.add_argument("--input",   type=str, default="results.csv", help="CSV input file")
    p.add_argument("--output",  type=str, default=".",           help="Output directory for figures")
    p.add_argument("--no-plot", action="store_true",             help="Skip figure generation")
    return p.parse_args()


def main():
    args = parse_args()

    if not Path(args.input).exists():
        print(f"[!] File not found: {args.input} – run benchmark.py first.")
        return

    results = load_results(args.input)
    print(f"[✓] Loaded {len(results)} rows from {args.input}")

    print_text_report(results)

    if args.no_plot or not HAS_MPL:
        return

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n[→] Generating figures...")
    plot_overall_bar(results, output_dir)
    plot_difficulty_grouped(results, output_dir)
    plot_heatmap(results, output_dir)
    plot_scaling(results, output_dir)
    plot_sat_comparison(results, output_dir)
    print("\n[✓] All figures generated successfully.")


if __name__ == "__main__":
    main()
