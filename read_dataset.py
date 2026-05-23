from pathlib import Path
import json
from models import Item, BinType


def read_dataset(path: str):
    """Read a generated JSON instance and return actual item count, items, and bin types."""
    p = Path(path)

    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)

    items_data = data["items"]

    items = []
    for i, it in enumerate(items_data):  # Read all items, not just first n
        w = int(it["weight"])
        cat = int(it["category"])
        compulsory = bool(it["compulsory"])
        profit = int(it["profit"])
        items.append(
            Item(
                idx = i,  # Preserve the solver's zero-based item index.
                w = w,
                cat = cat,
                compulsory = compulsory,
                r = profit
            )
        )

    bin_types_data = data.get("bin_types", [])
    if not bin_types_data:
        raise ValueError(f"No bin types found in {path}")

    bin_types = []
    for bt in bin_types_data:
        bin_types.append(
            BinType(
                id = int(bt["id"]),
                capacity = int(bt["capacity"]),
                cost = int(bt["cost"]),
            )
        )

    return len(items), items, bin_types
