"""
main.py – Entry point chính cho hệ thống Sudoku Solver.

Cung cấp:
  1. Demo giải một puzzle bằng tất cả các phương pháp.
  2. Chạy benchmark đầy đủ.

Sử dụng:
  python main.py                     # Demo + Benchmark đầy đủ
  python main.py --demo-only         # Chỉ demo
  python main.py --benchmark-only    # Chỉ benchmark
  python main.py --puzzle expert2    # Demo với puzzle cụ thể
  python main.py --quick             # Benchmark nhanh (1 run)
"""

from __future__ import annotations
import argparse
import time

from puzzles import PUZZLES, ALL_PUZZLES, count_clues
from sat_solver import solve_sat, verify_solution, MAIN_SAT_SOLVERS, SOLVER_MAP
from cp_solver import solve_cp_sat
from ilp_solver import solve_ilp


# ── Hiển thị grid Sudoku ───────────────────────────────────────────────────────

def print_grid(grid: list[list[int]], title: str = "") -> None:
    """In grid Sudoku theo dạng đẹp với đường phân cách."""
    if title:
        print(f"\n  {title}")

    print("  ┌───────┬───────┬───────┐")
    for r in range(9):
        if r in (3, 6):
            print("  ├───────┼───────┼───────┤")
        row = ""
        for c in range(9):
            if c in (0, 3, 6):
                row += "  │ "
            v = grid[r][c]
            row += ("." if v == 0 else str(v)) + " "
        row += " │"
        print(row)
    print("  └───────┴───────┴───────┘")


# ── Demo một puzzle ────────────────────────────────────────────────────────────

def demo_puzzle(
    puzzle_name: str,
    grid: list[list[int]],
    show_solution: bool = True,
) -> None:
    """Giải một puzzle bằng tất cả phương pháp và so sánh kết quả."""
    print("\n" + "=" * 80)
    print(f"  DEMO: {puzzle_name}  (clues: {count_clues(grid)})")
    print("=" * 80)
    print_grid(grid, "Puzzle đầu vào:")

    results = []

    # ── SAT Solvers ──────────────────────────────────────────────────────────
    print("\n  [SAT Solvers]")
    for solver_name in ["cadical195", "glucose4", "kissat", "cryptominisat",
                        "lingeling", "minisat22"]:
        r = solve_sat(grid, solver_name)
        valid = verify_solution(grid, r.get("solution")) if r["status"] == "SAT" else False
        results.append(r)
        status_icon = "✓" if valid else ("✗" if r["status"] == "SAT" else "–")
        print(
            f"    {solver_name:<20} │ {r['status']:<6} │ {status_icon} │ "
            f"encode={r.get('time_encode', 0)*1000:7.3f}ms  "
            f"solve={r.get('time_solve', 0)*1000:7.3f}ms  "
            f"total={r.get('time_total', 0)*1000:7.3f}ms"
        )

    # ── CP Solver ────────────────────────────────────────────────────────────
    print("\n  [CP Solver]")
    r_cp = solve_cp_sat(grid)
    valid = verify_solution(grid, r_cp.get("solution")) if r_cp["status"] == "SAT" else False
    status_icon = "✓" if valid else ("✗" if r_cp["status"] == "SAT" else "–")
    print(
        f"    {'OR-Tools CP-SAT':<20} │ {r_cp['status']:<6} │ {status_icon} │ "
        f"model={r_cp.get('time_model', 0)*1000:7.3f}ms  "
        f"solve={r_cp.get('time_solve', 0)*1000:7.3f}ms  "
        f"total={r_cp.get('time_total', 0)*1000:7.3f}ms"
    )

    # ── ILP Solver ───────────────────────────────────────────────────────────
    print("\n  [ILP/MIP Solver]")
    r_ilp = solve_ilp(grid, "highs")
    valid = verify_solution(grid, r_ilp.get("solution")) if r_ilp["status"] == "SAT" else False
    status_icon = "✓" if valid else ("✗" if r_ilp["status"] == "SAT" else "–")
    actual_name = r_ilp.get("solver_name", "HiGHS")
    print(
        f"    {actual_name:<20} │ {r_ilp['status']:<6} │ {status_icon} │ "
        f"model={r_ilp.get('time_model', 0)*1000:7.3f}ms  "
        f"solve={r_ilp.get('time_solve', 0)*1000:7.3f}ms  "
        f"total={r_ilp.get('time_total', 0)*1000:7.3f}ms"
    )

    # ── Hiển thị solution ────────────────────────────────────────────────────
    if show_solution and results and results[0].get("solution"):
        print_grid(results[0]["solution"], "Solution (Cadical195):")


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Sudoku SAT/CP/ILP Solver")
    p.add_argument("--demo-only",      action="store_true", help="Chỉ chạy demo")
    p.add_argument("--benchmark-only", action="store_true", help="Chỉ chạy benchmark")
    p.add_argument("--puzzle",         type=str, default=None,
                   help="Tên puzzle cho demo (easy1/medium2/hard3/expert1/...)")
    p.add_argument("--quick",          action="store_true",
                   help="Benchmark nhanh (1 run, debug)")
    p.add_argument("--runs",           type=int, default=3,
                   help="Số lần chạy mỗi task (default: 3)")
    p.add_argument("--timeout",        type=float, default=30.0,
                   help="Timeout (giây, default: 30)")
    p.add_argument("--output",         type=str, default="results",
                   help="Tiền tố file output")
    return p.parse_args()


