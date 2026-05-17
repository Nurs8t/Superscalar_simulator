import sys
import json
from simulator    import InOrderSuperscalar
from ooo_scheduler import OutOfOrderSuperscalar
from benchmarks   import BENCHMARKS, compute_ideal_ilp, print_comparison


def run_benchmark(name: str, verbose: bool = False):
    program = BENCHMARKS[name]
    ideal   = compute_ideal_ilp(program)

    configs = [
        InOrderSuperscalar(list(program),  width=2),
        InOrderSuperscalar(list(program),  width=4),
        OutOfOrderSuperscalar(list(program), width=2),
        OutOfOrderSuperscalar(list(program), width=4),
    ]

    results = []
    for sim in configs:
        r = sim.run()
        results.append(r)
        if verbose:
            print(f"\n[{r['name']}] commit log (last 5):")
            for entry in sim.log[-5:]:
                print(f"  cycle={entry['cycle']:3d}  {entry['instr']}")

    print(f"\n{'─'*70}")
    print(f"  Benchmark: {name}   ({len(program)} instructions)")
    print_comparison(results, ideal)
    return results, ideal


def run_all():
    all_data = {}
    for bname in BENCHMARKS:
        results, ideal = run_benchmark(bname, verbose=False)
        all_data[bname] = {"results": results, "ideal": ideal}

    # Summary: IPC across all benchmarks
    print("\n" + "="*70)
    print("  IPC SUMMARY  (higher = better)")
    print("="*70)
    header = f"{'Benchmark':<22}"
    for cfg in ["InOrder-2wide","InOrder-4wide","OoO-2wide","OoO-4wide","Ideal"]:
        header += f" {cfg:>12}"
    print(header)
    print("-"*70)
    for bname, data in all_data.items():
        row = f"{bname:<22}"
        for r in data["results"]:
            row += f" {r['IPC']:>12.3f}"
        row += f" {data['ideal']['ideal_ipc']:>12.3f}"
        print(row)
    print("="*70)

    # Save JSON for optional plotting
    with open("results.json", "w") as f:
        json.dump(all_data, f, indent=2)
    print("\nResults saved to results.json")


def run_single(bench_name: str):
    if bench_name not in BENCHMARKS:
        print(f"Unknown benchmark: {bench_name}")
        print(f"Available: {list(BENCHMARKS.keys())}")
        sys.exit(1)
    run_benchmark(bench_name, verbose=True)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Superscalar Simulator — Topic 5")
        print("Usage:")
        print("  python main.py              # run all benchmarks")
        print("  python main.py <benchmark>  # run one benchmark verbosely")
        print(f"\nAvailable benchmarks: {list(BENCHMARKS.keys())}\n")
        run_all()
    else:
        run_single(sys.argv[1])
