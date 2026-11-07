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


def test_run_without_the_input_names_the_missing_file(workdir):
    """The example needs make_input.py first; without it the error must say which file."""
    proc = run(["my_executor.py", "run", "--input", "forest.tif", "--output", "result.tif",
                "--toml", "model.toml"], workdir, check=False)
    assert proc.returncode != 0
    assert "forest.tif" in proc.stderr


def test_example_readme_tells_to_create_the_input_first():
    text = (EXAMPLE / "README.md").read_text()
    assert text.index("python make_input.py") < text.index("my_executor.py run")


def test_phase_banners_appear_when_the_phase_starts(workdir):
    """A failing load must not have announced Running or Saving."""
    bad = run(["my_executor.py", "run", "--input", "forest.tif", "--output", "result.tif",
               "--toml", "model.toml"], workdir, check=False)
    assert "Validating" in bad.stdout and "Loading" in bad.stdout
    assert "Running" not in bad.stdout and "Saving" not in bad.stdout

    run(["make_input.py"], workdir)
    ok = run(["my_executor.py", "run", "--input", "forest.tif", "--output", "result.tif",
              "--toml", "model.toml"], workdir)
    order = [ok.stdout.index(w) for w in ("Validating", "Loading", "Running", "Saving")]
    assert order == sorted(order)


def test_docs_warn_that_ids_differ_and_input_comes_first():
    walk = DOC.read_text()
    assert "will not match" in walk and "Run this before step 4" in walk
    assert "will be different" in (ROOT / "README.md").read_text()
    assert "generated at each run" in (EXAMPLE / "README.md").read_text()
