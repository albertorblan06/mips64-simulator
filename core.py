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

        # 4. Write Result
        for i in insts:
            if i.exe > 0 and i.exe < clock and i.wb == 0:
                war = False
                for j in insts:
                    if (
                        j.id < i.id
                        and j.iss > 0
                        and j.read == 0
                        and (j.src1 == i.dest or j.src2 == i.dest)
                    ):
                        war = True
                if not war:
                    i.wb = clock

        # 3. Execution
        for i in insts:
            if i.read > 0 and i.read < clock and i.exe == 0:
                op_type = get_unit(i.op)
                lat = latencies.get(op_type, 1)
                if clock - i.read == lat:
                    i.exe = clock

        # 2. Read Operands
        for i in insts:
            if i.iss > 0 and i.iss < clock and i.read == 0:
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
                    i.read = clock

        # 1. Issue
        if issue_idx < len(insts):
            i = insts[issue_idx]
            utype = get_unit(i.op)
            active = sum(
                1 for j in insts if get_unit(j.op) == utype and j.iss > 0 and j.wb == 0
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

            if active < units.get(utype, 1) and not waw:
                i.iss = clock
                issue_idx += 1

        clock += 1

    return insts


def simulate_tomasulo(code_text, rs_limits, latencies):
    insts = parse_code(code_text)
    clock = 1
    issue_idx = 0

    while True:
        if len(insts) > 0 and all(i.wb > 0 for i in insts):
            break
        if clock > 1000:
            break

        # 3. Write Result
        for i in insts:
            if i.exe > 0 and i.exe < clock and i.wb == 0:
                i.wb = clock

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
