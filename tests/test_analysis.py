from pathlib import Path

from rdkit import Chem

from sidock.analysis import (
    add_compound_comparison, analyze_docking_results, parse_dlg_clusters,
    parse_dlg_poses,
)
from sidock.activity import correlate_activity, extract_activity_metadata
from sidock.plip_analysis import interaction_rows_from_set


RECEPTOR = """HETATM    1 FE   HEM A 601       0.000   0.000   0.000  1.00  0.00     0.000 Fe
ATOM      2  C1  PHE A 100       4.000   0.000   0.000  1.00  0.00     0.000 C
"""

DLG = """DOCKED: MODEL        1
DOCKED: USER    Run = 1
DOCKED: USER    Estimated Free Energy of Binding    =   -8.00 kcal/mol
DOCKED: USER    Cluster Rank = 1
DOCKED: USER    Number of conformations in this cluster = 2
DOCKED: ROOT
DOCKED: ATOM      1  O1  LIG A   1       2.500   0.000   0.000  1.00  0.00    -0.200 OA
DOCKED: ENDROOT
DOCKED: TORSDOF 0
DOCKED: ENDMDL
DOCKED: MODEL        2
DOCKED: USER    Run = 2
DOCKED: USER    Estimated Free Energy of Binding    =   -7.00 kcal/mol
DOCKED: USER    Cluster Rank = 1
DOCKED: USER    Number of conformations in this cluster = 2
DOCKED: ROOT
DOCKED: ATOM      1  O1  LIG A   1       3.000   0.000   0.000  1.00  0.00    -0.200 OA
DOCKED: ENDROOT
DOCKED: TORSDOF 0
DOCKED: ENDMDL
Successful Completion
"""


def test_complete_analysis(tmp_path: Path):
    receptor = tmp_path / "receptor.pdbqt"; receptor.write_text(RECEPTOR)
    dlg_dir = tmp_path / "dlg"; dlg_dir.mkdir(); dlg = dlg_dir / "ligand_1.dlg"; dlg.write_text(DLG)
    poses = parse_dlg_poses(dlg)
    assert len(poses) == 2 and poses[0].cluster_rank == 1
    output = tmp_path / "analysis"
    result = analyze_docking_results(receptor, dlg_dir, output, 10)
    assert result["successful"] == 1 and result["poses"] == 1
    assert (output / "poses" / "ligand_1_best.pdbqt").exists()
    complex_path = output / "complexes" / "ligand_1_best_complex.pdb"
    assert complex_path.exists()
    complex_text = complex_path.read_text()
    assert "PHE A 100" in complex_text
    assert "HETATM" in complex_text and "LIG L   1" in complex_text
    assert "metal_coordination" in (output / "contacts.csv").read_text()
    report = (output / "report.html").read_text()
    assert "SIDock AD4 post-docking analysis" in report and "-8.000" in report
    assert "Open complex" in report and "Download PDB" in report and " download" in report
    assert "complexes/ligand_1_best_complex.pdb" in report
    assert "complex_file" in (output / "ranking.csv").read_text()
    assert (output / "comparison.csv").exists()
    assert (output / "evidence.json").exists()
    assert (output / "CODEX_DISCUSSION_PROMPT.md").exists()


def test_consensus_ranking_is_transparent():
    rows = [
        {"rank": 1, "ligand": "A", "energy_kcal_mol": "-10", "ligand_efficiency": "0.4", "cluster_size": 1},
        {"rank": 2, "ligand": "B", "energy_kcal_mol": "-9", "ligand_efficiency": "0.6", "cluster_size": 10},
    ]
    comparison = add_compound_comparison(rows, [], 2)
    assert comparison[0]["ligand"] == "A"
    assert comparison[0]["consensus_rank"] == 1
    assert rows[1]["ligand_efficiency_rank"] == 1


