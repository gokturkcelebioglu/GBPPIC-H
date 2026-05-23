"""
Helper functions shared across ALNS mechanisms.
"""

from typing import List, Set, Tuple
from models import Solution, Bin, Item, BinType
from constants import COMPAT


def compatible_catset(cat: int, present):
    """Check if a category is compatible with a set of present categories."""
    if not present:
        return True

    K = len(COMPAT)

    if not (1 <= cat <= K):
        raise ValueError(f"Category out of range: {cat} (expected 1..{K})")

    k = cat - 1
    for c in present:
        if not (1 <= c <= K):
            raise ValueError(f"Category out of range in present set: {c} (expected 1..{K})")
        c0 = c - 1
        if COMPAT[k][c0] == 0 or COMPAT[c0][k] == 0:
            return False

    return True


def evaluate(bins: List[Bin], unloaded: Set[int], items: List[Item], bin_types: List[BinType]) -> int:
    """
    Implements objective: Σ (bin_type_cost for each used bin) - Σ r_j for loaded items.
    
    Uses actual bin type costs from bin_types.
    Subtracts revenue from all loaded items (both compulsory and non-compulsory).
    """

    # Calculate revenue from all items that were *successfully loaded*
    loaded_rev = 0
    for b in bins:
        for item_idx in b.items:
            loaded_rev += items[item_idx].r

    # Calculate total bin cost using actual bin type costs
    cost_map = {bt.id: bt.cost for bt in bin_types}
    total_bin_cost = 0
    for b in bins:
        bin_cost = cost_map.get(b.bin_type_id, 0)
        total_bin_cost += bin_cost

    # A valid solution *must* pack all compulsory items.
    # We must add a massive penalty for any compulsory items left in the 'unloaded' set.
    # This penalty must be larger than any possible objective value.
    infeasibility_penalty = 0
    # Use a penalty based on maximum possible bin cost
    max_bin_cost = max(bt.cost for bt in bin_types) if bin_types else 1
    penalty_per_item = max_bin_cost * 10000  # Large penalty multiplier
    
    for item_idx in unloaded:
        if items[item_idx].compulsory:
            # Add a penalty larger than any possible bin cost for *each* unplaced compulsory item.
            # This ensures any invalid solution is always worse than any valid one.
            infeasibility_penalty += penalty_per_item

    # The final objective is: total bin cost - revenue from loaded items + infeasibility penalty
    return total_bin_cost - loaded_rev + infeasibility_penalty


def _clone_solution(sol: Solution) -> Solution:
    """Create a deep copy of a solution."""
    return Solution(
        bins=[
            Bin(
                items=b.items[:],
                load=b.load,
                cats=set(b.cats),
                bin_type_id=b.bin_type_id,
                capacity=b.capacity
            ) for b in sol.bins
        ],
        unloaded=set(sol.unloaded),
        obj=sol.obj,
        used_bins=sol.used_bins
    )


def _clone_bins_list(bins: List[Bin]) -> List[Bin]:
    """Create a deep copy of a list of bins."""
    return [
        Bin(
            items=b.items[:],
            load=b.load,
            cats=set(b.cats),
            bin_type_id=b.bin_type_id,
            capacity=b.capacity
        ) for b in bins
    ]


def _recompute_bin(b: Bin, items: List[Item]) -> None:
    """Recompute load and cats from its items list."""
    b.load = 0
    cats = set()
    for i in b.items:
        it = items[i]
        b.load += it.w
        cats.add(it.cat)
    b.cats = cats


def _first_fit_place(bins: List[Bin], it: Item) -> bool:
    """Try to place item in first bin that fits."""
    for b in bins:
        if b.load + it.w <= b.capacity and compatible_catset(it.cat, b.cats):
            b.items.append(it.idx)
            b.load += it.w
            b.cats.add(it.cat)
            return True
    return False


def _reallocate_compulsories(s: Solution, items: List[Item], comp_to_place: List[int]) -> List[int]:
    """Attempt to reallocate compulsory items into remaining bins (with evictions). Return not-placed."""
    not_placed: List[int] = []
    for i in comp_to_place:
        it = items[i]
        placed = False
        # First pass: try direct first-fit
        if _first_fit_place(s.bins, it):
            placed = True
        else:
            # Second pass: try evicting non-comp items in compatible bins
            for b in s.bins:
                # Try to place compulsory item 'it' into bin 'b' by evicting non-comp items
                if not compatible_catset(it.cat, b.cats):
                    continue
                if b.load + it.w <= b.capacity:
                    b.items.append(it.idx)
                    b.load += it.w
                    b.cats.add(it.cat)
                    placed = True
                    break
                else:
                    # Evict lightest non-compulsory items first
                    noncomp = [j for j in b.items if not items[j].compulsory]
                    noncomp.sort(key=lambda j: items[j].w)  # lightest first
                    freed = 0
                    evicted: List[int] = []
                    for j in noncomp:
                        freed += items[j].w
                        evicted.append(j)
                        if b.load - freed + it.w <= b.capacity:
                            # Perform evictions & place
                            for e in evicted:
                                b.items.remove(e)
                            b.items.append(it.idx)
                            _recompute_bin(b, items)
                            # evicted items become unloaded
                            for e in evicted:
                                s.unloaded.add(e)
                            placed = True
                            break
                    if placed:
                        break
        if not placed:
            not_placed.append(i)
        else:
            # remove from unloaded if present
            if i in s.unloaded:
                s.unloaded.remove(i)
    # Drop empty bins after reallocations
    s.bins = [b for b in s.bins if b.items]
    s.used_bins = len(s.bins)
    return not_placed


