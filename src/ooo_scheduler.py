"""
Out-of-Order Superscalar — Dynamic Scheduling
Topic 5: Multiple Issue, Dynamic Scheduling, Speculation

Author: Nursayat (Out-of-Order Issue + Branch Prediction)
AI Tool: Claude (claude-sonnet-4-20250514)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Deque
from collections import deque
from simulator import (
    SuperscalarBase, Instruction, OpType, NOP_INST,
    LATENCY, PipelineSlot
)


# ─────────────────────────────────────────────
#  Simple 2-bit Branch Predictor
# ─────────────────────────────────────────────

class TwoBitPredictor:
    """
    2-bit saturating counter predictor.
    States: 0=StrongNot, 1=WeakNot, 2=WeakTaken, 3=StrongTaken
    """
    def __init__(self, table_size: int = 64):
        self.table = [2] * table_size   # start weakly taken
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
#  ROB Entry (simplified)
# ─────────────────────────────────────────────

@dataclass
class ROBEntry:
    instr:      Instruction
    pc:         int
    done:       bool  = False
    result:     int   = 0
    rd:         int   = 0
    mispredict: bool  = False


# ─────────────────────────────────────────────
#  Out-of-Order Superscalar (Dynamic Scheduling)
# ─────────────────────────────────────────────

class OutOfOrderSuperscalar(SuperscalarBase):
    """
    2- or 4-wide out-of-order processor.
    - Issue queue (IQ) holds up to 16 instructions waiting for operands.
    - ROB (Reorder Buffer) enforces in-order commit.
    - 2-bit branch predictor + mispredict recovery.
    - WAW/WAR hazards resolved by register renaming (simplified: use ROB index).
    """

    IQ_SIZE  = 16
    ROB_SIZE = 32

    def __init__(self, program, width=2, memory_size=1024):
        super().__init__(program, width, memory_size,
                         name=f"OoO-{width}wide")
        self.predictor = TwoBitPredictor()

        # Issue Queue: instructions waiting to execute
        self.iq: List[Dict] = []          # {"instr", "pc", "rs1_ready", "rs2_ready", "rs1_val", "rs2_val", "rob_idx"}

        # Reorder Buffer (circular conceptually, list here for simplicity)
        self.rob: Deque[ROBEntry] = deque()

        # Rename table: reg -> ROB index that will produce it (None = arch. file)
        self.rename: List[Optional[int]] = [None] * 32

        # In-flight execution (same PipelineSlot as base class)
        self.in_flight: List[PipelineSlot] = []

        # Forwarding bus: rob_idx -> value (available this cycle)
        self.forward: Dict[int, int] = {}

    # ── Helpers ─────────────────────────────────────────────

    def _resolve_src(self, reg: int) -> Tuple[bool, int]:
        """Return (ready, value) for register `reg`, checking ROB forwarding."""
        rob_idx = self.rename[reg]
        if rob_idx is None:
            return True, self.rf.read(reg)
        # Check forwarding bus first
        if rob_idx in self.forward:
            return True, self.forward[rob_idx]
        # Check ROB
        for entry in self.rob:
            if id(entry) == rob_idx:
                if entry.done:
                    return True, entry.result
                return False, 0
        # ROB entry gone (committed) — use arch file
        return True, self.rf.read(reg)

    def _add_to_rob(self, instr: Instruction, pc: int) -> ROBEntry:
        entry = ROBEntry(instr=instr, pc=pc, rd=instr.rd)
        self.rob.append(entry)
        return entry

    def run(self) -> Dict:
        while self.pc < len(self.program) or self.rob or self.in_flight:
            self.cycle += 1
            self.forward = {}

            # ── 1. Writeback (complete execution) ──────────
            still_busy = []
            for slot in self.in_flight:
                slot.cycles_left -= 1
                if slot.cycles_left <= 0:
                    # Broadcast result on forwarding bus
                    if slot.rd != 0:
                        self.forward[slot.rob_entry_id] = slot.result
                    # Mark ROB entry done
                    for entry in self.rob:
                        if entry.pc == slot.pc and entry.instr is slot.instr:
                            entry.done   = True
                            entry.result = slot.result
                            break
                else:
                    still_busy.append(slot)
            self.in_flight = still_busy

            # ── 2. Commit (in-order from ROB head) ─────────
            committed = 0
            while self.rob and self.rob[0].done and committed < self.width:
                entry = self.rob.popleft()
                instr = entry.instr
                if instr.op in (OpType.ALU, OpType.MUL):
                    self.rf.write(instr.rd, entry.result)
                elif instr.op == OpType.LOAD:
                    addr = self.mem_read(entry.result)  # result holds addr
                    val  = self.mem_read(entry.result)
                    self.rf.write(instr.rd, val)
                elif instr.op == OpType.STORE:
                    self.mem_write(entry.result, self.rf.read(instr.rs2))
                # Clear rename if this ROB entry was the producer
                if instr.rd != 0 and self.rename[instr.rd] == id(entry):
                    self.rename[instr.rd] = None
                self.instr_retired += 1
                committed += 1
                self.log.append({
                    "cycle": self.cycle,
                    "pc":    entry.pc,
                    "instr": str(instr),
                    "mode":  "commit"
                })

            # ── 3. Issue from IQ to execution ───────────────
            newly_executing = []
            remaining_iq    = []
            exec_slots_used = 0

            # Refresh readiness using forwarding bus
            for iq_entry in self.iq:
                if not iq_entry["rs1_ready"]:
                    r, v = self._resolve_src(iq_entry["instr"].rs1)
                    if r:
                        iq_entry["rs1_ready"] = True
                        iq_entry["rs1_val"]   = v
                if not iq_entry["rs2_ready"]:
                    r, v = self._resolve_src(iq_entry["instr"].rs2)
                    if r:
                        iq_entry["rs2_ready"] = True
                        iq_entry["rs2_val"]   = v

            for iq_entry in self.iq:
                if exec_slots_used >= self.width:
                    remaining_iq.append(iq_entry)
                    continue
                if iq_entry["rs1_ready"] and iq_entry["rs2_ready"]:
                    instr  = iq_entry["instr"]
                    result = 0
                    if instr.op in (OpType.ALU, OpType.MUL):
                        # Patch rf temporarily for execute_alu
                        self.rf.regs[instr.rs1] = iq_entry["rs1_val"]
                        self.rf.regs[instr.rs2] = iq_entry["rs2_val"]
                        result = self.execute_alu(instr)
                    elif instr.op == OpType.LOAD:
                        result = iq_entry["rs1_val"] + instr.imm  # addr
                    slot = PipelineSlot(
                        instr=instr,
                        pc=iq_entry["pc"],
                        cycles_left=LATENCY[instr.op],
                        rd=instr.rd,
                        result=result,
                        issued_cycle=self.cycle,
                    )
                    slot.rob_entry_id = iq_entry["rob_idx"]
                    newly_executing.append(slot)
                    exec_slots_used += 1
                else:
                    remaining_iq.append(iq_entry)

            self.in_flight.extend(newly_executing)
            self.iq = remaining_iq

            # ── 4. Fetch + Rename + IQ Dispatch ────────────
            fetched = 0
            while (fetched < self.width and
                   self.pc < len(self.program) and
                   len(self.rob) < self.ROB_SIZE and
                   len(self.iq)  < self.IQ_SIZE):

                instr = self.program[self.pc]

                # Branch prediction
                predicted_taken = False
                if instr.op == OpType.BRANCH:
                    predicted_taken = self.predictor.predict(self.pc)
                    # Check actual outcome (resolve speculatively here for simplicity)
                    rs1 = self.rf.read(instr.rs1)
                    rs2 = self.rf.read(instr.rs2)
                    actual_taken = (instr.mnem == "beq" and rs1 == rs2) or \
                                   (instr.mnem == "bne" and rs1 != rs2)
                    self.predictor.update(self.pc, actual_taken)
                    if predicted_taken != actual_taken:
                        self.branch_mispredicts += 1
                        # Flush IQ and in-flight (simplified recovery)
                        self.iq       = []
                        self.in_flight = []
                        self.pc = self.pc + instr.imm if actual_taken else self.pc + 1
                        self.instr_retired += 1
                        fetched += 1
                        break
                    else:
                        self.pc = self.pc + instr.imm if actual_taken else self.pc + 1
                        self.instr_retired += 1
                        fetched += 1
                        continue

                # Add to ROB
                rob_entry = self._add_to_rob(instr, self.pc)

                # Register renaming for destination
                if instr.rd != 0:
                    self.rename[instr.rd] = id(rob_entry)

                # Resolve sources
                rs1_ready, rs1_val = self._resolve_src(instr.rs1)
                rs2_ready, rs2_val = self._resolve_src(instr.rs2)

                # Mark NOP / STORE as done immediately (no writeback needed)
                if instr.op in (OpType.NOP,):
                    rob_entry.done = True

                self.iq.append({
                    "instr":     instr,
                    "pc":        self.pc,
                    "rs1_ready": rs1_ready,
                    "rs2_ready": rs2_ready,
                    "rs1_val":   rs1_val,
                    "rs2_val":   rs2_val,
                    "rob_idx":   id(rob_entry),
                })

                self.pc    += 1
                fetched    += 1

        return self.stats()


# needed for type hint in simulator.py import
from typing import Tuple
