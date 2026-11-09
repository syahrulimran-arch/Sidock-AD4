from __future__ import annotations

import csv
import html
import json
import math
import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .activity import correlate_activity, extract_activity_metadata, write_activity_scatter_svg
from .core import ENERGY_RE, RUN_RE, parse_dlg, safe_stem
from .plip_analysis import run_plip_for_ranked_complexes


CLUSTER_RANK_RE = re.compile(r"Cluster\s+Rank\s*=\s*(\d+)", re.IGNORECASE)
CLUSTER_SIZE_RE = re.compile(
    r"(?:Number\s+of\s+conformations\s+in\s+this\s+cluster|Cluster\s+Size)\s*=\s*(\d+)",
    re.IGNORECASE,
)
CLUSTER_RMSD_RE = re.compile(r"Cluster\s+RMSD\s*=\s*([-+]?\d+(?:\.\d+)?)", re.IGNORECASE)
REFERENCE_RMSD_RE = re.compile(
    r"RMSD\s+from\s+reference\s+structure\s*=\s*([-+]?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
CLUSTER_HISTOGRAM_RE = re.compile(
    r"^\s*(\d+)\s*\|\s*([-+]?\d+(?:\.\d+)?)\s*\|\s*(\d+)\s*\|\s*"
    r"([-+]?\d+(?:\.\d+)?)\s*\|\s*(\d+)\s*\|",
)


@dataclass
class Pose:
    run: int | None
    energy: float
    cluster_rank: int | None
    cluster_size: int | None
    cluster_rmsd: float | None
    lines: list[str]


@dataclass(frozen=True)
class Atom:
    x: float
    y: float
    z: float
    atom_type: str
    atom_name: str
    residue_name: str
    chain: str
    residue_number: str
    record: str = "ATOM"

    @property
    def residue(self) -> str:
        chain = f"{self.chain}:" if self.chain else ""
        return f"{self.residue_name} {chain}{self.residue_number}".strip()


def _prefixed_blocks(text: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for raw in text.splitlines():
        if not raw.startswith("DOCKED:"):
            continue
        line = raw[7:].lstrip()
        if line.startswith("MODEL"):
            if current:
                blocks.append(current)
            current = [line]
        elif current:
            current.append(line)
            if line.startswith("ENDMDL"):
                blocks.append(current)
                current = []
    if current:
        blocks.append(current)
    return blocks


def _cluster_representative_blocks(text: str) -> list[list[str]]:
    """Read the unprefixed representative poses written after cluster analysis."""
    marker = "LOWEST ENERGY DOCKED CONFORMATION from EACH CLUSTER"
    if marker not in text:
        return []
    section = text.split(marker, 1)[1]
    blocks: list[list[str]] = []
    current: list[str] = []
    for raw in section.splitlines():
        line = raw.rstrip()
        if line.startswith("AVSFLD:"):
            break
        if line.startswith("MODEL"):
            if current:
                blocks.append(current)
            current = [line]
        elif current:
            current.append(line)
            if line.startswith("ENDMDL"):
                blocks.append(current)
                current = []
    if current:
        blocks.append(current)
    return blocks


def _pose_from_block(block: list[str]) -> Pose | None:
    joined = "\n".join(block)
    energy = ENERGY_RE.search(joined)
    if not energy:
        return None
    run = RUN_RE.search(joined)
    cluster_rank = CLUSTER_RANK_RE.search(joined)
    cluster_size = CLUSTER_SIZE_RE.search(joined)
    cluster_rmsd = CLUSTER_RMSD_RE.search(joined) or REFERENCE_RMSD_RE.search(joined)
    return Pose(
        int(run.group(1)) if run else None,
        float(energy.group(1)),
        int(cluster_rank.group(1)) if cluster_rank else None,
        int(cluster_size.group(1)) if cluster_size else None,
        float(cluster_rmsd.group(1)) if cluster_rmsd else None,
        block,
    )


def parse_dlg_poses(path: Path) -> list[Pose]:
    text = path.read_text(encoding="utf-8", errors="replace")
    docked = [pose for block in _prefixed_blocks(text) if (pose := _pose_from_block(block))]
    representatives = [
        pose for block in _cluster_representative_blocks(text)
        if (pose := _pose_from_block(block))
    ]
    if not representatives:
        return docked

    # The first pose blocks retain AutoDock atom types, while the later cluster
    # representatives contain cluster metadata but replace the atom-type field
    # with RMSD. Merge metadata by run and keep the original coordinate lines.
    clustered_by_run = {pose.run: pose for pose in representatives if pose.run is not None}
    merged: list[Pose] = []
    seen_runs: set[int] = set()
    for pose in docked:
        clustered = clustered_by_run.get(pose.run)
        if clustered:
            merged.append(Pose(
                pose.run, pose.energy, clustered.cluster_rank,
                clustered.cluster_size, clustered.cluster_rmsd, pose.lines,
            ))
            if pose.run is not None:
                seen_runs.add(pose.run)
        else:
            merged.append(pose)
    merged.extend(pose for pose in representatives if pose.run not in seen_runs and pose.run not in {p.run for p in docked})
    return merged


def parse_dlg_clusters(path: Path, ligand: str | None = None) -> list[dict[str, object]]:
    """Parse AutoDock's clustering histogram, including mean energy and size."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if "CLUSTERING HISTOGRAM" not in text:
        return []
    section = text.split("CLUSTERING HISTOGRAM", 1)[1]
    if "RMSD TABLE" in section:
        section = section.split("RMSD TABLE", 1)[0]
    rows: list[dict[str, object]] = []
    for line in section.splitlines():
        match = CLUSTER_HISTOGRAM_RE.match(line)
        if not match:
            continue
        rank, best, run, mean, members = match.groups()
        rows.append({
            "ligand": ligand or path.stem,
            "cluster_rank": int(rank),
            "members": int(members),
            "best_energy_kcal_mol": f"{float(best):.3f}",
            "mean_energy_kcal_mol": f"{float(mean):.3f}",
            "best_run": int(run),
        })
    return rows


def write_pose(pose: Pose, ligand: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"REMARK SIDock best pose for {ligand}",
        f"REMARK Binding energy {pose.energy:.3f} kcal/mol",
    ]
    if pose.run is not None:
        lines.append(f"REMARK AutoDock run {pose.run}")
    lines.extend(line for line in pose.lines if not line.startswith("USER"))
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _pdb_element(atom_type: str) -> str:
    """Translate AutoDock atom types into standard PDB element symbols."""
    value = atom_type.upper()
    mapped = {
        "A": "C", "HD": "H", "NA": "N", "NS": "N",
        "OA": "O", "OS": "O", "SA": "S",
    }
    two_letter_elements = {"CL", "BR", "FE", "ZN", "MG", "MN", "CA", "CU"}
    return mapped.get(value, value.title() if value in two_letter_elements else value[:1]) or "C"


def _pdb_atom_line(
    atom: Atom, serial: int, *, record: str | None = None,
    residue_name: str | None = None, chain: str | None = None,
    residue_number: str | None = None,
) -> str:
    """Create a conservative fixed-column PDB atom record."""
    selected_record = (record or atom.record or "ATOM")[:6].upper()
    selected_residue = (residue_name or atom.residue_name or "UNK")[:3].upper()
    selected_chain = (atom.chain if chain is None else chain)[:1]
    selected_number = (atom.residue_number if residue_number is None else residue_number).strip()[-4:] or "1"
    return (
        f"{selected_record:<6}{serial:>5} {atom.atom_name[:4]:<4} "
        f"{selected_residue:>3} {selected_chain:1}{selected_number:>4}    "
        f"{atom.x:8.3f}{atom.y:8.3f}{atom.z:8.3f}"
        f"{1.00:6.2f}{0.00:6.2f}          {_pdb_element(atom.atom_type):>2}"
    )


def write_receptor_ligand_complex(
    receptor_atoms: list[Atom], ligand_atoms: list[Atom], ligand: str,
    pose: Pose, destination: Path,
) -> None:
    """Write a visualization-ready PDB containing receptor and best pose."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"REMARK   1 SIDock AD4 receptor-ligand complex for {ligand}",
        f"REMARK   2 AutoDock binding energy {pose.energy:.3f} kcal/mol",
    ]
    if pose.run is not None:
        lines.append(f"REMARK   3 AutoDock run {pose.run}")
    serial = 1
    for atom in receptor_atoms:
        lines.append(_pdb_atom_line(atom, serial))
        serial += 1
    lines.append("TER")
    for atom in ligand_atoms:
        lines.append(_pdb_atom_line(
            atom, serial, record="HETATM", residue_name="LIG",
            chain="L", residue_number="1",
        ))
        serial += 1
    lines.append("END")
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_pdbqt_atoms(path: Path) -> list[Atom]:
    atoms: list[Atom] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line[:6].strip().upper() not in {"ATOM", "HETATM"}:
            continue
        try:
            x, y, z = float(line[30:38]), float(line[38:46]), float(line[46:54])
        except ValueError:
            continue
        parts = line.split()
        atom_type = line[77:79].strip() if len(line) >= 78 else ""
        if not atom_type and parts:
            atom_type = parts[-1]
        atoms.append(Atom(
            x, y, z, atom_type,
            line[12:16].strip() or "?",
            line[17:20].strip() or "UNK",
            line[21].strip() if len(line) > 21 else "",
            line[22:26].strip() if len(line) >= 26 else "",
            line[:6].strip().upper(),
        ))
    return atoms


def _distance(a: Atom, b: Atom) -> float:
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)


