class Instruction:
    def __init__(self, op, dest, src1, src2, id):
        self.id = id
        self.op = op
        self.dest = dest
        self.src1 = src1
        self.src2 = src2
        self.iss = 0
        self.read = 0
        self.exe = 0
        self.wb = 0
        self.ex_start = 0
        self.raw_stall = 0
        self.waw_stall = 0
        self.war_stall = 0
        self.struct_stall = 0
        self.cdb_stall = 0
        self.timeline = {}

def parse_code(code_text):
    """Parse MIPS64 assembly code, skipping .data section, directives, labels, and syscall."""
    lines = code_text.strip().split('\n')
    instructions = []
    idx = 1
    in_data = False
    for line in lines:
        line = line.split('#')[0].strip()
        if not line:
            continue
        # Handle section directives
        if line.startswith('.data'):
            in_data = True
            continue
        if line.startswith('.text'):
            in_data = False
            continue
        if in_data:
            continue
        # Skip assembler directives and labels
        if line.startswith('.'):
            continue
        if line.endswith(':'):
            continue
        # Remove label prefix if label is on same line as instruction
        if ':' in line:
            line = line.split(':', 1)[1].strip()
            if not line:
                continue
        # Skip syscall
        if line.lower().startswith('syscall'):
            continue
        parts = line.replace(',', ' ').split()
        op = parts[0]
        dest = parts[1] if len(parts) > 1 else None
        src1 = parts[2] if len(parts) > 2 else None
        src2 = parts[3] if len(parts) > 3 else None
        # Handle memory operands like 0($s0) -> extract register
        if op in ["lwc1", "ld", "lw", "l.d", "l.s"] and src1 and '(' in src1:
            base_reg = src1.split('(')[1].replace(')', '')
            src1 = base_reg
            src2 = None
        if op in ["swc1", "sw", "sd", "s.d", "s.s"] and src1 and '(' in src1:
            base_reg = src1.split('(')[1].replace(')', '')
            src1 = base_reg
            src2 = None
        instructions.append(Instruction(op, dest, src1, src2, idx))
        idx += 1
    return instructions

def get_unit(op):
    if op in ["add.d", "sub.d", "add.s", "sub.s"]: return "Add"
    if op in ["mul.d", "mul.s"]: return "Mult"
    if op in ["div.d", "div.s"]: return "Div"
    if op in ["lwc1", "ld", "lw", "l.d", "l.s"]: return "Load"
    if op in ["swc1", "sw", "sd", "s.d", "s.s"]: return "Store"
    return "Int"


# ---------------------------------------------------------------------------
# TOMASULO ALGORITHM
# ---------------------------------------------------------------------------
# Model:
#   - Issue: in-order, 1 per cycle. Requires a free reservation station (RS).
#     An instruction issued in cycle N cannot start execution until cycle N+1
#     at the earliest.
#   - Execute: out-of-order. Starts the cycle AFTER all source operands are
#     available (i.e., the cycle after the producer writes on the CDB).
#     Execution takes `latency` cycles.  The last cycle of execution is also
#     the Write-Result cycle (the result is broadcast on the CDB at the END
#     of the last execution cycle).
#   - Write Result (CDB): Only `cdb_limit` results can be broadcast per cycle.
#     If there is a conflict, the OLDEST instruction wins.
#   - A reservation station is freed when its instruction writes its result.
# ---------------------------------------------------------------------------

