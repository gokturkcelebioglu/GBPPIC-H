# GBPPIC-H

Python implementation for a Master's thesis on the **Generalized Bin Packing
Problem under Category Incompatibilities and Heterogeneous Bins (GBPPIC-H)**.

The project combines an exact mixed-integer linear programming model with a
scalable Adaptive Large Neighborhood Search heuristic. It is intended to show
both the mathematical optimization formulation and the engineering work needed
to solve larger instances where an exact solver becomes impractical.

## Thesis Context

This project was developed as part of a Master's thesis in Industrial
Engineering at Başkent University.

Turkish thesis title:

```text
Heterojen Kutu Tipleri ve Kategori Uyuşmazlıkları Altında
Genelleştirilmiş Kutu Paketleme Problemi
```

English thesis title:

```text
Generalized Bin Packing Problem Under Category Incompatibilities
and Heterogeneous Bins
```

The thesis studies a realistic extension of bin packing where three modeling
features are handled together:

- **Heterogeneous bin types:** bins have different capacities and fixed costs.
- **Category incompatibilities:** some item categories cannot be placed in the
  same bin.
- **Compulsory and optional items:** compulsory items must be packed; optional
  items may be packed if their revenue justifies the additional bin cost.

## Why This Problem Matters

Classic bin packing assumes items are placed into identical bins while
respecting capacity. Real logistics and storage decisions are often messier:
vehicles or containers can have different capacities and costs, some products
cannot travel together, and some jobs or items are optional because they create
extra revenue only if there is enough capacity.

GBPPIC-H models this richer setting. It is relevant to applications such as:

- Logistics and load planning with multiple vehicle or container types.
- Storage planning where product categories have compatibility restrictions.
- Distribution operations where some shipments are mandatory and others are
  optional revenue opportunities.
- Decision support systems that need to balance cost, feasibility, and service
  value.

## Problem Definition

Each item has:

- a weight,
- a category,
- a compulsory or optional status,
- and a revenue value if the item is optional.

Each bin type has:

- a capacity,
- and a fixed cost.

The solution decides:

- which bins to use,
- which bin type each used bin should have,
- which items should be assigned to which bins,
- which optional items should remain unpacked,
- and which item categories are active in each bin.

The objective is:

```text
minimize total fixed cost of used bins - revenue from loaded optional items
```

A feasible solution must satisfy:

- every compulsory item is packed exactly once,
- every optional item is packed at most once,
- bin capacity is not exceeded,
- incompatible categories are not assigned to the same bin,
- every used bin selects exactly one bin type,
- and all assignments are internally consistent.

## Solution Approaches

This repository implements two solvers.

### Exact MILP Solver

The exact solver is implemented with Pyomo and solved with IBM ILOG CPLEX. It
models:

- item-to-bin assignment,
- bin opening decisions,
- heterogeneous bin type selection,
- category activation per bin,
- category incompatibility constraints,
- compulsory item assignment,
- optional item assignment,
- and the cost-minus-revenue objective.

The exact model is useful for validating the formulation and comparing solution
quality on smaller instances. Its limitation is scalability: as the number of
items grows, CPLEX may spend most of the time in the root relaxation or fail to
produce a feasible solution within the time limit.

### ALNS Heuristic Solver

The heuristic solver is based on **Adaptive Large Neighborhood Search (ALNS)**.
It is designed for larger GBPPIC-H instances where exact optimization becomes
too slow.

The ALNS flow is:

1. Build an initial feasible solution with a GRASP-style first-fit decreasing
   repair heuristic.
2. Select destroy and repair operators using adaptive roulette-wheel selection.
3. Apply partial destroy, full destroy, repair, and local search operators.
4. Evaluate the candidate solution with the cost-minus-revenue objective.
5. Accept or reject the candidate using simulated annealing.
6. Update operator weights from segment-level rewards.
7. Restart from the best solution or rebuild a solution when the search
   stagnates.

## Implemented ALNS Operators

Full destroy operators:

- remove bins with the highest optional-item weight,
- remove least-occupied bins,
- remove random bins,
- remove bins that contain only optional items.

Partial destroy operators:

