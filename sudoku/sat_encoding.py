"""
sat_encoding.py – Mã hoá Sudoku n×n thành CNF với nhiều chiến lược AMO.

Hỗ trợ bất kỳ kích thước n×n với n = k² (9, 16, 25, ...).
Tích hợp các AMO encoding: Pairwise, Binary, Commander, Product, Sequential Counter.

Encoding scheme:
  Biến: x(r, c, v) = True ⟺ ô (r,c) chứa giá trị v.
  Biến số: n²(r) + n(c) + (v-1) + 1  (1-indexed, r,c,v ∈ {0..n-1})

Ràng buộc:
  ∀(r,c)  : EO{v∈[1..n]} x(r,c,v)   [cell   – exactly one value per cell]
  ∀(r,v)  : EO{c∈[0..n)} x(r,c,v)   [row    – each value once per row]
  ∀(c,v)  : EO{r∈[0..n)} x(r,c,v)   [col    – each value once per column]
  ∀(box,v): EO{(r,c)∈box} x(r,c,v)  [box    – each value once per box]
  ∀clue   : x(r,c,given)             [clue   – given values]
"""

from __future__ import annotations
import time
import math
from typing import Optional

from pysat.formula import CNF, IDPool
from pysat.solvers import (
    Cadical195, Cadical300, Glucose4, Glucose42,
    Kissat404, CryptoMinisat, Minisat22,
)

from amo_encodings import (
    alo, get_amo_fn, get_eo_fn,
    AMO_ENCODINGS, EO_DISPLAY_NAMES,
)

# ── SAT Solver map ──────────────────────────────────────────────────────────
SAT_SOLVER_MAP = {
    "cadical195":    Cadical195,
    "cadical300":    Cadical300,
    "glucose4":      Glucose4,
    "glucose42":     Glucose42,
    "kissat":        Kissat404,
    "cryptominisat": CryptoMinisat,
    "minisat22":     Minisat22,
}


# ── Variable mapping ────────────────────────────────────────────────────────

def var(r: int, c: int, v: int, n: int) -> int:
    """
    Ánh xạ (row, col, val) → biến SAT.
    r, c ∈ {0..n-1}, v ∈ {1..n}
    → số nguyên trong [1..n³]
    """
    return n * n * r + n * c + (v - 1) + 1


def decode_model(model: list[int], n: int) -> list[list[int]]:
    """Chuyển SAT model → grid n×n."""
    grid = [[0] * n for _ in range(n)]
    for lit in model:
        if lit > 0:
            idx = lit - 1  # 0-indexed
            v   = idx % n + 1
            idx //= n
            c   = idx % n
            r   = idx // n
            if 0 <= r < n and 0 <= c < n and 1 <= v <= n:
                grid[r][c] = v
    return grid


# ── CNF Builder ─────────────────────────────────────────────────────────────

def build_sudoku_cnf_general(
    grid: list[list[int]],
    n: int,
    amo_name: str = "pairwise",
) -> tuple[CNF, IDPool]:
    """
    Xây dựng CNF cho Sudoku n×n với chiến lược AMO chọn sẵn.

    Parameters
    ----------
    grid     : puzzle n×n (0 = ô trống)
    n        : kích thước (9, 16, 25)
    amo_name : tên AMO encoding (pairwise/binary/commander/product/sequential)

    Returns
    -------
    (cnf, pool) : CNF formula và IDPool đã dùng
    """
    k = int(math.isqrt(n))
    assert k * k == n, f"n={n} phải là số chính phương"

    # Biến gốc: [1 .. n³], aux vars bắt đầu từ n³+1
    base_top = n * n * n
    pool = IDPool(start_from=base_top + 1)
    amo_fn = get_amo_fn(amo_name)
    cnf = CNF()

    def add_eo(lits):
        """Thêm Exactly-One constraint: ALO + AMO."""
        # ALO
        cnf.extend(alo(lits))
        # AMO
        if amo_name == "pairwise":
            cnf.extend(amo_fn(lits))
        else:
            cnf.extend(amo_fn(lits, pool))

    # ── 1. Cell constraints: EO của các giá trị trong mỗi ô ───────────────
    for r in range(n):
        for c in range(n):
            add_eo([var(r, c, v, n) for v in range(1, n + 1)])

    # ── 2. Row constraints: EO của mỗi giá trị theo từng hàng ─────────────
    for r in range(n):
        for v in range(1, n + 1):
            add_eo([var(r, c, v, n) for c in range(n)])

    # ── 3. Column constraints: EO theo từng cột ────────────────────────────
    for c in range(n):
        for v in range(1, n + 1):
            add_eo([var(r, c, v, n) for r in range(n)])

    # ── 4. Box constraints: EO theo từng box k×k ───────────────────────────
    for br in range(k):
        for bc in range(k):
            cells = [
                (br * k + dr, bc * k + dc)
                for dr in range(k) for dc in range(k)
            ]
            for v in range(1, n + 1):
                add_eo([var(r, c, v, n) for (r, c) in cells])

    # ── 5. Clues (given values) ────────────────────────────────────────────
    for r in range(n):
        for c in range(n):
            v = grid[r][c]
            if v != 0:
                cnf.append([var(r, c, v, n)])

    return cnf, pool


