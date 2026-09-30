"""
benchmark.py – Thực nghiệm so sánh toàn diện các phương pháp giải Sudoku.

Phương pháp so sánh:
  ┌─────────────────┬─────────────────────────────────────────────────────┐
  │ Nhóm            │ Solvers                                             │
  ├─────────────────┼─────────────────────────────────────────────────────┤
  │ SAT Solving     │ Cadical195, Cadical300, Glucose4, Glucose42,       │
  │ (PySAT)         │ Kissat404, CryptoMiniSAT, Lingeling, Minisat22     │
  ├─────────────────┼─────────────────────────────────────────────────────┤
  │ CP              │ OR-Tools CP-SAT                                     │
  ├─────────────────┼─────────────────────────────────────────────────────┤
  │ ILP/MIP         │ HiGHS (via PuLP) – CPLEX MIP / Gurobi fallback    │
  └─────────────────┴─────────────────────────────────────────────────────┘

Chạy thực nghiệm:
  python benchmark.py [--runs N] [--timeout T] [--output results.csv]
"""

from __future__ import annotations
import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

from puzzles import ALL_PUZZLES, count_clues
from sat_solver import solve_sat, verify_solution, MAIN_SAT_SOLVERS
from cp_solver import solve_cp_sat
from ilp_solver import solve_ilp


# ── Cấu hình mặc định ─────────────────────────────────────────────────────────
DEFAULT_RUNS    = 3      # Số lần chạy mỗi (puzzle × solver) để lấy median
DEFAULT_TIMEOUT = 30.0   # Giây


# ── Định nghĩa các cấu hình solver cần thực nghiệm ────────────────────────────
def get_solver_configs() -> list[dict]:
    """Trả về danh sách các cấu hình solver sẽ được benchmark."""
    configs = []

    # ── SAT solvers ────────────────────────────────────────────────────────────
    sat_solvers = [
        ("cadical195",    "SAT",  "Cadical 1.9.5"),
        ("cadical300",    "SAT",  "Cadical 3.0.0"),
        ("glucose4",      "SAT",  "Glucose 4.x"),
        ("glucose42",     "SAT",  "Glucose 4.2"),
        ("kissat",        "SAT",  "Kissat 4.0.4"),
        ("cryptominisat", "SAT",  "CryptoMiniSAT"),
        ("lingeling",     "SAT",  "Lingeling"),
        ("minisat22",     "SAT",  "MiniSAT 2.2"),
    ]
    for solver_key, method, display_name in sat_solvers:
        configs.append({
            "method":       method,
            "solver_key":   solver_key,
            "display_name": display_name,
            "run_fn":       lambda g, sk=solver_key, to=DEFAULT_TIMEOUT: solve_sat(g, sk, to),
        })

    # ── CP solver ──────────────────────────────────────────────────────────────
    configs.append({
        "method":       "CP",
        "solver_key":   "cp-sat",
        "display_name": "OR-Tools CP-SAT",
        "run_fn":       lambda g, to=DEFAULT_TIMEOUT: solve_cp_sat(g, to),
    })

    # ── ILP/MIP solvers ────────────────────────────────────────────────────────
    ilp_backends = [
        ("cplex_mip", "ILP/MIP", "CPLEX MIP"),
        ("gurobi",    "ILP/MIP", "Gurobi MIP"),
        ("cpsat",     "ILP/MIP", "CPSAT-ILP (OR-Tools)"),
    ]
    for solver_key, method, display_name in ilp_backends:
        configs.append({
            "method":       method,
            "solver_key":   solver_key,
            "display_name": display_name,
            "run_fn":       lambda g, sk=solver_key, to=DEFAULT_TIMEOUT: solve_ilp(g, sk, to),
        })

    return configs


# ── Tiện ích ──────────────────────────────────────────────────────────────────

