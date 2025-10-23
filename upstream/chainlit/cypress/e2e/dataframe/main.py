from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from types import ModuleType
from typing import Any

try:
    import pandas as pd
except ModuleNotFoundError:
    class _FallbackDataFrame:
        """Minimal pandas.DataFrame replacement for test usage."""

        def __init__(self, data: Mapping[str, Sequence[Any]]) -> None:
            if not isinstance(data, Mapping):
                raise TypeError("data must be a mapping of column names to sequences")

            values = [list(column) for column in data.values()]
            if values and len({len(column) for column in values}) != 1:
                raise ValueError("all columns must have the same length")

            self._columns = list(data.keys())
            self._data = list(map(list, zip(*values))) if values else []
            self._index = list(range(len(self._data)))

        def to_json(self, orient: str = "split", date_format: str = "iso") -> str:
            if orient != "split":
                raise ValueError("only orient='split' is supported")

            payload = {
                "columns": self._columns,
                "index": self._index,
                "data": self._data,
            }
            return json.dumps(payload)

    pd = ModuleType("pandas")
    setattr(pd, "DataFrame", _FallbackDataFrame)
    sys.modules["pandas"] = pd

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
