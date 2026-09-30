"""
amo_encodings.py – AMO (At-Most-One) và ALO (At-Least-One) Encodings cho SAT.

Các phương pháp AMO:
  1. Pairwise (Naive) – O(n²) clauses, 0 aux vars        [Cook 1971]
  2. Binary (Bitwise)  – O(n·log₂n) clauses, ⌈log₂n⌉ aux vars
  3. Commander         – O(n) clauses, O(n/k) aux vars   [Klieber & Kwon 2007]
  4. Product           – O(n + p² + q²) clauses, p+q aux [Chen 2010]
  5. Sequential Counter (Ladder/Sinz) – O(n) clauses, n-1 aux vars [Sinz 2005]

Tham chiếu:
  - Sinz C. (2005). Towards an Optimal CNF Encoding of Boolean Cardinality Constraints.
    CP 2005, LNCS 3709, pp. 827–831.
  - Klieber W., Kwon G. (2007). Efficient CNF Encoding for Selecting 1 from N Objects.
    FMCAD 2007 Workshop.
  - Chen J. (2010). A New SAT Encoding of the At-Most-One Constraint.
    CP 2010.

Interface:
  lits  : list[int] – danh sách SAT literals (1-indexed, dương)
  pool  : IDPool    – pool tạo biến auxiliary (pysat.formula.IDPool)
  Trả về: list[list[int]] – CNF clauses
"""

from __future__ import annotations
import math
from typing import Callable
from itertools import count as _count

from pysat.formula import IDPool

# Global monotonic counter để tạo key unique cho mỗi constraint
# Tránh Python reuse memory address của list objects (id() collision)
_CONSTRAINT_COUNTER = _count(0)

def _next_cid() -> int:
    """Trả về ID constraint duy nhất, tăng dần."""
    return next(_CONSTRAINT_COUNTER)


# ── ALO: At-Least-One ────────────────────────────────────────────────────────

def alo(lits: list[int]) -> list[list[int]]:
    """At-Least-One: ít nhất một literal trong lits là True.
    
    Một clause duy nhất: (x₁ ∨ x₂ ∨ ... ∨ xₙ).
    Phức tạp: O(1) clause, 0 aux vars.
    """
    return [list(lits)]


# ── AMO encodings ─────────────────────────────────────────────────────────────

def amo_pairwise(lits: list[int], pool: IDPool = None) -> list[list[int]]:
    """
    AMO Pairwise (Naive) Encoding.
    
    Với mỗi cặp (i,j), i < j: thêm clause (¬xᵢ ∨ ¬xⱼ).
    
    Phức tạp:
      Clauses : n(n-1)/2
      Aux vars: 0
    Tốt cho n nhỏ (n ≤ 5).
    """
    clauses = []
    n = len(lits)
    for i in range(n - 1):
        for j in range(i + 1, n):
            clauses.append([-lits[i], -lits[j]])
    return clauses


def amo_binary(lits: list[int], pool: IDPool) -> list[list[int]]:
    """
    AMO Binary (Bitwise/Log) Encoding.
    
    Dùng k = ⌈log₂n⌉ biến auxiliary b₀..b_{k-1} để mã hoá chỉ số.
    Nếu xᵢ = True thì bits của i được enforce: ∀j: (¬xᵢ ∨ bⱼ) nếu bit j của i = 1,
                                                     (¬xᵢ ∨ ¬bⱼ) nếu bit j của i = 0.
    
    Phức tạp:
      Clauses : n·⌈log₂n⌉
      Aux vars: ⌈log₂n⌉
    """
    n = len(lits)
    if n <= 1:
        return []
    
    k = math.ceil(math.log2(n)) if n > 1 else 1
    # Tạo k auxiliary variables (bit variables)
    cid = _next_cid()
    bits = [pool.id(f"__bin_bit_{cid}_{j}") for j in range(k)]
    
    clauses = []
    for i, lit in enumerate(lits):
        # Encode index i in binary
        for j in range(k):
            if (i >> j) & 1:
                # bit j of i is 1 → ¬xᵢ ∨ bⱼ
                clauses.append([-lit, bits[j]])
            else:
                # bit j of i is 0 → ¬xᵢ ∨ ¬bⱼ
                clauses.append([-lit, -bits[j]])
    
    return clauses


