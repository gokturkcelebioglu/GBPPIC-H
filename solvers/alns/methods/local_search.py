"""
Local search operators (LS1, LS2, LS3, LS4).
These operators improve solutions by swapping items or modifying bins.
"""

import random
import math
from typing import List
from models import Solution, Bin, Item, BinType
from ..helpers import compatible_catset
from constants import ALNS_PARAMS
from ..helpers import (
    _clone_solution, _recompute_bin, _cats_without_item,
    _all_categories_compatible, _validate_solution_integrity
)


def ls1(sol: Solution, items: List[Item], use_noncomp: bool = True) -> Solution:
    """
    Implements Algorithm 5: Swap heuristic.
    In each bin, try to replace one item 'u' with a heavier UNLOADED COMPULSORY item 'v'.
    """
    s = _clone_solution(sol)
    if not s.bins or not s.unloaded:
        return s

    for b in s.bins:
        if not b.items:
            continue

        # Implement Alg 5, Steps 3-5: Select one random item 'u',
        # prioritizing non-compulsory, *only if* use_noncomp is True.
        # If use_noncomp is False, only select from compulsory items.

        i_idx_to_swap = -1
        if use_noncomp:
            # Original logic: Prioritize non-comp
            noncomp_in_bin = [i for i in b.items if not items[i].compulsory]
            if noncomp_in_bin:
                # Step 3: item u <- select random item from J_i_L_nonC
                i_idx_to_swap = random.choice(noncomp_in_bin)
            elif b.items:
                # Step 5: item u <- select random item from J_i_L
                i_idx_to_swap = random.choice(b.items)
        else:
            # Compulsory-only phase: Only pick from compulsory items
            comp_in_bin = [i for i in b.items if items[i].compulsory]
            if comp_in_bin:
                # Step 5, but restricted to compulsory items
                i_idx_to_swap = random.choice(comp_in_bin)

        # If no valid item to swap was found (e.g., bin only had non-comp
        # items during comp-only phase), skip this bin.
        if i_idx_to_swap == -1:
            continue

        it_in = items[i_idx_to_swap]

        # Calculate bin state after removing item 'i_idx_to_swap'
        cats_after = _cats_without_item(b, i_idx_to_swap, items)
        load_after = b.load - it_in.w

        # Alg 5, Step 8: argmax logic
        # Find the HEAVIEST valid unloaded compulsory item 'v'
        best_v_idx = -1
        best_v_w = it_in.w  # Must be strictly heavier than this

        for v_idx in s.unloaded:
            it_v = items[v_idx]

            # Alg 5, Step 6: v must be compulsory
            if not it_v.compulsory:
                continue

            # Alg 5, Step 6: w_v > w_u AND w_v > best_v_w (argmax)
            if it_v.w <= best_v_w:
                continue

            # Alg 5, Step 6: w(J_i) - w_u + w_v <= b
            if load_after + it_v.w > b.capacity:
                continue

            # Alg 5, Step 6: c_cat_v,cat_u = 1
            if not compatible_catset(it_v.cat, cats_after):
                continue

            # This is a valid candidate and heavier than current best
            best_v_idx = v_idx
            best_v_w = it_v.w

        # After checking all unloaded items, perform the best swap if found
        if best_v_idx != -1:
            # perform swap (Alg 5, Steps 8-9)
            b.items.remove(i_idx_to_swap)
            b.items.append(best_v_idx)
            _recompute_bin(b, items)

            s.unloaded.remove(best_v_idx)
            s.unloaded.add(i_idx_to_swap)

    s.used_bins = len(s.bins)
    
    # Alg 5, Step 10: Sort y^s in descending order of occupation rate
    s.bins.sort(key=lambda b: b.load, reverse=True)

    return s


