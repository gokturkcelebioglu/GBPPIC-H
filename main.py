import argparse
import time
from pathlib import Path
from datetime import datetime
from typing import Callable
from read_dataset import read_dataset
from solvers import available_solvers, create_solver, check_feasibility
from models import Solution, Item
from constants import ALNS_PARAMS, RESULTS_FILE, SEED


def _import_pandas():
    try:
        import pandas as pd
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "pandas and openpyxl are required for Excel exports. "
            "Install dependencies with `pip install -r requirements.txt`."
        ) from exc
    return pd


def _run_solver_with_timing(solve_func: Callable[[], Solution]) -> tuple[Solution, float]:
    start_time = time.time()
    sol = solve_func()
    end_time = time.time()
    return sol, end_time - start_time

def _print_summary(path: str, n: int, sol: Solution, run_time: float, is_feasible: bool, violations, noncompulsory_count: int = 0):
    print(f"\nResults for {Path(path).name}")
    print(f"  n={n}")
    print(f"  Noncompulsory Items = {noncompulsory_count}")
    print(f"  Used Bins = {sol.used_bins}")
    print(f"  Best Objective = {sol.obj}")
    print(f"  Run Time = {run_time:.2f}s")
    print(f"  Feasible = {is_feasible}")
    if not is_feasible:
        print(f"  Feasibility Violations ({len(violations)}):")
        for violation in violations[:10]:
            print(f"    - {violation}")
        if len(violations) > 10:
            print(f"    ... and {len(violations) - 10} more violations")

def save_results(instance_name: str, algorithm: str, run_id: int, run_time: float, sol: Solution, bin_types: list = None, gap: float = None, mechanisms: dict = None, noncompulsory_count: int = 0):
    pd = _import_pandas()
    loaded_revenue = 0
    if sol.obj < float('inf'): # Check if a valid solution was found
        # Calculate revenue: obj = total_bin_cost - revenue, so revenue = total_bin_cost - obj
        if bin_types is not None:
            # Use actual bin costs
            cost_map = {bt.id: bt.cost for bt in bin_types}
            total_bin_cost = sum(cost_map.get(b.bin_type_id, 0) for b in sol.bins)
            loaded_revenue = total_bin_cost - sol.obj
        else:
            # Fallback: This shouldn't happen in normal usage since we always pass bin_types
            loaded_revenue = 0

    new_data = {
        "InstanceName": instance_name,
        "Algorithm": algorithm,
        "RunID": run_id,
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "RunTime_s": round(run_time, 2),
        "BestObj": sol.obj if sol.obj < float('inf') else "N/A",
        "UsedBins": sol.used_bins,
        "NoncompulsoryItems": noncompulsory_count,
        "LoadedRevenue": loaded_revenue,
        "CplexGap_pct": f"{gap:.2f}" if gap is not None else "N/A"
    }
    
    # All operators are always enabled for ALNS
    if mechanisms:  # ALNS solver
        # Set all to "Yes" since all operators are always enabled
        for col in ["Omega_d1", "Omega_d2", "Omega_d3", "Omega_d4",
                   "Omega_k1", "Omega_k2", "Omega_k3", "Omega_k4",
                   "Omega_plus1", "Omega_plus2", "Omega_plus3", "Omega_plus4",
                   "LS1", "LS2", "LS3", "LS4"]:
            new_data[col] = "Yes"
    else:
        # Set all to N/A for non-ALNS solvers
        for col in ["Omega_d1", "Omega_d2", "Omega_d3", "Omega_d4",
                   "Omega_k1", "Omega_k2", "Omega_k3", "Omega_k4",
                   "Omega_plus1", "Omega_plus2", "Omega_plus3", "Omega_plus4",
                   "LS1", "LS2", "LS3", "LS4"]:
            new_data[col] = "N/A"
    
    if RESULTS_FILE.exists():
        try:
            df = pd.read_excel(RESULTS_FILE)
            # Ensure all mechanism columns exist (for backward compatibility)
            mechanism_cols = ["Omega_d1", "Omega_d2", "Omega_d3", "Omega_d4", "Omega_k1", "Omega_k2", "Omega_k3", "Omega_k4",
                             "Omega_plus1", "Omega_plus2", "Omega_plus3", "Omega_plus4", "LS1", "LS2",
                             "LS3", "LS4"]
            for col in mechanism_cols:
                if col not in df.columns:
                    df[col] = "N/A"
            # Ensure NoncompulsoryItems column exists (for backward compatibility)
            if "NoncompulsoryItems" not in df.columns:
                df["NoncompulsoryItems"] = 0
        except Exception as e:
            print(f"Warning: Could not read {RESULTS_FILE}, creating new file. Error: {e}")
            df = pd.DataFrame(columns=list(new_data.keys()))
    else:
        df = pd.DataFrame(columns=list(new_data.keys()))

    new_df_row = pd.DataFrame([new_data])
    df = pd.concat([df, new_df_row], ignore_index=True)
    
    df.to_excel(RESULTS_FILE, index=False, engine='openpyxl')