def amo_commander(lits: list[int], pool: IDPool, k: int = 4) -> list[list[int]]:
    """
    AMO Commander Encoding [Klieber & Kwon 2007].
    
    Chia literals thành các nhóm kích thước ≤ k, tạo biến commander cho mỗi nhóm.
    Áp dụng đệ quy lên các commander variables.
    
    Với mỗi nhóm G = {x₁,...,xₘ}, biến commander c:
      - UP propagation : ∀i: (¬xᵢ ∨ c)         → nếu xᵢ true thì c true
      - AMO trong nhóm: ∀i<j: (¬xᵢ ∨ ¬xⱼ)     → pairwise trong nhóm
      - DOWN clause    : (¬c ∨ x₁ ∨ ... ∨ xₘ)  → nếu c true thì ít nhất một xi true
    
    Phức tạp:
      Clauses : O(n·k/2) ≈ O(n) (với k nhỏ)
      Aux vars: O(n/k) levels ≈ O(n/k)
    """
    if len(lits) <= 1:
        return []
    if len(lits) <= k:
        # Base: pairwise AMO trên nhóm nhỏ
        return amo_pairwise(lits)
    
    clauses = []
    commanders = []
    
    # Chia thành các nhóm kích thước k
    for i in range(0, len(lits), k):
        group = lits[i : i + k]
        
        if len(group) == 1:
            commanders.append(group[0])
            continue
        
        # Tạo commander variable cho nhóm này
        cmd = pool.id(f"__cmd_{_next_cid()}")
        commanders.append(cmd)
        
        # AMO trong nhóm (pairwise)
        for a in range(len(group) - 1):
            for b in range(a + 1, len(group)):
                clauses.append([-group[a], -group[b]])
        
        # UP: ∀xᵢ ∈ group: (¬xᵢ ∨ cmd)
        for x in group:
            clauses.append([-x, cmd])
        
        # DOWN: (¬cmd ∨ x₁ ∨ ... ∨ xₘ)
        clauses.append([-cmd] + list(group))
    
    # Áp dụng đệ quy AMO lên danh sách commanders
    clauses += amo_commander(commanders, pool, k)
    
    return clauses


def amo_product(lits: list[int], pool: IDPool) -> list[list[int]]:
    """
    AMO Product Encoding [Chen 2010].
    
    Sắp xếp n literals vào một lưới p × q (p·q ≥ n, p ≈ q ≈ √n).
    Tạo row vars R₀..R_{p-1} và col vars C₀..C_{q-1}.
    
    Với xᵢ tại vị trí (rᵢ, cᵢ):
      (¬xᵢ ∨ R_{rᵢ}) và (¬xᵢ ∨ C_{cᵢ})   → implications
    
    AMO trên rows và cols (pairwise, chỉ O(√n²) clauses):
      ∀j<k: (¬Rⱼ ∨ ¬Rₖ)   → AMO rows
      ∀j<k: (¬Cⱼ ∨ ¬Cₖ)   → AMO cols
    
    Lý do đúng: Nếu xᵢ và xⱼ đều true (i ≠ j):
      - Nếu rᵢ = rⱼ: Rᵣ = True bị enforced 2 lần, nhưng không vi phạm.
        Tuy nhiên, cᵢ ≠ cⱼ (vì i≠j và cùng row). Thực ra p×q > n nên
        cùng row và khác col → Cᵢ và Cⱼ cả hai true → AMO(C) vi phạm.
      - Nếu rᵢ ≠ rⱼ: Rᵢ và Rⱼ đều true → AMO(R) vi phạm.
    
    Phức tạp:
      Clauses : 2n (implications) + p(p-1)/2 + q(q-1)/2 ≈ 2n + n
      Aux vars: p + q ≈ 2√n
    """
    n = len(lits)
    if n <= 1:
        return []
    
    p = math.ceil(math.sqrt(n))
    q = math.ceil(n / p)
    
    cid = _next_cid()
    R = [pool.id(f"__prod_R_{cid}_{j}") for j in range(p)]
    C = [pool.id(f"__prod_C_{cid}_{j}") for j in range(q)]
    
    clauses = []
    
    # Implication clauses: xᵢ → R_{row(i)} và xᵢ → C_{col(i)}
    for idx, lit in enumerate(lits):
        r_idx = idx // q
        c_idx = idx % q
        clauses.append([-lit, R[r_idx]])
        clauses.append([-lit, C[c_idx]])
    
    # AMO trên rows (pairwise)
    for i in range(p - 1):
        for j in range(i + 1, p):
            clauses.append([-R[i], -R[j]])
    
    # AMO trên cols (pairwise)
    for i in range(q - 1):
        for j in range(i + 1, q):
            clauses.append([-C[i], -C[j]])
    
    return clauses


