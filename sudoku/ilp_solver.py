"""
ilp_solver.py – Giải Sudoku bằng Integer Linear Programming (ILP/MIP).

Sử dụng PuLP 4.x làm giao diện mô hình hoá.
Backend solver hỗ trợ:
  - CPLEX MIP   : dùng pulp.CPLEX_PY nếu có licence
  - Gurobi      : dùng pulp.GUROBI nếu có licence
  - CPSAT (PuLP): OR-Tools CP-SAT qua PuLP (mặc định, luôn có)
  - HiGHS       : nếu cài highspy
  - CBC         : nếu cài coin-bc

Mô hình ILP (Binary Integer Program):
  Biến quyết định:
    x[r,c,v] ∈ {0, 1}  (binary)
    = 1 nếu ô (r, c) chứa giá trị v.

  Ràng buộc:
    (1) Cell:   Σ_v x[r,c,v] = 1   ∀ r, c
    (2) Row:    Σ_c x[r,c,v] = 1   ∀ r, v
    (3) Col:    Σ_r x[r,c,v] = 1   ∀ c, v
    (4) Box:    Σ_{r,c ∈ box} x[r,c,v] = 1   ∀ box, v
    (5) Clue:   x[r,c,v] = 1   nếu grid[r][c] = v

  Hàm mục tiêu: minimize 0 (feasibility problem).

Ghi chú về CPLEX / Gurobi:
  Hai solver này cần licence thương mại riêng.
  Trong môi trường không có licence, code tự động fallback
  về CPSAT (OR-Tools) vì đây là solver miễn phí duy nhất
  trong PuLP 4.x có trong môi trường này.
"""

from __future__ import annotations
import time
from typing import Optional

import pulp
from pulp import LpSolveStatus


def _get_solver(solver_name: str, timeout: float):
    """
    Trả về (pulp_solver_object, tên_thực_tế) dựa trên solver_name.
    Nếu solver yêu cầu không có sẵn, fallback về CPSAT.
    """
    name = solver_name.lower()

    def try_solver(cls_name, display, **kwargs):
        try:
            solver_cls = getattr(pulp, cls_name, None)
            if solver_cls is None:
                return None
            s = solver_cls(msg=False, **kwargs)
            if s.available():
                return s, display
        except Exception:
            pass
        return None

    if name in ("cplex_mip", "cplex"):
        result = try_solver("CPLEX_PY", "CPLEX MIP", timeLimit=timeout)
        if result:
            return result
        result = try_solver("CPLEX_CMD", "CPLEX MIP (CMD)", timelimit=timeout)
        if result:
            return result
        print(f"    [!] CPLEX không khả dụng → fallback CPSAT (OR-Tools)")

    elif name == "gurobi":
        result = try_solver("GUROBI", "Gurobi", timeLimit=timeout)
        if result:
            return result
        result = try_solver("GUROBI_CMD", "Gurobi (CMD)", timeLimit=timeout)
        if result:
            return result
        print(f"    [!] Gurobi không khả dụng → fallback CPSAT (OR-Tools)")

    elif name in ("highs",):
        result = try_solver("HiGHS", "HiGHS", timeLimit=timeout)
        if result:
            return result
        result = try_solver("HiGHS_CMD", "HiGHS (CMD)", timeLimit=timeout)
        if result:
            return result

    elif name in ("cbc", "coin"):
        result = try_solver("COIN_CMD", "CBC/COIN", timeLimit=timeout)
        if result:
            return result
        result = try_solver("PULP_CBC_CMD", "CBC", timeLimit=timeout)
        if result:
            return result

    # Fallback: CPSAT (luôn có trong môi trường này)
    try:
        s = pulp.CPSAT(msg=False, time_limit=int(timeout))
        if s.available():
            return s, "CPSAT (OR-Tools via PuLP)"
    except Exception:
        pass

    return None, "NONE"


