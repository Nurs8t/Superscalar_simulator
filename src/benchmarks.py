"""
ILP Analysis & Benchmark Programs
Topic 5: How much ILP is actually in the program?

Author: Member 4 (ILP Analysis + Presentation)
AI Tool: Claude (claude-sonnet-4-20250514)
"""

from simulator import Instruction, OpType
from typing import List, Dict
import math


# ─────────────────────────────────────────────
#  Benchmark Programs (RISC-V subset assembly)
# ─────────────────────────────────────────────

def prog_add_chain(n: int = 10) -> List[Instruction]:
    """
    RAW dependency chain — very low ILP.
    add x1, x1, x2  (each depends on previous)
    """
    prog = []
    for _ in range(n):
        prog.append(Instruction(OpType.ALU, "add", rd=1, rs1=1, rs2=2))
    return prog


def prog_independent_adds(n: int = 10) -> List[Instruction]:
    """
    Fully independent adds — maximum ILP = width.
    add x1, x3, x4
    add x2, x5, x6
    add x7, x8, x9   ...
    """
    prog = []
    regs = [(1,3,4),(2,5,6),(7,8,9),(10,11,12),
            (13,14,15),(16,17,18),(19,20,21),(22,23,24)]
    for i in range(n):
        r = regs[i % len(regs)]
        prog.append(Instruction(OpType.ALU, "add", rd=r[0], rs1=r[1], rs2=r[2]))
    return prog


def prog_dot_product(n: int = 8) -> List[Instruction]:
    """
    Dot product loop body (unrolled 4x):
      lw  x1, 0(x10)
      lw  x2, 4(x10)
      mul x3, x1, x2
      add x4, x4, x3   ← RAW on x3
    """
    prog = []
    base = 0
    for i in range(n):
        prog += [
            Instruction(OpType.LOAD,  "lw",  rd=1,  rs1=10, imm=base),
            Instruction(OpType.LOAD,  "lw",  rd=2,  rs1=11, imm=base),
            Instruction(OpType.MUL,   "mul", rd=3,  rs1=1,  rs2=2),
            Instruction(OpType.ALU,   "add", rd=4,  rs1=4,  rs2=3),
        ]
        base += 4
    return prog


def prog_matrix_row(cols: int = 4) -> List[Instruction]:
    """
    Matrix-row accumulation with pointer increments.
    """
    prog = []
    for i in range(cols):
        prog += [
            Instruction(OpType.LOAD, "lw",  rd=5,  rs1=10, imm=i*4),
            Instruction(OpType.LOAD, "lw",  rd=6,  rs1=11, imm=i*4),
            Instruction(OpType.MUL,  "mul", rd=7,  rs1=5,  rs2=6),
            Instruction(OpType.ALU,  "add", rd=8,  rs1=8,  rs2=7),
        ]
    return prog


def prog_branch_heavy(n: int = 8) -> List[Instruction]:
    """
    Mix of arithmetic + frequent branches.
    Stresses branch prediction.
    """
    prog = []
    for i in range(n):
        prog += [
            Instruction(OpType.ALU,    "add",  rd=1, rs1=2, rs2=3),
            Instruction(OpType.ALU,    "slt",  rd=4, rs1=1, rs2=5),
            Instruction(OpType.BRANCH, "beq",  rs1=4, rs2=0, imm=1),
            Instruction(OpType.ALU,    "add",  rd=6, rs1=6, rs2=1),
        ]
    return prog


BENCHMARKS: Dict[str, List[Instruction]] = {
    "add_chain":        prog_add_chain(12),
    "independent_adds": prog_independent_adds(12),
    "dot_product":      prog_dot_product(4),
    "matrix_row":       prog_matrix_row(4),
    "branch_heavy":     prog_branch_heavy(6),
}


# ─────────────────────────────────────────────
#  Static ILP Oracle (ideal infinite machine)
# ─────────────────────────────────────────────

def compute_ideal_ilp(program: List[Instruction]) -> Dict:
    """
    Simulate an ideal processor (infinite width, no hazards except true RAW).
    Returns the critical-path length and theoretical max ILP.
    """
    n = len(program)
    if n == 0:
        return {"ideal_cycles": 0, "ideal_ipc": 0.0}

    # ready[i] = earliest cycle instruction i can START (1-indexed cycles)
    earliest = [1] * n
    # last writer: reg -> (cycle it becomes available)
    last_write: Dict[int, int] = {}

    for i, instr in enumerate(program):
        dep_cycle = 1
        if instr.op not in (OpType.NOP, OpType.STORE, OpType.BRANCH):
            rs1_rdy = last_write.get(instr.rs1, 0)
            rs2_rdy = last_write.get(instr.rs2, 0)
            dep_cycle = max(dep_cycle, rs1_rdy + 1, rs2_rdy + 1)

        earliest[i] = dep_cycle
        latency = {
            OpType.ALU: 1, OpType.MUL: 3, OpType.LOAD: 2,
            OpType.STORE: 1, OpType.BRANCH: 1, OpType.NOP: 1
        }[instr.op]

        if instr.rd != 0 and instr.op not in (OpType.STORE, OpType.BRANCH, OpType.NOP):
            finish = dep_cycle + latency - 1
            prev   = last_write.get(instr.rd, 0)
            last_write[instr.rd] = max(prev, finish)

    ideal_cycles = max(last_write.values()) if last_write else n
    ideal_ipc    = n / ideal_cycles if ideal_cycles > 0 else float("inf")

    return {
        "ideal_cycles": ideal_cycles,
        "ideal_ipc":    round(ideal_ipc, 3),
        "instructions": n,
    }


# ─────────────────────────────────────────────
#  Print comparison table
# ─────────────────────────────────────────────

def print_comparison(results: List[Dict], ideal: Dict):
    print("\n" + "="*70)
    print(f"{'Config':<22} {'Cycles':>8} {'IPC':>8} {'Stalls':>8} {'Mispredicts':>12}")
    print("-"*70)
    for r in results:
        print(f"{r['name']:<22} {r['cycles']:>8} {r['IPC']:>8.3f} "
              f"{r['stall_cycles']:>8} {r['branch_mispredicts']:>12}")
    print("-"*70)
    print(f"{'Ideal (oracle)':<22} {ideal['ideal_cycles']:>8} {ideal['ideal_ipc']:>8.3f}")
    print("="*70 + "\n")
