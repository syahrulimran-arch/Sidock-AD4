# SIDock AD4 0.7.7 analysis and PLIP guide

SIDock keeps its original AutoDock4 post-docking analysis and adds the
activity/evidence workflow from SIDock Ubuntu plus optional PLIP interaction
profiling. The original geometry-based contacts and PLIP results are reported
separately because they use different definitions.

## Running the analysis

1. Open or create the SIDock project.
2. On **4 Screen & results**, set **Top poses for receptor-contact analysis**.
3. Leave **Run PLIP profiling and create 2D interaction maps** selected when
   PLIP output is required.
4. Run the screen normally, or click **Analyze existing results** for existing
   DLG files.
5. Click **Open analysis report**.

PLIP is bundled with the Windows installer. It is not necessary to select a
PLIP executable or install a separate Python environment. If PLIP cannot
analyze one complex, that ligand is marked as failed in `plip_status.csv`; the
docking ranking and all other analysis outputs are still retained.

## Experimental activity data

SIDock reads numerical IC50 values from properties in the normalized ligand
SDF files. Supported property names are:

- `IC50`
- `IC50_UM` or `IC50_uM`
- `IC50 (uM)`
- `IC50_MICROMOLAR`
- `IC50 µM` or `IC50 μM`

Values are interpreted as micromolar. Compound names must match the names used
for the prepared ligand and DLG file. SIDock calculates
`pIC50 = -log10(IC50 in molar units)`. Pearson correlation, Spearman
correlation, and linear R² are calculated only when at least three numerical
ligand/activity pairs match. These statistics describe association; they do
not validate docking accuracy or establish causation.

## Generated files

| File | Purpose |
|---|---|
| `report.html` | Combined ranking, plots, contacts, activity and PLIP report |
| `ranking.csv` | Binding-energy order and best-pose links |
| `comparison.csv` | Transparent consensus comparison |
| `clusters.csv` | AutoDock cluster summary |
| `contacts.csv` | SIDock geometry-based contacts |
| `activity.csv` | Extracted IC50 and calculated pIC50 values |
| `activity_statistics.json` | Matched data and correlation statistics |
| `activity_scatter.svg` | Docking energy versus pIC50 plot |
| `plip_interactions.csv` | Normalized PLIP interaction records |
| `plip_status.csv` | Per-ligand PLIP completion or error status |
| `plip_maps/*.svg` | Downloadable ligand-centred 2D interaction maps |
| `evidence.json` | Machine-readable grid, activity and PLIP evidence summary |
| `CODEX_DISCUSSION_PROMPT.md` | Traceability rules for evidence-based writing |

The report provides **Open 2D map** and **Download SVG** controls. When the
normalized SDF is available, the map contains an RDKit-rendered ligand
structure surrounded by the PLIP-identified residues. If the SDF cannot be
read, SIDock creates a labelled ligand placeholder instead of failing.

## Interpretation limits

- Docking scores are scoring-function predictions, not measured binding free
  energies.
- PLIP labels geometric interaction patterns in a predicted pose; they are not
  energetic decompositions or experimental proof of binding.
- Protonation, tautomer state, receptor preparation, retained cofactors and
  the selected grid can materially change the result.
- Inspect the downloaded receptor-ligand PDB complex and the 2D map before
  making residue-level claims.
- Use `evidence.json` and the CSV files as the source of numerical and residue
  claims. Do not infer missing values.
