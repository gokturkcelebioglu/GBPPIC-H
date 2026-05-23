from dataclasses import dataclass
from typing import List, Set

@dataclass
class Item:
    idx: int
    w: int
    cat: int
    compulsory: bool
    r: int

@dataclass
class BinType:
    id: int
    capacity: int
    cost: int

@dataclass
class Bin:
    items: List[int]
    load: int
    cats: Set[int]
    bin_type_id: int
    capacity: int = 0  # Will be set based on bin_type_id

@dataclass
class Solution:
    bins: List[Bin]
    unloaded: Set[int]
    obj: int
    used_bins: int