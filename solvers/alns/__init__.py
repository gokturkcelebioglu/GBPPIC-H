import random
from typing import List

from models import Solution, Item, BinType
from read_dataset import read_dataset
from solvers import SolverStrategy
from solvers.utils import print_bin_results
from constants import ALNS_PARAMS, SEED

from .acceptance import SA
from .adaptive import AdaptiveChooser

from .methods.destroy_partial import (destroy_random_items_per_bin, destroy_lightest_category_per_bin, destroy_random_category_per_bin, destroy_all_noncompulsory_items)
from .methods.destroy_full import (destroy_bins_highest_noncomp_weight, destroy_bins_least_occupied, destroy_bins_random, destroy_bins_only_noncompulsory)
from .methods.repair import (repair_grasp_ffd, repair_ffd_by_weight, repair_ffd_desc_compatibility, repair_ffd_asc_compatibility)
from .methods.local_search import (ls1, ls2, ls3, ls4)
from .helpers import _validate_solution_integrity, _clone_solution, evaluate

def _get_partial_destroy_ops(params):
    return {
        "Ωd1": lambda s, items: destroy_random_items_per_bin(s, items, params["alpha"]),
        "Ωd2": lambda s, items: destroy_lightest_category_per_bin(s, items),
        "Ωd3": lambda s, items: destroy_random_category_per_bin(s, items),
        "Ωd4": lambda s, items: destroy_all_noncompulsory_items(s, items),
    }

def _get_full_destroy_ops(params):
    return {
        "Ωk1": lambda s, items: destroy_bins_highest_noncomp_weight(s, items, params["beta"]),
        "Ωk2": lambda s, items: destroy_bins_least_occupied(s, items, params["beta"]),
        "Ωk3": lambda s, items: destroy_bins_random(s, items, params["gamma"]),
    }

def _get_repair_ops(params):
    return {
        "Ω+1": lambda s, items, bin_types, use_noncomp: repair_grasp_ffd(s, items, bin_types, params["grasp_R"], use_noncomp),
        "Ω+2": lambda s, items, bin_types, use_noncomp: repair_ffd_by_weight(s, items, bin_types, use_noncomp),
        "Ω+3": lambda s, items, bin_types, use_noncomp: repair_ffd_desc_compatibility(s, items, bin_types, use_noncomp),
        "Ω+4": lambda s, items, bin_types, use_noncomp: repair_ffd_asc_compatibility(s, items, bin_types, use_noncomp),
    }

def apply_partial_destroy(s, operator: str, items, params):
    ops = _get_partial_destroy_ops(params)
    return ops.get(operator, lambda s, items: s)(s, items)

def apply_full_destroy(s, operator: str, items, params):
    ops = _get_full_destroy_ops(params)
    return ops.get(operator, ops["Ωk3"])(s, items)

def apply_repair(s, operator: str, items, bin_types: List[BinType], use_noncomp: bool, params):
    ops = _get_repair_ops(params)
    return ops.get(operator, ops["Ω+4"])(s, items, bin_types, use_noncomp)