def test_unprefixed_autodock_cluster_section_is_merged(tmp_path: Path):
    dlg = tmp_path / "realistic.dlg"
    dlg.write_text(
        "DOCKED: MODEL        1\n"
        "DOCKED: USER    Run = 1\n"
        "DOCKED: USER    Estimated Free Energy of Binding = -8.52 kcal/mol\n"
        "DOCKED: ATOM      1  O1  LIG A   1       2.500   0.000   0.000  1.00  0.00    -0.200 OA\n"
        "DOCKED: ENDMDL\n"
        "CLUSTERING HISTOGRAM\n"
        "   1 |     -8.52 |   1 |     -8.52 |   1 |#\n"
        "RMSD TABLE\n"
        "LOWEST ENERGY DOCKED CONFORMATION from EACH CLUSTER\n"
        "MODEL        1\n"
        "USER    Run = 1\n"
        "USER    Cluster Rank = 1\n"
        "USER    Number of conformations in this cluster = 1\n"
        "USER    RMSD from reference structure = 4.602 A\n"
        "USER    Estimated Free Energy of Binding = -8.52 kcal/mol\n"
        "ATOM      1  O1  LIG A   1       2.500   0.000   0.000  0.00  0.00    -0.200     4.602\n"
        "ENDMDL\n"
        "AVSFLD: # end\n"
    )
    poses = parse_dlg_poses(dlg)
    assert len(poses) == 1
    assert poses[0].cluster_rank == 1 and poses[0].cluster_size == 1
    assert poses[0].lines[-2].endswith("OA")
    clusters = parse_dlg_clusters(dlg)
    assert clusters == [{
        "ligand": "realistic", "cluster_rank": 1, "members": 1,
        "best_energy_kcal_mol": "-8.520", "mean_energy_kcal_mol": "-8.520",
        "best_run": 1,
    }]


def test_activity_metadata_and_correlations_are_traceable(tmp_path: Path):
    sdf_files = []
    activity = [("ligand_1", 1.0), ("ligand_2", 10.0), ("ligand_3", 100.0)]
    for name, ic50 in activity:
        molecule = Chem.AddHs(Chem.MolFromSmiles("CCO"))
        molecule.SetProp("_Name", name)
        molecule.SetProp("IC50_uM", str(ic50))
        path = tmp_path / f"{name}.sdf"
        writer = Chem.SDWriter(str(path)); writer.write(molecule); writer.close()
        sdf_files.append(path)
    rows = extract_activity_metadata(sdf_files, tmp_path / "activity.csv")
    ranking = [
        {"ligand": name, "energy_kcal_mol": energy}
        for name, energy in (("ligand_1", "-9.0"), ("ligand_2", "-8.0"), ("ligand_3", "-7.0"))
    ]
    stats = correlate_activity(ranking, rows, tmp_path / "activity_statistics.json")
    assert stats["n"] == 3
    assert stats["pearson_energy_vs_pIC50"] is not None
    assert ranking[0]["pIC50"] == "6.000000"
    assert "ligand_3" in (tmp_path / "activity.csv").read_text()


def test_plip_interactions_are_normalized_without_plip_runtime():
    class Interaction:
        restype = "ASP"
        resnr = 25
        reschain = "A"
        distance = 3.1
        ligatom_orig_idx = 7

    class InteractionSet:
        hydrophobic_contacts = [Interaction()]

    rows = interaction_rows_from_set("ligand_1", 1, "LIG:A:1", InteractionSet())
    assert rows == [{
        "ligand": "ligand_1", "rank": 1, "binding_site": "LIG:A:1",
        "interaction_type": "hydrophobic", "residue": "ASP A:25",
        "residue_name": "ASP", "chain": "A", "residue_number": "25",
        "distance_A": "3.100", "ligand_atom_ids": "7",
    }]


def test_plip_failure_is_nonfatal_and_recorded(tmp_path: Path, monkeypatch):
    receptor = tmp_path / "receptor.pdbqt"; receptor.write_text(RECEPTOR)
    dlg_dir = tmp_path / "dlg"; dlg_dir.mkdir(); (dlg_dir / "ligand_1.dlg").write_text(DLG)

    def fail_plip(*_args, **_kwargs):
        raise RuntimeError("synthetic PLIP failure")

    monkeypatch.setattr("sidock.plip_analysis.analyze_complex_with_plip", fail_plip)
    output = tmp_path / "analysis"
    result = analyze_docking_results(receptor, dlg_dir, output, 10, run_plip=True)
    assert result["successful"] == 1
    assert result["plip_completed"] == 0
    assert "synthetic PLIP failure" in (output / "plip_status.csv").read_text()
    assert "PLIP interaction profiling" in (output / "report.html").read_text()
