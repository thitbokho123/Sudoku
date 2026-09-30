"""
sat_solver.py – Giải Sudoku bằng SAT Solving với PySAT.

Encoding:
  Biến Boolean x_{r,c,v} = True nếu ô (r,c) chứa giá trị v.
  
  Biến được đánh số theo công thức: var(r, c, v) = 81*(r-1) + 9*(c-1) + v
  với r, c, v ∈ {1..9}.

Các ràng buộc Sudoku (CNF clauses):
  1. Cell constraint   – mỗi ô chứa ÍT NHẤT một giá trị.
  2. Cell uniqueness   – mỗi ô chứa NHIỀU NHẤT một giá trị.
  3. Row constraint    – mỗi hàng chứa mỗi giá trị đúng một lần.
  4. Column constraint – mỗi cột chứa mỗi giá trị đúng một lần.
  5. Box constraint    – mỗi box 3×3 chứa mỗi giá trị đúng một lần.
  6. Given (clue)      – các ô đã biết được gán cứng.

Hỗ trợ các SAT solvers qua PySAT:
  Cadical103, Cadical153, Cadical195, Cadical300,
  CryptoMiniSAT, Glucose3, Glucose4, Glucose42,
  Kissat404, Lingeling, Minisat22, Mergesat3
"""

from __future__ import annotations
import time
from typing import Optional

from pysat.formula import CNF
from pysat.solvers import (
    Cadical103, Cadical153, Cadical195, Cadical300,
    CryptoMinisat, Glucose3, Glucose4, Glucose42,
    Kissat404, Lingeling, Minisat22, Mergesat3,
)

# ── Ánh xạ tên → class solver ──────────────────────────────────────────────
SOLVER_MAP = {
    "cadical103":    Cadical103,
    "cadical153":    Cadical153,
    "cadical195":    Cadical195,
    "cadical300":    Cadical300,
    "cryptominisat": CryptoMinisat,
    "glucose3":      Glucose3,
    "glucose4":      Glucose4,
    "glucose42":     Glucose42,
    "kissat":        Kissat404,
    "lingeling":     Lingeling,
    "minisat22":     Minisat22,
    "mergesat3":     Mergesat3,
}

# Danh sách solvers chính cho thực nghiệm
MAIN_SAT_SOLVERS = [
    "cadical195",
    "glucose4",
    "kissat",
    "cryptominisat",
    "lingeling",
    "minisat22",
]


# ── Hàm encoding ─────────────────────────────────────────────────────────────

def var(r: int, c: int, v: int) -> int:
    """Chuyển (row, col, val) → biến SAT nguyên dương.
    
    r, c, v ∈ {1..9}.
    Trả về một số nguyên dương duy nhất trong [1..729].
    """
    return 81 * (r - 1) + 9 * (c - 1) + v


def build_sudoku_cnf(grid: list[list[int]]) -> CNF:
    """
    Tạo công thức CNF mã hoá bài toán Sudoku từ grid đầu vào.

    Parameters
    ----------
    grid : list[list[int]]
        Ma trận 9×9, giá trị 0 = ô trống, 1–9 = giá trị đã biết.

    Returns
    -------
    CNF
        Công thức CNF chứa tất cả clauses.
    """
    cnf = CNF()

    # ── 1. Cell constraint: mỗi ô có ÍT NHẤT một giá trị ──────────────────
    for r in range(1, 10):
        for c in range(1, 10):
            cnf.append([var(r, c, v) for v in range(1, 10)])

    # ── 2. Cell uniqueness: mỗi ô có NHIỀU NHẤT một giá trị ───────────────
    for r in range(1, 10):
        for c in range(1, 10):
            for v in range(1, 9):
                for u in range(v + 1, 10):
                    cnf.append([-var(r, c, v), -var(r, c, u)])

    # ── 3. Row constraint: mỗi giá trị xuất hiện đúng một lần mỗi hàng ────
    for r in range(1, 10):
        for v in range(1, 10):
            # At-least-one
            cnf.append([var(r, c, v) for c in range(1, 10)])
            # At-most-one (pairwise)
            for c in range(1, 9):
                for d in range(c + 1, 10):
                    cnf.append([-var(r, c, v), -var(r, d, v)])

    # ── 4. Column constraint ────────────────────────────────────────────────
    for c in range(1, 10):
        for v in range(1, 10):
            cnf.append([var(r, c, v) for r in range(1, 10)])
            for r in range(1, 9):
                for s in range(r + 1, 10):
                    cnf.append([-var(r, c, v), -var(s, c, v)])

    # ── 5. Box constraint (3×3) ─────────────────────────────────────────────
    for br in range(3):
        for bc in range(3):
            cells = [
                (br * 3 + dr + 1, bc * 3 + dc + 1)
                for dr in range(3) for dc in range(3)
            ]
            for v in range(1, 10):
                cnf.append([var(r, c, v) for (r, c) in cells])
                for i in range(len(cells) - 1):
                    for j in range(i + 1, len(cells)):
                        r1, c1 = cells[i]
                        r2, c2 = cells[j]
                        cnf.append([-var(r1, c1, v), -var(r2, c2, v)])

    # ── 6. Given clues ──────────────────────────────────────────────────────
    for r in range(9):
        for c in range(9):
            v = grid[r][c]
            if v != 0:
                cnf.append([var(r + 1, c + 1, v)])

    return cnf


