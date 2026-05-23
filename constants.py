import os
from pathlib import Path
from typing import List, Optional


def _int_from_env(name: str, default: Optional[int]) -> Optional[int]:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def _bool_from_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.lower() in {"1", "true", "yes", "on"}


# Solver configuration
CPLEX_TIME_LIMIT = _int_from_env("GBPPIC_CPLEX_TIME_LIMIT", 3600)  # seconds
CPLEX_EXECUTABLE = os.getenv("GBPPIC_CPLEX_EXECUTABLE") or None
CPLEX_KEEPFILES = _bool_from_env("GBPPIC_CPLEX_KEEPFILES", False)
CPLEX_TEE = _bool_from_env("GBPPIC_CPLEX_TEE", True)


# Global seed for reproducibility
SEED = 0

# Results file path
RESULTS_FILE = Path(os.getenv("GBPPIC_RESULTS_FILE", "results.xlsx"))

# N

# ALNS Parameters
ALNS_PARAMS = {
    # Destruction parameters
    "alpha": 0.05,
    "beta": 0.25,
    "gamma": 0.01,

    # Iteration control
    "N": 5000,
    "Ns": 5,
    "N_nic": 10,
    "N_t": 300,
    "N_nib": 500,

    # Adaptive weights
    "rho": 0.1,

    # Simulated annealing
    "use_simulated_annealing": True,  # Enable/disable simulated annealing acceptance
    "cooling": 0.999,
    "w": 0.35,

    # GRASP restricted candidate list (Rmin, Rmax)
    "grasp_R": (5, 10),
    
    # Validation (set to True for debugging, False for performance)
    "validate_operators": False,  # Validate after each operator
    
    # Output control
    "print_iteration_results": True,  # Print iteration progress every x iterations
    "print_bin_results": True,  # Print bin results at the end
    
    # Partial destroy operators (Ωd1-Ωd4)
    "use_omega_d1": True,  # Random items per bin
    "use_omega_d2": True,  # Lightest category per bin
    "use_omega_d3": True,  # Random category per bin
    "use_omega_d4": True,  # All non-compulsory items
    
    # Full destroy operators (Ωk1-Ωk4)
    "use_omega_k1": True,  # Highest non-compulsory weight
    "use_omega_k2": True,  # Least occupied bins
    "use_omega_k3": True,  # Random bins
    "use_omega_k4": True,  # Bins containing only non-compulsory items
    
    # Repair operators (Ω+1-Ω+4)
    "use_omega_plus1": True,  # GRASP FFD
    "use_omega_plus2": True,  # FFD by weight
    "use_omega_plus3": True,  # FFD desc compatibility
    "use_omega_plus4": True,  # FFD asc compatibility
    
    # Local search operators (LS1-LS4)
    "use_ls1": True,  # Swap with unloaded
    "use_ls2": True,  # Swap between bins
    "use_ls3": True,  # Bin type downgrade
    "use_ls4": True,  # Bin merging
    
    # Reward values (sigma)
    "sigma": {
        "best": 3,      # σ1: new global best
        "improve": 2,   # σ2: accepted improving move
        "worse": 1,     # σ3: accepted worsening move
    },
}

# Category Incompatibility Matrix
COMPAT: List[List[int]] = [
    # C1 C2 C3 C4 C5 C6
    [ 1, 0, 1, 0, 0, 0],  # C1
    [ 0, 1, 0, 1, 1, 1],  # C2
    [ 1, 0, 1, 1, 0, 0],  # C3
    [ 0, 1, 1, 1, 1, 1],  # C4
    [ 0, 1, 0, 1, 1, 0],  # C5
    [ 0, 1, 0, 1, 0, 1],  # C6
]