def ls2(sol: Solution, items: List[Item], use_noncomp: bool = True) -> Solution:
    """
    Implements Algorithm 6: Swap operator.
    Tries to swap an item 'j' from a heavy bin 'i' with a
    heavier compulsory item 'v' from a light bin 'u'.
    """
    s = _clone_solution(sol)
    if len(s.bins) <= 1:
        return s

    # Sort bins by occupation rate (descending)
    # This implements the "Input: y^s sorted..." requirement of Alg 6
    bin_indices = sorted(range(len(s.bins)), key=lambda bi: s.bins[bi].load, reverse=True)

    cut = int(math.ceil(len(s.bins) / 2.0))
    # Per Alg 6, Step 2: i < cut
    heavy_bin_indices = bin_indices[:cut]
    # Per Alg 6, Step 3: u >= cut
    light_bin_indices = bin_indices[cut:]

    if not heavy_bin_indices or not light_bin_indices:
        return s  # No heavy/light bins to swap between

    # Alg 6, Step 2: foreach bin i in {i | i < cut and w(J_i) < b}
    for i_idx in heavy_bin_indices:
        b_i = s.bins[i_idx]

        # Check w(J_i) < b
        if b_i.load >= b_i.capacity:
            continue

        # Alg 6, Step 4: foreach item j in J_i_L
        # Iterate over a copy of items in bin i, as we might modify it
        for j_idx in list(b_i.items):
            it_j = items[j_idx]

            # In compulsory-only phase, only consider swapping out compulsory items.
            if not use_noncomp and not it_j.compulsory:
                continue

            best_v_idx = -1
            best_v_w = it_j.w  # Must be strictly heavier
            best_u_idx = -1

            # Check compatibility of v in bin i
            cats_i_after_j = _cats_without_item(b_i, j_idx, items)
            load_i_after_j = b_i.load - it_j.w

            # Find the best valid swap partner 'v' from all light bins
            # Alg 6, Step 3: P <- {u | u >= cut and c_cat_m,cat_n = 1 ...}
            # Note: The compatibility check in Step 3 seems to be a mistake
            # in the paper, as it should be specific to the items being swapped.
            # We follow the item-specific check in Step 5.
            for u_idx in light_bin_indices:
                if u_idx == i_idx:
                    continue
                b_u = s.bins[u_idx]

                for v_idx in list(b_u.items):
                    it_v = items[v_idx]

                    # Algorithm 6 Step 5 conditions:
                    # 1. v is compulsory
                    # 2. v is heavier than j
                    # 3. v is heavier than current best v candidate
                    if not it_v.compulsory or it_v.w <= best_v_w:
                        continue

                    # 4. v fits in bin i
                    if load_i_after_j + it_v.w > b_i.capacity:
                        continue

                    # 5. v is compatible with bin i (after j is removed)
                    if not compatible_catset(it_v.cat, cats_i_after_j):
                        continue

                    # 6. Check if j fits in bin u (after v is removed)
                    cats_u_after_v = _cats_without_item(b_u, v_idx, items)
                    load_u_after_v = b_u.load - it_v.w

                    if load_u_after_v + it_j.w > b_u.capacity:
                        continue

                    # 7. Check if j is compatible with bin u (after v is removed)
                    if not compatible_catset(it_j.cat, cats_u_after_v):
                        continue

                    # This is a valid swap, and it_v is the best so far
                    best_v_idx = v_idx
                    best_v_w = it_v.w
                    best_u_idx = u_idx

            # After checking all light bins, perform the best swap found for j
            if best_v_idx != -1:
                # Perform the swap (Alg 6, Steps 8-9)
                b_u = s.bins[best_u_idx]

                # j (from i) goes to u
                b_u.items.remove(best_v_idx)
                b_u.items.append(j_idx)
                _recompute_bin(b_u, items)

                # v (from u) goes to i
                b_i.items.remove(j_idx)
                b_i.items.append(best_v_idx)
                _recompute_bin(b_i, items)

    s.used_bins = len(s.bins)
    
    # Alg 6, Step 10: Sort ys in descending order of occupation rate
    s.bins.sort(key=lambda b: b.load, reverse=True)
    
    return s


def ls3(sol: Solution, items: List[Item], bin_types: List[BinType]) -> Solution:
    """
    Local search operator LS3: Bin Type Downgrade.
    
    Reduces cost by downgrading bins to smaller/cheaper types when feasible.
    This directly addresses the heterogeneous bin cost structure by optimizing
    bin type selection after items have been placed.
    """
    s = _clone_solution(sol)
    
    for bin in s.bins:
        if not bin.items:
            continue
            
        # Find current bin type
        current_type = None
        for bt in bin_types:
            if bt.id == bin.bin_type_id:
                current_type = bt
                break
        
        if current_type is None:
            continue
        
        current_cost = current_type.cost
        
        # Find cheaper bin types that can hold this load
        feasible_cheaper = [
            bt for bt in bin_types 
            if bt.capacity >= bin.load and bt.cost < current_cost
        ]
        
        if feasible_cheaper:
            # Choose cheapest (with smallest capacity as tiebreaker)
            new_type = min(feasible_cheaper, key=lambda bt: (bt.cost, bt.capacity))
            
            # Verify all items still fit (should always be true, but double-check)
            if new_type.capacity >= bin.load:
                bin.bin_type_id = new_type.id
                bin.capacity = new_type.capacity
                # Load and categories remain the same
    
    # Validation
    if ALNS_PARAMS.get("validate_operators", False):
        is_valid, errors = _validate_solution_integrity(s, items, "LS3")
        if not is_valid:
            print(f"WARNING: LS3 validation failed: {errors}")
            return _clone_solution(sol)
    
    return s


