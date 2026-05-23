from typing import List
from models import Solution, Item


def check_feasibility(solution: Solution, items: List[Item]):
    """
    Check if a solution is feasible and return violations if any.
    
    Returns:
        Tuple of (is_feasible: bool, violations: List[str])
    """
    violations = [] 
    n = len(items) 
    # Track which items are loaded 
    loaded_items = set() 
    for bin in solution.bins: 
        for item_idx in bin.items: 
            loaded_items.add(item_idx) 
    
    # Check 1: All compulsory items must be loaded 
    for item_idx in range(n): 
        if items[item_idx].compulsory and item_idx in solution.unloaded: 
            violations.append(f"Compulsory item {item_idx} is unloaded") 
            
    # Check 2: No duplicate items (each item appears at most once in bins) 
    all_items_in_bins = [] 
    for bin in solution.bins:
        all_items_in_bins.extend(bin.items) 
        if len(all_items_in_bins) != len(set(all_items_in_bins)): 
            violations.append("Duplicate items found in bins") 
            
    # Check 3: Items in bins should not be in unloaded set (and vice versa)
    items_in_bins_set = set(all_items_in_bins) 
    overlap = items_in_bins_set & solution.unloaded 
    if overlap: 
        violations.append(f"Items {overlap} appear in both bins and unloaded set") 
        
    # Check 4: All items must be accounted for (either in bins or unloaded)
    all_accounted = items_in_bins_set | solution.unloaded
    missing_items = set(range(n)) - all_accounted 
    if missing_items: 
        violations.append(f"Items {missing_items} are not accounted for (neither in bins nor unloaded)")
        extra_items = all_accounted - set(range(n))
        if extra_items: violations.append(f"Invalid item indices found: {extra_items}") 
        
    # Check 5: Bin capacity constraints
    for bin_idx, bin in enumerate(solution.bins):
        if bin.load > bin.capacity:
            violations.append(f"Bin {bin_idx} exceeds capacity: load={bin.load} > capacity={bin.capacity}")
            
    # Check 6: Bin load matches sum of item weights
    for bin_idx, bin in enumerate(solution.bins):
        computed_load = sum(items[item_idx].w for item_idx in bin.items)
        if bin.load != computed_load:
            violations.append(f"Bin {bin_idx} load mismatch: stored={bin.load}, computed={computed_load}")

    # Check 7: Category compatibility within each bin and category set correctness
    from .alns.helpers import compatible_catset
    for bin_idx, bin in enumerate(solution.bins):
        computed_cats = {items[item_idx].cat for item_idx in bin.items}
        if bin.cats != computed_cats:
            violations.append(f"Bin {bin_idx} category set mismatch: stored={bin.cats}, computed={computed_cats}")

        # Check pairwise category compatibility
        items_in_bin = [items[item_idx] for item_idx in bin.items]
        for i, item1 in enumerate(items_in_bin):
            for j, item2 in enumerate(items_in_bin):
                if i < j: # Check each pair only once
                    if not compatible_catset(item1.cat, {item2.cat}):
                        violations.append(f"Bin {bin_idx}: incompatible categories - item {item1.idx} (cat {item1.cat}) and item {item2.idx} (cat {item2.cat})")
    
    return len(violations) == 0, violations


def print_bin_results(solution: Solution):
    """Print bin results showing items, capacity, and percentage used for each bin."""
    print("Number of bins used:", len(solution.bins))
    for i, bin in enumerate(solution.bins, 1):
        percentage = (bin.load / bin.capacity * 100) if bin.capacity > 0 else 0.0
        items_display = [item + 1 for item in bin.items]    
        print(f"Bin {i} (capacity {bin.capacity}): {items_display} ({percentage:.2f}% used)")