# ── Solver ──────────────────────────────────────────────────────────────────

def solve_sudoku_sat(
    grid: list[list[int]],
    n: int = 9,
    amo_name: str = "pairwise",
    sat_solver: str = "cadical195",
    timeout: float = 120.0,
) -> dict:
    """
    Giải Sudoku n×n bằng SAT với chiến lược AMO được chọn.

    Returns
    -------
    dict với các keys:
        status       : "SAT" | "UNSAT" | "ERROR"
        solution     : grid n×n nếu SAT
        time_encode  : thời gian encoding (giây)
        time_solve   : thời gian solving (giây)
        time_total   : tổng
        num_vars     : số biến SAT (gốc)
        num_aux_vars : số biến auxiliary do AMO encoding thêm vào
        num_clauses  : số clauses
        amo_name     : tên AMO encoding
        sat_solver   : tên SAT solver
        n            : kích thước
    """
    solver_cls = SAT_SOLVER_MAP.get(sat_solver.lower())
    if solver_cls is None:
        return {"status": "ERROR", "message": f"Unknown solver: {sat_solver}"}

    # ── Encoding ─────────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    try:
        cnf, pool = build_sudoku_cnf_general(grid, n, amo_name)
    except Exception as e:
        return {"status": "ERROR", "message": f"Encoding error: {e}"}
    t_encode = time.perf_counter() - t0

    base_vars = n * n * n
    num_aux   = cnf.nv - base_vars
    num_clauses = len(cnf.clauses)

    # ── Solving ──────────────────────────────────────────────────────────────
    t1 = time.perf_counter()
    try:
        with solver_cls(bootstrap_with=cnf.clauses) as solver:
            sat    = solver.solve()
            model  = solver.get_model() if sat else None
    except Exception as e:
        return {"status": "ERROR", "message": f"Solver error: {e}",
                "time_encode": round(t_encode, 6)}
    t_solve = time.perf_counter() - t1
    t_total = time.perf_counter() - t0

    solution = decode_model(model, n) if model else None

    return {
        "status":       "SAT" if sat else "UNSAT",
        "solution":     solution,
        "time_encode":  round(t_encode, 6),
        "time_solve":   round(t_solve, 6),
        "time_total":   round(t_total, 6),
        "num_vars":     base_vars,
        "num_aux_vars": max(num_aux, 0),
        "num_clauses":  num_clauses,
        "amo_name":     amo_name,
        "sat_solver":   sat_solver,
        "n":            n,
    }


def verify_solution_general(
    grid: list[list[int]], solution: list[list[int]], n: int
) -> bool:
    """Kiểm tra solution hợp lệ."""
    if solution is None:
        return False
    if len(solution) != n or any(len(row) != n for row in solution):
        return False
    k = int(math.isqrt(n))
    expected = set(range(1, n + 1))

    # Kiểm tra clues
    for r in range(n):
        for c in range(n):
            if grid[r][c] != 0 and solution[r][c] != grid[r][c]:
                return False

    # Kiểm tra rows, cols, boxes
    for i in range(n):
        if set(solution[i]) != expected:
            return False
        if set(solution[r][i] for r in range(n)) != expected:
            return False

    for br in range(k):
        for bc in range(k):
            box = {solution[br*k+dr][bc*k+dc] for dr in range(k) for dc in range(k)}
            if box != expected:
                return False

    return True