def _element(atom_type: str) -> str:
    value = atom_type.upper()
    if value in {"CL", "BR", "FE", "ZN", "MG", "MN", "CA", "CU"}:
        return value
    return value[:1]


def _heavy(atom: Atom) -> bool:
    return _element(atom.atom_type) != "H"


def _acceptor(atom: Atom) -> bool:
    return atom.atom_type.upper() in {"NA", "OA", "SA", "N", "O", "S"}


def _hydrophobic(atom: Atom) -> bool:
    return atom.atom_type.upper() in {"A", "C"}


def _metal(atom: Atom) -> bool:
    return _element(atom.atom_type) in {"FE", "ZN", "MG", "MN", "CA", "CU"}


def _donor_heavy_for_hydrogen(hydrogen: Atom, atoms: Iterable[Atom]) -> Atom | None:
    candidates = [atom for atom in atoms if _element(atom.atom_type) in {"N", "O", "S"}]
    close = [(atom, _distance(hydrogen, atom)) for atom in candidates]
    close = [item for item in close if item[1] <= 1.35]
    return min(close, key=lambda item: item[1])[0] if close else None


def contact_rows(ligand: str, rank: int, ligand_atoms: list[Atom], receptor_atoms: list[Atom]) -> list[dict[str, object]]:
    by_residue: dict[tuple[str, str, str], dict[str, object]] = {}
    ligand_heavy = [atom for atom in ligand_atoms if _heavy(atom)]
    receptor_heavy = [atom for atom in receptor_atoms if _heavy(atom)]

    def add(rec: Atom, lig: Atom, distance: float, kind: str) -> None:
        key = (rec.residue_name, rec.chain, rec.residue_number)
        row = by_residue.setdefault(key, {
            "ligand": ligand, "rank": rank, "residue": rec.residue,
            "residue_name": rec.residue_name, "chain": rec.chain,
            "residue_number": rec.residue_number, "minimum_distance_A": distance,
            "interaction_types": set(), "ligand_atoms": set(), "receptor_atoms": set(),
        })
        row["minimum_distance_A"] = min(float(row["minimum_distance_A"]), distance)
        row["interaction_types"].add(kind)  # type: ignore[union-attr]
        row["ligand_atoms"].add(lig.atom_name)  # type: ignore[union-attr]
        row["receptor_atoms"].add(rec.atom_name)  # type: ignore[union-attr]

    for lig in ligand_heavy:
        for rec in receptor_heavy:
            distance = _distance(lig, rec)
            if distance <= 4.0:
                add(rec, lig, distance, "close_contact")
            if distance <= 4.5 and _hydrophobic(lig) and _hydrophobic(rec):
                add(rec, lig, distance, "hydrophobic")
            if distance <= 3.5 and _acceptor(lig) and _acceptor(rec):
                add(rec, lig, distance, "polar_contact")
            if distance <= 3.0 and _acceptor(lig) and _metal(rec):
                add(rec, lig, distance, "metal_coordination")

    ligand_h = [atom for atom in ligand_atoms if atom.atom_type.upper() == "HD"]
    receptor_h = [atom for atom in receptor_atoms if atom.atom_type.upper() == "HD"]
    for hydrogen in ligand_h:
        donor = _donor_heavy_for_hydrogen(hydrogen, ligand_atoms)
        if not donor:
            continue
        for rec in receptor_heavy:
            distance = _distance(hydrogen, rec)
            if _acceptor(rec) and distance <= 2.5 and _distance(donor, rec) <= 3.5:
                add(rec, donor, _distance(donor, rec), "putative_hydrogen_bond")
    for hydrogen in receptor_h:
        donor = _donor_heavy_for_hydrogen(hydrogen, receptor_atoms)
        if not donor:
            continue
        for lig in ligand_heavy:
            distance = _distance(hydrogen, lig)
            if _acceptor(lig) and distance <= 2.5 and _distance(donor, lig) <= 3.5:
                add(donor, lig, _distance(donor, lig), "putative_hydrogen_bond")

    rows: list[dict[str, object]] = []
    for row in by_residue.values():
        row["minimum_distance_A"] = f"{float(row['minimum_distance_A']):.2f}"
        row["interaction_types"] = ";".join(sorted(row["interaction_types"]))  # type: ignore[arg-type]
        row["ligand_atoms"] = ";".join(sorted(row["ligand_atoms"]))  # type: ignore[arg-type]
        row["receptor_atoms"] = ";".join(sorted(row["receptor_atoms"]))  # type: ignore[arg-type]
        rows.append(row)
    return sorted(rows, key=lambda row: (float(row["minimum_distance_A"]), str(row["residue"])))