def simulate_tomasulo(code_text, rs_limits, latencies, cdb_limit=1):
    insts = parse_code(code_text)
    if not insts:
        return insts
    clock = 0
    issue_idx = 0

    while True:
        clock += 1
        if clock > 1000:
            break

        # ---------- PHASE 1: Try to ISSUE the next instruction ----------
        if issue_idx < len(insts):
            i = insts[issue_idx]
            # Can issue if: previous instruction was issued in a strictly earlier cycle
            can_issue = (issue_idx == 0) or (insts[issue_idx - 1].iss > 0 and insts[issue_idx - 1].iss < clock)
            if can_issue:
                utype = get_unit(i.op)
                rs_limit = rs_limits.get(utype, 1)
                # Count active RS entries for this unit type (issued but not yet written)
                # An instruction that writes THIS cycle still occupies the RS at the
                # start of the cycle, so it counts as active for issue purposes.
                active = sum(1 for j in insts if j.id != i.id and get_unit(j.op) == utype and j.iss > 0 and j.wb == 0)
                if active >= rs_limit:
                    i.struct_stall += 1
                    i.timeline[clock] = "-"
                else:
                    i.iss = clock
                    i.timeline[clock] = "D/E"
                    issue_idx += 1

        # ---------- PHASE 2: Try to start / continue EXECUTION ----------
        for i in insts:
            if i.iss == 0 or i.iss == clock:
                continue  # not yet issued, or just issued this cycle
            if i.exe > 0 or i.wb > 0:
                continue  # already finished execution or written

            if i.ex_start == 0:
                # Check RAW: all producers must have written (wb > 0)
                raw = False
                for j in insts:
                    if j.id >= i.id:
                        continue
                    if j.dest and (j.dest == i.src1 or j.dest == i.src2):
                        if j.wb == 0:
                            raw = True
                            break
                if raw:
                    i.raw_stall += 1
                    i.timeline[clock] = "-"
                else:
                    # Start execution
                    i.ex_start = clock
                    utype = get_unit(i.op)
                    lat = latencies.get(utype, 1)
                    i.timeline[clock] = "X"
                    if lat <= 1:
                        i.exe = clock  # finishes this cycle
            else:
                # Continue execution
                utype = get_unit(i.op)
                lat = latencies.get(utype, 1)
                i.timeline[clock] = "X"
                if clock - i.ex_start + 1 >= lat:
                    i.exe = clock  # execution complete

        # ---------- PHASE 3: WRITE RESULT on CDB ----------
        # Collect all instructions that finished execution this cycle or earlier
        # and haven't written yet.  Oldest-first priority.
        candidates = [i for i in insts if i.exe > 0 and i.wb == 0]
        candidates.sort(key=lambda x: x.id)
        writes_this_cycle = 0
        for i in candidates:
            if writes_this_cycle >= cdb_limit:
                if i.exe == clock:
                    # Just finished, will try next cycle
                    pass
                else:
                    i.cdb_stall += 1
                    i.timeline[clock] = "-"
                break  # remaining candidates also stall but we mark only oldest waiting
            # Write result
            i.wb = clock
            i.timeline[clock] = "W"
            writes_this_cycle += 1
        # Mark remaining candidates as CDB stall
        for i in candidates:
            if i.wb == 0 and i.exe > 0 and i.exe < clock:
                i.cdb_stall += 1
                if clock not in i.timeline or i.timeline[clock] == "X":
                    i.timeline[clock] = "-"

        # Check termination
        if all(i.wb > 0 for i in insts):
            break

    return insts


# ---------------------------------------------------------------------------
# SCOREBOARD ALGORITHM
# ---------------------------------------------------------------------------
# Model (CDC 6600 style):
#   - Issue: in-order, 1 per cycle.  Requires a free functional unit (FU) AND
#     no WAW hazard (no active instruction writing to the same dest register).
#     Issue and Read-Operands cannot happen in the same cycle.
#   - Read Operands: wait until all source operands are available (RAW check).
#     An operand is available when the instruction that writes it has reached
#     Write-Result.  In the scoreboard, the consumer can read in the SAME
#     cycle the producer writes (if no WAR blocks the write).
#     Reading takes 1 cycle.
#   - Execute: starts the cycle after Read-Operands.  Takes `latency` cycles.
#   - Write Result: check WAR hazard — cannot write if an earlier instruction
#     (that has been issued but has NOT YET read its operands) reads the
#     destination register.  Takes 1 cycle if not blocked.
#   - A functional unit is freed after Write Result.
# ---------------------------------------------------------------------------

