from __future__ import annotations

import sys
from types import ModuleType
from typing import Any, Mapping, Sequence

try:
    import pandas as pd
except ModuleNotFoundError:
    import json

    class _StubDataFrame:
        """Minimal pandas.DataFrame replacement for test environments."""

        def __init__(self, data: Mapping[str, Sequence[Any]]):
            self._data = {column: list(values) for column, values in data.items()}
            lengths = {len(values) for values in self._data.values()}
            if len(lengths) > 1:
                raise ValueError("All columns must have the same length.")

        def to_json(self, orient: str = "split", date_format: str = "iso") -> str:
            if orient != "split":
                raise ValueError("Only 'split' orient is supported.")

            columns = list(self._data.keys())
            rows = [list(row) for row in zip(*self._data.values())] if columns else []

            return json.dumps(
                {
                    "columns": columns,
                    "index": list(range(len(rows))),
                    "data": rows,
                }
            )

    _stub = ModuleType("pandas")
    _stub.DataFrame = _StubDataFrame  # type: ignore[attr-defined]
    sys.modules.setdefault("pandas", _stub)
    pd = _stub  # type: ignore[assignment]

import chainlit as cl


@cl.on_chat_start
async def start():
    # Create a sample DataFrame with more than 10 rows to test pagination functionality
    data = {
        "Name": [
            "Alice",
            "David",
            "Charlie",
            "Bob",
            "Eva",
            "Grace",
            "Hannah",
            "Jack",
            "Frank",
            "Kara",
            "Liam",
            "Ivy",
            "Mia",
            "Noah",
            "Olivia",
        ],
        "Age": [25, 40, 35, 30, 45, 55, 60, 70, 50, 75, 80, 65, 85, 90, 95],
        "City": [
            "New York",
            "Houston",
            "Chicago",
            "Los Angeles",
            "Phoenix",
            "San Antonio",
            "San Diego",
            "San Jose",
            "Philadelphia",
            "Austin",
            "Fort Worth",
            "Dallas",
            "Jacksonville",
            "Columbus",
            "Charlotte",
        ],
        "Salary": [
            70000,
            100000,
            90000,
            80000,
            110000,
            130000,
            140000,
            160000,
            120000,
            170000,
            180000,
            150000,
            190000,
            200000,
            210000,
        ],
    }

    df = pd.DataFrame(data)

    elements = [cl.Dataframe(data=df, name="Dataframe")]

    await cl.Message(content="This message has a Dataframe", elements=elements).send()