def amo_sequential(lits: list[int], pool: IDPool) -> list[list[int]]:
    """
    AMO Sequential Counter (Ladder) Encoding [Sinz 2005].
    
    Giới thiệu n-1 register variables s₁..s_{n-1}:
      sᵢ = True ⟺ ít nhất một trong x₁..xᵢ là True.
    
    Clauses:
      (¬x₁ ∨ s₁)                               [C1: x₁ → s₁]
      ∀i ∈ {2..n-1}: (¬xᵢ ∨ sᵢ)               [C2: xᵢ → sᵢ]
      ∀i ∈ {2..n-1}: (¬s_{i-1} ∨ sᵢ)           [C3: monotone propagation]
      ∀i ∈ {2..n}  : (¬xᵢ ∨ ¬s_{i-1})         [C4: AMO enforcement]
    
    Ý nghĩa C4: nếu sᵢ₋₁ = True (có x₁..xᵢ₋₁ đã True), thì xᵢ phải False.
    
    Phức tạp:
      Clauses : 4(n-1) - 1 ≈ 4n   → chính xác: (n-1) + (n-2) + (n-2) + (n-1) = 4n-4
      Aux vars: n-1
    """
    n = len(lits)
    if n <= 1:
        return []
    
    # Register variables s₁..s_{n-1}
    cid = _next_cid()
    s = [pool.id(f"__seq_{cid}_{i}") for i in range(n - 1)]
    
    clauses = []
    
    # [C1] x₁ → s₁
    clauses.append([-lits[0], s[0]])
    
    for i in range(1, n - 1):
        # [C2] xᵢ₊₁ → sᵢ
        clauses.append([-lits[i], s[i]])
        # [C3] sᵢ₋₁ → sᵢ (monotone)
        clauses.append([-s[i - 1], s[i]])
        # [C4] xᵢ₊₁ ∧ sᵢ₋₁ → ⊥
        clauses.append([-lits[i], -s[i - 1]])
    
    # [C4] cho i = n-1 (literal cuối)
    clauses.append([-lits[n - 1], -s[n - 2]])
    
    return clauses


# ── EO (Exactly-One) = AMO + ALO ────────────────────────────────────────────

def eo_pairwise(lits: list[int], pool: IDPool = None) -> list[list[int]]:
    return alo(lits) + amo_pairwise(lits)

def eo_binary(lits: list[int], pool: IDPool) -> list[list[int]]:
    return alo(lits) + amo_binary(lits, pool)

def eo_commander(lits: list[int], pool: IDPool, k: int = 4) -> list[list[int]]:
    return alo(lits) + amo_commander(lits, pool, k)

def eo_product(lits: list[int], pool: IDPool) -> list[list[int]]:
    return alo(lits) + amo_product(lits, pool)

def eo_sequential(lits: list[int], pool: IDPool) -> list[list[int]]:
    return alo(lits) + amo_sequential(lits, pool)


# ── Registry ──────────────────────────────────────────────────────────────────

AMO_ENCODINGS = {
    "pairwise":   amo_pairwise,
    "binary":     amo_binary,
    "commander":  amo_commander,
    "product":    amo_product,
    "sequential": amo_sequential,
}

EO_ENCODINGS = {
    "pairwise":   eo_pairwise,
    "binary":     eo_binary,
    "commander":  eo_commander,
    "product":    eo_product,
    "sequential": eo_sequential,
}

EO_DISPLAY_NAMES = {
    "pairwise":   "Pairwise (Naive)",
    "binary":     "Binary (Log)",
    "commander":  "Commander",
    "product":    "Product",
    "sequential": "Sequential Counter",
}


def get_amo_fn(name: str) -> Callable:
    """Trả về AMO function theo tên."""
    fn = AMO_ENCODINGS.get(name.lower())
    if fn is None:
        raise ValueError(f"Unknown AMO encoding: {name}. "
                         f"Available: {list(AMO_ENCODINGS.keys())}")
    return fn


def get_eo_fn(name: str) -> Callable:
    """Trả về EO (Exactly-One) function theo tên."""
    fn = EO_ENCODINGS.get(name.lower())
    if fn is None:
        raise ValueError(f"Unknown EO encoding: {name}. "
                         f"Available: {list(EO_ENCODINGS.keys())}")
    return fn


def encoding_stats(lits: list[int], pool_start: int = 10000) -> dict:
    """
    Tính thống kê (số clause, số aux var) cho mỗi encoding.
    Chỉ tính AMO (không tính ALO).
    """
    results = {}
    for name, fn in AMO_ENCODINGS.items():
        pool = IDPool(start_from=pool_start)
        before = pool_start - 1
        clauses = fn(lits, pool) if fn != amo_pairwise else fn(lits)
        n_aux = max(pool.top - before, 0) if hasattr(pool, 'top') else 0
        # Đếm aux vars thực sự được dùng
        aux_vars = set()
        for c in clauses:
            for lit in c:
                v = abs(lit)
                if v >= pool_start:
                    aux_vars.add(v)
        results[name] = {
            "clauses":  len(clauses),
            "aux_vars": len(aux_vars),
        }
    return results
