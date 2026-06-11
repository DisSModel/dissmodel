from __future__ import annotations

from typing import Any


def display_inputs(obj: Any, st: Any) -> None:
    """
    Render Streamlit input widgets for every annotated attribute on ``obj``.

    Iterates over ``obj.__annotations__`` and creates an appropriate widget
    for each attribute based on its current value type. The attribute is
    updated in-place on ``obj`` after each interaction.

    Widget mapping:

    - ``bool``  → ``st.checkbox``  *(checked before int — bool subclasses int)*
    - ``int``   → ``st.slider`` (0 – 1000)
    - ``float`` → ``st.slider`` (0.0 – 1.0, step 0.01)
    - anything else → ``st.text_input``

    Parameters
    ----------
    obj : any
        Any object with ``__annotations__`` and matching instance attributes,
        typically a :class:`~dissmodel.core.Model` subclass.
    st : any
        Streamlit module or sidebar object (e.g. ``st`` or ``st.sidebar``).
        Passed as an argument to avoid a hard dependency on Streamlit at
        import time.

    Examples
    --------
    ```python
    # sir_model, ca_model: Model instances; st: the imported streamlit module
    display_inputs(sir_model, st.sidebar)
    display_inputs(ca_model, st)
    ```
    """
    annotations: dict[str, Any] = getattr(obj, "__annotations__", {})

    for name in annotations:
        value: Any = getattr(obj, name, None)

        if isinstance(value, bool):
            # bool must come before int — bool is a subclass of int in Python
            new_value = st.checkbox(name, value=value)
        elif isinstance(value, int):
            new_value = st.slider(name, 0, 1000, value)
        elif isinstance(value, float):
            new_value = st.slider(name, 0.0, 1.0, value, step=0.01)
        else:
            new_value = st.text_input(name, str(value))

        setattr(obj, name, new_value)
