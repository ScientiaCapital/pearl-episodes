"""scripts/check_notebook_outputs.py (issue #9): notebooks are committed with outputs cleared, because outputs
can embed frames that show people."""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_notebook_outputs.py"


def _module():
    spec = importlib.util.spec_from_file_location("check_notebook_outputs", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _code(outputs: list | None = None, execution_count: int | None = None) -> dict:
    return {
        "cell_type": "code", "id": "c1", "metadata": {}, "source": ["1 + 1"],
        "outputs": outputs or [], "execution_count": execution_count,
    }  # fmt: skip


def _notebook(tmp_path: Path, *cells: dict, name: str = "demo.ipynb") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps({"cells": list(cells), "metadata": {}, "nbformat": 4, "nbformat_minor": 5}))
    return path


def test_a_cleared_notebook_passes(tmp_path: Path) -> None:
    markdown = {"cell_type": "markdown", "id": "m1", "metadata": {}, "source": ["# Title"]}
    assert _module().check(_notebook(tmp_path, markdown, _code())) == []


def test_a_code_cell_with_outputs_is_reported_by_position(tmp_path: Path) -> None:
    output = {"output_type": "display_data", "data": {"image/png": "AAAA"}, "metadata": {}}
    problems = _module().check(_notebook(tmp_path, _code(), _code(outputs=[output])))
    assert len(problems) == 1 and "cell 1" in problems[0] and "output" in problems[0]


def test_an_execution_count_is_reported(tmp_path: Path) -> None:
    problems = _module().check(_notebook(tmp_path, _code(execution_count=3)))
    assert len(problems) == 1 and "execution count" in problems[0]


def test_images_attached_to_a_markdown_cell_are_reported(tmp_path: Path) -> None:
    cell = {
        "cell_type": "markdown", "id": "m1", "metadata": {}, "source": ["![x](attachment:a.png)"],
        "attachments": {"a.png": {"image/png": "AAAA"}},
    }  # fmt: skip
    problems = _module().check(_notebook(tmp_path, cell))
    assert len(problems) == 1 and "attachment" in problems[0]


def test_a_file_that_is_not_json_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "bad.ipynb"
    path.write_text("not json")
    assert len(_module().check(path)) == 1


def test_main_exits_1_when_any_notebook_has_problems_and_0_otherwise(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _module()
    clean = _notebook(tmp_path, _code(), name="clean.ipynb")
    dirty = _notebook(tmp_path, _code(execution_count=1), name="dirty.ipynb")
    assert module.main([str(clean)]) == 0
    assert module.main([str(clean), str(dirty)]) == 1
    assert "dirty.ipynb" in capsys.readouterr().err
