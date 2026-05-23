import random
import math


class SA:
    """Simulated Annealing acceptance criterion."""
    
    def __init__(self, initial_solution: float, w: float, cooling: float):
        self.initial_solution = initial_solution
        self.t = None
        self.w = w
        self.cooling = cooling

    def start(self):
        """Initialize temperature T0 so that a relative worsening of w is accepted with probability 0.5 at the start."""
        self.t = self.initial_solution * self.w / math.log(2)

    def cool(self):
        if self.t is not None:
            self.t *= self.cooling

    def accept(self, f_curr: int, f_next: int) -> bool:
        # Always accept if not worse
        if f_next <= f_curr:
            return True
        if self.t is None or self.t <= 0:
            return False
            
        delta = f_next - f_curr
        p = math.exp(-delta / self.t)
        return random.random() < p

