"""
Full destroy operators (Ωk1-Ωk4).
These operators remove entire bins and attempt to reallocate compulsory items.
"""

import random
import math
from typing import List
from models import Solution, Item
from ..helpers import _clone_solution, _remove_bins_and_collect, _reallocate_compulsories


def destroy_bins_highest_noncomp_weight(sol: Solution, items: List[Item], beta: float) -> Solution:
    """
    Full destroy operator Ωk1.

    Remove β fraction of bins with highest non-compulsory weight.
    """
    s = _clone_solution(sol)
    if not s.bins:
        return s
    ranks = []
    for idx, b in enumerate(s.bins):
        w_noncomp = sum(items[i].w for i in b.items if not items[i].compulsory)
        ranks.append((idx, w_noncomp))
    ranks.sort(key=lambda x: x[1], reverse=True)
    k = max(1, int(math.floor(beta * len(s.bins))))
    remove = {idx for idx, _ in ranks[:k]}

    # FIRST: collect items from bins to be removed
    removed_items = _remove_bins_and_collect(s, remove)

    # SECOND: separate compulsory from non-compulsory
    comp = [i for i in removed_items if items[i].compulsory]
    nonc = [i for i in removed_items if not items[i].compulsory]

    # THIRD: try to reallocate compulsory items into remaining bins
    not_placed = _reallocate_compulsories(s, items, comp)

    # FINALLY: unload items that couldn't be placed (non-comp + not-placed comp)
    for i in not_placed + nonc:
        s.unloaded.add(i)
    return s


def destroy_bins_least_occupied(sol: Solution, items: List[Item], beta: float) -> Solution:
    """
    Full destroy operator Ωk2.

    Remove β fraction of least-occupied bins (by load).
    """
    s = _clone_solution(sol)
    if not s.bins:
        return s
    ranks = sorted([(idx, b.load) for idx, b in enumerate(s.bins)], key=lambda x: x[1])
    k = max(1, int(math.floor(beta * len(s.bins))))
    remove = {idx for idx, _ in ranks[:k]}

    # FIRST: collect items from bins to be removed
    removed_items = _remove_bins_and_collect(s, remove)

    # SECOND: separate compulsory from non-compulsory
    comp = [i for i in removed_items if items[i].compulsory]
    nonc = [i for i in removed_items if not items[i].compulsory]

    # THIRD: try to reallocate compulsory items into remaining bins
    not_placed = _reallocate_compulsories(s, items, comp)

    # FINALLY: unload items that couldn't be placed
    for i in not_placed + nonc:
        s.unloaded.add(i)
    return s


def destroy_bins_random(sol: Solution, items: List[Item], gamma: float) -> Solution:
    """
    Full destroy operator Ωk3.

    Remove each bin independently with probability γ.
    """
    s = _clone_solution(sol)
    remove = {idx for idx, _ in enumerate(s.bins) if random.random() < gamma}
    if not remove:
        return s

    # FIRST: collect items from bins to be removed
    removed_items = _remove_bins_and_collect(s, remove)

    # SECOND: separate compulsory from non-compulsory
    comp = [i for i in removed_items if items[i].compulsory]
    nonc = [i for i in removed_items if not items[i].compulsory]

    # THIRD: try to reallocate compulsory items into remaining bins
    not_placed = _reallocate_compulsories(s, items, comp)

    # FINALLY: unload items that couldn't be placed
    for i in not_placed + nonc:
        s.unloaded.add(i)
    return s


def destroy_bins_only_noncompulsory(sol: Solution, items: List[Item]) -> Solution:
    """
    Full destroy operator Ωk4.

    Remove bins containing only non-compulsory items.
    """
    s = _clone_solution(sol)
    remove = {idx for idx, b in enumerate(s.bins) if b.items and all(not items[i].compulsory for i in b.items)}
    if not remove:
        return s

    # FIRST: collect items from bins to be removed (all are non-compulsory by definition)
    removed_items = _remove_bins_and_collect(s, remove)

    # SECOND: separate compulsory from non-compulsory (comp will be empty by definition)
    comp = [i for i in removed_items if items[i].compulsory]
    nonc = [i for i in removed_items if not items[i].compulsory]

    # THIRD: try to reallocate compulsory items (will be none, but kept for consistency)
    not_placed = _reallocate_compulsories(s, items, comp)

    # FINALLY: unload all items (all non-compulsory)
    for i in not_placed + nonc:
        s.unloaded.add(i)
    return s

