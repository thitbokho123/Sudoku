"""
large_puzzles.py – Sinh và quản lý Sudoku puzzles kích thước lớn.

Hỗ trợ: 9×9 (3²), 16×16 (4²), 25×25 (5²).

Phương pháp sinh:
  Dùng công thức Latin Square: cell(r,c) = (k*(r%k) + r//k + c) % n
  với k = sqrt(n). Công thức này đảm bảo mọi hàng, cột, box đều có đầy đủ
  giá trị {0..n-1}. Sau đó remove ngẫu nhiên ~60% cells để tạo puzzle.
"""

from __future__ import annotations
import random
import copy
from typing import Optional


# ── Construction ──────────────────────────────────────────────────────────────

def make_complete_grid(n: int, seed: int = 42) -> list[list[int]]:
    """
    Tạo grid Sudoku hoàn chỉnh hợp lệ kích thước n×n (n phải là số chính phương).
    
    Dùng công thức: cell(r,c) = (k*(r%k) + r//k + c) % n + 1
    với k = int(sqrt(n)).
    
    Parameters
    ----------
    n    : kích thước (9, 16, 25)
    seed : seed cho random shuffle
    
    Returns
    -------
    grid : list[list[int]] giá trị trong [1..n]
    """
    import math
    k = int(math.isqrt(n))
    assert k * k == n, f"n={n} phải là số chính phương"
    
    # Base grid theo công thức Latin Square
    grid = [
        [(k * (r % k) + r // k + c) % n + 1
         for c in range(n)]
        for r in range(n)
    ]
    
    # Shuffle để tạo nhiều biến thể (permute rows within bands, cols within stacks)
    rng = random.Random(seed)
    
    # Permute rows within each band of k rows
    for band in range(k):
        rows_in_band = list(range(band * k, (band + 1) * k))
        perm = rows_in_band[:]
        rng.shuffle(perm)
        new_rows = [grid[r][:] for r in perm]
        for i, r in enumerate(rows_in_band):
            grid[r] = new_rows[i]
    
    # Permute cols within each stack of k cols
    for stack in range(k):
        cols_in_stack = list(range(stack * k, (stack + 1) * k))
        perm = cols_in_stack[:]
        rng.shuffle(perm)
        new_cols = [[grid[r][c] for c in perm] for r in range(n)]
        for r in range(n):
            for i, c in enumerate(cols_in_stack):
                grid[r][c] = new_cols[r][i]
    
    return grid


def make_puzzle(grid: list[list[int]], n: int,
                keep_ratio: float = 0.40, seed: int = 42) -> list[list[int]]:
    """
    Tạo puzzle từ complete grid bằng cách xóa ~(1-keep_ratio)*n² cells.
    
    Parameters
    ----------
    grid       : complete valid grid
    n          : kích thước
    keep_ratio : tỉ lệ ô được giữ lại (0.35–0.45 thường dùng)
    seed       : random seed
    
    Returns
    -------
    puzzle : grid với 0 = ô trống
    """
    rng = random.Random(seed)
    puzzle = copy.deepcopy(grid)
    
    # Danh sách tất cả vị trí
    positions = [(r, c) for r in range(n) for c in range(n)]
    rng.shuffle(positions)
    
    n_to_remove = int(n * n * (1 - keep_ratio))
    for r, c in positions[:n_to_remove]:
        puzzle[r][c] = 0
    
    return puzzle


def count_clues(grid: list[list[int]]) -> int:
    """Đếm số ô đã cho (clue)."""
    return sum(1 for row in grid for v in row if v != 0)


def fill_ratio(grid: list[list[int]], n: int) -> float:
    """Tính tỉ lệ ô đã biết."""
    return count_clues(grid) / (n * n)


def verify_complete_grid(grid: list[list[int]], n: int) -> bool:
    """Kiểm tra grid hoàn chỉnh có hợp lệ không."""
    import math
    k = int(math.isqrt(n))
    expected = set(range(1, n + 1))
    
    for i in range(n):
        # Row
        if set(grid[i]) != expected:
            return False
        # Col
        if set(grid[r][i] for r in range(n)) != expected:
            return False
    
    # Boxes
    for br in range(k):
        for bc in range(k):
            box = {grid[br*k+dr][bc*k+dc] for dr in range(k) for dc in range(k)}
            if box != expected:
                return False
    
    return True


# ── 9×9 Puzzles ───────────────────────────────────────────────────────────────

_GRID_9_BASE = [
    [5, 3, 4, 6, 7, 8, 9, 1, 2],
    [6, 7, 2, 1, 9, 5, 3, 4, 8],
    [1, 9, 8, 3, 4, 2, 5, 6, 7],
    [8, 5, 9, 7, 6, 1, 4, 2, 3],
    [4, 2, 6, 8, 5, 3, 7, 9, 1],
    [7, 1, 3, 9, 2, 4, 8, 5, 6],
    [9, 6, 1, 5, 3, 7, 2, 8, 4],
    [2, 8, 7, 4, 1, 9, 6, 3, 5],
    [3, 4, 5, 2, 8, 6, 1, 7, 9],
]

def _make_9x9_puzzles():
    """Tạo 3 puzzle 9×9 với mức độ khác nhau."""
    puzzles = []
    for seed, keep, label in [(42, 0.38, "9x9-Easy"), (7, 0.32, "9x9-Medium"), (99, 0.28, "9x9-Hard")]:
        g = make_complete_grid(9, seed=seed)
        p = make_puzzle(g, 9, keep_ratio=keep, seed=seed)
        puzzles.append((label, p, 9, 3))
    return puzzles


# ── 16×16 Puzzles ─────────────────────────────────────────────────────────────

def _make_16x16_puzzles():
    """Tạo 3 puzzle 16×16 (hexadoku) với mức độ khác nhau."""
    puzzles = []
    configs = [
        (42, 0.38, "16x16-Easy"),
        (17, 0.32, "16x16-Medium"),
        (88, 0.27, "16x16-Hard"),
    ]
    for seed, keep, label in configs:
        g = make_complete_grid(16, seed=seed)
        assert verify_complete_grid(g, 16), f"Invalid 16x16 grid (seed={seed})"
        p = make_puzzle(g, 16, keep_ratio=keep, seed=seed)
        puzzles.append((label, p, 16, 4))
    return puzzles


# ── 25×25 Puzzles ─────────────────────────────────────────────────────────────

def _make_25x25_puzzles():
    """Tạo 2 puzzle 25×25 với mức độ khác nhau."""
    puzzles = []
    configs = [
        (42, 0.38, "25x25-Easy"),
        (13, 0.30, "25x25-Hard"),
    ]
    for seed, keep, label in configs:
        g = make_complete_grid(25, seed=seed)
        assert verify_complete_grid(g, 25), f"Invalid 25x25 grid (seed={seed})"
        p = make_puzzle(g, 25, keep_ratio=keep, seed=seed)
        puzzles.append((label, p, 25, 5))
    return puzzles


# ── Registry ─────────────────────────────────────────────────────────────────

def build_all_puzzles() -> dict:
    """Xây dựng toàn bộ puzzle registry."""
    return {
        9:  _make_9x9_puzzles(),
        16: _make_16x16_puzzles(),
        25: _make_25x25_puzzles(),
    }


# Lazy load
_ALL_LARGE_PUZZLES = None

def get_all_large_puzzles() -> dict:
    global _ALL_LARGE_PUZZLES
    if _ALL_LARGE_PUZZLES is None:
        _ALL_LARGE_PUZZLES = build_all_puzzles()
    return _ALL_LARGE_PUZZLES


ALL_LARGE_PUZZLES = get_all_large_puzzles()


def get_puzzles_by_size(n: int) -> list:
    """Trả về danh sách (name, grid, n, k) cho kích thước n."""
    return ALL_LARGE_PUZZLES.get(n, [])


def print_puzzle_info() -> None:
    """In thông tin tóm tắt về tất cả puzzles."""
    for n, puzzles in sorted(ALL_LARGE_PUZZLES.items()):
        print(f"\n  {n}×{n} Sudoku ({len(puzzles)} puzzles):")
        for name, grid, n_, k in puzzles:
            clues = count_clues(grid)
            ratio = fill_ratio(grid, n_)
            print(f"    {name}: {clues}/{n_*n_} clues ({ratio:.1%} filled)")


if __name__ == "__main__":
    print("=== Large Sudoku Puzzle Info ===")
    print_puzzle_info()
    
    # Verify grids
    print("\n=== Verification ===")
    for n, puzzles in sorted(ALL_LARGE_PUZZLES.items()):
        for name, puzzle, n_, k in puzzles:
            # Tạo lại complete grid để verify
            import math
            seed = 42 if "Easy" in name else (17 if "Medium" in name else 
                   (13 if n==25 else 88))
            g = make_complete_grid(n_, seed=seed)
            ok = verify_complete_grid(g, n_)
            print(f"  {name}: complete grid valid={ok}")
