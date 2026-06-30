"""Execute and persist the demo notebook."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NOTEBOOK = PROJECT_ROOT / "notebooks" / "product_ad_demo.ipynb"


def _has_executed_output(notebook: dict[str, Any]) -> bool:
    """Return whether at least one code cell has a saved execution output."""

    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        if cell.get("execution_count") is not None and cell.get("outputs"):
            return True
    return False


def _print_failure_cells(notebook: dict[str, Any]) -> None:
    """Print compact failure information for cells with error outputs."""

    for index, cell in enumerate(notebook.get("cells", []), start=1):
        if cell.get("cell_type") != "code":
            continue
        for output in cell.get("outputs", []):
            if output.get("output_type") != "error":
                continue
            ename = output.get("ename", "Error")
            evalue = output.get("evalue", "")
            print(f"Failed cell {index}: {ename}: {evalue}", file=sys.stderr)


def execute_notebook(notebook_path: Path, timeout: int) -> int:
    """Execute a notebook in-place and return a process exit code."""

    started_at = time.perf_counter()
    notebook = nbformat.read(notebook_path, as_version=4)
    client = NotebookClient(
        notebook,
        timeout=timeout,
        kernel_name="python3",
        resources={"metadata": {"path": str(PROJECT_ROOT)}},
    )
    try:
        client.execute()
    except CellExecutionError as error:
        _print_failure_cells(notebook)
        elapsed = time.perf_counter() - started_at
        print(f"Notebook execution failed after {elapsed:.2f}s", file=sys.stderr)
        print(str(error), file=sys.stderr)
        return 1

    nbformat.write(notebook, notebook_path)
    elapsed = time.perf_counter() - started_at
    print(f"Executed {notebook_path} in {elapsed:.2f}s")
    return 0


def smoke_check(notebook_path: Path) -> int:
    """Validate that the committed notebook contains at least one saved output."""

    notebook = nbformat.read(notebook_path, as_version=4)
    if _has_executed_output(notebook):
        print(f"Notebook smoke check passed: {notebook_path}")
        return 0
    print(
        f"Notebook smoke check failed: {notebook_path} has no executed outputs.",
        file=sys.stderr,
    )
    return 1


def main() -> int:
    """CLI entrypoint."""

    parser = argparse.ArgumentParser(description="Execute the demo notebook.")
    parser.add_argument(
        "--notebook",
        default=str(DEFAULT_NOTEBOOK),
        help="Notebook path to execute in-place.",
    )
    parser.add_argument("--timeout", type=int, default=600, help="Per-cell timeout in seconds.")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Only verify that committed notebook output exists.",
    )
    args = parser.parse_args()

    notebook_path = Path(args.notebook)
    if not notebook_path.is_absolute():
        notebook_path = PROJECT_ROOT / notebook_path
    if not notebook_path.exists():
        print(f"Notebook not found: {notebook_path}", file=sys.stderr)
        return 1
    if args.smoke:
        return smoke_check(notebook_path)
    return execute_notebook(notebook_path, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
