"""examples/hello_reproducible: the example runs, and the walkthrough matches it."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("rasterio")

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "hello_reproducible"
DOC = ROOT / "docs" / "getting_started.md"


def run(args, cwd, check=True):
    proc = subprocess.run([sys.executable, *args], cwd=cwd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise AssertionError(f"{args} exited {proc.returncode}\n{proc.stdout}\n{proc.stderr}")
    return proc


def command(name):
    return ["-m", "dissmodel.executor.commands", name]


@pytest.fixture
def workdir(tmp_path):
    for f in EXAMPLE.iterdir():
        if f.suffix in (".py", ".toml"):
            shutil.copy(f, tmp_path)
    return tmp_path


def test_example_runs_verifies_reproduces_and_shows_a_difference(workdir):
    run(["make_input.py"], workdir)
    assert (workdir / "forest.tif").exists()

    run(["my_executor.py", "run", "--input", "forest.tif", "--output", "result.tif",
         "--toml", "model.toml", "--preserve-output-name"], workdir)
    assert (workdir / "result.tif").exists() and (workdir / "result.record.json").exists()

    assert "matches the record" in run([*command("verify"), "result.record.json"], workdir).stdout

    again = run([*command("reproduce"), "result.record.json", "--module", "my_executor"], workdir)
    assert "identical" in again.stdout and "differs" not in again.stdout

    run(["my_executor.py", "run", "--input", "forest.tif", "--output", "other.tif",
         "--toml", "model.toml", "--param", "prob_spread=0.5", "--preserve-output-name"], workdir)
    diff = run([*command("compare"), "result.tif", "other.tif"], workdir, check=False)
    assert diff.returncode == 1 and "differs" in diff.stdout


def test_run_script_is_valid_bash_and_lists_the_documented_commands():
    script = (EXAMPLE / "run.sh").read_text()
    assert subprocess.run(["bash", "-n", str(EXAMPLE / "run.sh")]).returncode == 0
    for needle in ("make_input.py", "dissmodel verify", "dissmodel reproduce", "dissmodel compare"):
        assert needle in script


def test_walkthrough_code_blocks_are_the_example_files():
    text = DOC.read_text()
    text = text[text.index("## Your first reproducible experiment"):text.index("## Storage & Reproducibility")]
    blocks = {}
    for lang, body in re.findall(r"```(\w+)\n(.*?)```", text, re.S):
        m = re.match(r"# (\S+\.(?:py|toml))$", body.splitlines()[0])
        if lang in ("python", "toml") and m:
            blocks[m.group(1)] = body
    expected = {"forest_fire_model.py", "my_executor.py", "make_input.py", "model.toml"}
    assert set(blocks) == expected, "the walkthrough must show exactly the example files"
    for name, body in blocks.items():
        assert (EXAMPLE / name).read_text() == body, f"{name} differs between the docs and the example"
