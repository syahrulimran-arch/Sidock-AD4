import sys
from pathlib import Path

import pytest

from sidock.core import (
    BUNDLED_MEEKO, check_tool_setup, command_parts, normalize_meeko_command,
    command_failure_detail, format_process_exit, prepare_ligand, prepare_receptor,
    resolve_executable, run_command, run_meeko,
    verify_openbabel_formats,
)
from sidock.model import GridBox


def test_run_command_records_output(tmp_path: Path):
    log = tmp_path / "command.log"
    code = run_command([sys.executable, "-c", "print('mock AutoDock complete')"], tmp_path, log)
    assert code == 0
    assert "mock AutoDock complete" in log.read_text()
    assert "EXIT CODE: 0" in log.read_text()


def test_silent_windows_loader_failure_is_explained(tmp_path: Path):
    log = tmp_path / "gpu.log"
    log.write_text("COMMAND: AutoDock-GPU.exe --help\n\nEXIT CODE: 3221225781\n")
    assert "0xC0000135" in format_process_exit(3221225781)
    detail = command_failure_detail(log, 3221225781, "AutoDock-GPU")
    assert "missing DLL dependency" in detail
    assert "produced no diagnostic output" in detail


def test_explicit_python_command_is_run_by_current_python(tmp_path: Path):
    script = tmp_path / "mock_tool.py"
    script.write_text("print('ok')")
    parts = command_parts(str(script))
    assert parts == [sys.executable, str(script)]


def test_bundled_openbabel_is_preferred(monkeypatch, tmp_path: Path):
    executable = tmp_path / "obabel.exe"
    executable.write_text("")
    monkeypatch.setattr("sidock.core.bundled_openbabel_path", lambda: executable)
    assert resolve_executable("Bundled Open Babel", "Open Babel") == str(executable)
    assert resolve_executable("obabel", "Open Babel") == str(executable)


def test_openbabel_check_requires_pdb_and_pdbqt_plugins(monkeypatch):
    class Probe:
        returncode = 0
        stdout = "pdb -- Protein Data Bank\npdbqt -- AutoDock PDBQT\n"
        stderr = ""

    monkeypatch.setattr("sidock.core.subprocess.run", lambda *args, **kwargs: Probe())
    verify_openbabel_formats("obabel.exe")

    Probe.stdout = "sdf -- MDL SDfile\n"
    with pytest.raises(RuntimeError, match="missing format plugins: pdb, pdbqt"):
        verify_openbabel_formats("obabel.exe")


def test_automatic_meeko_runs_in_process(monkeypatch, tmp_path: Path):
    class FakeModule:
        @staticmethod
        def main():
            print("automatic Meeko invoked")
            return 0

    monkeypatch.setattr("sidock.core.import_module", lambda _: FakeModule)
    log = tmp_path / "meeko.log"
    code = run_meeko(
        "Auto (installed Meeko)", "fake.meeko", ["--help"], tmp_path, log,
    )
    assert code == 0
    assert "automatic Meeko invoked" in log.read_text()


def test_automatic_meeko_cannot_be_turned_into_python_subprocess():
    with pytest.raises(RuntimeError, match="must run inside SIDock"):
        command_parts("Auto (installed Meeko)", "meeko.cli.mk_prepare_ligand")


@pytest.mark.parametrize("executable_name", ["SIDock.exe", "DockFlow.exe"])
def test_legacy_frozen_executable_value_is_migrated(monkeypatch, tmp_path: Path, executable_name):
    executable = tmp_path / executable_name
    executable.write_text("")
    monkeypatch.setattr("sidock.core.is_frozen", lambda: True)
    monkeypatch.setattr("sidock.core.sys.executable", str(executable))
    assert normalize_meeko_command(str(executable)) == BUNDLED_MEEKO


@pytest.mark.parametrize("legacy_value", [
    "mk_prepare_ligand.py", "mk_prepare_receptor.py",
    "mk_prepare_ligand.exe", "mk_prepare_receptor.exe",
])
def test_legacy_meeko_wrapper_name_is_migrated(legacy_value):
    assert normalize_meeko_command(legacy_value) == BUNDLED_MEEKO


def test_automatic_meeko_tool_check_never_starts_subprocess(monkeypatch):
    class FakeModule:
        @staticmethod
        def main():
            return 0

    monkeypatch.setattr("sidock.core.import_module", lambda _: FakeModule)
    monkeypatch.setattr(
        "sidock.core.subprocess.run",
        lambda *args, **kwargs: pytest.fail("automatic Meeko started a subprocess"),
    )
    messages = check_tool_setup("missing-grid", "missing-dock", BUNDLED_MEEKO, BUNDLED_MEEKO)
    assert any("OK: Meeko ligand preparation" in message for message in messages)
    assert any("OK: Meeko receptor preparation" in message for message in messages)


def test_meeko_preparation_paths_are_absolute(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    receptor = Path("testing/receptor/receptor_clean.pdb")
    ligand = Path("testing/ligands/source/ligand.sdf")
    receptor.parent.mkdir(parents=True)
    ligand.parent.mkdir(parents=True)
    receptor.write_text("ATOM\n")
    ligand.write_text("mock\n")
    captured = []

    def fake_run(command, module_name, cli_args, cwd, log_path, cancel_check=None):
        captured.append((cli_args, cwd, log_path))
        return 0

    monkeypatch.setattr("sidock.core.run_meeko", fake_run)
    receptor_code, receptor_output = prepare_receptor(
        BUNDLED_MEEKO, receptor, Path("testing/receptor/receptor"),
        GridBox(), Path("testing/logs/prepare_receptor.log"),
    )
    ligand_code = prepare_ligand(
        BUNDLED_MEEKO, ligand, Path("testing/ligands/prepared/ligand.pdbqt"),
        Path("testing/logs/prepare_ligand.log"),
    )

    assert receptor_code == ligand_code == 0
    assert receptor_output.is_absolute()
    for cli_args, cwd, log_path in captured:
        assert cwd.is_absolute()
        assert log_path.is_absolute()
        for flag in ("--read_pdb", "-i", "-o"):
            if flag in cli_args:
                assert Path(cli_args[cli_args.index(flag) + 1]).is_absolute()
