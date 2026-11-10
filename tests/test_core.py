import os
from pathlib import Path

import pytest

from sidock.core import (
    box_from_reference, box_from_receptor_residue, bundled_autodock_gpu_runtime_path,
    clean_receptor_pdb, configure_bundled_runtime, external_tool_environment, parse_dlg, pdbqt_atom_types,
    safe_stem, write_dpf, prepare_receptor_autodocktools, write_gpf, write_results,
)
from sidock.model import DockingParameters, GridBox, Project


PDBQT = """ROOT
ATOM      1  C1  LIG A   1       1.000   2.000   3.000  1.00  0.00     0.000 C
ATOM      2  O1  LIG A   1       3.000   4.000   5.000  1.00  0.00    -0.200 OA
ENDROOT
TORSDOF 2
"""


def test_safe_stem():
    assert safe_stem("Ligand 1 / beta") == "Ligand_1_beta"


def test_bundled_gpu_runtime_is_added_to_child_path(monkeypatch, tmp_path: Path):
    runtime = tmp_path / "packaging" / "runtime" / "libomp140.x86_64.dll"
    runtime.parent.mkdir(parents=True)
    runtime.write_bytes(b"test")
    monkeypatch.setattr("sidock.core.bundled_resource_dir", lambda: tmp_path)
    monkeypatch.setenv("PATH", "existing-path")
    assert bundled_autodock_gpu_runtime_path() == runtime
    assert external_tool_environment()["PATH"].split(os.pathsep)[0] == str(runtime.parent)


def test_openbabel_environment_paths_have_required_final_separator(monkeypatch, tmp_path: Path):
    root = tmp_path / "tools" / "openbabel"
    root.mkdir(parents=True)
    (root / "data").mkdir()
    monkeypatch.setattr("sidock.core.bundled_resource_dir", lambda: tmp_path)
    environment = external_tool_environment()
    assert environment["BABEL_LIBDIR"] == str(root) + os.sep
    assert environment["BABEL_DATADIR"] == str(root / "data") + os.sep


def test_frozen_runtime_registers_openbabel_dll_directory(monkeypatch, tmp_path: Path):
    root = tmp_path / "tools" / "openbabel"
    root.mkdir(parents=True)
    registered = []
    monkeypatch.setattr("sidock.core.bundled_resource_dir", lambda: tmp_path)
    monkeypatch.setattr("sidock.core.is_frozen", lambda: True)
    monkeypatch.setattr(os, "add_dll_directory", lambda path: registered.append(path) or object(), raising=False)
    monkeypatch.setattr("sidock.core._DLL_DIRECTORY_HANDLES", [])
    monkeypatch.setattr("sidock.core._REGISTERED_DLL_DIRECTORIES", set())
    configure_bundled_runtime()
    configure_bundled_runtime()
    assert registered == [str(root.resolve()), str(tmp_path.resolve())]


def test_pdbqt_atom_types_accepts_openbabel_spacing(tmp_path: Path):
    path = tmp_path / "openbabel.pdbqt"
    path.write_text(
        "ATOM 1 C1 LIG A 1 1.000 2.000 3.000 1.00 0.00 0.000 C\n"
        "HETATM    2  O1  LIG A   1       3.000   4.000   5.000  1.00  0.00    -0.200 OA\n"
    )
    assert pdbqt_atom_types(path) == ["C", "OA"]


def test_pdbqt_atom_types_reports_empty_output(tmp_path: Path):
    path = tmp_path / "empty.pdbqt"
    path.write_text("REMARK  0 molecules converted\n")
    with pytest.raises(ValueError, match="0 molecules converted"):
        pdbqt_atom_types(path)


def test_autodocktools_receptor_command(monkeypatch, tmp_path: Path):
    python = tmp_path / "python.exe"; python.write_text("")
    script = tmp_path / "prepare_receptor4.py"; script.write_text("")
    source = tmp_path / "treated.pdb"; source.write_text("ATOM\n")
    destination = tmp_path / "receptor.pdbqt"; log = tmp_path / "adt.log"
    captured = {}

    def fake_run(args, cwd, log_path, cancel_check=None):
        captured["args"] = args
        return 0

    monkeypatch.setattr("sidock.core.run_command", fake_run)
    assert prepare_receptor_autodocktools(str(python), str(script), source, destination, log) == 0
    assert captured["args"][-4:] == ["-A", "hydrogens", "-U", "nphs_lps_waters"]


def test_grid_and_dpf_generation(tmp_path: Path):
    receptor = tmp_path / "receptor.pdbqt"; receptor.write_text(PDBQT)
    ligand = tmp_path / "lig.pdbqt"; ligand.write_text(PDBQT)
    grid = GridBox(1, 2, 3, 60, 62, 64, 0.375)
    gpf = tmp_path / "receptor.gpf"; write_gpf(receptor, pdbqt_atom_types(ligand), grid, gpf)
    assert "ligand_types C OA" in gpf.read_text()
    assert "map receptor.OA.map" in gpf.read_text()
    dpf = tmp_path / "lig.dpf"; write_dpf("receptor", ligand, ["C", "OA"], DockingParameters(ga_runs=25), dpf)
    text = dpf.read_text(); assert "ga_run 25" in text; assert "torsdof 2" in text; assert "about 2.000 3.000 4.000" in text


def test_grid_rejects_odd_points():
    with pytest.raises(ValueError): GridBox(npts_x=61).validate()


def test_project_root_is_absolute(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    project = Project("testing")
    assert project.path == (tmp_path / "testing").resolve()


def test_reference_box(tmp_path: Path):
    path = tmp_path / "ref.pdbqt"; path.write_text(PDBQT)
    box = box_from_reference(path, padding=5.0)
    assert box.center_x == 2.0
    assert box.npts_x % 2 == 0


def test_chain_and_selective_hetero_cleanup(tmp_path: Path):
    source = tmp_path / "source.pdb"
    source.write_text(
        "ATOM      1  CA  ALA A   1       1.000   1.000   1.000  1.00  0.00           C\n"
        "ATOM      2  CA  ALA B   1       2.000   2.000   2.000  1.00  0.00           C\n"
        "HETATM    3 FE   HEM B 601       3.000   3.000   3.000  1.00  0.00          FE\n"
        "HETATM    4  C1  VT1 B 602       4.000   4.000   4.000  1.00  0.00           C\n"
        "HETATM    5  O   HOH B 701       5.000   5.000   5.000  1.00  0.00           O\nEND\n"
    )
    cleaned = tmp_path / "clean.pdb"
    clean_receptor_pdb(source, cleaned, True, True, "B", "HEM")
    text = cleaned.read_text()
    assert "ALA B" in text and "HEM B" in text
    assert "ALA A" not in text and "VT1 B" not in text and "HOH B" not in text
    box = box_from_receptor_residue(source, "VT1", "B", 5.0)
    assert box.center_x == 4.0


def test_parse_and_rank_dlg(tmp_path: Path):
    dlg = tmp_path / "lig.dlg"
    dlg.write_text("Run = 1\nDOCKED: USER    Estimated Free Energy of Binding    =   -7.10 kcal/mol\nRun = 2\nDOCKED: USER    Estimated Free Energy of Binding    =   -8.25 kcal/mol\nSuccessful Completion")
    result = parse_dlg(dlg)
    assert result.best_energy == -8.25
    assert result.run == 2
    csv_path = tmp_path / "results.csv"; write_results([result], csv_path)
    assert "-8.25" in csv_path.read_text()
