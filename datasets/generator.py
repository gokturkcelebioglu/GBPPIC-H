import json
import random
from pathlib import Path

BIN_TYPE_1_MULTIPLIER = 0.75
BIN_TYPE_2_MULTIPLIER = 1
BIN_TYPE_3_MULTIPLIER = 1.25

class Item:
    def __init__(self, item_id: int, weight: int, category: int, compulsory: bool):
        self.item_id = item_id
        self.weight = weight
        self.category = category
        self.compulsory = compulsory
        self.profit = weight if not compulsory else 0

def parse_filename(filename: str):
    stem = Path(filename).stem

    filename_parts = stem.split("_")

    n_items = int(filename_parts[0])
    base_capacity = int(filename_parts[1])
    instance_type = "AI" if filename_parts[2] == "DI" else "ANI"
    instance_id = int(filename_parts[3])
    return n_items, base_capacity, instance_type, instance_id

def read_item_weights(path: Path):
    weights = []
    with path.open("r") as f:
        # Read all rows
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                w = int(line)
            except ValueError:
                # Ignore non-integer lines silently
                continue
            weights.append(w)

    # Remove first item (which is the count from first row)
    return weights[1:]

def process_instance(input_path: Path, script_dir: Path):
    source_n_items, base_capacity, instance_type, instance_id = parse_filename(input_path.name)
    
    base_items = read_item_weights(input_path)

    rng = random.Random(instance_id)
    num_compulsory = int(round(0.85 * source_n_items))
    rng.shuffle(base_items)
    
    compulsory_counter = 0

    items = []

    i = 0

    for base_item in base_items:
        item_id = 0
        new_item_type = False
        new_item_category = ((i + instance_id) % 6) + 1
        
        if compulsory_counter < num_compulsory:
            new_item_type = True
            compulsory_counter += 1

        items.append(Item(
            item_id = item_id,
            weight = base_item,
            category = new_item_category,
            compulsory = new_item_type,
        ))

        i = i + 1

    items.sort(key=lambda x: x.weight, reverse=True)

    item_id = 1
    for item in items:
        item.item_id = item_id
        item_id += 1

    F = sum(item.weight for item in items if not item.compulsory)

    # Create bin types with capacities based on base_capacity and costs based on F
    bin_types = [
        {
            "id": 1,
            "capacity": round(base_capacity * BIN_TYPE_1_MULTIPLIER),
            "cost": round(F * BIN_TYPE_1_MULTIPLIER)
        },
        {
            "id": 2,
            "capacity": round(base_capacity * BIN_TYPE_2_MULTIPLIER),
            "cost": round(F * BIN_TYPE_2_MULTIPLIER)
        },
        {
            "id": 3,
            "capacity": round(base_capacity * BIN_TYPE_3_MULTIPLIER),
            "cost": round(F * BIN_TYPE_3_MULTIPLIER)
        },
    ]

    actual_n_items = len(items)
    instance_name = f"{instance_type}_{source_n_items}_{base_capacity}_{instance_id}"
    json_data = {
        "instance_name": instance_name,
        "instance_type": instance_type,
        "instance_id": instance_id,
        "source_n_items": source_n_items,
        "n_items": actual_n_items,
        "bin_types": bin_types,
        "items": [
            {
                "id": item.item_id,
                "weight": item.weight,
                "category": item.category,
                "compulsory": item.compulsory,
                "profit": item.profit
            }
            for item in items
        ]
    }

    output_dir = script_dir / instance_type
    output_dir.mkdir(exist_ok=True)

    output_path = output_dir / f"{instance_name}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2)
    
    return True

def main():
    script_dir = Path(__file__).resolve().parent
    base_datasets_dir = script_dir / "base_datasets"
    
    input_files = []
    for sub in ("ANI", "AI"):
        sub_dir = base_datasets_dir / sub
        if sub_dir.is_dir():
            input_files.extend(sorted(sub_dir.glob("*.txt")))
            input_files.extend(sorted(sub_dir.glob("*.TXT")))
    
    success_count = 0
    for input_path in input_files:
        if process_instance(input_path, script_dir):
            success_count += 1
            print(f"Processed: {input_path.name}")


if __name__ == "__main__":
    main()