def build_ilp_model(
    grid: list[list[int]],
    prob: pulp.LpProblem,
) -> dict:
    """
    Xây dựng mô hình ILP Binary Integer Program cho Sudoku.
    Thêm trực tiếp vào prob (LpProblem đã tạo sẵn).

    Returns
    -------
    dict[tuple(r,c,v) -> LpVariable]
    """
    import math as _math
    n = len(grid)
    k = int(_math.isqrt(n))

    # ── Biến quyết định: x[r][c][v] ∈ {0,1} ────────────────────────────────
    x = {}
    for r in range(n):
        for c in range(n):
            for v in range(1, n + 1):
                x[r, c, v] = prob.add_variable(
                    f"x_{r}_{c}_{v}",
                    lowBound=0,
                    upBound=1,
                    cat="Binary",
                )

    # ── Objective: feasibility ────────────────────────────────────────────────
    # Minimize 0 → không cần gán explicit

    # ── (1) Cell constraints: Σ_v x[r,c,v] = 1 ──────────────────────────────
    for r in range(n):
        for c in range(n):
            prob += (
                pulp.lpSum(x[r, c, v] for v in range(1, n + 1)) == 1,
                f"cell_{r}_{c}",
            )


    # ── (2) Row constraints: Σ_c x[r,c,v] = 1 ──────────────────────────────
    for r in range(n):
        for v in range(1, n + 1):
            prob += (
                pulp.lpSum(x[r, c, v] for c in range(n)) == 1,
                f"row_{r}_{v}",
            )

    # ── (3) Column constraints: Σ_r x[r,c,v] = 1 ────────────────────────────
    for c in range(n):
        for v in range(1, n + 1):
            prob += (
                pulp.lpSum(x[r, c, v] for r in range(n)) == 1,
                f"col_{c}_{v}",
            )

    # ── (4) Box constraints ───────────────────────────────────────────────────
    for br in range(k):
        for bc in range(k):
            for v in range(1, n + 1):
                prob += (
                    pulp.lpSum(
                        x[br * k + dr, bc * k + dc, v]
                        for dr in range(k)
                        for dc in range(k)
                    )
                    == 1,
                    f"box_{br}_{bc}_{v}",
                )

    # ── (5) Clues ─────────────────────────────────────────────────────────────
    for r in range(n):
        for c in range(n):
            given = grid[r][c]
            if given != 0:
                prob += (x[r, c, given] == 1, f"clue_{r}_{c}")

    return x


def solve_ilp(
    grid: list[list[int]],
    solver_name: str = "cpsat",
    timeout: float = 60.0,
) -> dict:
    """
    Giải Sudoku bằng ILP/MIP.

    Parameters
    ----------
    grid        : puzzle 9×9
    solver_name : "cplex_mip" | "gurobi" | "highs" | "cbc" | "cpsat"
    timeout     : thời gian tối đa (giây)

    Returns
    -------
    dict với các keys:
        status          : "SAT" | "UNSAT" | "TIMEOUT" | "ERROR"
        solution        : grid 9×9 nếu SAT, else None
        time_model      : thời gian xây dựng model (giây)
        time_solve      : thời gian solve (giây)
        time_total      : tổng (giây)
        num_vars        : số biến ILP
        num_constraints : số ràng buộc
        solver_name     : tên solver thực sự được dùng
    """
    t0 = time.perf_counter()

    # ── Chọn solver ──────────────────────────────────────────────────────────
    solver_obj, actual_name = _get_solver(solver_name, timeout)
    if solver_obj is None:
        return {
            "status":      "ERROR",
            "message":     "No solver available",
            "solver_name": solver_name,
            "time_total":  0,
        }

    # ── Xây dựng model ────────────────────────────────────────────────────────
    prob = pulp.LpProblem("Sudoku_ILP", pulp.LpMinimize)
    x    = build_ilp_model(grid, prob)
    t_model = time.perf_counter() - t0

    num_vars        = prob._model.num_variables
    num_constraints = prob._model.num_constraints

    # ── Giải ─────────────────────────────────────────────────────────────────
    t1 = time.perf_counter()
    try:
        stats = prob.solve(solver_obj)
    except Exception as e:
        return {
            "status":     "ERROR",
            "message":    str(e),
            "time_model": round(t_model, 6),
            "solver_name": actual_name,
            "time_total": round(time.perf_counter() - t0, 6),
        }
    t_solve = time.perf_counter() - t1
    t_total = time.perf_counter() - t0

    # ── Đọc trạng thái ───────────────────────────────────────────────────────
    solve_status = stats.status  # LpSolveStatus enum

    if solve_status == LpSolveStatus.Optimal:
        status = "SAT"
    elif solve_status == LpSolveStatus.Infeasible:
        status = "UNSAT"
    elif solve_status in (LpSolveStatus.TimeLimit, LpSolveStatus.NodeLimit,
                          LpSolveStatus.Stopped, LpSolveStatus.Interrupted):
        status = "TIMEOUT"
    else:
        status = f"UNKNOWN({solve_status.name})"

    # ── Đọc solution ─────────────────────────────────────────────────────────
    solution = None
    if stats.has_solution:
        solution = [[0] * 9 for _ in range(9)]
        for r in range(9):
            for c in range(9):
                for v in range(1, 10):
                    val = pulp.value(x[r, c, v])
                    if val is not None and round(val) == 1:
                        solution[r][c] = v

        # Validate giải thực sự là SAT (có thể đọc được solution)
        if status not in ("SAT",):
            status = "SAT"  # has_solution → có solution tốt

    return {
        "status":          status,
        "solution":        solution,
        "time_model":      round(t_model, 6),
        "time_solve":      round(t_solve, 6),
        "time_total":      round(t_total, 6),
        "num_vars":        num_vars,
        "num_constraints": num_constraints,
        "solver_name":     actual_name,
    }