def _remove_bins_and_collect(s: Solution, which: Set[int]) -> List[int]:
    """Remove bins by indices; return all items contained in removed bins."""
    to_unload: List[int] = []
    keep: List[Bin] = []
    for idx, b in enumerate(s.bins):
        if idx in which:
            to_unload.extend(b.items)
        else:
            keep.append(b)
    s.bins = keep
    s.used_bins = len(s.bins)
    return to_unload


def _cats_without_item(b: Bin, removed_idx: int, items: List[Item]) -> set:
    """Return the category set of bin b if item 'removed_idx' were removed."""
    cat_counts = {}
    for i in b.items:
        c = items[i].cat
        cat_counts[c] = cat_counts.get(c, 0) + 1
    # simulate removal
    c_rem = items[removed_idx].cat
    if cat_counts.get(c_rem, 0) <= 1:
        # last of its category -> category disappears
        return {c for c in b.cats if c != c_rem}
    else:
        # still present
        return set(b.cats)


def _open_new_bin(bins: List[Bin], item: Item, bin_types: List[BinType]):
    """
    Create a new bin with the smallest feasible (cheapest) bin type.
    
    Args:
        bins: List of bins to append to
        item: Item to place in the new bin
        bin_types: List of available bin types
    """
    # Filter bin_types where capacity >= item.w
    feasible_types = [bt for bt in bin_types if bt.capacity >= item.w]
    
    if not feasible_types:
        # No feasible bin type found - this should not happen for compulsory items
        # but we'll use the largest available as fallback
        feasible_types = [max(bin_types, key=lambda bt: bt.capacity)]
    
    # Sort by cost (ascending), then by capacity (ascending) as tiebreaker
    selected_bt = min(feasible_types, key=lambda bt: (bt.cost, bt.capacity))
    
    bins.append(Bin(
        items=[item.idx],
        load=item.w,
        cats={item.cat},
        bin_type_id=selected_bt.id,
        capacity=selected_bt.capacity
    ))


def _grasp_pick(sorted_items: List[Item], remaining: Set[int], R_range: Tuple[int, int]):
    """GRASP selection: pick from top R candidates."""
    import random
    
    Rmin, Rmax = R_range
    # Filter the pre-sorted list to find candidates still in 'remaining'
    cand = [it for it in sorted_items if it.idx in remaining]
    if not cand:
        return None
    rmax = min(Rmax, len(cand))
    rmin = Rmin if len(cand) >= Rmin else 1
    if rmax < 1:
        return None
    if rmax < rmin:
        R = rmax
    else:
        R = random.randint(rmin, rmax)
    return random.choice(cand[:R])  # Pick from the top R of the *remaining* items


def _compat_degree(cat: int) -> int:
    """Calculate compatibility degree of a category."""
    # Adjust for 0-indexing of COMPAT matrix (categories are 1-based)
    return sum(COMPAT[cat - 1])


def _all_categories_compatible(cats: Set[int]) -> bool:
    """Check if all categories in the set are pairwise compatible."""
    cats_list = list(cats)
    for i in range(len(cats_list)):
        for j in range(i + 1, len(cats_list)):
            cat1, cat2 = cats_list[i], cats_list[j]
            # Check both directions in compatibility matrix
            if COMPAT[cat1 - 1][cat2 - 1] == 0 or COMPAT[cat2 - 1][cat1 - 1] == 0:
                return False
    return True


def _validate_solution_integrity(sol: Solution, items: List[Item], context: str = "") -> Tuple[bool, List[str]]:
    """
    Validate that a solution maintains integrity (all items accounted for, no duplicates).
    This is a lightweight check for debugging - use check_feasibility for full validation.
    
    Returns: (is_valid, list of error messages)
    """
    errors = []
    n = len(items)
    
    # Collect all items in bins
    all_items_in_bins = []
    for bin in sol.bins:
        all_items_in_bins.extend(bin.items)
    
    items_in_bins_set = set(all_items_in_bins)
    
    # Check for duplicates
    if len(all_items_in_bins) != len(items_in_bins_set):
        duplicates = [x for x in all_items_in_bins if all_items_in_bins.count(x) > 1]
        errors.append(f"{context}: Duplicate items found: {set(duplicates)}")
    
    # Check for overlap between bins and unloaded
    overlap = items_in_bins_set & sol.unloaded
    if overlap:
        errors.append(f"{context}: Items in both bins and unloaded: {overlap}")
    
    # Check all items are accounted for
    all_accounted = items_in_bins_set | sol.unloaded
    missing_items = set(range(n)) - all_accounted
    if missing_items:
        errors.append(f"{context}: Missing items (not in bins or unloaded): {missing_items}")
    
    # Check for invalid item indices
    extra_items = all_accounted - set(range(n))
    if extra_items:
        errors.append(f"{context}: Invalid item indices: {extra_items}")
    
    # Check bin load consistency
    for bin_idx, bin in enumerate(sol.bins):
        computed_load = sum(items[item_idx].w for item_idx in bin.items)
        if bin.load != computed_load:
            errors.append(f"{context}: Bin {bin_idx} load mismatch: stored={bin.load}, computed={computed_load}")
    
    # Check bin category consistency
    for bin_idx, bin in enumerate(sol.bins):
        computed_cats = {items[item_idx].cat for item_idx in bin.items}
        if bin.cats != computed_cats:
            errors.append(f"{context}: Bin {bin_idx} category mismatch: stored={bin.cats}, computed={computed_cats}")
    
    return len(errors) == 0, errors