def save_bin_results(sol: Solution, items_list: list[Item], solver_name: str, instance_name: str, bin_types: list = None):
    """Export bin results to Excel file with item details."""
    pd = _import_pandas()
    # Create results folder if it doesn't exist
    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)
    
    # Map solver name to solve type
    solve_type = "exact" if solver_name.lower() in ["cplex", "exact"] else "alns"
    
    # Get instance name without extension
    instance_base = Path(instance_name).stem
    
    # Generate timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create filename: solve_type_instance_name_time.xlsx
    filename = f"{solve_type}_{instance_base}_{timestamp}.xlsx"
    filepath = results_dir / filename
    
    # Create item lookup dictionary
    item_lookup = {item.idx: item for item in items_list}
    
    # Create capacity mapping from bin_type_id to capacity
    capacity_map = {}
    if bin_types:
        capacity_map = {bt.id: bt.capacity for bt in bin_types}
    
    # Build rows for Excel
    rows = []
    # Add items in bins
    for bin_idx, bin_obj in enumerate(sol.bins, start=1):  # Bin IDs start from 1
        # Get bin capacity from bin_type_id
        bin_capacity = capacity_map.get(bin_obj.bin_type_id, bin_obj.capacity if bin_obj.capacity > 0 else None)
        
        for item_idx in bin_obj.items:
            item = item_lookup.get(item_idx)
            if item:
                rows.append({
                    "Bin ID": bin_idx,
                    "Bin Capacity": bin_capacity,
                    "Item ID": item.idx,
                    "Item Weight": item.w,
                    "Item Type": "compulsory" if item.compulsory else "noncompulsory",
                    "Category": item.cat
                })
    
    # Add unloaded items (with Bin ID = "Unloaded")
    for item_idx in sol.unloaded:
        item = item_lookup.get(item_idx)
        if item:
            rows.append({
                "Bin ID": "Unloaded",
                "Bin Capacity": None,
                "Item ID": item.idx,
                "Item Weight": item.w,
                "Item Type": "compulsory" if item.compulsory else "noncompulsory",
                "Category": item.cat
            })
    
    # Create DataFrame and save to Excel
    if rows:
        df = pd.DataFrame(rows)
        
        # Calculate summary statistics
        total_items = len(items_list)
        noncompulsory_count = sum(1 for item in items_list if not item.compulsory)
        noncompulsory_loaded = sum(1 for row in rows if row["Item Type"] == "noncompulsory" and row["Bin ID"] != "Unloaded")
        noncompulsory_unloaded = sum(1 for row in rows if row["Item Type"] == "noncompulsory" and row["Bin ID"] == "Unloaded")
        compulsory_count = sum(1 for item in items_list if item.compulsory)
        compulsory_loaded = sum(1 for row in rows if row["Item Type"] == "compulsory" and row["Bin ID"] != "Unloaded")
        compulsory_unloaded = sum(1 for row in rows if row["Item Type"] == "compulsory" and row["Bin ID"] == "Unloaded")
        
        # Create summary DataFrame
        summary_data = {
            "Metric": [
                "Total Items",
                "Noncompulsory Items (Total)",
                "Noncompulsory Items (Loaded)",
                "Noncompulsory Items (Unloaded)",
                "Compulsory Items (Total)",
                "Compulsory Items (Loaded)",
                "Compulsory Items (Unloaded)",
                "Used Bins"
            ],
            "Value": [
                total_items,
                noncompulsory_count,
                noncompulsory_loaded,
                noncompulsory_unloaded,
                compulsory_count,
                compulsory_loaded,
                compulsory_unloaded,
                sol.used_bins
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        
        # Save to Excel with multiple sheets
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Bin Details', index=False)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        print(f"Bin results saved to {filepath}")
    else:
        print(f"Warning: No items found in bins to save.")

def main():
    parser = argparse.ArgumentParser(description="GBPPIC Solver")
    parser.add_argument("--instance", type=str, default="datasets/AI/AI_201_2500_0.json", help="Path to instance file")
    solver_choices = available_solvers()
    default_solver = "alns" if "alns" in solver_choices else solver_choices[0]
    parser.add_argument(
        "--solver",
        type=str,
        default=default_solver,
        choices=solver_choices,
        help=f"Solver type: one of {', '.join(solver_choices)}",
    )
    parser.add_argument(
        "--save-bins",
        action="store_true",
        help="Export bin results to Excel file in results folder",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=None,
        help="Override the ALNS iteration count for quick experiments",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=SEED,
        help="Random seed for the ALNS solver",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce ALNS progress and bin-level console output",
    )
    parser.add_argument(
        "--no-save-summary",
        action="store_true",
        help="Do not append the aggregate run summary to results.xlsx",
    )
    args = parser.parse_args()
    if args.iterations is not None and args.iterations < 1:
        parser.error("--iterations must be greater than 0")

    path = args.instance
    try:
        n, items_list, bin_types = read_dataset(path)
    except FileNotFoundError:
        print(f"Error: Instance file not found at {path}")
        return

    run_id = 1

    print(f"\n--- Starting solver | Instance: {path} ---")

    solver = create_solver(args.solver, path)
    print(f"Solving with {solver.get_name()}...")

    def solve_current_instance() -> Solution:
        if solver.get_name() != "ALNS":
            return solver.solve()

        params = dict(ALNS_PARAMS)
        if args.iterations is not None:
            params["N"] = args.iterations
        if args.quiet:
            params["print_iteration_results"] = False
            params["print_bin_results"] = False
        return solver.solve(params, seed=args.seed)

    sol, run_time = _run_solver_with_timing(solve_current_instance)

    # Calculate loaded noncompulsory items count (items placed in bins)
    item_lookup = {item.idx: item for item in items_list}
    loaded_noncompulsory_count = 0
    for bin_obj in sol.bins:
        for item_idx in bin_obj.items:
            item = item_lookup.get(item_idx)
            if item and not item.compulsory:
                loaded_noncompulsory_count += 1

    is_feasible, violations = check_feasibility(sol, items_list)
    _print_summary(path, n, sol, run_time, is_feasible, violations, loaded_noncompulsory_count)

    # All operators are always enabled for ALNS
    mechanisms = None
    if solver.get_name() == "ALNS":
        mechanisms = {}  # Empty dict to indicate ALNS (all operators enabled)

    # Save results to Excel
    instance_name = Path(path).name
    if not args.no_save_summary:
        try:
            save_results(
                instance_name = instance_name,
                algorithm = solver.get_name(),
                run_id = run_id,
                run_time = run_time,
                sol = sol,
                bin_types = bin_types,
                gap = None,
                mechanisms = mechanisms,
                noncompulsory_count = loaded_noncompulsory_count
            )
            print(f"Results saved to {RESULTS_FILE}")
        except RuntimeError as exc:
            print(f"Warning: {exc}")
    
    # Save bin results if requested
    if args.save_bins:
        try:
            save_bin_results(sol, items_list, solver.get_name(), instance_name, bin_types)
        except RuntimeError as exc:
            print(f"Warning: {exc}")

if __name__ == "__main__":
    main()
