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
    
# ─────────────────────────────────────────────
#  In-Order Superscalar (Static Scheduling)
#  Contributor: Member 2
# ─────────────────────────────────────────────

class InOrderSuperscalar(SuperscalarBase):
    """
    2- or 4-wide in-order issue.
    Stalls on RAW hazards. No speculation.
    Branch resolves in 1 cycle; incorrect prediction flushes fetch.
    """

    def __init__(self, program, width=2, memory_size=1024):
        super().__init__(program, width, memory_size, name=f"InOrder-{width}wide")
        # Scoreboard: which cycle each register will be ready
        self.scoreboard: List[int] = [0] * 32   # 0 = ready now

    def _reg_ready(self, r: int, current_cycle: int) -> bool:
        return self.scoreboard[r] <= current_cycle

    def _can_issue(self, instr: Instruction, current_cycle: int) -> bool:
        """Check RAW hazards for in-order issue."""
        if instr.op == OpType.NOP:
            return True
        rs1_ok = self._reg_ready(instr.rs1, current_cycle)
        rs2_ok = instr.op in (OpType.STORE, OpType.BRANCH, OpType.ALU, OpType.MUL) \
                 and self._reg_ready(instr.rs2, current_cycle) or \
                 instr.op in (OpType.LOAD,) and True
        # For LOAD only rs1 matters at issue (rs2 unused)
        if instr.op == OpType.LOAD:
            return rs1_ok
        return rs1_ok and self._reg_ready(instr.rs2, current_cycle)

    def run(self) -> Dict:
        # Straightforward cycle-accurate simulation
        # Each cycle: try to fetch+issue up to `width` instructions
        # then advance execution units by 1 cycle
        in_flight: List[PipelineSlot] = []

        while self.pc < len(self.program) or in_flight:
            self.cycle += 1

            # ── Writeback (complete execution) ──────────────
            newly_done = []
            still_busy = []
            for slot in in_flight:
                slot.cycles_left -= 1
                if slot.cycles_left <= 0:
                    newly_done.append(slot)
                else:
                    still_busy.append(slot)
            in_flight = still_busy

            for slot in newly_done:
                instr = slot.instr
                if instr.op in (OpType.ALU, OpType.MUL):
                    self.rf.write(instr.rd, slot.result)
                elif instr.op == OpType.LOAD:
                    addr = self.rf.read(instr.rs1) + instr.imm
                    val  = self.mem_read(addr)
                    self.rf.write(instr.rd, val)
                elif instr.op == OpType.STORE:
                    addr = self.rf.read(instr.rs1) + instr.imm
                    self.mem_write(addr, self.rf.read(instr.rs2))
                self.instr_retired += 1
                self.log.append({
                    "cycle": self.cycle,
                    "pc":    slot.pc,
                    "instr": str(instr),
                    "mode":  "commit"
                })

            # ── Fetch + Issue (up to `width` instructions) ──
            issued_this_cycle = 0
            stall_this_issue  = False

            while issued_this_cycle < self.width and \
                  self.pc < len(self.program) and \
                  not stall_this_issue:

                instr = self.program[self.pc]

                if not self._can_issue(instr, self.cycle):
                    stall_this_issue = True
                    self.stall_cycles += 1
                    break

                # Mark destination as busy
                if instr.op in (OpType.ALU, OpType.MUL, OpType.LOAD) and instr.rd != 0:
                    ready_cycle = self.cycle + LATENCY[instr.op]
                    self.scoreboard[instr.rd] = ready_cycle

                # Compute result for ALU immediately (value available after latency)
                result = 0
                if instr.op in (OpType.ALU, OpType.MUL):
                    result = self.execute_alu(instr)

                # Branch: resolve immediately (no prediction, just stall 1 cycle)
                if instr.op == OpType.BRANCH:
                    rs1 = self.rf.read(instr.rs1)
                    rs2 = self.rf.read(instr.rs2)
                    taken = (instr.mnem == "beq" and rs1 == rs2) or \
                            (instr.mnem == "bne" and rs1 != rs2)
                    if taken:
                        self.pc += instr.imm
                        self.instr_retired += 1
                        issued_this_cycle += 1
                        break
                    else:
                        self.pc += 1
                        self.instr_retired += 1
                        issued_this_cycle += 1
                        continue

                slot = PipelineSlot(
                    instr=instr,
                    pc=self.pc,
                    cycles_left=LATENCY[instr.op],
                    rd=instr.rd,
                    result=result,
                    issued_cycle=self.cycle,
                )
                in_flight.append(slot)
                self.pc += 1
                issued_this_cycle += 1

        return self.stats()