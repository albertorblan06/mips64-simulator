import tkinter as tk
from tkinter import ttk
from core import simulate_scoreboard, simulate_tomasulo


class SimulatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MIPS64 Dynamic Simulator (Scoreboard & Tomasulo)")
        self.root.geometry("1100x700")

        # Top Frame: Code and Config
        top_frame = tk.Frame(root)
        top_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Code Editor
        code_frame = tk.LabelFrame(top_frame, text="MIPS64 Assembly Code")
        code_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        self.code_text = tk.Text(code_frame, width=40, font=("Courier", 12))
        self.code_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        default_code = """lui $s0, 0x1001
lwc1 $f0, 0($s0)
lwc1 $f2, 8($s0)
add.d $f4, $f0, $f2
sub.d $f6, $f0, $f2
mul.d $f8, $f4, $f6
div.d $f10, $f8, $f2
add.d $f12, $f6, $f10
mul.d $f14, $f4, $f8
mul.d $f16, $f6, $f12"""
        self.code_text.insert(tk.END, default_code)

        # Config Panel
        config_frame = tk.LabelFrame(
            top_frame, text="Configuration (Units / RS limits & Latencies)"
        )
        config_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5)

        self.configs = {}
        row = 0
        tk.Label(config_frame, text="Unit/Op").grid(row=row, column=0, padx=5, pady=5)
        tk.Label(config_frame, text="Count/RS Limit").grid(
            row=row, column=1, padx=5, pady=5
        )
        tk.Label(config_frame, text="Latency").grid(row=row, column=2, padx=5, pady=5)

        row += 1
        self.add_config_row(config_frame, "Int", row, count=1, lat=1)
        row += 1
        self.add_config_row(config_frame, "Add", row, count=2, lat=2)
        row += 1
        self.add_config_row(config_frame, "Mult", row, count=2, lat=4)
        row += 1
        self.add_config_row(config_frame, "Div", row, count=1, lat=7)
        row += 1
        self.add_config_row(
            config_frame, "Load", row, count=2, lat=2
        )  # Default Load config

        # Buttons
        btn_frame = tk.Frame(config_frame)
        btn_frame.grid(row=row + 1, column=0, columnspan=3, pady=20)

        tk.Button(
            btn_frame,
            text="Run Scoreboard",
            command=self.run_scoreboard,
            bg="lightblue",
        ).pack(side=tk.LEFT, padx=5)
        tk.Button(
            btn_frame, text="Run Tomasulo", command=self.run_tomasulo, bg="lightgreen"
        ).pack(side=tk.LEFT, padx=5)

        # Bottom Frame: Timeline Table
        bottom_frame = tk.LabelFrame(root, text="Cycle Timeline")
        bottom_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.tree = ttk.Treeview(bottom_frame)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar_y = ttk.Scrollbar(
            bottom_frame, orient=tk.VERTICAL, command=self.tree.yview
        )
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar_y.set)

        scrollbar_x = ttk.Scrollbar(
            bottom_frame, orient=tk.HORIZONTAL, command=self.tree.xview
        )
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.configure(xscrollcommand=scrollbar_x.set)

    def add_config_row(self, parent, name, row, count, lat):
        tk.Label(parent, text=name).grid(row=row, column=0)

        count_var = tk.StringVar(value=str(count))
        e1 = tk.Entry(parent, textvariable=count_var, width=5)
        e1.grid(row=row, column=1)

        lat_var = tk.StringVar(value=str(lat))
        e2 = tk.Entry(parent, textvariable=lat_var, width=5)
        e2.grid(row=row, column=2)

        self.configs[name] = {"count": count_var, "lat": lat_var}

    def get_configs(self):
        units = {}
        latencies = {}
        for k, v in self.configs.items():
            units[k] = int(v["count"].get())
            latencies[k] = int(v["lat"].get())
        return units, latencies

    def run_scoreboard(self):
        code = self.code_text.get("1.0", tk.END)
        units, latencies = self.get_configs()
        insts = simulate_scoreboard(code, units, latencies)
        self.render_table(insts, algo="scoreboard")

    def run_tomasulo(self):
        code = self.code_text.get("1.0", tk.END)
        rs_limits, latencies = self.get_configs()
        insts = simulate_tomasulo(code, rs_limits, latencies)
        self.render_table(insts, algo="tomasulo")

    def render_table(self, insts, algo):
        # Clear tree
        self.tree.delete(*self.tree.get_children())
        if not insts:
            return

        max_cycle = max(i.wb for i in insts) if any(i.wb > 0 for i in insts) else 0
        if max_cycle == 0:
            return

        cols = ["Instruction"] + [str(c) for c in range(1, max_cycle + 1)]
        self.tree["columns"] = cols
        self.tree.column("#0", width=0, stretch=tk.NO)  # Hide default first col
        self.tree.heading("#0", text="")

        for c in cols:
            w = 120 if c == "Instruction" else 30
            self.tree.column(c, width=w, anchor=tk.CENTER)
            self.tree.heading(c, text=c)

        for i in insts:
            row_data = [f"{i.op} {i.dest or ''}"]
            for c in range(1, max_cycle + 1):
                cell = ""
                if algo == "scoreboard":
                    if c == i.iss:
                        cell = "D/E"
                    elif i.iss < c < i.read:
                        cell = "-"
                    elif c == i.read:
                        cell = "LO"
                    elif i.read < c <= i.exe:
                        cell = "X"
                    elif i.exe < c < i.wb:
                        cell = "-"
                    elif c == i.wb:
                        cell = "W"
                else:  # tomasulo
                    if c == i.iss:
                        cell = "D/E"
                    elif i.iss < c < i.ex_start:
                        cell = "-"
                    elif i.ex_start <= c <= i.exe:
                        cell = "X"
                    elif i.exe < c < i.wb:
                        cell = "-"
                    elif c == i.wb:
                        cell = "W"
                row_data.append(cell)
            self.tree.insert("", tk.END, values=row_data)


if __name__ == "__main__":
    root = tk.Tk()
    app = SimulatorApp(root)
    root.mainloop()
