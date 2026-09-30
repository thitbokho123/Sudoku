"""
cp_solver.py – Giải Sudoku n×n bằng Constraint Programming (CP).

Hỗ trợ kích thước: 9×9, 16×16, 25×25 (n phải là số chính phương).
Sử dụng OR-Tools CP-SAT solver (Google OR-Tools).

Mô hình CP:
  - Biến: x[r][c] ∈ {1..n} cho mỗi ô (r,c).
  - Ràng buộc AllDifferent cho từng hàng, cột, và box k×k (k=√n).
  - Clues: x[r][c] == given_value (fixed).

CP-SAT là hybrid CP/SAT solver của Google, sử dụng propagation + clause learning.
"""

from __future__ import annotations
import time
import math
from typing import Optional

from ortools.sat.python import cp_model


def solve_cp_sat(
    grid: list[list[int]],
    n: int = 9,
    timeout: float = 60.0,
) -> dict:
    """
    Giải Sudoku n×n bằng CP-SAT (OR-Tools).

    Parameters
    ----------
    grid    : puzzle n×n (0 = ô trống)
    n       : kích thước (9, 16, 25). Tự detect từ grid nếu để mặc định 9.
    timeout : thời gian tối đa (giây)

    Returns
    -------
    dict với các keys:
        status      : "SAT" | "UNSAT" | "TIMEOUT" | "ERROR"
        solution    : grid n×n nếu SAT, else None
        time_model  : thời gian xây dựng model (giây)
        time_solve  : thời gian solve (giây)
        time_total  : tổng (giây)
        solver_name : "cp-sat"
        n           : kích thước
    """
    # Auto-detect n from grid size
    if grid:
        n = len(grid)
    k = int(math.isqrt(n))

    t0 = time.perf_counter()
    model = cp_model.CpModel()

    # ── Khai báo biến ─────────────────────────────────────────────────────────
    x = [
        [model.new_int_var(1, n, f"x_{r}_{c}") for c in range(n)]
        for r in range(n)
    ]

    # ── Clues ─────────────────────────────────────────────────────────────────
    for r in range(n):
        for c in range(n):
            if grid[r][c] != 0:
                model.add(x[r][c] == grid[r][c])

    # ── Row constraints ───────────────────────────────────────────────────────
    for r in range(n):
        model.add_all_different(x[r])

    # ── Column constraints ────────────────────────────────────────────────────
    for c in range(n):
        model.add_all_different([x[r][c] for r in range(n)])

    # ── Box constraints (k×k boxes) ───────────────────────────────────────────
    for br in range(k):
        for bc in range(k):
            box_cells = [
                x[br * k + dr][bc * k + dc]
                for dr in range(k) for dc in range(k)
            ]
            model.add_all_different(box_cells)

    t_model = time.perf_counter() - t0

    # ── Giải ──────────────────────────────────────────────────────────────────
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = timeout
    solver.parameters.log_search_progress = False

    t1 = time.perf_counter()
    status_code = solver.solve(model)
    t_solve = time.perf_counter() - t1
    t_total = time.perf_counter() - t0

    status_map = {
        cp_model.FEASIBLE:   "SAT",
        cp_model.OPTIMAL:    "SAT",
        cp_model.INFEASIBLE: "UNSAT",
        cp_model.UNKNOWN:    "TIMEOUT",
    }
    status = status_map.get(status_code, "ERROR")

    solution = None
    if status == "SAT":
        solution = [
            [solver.value(x[r][c]) for c in range(n)]
            for r in range(n)
        ]

    return {
        "status":     status,
        "solution":   solution,
        "time_model": round(t_model, 6),
        "time_solve": round(t_solve, 6),
        "time_total": round(t_total, 6),
        "solver_name": "cp-sat",
        "n":           n,
    }