def simulate_scoreboard(code_text, units, latencies):
    insts = parse_code(code_text)
    if not insts:
        return insts
    clock = 0
    issue_idx = 0

    while True:
        clock += 1
        if clock > 1000:
            break

        # Process stages: EX first, then WB (so W can happen same cycle as
        # last exec), then RO, then ISS.
        # Model:
        #   Issue (1 cycle) -> Read Operands (1 cycle) -> Execute (lat cycles)
        #   Write Result = last cycle of execution (merged, no extra cycle).
        #   WAR hazard can delay the write.
        #   No same-cycle forwarding: RO reads the cycle AFTER producer writes.
        #   FU freed at Write Result; new instruction can issue same cycle.

        # ---------- PHASE 3: EXECUTION ----------
        for i in insts:
            if i.read > 0 and i.read < clock and i.exe == 0 and i.wb == 0:
                utype = get_unit(i.op)
                lat = latencies.get(utype, 1)
                # Execution starts cycle after RO, takes `lat` cycles.
                # ExEnd = read + lat
                i.timeline[clock] = "X"
                if clock >= i.read + lat:
                    i.exe = clock

        # ---------- PHASE 2: WRITE RESULT (= last exec cycle) ----------
        for i in insts:
            if i.exe > 0 and i.wb == 0:
                # Execution finished (possibly this cycle). Check WAR.
                war = False
                for j in insts:
                    if j.id < i.id and j.iss > 0 and j.read == 0:
                        if j.src1 == i.dest or j.src2 == i.dest:
                            war = True
                            break
                if war:
                    i.war_stall += 1
                    i.timeline[clock] = "-"
                else:
                    i.wb = clock
                    i.timeline[clock] = "W"

        # ---------- PHASE 1b: READ OPERANDS ----------
        for i in insts:
            if i.iss > 0 and i.iss < clock and i.read == 0:
                # Check RAW: source operands available when producer has
                # completed Write Result.  NO same-cycle forwarding: the
                # consumer can read only the cycle AFTER the producer writes.
                raw = False
                for j in insts:
                    if j.id == i.id:
                        continue
                    if j.dest and (j.dest == i.src1 or j.dest == i.src2):
                        if j.iss > 0 and (j.wb == 0 or j.wb == clock):
                            raw = True
                            break
                if raw:
                    i.raw_stall += 1
                    i.timeline[clock] = "-"
                else:
                    i.read = clock
                    i.timeline[clock] = "LO"

        # ---------- PHASE 1a: ISSUE ----------
        if issue_idx < len(insts):
            i = insts[issue_idx]
            can_issue = (issue_idx == 0) or (insts[issue_idx - 1].iss > 0 and insts[issue_idx - 1].iss < clock)
            if can_issue:
                utype = get_unit(i.op)
                num_units = units.get(utype, 1)

                # FU freed when wb is set.  Since WB phase runs before ISS,
                # an instruction that writes THIS cycle has already freed
                # its FU, so it does NOT count as active.
                active = sum(1 for j in insts if j.id != i.id
                             and get_unit(j.op) == utype
                             and j.iss > 0 and j.wb == 0)

                # WAW: active instruction writing to the same dest?
                waw = False
                for j in insts:
                    if j.id < i.id and j.iss > 0 and j.wb == 0:
                        if j.dest and j.dest == i.dest:
                            waw = True
                            break

                if active >= num_units:
                    i.struct_stall += 1
                    i.timeline[clock] = "-"
                elif waw:
                    i.waw_stall += 1
                    i.timeline[clock] = "-"
                else:
                    i.iss = clock
                    i.timeline[clock] = "D/E"
                    issue_idx += 1

        # Check termination
        if all(i.wb > 0 for i in insts):
            break

    return insts
