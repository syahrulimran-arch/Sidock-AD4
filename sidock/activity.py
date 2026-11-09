from __future__ import annotations

import csv
import html
import json
import math
import re
from pathlib import Path
from typing import Iterable

from .core import safe_stem


IC50_KEYS = (
    "IC50", "IC50_UM", "IC50_uM", "IC50 (uM)", "IC50_MICROMOLAR",
    "IC50 µM", "IC50 μM",
)
ID_KEYS = ("Compound_ID", "COMPOUND_ID", "ID", "Name", "NAME")


def _number(value: object) -> float | None:
    text = str(value or "").strip().replace("µ", "u").replace("μ", "u")
    match = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", text)
    return float(match.group(0)) if match else None


def _key(value: object) -> str:
    return safe_stem(str(value or "")).casefold()


def extract_activity_metadata(
    sdf_files: Iterable[Path], destination: Path,
) -> list[dict[str, object]]:
    """Read experimental IC50 values without altering the input structures."""
    try:
        from rdkit import Chem
    except ImportError as exc:
        raise RuntimeError("RDKit is required to read ligand activity metadata.") from exc

    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for source in sdf_files:
        if source.suffix.lower() != ".sdf" or not source.is_file():
            continue
        supplier = Chem.SDMolSupplier(str(source), removeHs=False)
        for index, molecule in enumerate(supplier, start=1):
            if molecule is None:
                continue
            properties = {name: molecule.GetProp(name) for name in molecule.GetPropNames()}
            title = molecule.GetProp("_Name").strip() if molecule.HasProp("_Name") else ""
            ligand = next(
                (properties[name].strip() for name in ID_KEYS if properties.get(name, "").strip()),
                title or f"{source.stem}_{index}",
            )
            raw = next((properties[name] for name in IC50_KEYS if name in properties), None)
            ic50 = _number(raw)
            key = _key(ligand)
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "ligand": safe_stem(ligand, f"{source.stem}_{index}"),
                "ic50_uM": "" if ic50 is None else f"{ic50:.8g}",
                "pIC50": "" if not ic50 or ic50 <= 0 else f"{-math.log10(ic50 * 1e-6):.6f}",
                "source": str(source),
            })

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ligand", "ic50_uM", "pIC50", "source"])
        writer.writeheader()
        writer.writerows(rows)
    return rows


def correlate_activity(
    ranking: list[dict[str, object]], activity: list[dict[str, object]], destination: Path,
) -> dict[str, object]:
    """Match ligand names and calculate traceable score/activity statistics."""
    lookup = {_key(row.get("ligand")): row for row in activity}
    matched: list[dict[str, object]] = []
    for row in ranking:
        item = lookup.get(_key(row.get("ligand")))
        if not item or item.get("pIC50") in {"", None}:
            row["ic50_uM"] = ""
            row["pIC50"] = ""
            continue
        row["ic50_uM"] = item["ic50_uM"]
        row["pIC50"] = item["pIC50"]
        matched.append({
            "ligand": str(row["ligand"]),
            "energy_kcal_mol": float(row["energy_kcal_mol"]),
            "ic50_uM": float(item["ic50_uM"]),
            "pIC50": float(item["pIC50"]),
        })

    stats: dict[str, object] = {
        "n": len(matched),
        "rows": matched,
        "pearson_energy_vs_pIC50": None,
        "pearson_p": None,
        "spearman_energy_vs_pIC50": None,
        "spearman_p": None,
        "r2_linear": None,
    }
    if len(matched) >= 3:
        import numpy as np
        import scipy.stats as scipy_stats

        x = np.asarray([row["energy_kcal_mol"] for row in matched], dtype=float)
        y = np.asarray([row["pIC50"] for row in matched], dtype=float)
        pearson = scipy_stats.pearsonr(x, y)
        spearman = scipy_stats.spearmanr(x, y)
        coefficients = np.polyfit(x, y, 1)
        predicted = np.polyval(coefficients, x)
        residual = float(np.sum((y - predicted) ** 2))
        total = float(np.sum((y - y.mean()) ** 2))
        stats.update({
            "pearson_energy_vs_pIC50": float(pearson.statistic),
            "pearson_p": float(pearson.pvalue),
            "spearman_energy_vs_pIC50": float(spearman.statistic),
            "spearman_p": float(spearman.pvalue),
            "r2_linear": (1.0 - residual / total) if total else None,
        })
    destination.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return stats


def write_activity_scatter_svg(stats: dict[str, object], destination: Path) -> Path | None:
    rows = stats.get("rows", [])
    if not isinstance(rows, list) or len(rows) < 2:
        return None
    width, height = 820, 500
    left, right, top, bottom = 80, 30, 45, 70
    xs = [float(row["energy_kcal_mol"]) for row in rows]
    ys = [float(row["pIC50"]) for row in rows]
    xpad = max((max(xs) - min(xs)) * 0.08, 0.25)
    ypad = max((max(ys) - min(ys)) * 0.08, 0.1)
    xmin, xmax = min(xs) - xpad, max(xs) + xpad
    ymin, ymax = min(ys) - ypad, max(ys) + ypad

    def sx(value: float) -> float:
        return left + (value - xmin) / (xmax - xmin) * (width - left - right)

    def sy(value: float) -> float:
        return height - bottom - (value - ymin) / (ymax - ymin) * (height - top - bottom)

    pieces = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" stroke="#64748b"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="#64748b"/>',
    ]
    for index in range(6):
        xv = xmin + index * (xmax - xmin) / 5
        yv = ymin + index * (ymax - ymin) / 5
        pieces.append(f'<text x="{sx(xv):.1f}" y="{height-bottom+22}" text-anchor="middle" font-size="12">{xv:.2f}</text>')
        pieces.append(f'<text x="{left-10}" y="{sy(yv)+4:.1f}" text-anchor="end" font-size="12">{yv:.2f}</text>')
    for row in rows:
        x, y = sx(float(row["energy_kcal_mol"])), sy(float(row["pIC50"]))
        label = html.escape(str(row["ligand"]))
        pieces.extend([
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#2f79c5"/>',
            f'<text x="{x+7:.1f}" y="{y-7:.1f}" font-size="11">{label}</text>',
        ])
    pieces.extend([
        f'<text x="{(left+width-right)/2:.1f}" y="{height-18}" text-anchor="middle" font-size="14">AutoDock4 binding energy (kcal/mol)</text>',
        f'<text transform="translate(22 {(top+height-bottom)/2:.1f}) rotate(-90)" text-anchor="middle" font-size="14">pIC50</text>',
        '</svg>',
    ])
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("".join(pieces), encoding="utf-8")
    return destination