def decode_solution(model: list[int]) -> list[list[int]]:
    """Chuyển model SAT (danh sách literals) → grid 9×9."""
    solution = [[0] * 9 for _ in range(9)]
    for lit in model:
        if lit > 0:
            lit -= 1  # 0-indexed
            v = lit % 9 + 1
            lit //= 9
            c = lit % 9
            r = lit // 9
            solution[r][c] = v
    return solution


def solve_sat(
    grid: list[list[int]],
    solver_name: str = "cadical195",
    timeout: float = 60.0,
) -> dict:
    """
    Giải một puzzle Sudoku bằng SAT solver.

    Parameters
    ----------
    grid        : puzzle 9×9
    solver_name : tên solver (key trong SOLVER_MAP)
    timeout     : thời gian tối đa (giây) – hiện không áp dụng hard-timeout
                  trong PySAT; dùng để ghi nhận.

    Returns
    -------
    dict với các keys:
        status      : "SAT" | "UNSAT" | "TIMEOUT" | "ERROR"
        solution    : grid 9×9 nếu SAT, else None
        time_encode : thời gian encoding CNF (giây)
        time_solve  : thời gian gọi solver (giây)
        time_total  : tổng (giây)
        num_vars    : số biến CNF
        num_clauses : số clauses CNF
        solver_name : tên solver đã dùng
    """
    solver_cls = SOLVER_MAP.get(solver_name.lower())
    if solver_cls is None:
        return {"status": "ERROR", "message": f"Unknown solver: {solver_name}"}

    # ── Encoding ────────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    cnf = build_sudoku_cnf(grid)
    t_encode = time.perf_counter() - t0

    num_vars    = cnf.nv
    num_clauses = len(cnf.clauses)

    # ── Solving ─────────────────────────────────────────────────────────────
    t1 = time.perf_counter()
    try:
        with solver_cls(bootstrap_with=cnf.clauses) as solver:
            sat = solver.solve()
            model = solver.get_model() if sat else None
        t_solve = time.perf_counter() - t1
    except Exception as e:
        return {
            "status": "ERROR",
            "message": str(e),
            "time_encode": t_encode,
            "solver_name": solver_name,
        }

    t_total = time.perf_counter() - t0
    solution = decode_solution(model) if model else None

    return {
        "status":       "SAT" if sat else "UNSAT",
        "solution":     solution,
        "time_encode":  round(t_encode, 6),
        "time_solve":   round(t_solve, 6),
        "time_total":   round(t_total, 6),
        "num_vars":     num_vars,
        "num_clauses":  num_clauses,
        "solver_name":  solver_name,
    }


def verify_solution(grid: list[list[int]], solution: list[list[int]]) -> bool:
    """Kiểm tra solution có hợp lệ và nhất quán với clues không."""
    if solution is None:
        return False

    # Kiểm tra clues
    for r in range(9):
        for c in range(9):
            if grid[r][c] != 0 and solution[r][c] != grid[r][c]:
                return False

    # Kiểm tra hàng, cột, box
    for i in range(9):
        row = [solution[i][c] for c in range(9)]
        col = [solution[r][i] for r in range(9)]
        br, bc = (i // 3) * 3, (i % 3) * 3
        box = [solution[br + dr][bc + dc] for dr in range(3) for dc in range(3)]

        if set(row) != set(range(1, 10)):
            return False
        if set(col) != set(range(1, 10)):
            return False
        if set(box) != set(range(1, 10)):
            return False

    return True
