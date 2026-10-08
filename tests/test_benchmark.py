"""Performance canary: fails only if a run regresses past a hard ceiling.

Guards against an accidental per-pixel Python loop. A plain pytest test, so it
needs no extra dependency.
"""

import logging
import time

import numpy as np

from soil_moisture_model import simulate

N_WEEKS = 520  # 10 years
N_PIXELS = 10_000
MAX_SECONDS = 1.5  # about 4x the first measured runtime (0.36 s); see the commit log


def test_block_runtime():
    rng = np.random.default_rng(0)
    shape = (N_WEEKS, N_PIXELS)
    args = (
        rng.uniform(-10.0, 30.0, shape),
        rng.gamma(1.5, 15.0, shape),
        rng.uniform(0.0, 600.0, shape),
        rng.uniform(0.0, 3000.0, N_PIXELS),
        rng.uniform(0.0, 80.0, N_PIXELS),
    )
    start = time.perf_counter()
    simulate(*args)
    elapsed = time.perf_counter() - start
    logging.getLogger(__name__).info("simulate %s: %.3f s", shape, elapsed)
    assert elapsed < MAX_SECONDS
