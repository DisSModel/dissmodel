from __future__ import annotations

import inspect
from typing import Any


def _parameter_annotations(obj: Any) -> dict[str, Any]:
    """
    Annotations declared by the user's classes, base classes included.

    Classes from the ``dissmodel`` package itself are skipped: their
    annotations (``env``, ``start_time``, ``end_time``, ``name``…) are
    framework state, not model parameters. Reading ``obj.__annotations__``
    directly would return them for any model that declares no annotation of
    its own, and the widget written back would replace ``env`` with a string.
    Names starting with ``_`` are skipped as private.
    """
    cls = obj if isinstance(obj, type) else type(obj)
    found: dict[str, Any] = {}
    for klass in reversed(cls.__mro__):
        module = getattr(klass, "__module__", "") or ""
        if module == "dissmodel" or module.startswith("dissmodel."):
            continue
        found.update(inspect.get_annotations(klass))
    return {k: v for k, v in found.items() if not k.startswith("_")}


def display_inputs(obj: Any, st: Any) -> None:
    """
    Render Streamlit input widgets for every annotated attribute on ``obj``.

    Iterates over the annotations of ``obj``'s class (and of its user-defined
    base classes; not those of dissmodel's own classes) and creates an appropriate widget
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
    annotations = _parameter_annotations(obj)

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
