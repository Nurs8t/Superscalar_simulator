"""
Out-of-Order Superscalar — Dynamic Scheduling
Topic 5: Multiple Issue, Dynamic Scheduling, Speculation
 
Author: Nursayat (Out-of-Order Issue + Branch Prediction)
AI Tool: Claude (claude-sonnet-4-20250514)
"""
 
from typing import List, Dict, Tuple
from simulator import SuperscalarBase, Instruction, OpType, LATENCY
 
 
# ─────────────────────────────────────────────
#  Simple 2-bit Branch Predictor
# ─────────────────────────────────────────────
 
class TwoBitPredictor:
    """
    2-bit saturating counter predictor.
    States: 0=StrongNot, 1=WeakNot, 2=WeakTaken, 3=StrongTaken
    """
    def __init__(self, table_size: int = 64):
        self.table = [2] * table_size
        self.size  = table_size
 
    def _idx(self, pc: int) -> int:
        return pc % self.size
 
    def predict(self, pc: int) -> bool:
        return self.table[self._idx(pc)] >= 2
 
    def update(self, pc: int, taken: bool):
        idx = self._idx(pc)
        if taken:
            self.table[idx] = min(3, self.table[idx] + 1)
        else:
            self.table[idx] = max(0, self.table[idx] - 1)
 
 
# ─────────────────────────────────────────────
#  Out-of-Order Superscalar (Dynamic Scheduling)
# ─────────────────────────────────────────────
 
class OutOfOrderSuperscalar(SuperscalarBase):
    """
    Simplified but correct OoO processor.
    Uses a ready-time scoreboard per register.
    Instructions execute out of order once operands are ready.
    """
 
    def __init__(self, program, width=2, memory_size=1024):
        super().__init__(program, width, memory_size,
                         name=f"OoO-{width}wide")
        self.predictor = TwoBitPredictor()
 
        # ready_at[reg] = cycle when register value will be available
        self.ready_at: List[int] = [0] * 32   # 0 = already ready
 
        # issue_queue: list of (pc, instr, earliest_start_cycle)
        self.issue_queue: List[Tuple[int, Instruction, int]] = []
 
        # in_flight: list of (finish_cycle, instr)
        self.in_flight: List[Tuple[int, Instruction]] = []
 
    def _operands_ready_at(self, instr: Instruction) -> int:
        """Return the earliest cycle both source operands are ready."""
        if instr.op == OpType.NOP:
            return 0
        rs1_ready = self.ready_at[instr.rs1]
        if instr.op in (OpType.ALU, OpType.MUL, OpType.BRANCH, OpType.STORE):
            rs2_ready = self.ready_at[instr.rs2]
        else:
            rs2_ready = 0  # LOAD only needs rs1
        return max(rs1_ready, rs2_ready)
 
    def _compute(self, instr: Instruction) -> int:
        """Compute ALU result using current register file values."""
        rs1 = self.rf.read(instr.rs1)
        rs2 = self.rf.read(instr.rs2)
        m = instr.mnem
        if m == "add":  return rs1 + rs2
        if m == "sub":  return rs1 - rs2
        if m == "and":  return rs1 & rs2
        if m == "or":   return rs1 | rs2
        if m == "xor":  return rs1 ^ rs2
        if m == "slt":  return 1 if rs1 < rs2 else 0
        if m == "mul":  return rs1 * rs2
        if m == "addi": return rs1 + instr.imm
        return 0
 
    def run(self) -> Dict:
        cycle = 0
        MAX_CYCLES = 100000
 
        while self.pc < len(self.program) or self.issue_queue or self.in_flight:
            cycle += 1
            self.cycle = cycle
 
            if cycle > MAX_CYCLES:
                break
 
            # ── 1. Complete in-flight instructions ──────────
            still_busy = []
            for (finish_cycle, instr) in self.in_flight:
                if finish_cycle <= cycle:
                    if instr.op in (OpType.ALU, OpType.MUL) and instr.rd != 0:
                        self.rf.write(instr.rd, self._compute(instr))
                    elif instr.op == OpType.LOAD and instr.rd != 0:
                        addr = self.rf.read(instr.rs1) + instr.imm
                        self.rf.write(instr.rd, self.mem_read(addr))
                    elif instr.op == OpType.STORE:
                        addr = self.rf.read(instr.rs1) + instr.imm
                        self.mem_write(addr, self.rf.read(instr.rs2))
                    self.instr_retired += 1
                    self.log.append({
                        "cycle": cycle,
                        "instr": str(instr),
                        "mode":  "commit"
                    })
                else:
                    still_busy.append((finish_cycle, instr))
            self.in_flight = still_busy
 
            # ── 2. Issue from queue (out-of-order) ──────────
            self.issue_queue.sort(key=lambda x: x[2])
            issued = 0
            remaining = []
            for (pc, instr, earliest) in self.issue_queue:
                if issued >= self.width:
                    remaining.append((pc, instr, earliest))
                    continue
                if earliest <= cycle:
                    lat = LATENCY[instr.op]
                    self.in_flight.append((cycle + lat, instr))
                    if instr.op in (OpType.ALU, OpType.MUL, OpType.LOAD) and instr.rd != 0:
                        self.ready_at[instr.rd] = cycle + lat
                    issued += 1
                else:
                    remaining.append((pc, instr, earliest))
            self.issue_queue = remaining
 
            # ── 3. Fetch up to width instructions ───────────
            fetched = 0
            while fetched < self.width and self.pc < len(self.program):
                instr = self.program[self.pc]
 
                if instr.op == OpType.BRANCH:
                    predicted = self.predictor.predict(self.pc)
                    rs1 = self.rf.read(instr.rs1)
                    rs2 = self.rf.read(instr.rs2)
                    actual = (instr.mnem == "beq" and rs1 == rs2) or \
                             (instr.mnem == "bne" and rs1 != rs2)
                    self.predictor.update(self.pc, actual)
                    if predicted != actual:
                        self.branch_mispredicts += 1
                        self.issue_queue = []
                        self.in_flight   = []
                    self.pc = self.pc + instr.imm if actual else self.pc + 1
                    self.instr_retired += 1
                    fetched += 1
                    break
 
                earliest = self._operands_ready_at(instr) + 1
                self.issue_queue.append((self.pc, instr, earliest))
                self.pc += 1
                fetched += 1
 
        self.cycle = cycle
        return self.stats()
 