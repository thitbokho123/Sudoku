# Sudoku Solver: SAT vs CP vs ILP – Thực nghiệm So sánh

## Yêu cầu

```
python >= 3.11
```

Cài đặt dependencies:

```bash
pip install python-sat ortools pulp matplotlib numpy
```

> **Lưu ý**: `python-sat` đã cài sẵn (version 1.9.dev15 với các solvers: Cadical103/153/195/300, Glucose3/4/42, Kissat404, CryptoMiniSAT, Lingeling, MiniSAT22, Mergesat3, ...).

---

## Cấu trúc Project

```
sudoku/
├── main.py         # Entry point chính (demo + benchmark)
├── puzzles.py      # Thư viện puzzle Sudoku (Easy/Medium/Hard/Expert)
├── sat_solver.py   # SAT Solver với PySAT (CNF encoding)
├── cp_solver.py    # CP Solver với OR-Tools CP-SAT
├── ilp_solver.py   # ILP/MIP Solver với PuLP (CPLEX/Gurobi/CPSAT fallback)
├── benchmark.py    # Framework thực nghiệm so sánh
├── analysis.py     # Phân tích & visualize kết quả
└── README.md
```

---

## Sử dụng nhanh

### Demo giải một puzzle

```bash
# Demo Expert-1 (AI Escargot – Arto Inkala 2006)
python main.py --demo-only --puzzle expert1

# Demo puzzle theo level
python main.py --demo-only --puzzle hard
python main.py --demo-only --puzzle medium2
```

### Chạy Benchmark đầy đủ

```bash
# Benchmark chuẩn (3 runs × 12 puzzles × 11 solvers)
python benchmark.py --runs 3 --timeout 30

# Benchmark nhanh (debug)
python benchmark.py --runs 1

# Tùy chỉnh
python benchmark.py --runs 5 --timeout 60 --output my_results
```

### Phân tích & Visualize

```bash
# Sau khi có results.csv
python analysis.py

# Chỉ báo cáo text, không vẽ hình
python analysis.py --no-plot

# Chỉ định file input/output
python analysis.py --input my_results.csv --output ./plots/
```

---

## Phương pháp Giải

### 1. SAT Solving (PySAT)

**Encoding**: Biến Boolean `x_{r,c,v}` = True nếu ô `(r,c)` chứa giá trị `v`.

| Ràng buộc | Clauses |
|-----------|---------|
| Cell: mỗi ô có ≥1 giá trị | 81 clauses |
| Cell uniqueness: mỗi ô có ≤1 giá trị | 81×36 = 2916 clauses |
| Row: mỗi giá trị xuất hiện đúng 1 lần/hàng | 9×(9+36) = 405 clauses |
| Column: tương tự | 405 clauses |
| Box 3×3: tương tự | 9×(9+36) = 405 clauses |
| Clues | #given clauses |
| **Tổng** | **~12,000+ clauses, 729 variables** |

**SAT Solvers hỗ trợ** (qua PySAT):

| Solver | Phiên bản | Đặc điểm |
|--------|-----------|----------|
| **Cadical** | 1.9.5, 3.0.0 | CDCL, state-of-the-art |
| **Glucose** | 4.x, 4.2 | CDCL+LBD, nhanh cho SAT |
| **Kissat** | 4.0.4 | Lightweight CDCL, giải thưởng SAT Competition |
| **CryptoMiniSAT** | 5.x | CDCL+XOR, phù hợp bài toán mật mã |
| **Lingeling** | - | Portfolio/look-ahead |
| **MiniSAT** | 2.2 | Classic baseline |

### 2. Constraint Programming – CP (OR-Tools CP-SAT)

Mô hình CP:
- Biến: `x[r][c] ∈ {1..9}`
- Ràng buộc: `AllDifferent` cho từng hàng, cột, box 3×3

CP-SAT là **hybrid CP/SAT solver** của Google, sử dụng propagation + clause learning.

### 3. Integer Linear Programming – ILP (PuLP)

**Mô hình BIP (Binary Integer Program)**:

```
minimize 0
s.t.
  Σ_v x[r,c,v] = 1    ∀ r,c    (cell)
  Σ_c x[r,c,v] = 1    ∀ r,v    (row)
  Σ_r x[r,c,v] = 1    ∀ c,v    (col)
  Σ_{r,c∈box} x[r,c,v] = 1  ∀ box,v  (box)
  x[r,c,v] ∈ {0,1}
```

**ILP/MIP Solvers** (với fallback tự động):

| Solver | Status | Ghi chú |
|--------|--------|---------|
| **CPLEX MIP** | Cần licence | Giao diện qua `pulp.CPLEX_PY` |
| **Gurobi** | Cần licence | Giao diện qua `pulp.GUROBI` |
| **CPSAT (OR-Tools)** | ✅ Miễn phí | Fallback mặc định qua `pulp.CPSAT` |
| **HiGHS** | ✅ Miễn phí | Cài `pip install highspy` |

---

## Kết quả Thực nghiệm (mẫu)

### Tổng kết (12 puzzles, 3 runs mỗi solver)

| Rank | Solver | Method | Mean (ms) | Verified |
|------|--------|--------|-----------|----------|
| 1 | MiniSAT 2.2 | SAT | ~8.96 | 12/12 ✓ |
| 2 | OR-Tools CP-SAT | CP | ~9.25 | 12/12 ✓ |
| 3 | Glucose 4.x | SAT | ~9.37 | 12/12 ✓ |
| 4 | Glucose 4.2 | SAT | ~10.06 | 12/12 ✓ |
| 5 | Cadical 1.9.5 | SAT | ~10.62 | 12/12 ✓ |
| ... | | | | |
| 10 | CPSAT-ILP | ILP/MIP | ~32.24 | 12/12 ✓ |

### Nhận xét

- **SAT Solving**: ~8–16ms, ổn định trên mọi mức độ khó
- **CP (CP-SAT)**: ~5–21ms, nhanh nhất trên Easy, cạnh tranh tốt
- **ILP/MIP**: ~22–95ms, chậm hơn ~3–4× so với SAT/CP (overhead mô hình hoá)
- Tất cả solver **giải đúng 100%** các puzzle (verified)
- SAT encoding **không phụ thuộc độ khó** → thời gian rất ổn định

---

## Thêm Solver Thương mại

### CPLEX MIP (IBM)

```bash
pip install cplex docplex
```

Code tự động phát hiện và dùng CPLEX khi có licence.

### Gurobi

```bash
pip install gurobipy
```

Code tự động phát hiện khi có Gurobi licence.

### CPLEX CP Optimizer

```bash
pip install docplex
```

Có thể tích hợp thêm vào `cp_solver.py` qua `docplex.cp.model`.

---

## Output Files

| File | Nội dung |
|------|---------|
| `results.csv` | Kết quả chi tiết từng (puzzle × solver) |
| `results.json` | Kết quả JSON (bao gồm solution grid) |
| `fig1_overall_bar.png` | Bar chart tổng hợp |
| `fig2_difficulty_grouped.png` | Grouped bar theo độ khó |
| `fig3_heatmap.png` | Heatmap solver × puzzle |
| `fig4_scaling.png` | Line plot scaling theo độ khó |
| `fig5_sat_comparison.png` | Chi tiết SAT solvers |
