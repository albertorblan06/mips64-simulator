# MIPS64 Dynamic Simulator 🚀

![Python](https://img.shields.io/badge/Python-3.x-blue.svg)
![Tkinter](https://img.shields.io/badge/GUI-Tkinter-green.svg)
![Subject](https://img.shields.io/badge/Subject-Arquitectura%20de%20Computadores-orange)

A powerful, interactive Python-based desktop simulator for visualizing dynamic instruction scheduling using the **Scoreboard** and **Tomasulo** algorithms in a MIPS64 architecture.

This project was developed as part of the *Arquitectura de Computadores* course (2º Ingeniería de Computadores, URJC, Alberto Rodríguez Blanco).

## ✨ Features

- **Interactive GUI**: Built with Tkinter. Write your MIPS64 assembly directly into the editor and visualize the pipeline cycles immediately.
- **Scoreboard Algorithm**: Accurately simulates the stages of D/E (Issue), LO (Read Operands), X (Execution), and W (Write Result), dealing with RAW, WAW, and WAR hazards.
- **Tomasulo Algorithm**: Accurately simulates dynamic scheduling with implicit register renaming via Reservation Stations (RS).
- **Customizable Pipelines**: Modify the number of available Functional Units (or Reservation Stations limits) and execution Latencies dynamically from the UI.
- **Cycle-by-Cycle Gantt Chart**: Automatically generates a scrollable visual timeline mapping instructions against cycles (`D/E`, `LO`, `X`, `W`, and `-` for stalls).

## 🚀 How to Run

1. Ensure you have Python 3 installed. No external dependencies are strictly required since it relies on the standard `tkinter` library.
2. Clone this repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/mips64-simulator.git
   cd mips64-simulator
   ```
3. Run the GUI application:
   ```bash
   python3 app.py
   ```

## 🛠 Project Structure

- `app.py`: Contains the Tkinter GUI frontend logic and layout.
- `core.py`: Contains the actual simulation backend logic and MIPS parser for both Scoreboard and Tomasulo.

## 📝 Example Configuration

By default, the simulator provides a configuration matching the usual classroom exercises:
- **Int**: Latency 1, Limit 1
- **Add FP**: Latency 2, Limit 2
- **Mult FP**: Latency 4, Limit 2
- **Div FP**: Latency 7, Limit 1 (or 2 for Tomasulo RS)
- **Load/Store**: Latency 2, Limit 2

Simply click "Run Scoreboard" or "Run Tomasulo" to see the magic happen!

## 🎓 Academic Info
- **Student:** Alberto Rodríguez Blanco
- **Degree:** 2º Ingeniería de Computadores
- **University:** Universidad Rey Juan Carlos (URJC)
- **Year:** 2025-2026