def ls4(sol: Solution, items: List[Item], bin_types: List[BinType]) -> Solution:
    """
    Local search operator LS4: Bin Merging.
    
    Directly reduces bin count by merging two bins into one when feasible.
    This operator is particularly important for heterogeneous bin problems with
    category incompatibilities, as it consolidates space efficiently.
    
    A merge is only accepted if the new bin cost is strictly less than the sum
    of the two original bin costs, ensuring the merge improves the objective.
    Among cost-improving merges, the one with highest utilization is selected.
    """
    s = _clone_solution(sol)
    
    if len(s.bins) < 2:
        return s
    
    # Sort bins by load (ascending - try merging light bins first)
    # Use list of bins directly, track which ones we've processed
    sorted_indices = sorted(range(len(s.bins)), key=lambda i: s.bins[i].load)
    merged = set()
    new_bins = []
    
    for i in range(len(sorted_indices)):
        idx_i = sorted_indices[i]
        if idx_i in merged:
            continue
        
        bin_i = s.bins[idx_i]
        best_merge = None
        best_utilization = -1.0  # Initialize to -1 to ensure any valid merge is better
        best_j = None
        
        for j in range(i + 1, len(sorted_indices)):
            idx_j = sorted_indices[j]
            if idx_j in merged:
                continue
            
            bin_j = s.bins[idx_j]
            
            # Check if categories are compatible
            combined_cats = bin_i.cats | bin_j.cats
            if not _all_categories_compatible(combined_cats):
                continue
            
            # Check capacity
            total_load = bin_i.load + bin_j.load
            feasible_types = [bt for bt in bin_types if bt.capacity >= total_load]
            
            if feasible_types:
                # Find current bin types and costs
                type_i = None
                type_j = None
                for bt in bin_types:
                    if bt.id == bin_i.bin_type_id:
                        type_i = bt
                    if bt.id == bin_j.bin_type_id:
                        type_j = bt
                    if type_i and type_j:
                        break
                
                if type_i is None or type_j is None:
                    continue  # Skip if we can't find bin types (shouldn't happen, but safe)
                
                total_current_cost = type_i.cost + type_j.cost
                
                # Choose cheapest feasible bin type
                best_type = min(feasible_types, key=lambda bt: (bt.cost, bt.capacity))
                
                # Only consider merge if it reduces cost (strictly improves objective)
                if best_type.cost >= total_current_cost:
                    continue  # Skip this merge - doesn't improve cost
                
                utilization = total_load / best_type.capacity if best_type.capacity > 0 else 0
                
                # Maximize utilization (higher is better - less wasted space)
                if utilization > best_utilization:
                    best_merge = (best_type, total_load, combined_cats)
                    best_utilization = utilization
                    best_j = idx_j
        
        if best_merge and best_j is not None:
            best_type, total_load, combined_cats = best_merge
            # Create merged bin with proper cloning
            merged_items = bin_i.items[:] + s.bins[best_j].items[:]
            new_bins.append(Bin(
                items=merged_items,
                load=total_load,
                cats=set(combined_cats),
                bin_type_id=best_type.id,
                capacity=best_type.capacity
            ))
            merged.add(idx_i)
            merged.add(best_j)
        else:
            # Keep original bin (create new instance to avoid reference issues)
            new_bins.append(Bin(
                items=bin_i.items[:],
                load=bin_i.load,
                cats=set(bin_i.cats),
                bin_type_id=bin_i.bin_type_id,
                capacity=bin_i.capacity
            ))
            merged.add(idx_i)
    
    # Verify all items are preserved
    all_items_in_new_bins = set()
    for bin in new_bins:
        all_items_in_new_bins.update(bin.items)
    
    all_items_in_original = set()
    for bin in sol.bins:
        all_items_in_original.update(bin.items)
    
    # If items are missing, something went wrong - return original
    if all_items_in_original != all_items_in_new_bins:
        return _clone_solution(sol)
    
    # Safety check: ensure all bins were processed
    if len(merged) != len(s.bins):
        # Some bins weren't processed - return original to be safe
        if ALNS_PARAMS.get("validate_operators", False):
            print(f"WARNING: LS4 not all bins processed: {len(merged)}/{len(s.bins)}")
        return _clone_solution(sol)
    
    s.bins = new_bins
    s.used_bins = len(s.bins)
    
    # Validation
    if ALNS_PARAMS.get("validate_operators", False):
        is_valid, errors = _validate_solution_integrity(s, items, "LS4")
        if not is_valid:
            print(f"WARNING: LS4 validation failed: {errors}")
            return _clone_solution(sol)
    
    return s
