
import json
import os
import sys

# Try matplotlib; fall back to ASCII art if not installed
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

RESULTS_FILE = "results.json"
OUT_DIR      = "plots"

CONFIGS      = ["InOrder-2wide", "InOrder-4wide", "OoO-2wide", "OoO-4wide"]
COLORS       = ["#4C72B0", "#55A868", "#C44E52", "#8172B2"]


def load_results() -> dict:
    if not os.path.exists(RESULTS_FILE):
        print(f"[ERROR] {RESULTS_FILE} not found. Run 'python main.py' first.")
        sys.exit(1)
    with open(RESULTS_FILE) as f:
        return json.load(f)


def plot_ipc_comparison(data: dict):
    """Bar chart: IPC per benchmark per configuration."""
    benchmarks = list(data.keys())
    n_bench    = len(benchmarks)
    n_cfg      = len(CONFIGS)
    bar_w      = 0.15
    x          = range(n_bench)

    fig, ax = plt.subplots(figsize=(12, 5))
    for ci, cfg in enumerate(CONFIGS):
        ipcs = []
        for bname in benchmarks:
            found = next((r for r in data[bname]["results"] if r["name"] == cfg), None)
            ipcs.append(found["IPC"] if found else 0)
        offset = (ci - n_cfg / 2 + 0.5) * bar_w
        ax.bar([xi + offset for xi in x], ipcs,
               width=bar_w, label=cfg, color=COLORS[ci], alpha=0.85)

    # Ideal IPC as scatter
    ideal_ipcs = [data[b]["ideal"]["ideal_ipc"] for b in benchmarks]
    ax.scatter(x, ideal_ipcs, marker="*", s=120, color="black",
               zorder=5, label="Ideal (oracle)")

    ax.set_xticks(list(x))
    ax.set_xticklabels(benchmarks, rotation=15, ha="right")
    ax.set_ylabel("IPC  (Instructions Per Cycle)")
    ax.set_title("Superscalar IPC — In-Order vs Out-of-Order vs Ideal")
    ax.legend(loc="upper right")
    ax.set_ylim(0, max(ideal_ipcs) * 1.4 + 0.5)
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    os.makedirs(OUT_DIR, exist_ok=True)
    path = f"{OUT_DIR}/ipc_comparison.png"
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    print(f"Saved: {path}")
    plt.close()


def plot_stalls(data: dict):
    """Stall cycles per benchmark, InOrder-2wide vs OoO-2wide."""
    benchmarks = list(data.keys())
    x = range(len(benchmarks))

    fig, ax = plt.subplots(figsize=(10, 4))
    for ci, cfg in enumerate(["InOrder-2wide", "OoO-2wide"]):
        stalls = []
        for bname in benchmarks:
            found = next((r for r in data[bname]["results"] if r["name"] == cfg), None)
            stalls.append(found["stall_cycles"] if found else 0)
        ax.bar([xi + ci * 0.35 for xi in x], stalls,
               width=0.35, label=cfg, color=COLORS[ci], alpha=0.85)

    ax.set_xticks([xi + 0.175 for xi in x])
    ax.set_xticklabels(benchmarks, rotation=15, ha="right")
    ax.set_ylabel("Stall cycles")
    ax.set_title("Stall Cycles: In-Order vs Out-of-Order")
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    path = f"{OUT_DIR}/stalls.png"
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    print(f"Saved: {path}")
    plt.close()


def ascii_bar(label: str, value: float, max_val: float, width: int = 40):
    filled = int(value / max_val * width)
    bar    = "█" * filled + "░" * (width - filled)
    print(f"  {label:<20} [{bar}]  {value:.3f}")


def ascii_summary(data: dict):
    """Fallback: print ASCII bar chart when matplotlib is unavailable."""
    print("\n" + "="*65)
    print("  IPC Comparison (ASCII chart)")
    for bname, bdata in data.items():
        print(f"\n  Benchmark: {bname}")
        all_ipcs = [r["IPC"] for r in bdata["results"]] + [bdata["ideal"]["ideal_ipc"]]
        max_ipc  = max(all_ipcs) or 1
        for r in bdata["results"]:
            ascii_bar(r["name"], r["IPC"], max_ipc)
        ascii_bar("Ideal", bdata["ideal"]["ideal_ipc"], max_ipc)
    print("="*65 + "\n")


def main():
    data = load_results()
    if HAS_MPL:
        plot_ipc_comparison(data)
        plot_stalls(data)
        print(f"\nPlots saved in ./{OUT_DIR}/")
    else:
        print("[WARNING] matplotlib not found — showing ASCII charts instead.")
        print("Install with: pip install matplotlib")
        ascii_summary(data)


if __name__ == "__main__":
    main()
