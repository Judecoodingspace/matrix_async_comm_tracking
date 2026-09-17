import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts/run_mdmt_mia_author_sync.sh"
FAKE_AUTHOR = ROOT / "tests/fixtures/fake_mdmt_mia_author.py"


def _value_after(argv, flag):
    return argv[argv.index(flag) + 1]


def _environment(tmp_path, output_root):
    mia_root = tmp_path / "mia-root"
    source_root = tmp_path / "source-root"
    mdmt_root = tmp_path / "mdmt-root"
    (mia_root / ".conda-env/bin").mkdir(parents=True)
    (mia_root / ".conda-env/bin/python").symlink_to(sys.executable)
    (mia_root / "run_configs").mkdir()
    (mia_root / "run_configs/one_carafe_bytetrack_full_mdmt_reproduction.py").write_text("# test\n")
    (source_root / "demo").mkdir(parents=True)
    (source_root / "demo/supplement_MIA.py").symlink_to(FAKE_AUTHOR)
    for path in (
        mdmt_root / "train/1/23-1",
        mdmt_root / "train/2/23-2",
        mdmt_root / "new_xml/1",
        mdmt_root / "new_xml/2",
        mdmt_root / "checkpoints/work_dirsfaster_rcnn_r50_fpn_carafe_1x_full_mdmt",
    ):
        path.mkdir(parents=True, exist_ok=True)
    (mdmt_root / "new_xml/1/23-1.xml").write_text("<test/>\n")
    (mdmt_root / "new_xml/2/23-2.xml").write_text("<test/>\n")
    (mdmt_root / "checkpoints/work_dirsfaster_rcnn_r50_fpn_carafe_1x_full_mdmt/epoch_12.pth").write_bytes(b"test")
    env = dict(os.environ)
    env.update({
        "MIA_ROOT": str(mia_root),
        "MIA_SOURCE_ROOT": str(source_root),
        "MDMT_ROOT": str(mdmt_root),
        "MIA_OUTPUT_ROOT": str(output_root),
        "MIA_RUN_INPUT_ROOT": "relative-input",
        "FAKE_AUTHOR_RECORD": str(tmp_path / "fake-author-record.json"),
        "MPLCONFIGDIR": str(tmp_path / "matplotlib"),
    })
    return env


def _run(tmp_path, output_root):
    env = _environment(tmp_path, output_root)
    completed = subprocess.run(
        ["bash", str(WRAPPER), "mia", "train", "23"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    record = json.loads((tmp_path / "fake-author-record.json").read_text())
    return completed, record


def _assert_resolved_paths(tmp_path, output_root, completed, record):
    run_root = (tmp_path / output_root / "mia/train_23").resolve() if not Path(output_root).is_absolute() else (Path(output_root) / "mia/train_23").resolve()
    run_input = (tmp_path / "relative-input/23/train").resolve()
    assert completed.returncode == 0, completed.stderr
    assert record["cwd"] == str(run_root)
    assert _value_after(record["argv"], "--result_dir") == str(run_root / "results")
    assert _value_after(record["argv"], "--output") == str(run_root / "view1")
    assert _value_after(record["argv"], "--output2") == str(run_root / "view2")
    assert _value_after(record["argv"], "--input") == str(run_input / "1") + "/"
    assert _value_after(record["argv"], "--xml_dir") == str(run_input / "xml") + "/"
    assert (run_root / "author.log").is_file()
    assert "[author-sync] complete" in completed.stdout
    return run_root


def test_relative_output_root_is_canonical_before_cwd_change(tmp_path):
    completed, record = _run(tmp_path, Path("relative-output"))
    run_root = _assert_resolved_paths(tmp_path, Path("relative-output"), completed, record)
    assert not (run_root / "relative-output").exists()


def test_absolute_output_root_still_resolves_exactly(tmp_path):
    output_root = tmp_path / "absolute-output"
    completed, record = _run(tmp_path, output_root)
    _assert_resolved_paths(tmp_path, output_root, completed, record)


def test_required_author_log_sink_failure_fails_closed(tmp_path):
    output_root = Path("relative-output")
    run_root = tmp_path / output_root / "mia/train_23"
    (run_root / "author.log").mkdir(parents=True)
    completed, record = _run(tmp_path, output_root)
    assert record["cwd"] == str(run_root.resolve())
    assert completed.returncode != 0
    assert "log persistence failed" in completed.stderr
    assert "[author-sync] complete" not in completed.stdout
