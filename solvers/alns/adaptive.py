import random
from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class AdaptiveChooser:
    """
    Adaptive operator selection mechanism using roulette wheel selection.
    
    Tracks operator performance and adjusts selection weights based on rewards.
    """
    names: List[str]
    eta: Dict[str, float] = field(default_factory=dict)  # operator weights
    pi: Dict[str, float] = field(default_factory=dict)   # total reward in segment
    tau: Dict[str, int] = field(default_factory=dict)    # num uses in segment
    rho: float = 0.1                                     # reaction factor

    def __post_init__(self):
        """Initialize default values for all operators."""
        for n in self.names:
            self.eta.setdefault(n, 1.0)
            self.pi.setdefault(n, 0.0)
            self.tau.setdefault(n, 0)

    def choose(self) -> str:
        """Choose an operator based on current weights (eta) using roulette wheel."""
        if not self.names:
            raise ValueError("Cannot choose from empty operator list")
        
        total = sum(self.eta.values())
        if total <= 0:
            # All weights are zero or negative - reset all weights to 1.0
            for k in self.names:
                self.eta[k] = 1.0
            total = len(self.names)
        
        r = random.random() * total
        acc = 0.0
        chosen_name = self.names[-1]  # Default to last in case of rounding
        # Iterate in the provided names order for deterministic tie behavior
        for k in self.names:
            w = self.eta[k]
            acc += w
            if r <= acc:
                chosen_name = k
                break

        # Track usage for this segment
        self.tau[chosen_name] += 1
        return chosen_name

    def choose_without_tracking(self) -> str:
        """Choose an operator without tracking usage (e.g., for restart operations)."""
        if not self.names:
            raise ValueError("Cannot choose from empty operator list")
        
        total = sum(self.eta.values())
        if total <= 0:
            # All weights are zero or negative - reset all weights to 1.0
            for k in self.names:
                self.eta[k] = 1.0
            total = len(self.names)
        
        r = random.random() * total
        acc = 0.0
        chosen_name = self.names[-1]  # Default to last in case of rounding
        # Iterate in the provided names order for deterministic tie behavior
        for k in self.names:
            w = self.eta[k]
            acc += w
            if r <= acc:
                chosen_name = k
                break
        # Don't track usage - this is for restart/escape mechanisms
        return chosen_name

    def reward(self, name: str, sigma: float):
        """Add reward 'sigma' to the operator 'name' for this segment."""
        self.pi[name] += sigma

    def update(self):
        """
        Update operator weights (eta) based on average reward, per Eq. (10).
        eta_a <- (1 - rho) * eta_a + rho * (pi_a / tau_a); then reset pi and tau.
        """
        for k in self.names:
            # Calculate average reward: pi / tau
            # If tau is 0, operator was not used, so avg_reward is 0.
            avg_reward = self.pi[k] / self.tau[k] if self.tau[k] > 0 else 0.0

            # Update weight (eta) using average reward
            self.eta[k] = (1.0 - self.rho) * self.eta[k] + self.rho * avg_reward

            # Reset segment counters
            self.pi[k] = 0.0
            self.tau[k] = 0

