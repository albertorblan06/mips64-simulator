import tkinter as tk
from tkinter import ttk, font as tkfont
from core import simulate_scoreboard, simulate_tomasulo

# ──────────────────── colour palette ────────────────────
BG           = "#1e1e2e"   # main background
BG_SECONDARY = "#282840"   # panels / frames
BG_INPUT     = "#313150"   # text inputs
FG           = "#cdd6f4"   # primary text
FG_DIM       = "#7f849c"   # secondary text
ACCENT       = "#89b4fa"   # blue accent
ACCENT2      = "#a6e3a1"   # green accent
ACCENT3      = "#f38ba8"   # red/pink accent
BORDER       = "#45475a"   # subtle borders
YELLOW       = "#f9e2af"
MAUVE        = "#cba6f7"
PEACH        = "#fab387"

# Timeline cell colours
CLR_ISSUE = "#89b4fa"    # light blue  (D/E)
CLR_READ  = "#3b5998"    # dark blue   (LO)
CLR_EXEC  = "#f38ba8"    # red         (X)
CLR_WRITE = "#cba6f7"    # purple      (W)
CLR_STALL = "#45475a"    # grey        (stalls)
CLR_EMPTY = BG_SECONDARY


class SimulatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MIPS64 Pipeline Simulator")
        self.root.configure(bg=BG)
        self.root.geometry("1280x780")
        self.root.minsize(1000, 600)

        # ── Fonts ──
        self.title_font   = tkfont.Font(family="Helvetica Neue", size=16, weight="bold")
        self.heading_font = tkfont.Font(family="Helvetica Neue", size=11, weight="bold")
        self.body_font    = tkfont.Font(family="Menlo", size=11)
        self.small_font   = tkfont.Font(family="Helvetica Neue", size=10)
        self.stat_font    = tkfont.Font(family="Menlo", size=12, weight="bold")

        # ── Custom ttk style ──
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure(".", background=BG, foreground=FG, fieldbackground=BG_INPUT,
                             borderwidth=0)
        self.style.configure("TFrame", background=BG)
        self.style.configure("Secondary.TFrame", background=BG_SECONDARY)
        self.style.configure("TLabel", background=BG, foreground=FG)
        self.style.configure("Dim.TLabel", background=BG_SECONDARY, foreground=FG_DIM)
        self.style.configure("Accent.TLabel", background=BG, foreground=ACCENT,
                             font=self.heading_font)
        self.style.configure("TNotebook", background=BG, borderwidth=0)
        self.style.configure("TNotebook.Tab", background=BG_SECONDARY, foreground=FG,
                             padding=[14, 6])
        self.style.map("TNotebook.Tab",
                       background=[("selected", ACCENT)],
                       foreground=[("selected", BG)])
        self.style.configure("Horizontal.TScrollbar", background=BG_SECONDARY,
                             troughcolor=BG, borderwidth=0, arrowsize=0)
        self.style.configure("Vertical.TScrollbar", background=BG_SECONDARY,
                             troughcolor=BG, borderwidth=0, arrowsize=0)

        # ── Title bar ──
        title_bar = tk.Frame(root, bg=BG, height=50)
        title_bar.pack(fill=tk.X, padx=20, pady=(15, 5))
        tk.Label(title_bar, text="⚙  MIPS64 Pipeline Simulator", font=self.title_font,
                 bg=BG, fg=FG).pack(side=tk.LEFT)
        tk.Label(title_bar, text="Scoreboard & Tomasulo", font=self.small_font,
                 bg=BG, fg=FG_DIM).pack(side=tk.LEFT, padx=12, pady=4)

        # ── Main horizontal split ──
        main = tk.PanedWindow(root, orient=tk.HORIZONTAL, bg=BG, sashwidth=4,
                              sashrelief=tk.FLAT, bd=0)
        main.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        # ════════════════ LEFT: Code editor ════════════════
        left = self._card(main)
        main.add(left, width=420, stretch="never")

        tk.Label(left, text="Assembly Code", font=self.heading_font,
                 bg=BG_SECONDARY, fg=ACCENT).pack(anchor="w", padx=12, pady=(10, 4))

        code_frame = tk.Frame(left, bg=BORDER, bd=1)
        code_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.code_text = tk.Text(code_frame, wrap=tk.NONE, font=self.body_font,
                                 bg=BG_INPUT, fg=FG, insertbackground=FG,
                                 selectbackground=ACCENT, selectforeground=BG,
                                 relief=tk.FLAT, padx=8, pady=6, spacing1=2)
        self.code_text.pack(fill=tk.BOTH, expand=True)

        default_code = (
            "lui $s0, 0x1001\n"
            "lwc1 $f0, 0($s0)\n"
            "lwc1 $f2, 8($s0)\n"
            "add.d $f4, $f0, $f2\n"
            "sub.d $f6, $f0, $f2\n"
            "mul.d $f8, $f4, $f6\n"
            "div.d $f10, $f8, $f2\n"
            "add.d $f12, $f6, $f10\n"
            "mul.d $f14, $f4, $f8\n"
            "mul.d $f16, $f6, $f12"
        )
        self.code_text.insert(tk.END, default_code)

        # ════════════════ RIGHT: Config + Results ════════════════
        right = tk.Frame(main, bg=BG)
        main.add(right, stretch="always")

        # ── Config section ──
        cfg_row = tk.Frame(right, bg=BG)
        cfg_row.pack(fill=tk.X, pady=(0, 8))

        config_card = self._card(cfg_row)
        config_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        tk.Label(config_card, text="Configuration", font=self.heading_font,
                 bg=BG_SECONDARY, fg=ACCENT).grid(row=0, column=0, columnspan=3,
                                                    sticky="w", padx=12, pady=(10, 6))

        headers = ["Unit", "Count / RS", "Latency"]
        for c, h in enumerate(headers):
            tk.Label(config_card, text=h, font=self.small_font,
                     bg=BG_SECONDARY, fg=FG_DIM).grid(row=1, column=c, padx=8, pady=2)

        self.configs = {}
        units_data = [("Int", 1, 1), ("Add", 2, 2), ("Mult", 2, 4),
                      ("Div", 2, 7), ("Load", 2, 2), ("Store", 2, 1)]
        for idx, (name, cnt, lat) in enumerate(units_data):
            self._config_row(config_card, name, idx + 2, cnt, lat)

        cdb_row = len(units_data) + 2
        tk.Label(config_card, text="CDB Limit", font=self.small_font,
                 bg=BG_SECONDARY, fg=PEACH).grid(row=cdb_row, column=0, padx=8, pady=6,
                                                   sticky="w")
        self.cdb_var = tk.StringVar(value="1")
        self._styled_entry(config_card, self.cdb_var).grid(row=cdb_row, column=1, pady=6)

        # ── Buttons ──
        btn_card = self._card(cfg_row)
        btn_card.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 0))

        tk.Label(btn_card, text="Run", font=self.heading_font,
                 bg=BG_SECONDARY, fg=ACCENT).pack(padx=16, pady=(10, 8))

        self._action_button(btn_card, "▶  Scoreboard", ACCENT,
                            self.run_scoreboard).pack(padx=16, pady=4, fill=tk.X)
        self._action_button(btn_card, "▶  Tomasulo", ACCENT2,
                            self.run_tomasulo).pack(padx=16, pady=4, fill=tk.X)

        # ── Stats panel ──
        self.stats_card = self._card(btn_card)
        self.stats_card.pack(padx=10, pady=(12, 10), fill=tk.X)

        self.cycles_var = tk.StringVar(value="—")
        self.cpi_var    = tk.StringVar(value="—")
        self.insts_var  = tk.StringVar(value="—")
        self.raw_var    = tk.StringVar(value="0")
        self.waw_var    = tk.StringVar(value="0")
        self.war_var    = tk.StringVar(value="0")
        self.str_var    = tk.StringVar(value="0")
        self.cdb_s_var  = tk.StringVar(value="0")

        tk.Label(self.stats_card, text="Results", font=self.heading_font,
                 bg=BG_SECONDARY, fg=YELLOW).pack(anchor="w", padx=8, pady=(6, 2))

        stats_grid = tk.Frame(self.stats_card, bg=BG_SECONDARY)
        stats_grid.pack(fill=tk.X, padx=8, pady=(0, 8))

        self._stat_row(stats_grid, 0, "Cycles", self.cycles_var, ACCENT)
        self._stat_row(stats_grid, 1, "CPI",    self.cpi_var,    ACCENT)
        self._stat_row(stats_grid, 2, "Insts",  self.insts_var,  FG_DIM)
        self._stat_row(stats_grid, 3, "RAW",    self.raw_var,    ACCENT3)
        self._stat_row(stats_grid, 4, "WAW",    self.waw_var,    PEACH)
        self._stat_row(stats_grid, 5, "WAR",    self.war_var,    PEACH)
        self._stat_row(stats_grid, 6, "Struct", self.str_var,    MAUVE)
        self._stat_row(stats_grid, 7, "CDB",    self.cdb_s_var,  MAUVE)

        # ── Timeline (canvas-based) ──
        timeline_label = tk.Label(right, text="Cycle Timeline", font=self.heading_font,
                                  bg=BG, fg=ACCENT)
        timeline_label.pack(anchor="w", padx=4, pady=(4, 2))

        # Legend
        legend = tk.Frame(right, bg=BG)
        legend.pack(anchor="w", padx=4, pady=(0, 4))
        for label, color in [("D/E", CLR_ISSUE), ("LO", CLR_READ),
                              ("X", CLR_EXEC), ("W", CLR_WRITE), ("—", CLR_STALL)]:
            tk.Frame(legend, bg=color, width=14, height=14).pack(side=tk.LEFT, padx=(0, 3))
            tk.Label(legend, text=label, bg=BG, fg=FG_DIM,
                     font=self.small_font).pack(side=tk.LEFT, padx=(0, 10))

        tl_frame = tk.Frame(right, bg=BORDER, bd=1)
        tl_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        self.canvas = tk.Canvas(tl_frame, bg=BG_SECONDARY, highlightthickness=0)
        self.h_scroll = ttk.Scrollbar(tl_frame, orient=tk.HORIZONTAL,
                                       command=self.canvas.xview)
        self.v_scroll = ttk.Scrollbar(tl_frame, orient=tk.VERTICAL,
                                       command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.h_scroll.set,
                              yscrollcommand=self.v_scroll.set)

        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Shift-MouseWheel>", self._on_shift_mousewheel)

    # ──────────────── helpers ────────────────

    def _card(self, parent):
        """Rounded-ish card container."""
        f = tk.Frame(parent, bg=BG_SECONDARY, bd=0,
                     highlightbackground=BORDER, highlightthickness=1)
        return f

    def _styled_entry(self, parent, var, width=5):
        e = tk.Entry(parent, textvariable=var, width=width, font=self.body_font,
                     bg=BG_INPUT, fg=FG, insertbackground=FG,
                     relief=tk.FLAT, justify=tk.CENTER,
                     highlightbackground=BORDER, highlightthickness=1)
        return e

    def _config_row(self, parent, name, row, cnt, lat):
        tk.Label(parent, text=name, font=self.body_font,
                 bg=BG_SECONDARY, fg=FG).grid(row=row, column=0, padx=8, pady=3, sticky="w")
        cv = tk.StringVar(value=str(cnt))
        lv = tk.StringVar(value=str(lat))
        self._styled_entry(parent, cv).grid(row=row, column=1, padx=4, pady=3)
        self._styled_entry(parent, lv).grid(row=row, column=2, padx=4, pady=3)
        self.configs[name] = {"count": cv, "lat": lv}

    def _action_button(self, parent, text, color, command):
        btn = tk.Button(parent, text=text, font=self.heading_font,
                        bg=color, fg=BG, activebackground=FG, activeforeground=BG,
                        relief=tk.FLAT, cursor="hand2", padx=12, pady=6,
                        command=command)
        btn.bind("<Enter>", lambda e, b=btn, c=color: b.config(bg=FG))
        btn.bind("<Leave>", lambda e, b=btn, c=color: b.config(bg=c))
        return btn

    def _stat_row(self, parent, row, label, var, color):
        tk.Label(parent, text=label, font=self.small_font,
                 bg=BG_SECONDARY, fg=FG_DIM).grid(row=row, column=0, sticky="w", padx=2)
        tk.Label(parent, textvariable=var, font=self.small_font,
                 bg=BG_SECONDARY, fg=color).grid(row=row, column=1, sticky="e", padx=2)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(-1 * (event.delta // 120), "units")

    def _on_shift_mousewheel(self, event):
        self.canvas.xview_scroll(-1 * (event.delta // 120), "units")

    # ──────────────── config helpers ────────────────

    def get_configs(self):
        units, latencies = {}, {}
        for k, v in self.configs.items():
            units[k] = int(v["count"].get())
            latencies[k] = int(v["lat"].get())
        return units, latencies

    # ──────────────── simulation runners ────────────────

    def run_scoreboard(self):
        code = self.code_text.get("1.0", tk.END)
        units, latencies = self.get_configs()
        insts = simulate_scoreboard(code, units, latencies)
        self._show_results(insts)

    def run_tomasulo(self):
        code = self.code_text.get("1.0", tk.END)
        rs_limits, latencies = self.get_configs()
        try:
            cdb_limit = int(self.cdb_var.get())
        except Exception:
            cdb_limit = 1
        insts = simulate_tomasulo(code, rs_limits, latencies, cdb_limit=cdb_limit)
        self._show_results(insts)

    # ──────────────── results display ────────────────

    def _show_results(self, insts):
        if not insts or not any(i.wb > 0 for i in insts):
            return

        max_cycle = max(i.wb for i in insts)
        num_insts = len(insts)
        cpi = max_cycle / num_insts if num_insts else 0

        self.cycles_var.set(str(max_cycle))
        self.cpi_var.set(f"{cpi:.2f}")
        self.insts_var.set(str(num_insts))
        self.raw_var.set(str(sum(i.raw_stall for i in insts)))
        self.waw_var.set(str(sum(i.waw_stall for i in insts)))
        self.war_var.set(str(sum(i.war_stall for i in insts)))
        self.str_var.set(str(sum(i.struct_stall for i in insts)))
        self.cdb_s_var.set(str(sum(i.cdb_stall for i in insts)))

        self._draw_timeline(insts, max_cycle)

    def _cell_color(self, text):
        if text == "D/E": return CLR_ISSUE
        if text == "LO":  return CLR_READ
        if text == "X":   return CLR_EXEC
        if text == "W":   return CLR_WRITE
        if text == "-":   return CLR_STALL
        return CLR_EMPTY

    def _draw_timeline(self, insts, max_cycle):
        c = self.canvas
        c.delete("all")

        cell_w   = 36
        cell_h   = 26
        label_w  = 150
        header_h = 28
        pad      = 4

        total_w = label_w + (max_cycle * cell_w) + pad * 2
        total_h = header_h + len(insts) * cell_h + pad * 2

        c.configure(scrollregion=(0, 0, total_w, total_h))

        # Header row (cycle numbers)
        for cyc in range(1, max_cycle + 1):
            x = label_w + (cyc - 1) * cell_w + pad
            c.create_text(x + cell_w // 2, header_h // 2 + pad,
                          text=str(cyc), fill=FG_DIM, font=self.small_font)

        # Instruction rows
        for row, inst in enumerate(insts):
            y = header_h + row * cell_h + pad
            # Instruction label
            label = f"{inst.op} {inst.dest or ''}"
            c.create_text(pad + 6, y + cell_h // 2, text=label, anchor="w",
                          fill=FG, font=self.body_font)

            # Cells
            for cyc in range(1, max_cycle + 1):
                x = label_w + (cyc - 1) * cell_w + pad
                text = inst.timeline.get(cyc, "")
                bg = self._cell_color(text)

                if text:
                    c.create_rectangle(x + 1, y + 1, x + cell_w - 1, y + cell_h - 1,
                                       fill=bg, outline="", width=0)
                    # Text colour: dark on light cells, light on dark cells
                    fg = BG if bg != CLR_STALL else FG_DIM
                    display = text if text != "-" else "—"
                    c.create_text(x + cell_w // 2, y + cell_h // 2,
                                  text=display, fill=fg, font=self.small_font)

            # Subtle row separator
            sep_y = y + cell_h
            c.create_line(pad, sep_y, total_w - pad, sep_y, fill=BORDER, width=1)


if __name__ == "__main__":
    root = tk.Tk()
    app = SimulatorApp(root)
    root.mainloop()
