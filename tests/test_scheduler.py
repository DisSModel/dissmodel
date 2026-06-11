"""
tests/core/test_scheduler.py
=============================
Test suite for the Environment / Model time-stepped scheduler.

Time semantics: ``end_time`` is INCLUSIVE (TerraME-style) — every
scheduled tick ``t`` with ``start_time <= t <= end_time`` executes,
both for the environment window and for each model's own window.

Covers:
- Clock accuracy and boundaries
- Model start_time / end_time constraints
- Multi-model heterogeneous step sizes
- Lifecycle hooks (setup, pre_execute, execute, post_execute)
- Edge cases: single tick, empty environment, re-run
"""
from __future__ import annotations

import math
import pytest

from dissmodel.core import Environment, Model


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class Recorder(Model):
    """Model that records every tick it executes."""

    def setup(self, **kwargs):
        self.ticks: list[float] = []
        self.pre_ticks: list[float] = []
        self.post_ticks: list[float] = []

    def pre_execute(self):
        self.pre_ticks.append(self.env.now())

    def execute(self):
        self.ticks.append(self.env.now())

    def post_execute(self):
        self.post_ticks.append(self.env.now())


# ---------------------------------------------------------------------------
# Clock
# ---------------------------------------------------------------------------

class TestClock:
    def test_now_returns_start_time_before_run(self):
        env = Environment(start_time=2010, end_time=2015)
        assert env.now() == 2010

    def test_now_advances_correctly(self):
        ticks = []

        class Capture(Model):
            def setup(self, **kwargs): pass
            def execute(self): ticks.append(self.env.now())

        env = Environment(start_time=0, end_time=5)
        Capture(step=1)
        env.run()
        assert ticks == [0, 1, 2, 3, 4, 5]

    def test_end_time_is_inclusive(self):
        """Last tick must be end_time itself (TerraME semantics)."""
        ticks = []

        class Capture(Model):
            def setup(self, **kwargs): pass
            def execute(self): ticks.append(self.env.now())

        env = Environment(start_time=0, end_time=3)
        Capture(step=1)
        env.run()
        assert max(ticks) == 3
        assert 3 in ticks
        assert 4 not in ticks

    def test_start_time_offset(self):
        """start_time=2010 means first tick is at 2010, not 0."""
        ticks = []

        class Capture(Model):
            def setup(self, **kwargs): pass
            def execute(self): ticks.append(self.env.now())

        env = Environment(start_time=2010, end_time=2013)
        Capture(step=1)
        env.run()
        assert ticks == [2010, 2011, 2012, 2013]

    def test_fractional_step(self):
        ticks = []

        class Capture(Model):
            def setup(self, **kwargs): pass
            def execute(self): ticks.append(self.env.now())

        env = Environment(start_time=0, end_time=1)
        Capture(step=0.25)
        env.run()
        assert len(ticks) == 5
        assert abs(ticks[-1] - 1.0) < 1e-9

    def test_till_overrides_end_time(self):
        ticks = []

        class Capture(Model):
            def setup(self, **kwargs): pass
            def execute(self): ticks.append(self.env.now())

        env = Environment(start_time=0, end_time=100)
        Capture(step=1)
        env.run(till=3)
        assert max(ticks) == 3

    def test_run_raises_without_end_time(self):
        env = Environment(start_time=0)

        class Noop(Model):
            def setup(self, **kwargs): pass

        Noop(step=1)
        with pytest.raises(ValueError, match="end_time"):
            env.run()


# ---------------------------------------------------------------------------
# Model start_time / end_time
# ---------------------------------------------------------------------------

class TestModelBoundaries:
    def test_model_start_time_respected(self):
        env = Environment(start_time=2010, end_time=2016)
        a = Recorder(start_time=2012)
        env.run()
        assert all(t >= 2012 for t in a.ticks)
        assert 2010 not in a.ticks
        assert 2011 not in a.ticks

    def test_model_end_time_respected(self):
        """Model end_time is inclusive: last execution at t == end_time."""
        env = Environment(start_time=2010, end_time=2016)
        b = Recorder(end_time=2013)
        env.run()
        assert all(t <= 2013 for t in b.ticks)
        assert 2013 in b.ticks
        assert 2014 not in b.ticks

    def test_model_end_time_does_not_stall_clock(self):
        """ModelB ending early must not stall the clock for ModelC."""
        env = Environment(start_time=2010, end_time=2016)
        b = Recorder(end_time=2013)
        c = Recorder()
        env.run()
        # ModelC must run until 2016 (the inclusive env end_time)
        assert max(c.ticks) == 2016
        assert len(c.ticks) == 7

    def test_three_models_mixed_boundaries(self):
        """Reproduces the canonical test from the docs."""
        env = Environment(start_time=2010, end_time=2016)
        a = Recorder(start_time=2012)
        b = Recorder(end_time=2013)
        c = Recorder()
        env.run()

        assert a.ticks == [2012, 2013, 2014, 2015, 2016]
        assert b.ticks == [2010, 2011, 2012, 2013]
        assert c.ticks == [2010, 2011, 2012, 2013, 2014, 2015, 2016]

    def test_model_active_single_tick(self):
        """Model with start_time == end_time executes exactly once."""
        env = Environment(start_time=0, end_time=5)
        r = Recorder(start_time=3, end_time=3)
        env.run()
        assert r.ticks == [3]

    def test_model_never_active(self):
        """Model whose window is entirely outside env range executes never."""
        env = Environment(start_time=0, end_time=5)
        r = Recorder(start_time=10, end_time=20)
        env.run()
        assert r.ticks == []


