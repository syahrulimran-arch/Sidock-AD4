from __future__ import annotations

import html
import math
import re
from pathlib import Path
from typing import Iterable

from .core import safe_stem


INTERACTION_GROUPS = (
    ("hydrophobic_contacts", "hydrophobic", ("distance",)),
    ("hbonds_ldon", "hydrogen_bond", ("distance_ad", "distance_ah", "distance")),
    ("hbonds_pdon", "hydrogen_bond", ("distance_ad", "distance_ah", "distance")),
    ("water_bridges", "water_bridge", ("distance_aw", "distance_dw", "distance")),
    ("saltbridge_lneg", "salt_bridge", ("distance",)),
    ("saltbridge_pneg", "salt_bridge", ("distance",)),
    ("pistacking", "pi_stacking", ("distance",)),
    ("pication_laro", "pi_cation", ("distance",)),
    ("pication_paro", "pi_cation", ("distance",)),
    ("halogen_bonds", "halogen_bond", ("distance",)),
    ("metal_complexes", "metal_complex", ("distance",)),
)

INTERACTION_COLORS = {
    "hydrophobic": "#d97706",
    "hydrogen_bond": "#2563eb",
    "water_bridge": "#06b6d4",
    "salt_bridge": "#dc2626",
    "pi_stacking": "#7c3aed",
    "pi_cation": "#c026d3",
    "halogen_bond": "#16a34a",
    "metal_complex": "#475569",
}


def _value(item: object, names: Iterable[str], default: object = "") -> object:
    for name in names:
        value = getattr(item, name, None)
        if value not in {None, ""}:
            return value
    return default


def _atom_ids(item: object) -> str:
    values: list[str] = []
    for name in (
        "ligatom_orig_idx", "ligatom", "lig_idx", "ligand_idx",
        "a_orig_idx", "d_orig_idx", "don_orig_idx", "acc_orig_idx",
    ):
        value = getattr(item, name, None)
        if value in {None, ""}:
            continue
        if isinstance(value, (list, tuple, set)):
            values.extend(str(part) for part in value)
        elif isinstance(value, (int, str)):
            values.append(str(value))
    return ";".join(dict.fromkeys(values))


