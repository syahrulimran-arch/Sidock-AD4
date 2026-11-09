import csv
from pathlib import Path

import pytest

rdkit = pytest.importorskip("rdkit")
from rdkit import Chem
from rdkit.Chem import AllChem

from sidock.core import (
    ligand_geometry_summary, split_and_normalize_ligands,
    validate_ligand_geometry,
)


def test_mol_input_generates_3d_and_minimizes(tmp_path: Path):
    molecule = Chem.MolFromSmiles("CCO")
    source = tmp_path / "ethanol.mol"
    Chem.MolToMolFile(molecule, str(source))
    outputs, errors = split_and_normalize_ligands(
        [source], tmp_path / "prepared", generate_3d=True,
        optimize=True, forcefield="MMFF94", max_iters=500, num_conformers=10,
    )
    assert errors == []
    assert len(outputs) == 1
    result = Chem.SDMolSupplier(str(outputs[0]), removeHs=False)[0]
    assert result.GetConformer().Is3D()
    assert result.GetProp("SIDock_Optimization_Method") == "MMFF94"
    assert result.GetProp("SIDock_Optimization_Status") == "converged"
    initial = float(result.GetProp("SIDock_Initial_Energy_kcal_mol"))
    final = float(result.GetProp("SIDock_Final_Energy_kcal_mol"))
    assert final <= initial + 1.0e-4
    assert int(result.GetProp("SIDock_Conformers_Attempted")) >= 1
    assert int(result.GetProp("SIDock_Conformers_Converged")) >= 1
    assert float(result.GetProp("SIDock_Coordinate_RMSD_A")) >= 0.0
    assert (tmp_path / "prepared" / "geometry_summary.csv").exists()
    details = ligand_geometry_summary(outputs[0])
    assert "MMFF94 converged" in details
    assert "kcal/mol" in details
    assert "converged" in validate_ligand_geometry(outputs[0], True)


def test_minimization_reports_visible_stages_and_audit_blocks_unminimized_sdf(tmp_path: Path):
    source = tmp_path / "ethanol.mol"
    Chem.MolToMolFile(Chem.MolFromSmiles("CCO"), str(source))
    stages: list[tuple[str, str]] = []
    outputs, errors = split_and_normalize_ligands(
        [source], tmp_path / "prepared", optimize=True, forcefield="MMFF94",
        num_conformers=3, stage_callback=lambda ligand, detail: stages.append((ligand, detail)),
    )
    assert errors == []
    assert any("Generating" in detail for _, detail in stages)
    assert any("Minimizing conformer" in detail for _, detail in stages)
    assert any("Writing and verifying" in detail for _, detail in stages)

    molecule = Chem.SDMolSupplier(str(outputs[0]), removeHs=False)[0]
    molecule.SetProp("SIDock_Optimization_Status", "not requested")
    writer = Chem.SDWriter(str(outputs[0])); writer.write(molecule); writer.close()
    with pytest.raises(ValueError, match="minimization was not completed"):
        validate_ligand_geometry(outputs[0], True)


def test_nonconverged_minimization_is_not_sent_forward(monkeypatch, tmp_path: Path):
    molecule = Chem.MolFromSmiles("CCCCCC")
    source = tmp_path / "hexane.mol"
    Chem.MolToMolFile(molecule, str(source))

    class NonConvergingForceField:
        def Initialize(self):
            return None

        def CalcEnergy(self):
            return 10.0

        def Minimize(self, **kwargs):
            return 1

    monkeypatch.setattr(
        AllChem, "MMFFGetMoleculeForceField",
        lambda molecule, properties, confId: NonConvergingForceField(),
    )
    output_dir = tmp_path / "prepared"
    outputs, errors = split_and_normalize_ligands(
        [source], output_dir, generate_3d=True, optimize=True,
        forcefield="MMFF94", max_iters=10, num_conformers=2,
    )
    assert outputs == []
    assert any("did not converge" in error for error in errors)
    with (output_dir / "geometry_summary.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["status"] == "failed"
    assert "did not converge" in rows[0]["error"]