class ALNSSolver(SolverStrategy):
    def __init__(self, instance_path: str):
        super().__init__(instance_path)

    def get_name(self) -> str:
        return "ALNS"

    def solve(self, ALNS_PARAMS: dict = ALNS_PARAMS, seed: int = SEED) -> Solution:
        random.seed(seed)
        n, items, bin_types = read_dataset(self.instance_path)
        
        # Get print flags from ALNS_PARAMS
        print_iteration_results = ALNS_PARAMS.get("print_iteration_results", True)
        print_bin_results_flag = ALNS_PARAMS.get("print_bin_results", True)

        # Initial solution - use GRASP FFD (Ω+1)
        s = repair_grasp_ffd(self._empty_solution(n), items, bin_types, ALNS_PARAMS["grasp_R"], use_noncomp = False)
        s.obj = evaluate(s.bins, s.unloaded, items, bin_types)
        s.used_bins = len(s.bins)
        best = _clone_solution(s)

        if print_iteration_results:
            print(f"Initial solution: {best.obj}")

        # Build operator lists - filter based on enabled operators
        d_ops = self._build_operator_list("omega_d",    ["Ωd1", "Ωd2", "Ωd3", "Ωd4"], ["Ωd1"], ALNS_PARAMS)
        k_ops = self._build_operator_list("omega_k",    ["Ωk1", "Ωk2", "Ωk3"],        ["Ωk3"], ALNS_PARAMS)
        r_ops = self._build_operator_list("omega_plus", ["Ω+1", "Ω+2", "Ω+3", "Ω+4"], ["Ω+4"], ALNS_PARAMS)

        choose_d = AdaptiveChooser(d_ops, rho = ALNS_PARAMS["rho"])
        choose_k = AdaptiveChooser(k_ops, rho = ALNS_PARAMS["rho"])
        choose_r = AdaptiveChooser(r_ops, rho = ALNS_PARAMS["rho"])

        # Initialize simulated annealing if enabled
        use_sa = ALNS_PARAMS.get("use_simulated_annealing", True)
        sa = None
        if use_sa:
            sa = SA(initial_solution = best.obj, w = ALNS_PARAMS["w"], cooling = ALNS_PARAMS["cooling"])
            sa.start()

        it, since_inc, since_best = 0, 0, 0
        sigma = ALNS_PARAMS["sigma"]

        if print_iteration_results:
            print(f"Starting ALNS: N={ALNS_PARAMS['N']} iterations")
            
        while it < ALNS_PARAMS["N"]:
            it += 1
            if print_iteration_results and it % 100 == 0:
                print(f"Iteration {it}/{ALNS_PARAMS['N']}: best_obj = {best.obj}, current_obj = {s.obj}", flush = True)

            use_noncomp = it > ALNS_PARAMS["N_t"]

            # Pick operators
            d = choose_d.choose()
            k = choose_k.choose()
            r = choose_r.choose()

            s1 = _clone_solution(s)
            s1 = self._apply_iteration_ops(s1, d, k, r, items, bin_types, use_noncomp, ALNS_PARAMS)

            # Evaluate & acceptance
            f_curr = s.obj
            f_next = evaluate(s1.bins, s1.unloaded, items, bin_types)

            accepted = sa.accept(f_curr, f_next) if use_sa else (f_next <= f_curr)

            if accepted:
                reward = sigma["best"] if f_next < best.obj else (sigma["improve"] if f_next < f_curr else sigma["worse"])
                choose_d.reward(d, reward)
                choose_k.reward(k, reward)
                choose_r.reward(r, reward)
                s = s1
                s.obj = f_next
                s.used_bins = len(s.bins)
                
                # Update best solution if the accepted solution is better
                if f_next < best.obj:
                    best = _clone_solution(s)
                    since_best = 0
                else:
                    since_best += 1
            else:
                since_best += 1

            # Segment updates
            if it % ALNS_PARAMS["Ns"] == 0:
                choose_d.update()
                choose_k.update()
                choose_r.update()
                if use_sa:
                    sa.cool()

            # Update counter for iterations without improvement to current solution
            # Improvement means: accepted solution is better than what we started with
            improved = accepted and f_next < f_curr
            if improved:
                since_inc = 0
            else:
                since_inc += 1

            # Restart / Reheat
            if since_inc >= ALNS_PARAMS["N_nic"]:
                use_noncomp_restart = it > ALNS_PARAMS["N_t"]
                if random.random() < 0.8:
                    s = _clone_solution(best)
                else:
                    # Use operator without tracking (restart is escape mechanism, not normal search)
                    s = apply_repair(self._empty_solution(n), choose_r.choose_without_tracking(), items, bin_types, use_noncomp_restart, ALNS_PARAMS)
                s.obj = evaluate(s.bins, s.unloaded, items, bin_types)
                s.used_bins = len(s.bins)
                since_inc = 0

            if since_best >= ALNS_PARAMS["N_nib"]:
                break

        if print_bin_results_flag:
            print_bin_results(best)

        return best

    @staticmethod
    def _empty_solution(n: int) -> Solution:
        return Solution(bins = [], unloaded = set(range(n)), obj = 0, used_bins = 0)

    @staticmethod
    def _build_operator_list(prefix: str, operators: List[str], defaults: List[str], params: dict) -> List[str]:
        """Build operator list based on ALNS_PARAMS flags."""
        enabled = [op for i, op in enumerate(operators) 
                   if params.get(f"use_{prefix}{i+1}", True)]
        return enabled if enabled else defaults

    def _validate_if_enabled(self, s: Solution, items: List[Item], context: str, params: dict) -> bool:
        """Validate solution if validation is enabled. Returns True if valid or validation disabled."""
        if not params.get("validate_operators", False):
            return True
        is_valid, errors = _validate_solution_integrity(s, items, context)
        if not is_valid:
            print(f"WARNING: Solution invalid {context}: {errors}")
        return is_valid

    def _apply_iteration_ops(self, s: Solution, d: str, k: str, r: str, items, bin_types, use_noncomp: bool, params: dict) -> Solution:
        s1 = apply_partial_destroy(s, d, items, params)
        if not self._validate_if_enabled(s1, items, f"after_destroy_{d}", params):
            return _clone_solution(s)
        
        s1 = apply_full_destroy(s1, k, items, params)
        
        if params.get("use_omega_k4", True):
            s1 = destroy_bins_only_noncompulsory(s1, items)
        
        if params.get("use_ls1", True):
            s1 = ls1(s1, items, use_noncomp=use_noncomp)
        
        s1 = apply_repair(s1, r, items, bin_types, use_noncomp, params)
        if not self._validate_if_enabled(s1, items, f"after_repair_{r}", params):
            return _clone_solution(s)

        if params.get("use_ls2", True):
            s1 = ls2(s1, items, use_noncomp=use_noncomp)
        if params.get("use_ls4", True):
            s1 = ls4(s1, items, bin_types)
        if params.get("use_ls3", True):
            s1 = ls3(s1, items, bin_types)
        
        if not self._validate_if_enabled(s1, items, "after_all_ops", params):
            return _clone_solution(s)
        
        return s1

__all__ = ["ALNSSolver"]
