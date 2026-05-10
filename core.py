class Instruction:
    def __init__(self, op, dest, src1, src2, id):
        self.id = id
        self.op = op
        self.dest = dest
        self.src1 = src1
        self.src2 = src2
        # Execution stages
        self.iss = 0
        self.read = 0
        self.exe = 0
        self.wb = 0
        self.ex_start = 0
        # Stalls tracking
        self.raw_stall = 0
        self.waw_stall = 0
        self.war_stall = 0
        self.struct_stall = 0
        self.cdb_stall = 0
        self.timeline = {}  # Cycle -> Stage string


def parse_code(code_text):
    """
    Parses a simple assembly text into Instruction objects.
    Format: OP DEST, SRC1, SRC2  (commas optional)
    """
    lines = code_text.strip().split("\n")
    instructions = []
    idx = 1
    for line in lines:
        line = line.split("#")[0].strip()  # remove comments
        if not line or line.endswith(":"):
            continue  # skip empty lines and labels

        parts = line.replace(",", " ").split()
        op = parts[0]
        dest = parts[1] if len(parts) > 1 else None
        src1 = parts[2] if len(parts) > 2 else None
        src2 = parts[3] if len(parts) > 3 else None

        # very basic normalization
        if op == "lwc1" and src1 and "(" in src1:
            # lwc1 $f0, 0($s0) -> dest=$f0, src1=$s0
            src1 = src1.split("(")[1].replace(")", "")
            src2 = None

        instructions.append(Instruction(op, dest, src1, src2, idx))
        idx += 1
    return instructions


def get_unit(op):
    if op in ["add.d", "sub.d", "add.s", "sub.s"]:
        return "Add"
    if op in ["mul.d", "mul.s"]:
        return "Mult"
    if op in ["div.d", "div.s"]:
        return "Div"
    if op in ["lwc1", "ld", "lw"]:
        return "Load"
    return "Int"


def simulate_scoreboard(code_text, units, latencies):
    insts = parse_code(code_text)
    clock = 1
    issue_idx = 0

    while True:
        if len(insts) > 0 and all(i.wb > 0 for i in insts):
            break
        if clock > 1000:  # safety break
            break

        for i in insts:
            if i.wb > 0:
                continue

            if i.exe > 0 and i.wb == 0:
                war = False
                for j in insts:
                    if (
                        j.id < i.id
                        and j.iss > 0
                        and j.read == 0
                        and (j.src1 == i.dest or j.src2 == i.dest)
                    ):
                        war = True
                if war:
                    i.war_stall += 1
                    i.timeline[clock] = "sWAR"
                else:
                    i.wb = clock
                    i.timeline[clock] = "W"
                continue

            if i.read > 0 and i.exe == 0:
                op_type = get_unit(i.op)
                lat = latencies.get(op_type, 1)
                # Ensure Scoreboard specific behavior matching class theory
                if op_type == "Load":
                    lat = 1
                i.timeline[clock] = "X"
                if clock - i.read == lat:
                    i.exe = clock
                continue

            if i.iss > 0 and i.read == 0:
                raw = False
                for j in insts:
                    if (
                        j.id < i.id
                        and j.dest
                        and (j.dest == i.src1 or j.dest == i.src2)
                    ):
                        if j.wb == 0:
                            raw = True
                if raw:
                    i.raw_stall += 1
                    i.timeline[clock] = "sRAW"
                else:
                    i.read = clock
                    i.timeline[clock] = "LO"
                continue

        if issue_idx < len(insts):
            i = insts[issue_idx]
            if issue_idx == 0 or (
                insts[issue_idx - 1].iss > 0 and insts[issue_idx - 1].iss < clock
            ):
                utype = get_unit(i.op)
                eff_units = units.get(utype, 1)
                if utype == "Load":
                    eff_units = 1  # Force 1 unit for Scoreboard Load matching theory

                active = sum(
                    1
                    for j in insts
                    if get_unit(j.op) == utype
                    and j.iss > 0
                    and j.wb == 0
                    and j.timeline.get(clock) != "W"
                )

                waw = False
                for j in insts:
                    if (
                        j.id < i.id
                        and j.iss > 0
                        and j.wb == 0
                        and j.dest
                        and j.dest == i.dest
                    ):
                        waw = True

                if waw:
                    i.waw_stall += 1
                    i.timeline[clock] = "sWAW"
                elif active >= eff_units:
                    i.struct_stall += 1
                    i.timeline[clock] = "sSTR"
                else:
                    i.iss = clock
                    i.timeline[clock] = "D/E"
                    issue_idx += 1

        clock += 1

    return insts


