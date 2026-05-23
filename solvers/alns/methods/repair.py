"""
Repair operators (Ω+1 to Ω+4).
These operators place unloaded items back into bins.
"""

from typing import List, Set, Tuple
from models import Solution, Bin, Item, BinType
from ..helpers import (
    _first_fit_place, _open_new_bin, _grasp_pick, _compat_degree, _clone_bins_list
)

def _ffd_pack(order: List[Item], initial_bins: List[Bin], bin_types: List[BinType]) -> Tuple[List[Bin], Set[int]]:
    """
    Packs a pre-sorted list of items into initial_bins.
    Compulsory items can open new bins; non-compulsory cannot.
    Returns the final bins and the set of *all* items that remain unloaded.
    """
    # Start with a copy of the bins passed in, preserving bin_type_id and capacity
    bins: List[Bin] = _clone_bins_list(initial_bins)

    # We only try to pack items in the 'order' list.
    unloaded_items_in_order = set(it.idx for it in order)

    for it in order:
        placed = _first_fit_place(bins, it)
        if not placed and it.compulsory:
            # Check if there's a feasible bin type for this item
            feasible_types = [bt for bt in bin_types if bt.capacity >= it.w]
            if feasible_types:
                # Compulsory items can open new bins
                _open_new_bin(bins, it, bin_types)
                placed = True

        if placed:
            unloaded_items_in_order.discard(it.idx)

    return bins, unloaded_items_in_order


def repair_grasp_ffd(sol: Solution, items: List[Item], bin_types: List[BinType], grasp_R: Tuple[int, int], use_noncomp: bool = True) -> Solution:
    """
    Repair operator Ω+1: GRASP FFD (Algorithm 3).

    Tries to place all items from sol.unloaded using a GRASP-based
    First Fit Decreasing heuristic.
    """

    # Start with the bins we already have, preserving bin_type_id and capacity
    bins: List[Bin] = _clone_bins_list(sol.bins)

    # We will try to place all items that are currently unloaded
    unloaded_now = set(sol.unloaded)

    # Pre-sort all items by weight (descending)
    sorted_by_w = sorted(items, key=lambda it: it.w, reverse=True)

    # Pass 1: compulsory (can open bins)
    # Get compulsory items that are currently unloaded
    remaining = {i for i in unloaded_now if items[i].compulsory}
    while remaining:
        pick = _grasp_pick(sorted_by_w, remaining, grasp_R)
        if pick is None:
            break

        placed = _first_fit_place(bins, pick)
        if not placed:
            # Check if there's a feasible bin type for this item
            feasible_types = [bt for bt in bin_types if bt.capacity >= pick.w]
            if feasible_types:
                # Can open a new bin
                _open_new_bin(bins, pick, bin_types)
                placed = True

        if placed:
            unloaded_now.discard(pick.idx)
        remaining.discard(pick.idx)  # Move to next item regardless

    # Pass 2: non-compulsory (no new bins)
    if use_noncomp:
        remaining = {i for i in unloaded_now if not items[i].compulsory}
        while remaining:
            pick = _grasp_pick(sorted_by_w, remaining, grasp_R)
            if pick is None:
                break

            # Can only place in existing bins
            if _first_fit_place(bins, pick):
                unloaded_now.discard(pick.idx)
            remaining.discard(pick.idx)

    return Solution(bins=bins, unloaded=unloaded_now, obj=0, used_bins=len(bins))


def repair_ffd_by_weight(sol: Solution, items: List[Item], bin_types: List[BinType], use_noncomp: bool = True) -> Solution:
    """
    Repair operator Ω+2: FFD by weight.

    First Fit Decreasing - compulsory items first, then by decreasing weight.
    """

    items_to_pack = [items[i] for i in sol.unloaded]
    if not use_noncomp:
        items_to_pack = [it for it in items_to_pack if it.compulsory]

    # Sort key: (compulsory status, weight)
    # (not it.compulsory) sorts False (comp) before True (non-comp)
    # (-it.w) sorts by weight descending
    items_to_pack.sort(key=lambda it: (not it.compulsory, -it.w))

    bins, unloaded_from_pack = _ffd_pack(items_to_pack, sol.bins, bin_types)

    # The final set of unloaded items is any items that *were not* in the packing
    # list (e.g., non-comp items if use_noncomp=False) *plus* any
    # items from the packing list that failed to be placed.
    final_unloaded = (sol.unloaded - set(it.idx for it in items_to_pack)) | unloaded_from_pack

    return Solution(bins=bins, unloaded=final_unloaded, obj=0, used_bins=len(bins))


def repair_ffd_desc_compatibility(sol: Solution, items: List[Item], bin_types: List[BinType], use_noncomp: bool = True) -> Solution:
    """
    Repair operator Ω+3: FFD by descending compatibility degree.

    First Fit Decreasing - compulsory items first, then by descending
    compatibility degree, then by descending weight.
    """

    items_to_pack = [items[i] for i in sol.unloaded]
    if not use_noncomp:
        items_to_pack = [it for it in items_to_pack if it.compulsory]

    # Sort key: (compulsory, DESC degree, DESC weight)
    items_to_pack.sort(key=lambda it: (
        not it.compulsory,
        -_compat_degree(it.cat),
        -it.w
    ))

    bins, unloaded_from_pack = _ffd_pack(items_to_pack, sol.bins, bin_types)
    final_unloaded = (sol.unloaded - set(it.idx for it in items_to_pack)) | unloaded_from_pack

    return Solution(bins=bins, unloaded=final_unloaded, obj=0, used_bins=len(bins))


def repair_ffd_asc_compatibility(sol: Solution, items: List[Item], bin_types: List[BinType], use_noncomp: bool = True) -> Solution:
    """
    Repair operator Ω+4: FFD by ascending compatibility degree.

    First Fit Decreasing - compulsory items first, then by ascending
    compatibility degree, then by descending weight.
    """

    items_to_pack = [items[i] for i in sol.unloaded]
    if not use_noncomp:
        items_to_pack = [it for it in items_to_pack if it.compulsory]

    # Sort key: (compulsory, ASC degree, DESC weight)
    items_to_pack.sort(key=lambda it: (
        not it.compulsory,
        _compat_degree(it.cat),
        -it.w
    ))

    bins, unloaded_from_pack = _ffd_pack(items_to_pack, sol.bins, bin_types)
    final_unloaded = (sol.unloaded - set(it.idx for it in items_to_pack)) | unloaded_from_pack

    return Solution(bins=bins, unloaded=final_unloaded, obj=0, used_bins=len(bins))