def select_puzzle(puzzle_arg: str | None) -> tuple[str, list[list[int]]]:
    """Chọn puzzle demo từ tham số dòng lệnh."""
    if puzzle_arg is None:
        # Mặc định: dùng Expert-1 (AI Escargot)
        return PUZZLES["expert"][0]

    puzzle_arg = puzzle_arg.lower()
    level_map = {
        "easy":   PUZZLES["easy"],
        "medium": PUZZLES["medium"],
        "hard":   PUZZLES["hard"],
        "expert": PUZZLES["expert"],
    }

    for level, puzzles in level_map.items():
        for idx, (name, grid) in enumerate(puzzles, start=1):
            if puzzle_arg in (level, f"{level}{idx}", name.lower().replace("-", "")):
                return name, grid

    print(f"[!] Không tìm thấy puzzle '{puzzle_arg}'. Dùng Expert-1.")
    return PUZZLES["expert"][0]


def main():
    args = parse_args()

    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║     SUDOKU SOLVER: SAT vs CP vs ILP – Thực nghiệm So sánh      ║")
    print("║     PySAT (Cadical/Glucose/Kissat/CryptoMiniSAT/Lingeling)      ║")
    print("║     CP: OR-Tools CP-SAT   │   ILP: HiGHS/CPLEX MIP/Gurobi     ║")
    print("╚══════════════════════════════════════════════════════════════════╝")

    run_demo      = not args.benchmark_only
    run_benchmark = not args.demo_only

    # ── DEMO ──────────────────────────────────────────────────────────────────
    if run_demo:
        puzzle_name, grid = select_puzzle(args.puzzle)
        demo_puzzle(puzzle_name, grid, show_solution=True)

        # Nếu chỉ demo và không phải expert, cũng demo 1 easy puzzle
        if args.demo_only and "Expert" not in puzzle_name:
            pass
        elif args.demo_only:
            # Demo thêm Easy
            demo_puzzle(*PUZZLES["easy"][0], show_solution=False)

    # ── BENCHMARK ─────────────────────────────────────────────────────────────
    if run_benchmark:
        from benchmark import run_benchmark as _bench, print_summary, print_difficulty_breakdown, save_csv, save_json

        print("\n\n" + "=" * 80)
        print("  BẮT ĐẦU BENCHMARK ĐẦY ĐỦ")
        print("=" * 80)

        runs    = 1 if args.quick else args.runs
        timeout = args.timeout

        t0 = time.perf_counter()
        results = _bench(runs=runs, timeout=timeout, verbose=True)
        t1 = time.perf_counter()

        print_summary(results)
        print_difficulty_breakdown(results)
        print(f"\n[⏱]  Tổng thời gian benchmark: {t1 - t0:.2f}s")

        save_csv(results,  args.output + ".csv")
        save_json(results, args.output + ".json")


if __name__ == "__main__":
    main()
