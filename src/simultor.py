"""
Superscalar / Multiple-Issue Simulator
Topic 5: Multiple Issue, Static/Dynamic Scheduling, Speculation

Author: Member 1 (Wide Fetch/Decode) + Member 2 (In-Order Issue)
AI Tool: Claude (claude-sonnet-4-20250514)
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Dict, Tuple
import copy


# ─────────────────────────────────────────────
#  Instruction Set (RISC-V subset)
# ─────────────────────────────────────────────

class OpType(Enum):
    ALU    = auto()   # add, sub, and, or, xor, slt
    MUL    = auto()   # mul (3-cycle latency)
    LOAD   = auto()   # lw  (2-cycle latency)
    STORE  = auto()   # sw
    BRANCH = auto()   # beq, bne
    NOP    = auto()


@dataclass
class Instruction:
    op:    OpType
    mnem:  str        # e.g. "add", "lw", "beq"
    rd:    int = 0    # destination register (0 = none)
    rs1:   int = 0
    rs2:   int = 0
    imm:   int = 0    # immediate / branch offset
    label: str = ""   # optional debug label

    def __str__(self):
        if self.op == OpType.LOAD:
            return f"{self.mnem} x{self.rd}, {self.imm}(x{self.rs1})"
        if self.op == OpType.STORE:
            return f"{self.mnem} x{self.rs2}, {self.imm}(x{self.rs1})"
        if self.op == OpType.BRANCH:
            return f"{self.mnem} x{self.rs1}, x{self.rs2}, {self.imm}"
        if self.op == OpType.NOP:
            return "nop"
        return f"{self.mnem} x{self.rd}, x{self.rs1}, x{self.rs2}"


NOP_INST = Instruction(OpType.NOP, "nop")

LATENCY = {
    OpType.ALU:    1,
    OpType.MUL:    3,
    OpType.LOAD:   2,
    OpType.STORE:  1,
    OpType.BRANCH: 1,
    OpType.NOP:    1,
}


# ─────────────────────────────────────────────
#  Register File
# ─────────────────────────────────────────────

class RegisterFile:
    def __init__(self):
        self.regs: List[int] = [0] * 32   # x0..x31
        self.ready: List[bool] = [True] * 32

    def read(self, r: int) -> int:
        return self.regs[r]

    def write(self, r: int, val: int):
        if r != 0:   # x0 is always 0
            self.regs[r] = val
            self.ready[r] = True

    def set_busy(self, r: int):
        if r != 0:
            self.ready[r] = False

    def is_ready(self, r: int) -> bool:
        return self.ready[r]

    def snapshot(self) -> List[int]:
        return list(self.regs)


# ─────────────────────────────────────────────
#  Pipeline Slot (one instruction in flight)
# ─────────────────────────────────────────────

@dataclass
class PipelineSlot:
    instr:       Instruction
    pc:          int
    cycles_left: int          # countdown to writeback
    rd:          int = 0
    result:      int = 0
    issued_cycle: int = 0


# ─────────────────────────────────────────────
#  Base Superscalar Processor
# ─────────────────────────────────────────────

class SuperscalarBase:
    """
    Shared infrastructure for both in-order and out-of-order variants.
    Width = number of instructions issued per cycle (2 or 4).
    """

    def __init__(self, program: List[Instruction], width: int = 2,
                 memory_size: int = 1024, name: str = "Superscalar"):
        self.program  = program
        self.width    = width
        self.memory   = [0] * memory_size
        self.name     = name

        # Architectural state
        self.rf       = RegisterFile()
        self.pc       = 0

        # Cycle counters / stats
        self.cycle         = 0
        self.instr_retired = 0
        self.stall_cycles  = 0
        self.branch_mispredicts = 0

        # In-flight execution units (list of PipelineSlot)
        self.exec_units: List[Optional[PipelineSlot]] = []

        # Commit log for visualization
        self.log: List[Dict] = []

    # ── Memory helpers ──────────────────────────────────────
    def mem_read(self, addr: int) -> int:
        idx = addr // 4
        if 0 <= idx < len(self.memory):
            return self.memory[idx]
        return 0

    def mem_write(self, addr: int, val: int):
        idx = addr // 4
        if 0 <= idx < len(self.memory):
            self.memory[idx] = val

    # ── ALU execution ───────────────────────────────────────
    def execute_alu(self, instr: Instruction) -> int:
        rs1 = self.rf.read(instr.rs1)
        rs2 = self.rf.read(instr.rs2)
        m   = instr.mnem
        if m == "add":  return rs1 + rs2
        if m == "sub":  return rs1 - rs2
        if m == "and":  return rs1 & rs2
        if m == "or":   return rs1 | rs2
        if m == "xor":  return rs1 ^ rs2
        if m == "slt":  return 1 if rs1 < rs2 else 0
        if m == "mul":  return rs1 * rs2
        if m == "addi": return rs1 + instr.imm
        return 0

    def stats(self) -> Dict:
        ipc = self.instr_retired / self.cycle if self.cycle else 0
        return {
            "name":              self.name,
            "width":             self.width,
            "cycles":            self.cycle,
            "instructions":      self.instr_retired,
            "IPC":               round(ipc, 3),
            "stall_cycles":      self.stall_cycles,
            "branch_mispredicts": self.branch_mispredicts,
        }
