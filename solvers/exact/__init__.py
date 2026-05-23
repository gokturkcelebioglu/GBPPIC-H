from dataclasses import dataclass
from typing import Dict, List, Tuple

from pyomo.environ import Binary, ConcreteModel, Constraint, Objective, Param, RangeSet, Set, Var, minimize, value
from pyomo.opt import SolverFactory

from constants import COMPAT, CPLEX_EXECUTABLE, CPLEX_KEEPFILES, CPLEX_TEE, CPLEX_TIME_LIMIT
from models import Bin, Item, Solution, BinType
from read_dataset import read_dataset
from solvers import SolverStrategy
from solvers.utils import print_bin_results

import os
from pathlib import Path


@dataclass
class InstanceData:
    n_items: int
    items: List[Item]
    categories: List[int]
    bin_types: List[BinType]


class CPLEXSolver(SolverStrategy):
    def __init__(self, instance_path: str):
        super().__init__(instance_path)

    def get_name(self) -> str:
        return "CPLEX"

    def solve(self):
        data = self._load_data()
        model = self._build_model(data)

        solver = SolverFactory("cplex")
        if CPLEX_EXECUTABLE is not None:
            solver.set_executable(CPLEX_EXECUTABLE)

        workdir = Path("./cplex_work").resolve()
        workdir.mkdir(parents=True, exist_ok=True)
        os.environ["TMPDIR"] = str(workdir)

        if CPLEX_TIME_LIMIT is not None:
            solver.options["timelimit"] = int(CPLEX_TIME_LIMIT)

        # Conservative defaults for thesis-sized MIP runs.
        solver.options["workdir"] = str(workdir)

        solver.options["threads"] = 1                 
        solver.options["workmem"] = 8192              

        # solver.options["mip tolerances mipgap"] = 0.0093
        # solver.options["mip strategy file"] = 3
        solver.options["mip strategy file"] = 0
        # solver.options["mip limits treememory"] = 3072   
        # solver.options["emphasis memory"] = "y"

        results = solver.solve(model, tee=CPLEX_TEE, keepfiles=CPLEX_KEEPFILES)
        print(
            "Status:",
            results.solver.status,
            "Termination:",
            results.solver.termination_condition,
        )
        print("Objective:", value(model.Obj))
        
        solution = self._extract_solution(model, data)
        print_bin_results(solution)

        return solution

    def _load_data(self) -> InstanceData:
        n_items, items, bin_types = read_dataset(self.instance_path)
        categories = sorted({item.cat for item in items})
        return InstanceData(
            n_items=n_items,
            items=items,
            categories=categories,
            bin_types=bin_types,
        )

    def _build_model(self, data: InstanceData):
        model = ConcreteModel()

        # SETS
        item_ids = [item.idx for item in data.items]
        categories = data.categories  # sorted list of category labels

        # Upper bound on number of bins: use number of items
        model.I = RangeSet(1, data.n_items)
        model.J = Set(initialize=item_ids, ordered=True)
        model.C = Set(initialize=categories, ordered=True)

        # Bin types (heterogeneous)
        bin_type_ids = [bt.id for bt in data.bin_types]
        model.T = Set(initialize=bin_type_ids, ordered=True)

        # PARAMETERS
        # Bin type capacities and costs
        cap_map = {bt.id: bt.capacity for bt in data.bin_types}
        cost_map = {bt.id: bt.cost for bt in data.bin_types}
        model.Bt = Param(model.T, initialize=cap_map)   # capacity B_t
        model.Ft = Param(model.T, initialize=cost_map)  # fixed cost F_t

        # Compulsory / optional items
        compulsory_ids = [item.idx for item in data.items if item.compulsory]
        optional_ids = [item.idx for item in data.items if not item.compulsory]
        model.J_compulsory = Set(within=model.J, initialize=compulsory_ids)
        model.J_optional = Set(within=model.J, initialize=optional_ids)

        # Items by category
        cat_to_items: Dict[int, List[int]] = {}
        for item in data.items:
            cat_to_items.setdefault(item.cat, []).append(item.idx)
        model.J_by_cat = Set(model.C, initialize=lambda m, k: cat_to_items.get(k, []))

        # Item weights and revenues
        weight_map = {item.idx: item.w for item in data.items}
        revenue_map = {item.idx: item.r for item in data.items}
        model.w = Param(model.J, initialize=weight_map)
        model.r = Param(model.J, initialize=revenue_map, default=0)

        # Compatibility c[k,l] from COMPAT matrix
        # Map category labels to indices in COMPAT
        cat_index_map: Dict[int, int] = {cat: idx for idx, cat in enumerate(categories)}
        compatibility_dict: Dict[Tuple[int, int], int] = {}
        for cat_k in categories:
            for cat_l in categories:
                row = cat_index_map[cat_k]
                col = cat_index_map[cat_l]
                compatibility_dict[(cat_k, cat_l)] = int(COMPAT[row][col])
        model.c = Param(
            model.C,
            model.C,
            initialize=compatibility_dict,
            within=Binary,
            default=1,
        )

        # Unordered incompatible category pairs (k < l, c[k,l] == 0)
        incompatible_pairs = [
            (cat_k, cat_l)
            for cat_k in categories
            for cat_l in categories
            if cat_k < cat_l and compatibility_dict[(cat_k, cat_l)] == 0
        ]
        model.IncompatPairs = Set(initialize=incompatible_pairs, dimen=2)

        # Big-M per category = number of items in that category (at least 1)
        cat_counts = {k: len(cat_to_items.get(k, [])) for k in categories}
        for k in cat_counts:
            if cat_counts[k] < 1:
                cat_counts[k] = 1
        model.Mk = Param(model.C, initialize=cat_counts)

        # VARIABLES
        model.y = Var(model.I, within=Binary)                 # bin open
        model.x = Var(model.I, model.J, within=Binary)        # item assignment
        model.f = Var(model.I, model.C, within=Binary)        # category activation
        model.z = Var(model.I, model.T, within=Binary)        # bin type selection

        # OBJECTIVE
        #   Minimize sum(F_t * z[i,t]) - sum(r_j * x[i,j])
        def obj_rule(m):
            return (
                sum(m.Ft[t] * m.z[i, t] for i in m.I for t in m.T)
                - sum(m.r[j] * m.x[i, j] for i in m.I for j in m.J_optional)
            )

        model.Obj = Objective(rule=obj_rule, sense=minimize)

        # CONSTRAINTS

        # 1) Capacity:
        #    sum_j w_j * x[i,j] <= sum_t B_t * z[i,t]  for all bins i
        def capacity_rule(m, i):
            return sum(m.w[j] * m.x[i, j] for j in m.J) <= sum(
                m.Bt[t] * m.z[i, t] for t in m.T
            )

        model.Capacity = Constraint(model.I, rule=capacity_rule)

        # 1b) Bin-type linking:
        #     sum_t z[i,t] == y[i]  (exactly one type if bin is open, none otherwise)
        def bin_type_link_rule(m, i):
            return sum(m.z[i, t] for t in m.T) == m.y[i]

        model.BinTypeLink = Constraint(model.I, rule=bin_type_link_rule)

        # 2) Compulsory items: must be assigned exactly once
        def compulsory_assign_rule(m, j):
            if j in m.J_compulsory:
                return sum(m.x[i, j] for i in m.I) == 1
            return Constraint.Skip

        model.CompulsoryAssign = Constraint(model.J, rule=compulsory_assign_rule)

        # 3) Optional items: assigned at most once
        def optional_assign_rule(m, j):
            if j in m.J_optional:
                return sum(m.x[i, j] for i in m.I) <= 1
            return Constraint.Skip

        model.OptionalAssign = Constraint(model.J, rule=optional_assign_rule)

        # 4) Link item assignments to category activation:
        #    sum_{j in J_k} x[i,j] <= M_k * f[i,k]
        def link_xf_rule(m, i, k):
            items_in_k = list(m.J_by_cat[k])
            if len(items_in_k) == 0:
                # no items of this category exist: force f=0
                return m.f[i, k] == 0
            return sum(m.x[i, j] for j in items_in_k) <= m.Mk[k] * m.f[i, k]

        model.LinkXF = Constraint(model.I, model.C, rule=link_xf_rule)

        # 4b) Ensure category activation implies bin is open: f[i,k] <= y[i]
        def f_y_link_rule(m, i, k):
            return m.f[i, k] <= m.y[i]

        model.Flink = Constraint(model.I, model.C, rule=f_y_link_rule)

        # 5) Category incompatibility:
        #    for each incompatible pair (k,l) and bin i: f[i,k] + f[i,l] <= 1
        def incompat_rule(m, i, cat_k, cat_l):
            return m.f[i, cat_k] + m.f[i, cat_l] <= 1

        model.Incompat = Constraint(
            model.I, model.IncompatPairs, rule=incompat_rule
        )

        # 6) Item-to-bin linking: items can only be assigned to open bins
        #    x[i,j] <= y[i]  for all i, j
        #    This is implicitly enforced through category activation, but
        #    adding it explicitly strengthens the LP relaxation.
        def item_bin_link_rule(m, i, j):
            return m.x[i, j] <= m.y[i]

        model.ItemBinLink = Constraint(model.I, model.J, rule=item_bin_link_rule)

        # 7) Symmetry-breaking: y[i] >= y[i+1]
        def symmetry_rule(m, i):
            if i < max(m.I):
                return m.y[i] >= m.y[i + 1]
            return Constraint.Skip

        model.Symmetry = Constraint(model.I, rule=symmetry_rule)

        return model

    def _extract_solution(self, model: ConcreteModel, data: InstanceData):
        item_lookup: Dict[int, Item] = {item.idx: item for item in data.items}
        bin_type_lookup: Dict[int, BinType] = {bt.id: bt for bt in data.bin_types}

        bins: List[Bin] = []
        assigned_items = set()

        for i in model.I:
            if value(model.y[i]) >= 0.5:
                # Items assigned to bin i
                assigned = [j for j in model.J if value(model.x[i, j]) >= 0.5]
                if not assigned:
                    continue

                assigned_items.update(assigned)

                load = sum(item_lookup[j].w for j in assigned)
                cats = {item_lookup[j].cat for j in assigned}

                # Determine bin type from z[i,t]
                chosen_type_id = None
                for t in model.T:
                    if value(model.z[i, t]) >= 0.5:
                        chosen_type_id = int(t)
                        break

                if chosen_type_id is not None and chosen_type_id in bin_type_lookup:
                    bt = bin_type_lookup[chosen_type_id]
                    capacity = bt.capacity
                    bin_type_id = bt.id
                else:
                    # Fallback: use first bin type
                    bt = data.bin_types[0] if data.bin_types else None
                    capacity = bt.capacity if bt else 0
                    bin_type_id = bt.id if bt else 1

                bins.append(
                    Bin(
                        items=assigned,
                        load=load,
                        cats=cats,
                        bin_type_id=bin_type_id,
                        capacity=capacity,
                    )
                )

        all_items = set(model.J)
        unloaded = all_items - assigned_items

        obj_value = value(model.Obj)
        return Solution(
            bins=bins,
            unloaded=unloaded,
            obj=obj_value,
            used_bins=len(bins),
        )


__all__ = ["CPLEXSolver"]