def simulate_tomasulo(code_text, rs_limits, latencies, cdb_limit=2):
    insts = parse_code(code_text)
    clock = 1
    issue_idx = 0

    while True:
        if len(insts) > 0 and all(i.wb > 0 for i in insts):
            break
        if clock > 1000:
            break

        writes_this_cycle = 0

        for i in insts:
            if i.wb > 0:
                continue

            if i.exe > 0 and i.wb == 0:
                if writes_this_cycle < cdb_limit:
                    i.wb = clock
                    i.timeline[clock] = "W"
                    writes_this_cycle += 1
                else:
                    i.cdb_stall += 1
                    i.timeline[clock] = "sCDB"
                continue

            if i.ex_start > 0 and i.exe == 0:
                op_type = get_unit(i.op)
                lat = latencies.get(op_type, 1)
                i.timeline[clock] = "X"
                if clock - i.ex_start == lat - 1:
                    i.exe = clock
                continue

            if i.iss > 0 and i.ex_start == 0:
                raw = False
                for j in insts:
                    if (
                        j.id < i.id
                        and j.dest
                        and (j.dest == i.src1 or j.dest == i.src2)
                    ):
                        if j.wb == 0 or j.timeline.get(clock) == "W":
                            raw = True
                if raw:
                    i.raw_stall += 1
                    i.timeline[clock] = "sRAW"
                else:
                    i.ex_start = clock
                    i.timeline[clock] = "X"
                    op_type = get_unit(i.op)
                    lat = latencies.get(op_type, 1)
                    if lat == 1:
                        i.exe = clock
                continue

        if issue_idx < len(insts):
            i = insts[issue_idx]
            if issue_idx == 0 or (
                insts[issue_idx - 1].iss > 0 and insts[issue_idx - 1].iss < clock
            ):
                utype = get_unit(i.op)
                active = sum(
                    1
                    for j in insts
                    if get_unit(j.op) == utype
                    and j.iss > 0
                    and j.wb == 0
                    and j.timeline.get(clock) != "W"
                )

                if active >= rs_limits.get(utype, 1):
                    i.struct_stall += 1
                    i.timeline[clock] = "sSTR"
                else:
                    i.iss = clock
                    i.timeline[clock] = "D/E"
                    issue_idx += 1

        clock += 1

    return insts


def simulate_tomasulo(code_text, rs_limits, latencies, cdb_limit=2):
    insts = parse_code(code_text)
    clock = 1
    issue_idx = 0

    while True:
        if len(insts) > 0 and all(i.wb > 0 for i in insts):
            break
        if clock > 1000:
            break

        # 3. Write Result
        writes_this_cycle = 0
        for i in insts:
            if i.exe > 0 and i.exe < clock and i.wb == 0:
                if writes_this_cycle < cdb_limit:
                    i.wb = clock
                    writes_this_cycle += 1
                else:
                    i.cdb_stall += 1

        # 2. Execute
        for i in insts:
            if i.iss > 0 and i.iss < clock and i.wb == 0:
                if i.ex_start == 0:
                    raw = False
                    for j in insts:
                        if (
                            j.id < i.id
                            and j.dest
                            and (j.dest == i.src1 or j.dest == i.src2)
                        ):
                            if j.wb == 0:
                                raw = True
                    if not raw:
                        i.ex_start = clock

                if i.ex_start > 0 and i.exe == 0:
                    op_type = get_unit(i.op)
                    lat = latencies.get(op_type, 1)
                    if clock - i.ex_start == lat - 1:
                        i.exe = clock

        # 1. Issue
        if issue_idx < len(insts):
            i = insts[issue_idx]
            utype = get_unit(i.op)
            active = sum(
                1 for j in insts if get_unit(j.op) == utype and j.iss > 0 and j.wb == 0
            )

            if active < rs_limits.get(utype, 1):
                i.iss = clock
                issue_idx += 1

        clock += 1

    return insts