- remove random items from bins,
- remove the lightest category from each bin,
- remove a random category from each bin,
- remove all optional items.

Repair operators:

- GRASP first-fit decreasing,
- first-fit decreasing by weight,
- first-fit decreasing by descending compatibility degree,
- first-fit decreasing by ascending compatibility degree.

Local search operators:

- swap with unloaded compulsory items,
- swap items between bins,
- downgrade bin type when a cheaper feasible type exists,
- merge bins when the merged bin reduces fixed cost.

## Contributions

This project contributes:

- an integrated MILP formulation for GBPPIC-H,
- a Python implementation of an ALNS heuristic tailored to heterogeneous bins
  and category incompatibilities,
- a generated benchmark dataset format for the problem,
- feasibility validation utilities,
- result export utilities for experiment tracking,
- and a computational comparison between ALNS and CPLEX.

## Repository Structure

```text
.
├── main.py                    # CLI entry point
├── constants.py               # Solver parameters and compatibility matrix
├── models.py                  # Item, bin, and solution data classes
├── read_dataset.py            # JSON instance reader
├── requirements.txt           # Python dependencies
├── datasets/
│   ├── generator.py           # Converts optional base text instances to JSON
│   ├── AI/                    # Generated AI JSON instances
│   └── ANI/                   # Generated ANI JSON instances
└── solvers/
    ├── alns/                  # ALNS heuristic and operators
    ├── exact/                 # Pyomo/CPLEX exact formulation
    └── utils.py               # Feasibility and reporting helpers
```

## Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Check the command-line interface:

```bash
python main.py --help
```

## Running ALNS

Run ALNS on a sample instance:

```bash
python main.py --solver alns --instance datasets/AI/AI_201_2500_0.json
```

Run a short ALNS demo without writing Excel output:

```bash
python main.py --solver alns --instance datasets/AI/AI_201_2500_0.json --iterations 10 --quiet --no-save-summary
```

Export detailed bin assignments:

```bash
python main.py --solver alns --instance datasets/AI/AI_201_2500_0.json --save-bins
```

Useful ALNS CLI options:

- `--iterations`: override the ALNS iteration count without editing
  `constants.py`.
- `--seed`: set the ALNS random seed.
- `--quiet`: suppress iteration progress and final bin-level output.
- `--no-save-summary`: skip the aggregate Excel summary file.
- `--save-bins`: export detailed bin assignments under `results/`.

The aggregate summary is written to `results.xlsx`. Detailed bin exports are
written under `results/`. Both are generated artifacts and ignored by git.

## Running CPLEX

The exact solver requires IBM ILOG CPLEX. If `cplex` is already available on
your `PATH`, run:

```bash
python main.py --solver cplex --instance datasets/AI/AI_201_2500_0.json
```

If CPLEX is installed elsewhere, configure the executable path:

```bash
export GBPPIC_CPLEX_EXECUTABLE="/path/to/cplex"
python main.py --solver cplex --instance datasets/AI/AI_201_2500_0.json
```

Optional environment variables:

```bash
export GBPPIC_CPLEX_TIME_LIMIT=3600
export GBPPIC_CPLEX_TEE=true
export GBPPIC_CPLEX_KEEPFILES=false
export GBPPIC_RESULTS_FILE=results.xlsx
```

## Dataset

The repository includes generated JSON instances used by the solver. The raw
base text files are not required to run the project.

Each generated instance contains:

- `instance_name`,
- `instance_type`,
- `instance_id`,
- `source_n_items`,
- `n_items`,
- `bin_types`,
- and `items`.

The `source_n_items` field preserves the item-count label from the original
benchmark filename. The `n_items` field stores the actual number of item records
in the generated JSON file.

If raw base text files are available, place them under
`datasets/base_datasets/AI/` and `datasets/base_datasets/ANI/`, then regenerate
the JSON instances:

```bash
python datasets/generator.py
```

The dataset contains 500 generated instances across two instance classes:

- `AI`
- `ANI`

Each instance uses three heterogeneous bin types derived from the base capacity:

- type 1: 0.75x base capacity,
- type 2: 1.00x base capacity,
- type 3: 1.25x base capacity.

