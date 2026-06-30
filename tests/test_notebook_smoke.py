"""Smoke checks for committed notebook outputs."""

from __future__ import annotations

import json
from pathlib import Path


def test_notebook_has_saved_execution_output() -> None:
    """Notebook should be committed with at least one executed code output."""

    notebook_path = Path("notebooks/product_ad_demo.ipynb")
    assert notebook_path.exists()

    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    executed_cells = [
        cell
        for cell in notebook.get("cells", [])
        if cell.get("cell_type") == "code"
        and cell.get("execution_count") is not None
        and cell.get("outputs")
    ]

    assert executed_cells
