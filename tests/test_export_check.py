"""
Tests for `scripts/export_service.py --check` — the guard on the exported copy.

The rule is that `apps/hrv-service` in the KARIRLINK monorepo is GENERATED, never
typed into. Until now that rule had no way to be tested, and an untestable rule is
one that breaks silently: the copy drifted five times before anyone noticed, and
nothing about a drifted copy looks wrong — the service starts, answers, and runs
code that no longer matches the numbers the thesis reports.

`--check` exports to a temporary folder and compares. These tests check the only
thing that matters about it: that it says "same" when the copy is untouched, and
says "different" — with a non-zero exit code — for each way a copy can drift.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "export_service.py"
_spec = importlib.util.spec_from_file_location("export_service", _PATH)
export_service = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = export_service
_spec.loader.exec_module(export_service)


@pytest.fixture(scope="module")
def copied(tmp_path_factory) -> Path:
    """One fresh export, reused by every test that does not modify it."""
    target = tmp_path_factory.mktemp("hrv-service")
    export_service.export(target, announce=False)
    return target


def test_an_untouched_copy_passes(copied, capsys):
    assert export_service.check(copied) == 0
    assert "sama persis" in capsys.readouterr().out


def test_a_missing_folder_is_not_reported_as_a_match(tmp_path, capsys):
    assert export_service.check(tmp_path / "belum-ada") == 2
    assert "Tidak ada folder salinan" in capsys.readouterr().err


def test_an_edited_file_is_caught(copied, capsys):
    edited = copied / "src" / "hrv_rag" / "features" / "stress_level.py"
    original = edited.read_text(encoding="utf-8")
    # The edit a hurried person actually makes: one line, in the copy, "just to
    # try something". It changes no behaviour visible from outside.
    edited.write_text(original + "\n# catatan cepat\n", encoding="utf-8")
    try:
        assert export_service.check(copied) == 1
        assert "isinya berbeda: src/hrv_rag/features/stress_level.py" in capsys.readouterr().out
    finally:
        edited.write_text(original, encoding="utf-8")


def test_a_deleted_file_is_caught(copied, capsys):
    removed = copied / "src" / "hrv_rag" / "features" / "signal_fitness.py"
    original = removed.read_bytes()
    removed.unlink()
    try:
        assert export_service.check(copied) == 1
        assert "hilang dari salinan" in capsys.readouterr().out
    finally:
        removed.write_bytes(original)


def test_a_file_that_was_never_exported_is_caught(copied, capsys):
    added = copied / "src" / "hrv_rag" / "patch_cepat.py"
    added.write_text("# ditambahkan langsung di salinan\n", encoding="utf-8")
    try:
        assert export_service.check(copied) == 1
        assert "bukan hasil ekspor: src/hrv_rag/patch_cepat.py" in capsys.readouterr().out
    finally:
        added.unlink()


def test_what_belongs_to_the_copy_alone_is_ignored(copied):
    """
    A copy in a real monorepo carries things this repository never exported: the
    virtual environment it runs in, the operator's own `.env`, and compiled
    bytecode. Reporting those as drift would make the check noise, and a noisy
    check is one people stop running.
    """
    (copied / ".env").write_text("HRV_API_KEYS=rahasia\n", encoding="utf-8")
    (copied / ".venv" / "Scripts").mkdir(parents=True, exist_ok=True)
    (copied / ".venv" / "Scripts" / "python.exe").write_bytes(b"MZ")
    cache = copied / "src" / "hrv_rag" / "__pycache__"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "settings.cpython-310.pyc").write_bytes(b"\x00")

    assert export_service.check(copied) == 0


def test_a_mistyped_flag_does_not_become_a_destination(capsys):
    """
    `--help` once exported the entire service into a folder literally named
    `--help`, because the destination was read straight off `sys.argv[1]`.
    """
    with pytest.raises(SystemExit) as exit_info:
        export_service.main(["--help"])

    assert exit_info.value.code == 0
    assert "usage:" in capsys.readouterr().out
    assert not (Path.cwd() / "--help").exists()
