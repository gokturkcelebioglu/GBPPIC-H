"""
Partial destroy operators (Ωd1-Ωd4).
These operators remove items from bins but keep the bins themselves.
"""

import random
from typing import List
from models import Solution, Item
from ..helpers import _clone_solution, _recompute_bin


def destroy_random_items_per_bin(sol: Solution, items: List[Item], alpha: float) -> Solution:
    """
    Partial destroy operator Ωd1.
    With probability α per bin, remove one random item from that bin.
    """
    s = _clone_solution(sol)
    for b in s.bins:
        if b.items and random.random() < alpha:
            i = random.choice(b.items)
            b.items.remove(i)
            s.unloaded.add(i)
            _recompute_bin(b, items)
    s.bins = [b for b in s.bins if b.items]
    s.used_bins = len(s.bins)
    return s


def destroy_lightest_category_per_bin(sol: Solution, items: List[Item]) -> Solution:
    """
    Partial destroy operator Ωd2.
    In each bin, remove all items of the least-weight category present.
    """
    s = _clone_solution(sol)
    for b in s.bins:
        if not b.items:
            continue
        # Sum weight per category in this bin
        cat_w: dict = {}
        for i in b.items:
            it = items[i]
            cat_w[it.cat] = cat_w.get(it.cat, 0) + it.w
        if not cat_w:
            continue
        min_weight = min(cat_w.values())
        # If multiple min, choose one deterministically by smallest category id
        target_cats = [c for c, w in cat_w.items() if w == min_weight]
        target_cat = min(target_cats)
        keep = [i for i in b.items if items[i].cat != target_cat]
        removed = [i for i in b.items if items[i].cat == target_cat]
        b.items = keep
        for i in removed:
            s.unloaded.add(i)
        _recompute_bin(b, items)
    s.bins = [b for b in s.bins if b.items]
    s.used_bins = len(s.bins)
    return s


def destroy_random_category_per_bin(sol: Solution, items: List[Item]) -> Solution:
    """
    Partial destroy operator Ωd3.
    In each bin, choose a random category present and remove all its items.
    """
    s = _clone_solution(sol)
    for b in s.bins:
        if not b.items:
            continue
        cats_present = {items[i].cat for i in b.items}
        if not cats_present:
            continue
        target_cat = random.choice(list(cats_present))
        keep = [i for i in b.items if items[i].cat != target_cat]
        removed = [i for i in b.items if items[i].cat == target_cat]
        b.items = keep
        for i in removed:
            s.unloaded.add(i)
        _recompute_bin(b, items)
    s.bins = [b for b in s.bins if b.items]
    s.used_bins = len(s.bins)
    return s


def destroy_all_noncompulsory_items(sol: Solution, items: List[Item]) -> Solution:
    """
    Partial destroy operator Ωd4.
    Remove all non-compulsory items from every bin.
    """
    s = _clone_solution(sol)
    for b in s.bins:
        keep = [i for i in b.items if items[i].compulsory]
        removed = [i for i in b.items if not items[i].compulsory]
        b.items = keep
        for i in removed:
            s.unloaded.add(i)
        _recompute_bin(b, items)
    s.bins = [b for b in s.bins if b.items]
    s.used_bins = len(s.bins)
    return s

