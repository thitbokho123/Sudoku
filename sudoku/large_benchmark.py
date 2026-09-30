"""
large_benchmark.py – Thực nghiệm toàn diện trên Sudoku kích thước lớn.

So sánh:
  - 5 chiến lược AMO encoding: Pairwise, Binary, Commander, Product, Sequential
  - 3 kích thước: 9×9, 16×16, 25×25
  - SAT solver: Cadical195 (primary), Glucose4, Kissat
  - CP: OR-Tools CP-SAT
  - ILP: PuLP CPSAT backend

Xuất kết quả ra CSV và JSON cho analysis.
"""
from __future__ import annotations
import csv
import json
import time
from pathlib import Path

from sat_encoding import (
    solve_sudoku_sat, verify_solution_general,
    SAT_SOLVER_MAP,
)
from cp_solver import solve_cp_sat
from ilp_solver import solve_ilp
from large_puzzles import ALL_LARGE_PUZZLES, count_clues, fill_ratio
from sat_solver import verify_solution  # for 9x9


TIMEOUT = 120.0
RUNS    = 3  # số lần chạy để lấy median

AMO_NAMES = ["pairwise", "sequential", "commander", "product", "binary"]
SAT_SOLVERS = ["cadical195", "glucose4", "kissat"]

# Solver chính để so sánh AMO (primary SAT solver)
PRIMARY_SAT = "cadical195"


