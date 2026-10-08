"""Run the python code blocks in the docs, so the examples cannot rot."""

import re
from pathlib import Path

import pytest

DOCS = Path(__file__).parents[1] / "docs"
PAGES = ["index.md"]
CODE = re.compile(r"^```python\n(.*?)^```", re.DOTALL | re.MULTILINE)


@pytest.mark.parametrize("page", PAGES)
def test_code_blocks_run(page):
    blocks = CODE.findall((DOCS / page).read_text())
    assert blocks
    namespace: dict = {}
    for block in blocks:  # blocks on a page share state, as a reader's session would
        exec(compile(block, f"{page}", "exec"), namespace)
