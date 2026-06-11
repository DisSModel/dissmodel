"""
tests/test_widgets.py
======================
Tests for dissmodel.visualization.widgets.display_inputs.

Streamlit is intentionally NOT a dependency: display_inputs receives the
Streamlit module (or sidebar) as a parameter, so a minimal stub exposing
checkbox / slider / text_input is enough to exercise the full contract.
"""
from __future__ import annotations

from dissmodel.visualization.widgets import display_inputs


class StubStreamlit:
    """Records widget calls and echoes the current value back."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def checkbox(self, name, value=False):
        self.calls.append(("checkbox", name))
        return value

    def slider(self, name, min_value, max_value, value, step=None):
        self.calls.append(("slider", name))
        return value

    def text_input(self, name, value=""):
        self.calls.append(("text_input", name))
        return value


class FakeModel:
    flag: bool
    count: int
    rate: float
    label: str

    def __init__(self):
        self.flag = True
        self.count = 10
        self.rate = 0.5
        self.label = "hello"


class TestDisplayInputs:

    def test_widget_mapping_per_type(self):
        st = StubStreamlit()
        display_inputs(FakeModel(), st)
        assert st.calls == [
            ("checkbox", "flag"),       # bool checked before int
            ("slider", "count"),
            ("slider", "rate"),
            ("text_input", "label"),
        ]

    def test_values_written_back_to_object(self):
        class Returning(StubStreamlit):
            def slider(self, name, min_value, max_value, value, step=None):
                return 99 if isinstance(value, int) else 0.25

        model = FakeModel()
        display_inputs(model, Returning())
        assert model.count == 99
        assert model.rate == 0.25
        assert model.flag is True
        assert model.label == "hello"

    def test_object_without_annotations_is_noop(self):
        st = StubStreamlit()
        display_inputs(object(), st)
        assert st.calls == []
