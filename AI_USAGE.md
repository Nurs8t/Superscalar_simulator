# AI Usage — Superscalar Simulator

**Tool:** Claude (`claude-sonnet-4-20250514`) via claude.ai  
**Requirement:** Per project instructions, AI usage is mandatory and must be documented.

---

## How We Used Claude

### Nurseyit — Wide Fetch/Decode Infrastructure

**Prompt example:**
> "Design a Python dataclass hierarchy for a cycle-accurate superscalar processor simulator.
> I need: an Instruction class (RISC-V subset ops: ALU, MUL, LOAD, STORE, BRANCH),
> a RegisterFile with read/write/busy tracking, and a PipelineSlot that holds
> an instruction in flight with a countdown. Keep it simple and extensible."

**What Claude generated:** The `Instruction`, `RegisterFile`, `PipelineSlot` dataclasses and the `SuperscalarBase` class skeleton.  
**What we changed:** Added `OpType.NOP`, tuned `LATENCY` dict values, added the `snapshot()` method.

---

### Bekzhan — In-Order Issue (Static Scheduling)

**Prompt example:**
> "Implement an in-order superscalar issue stage in Python.
> The processor is N-wide (N=2 or 4). It uses a scoreboard (array of 'ready cycle'
> per register). On each cycle, try to fetch up to N instructions; stall if any
> source register is not ready. Branches resolve in 1 cycle without prediction.
> Show the main run() loop."

**What Claude generated:** The `InOrderSuperscalar.run()` loop with scoreboard checks.  
**What we changed:** Fixed branch handling to break out of the issue loop correctly; added `stall_cycles` counter.

---

### Nursayat — Out-of-Order Issue + Branch Predictor

**Prompt example:**
> "Add an Out-of-Order issue engine to my superscalar simulator.
> It should have: an Issue Queue (max 16 entries), a Reorder Buffer (max 32 entries)
> for in-order commit, a forwarding bus to resolve RAW hazards as instructions complete,
> and a 2-bit saturating counter branch predictor with a 64-entry table.
> On mispredict: flush IQ and in-flight units."

**What Claude generated:** The `TwoBitPredictor`, `ROBEntry`, and `OutOfOrderSuperscalar` class.  
**What we changed:** Debugged the `_resolve_src()` forwarding logic; simplified ROB entry matching using `id()`.

---

### Ali— ILP Analysis + Benchmarks + Visualization

**Prompt example:**
> "Write 5 short RISC-V benchmark programs as Python lists of Instruction objects.
> They should cover: (1) a pure RAW dependency chain, (2) fully independent adds,
> (3) dot-product loop body with load+mul+add, (4) matrix row accumulation,
> (5) branch-heavy code. Also write an 'ILP oracle' function that computes the
> ideal IPC assuming an infinitely wide machine with no hazards except true RAW."

**What Claude generated:** All 5 benchmark functions and the `compute_ideal_ilp()` function.  
**What we changed:** Fixed the `last_write` tracking for STORE/BRANCH (they don't write registers); added the `ascii_bar` fallback for systems without matplotlib.


## What We Learned About Working With AI

1. **AI is great for boilerplate** — class skeletons, dataclasses, loop structure
2. **AI makes mistakes in complex state logic** — the forwarding bus and ROB commit needed manual debugging
3. **Prompts need to be specific** — vague prompts give vague code; specifying exact fields and behaviors gives working code
4. **Understand before committing** — we had to explain every function at the defense