def interaction_rows_from_set(
    ligand: str, rank: int, binding_site: str, interaction_set: object,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for attribute, interaction_type, distance_names in INTERACTION_GROUPS:
        for item in getattr(interaction_set, attribute, ()) or ():
            distance = _value(item, distance_names)
            try:
                distance_text = f"{float(distance):.3f}"
            except (TypeError, ValueError):
                distance_text = ""
            residue_name = str(_value(item, ("restype", "resname"), ""))
            residue_number = str(_value(item, ("resnr", "resnum"), ""))
            chain = str(_value(item, ("reschain", "chain"), ""))
            residue = f"{residue_name} {chain + ':' if chain else ''}{residue_number}".strip()
            rows.append({
                "ligand": ligand,
                "rank": rank,
                "binding_site": binding_site,
                "interaction_type": interaction_type,
                "residue": residue,
                "residue_name": residue_name,
                "chain": chain,
                "residue_number": residue_number,
                "distance_A": distance_text,
                "ligand_atom_ids": _atom_ids(item),
            })
    return rows


def analyze_complex_with_plip(
    complex_pdb: Path, ligand: str, rank: int,
) -> list[dict[str, object]]:
    try:
        from plip.structure.preparation import PDBComplex
    except ImportError as exc:
        raise RuntimeError("PLIP is not available in this SIDock installation.") from exc

    structure = PDBComplex()
    structure.load_pdb(str(complex_pdb))
    structure.analyze()
    rows: list[dict[str, object]] = []
    for binding_site, interaction_set in structure.interaction_sets.items():
        # The complex can contain retained cofactors such as HEM. SIDock writes
        # the docked compound as residue LIG, chain L, residue 1, so exclude
        # PLIP sites belonging to protein cofactors from this ligand's result.
        site_text = str(binding_site)
        if "LIG" not in site_text.upper():
            continue
        rows.extend(interaction_rows_from_set(ligand, rank, site_text, interaction_set))
    return rows


def _ligand_svg(source: Path | None) -> str:
    """Return a nested RDKit SVG of the prepared ligand when it is available."""
    if source is None or not source.is_file():
        return ""
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem
        from rdkit.Chem.Draw import rdMolDraw2D

        supplier = Chem.SDMolSupplier(str(source), removeHs=False)
        molecule = next((item for item in supplier if item is not None), None)
        if molecule is None:
            return ""
        molecule = Chem.RemoveHs(molecule)
        AllChem.Compute2DCoords(molecule)
        drawer = rdMolDraw2D.MolDraw2DSVG(430, 300)
        drawer.drawOptions().clearBackground = False
        drawer.DrawMolecule(molecule)
        drawer.FinishDrawing()
        nested = re.sub(r"<\?xml[^>]*>\s*", "", drawer.GetDrawingText()).strip()
        return nested.replace(
            "<svg ", '<svg x="235" y="160" width="430" height="300" ', 1,
        )
    except Exception:
        return ""


def _fallback_svg(
    ligand: str, rows: list[dict[str, object]], width: int, height: int,
    ligand_sdf: Path | None = None,
) -> str:
    labels = sorted({(str(row["residue"]), str(row["interaction_type"])) for row in rows})[:24]
    cx, cy = width / 2, height / 2
    structure = _ligand_svg(ligand_sdf)
    pieces = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<rect x="220" y="145" width="460" height="330" rx="12" fill="#fbfdff" stroke="#2f79c5" stroke-width="2"/>',
    ]
    if structure:
        pieces.append(structure)
        pieces.append(f'<text x="{cx}" y="492" text-anchor="middle" font-size="16" font-weight="600">{html.escape(ligand)}</text>')
    else:
        pieces.extend([
            f'<ellipse cx="{cx}" cy="{cy}" rx="105" ry="55" fill="#eaf3fb" stroke="#2f79c5" stroke-width="2"/>',
            f'<text x="{cx}" y="{cy+5}" text-anchor="middle" font-size="18" font-weight="600">{html.escape(ligand)}</text>',
        ])
    for index, (residue, interaction_type) in enumerate(labels):
        angle = 2 * math.pi * index / max(1, len(labels)) - math.pi / 2
        x, y = cx + math.cos(angle) * 285, cy + math.sin(angle) * 205
        color = INTERACTION_COLORS.get(interaction_type, "#64748b")
        pieces.extend([
            f'<line x1="{cx}" y1="{cy}" x2="{x}" y2="{y}" stroke="{color}" stroke-width="2" stroke-dasharray="6 4"/>',
            f'<rect x="{x-68}" y="{y-20}" width="136" height="40" rx="6" fill="white" stroke="{color}"/>',
            f'<text x="{x}" y="{y-2}" text-anchor="middle" font-size="12" font-weight="600">{html.escape(residue)}</text>',
            f'<text x="{x}" y="{y+13}" text-anchor="middle" font-size="10" fill="{color}">{html.escape(interaction_type.replace("_", " "))}</text>',
        ])
    pieces.append('</svg>')
    return "".join(pieces)


def write_plip_interaction_svg(
    ligand: str, rows: list[dict[str, object]], destination: Path,
    ligand_sdf: Path | None = None,
) -> Path:
    """Write a portable 2D PLIP interaction map for the HTML report."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(_fallback_svg(ligand, rows, 900, 620, ligand_sdf), encoding="utf-8")
    return destination


def run_plip_for_ranked_complexes(
    ranking: list[dict[str, object]], output_dir: Path, top_n: int,
    progress=None, ligand_sdf_dir: Path | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    rows: list[dict[str, object]] = []
    status: list[dict[str, object]] = []
    selected = [row for row in ranking[:max(1, top_n)] if row.get("complex_file")]
    maps_dir = output_dir / "plip_maps"
    for index, row in enumerate(selected, start=1):
        ligand = str(row["ligand"])
        complex_path = output_dir / str(row["complex_file"])
        try:
            interactions = analyze_complex_with_plip(complex_path, ligand, int(row["rank"]))
            rows.extend(interactions)
            map_path = maps_dir / f"{safe_stem(ligand)}_plip.svg"
            ligand_sdf = ligand_sdf_dir / f"{safe_stem(ligand)}.sdf" if ligand_sdf_dir else None
            write_plip_interaction_svg(ligand, interactions, map_path, ligand_sdf)
            row["plip_interactions"] = len(interactions)
            row["plip_map"] = f"plip_maps/{map_path.name}"
            status.append({
                "ligand": ligand, "status": "complete", "interactions": len(interactions),
                "map": row["plip_map"], "error": "",
            })
        except Exception as exc:
            row["plip_interactions"] = ""
            row["plip_map"] = ""
            status.append({
                "ligand": ligand, "status": "failed", "interactions": "",
                "map": "", "error": str(exc),
            })
        if progress:
            progress(index, len(selected))
    return rows, status
