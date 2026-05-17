# Superscalar / Multiple-Issue Simulator

**Course:** Computer Architecture and Operating Systems  
**Topic 5:** Multiple Issue, Static / Dynamic Scheduling, Speculation  
**Team:** [K27]  

---

## What It Does

A cycle-accurate simulator of a 2- and 4-wide superscalar processor that can switch between:

| Mode | Description |
|------|-------------|
| **In-Order (Static Scheduling)** | Issues up to N instructions per cycle; stalls on RAW hazards |
| **Out-of-Order (Dynamic Scheduling)** | Issue Queue + ROB; executes instructions as operands become ready |

The simulator also includes:
- 2-bit saturating branch predictor + mispredict recovery
- ILP oracle (ideal infinite machine) for comparison
- 5 benchmark programs showing different levels of ILP
- IPC comparison plots

---

## Quick Start

```bash
# 1. Run all benchmarks
cd src
python main.py

# 2. Run a specific benchmark verbosely
python main.py dot_product

# 3. Generate plots (requires matplotlib)
cd ../visualization
python visualize.py

# 4. Run tests
cd ../tests
python test_simulator.py
```

---

## Project Structure

```
superscalar-sim/
├── src/
│   ├── simulator.py        # Base class + InOrder Superscalar  (Member 1 & 2)
│   ├── ooo_scheduler.py    # Out-of-Order + Branch Predictor   (Member 3)
│   ├── benchmarks.py       # Benchmark programs + ILP oracle   (Member 4)
│   └── main.py             # Runner + summary table            (Member 4)
├── visualization/
│   └── visualize.py        # IPC bar charts (matplotlib)       (Member 4)
├── tests/
│   └── test_simulator.py   # Unit tests                        (Member 1 & 2)
├── AI_USAGE.md             # How AI tools were used
└── README.md
```

---

## Benchmarks

| Benchmark | Description | Expected ILP |
|-----------|-------------|-------------|
| `add_chain` | RAW dependency chain | Very low |
| `independent_adds` | Fully independent adds | High (≈ width) |
| `dot_product` | Load-mul-add with RAW | Medium |
| `matrix_row` | Row accumulation | Medium |
| `branch_heavy` | Frequent branches | Low–Medium |

---

## Key Concepts Demonstrated

- **ILP wall:** Even with 4-wide issue, a dependency chain runs at IPC ≈ 1
- **Out-of-order advantage:** Independent instructions hidden behind a stall are found and executed
- **Branch misprediction cost:** Shows flush penalty for wrong predictions
- **Width scaling:** Going from 2-wide to 4-wide only helps if the program has enough ILP

---

## Team & Contributions

| Member | Role | Files |
|--------|------|-------|
| Member 1 | Wide Fetch/Decode + base infrastructure | `simulator.py` (base class, RegisterFile, PipelineSlot) |
| Member 2 | In-Order Issue + tests | `simulator.py` (InOrderSuperscalar), `test_simulator.py` |
| Member 3 | Out-of-Order Issue + Branch Predictor | `ooo_scheduler.py` |
| Member 4 | ILP Analysis + Visualization + Main | `benchmarks.py`, `main.py`, `visualize.py` |

---

## AI Tool Used

**Claude** (`claude-sonnet-4-20250514`) via [claude.ai](https://claude.ai)  
See [AI_USAGE.md](AI_USAGE.md) for example prompts and how AI assisted the project.