def _write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _normalized_scores(rows: list[dict[str, object]], key: str, higher_is_better: bool) -> dict[str, float]:
    available = [(str(row["ligand"]), float(row[key])) for row in rows if row.get(key) not in {"", None}]
    if not available:
        return {}
    values = [value for _, value in available]
    low, high = min(values), max(values)
    if math.isclose(low, high):
        return {ligand: 100.0 for ligand, _ in available}
    if higher_is_better:
        return {ligand: (value - low) / (high - low) * 100.0 for ligand, value in available}
    return {ligand: (high - value) / (high - low) * 100.0 for ligand, value in available}


def _metric_ranks(rows: list[dict[str, object]], key: str, higher_is_better: bool) -> dict[str, int]:
    available = [(str(row["ligand"]), float(row[key])) for row in rows if row.get(key) not in {"", None}]
    available.sort(key=lambda item: item[1], reverse=higher_is_better)
    ranks: dict[str, int] = {}
    previous: float | None = None
    current_rank = 0
    for position, (ligand, value) in enumerate(available, start=1):
        if previous is None or not math.isclose(value, previous):
            current_rank = position
            previous = value
        ranks[ligand] = current_rank
    return ranks


def add_compound_comparison(ranking: list[dict[str, object]], contacts: list[dict[str, object]], top_n: int) -> list[dict[str, object]]:
    """Add transparent metric ranks and a balanced consensus score.

    Consensus weights are 65% binding energy, 25% ligand efficiency, and 10%
    cluster support. Unavailable metrics are excluded and remaining weights are
    renormalized. Contact counts are descriptive and never increase the score.
    """
    contact_by_ligand: dict[str, list[dict[str, object]]] = {}
    for row in contacts:
        contact_by_ligand.setdefault(str(row["ligand"]), []).append(row)
    analyzed = {str(row["ligand"]) for row in ranking[:max(1, top_n)]}
    for row in ranking:
        ligand = str(row["ligand"])
        row["energy_rank"] = row["rank"]
        row["cluster_support"] = row.get("cluster_size", "")
        rows = contact_by_ligand.get(ligand, [])
        row["contacts_analyzed"] = "yes" if ligand in analyzed else "no"
        if ligand in analyzed:
            row["contact_residues"] = len(rows)
            row["putative_hbond_residues"] = sum("putative_hydrogen_bond" in str(item["interaction_types"]) for item in rows)
            row["hydrophobic_residues"] = sum("hydrophobic" in str(item["interaction_types"]) for item in rows)
            row["polar_contact_residues"] = sum("polar_contact" in str(item["interaction_types"]) for item in rows)
            row["metal_coordination_residues"] = sum("metal_coordination" in str(item["interaction_types"]) for item in rows)
        else:
            for key in ("contact_residues", "putative_hbond_residues", "hydrophobic_residues", "polar_contact_residues", "metal_coordination_residues"):
                row[key] = ""

    energy_scores = _normalized_scores(ranking, "energy_kcal_mol", False)
    efficiency_scores = _normalized_scores(ranking, "ligand_efficiency", True)
    cluster_scores = _normalized_scores(ranking, "cluster_support", True)
    efficiency_ranks = _metric_ranks(ranking, "ligand_efficiency", True)
    cluster_ranks = _metric_ranks(ranking, "cluster_support", True)
    for row in ranking:
        ligand = str(row["ligand"])
        row["ligand_efficiency_rank"] = efficiency_ranks.get(ligand, "")
        row["cluster_support_rank"] = cluster_ranks.get(ligand, "")
        components: list[tuple[float, float]] = [(0.65, energy_scores[ligand])]
        if ligand in efficiency_scores:
            components.append((0.25, efficiency_scores[ligand]))
        if ligand in cluster_scores:
            components.append((0.10, cluster_scores[ligand]))
        weight = sum(item[0] for item in components)
        row["consensus_score"] = f"{sum(w * score for w, score in components) / weight:.2f}"
    comparison = sorted(ranking, key=lambda row: (-float(row["consensus_score"]), float(row["energy_kcal_mol"]), str(row["ligand"])))
    for rank, row in enumerate(comparison, start=1):
        row["consensus_rank"] = rank
    return comparison