def median(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 == 1 else (s[mid - 1] + s[mid]) / 2


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def print_separator(char: str = "─", width: int = 110) -> None:
    print(char * width)


def print_table_row(*cols, widths=None) -> None:
    if widths is None:
        widths = [20] * len(cols)
    row = " │ ".join(str(c).ljust(w) for c, w in zip(cols, widths))
    print("│ " + row + " │")


def format_time(t: float) -> str:
    if t < 0.001:
        return f"{t * 1000:.3f} ms"
    elif t < 1.0:
        return f"{t * 1000:.2f} ms"
    else:
        return f"{t:.4f}  s"


# ── Hàm chạy benchmark ──────────────────────────────────────────────────────────

def run_single(
    puzzle_name: str,
    grid: list[list[int]],
    cfg: dict,
    runs: int,
    timeout: float,
) -> dict:
    """
    Chạy một solver trên một puzzle nhiều lần, trả về dict kết quả tổng hợp.
    """
    times_total  = []
    times_solve  = []
    last_result  = None

    for _ in range(runs):
        result = cfg["run_fn"](grid)
        last_result = result
        if result.get("status") in ("SAT", "UNSAT"):
            times_total.append(result.get("time_total", 0))
            times_solve.append(result.get("time_solve", result.get("time_total", 0)))

    status = last_result.get("status", "ERROR") if last_result else "ERROR"

    # Xác minh solution
    valid = False
    if status == "SAT" and last_result and last_result.get("solution"):
        valid = verify_solution(grid, last_result["solution"])

    return {
        "puzzle":        puzzle_name,
        "clues":         count_clues(grid),
        "method":        cfg["method"],
        "solver":        cfg["display_name"],
        "solver_key":    cfg["solver_key"],
        "status":        status,
        "valid":         valid,
        "time_median_s": round(median(times_total), 6) if times_total else None,
        "time_mean_s":   round(mean(times_total),   6) if times_total else None,
        "time_min_s":    round(min(times_total),     6) if times_total else None,
        "num_runs":      len(times_total),
        # Thông tin model (lấy từ lần chạy cuối)
        "num_vars":      last_result.get("num_vars"),
        "num_clauses":   last_result.get("num_clauses")
                         or last_result.get("num_constraints"),
    }


def run_benchmark(
    runs: int = DEFAULT_RUNS,
    timeout: float = DEFAULT_TIMEOUT,
    verbose: bool = True,
) -> list[dict]:
    """
    Chạy toàn bộ thực nghiệm.

    Returns
    -------
    list[dict] – mỗi dict là kết quả một (puzzle × solver).
    """
    configs = get_solver_configs()
    all_results = []

    total_tasks = len(ALL_PUZZLES) * len(configs)
    done = 0

    if verbose:
        print()
        print("=" * 110)
        print(" SUDOKU SOLVER BENCHMARK – So sánh SAT / CP / ILP".center(110))
        print("=" * 110)
        print(f"  Puzzles  : {len(ALL_PUZZLES)}")
        print(f"  Solvers  : {len(configs)}")
        print(f"  Runs/task: {runs}")
        print(f"  Timeout  : {timeout}s")
        print(f"  Total    : {total_tasks} tasks")
        print("=" * 110)

    for puzzle_name, grid in ALL_PUZZLES:
        if verbose:
            print(f"\n{'─'*110}")
            print(f"  Puzzle: {puzzle_name}  (clues: {count_clues(grid)})")
            print(f"{'─'*110}")
            header_widths = [22, 12, 15, 8, 7, 15, 15, 10]
            print_table_row(
                "Solver", "Method", "Status", "Valid",
                "Runs", "Median (total)", "Min (total)", "Vars/Clauses",
                widths=header_widths,
            )
            print_separator()

        for cfg in configs:
            result = run_single(puzzle_name, grid, cfg, runs, timeout)
            all_results.append(result)
            done += 1

            if verbose:
                t_str = (
                    format_time(result["time_median_s"])
                    if result["time_median_s"] is not None
                    else "N/A"
                )
                t_min_str = (
                    format_time(result["time_min_s"])
                    if result["time_min_s"] is not None
                    else "N/A"
                )
                model_info = ""
                if result["num_vars"] and result["num_clauses"]:
                    model_info = f"{result['num_vars']}v/{result['num_clauses']}c"
                elif result["num_vars"]:
                    model_info = f"{result['num_vars']}v"

                print_table_row(
                    result["solver"][:22],
                    result["method"],
                    result["status"],
                    "✓" if result["valid"] else ("✗" if result["status"] == "SAT" else "–"),
                    str(result["num_runs"]),
                    t_str,
                    t_min_str,
                    model_info,
                    widths=header_widths,
                )

    return all_results


# ── Xuất kết quả ──────────────────────────────────────────────────────────────

def save_csv(results: list[dict], path: str) -> None:
    """Ghi kết quả ra file CSV."""
    if not results:
        return
    fieldnames = list(results[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"\n[✓] Kết quả CSV đã lưu → {path}")


def save_json(results: list[dict], path: str) -> None:
    """Ghi kết quả ra file JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"[✓] Kết quả JSON đã lưu → {path}")


# ── Bảng tổng kết ─────────────────────────────────────────────────────────────

def print_summary(results: list[dict]) -> None:
    """In bảng tổng kết theo solver."""
    print("\n")
    print("=" * 110)
    print(" BẢNG TỔNG KẾT – Hiệu năng trung bình theo Solver".center(110))
    print("=" * 110)

    # Nhóm theo solver
    from collections import defaultdict
    solver_results = defaultdict(list)
    for r in results:
        if r["status"] in ("SAT", "UNSAT") and r["time_median_s"] is not None:
            solver_results[(r["solver"], r["method"])].append(r)

    # Header
    widths = [25, 12, 8, 12, 12, 12, 10]
    print_table_row(
        "Solver", "Method", "Solved", "Mean (s)", "Median (s)", "Max (s)", "Verify OK",
        widths=widths,
    )
    print_separator()

    # Sort theo mean time
    rows = []
    for (solver, method), rs in solver_results.items():
        times    = [r["time_median_s"] for r in rs if r["time_median_s"] is not None]
        n_solved = sum(1 for r in rs if r["status"] == "SAT")
        n_valid  = sum(1 for r in rs if r["valid"])
        n_total  = len(rs)

        rows.append({
            "solver":    solver,
            "method":    method,
            "n_solved":  n_solved,
            "n_total":   n_total,
            "mean_time": mean(times),
            "med_time":  median(times),
            "max_time":  max(times) if times else 0,
            "n_valid":   n_valid,
        })

    rows.sort(key=lambda r: r["mean_time"])

    for row in rows:
        print_table_row(
            row["solver"][:25],
            row["method"],
            f"{row['n_solved']}/{row['n_total']}",
            f"{row['mean_time']:.6f}",
            f"{row['med_time']:.6f}",
            f"{row['max_time']:.6f}",
            f"{row['n_valid']}/{row['n_total']}",
            widths=widths,
        )

    print_separator()
    print()


def print_difficulty_breakdown(results: list[dict]) -> None:
    """In bảng chi tiết theo difficulty level."""
    from collections import defaultdict

    # Xác định difficulty từ tên puzzle
    def get_difficulty(puzzle_name: str) -> str:
        name = puzzle_name.lower()
        for level in ("easy", "medium", "hard", "expert"):
            if level in name:
                return level.capitalize()
        return "Unknown"

    print("=" * 110)
    print(" PHÂN TÍCH THEO MỨC ĐỘ KHÓ".center(110))
    print("=" * 110)

    by_difficulty = defaultdict(lambda: defaultdict(list))
    for r in results:
        if r["time_median_s"] is not None and r["status"] == "SAT":
            diff = get_difficulty(r["puzzle"])
            by_difficulty[diff][(r["solver"], r["method"])].append(r["time_median_s"])

    widths = [25, 12, 12, 12, 12, 12]
    print_table_row("Solver", "Method", "Easy(s)", "Medium(s)", "Hard(s)", "Expert(s)", widths=widths)
    print_separator()

    # Collect all solvers
    all_solvers = set()
    for diff_data in by_difficulty.values():
        all_solvers.update(diff_data.keys())

    for (solver, method) in sorted(all_solvers):
        row = [solver[:25], method]
        for level in ("Easy", "Medium", "Hard", "Expert"):
            times = by_difficulty[level].get((solver, method), [])
            row.append(f"{mean(times):.6f}" if times else "  N/A   ")
        print_table_row(*row, widths=widths)

    print_separator()


# ── Entry point ───────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Sudoku Solver Benchmark")
    p.add_argument("--runs",    type=int,   default=DEFAULT_RUNS,    help="Số lần chạy mỗi task (default: 3)")
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="Timeout mỗi solver (giây, default: 30)")
    p.add_argument("--output",  type=str,   default="results",       help="Tiền tố tên file output (default: results)")
    p.add_argument("--no-save", action="store_true",                 help="Không lưu file kết quả")
    p.add_argument("--quick",   action="store_true",                 help="Chỉ chạy 1 lần, ít solver hơn (debug)")
    return p.parse_args()


def main():
    args = parse_args()

    runs    = 1 if args.quick else args.runs
    timeout = args.timeout

    t_start = time.perf_counter()
    results = run_benchmark(runs=runs, timeout=timeout, verbose=True)
    t_end   = time.perf_counter()

    print_summary(results)
    print_difficulty_breakdown(results)

    print(f"\n[⏱]  Tổng thời gian benchmark: {t_end - t_start:.2f}s")

    if not args.no_save:
        save_csv(results,  args.output + ".csv")
        save_json(results, args.output + ".json")


if __name__ == "__main__":
    main()