## Experimental Setup

The thesis experiments compare ALNS and CPLEX on representative samples from
both instance classes and multiple size groups. ALNS is stochastic, so repeated
runs were used in the thesis experiments. CPLEX was run with:

- one thread,
- 4096 MB memory setting,
- and a 3600 second time limit for comparison experiments.

Lower objective values are better because the objective minimizes bin cost minus
loaded optional-item revenue.

## Experimental Results

Average ALNS and CPLEX comparison by actual item count:

| Items | ALNS objective | ALNS optional weight | ALNS time | CPLEX objective | CPLEX optional weight | CPLEX time | Objective difference |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 202 | 1,373,657.0 | 35.2 | 1.43s | 1,378,239.6 | 1,108.0 | 3601.40s | -4,582.6 |
| 203 | 1,416,610.6 | 74.8 | 1.53s | 1,422,028.2 | 1,149.6 | 3601.50s | -5,417.6 |
| 403 | 16,562,871.6 | 454.8 | 5.08s | 29,878,109.4 | 16,001.8 | 3603.55s | -13,315,237.8 |
| 404 | 16,815,445.8 | 225.6 | 6.06s | 17,212,021.4 | 16,605.4 | 3603.64s | -396,575.6 |
| 601 | 70,687,687.0 | 554.0 | 10.06s | 220,980,000.0 | 73,660.0 | 3607.07s | -150,292,313.0 |
| 602 | 72,265,054.8 | 565.4 | 10.84s | 231,613,358.0 | 75,938.8 | 3607.20s | -159,348,303.2 |
| 802 | 237,270,186.6 | 5,273.8 | 24.63s | no feasible solution | no feasible solution | 3612.20s | n/a |
| 803 | 238,859,655.4 | 4,357.2 | 24.45s | no feasible solution | no feasible solution | 3612.31s | n/a |
| 1003 | 725,071,499.2 | 3,876.8 | 29.76s | no feasible solution | no feasible solution | 3619.08s | n/a |
| 1004 | 726,990,439.6 | 4,165.6 | 29.51s | no feasible solution | no feasible solution | 3619.19s | n/a |

CPLEX feasibility summary:

| Items | Feasible CPLEX runs | Root relaxation time | Node count | MIP gap |
| ---: | ---: | ---: | ---: | ---: |
| 202 | 5/5 | 36.05-39.71s | 49,413-398,793 | approximately 1.12% |
| 203 | 5/5 | 38.24-52.25s | 88,185-935,590 | approximately 1.15% |
| 403 | 5/5 | 615.32-3597.18s | 0-710 | not reported |
| 404 | 5/5 | 1167.33-1962.77s | 0-1084 | approximately 2.72% |
| 601 | 1/5 | approximately 3592s | approximately 0 | not reported |
| 602 | 1/5 | approximately 3592s | approximately 0 | not reported |
| 802 | 0/5 | approximately 3585s | 0 | not applicable |
| 803 | 0/5 | approximately 3585s | 0 | not applicable |
| 1003 | 0/5 | approximately 3576s | 0 | not applicable |
| 1004 | 0/5 | approximately 3576s | 0 | not applicable |

## Result Interpretation

The exact CPLEX model is useful for small and medium-size instances, where it
can produce feasible solutions within the time limit. However, runtime grows
quickly as instance size increases. For 601 and 602 item groups, CPLEX produced
feasible solutions in only one out of five representative runs. For 802 and
larger item groups, CPLEX did not produce feasible solutions within the 3600
second time limit in the reported experiments.

The ALNS solver produced feasible solutions for every reported size group in
seconds. This is the main engineering result of the project: the repository
contains both a mathematically explicit exact model and a scalable heuristic for
larger problem instances.

## Reproducibility

The global random seed is defined in `constants.py`. ALNS parameters, operator
toggles, simulated annealing settings, and the category compatibility matrix are
centralized in the same file.

Generated result files are intentionally ignored:

- `results.xlsx`
- `results/`
- `cplex_work/`
- CPLEX temporary files such as `.lp`, `.log`, `.mps`, `.nl`, and `.sol`
