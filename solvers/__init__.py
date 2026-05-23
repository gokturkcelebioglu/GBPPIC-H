from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Dict, List

from models import Solution


class SolverStrategy(ABC):
    """Base class for all solver strategies."""

    def __init__(self, instance_path: str) -> None:
        self.instance_path = instance_path

    @abstractmethod
    def get_name(self) -> str:
        """Return human-readable solver name."""

    @abstractmethod
    def solve(self) -> Solution:
        """Execute solver and return a Solution."""

FactoryFunc = Callable[[str], SolverStrategy]


def _create_alns_solver(instance_path: str) -> SolverStrategy:
    from .alns import ALNSSolver

    return ALNSSolver(instance_path)


def _create_cplex_solver(instance_path: str) -> SolverStrategy:
    try:
        from .exact import CPLEXSolver
    except ModuleNotFoundError as exc:
        if exc.name == "pyomo":
            raise RuntimeError(
                "The CPLEX solver requires Pyomo. Install dependencies with "
                "`pip install -r requirements.txt` before using `--solver cplex`."
            ) from exc
        raise

    return CPLEXSolver(instance_path)


def _build_factories() -> Dict[str, FactoryFunc]:
    return {
        "alns": _create_alns_solver,
        "cplex": _create_cplex_solver,
    }

_SOLVER_FACTORIES: Dict[str, FactoryFunc] = _build_factories()

def available_solvers() -> List[str]:
    """List available solver names."""

    return sorted(_SOLVER_FACTORIES.keys())

def create_solver(name: str, instance_path: str) -> SolverStrategy:
    """Instantiate a solver strategy by factory name."""

    key = name.lower()
    try:
        factory = _SOLVER_FACTORIES[key]
    except KeyError as exc:
        raise ValueError(
            f"Unknown solver '{name}'. Available solvers: {', '.join(available_solvers())}"
        ) from exc
    return factory(instance_path)

# Re-export utility functions for convenience
from .utils import check_feasibility, print_bin_results

__all__ = [
    "SolverStrategy",
    "create_solver",
    "available_solvers",
    "check_feasibility",
    "print_bin_results",
]
