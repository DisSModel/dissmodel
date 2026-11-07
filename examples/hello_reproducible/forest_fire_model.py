# forest_fire_model.py
import numpy as np
from dissmodel.geo import SyncRasterModel

FOREST, BURNING, BURNED = 0, 1, 2


class ForestFire(SyncRasterModel):
    def setup(self, backend, prob_spread=0.4, seed=42):
        super().setup(backend)
        self.land_use_types = ["state"]       # bands kept as state_past
        self.prob_spread = prob_spread
        self.rng = np.random.default_rng(seed)

    def execute(self):                        # once per step: only maths, no I/O
        past = self.backend.get("state_past")
        burning_neighbours = self.backend.focal_sum_mask(past == BURNING)
        catch = (past == FOREST) & (
            self.rng.random(self.shape) < 1 - (1 - self.prob_spread) ** burning_neighbours
        )
        state = past.copy()
        state[catch] = BURNING
        state[past == BURNING] = BURNED
        self.backend.arrays["state"] = state