def _energy_bars(rows: list[dict[str, object]], limit: int = 20) -> str:
    shown = rows[:limit]
    if not shown:
        return "<p>No successful docking energies.</p>"
    width, left, row_h = 760, 180, 25
    values = [float(row["energy_kcal_mol"]) for row in shown]
    magnitude = max(abs(min(values)), 1.0)
    pieces = [f'<svg viewBox="0 0 {width} {35 + row_h * len(shown)}" role="img" aria-label="Top docking energies">']
    for index, row in enumerate(shown):
        y = 20 + index * row_h
        bar_width = max(2.0, abs(float(row["energy_kcal_mol"])) / magnitude * (width - left - 90))
        label = html.escape(str(row["ligand"])[:24])
        pieces.append(f'<text x="{left - 8}" y="{y + 13}" text-anchor="end">{label}</text>')
        pieces.append(f'<rect x="{left}" y="{y}" width="{bar_width:.1f}" height="16" rx="3" fill="#2878b5"/>')
        pieces.append(f'<text x="{left + bar_width + 7:.1f}" y="{y + 13}">{float(row["energy_kcal_mol"]):.2f}</text>')
    pieces.append("</svg>")
    return "".join(pieces)


def _histogram(values: list[float]) -> str:
    if not values:
        return "<p>No energies available.</p>"
    bins = max(1, min(12, math.ceil(math.sqrt(len(values)))))
    lo, hi = min(values), max(values)
    if math.isclose(lo, hi):
        counts, edges = [len(values)], [lo, hi]
    else:
        step = (hi - lo) / bins
        edges = [lo + index * step for index in range(bins + 1)]
        counts = [0] * bins
        for value in values:
            counts[min(bins - 1, int((value - lo) / step))] += 1
    width, height, margin = 720, 240, 45
    bar_w = (width - 2 * margin) / len(counts)
    max_count = max(counts) or 1
    pieces = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Energy distribution">']
    pieces.append(f'<line x1="{margin}" y1="{height-margin}" x2="{width-margin}" y2="{height-margin}" stroke="#65758b"/>')
    for index, count in enumerate(counts):
        bar_h = count / max_count * (height - 2 * margin)
        x, y = margin + index * bar_w + 2, height - margin - bar_h
        pieces.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(1, bar_w-4):.1f}" height="{bar_h:.1f}" fill="#67a9cf"/>')
        pieces.append(f'<text x="{x + (bar_w-4)/2:.1f}" y="{y-4:.1f}" text-anchor="middle">{count}</text>')
        pieces.append(f'<text x="{x + (bar_w-4)/2:.1f}" y="{height-margin+17}" text-anchor="middle" font-size="10">{edges[index]:.1f}</text>')
    pieces.append(f'<text x="{width/2}" y="{height-5}" text-anchor="middle">Binding energy (kcal/mol)</text></svg>')
    return "".join(pieces)