# ---------------------------------------------------------------------------
# Heterogeneous step sizes
# ---------------------------------------------------------------------------

class TestHeterogeneousSteps:
    def test_two_models_different_steps(self):
        env = Environment(start_time=0, end_time=6)
        fast = Recorder(step=1)
        slow = Recorder(step=2)
        env.run()

        assert fast.ticks == [0, 1, 2, 3, 4, 5, 6]
        assert slow.ticks == [0, 2, 4, 6]

    def test_clock_does_not_skip_ticks(self):
        """Clock must stop at every tick needed by any model."""
        env = Environment(start_time=0, end_time=6)
        Recorder(step=1)
        Recorder(step=3)
        # clock must visit 0,1,2,3,4,5,6 — not skip to 0,3,6
        visited = []

        class ClockWatcher(Model):
            def setup(self, **kwargs): pass
            def execute(self): visited.append(self.env.now())

        ClockWatcher(step=1)
        env.run()
        assert visited == [0, 1, 2, 3, 4, 5, 6]


# ---------------------------------------------------------------------------
# Lifecycle hooks
# ---------------------------------------------------------------------------

class TestLifecycleHooks:
    def test_setup_called_once(self):
        setup_calls = []

        class SetupModel(Model):
            def setup(self, tag="x", **kwargs):
                setup_calls.append(tag)

        env = Environment(start_time=0, end_time=3)
        SetupModel(tag="hello")
        env.run()
        assert setup_calls == ["hello"]

    def test_setup_receives_kwargs(self):
        received = {}

        class KwargsModel(Model):
            def setup(self, rate=0.0, name_tag="", **kwargs):
                received["rate"] = rate
                received["name_tag"] = name_tag

        env = Environment(start_time=0, end_time=1)
        KwargsModel(rate=0.5, name_tag="test")
        env.run()
        assert received == {"rate": 0.5, "name_tag": "test"}

    def test_pre_post_execute_order(self):
        order = []

        class OrderModel(Model):
            def setup(self, **kwargs): pass
            def pre_execute(self): order.append("pre")
            def execute(self): order.append("exec")
            def post_execute(self): order.append("post")

        env = Environment(start_time=0, end_time=2)
        OrderModel(step=1)
        env.run()
        assert order == ["pre", "exec", "post"] * 3

    def test_pre_post_execute_same_tick(self):
        """pre/post must record the same time as execute."""
        env = Environment(start_time=0, end_time=3)
        r = Recorder(step=1)
        env.run()
        assert r.pre_ticks == r.ticks == r.post_ticks

    def test_hooks_not_called_outside_model_window(self):
        env = Environment(start_time=0, end_time=5)
        r = Recorder(start_time=2, end_time=4)
        env.run()
        assert r.pre_ticks == [2, 3, 4]
        assert r.ticks == [2, 3, 4]
        assert r.post_ticks == [2, 3, 4]


# ---------------------------------------------------------------------------
# Re-run and reset
# ---------------------------------------------------------------------------

class TestReRun:
    def test_rerun_produces_same_ticks(self):
        env = Environment(start_time=0, end_time=3)
        r = Recorder(step=1)
        env.run()
        assert len(r.ticks) == 4   # primeiro run
        env.run()
        assert len(r.ticks) == 8   # segundo run acumula — comportamento esperado

    def test_reset_clears_plot_metadata(self):
        env = Environment(start_time=0, end_time=2)
        env._plot_metadata = {"x": {"data": [1, 2, 3]}}

        class Noop(Model):
            def setup(self, **kwargs): pass

        Noop(step=1)
        env.run()
        assert env._plot_metadata["x"]["data"] == []

    def test_environment_current_updated_on_init(self):
        env1 = Environment(start_time=0, end_time=5)
        assert Environment._current is env1
        env2 = Environment(start_time=0, end_time=5)
        assert Environment._current is env2


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_environment_runs_without_error(self):
        env = Environment(start_time=0, end_time=5)
        env.run()  # no models registered

    def test_model_without_environment_raises(self):
        Environment._current = None
        with pytest.raises(RuntimeError, match="No active Environment"):
            Recorder(step=1)

    def test_single_tick_simulation(self):
        """start_time == end_time executes exactly one tick."""
        env = Environment(start_time=1, end_time=1)
        r = Recorder(step=1)
        env.run()
        assert r.ticks == [1]

    def test_model_inf_end_time(self):
        """Model with default end_time=inf must respect env end_time."""
        env = Environment(start_time=0, end_time=3)
        r = Recorder(step=1)
        assert r.end_time == math.inf
        env.run()
        assert r.ticks == [0, 1, 2, 3]