def median(vals):
    if not vals:
        return None
    s = sorted(vals)
    n = len(s)
    return s[n // 2]


def mean(vals):
    return sum(vals) / len(vals) if vals else 0.0


def run_sat_encoding_experiment(
    verbose: bool = True,
) -> list[dict]:
    """
    Thực nghiệm chính: so sánh AMO encodings trên tất cả kích thước.
    """
    results = []

    for n, puzzles in sorted(ALL_LARGE_PUZZLES.items()):
        for puzzle_name, grid, n_, k in puzzles:
            clues     = count_clues(grid)
            fill_pct  = fill_ratio(grid, n_)

            if verbose:
                print(f"\n  ── {puzzle_name} ({n}×{n}, clues={clues}, fill={fill_pct:.1%}) ──")

            # ── SAT: AMO encoding comparison ──────────────────────────────
            for amo in AMO_NAMES:
                times_total  = []
                times_encode = []
                times_solve  = []
                last_r = None

                for run in range(RUNS):
                    r = solve_sudoku_sat(grid, n_, amo, PRIMARY_SAT, TIMEOUT)
                    last_r = r
                    if r.get("status") == "SAT":
                        times_total.append(r["time_total"])
                        times_encode.append(r["time_encode"])
                        times_solve.append(r["time_solve"])

                status = last_r.get("status", "ERROR")
                valid  = (verify_solution_general(grid, last_r.get("solution"), n_)
                          if status == "SAT" else False)

                record = {
                    "puzzle":        puzzle_name,
                    "n":             n_,
                    "clues":         clues,
                    "fill_pct":      round(fill_pct, 4),
                    "method":        "SAT",
                    "solver":        f"SAT-{amo}",
                    "amo_encoding":  amo,
                    "sat_backend":   PRIMARY_SAT,
                    "status":        status,
                    "valid":         valid,
                    "time_median_s": round(median(times_total) or 0, 6),
                    "time_mean_s":   round(mean(times_total), 6),
                    "time_encode_s": round(median(times_encode) or 0, 6),
                    "time_solve_s":  round(median(times_solve) or 0, 6),
                    "num_base_vars": last_r.get("num_vars", 0),
                    "num_aux_vars":  last_r.get("num_aux_vars", 0),
                    "num_clauses":   last_r.get("num_clauses", 0),
                    "num_runs":      len(times_total),
                }
                results.append(record)

                if verbose:
                    t_str = f"{record['time_median_s']*1000:.2f}ms" if times_total else "N/A"
                    print(f"    SAT-{amo:<12}: {status} valid={valid} "
                          f"clauses={record['num_clauses']:7d} aux={record['num_aux_vars']:5d} "
                          f"t={t_str}")

            # ── SAT: solver comparison (pairwise encoding, different SAT backends) ──
            if n_ <= 16:  # 25x25 too slow for some solvers
                for sat_solver in SAT_SOLVERS:
                    times = []
                    last_r = None
                    for _ in range(RUNS):
                        r = solve_sudoku_sat(grid, n_, "pairwise", sat_solver, TIMEOUT)
                        last_r = r
                        if r.get("status") == "SAT":
                            times.append(r["time_total"])

                    status = last_r.get("status", "ERROR") if last_r else "ERROR"
                    valid  = (verify_solution_general(grid, last_r.get("solution"), n_)
                              if status == "SAT" else False)

                    record = {
                        "puzzle":        puzzle_name,
                        "n":             n_,
                        "clues":         clues,
                        "fill_pct":      round(fill_pct, 4),
                        "method":        "SAT-backend",
                        "solver":        f"SAT-{sat_solver}",
                        "amo_encoding":  "pairwise",
                        "sat_backend":   sat_solver,
                        "status":        status,
                        "valid":         valid,
                        "time_median_s": round(median(times) or 0, 6),
                        "time_mean_s":   round(mean(times), 6),
                        "time_encode_s": round(last_r.get("time_encode", 0), 6) if last_r else 0,
                        "time_solve_s":  round(last_r.get("time_solve", 0), 6) if last_r else 0,
                        "num_base_vars": n_**3,
                        "num_aux_vars":  0,
                        "num_clauses":   last_r.get("num_clauses", 0) if last_r else 0,
                        "num_runs":      len(times),
                    }
                    results.append(record)

            # ── CP solver ─────────────────────────────────────────────────
            if n_ <= 25:
                times = []
                last_r = None
                for _ in range(RUNS):
                    r = solve_cp_sat(grid, timeout=TIMEOUT)
                    last_r = r
                    if r.get("status") == "SAT":
                        times.append(r["time_total"])

                status = last_r.get("status", "ERROR") if last_r else "ERROR"
                valid  = (verify_solution_general(grid, last_r.get("solution"), n_)
                          if status == "SAT" else False)

                record = {
                    "puzzle":        puzzle_name,
                    "n":             n_,
                    "clues":         clues,
                    "fill_pct":      round(fill_pct, 4),
                    "method":        "CP",
                    "solver":        "CP-SAT",
                    "amo_encoding":  "N/A",
                    "sat_backend":   "OR-Tools",
                    "status":        status,
                    "valid":         valid,
                    "time_median_s": round(median(times) or 0, 6),
                    "time_mean_s":   round(mean(times), 6),
                    "time_encode_s": round(last_r.get("time_model", 0), 6) if last_r else 0,
                    "time_solve_s":  round(last_r.get("time_solve", 0), 6) if last_r else 0,
                    "num_base_vars": 0,
                    "num_aux_vars":  0,
                    "num_clauses":   0,
                    "num_runs":      len(times),
                }
                results.append(record)

                if verbose:
                    t_str = f"{record['time_median_s']*1000:.2f}ms" if times else "N/A"
                    print(f"    CP-SAT          : {status} valid={valid} t={t_str}")

            # ── ILP solver ────────────────────────────────────────────────
            if n_ <= 9:  # ILP too slow for 16x16+
                times = []
                last_r = None
                for _ in range(RUNS):
                    r = solve_ilp(grid, "cpsat", timeout=TIMEOUT)
                    last_r = r
                    if r.get("status") == "SAT":
                        times.append(r["time_total"])

                status = last_r.get("status", "ERROR") if last_r else "ERROR"
                valid  = (verify_solution_general(grid, last_r.get("solution"), n_)
                          if status == "SAT" else False)

                record = {
                    "puzzle":        puzzle_name,
                    "n":             n_,
                    "clues":         clues,
                    "fill_pct":      round(fill_pct, 4),
                    "method":        "ILP",
                    "solver":        "ILP-CPSAT",
                    "amo_encoding":  "N/A",
                    "sat_backend":   "OR-Tools",
                    "status":        status,
                    "valid":         valid,
                    "time_median_s": round(median(times) or 0, 6),
                    "time_mean_s":   round(mean(times), 6),
                    "time_encode_s": round(last_r.get("time_model", 0), 6) if last_r else 0,
                    "time_solve_s":  round(last_r.get("time_solve", 0), 6) if last_r else 0,
                    "num_base_vars": last_r.get("num_vars", 0) if last_r else 0,
                    "num_aux_vars":  0,
                    "num_clauses":   last_r.get("num_constraints", 0) if last_r else 0,
                    "num_runs":      len(times),
                }
                results.append(record)

                if verbose:
                    t_str = f"{record['time_median_s']*1000:.2f}ms" if times else "N/A"
                    print(f"    ILP-CPSAT       : {status} valid={valid} t={t_str}")

    return results


def save_results(results: list[dict], prefix: str = "large_results") -> None:
    if not results:
        return
    fields = list(results[0].keys())
    with open(f"{prefix}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(results)
    with open(f"{prefix}.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n[✓] Saved {prefix}.csv and {prefix}.json")


def print_summary_table(results: list[dict]) -> None:
    print("\n" + "="*110)
    print(" BẢNG TỔNG KẾT – AMO Encoding × Kích thước")
    print("="*110)

    # Group by (n, amo_encoding, method)
    from collections import defaultdict
    data = defaultdict(list)
    for r in results:
        if r["status"] == "SAT":
            key = (r["n"], r.get("amo_encoding", "N/A"), r["method"])
            data[key].append(r["time_median_s"])

    print(f"{'n':>4} {'AMO Encoding':<16} {'Method':<14} {'Mean(ms)':>10} {'n_results':>10}")
    print("-"*60)
    for (n, amo, method), times in sorted(data.items()):
        avg = mean(times) * 1000
        print(f"{n:>4} {amo:<16} {method:<14} {avg:>10.3f} {len(times):>10}")


if __name__ == "__main__":
    print("="*80)
    print(" LARGE SUDOKU BENCHMARK – AMO Encoding Comparison")
    print("="*80)

    t0 = time.perf_counter()
    results = run_sat_encoding_experiment(verbose=True)
    t1 = time.perf_counter()

    print_summary_table(results)
    print(f"\n[⏱] Total time: {t1-t0:.1f}s")
    save_results(results, "large_results")