def _table(rows: list[dict[str, object]], fields: list[tuple[str, str]], limit: int | None = None) -> str:
    shown = rows if limit is None else rows[:limit]
    head = "".join(f"<th>{html.escape(label)}</th>" for _, label in fields)
    body = []
    for row in shown:
        cells = []
        for key, _ in fields:
            value = str(row.get(key, ""))
            if key == "complex_file" and value:
                link = html.escape(value, quote=True)
                cells.append(
                    '<td><span class="pose-actions">'
                    f'<a class="action" href="{link}" target="_blank">Open complex</a>'
                    f'<a class="action download" href="{link}" download>Download PDB</a>'
                    '</span></td>'
                )
            elif key == "pose_file" and value:
                cells.append(f'<td><a href="{html.escape(value, quote=True)}">Open pose</a></td>')
            elif key == "plip_map" and value:
                link = html.escape(value, quote=True)
                cells.append(
                    '<td><span class="pose-actions">'
                    f'<a class="action" href="{link}" target="_blank">Open 2D map</a>'
                    f'<a class="action download" href="{link}" download>Download SVG</a>'
                    '</span></td>'
                )
            else:
                cells.append(f"<td>{html.escape(value)}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def write_html_report(
    destination: Path, ranking: list[dict[str, object]], comparison: list[dict[str, object]], clusters: list[dict[str, object]],
    contacts: list[dict[str, object]], total_dlgs: int, top_n: int,
    activity_stats: dict[str, object] | None = None,
    plip_rows: list[dict[str, object]] | None = None,
    plip_status: list[dict[str, object]] | None = None,
) -> None:
    activity_stats = activity_stats or {"n": 0, "rows": []}
    plip_rows = plip_rows or []
    plip_status = plip_status or []
    energies = [float(row["energy_kcal_mol"]) for row in ranking]
    mean = statistics.mean(energies) if energies else float("nan")
    median = statistics.median(energies) if energies else float("nan")
    best = energies[0] if energies else float("nan")
    cards = [
        ("DLG files", str(total_dlgs)), ("Successful", str(len(ranking))),
        ("Best energy", f"{best:.2f}" if energies else "N/A"),
        ("Median energy", f"{median:.2f}" if energies else "N/A"),
        ("Mean energy", f"{mean:.2f}" if energies else "N/A"),
    ]
    cards_html = "".join(f'<div class="card"><span>{html.escape(k)}</span><strong>{html.escape(v)}</strong></div>' for k, v in cards)
    ranking_table = _table(ranking, [
        ("energy_rank", "Energy rank"), ("ligand", "Ligand"), ("energy_kcal_mol", "Energy"),
        ("ligand_efficiency", "Ligand efficiency"), ("heavy_atoms", "Heavy atoms"),
        ("best_run", "Run"), ("cluster_rank", "Cluster"), ("cluster_size", "Cluster size"),
        ("ic50_uM", "IC50 (µM)"), ("pIC50", "pIC50"),
        ("plip_interactions", "PLIP interactions"), ("plip_map", "PLIP 2D map"),
        ("complex_file", "Best pose complex"),
    ])
    comparison_table = _table(comparison, [
        ("consensus_rank", "Overall rank"), ("ligand", "Ligand"), ("consensus_score", "Consensus score"),
        ("energy_rank", "Energy rank"), ("energy_kcal_mol", "Energy"),
        ("ligand_efficiency_rank", "LE rank"), ("ligand_efficiency", "Ligand efficiency"),
        ("cluster_support_rank", "Cluster rank"), ("cluster_support", "Cluster support"),
        ("ic50_uM", "IC50 (µM)"), ("pIC50", "pIC50"),
        ("contact_residues", "Contact residues"), ("putative_hbond_residues", "H-bond residues"),
        ("metal_coordination_residues", "Metal contacts"),
        ("plip_interactions", "PLIP interactions"), ("plip_map", "PLIP 2D map"),
        ("complex_file", "Best pose complex"),
    ])
    cluster_table = _table(clusters, [
        ("ligand", "Ligand"), ("cluster_rank", "Cluster"), ("members", "Members"),
        ("best_energy_kcal_mol", "Best energy"), ("mean_energy_kcal_mol", "Mean energy"),
    ], 200)
    contact_table = _table(contacts, [
        ("rank", "Rank"), ("ligand", "Ligand"), ("residue", "Residue"),
        ("interaction_types", "Geometry-based contacts"), ("minimum_distance_A", "Min distance (Å)"),
        ("ligand_atoms", "Ligand atoms"), ("receptor_atoms", "Receptor atoms"),
    ], 500)
    plip_table = _table(plip_rows, [
        ("rank", "Rank"), ("ligand", "Ligand"), ("interaction_type", "PLIP interaction"),
        ("residue", "Residue"), ("distance_A", "Distance (Å)"),
        ("binding_site", "Binding site"), ("ligand_atom_ids", "Ligand atom IDs"),
    ], 1000)
    activity_n = int(activity_stats.get("n", 0) or 0)
    activity_values = []
    for label, key in (
        ("Pearson r", "pearson_energy_vs_pIC50"),
        ("Pearson p", "pearson_p"),
        ("Spearman rho", "spearman_energy_vs_pIC50"),
        ("Spearman p", "spearman_p"),
        ("Linear R²", "r2_linear"),
    ):
        value = activity_stats.get(key)
        activity_values.append(f"<strong>{html.escape(label)}:</strong> {'N/A' if value is None else f'{float(value):.4g}'}")
    activity_section = (
        f'<section><h2>Experimental activity correlation</h2><p>Matched ligands: {activity_n}. '
        + " &nbsp; ".join(activity_values)
        + '</p><p class="note">Correlation is reported only for matched numerical IC50 values. '
          'It describes association and does not validate docking accuracy or establish causation.</p>'
        + ('<img class="analysis-figure" src="activity_scatter.svg" alt="Docking energy versus pIC50 scatter plot">' if activity_n >= 2 else '<p>At least two matched activity values are required for a scatter plot.</p>')
        + '</section>'
    )
    map_cards = []
    for row in ranking:
        link = str(row.get("plip_map", ""))
        if not link:
            continue
        escaped_link = html.escape(link, quote=True)
        map_cards.append(
            '<article class="map-card">'
            f'<h3>{html.escape(str(row["ligand"]))}</h3>'
            f'<a href="{escaped_link}" target="_blank"><img src="{escaped_link}" alt="PLIP interaction map for {html.escape(str(row["ligand"]), quote=True)}"></a>'
            f'<p><a class="action download" href="{escaped_link}" download>Download SVG</a></p>'
            '</article>'
        )
    plip_failures = [row for row in plip_status if row.get("status") == "failed"]
    plip_note = (
        f"PLIP completed for {len(plip_status) - len(plip_failures)} of {len(plip_status)} selected complexes. "
        f"Detected interactions: {len(plip_rows)}."
    ) if plip_status else "PLIP profiling was disabled or no receptor-ligand complexes were available."
    if plip_failures:
        failure_text = "; ".join(
            f"{row.get('ligand')}: {row.get('error')}" for row in plip_failures[:8]
        )
        plip_note += f" Failures: {failure_text}"
    plip_section = (
        '<section><h2>PLIP protein–ligand interaction profiling</h2>'
        f'<p class="note">{html.escape(plip_note)}</p>'
        f'<div class="map-grid">{"".join(map_cards)}</div>'
        f'{plip_table or "<p>No PLIP interaction rows were generated.</p>"}</section>'
    )
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SIDock AD4 analysis</title><style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#f4f7fb;color:#172033}}main{{max-width:1180px;margin:auto;padding:28px}}
h1{{color:#174b7a}}h2{{margin-top:34px}}.cards{{display:flex;flex-wrap:wrap;gap:12px}}.card{{background:white;border:1px solid #d8e1ec;border-radius:8px;padding:14px 18px;min-width:145px}}
.card span{{display:block;color:#64748b;font-size:13px}}.card strong{{font-size:24px}}section{{background:white;border:1px solid #d8e1ec;border-radius:9px;padding:18px;margin-top:18px;overflow:auto}}
table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{border-bottom:1px solid #e5eaf0;padding:8px;text-align:left;white-space:nowrap}}th{{background:#edf4fa;position:sticky;top:0}}
svg{{width:100%;height:auto;font:12px Segoe UI,Arial}}.note{{background:#fff7dc;border-left:4px solid #d89b00;padding:12px}}
.analysis-figure{{display:block;max-width:900px;width:100%;height:auto;margin:16px auto}}.map-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:16px}}
.map-card{{border:1px solid #d8e1ec;border-radius:8px;padding:12px;background:#fbfdff}}.map-card img{{width:100%;height:auto;background:white}}
.pose-actions{{display:flex;gap:7px;align-items:center}}.action{{display:inline-block;padding:6px 10px;border:1px solid #2f6fa6;border-radius:5px;color:#1d5d91;text-decoration:none;font-weight:600;background:#f5faff}}
.action:hover{{background:#e8f3fc}}.action.download{{color:white;background:#2f6fa6}}.action.download:hover{{background:#245a87}}
</style></head><body><main><h1>SIDock AD4 post-docking analysis</h1>
<div class="cards">{cards_html}</div>
<section><h2>Top-ranked ligands</h2>{_energy_bars(ranking)}</section>
<section><h2>Energy distribution</h2>{_histogram(energies)}</section>
{activity_section}
<section><h2>Compound comparison and overall ranking</h2><p class="note">Consensus score: 65% binding energy, 25% ligand efficiency, and 10% AutoDock cluster support. Missing metrics are excluded and the remaining weights are renormalized. Contact counts are displayed for comparison but do not increase the score.</p>{comparison_table}</section>
<section><h2>Binding-energy ranking</h2>{ranking_table}</section>
<section><h2>AutoDock clusters</h2>{cluster_table or '<p>No cluster annotations were found.</p>'}</section>
<section><h2>Receptor contacts for top {top_n} poses</h2><p class="note">Contact labels are geometry-based screening annotations. Putative hydrogen bonds require an explicit polar hydrogen in the PDBQT; they are not an energetic decomposition or a replacement for manual pose inspection.</p>{contact_table}</section>
{plip_section}
</main></body></html>"""
    destination.write_text(document, encoding="utf-8")


def analyze_docking_results(
    receptor: Path, dlg_dir: Path, output_dir: Path, top_n: int = 20,
    progress: Callable[[int, int], None] | None = None,
    *, engine: str = "autodock4", ligand_sdf_dir: Path | None = None,
    grid_metadata: dict[str, object] | None = None, run_plip: bool = False,
) -> dict[str, object]:
    if not receptor.exists():
        raise FileNotFoundError("Prepared receptor PDBQT is missing.")
    dlgs = sorted(dlg_dir.glob("*.dlg"))
    if not dlgs:
        raise FileNotFoundError("No AutoDock DLG files were found to analyze.")
    output_dir.mkdir(parents=True, exist_ok=True)
    poses_dir = output_dir / "poses"; poses_dir.mkdir(parents=True, exist_ok=True)
    complexes_dir = output_dir / "complexes"; complexes_dir.mkdir(parents=True, exist_ok=True)
    receptor_atoms = parse_pdbqt_atoms(receptor)
    if not receptor_atoms:
        raise ValueError("No receptor atoms could be read for contact analysis.")

    ranking: list[dict[str, object]] = []
    cluster_rows: list[dict[str, object]] = []
    best_pose_by_ligand: dict[str, tuple[Pose, Path]] = {}
    for index, dlg in enumerate(dlgs, start=1):
        result = parse_dlg(dlg, dlg.stem)
        poses = parse_dlg_poses(dlg)
        # A GPU DLG with an energy but no coordinates cannot supply a pose,
        # receptor complex, or contact analysis. Do not rank it as complete.
        if engine == "autodock_gpu" and (
            not poses or "Unsuccessful Completion" in dlg.read_text(encoding="utf-8", errors="replace")
        ):
            result.best_energy = None
        if result.best_energy is not None:
            best_pose = min(poses, key=lambda pose: pose.energy) if poses else None
            pose_path = poses_dir / f"{safe_stem(dlg.stem)}_best.pdbqt"
            if best_pose:
                write_pose(best_pose, dlg.stem, pose_path)
                best_pose_by_ligand[dlg.stem] = (best_pose, pose_path)
            pose_atoms = parse_pdbqt_atoms(pose_path) if best_pose else []
            complex_path = complexes_dir / f"{safe_stem(dlg.stem)}_best_complex.pdb"
            if best_pose and pose_atoms:
                write_receptor_ligand_complex(
                    receptor_atoms, pose_atoms, dlg.stem, best_pose, complex_path,
                )
            heavy_atoms = sum(1 for atom in pose_atoms if _heavy(atom))
            ranking.append({
                "rank": 0, "ligand": dlg.stem,
                "energy_kcal_mol": f"{result.best_energy:.3f}",
                "best_run": result.run or (best_pose.run if best_pose else ""),
                "cluster_rank": best_pose.cluster_rank if best_pose and best_pose.cluster_rank is not None else "",
                "cluster_size": best_pose.cluster_size if best_pose and best_pose.cluster_size is not None else "",
                "heavy_atoms": heavy_atoms or "",
                "ligand_efficiency": f"{-result.best_energy / heavy_atoms:.3f}" if heavy_atoms else "",
                "pose_file": f"poses/{pose_path.name}" if best_pose else "",
                "complex_file": f"complexes/{complex_path.name}" if best_pose and pose_atoms else "",
                "dlg": str(dlg),
            })
        parsed_clusters = parse_dlg_clusters(dlg, dlg.stem)
        if parsed_clusters:
            cluster_rows.extend(parsed_clusters)
        else:
            grouped: dict[int, list[Pose]] = {}
            for pose in poses:
                if pose.cluster_rank is not None:
                    grouped.setdefault(pose.cluster_rank, []).append(pose)
            for cluster_rank, members in sorted(grouped.items()):
                values = [pose.energy for pose in members]
                reported = max((pose.cluster_size or 0 for pose in members), default=0)
                cluster_rows.append({
                    "ligand": dlg.stem, "cluster_rank": cluster_rank,
                    "members": reported or len(members),
                    "best_energy_kcal_mol": f"{min(values):.3f}",
                    "mean_energy_kcal_mol": f"{statistics.mean(values):.3f}",
                })
        if progress:
            progress(index, len(dlgs))

    ranking.sort(key=lambda row: float(row["energy_kcal_mol"]))
    for rank, row in enumerate(ranking, start=1):
        row["rank"] = rank

    contacts: list[dict[str, object]] = []
    for row in ranking[:max(1, top_n)]:
        item = best_pose_by_ligand.get(str(row["ligand"]))
        if not item:
            continue
        ligand_atoms = parse_pdbqt_atoms(item[1])
        contacts.extend(contact_rows(str(row["ligand"]), int(row["rank"]), ligand_atoms, receptor_atoms))

    activity_files = sorted(ligand_sdf_dir.glob("*.sdf")) if ligand_sdf_dir and ligand_sdf_dir.is_dir() else []
    activity_rows = extract_activity_metadata(activity_files, output_dir / "activity.csv")
    activity_stats = correlate_activity(ranking, activity_rows, output_dir / "activity_statistics.json")
    write_activity_scatter_svg(activity_stats, output_dir / "activity_scatter.svg")

    plip_rows: list[dict[str, object]] = []
    plip_status: list[dict[str, object]] = []
    if run_plip:
        plip_rows, plip_status = run_plip_for_ranked_complexes(
            ranking, output_dir, top_n, ligand_sdf_dir=ligand_sdf_dir,
        )
    _write_csv(output_dir / "plip_interactions.csv", plip_rows, [
        "ligand", "rank", "binding_site", "interaction_type", "residue",
        "residue_name", "chain", "residue_number", "distance_A", "ligand_atom_ids",
    ])
    _write_csv(output_dir / "plip_status.csv", plip_status, [
        "ligand", "status", "interactions", "map", "error",
    ])

    comparison = add_compound_comparison(ranking, contacts, top_n)

    _write_csv(output_dir / "ranking.csv", ranking, [
        "rank", "energy_rank", "consensus_rank", "ligand", "energy_kcal_mol", "ligand_efficiency", "heavy_atoms",
        "ic50_uM", "pIC50", "plip_interactions", "plip_map",
        "best_run", "cluster_rank", "cluster_size", "pose_file", "complex_file", "dlg",
    ])
    _write_csv(output_dir / "comparison.csv", comparison, [
        "consensus_rank", "ligand", "consensus_score", "energy_rank", "energy_kcal_mol",
        "ligand_efficiency_rank", "ligand_efficiency", "heavy_atoms",
        "cluster_support_rank", "cluster_support", "contacts_analyzed", "contact_residues",
        "ic50_uM", "pIC50", "plip_interactions", "plip_map",
        "putative_hbond_residues", "hydrophobic_residues", "polar_contact_residues",
        "metal_coordination_residues", "best_run", "pose_file", "complex_file", "dlg",
    ])
    _write_csv(output_dir / "clusters.csv", cluster_rows, [
        "ligand", "cluster_rank", "members", "best_energy_kcal_mol", "mean_energy_kcal_mol",
    ])
    _write_csv(output_dir / "contacts.csv", contacts, [
        "ligand", "rank", "residue", "residue_name", "chain", "residue_number",
        "minimum_distance_A", "interaction_types", "ligand_atoms", "receptor_atoms",
    ])
    report = output_dir / "report.html"
    write_html_report(
        report, ranking, comparison, cluster_rows, contacts, len(dlgs), top_n,
        activity_stats, plip_rows, plip_status,
    )
    evidence = {
        "rules": [
            "Only discuss values present in generated files.",
            "Do not invent residues, interactions, scores, or statistical significance.",
            "Docking and PLIP interactions are computational predictions, not experimental proof.",
            "Separate experimental IC50 values from docking-derived quantities.",
        ],
        "grid": grid_metadata or {},
        "activity_statistics": activity_stats,
        "plip": {
            "enabled": run_plip,
            "complexes_attempted": len(plip_status),
            "complexes_completed": sum(row.get("status") == "complete" for row in plip_status),
            "interaction_rows": len(plip_rows),
        },
        "files": {
            "ranking": "ranking.csv", "comparison": "comparison.csv",
            "clusters": "clusters.csv", "contacts": "contacts.csv",
            "activity": "activity.csv", "activity_statistics": "activity_statistics.json",
            "plip_interactions": "plip_interactions.csv", "plip_status": "plip_status.csv",
            "report": "report.html",
        },
    }
    (output_dir / "evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    (output_dir / "CODEX_DISCUSSION_PROMPT.md").write_text(
        "# SIDock AD4 evidence-based writing task\n\n"
        "Read evidence.json and the generated CSV files before writing. Every numerical, "
        "residue, interaction, and statistical claim must be traceable to those outputs. "
        "Do not invent missing data. Distinguish docking predictions, PLIP annotations, "
        "and experimental activity, and state their limitations.\n",
        encoding="utf-8",
    )
    return {
        "report": report, "ranking": output_dir / "ranking.csv", "comparison": output_dir / "comparison.csv",
        "clusters": output_dir / "clusters.csv", "contacts": output_dir / "contacts.csv",
        "activity": output_dir / "activity.csv", "activity_statistics": output_dir / "activity_statistics.json",
        "plip_interactions": output_dir / "plip_interactions.csv", "plip_status": output_dir / "plip_status.csv",
        "evidence": output_dir / "evidence.json",
        "successful": len(ranking), "total": len(dlgs), "poses": len(best_pose_by_ligand),
        "plip_completed": sum(row.get("status") == "complete" for row in plip_status),
    }
