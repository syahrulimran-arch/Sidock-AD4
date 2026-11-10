# SIDock AD4

**Developed by Dr Syahrul Imran**

**SIDock** means **Streamlined Interface for Docking** and is pronounced
"sigh-dock." Version 0.7.0 introduces the SIDock AD4 product name across the
application, executable, installer, shortcuts, Python package, reports, and
build system. Projects made with releases under the former DockFlow AD4 name
remain compatible, and saved tool settings are migrated automatically.

Version 0.7.9 fixes treated-PDB receptor preparation in the installed Windows
application by packaging Open Babel's `.obf` format plugins and supplying the
final directory separator required by its Windows plugin loader. Tool checking
and the frozen-runtime self-test verify that both PDB and PDBQT formats can be
loaded, preventing an incomplete installer from being published.

Version 0.7.7 adds optional bundled PLIP interaction profiling for the top
ranked receptor-ligand complexes, downloadable per-ligand 2D interaction maps,
detailed interaction/status CSV files, experimental IC50/pIC50 extraction from
SDF properties, docking-versus-activity statistics and plot, plus an auditable
evidence bundle and discussion prompt. A PLIP failure is reported per ligand
and does not discard the docking ranking or the existing geometric analysis.

Version 0.7.6 packages the x64 LLVM OpenMP runtime required by common Windows
AutoDock-GPU builds. SIDock adds its private runtime directory to the external
tool environment automatically, so end users no longer need to install
`libomp140.x86_64.dll`, copy it into System32, or modify the AutoDock folder.
The AutoDock-GPU executable and GPU driver remain user-supplied.

Version 0.7.5 makes AutoDock-GPU failures diagnosable. Command logs now retain
the numeric exit code and decode common Windows loader failures such as missing
DLLs and 32/64-bit mismatches. The results table displays each ligand's error,
the tool check verifies that the selected GPU executable can launch, and a
screen with zero usable DLGs is reported as a failure instead of success.

Version 0.7.4 fixes an omitted GUI import that interrupted existing-project
population before the Receptor & grid tab could be unlocked. The exact GUI
sequence—launch, select an existing project, open it, and verify all workflow
tabs and preparation buttons—is now an automated regression test.

Version 0.7.3 fixes project reopening so all receptor and ligand workflow
controls are explicitly restored. Ligand preparation now shows its ETKDG and
force-field minimization stages in the ligand table and audits the normalized
SDF before Meeko can receive it. The packaged-runtime self-test also performs
a real MMFF94 minimization and verifies that reopening a project enables the
two preparation buttons.

Version 0.7.2 adds an optional AutoDock-GPU docking engine. Select a user-installed AutoDock-GPU executable on the Project tab and choose the engine on the Screen tab. AutoGrid4 still generates the shared grid maps. CPU and GPU DLGs, results, and reports are kept in separate project folders. AutoDock-GPU is not included in the installer. Its CUDA/OpenCL runtime and supported hardware must be installed separately. See `documentation/AutoDock_GPU_Guide_v0.7.2.md` for setup and verification.

Version 0.7.1 creates a visualization-ready receptor-ligand PDB complex for
every extracted best pose. The HTML ranking tables provide separate **Open
complex** and **Download PDB** controls, while retaining the ligand-only PDBQT
pose for compatibility.

The ligand minimization workflow generates a user-selected conformer ensemble
when 3D coordinates are missing,
minimizes every candidate, requires convergence, and sends the lowest-energy
converged conformer to Meeko. The ligand table and `geometry_summary.csv` show
the initial and final force-field energies, energy change, coordinate RMSD,
conformer counts, elapsed time, and convergence result. Version 0.6.6 prevents
installation on unsupported Windows versions and requires 64-bit Windows 10
version 1809 (build 17763) or newer, including Windows 11. Version 0.6.5 reads AutoDock's unprefixed cluster-representative records and
clustering histogram, preserving atom types when merging them with docked
poses. Version 0.6.4 made project and tool input/output paths absolute, including
projects entered with a relative name such as `testing`. Version 0.6.3
automatically migrated legacy `mk_prepare_ligand.py` and
`mk_prepare_receptor.py` tool settings to bundled Meeko. Version 0.6.2 fixed
bundled Meeko execution in the installed application and
prevents tool subprocesses from opening duplicate SIDock windows. Version
0.6.1 added automatic post-docking analysis and explicit compound
comparison. SIDock now extracts each
best pose, summarizes AutoDock clusters, calculates ligand efficiency, annotates
geometry-based residue, hydrophobic, polar, putative hydrogen-bond, and metal
coordination contacts, and creates ranking, cluster, and contact CSV files plus
a self-contained HTML report with energy plots. Compounds receive separate
binding-energy, ligand-efficiency, and cluster-support ranks plus a transparent
consensus rank weighted 65%, 25%, and 10%, respectively. Contact counts are
shown side by side but do not inflate the score. The analysis runs after docking
and can be rerun for existing DLG files.

Current version: **0.7.9**

SIDock AD4 is a Windows-friendly Python desktop application for batch virtual screening with AutoGrid4 and either AutoDock4 or optional AutoDock-GPU. It keeps the native AutoDock4 file formats visible while replacing the repetitive command-line workflow with four guided tabs.

Complete end-user, scientific, troubleshooting, and developer guidance is
provided in `documentation/SIDock_AD4_Software_Documentation_v0.7.1.pdf` and
the editable Word version beside it. These documents describe the 0.7.1 CPU workflow; see the 0.7.2 GPU supplement for the new engine.
The v0.7.7 analysis, experimental-activity and PLIP workflow is documented in
`documentation/Analysis_and_PLIP_Guide_v0.7.7.md`.

## What the first version does

- accepts multi-molecule SDF plus single-molecule MOL and MOL2 files;
- cleans names, adds explicit hydrogens, generates and minimizes a 3D conformer ensemble when needed, selects the lowest-energy converged conformer, and prepares one PDBQT per ligand through Meeko;
- prepares a rigid receptor PDBQT through Meeko, with explicit chain selection and selective cofactor retention;
- accepts a treated PDB through rigid Open Babel conversion or an already prepared PDBQT without conversion;
- defines the grid numerically or obtains its center and size from a reference ligand;
- creates an AutoGrid GPF using the union of every ligand atom type;
- runs `autogrid4.exe` once and `autodock4.exe` across the ligand library with configurable parallel jobs;
- can select an external AutoDock-GPU executable for sequential GPU docking, with its required LLVM OpenMP runtime supplied privately and CPU/GPU results kept separately;
- supports cancellation, resuming a project, and rerunning only failed ligands;
- parses DLG binding energies and writes a ranked `results/results.csv` file;
- extracts best-pose PDBQT files, creates receptor-ligand PDB complexes, and writes an interactive post-docking HTML report with open and download controls;
- optionally runs bundled PLIP on top-ranked complexes and creates detailed interaction CSV files plus ligand-centred 2D SVG maps;
- extracts IC50 metadata from prepared SDF files, calculates pIC50 correlations when sufficient matched data exist, and writes an evidence bundle for traceable reporting;
- preserves every PDBQT, GPF, DPF, GLG, DLG, command, and error log for auditability.

SIDock does not modify or redistribute AutoDock executables. Supply `autogrid4.exe` and your selected docking engine executable yourself.

## Installation on Windows

### Normal installer (recommended)

Download `SIDock_AD4_Setup_v0.7.9.exe`, double-click it, and follow the
wizard. The installed application includes Python, PySide6, RDKit, Meeko,
SciPy, Gemmi, and Open Babel. Conda and manual `pip` commands are not required.

The installer requires **64-bit Windows 10 version 1809 (OS build 17763) or
newer**, including Windows 11. It checks both the Windows version and the
64-bit architecture before copying application files. Windows 7, Windows 8,
Windows 8.1, 32-bit Windows, and older Windows 10 builds are not supported.

AutoGrid4 and AutoDock4 remain external because SIDock does not redistribute
them. Select `autogrid4.exe` and `autodock4.exe` on the Project tab the first
time SIDock is used. MGLTools also remains optional and external; it is only
needed for the AutoDockTools receptor mode.

### Source/developer installation

Miniforge/Conda is recommended because RDKit is substantially easier to install reliably that way. From the extracted source folder, either create the environment manually or use the supplied file:

```powershell
conda create -n sidock -c conda-forge python=3.11 rdkit pyside6 numpy scipy gemmi openbabel plip
conda activate sidock
pip install meeko
pip install -e .
sidock
```

Alternatively:

```powershell
conda env create -f environment.yml
conda activate sidock
pip install -e .
run_sidock.bat
```

Leave both Meeko fields at **Bundled Meeko (automatic)**. SIDock invokes the Meeko module inside the application, so Windows does not need to find or launch a separate Python interpreter. Old project values are upgraded automatically. The **Check tool setup** button verifies Meeko plus both AutoDock executables before a run. A manually selected Meeko script remains supported.

For a CYP or other metalloprotein receptor, install AutoDockTools/MGLTools from
the official AutoDockTools download linked by the AutoDock project. On the
SIDock **Project** tab, select the MGLTools `python.exe` (or `pythonsh.exe`)
and its `AutoDockTools/Utilities24/prepare_receptor4.py` script. Then choose
**Treated PDB — AutoDockTools (recommended for HEM/metals)**. SIDock uses
`-A hydrogens -U nphs_lps_waters`, which retains nonstandard residues such as
HEM instead of deleting them.

Version 0.3.0 provides three receptor modes: Meeko preparation for a raw PDB, structure-preserving rigid Open Babel conversion for a treated PDB, and direct use of an existing PDBQT. Treated-PDB mode bypasses Meeko residue-template matching and does not delete failed residues. Open Babel assigns Gasteiger charges and AutoDock atom types while writing one rigid PDBQT.

The ligand geometry controls use RDKit to add explicit hydrogens and generate
missing 3D coordinates with ETKDGv3. The **Generated conformers** setting
defaults to 10; every candidate is minimized with MMFF94, MMFF94s, or UFF, and
the lowest-energy converged conformer is retained. If the imported molecule
already has 3D coordinates, SIDock respects those coordinates and minimizes
the supplied conformer instead of replacing it with generated conformers.

**Maximum iterations per conformer** is a ceiling, not a required number of
steps, so a small molecule may legitimately finish quickly. SIDock verifies
the return status and energy, fails rather than silently passing a
non-converged conformer to Meeko, and records the audit values in the normalized
SDF and `ligands/source/geometry_summary.csv`. It never silently changes the
selected force field when parameters are unavailable.

For the supplied treated **5TZ1** structure, use chain `A`, retain `HEM`, and
use the isolated `VT1` coordinates as the grid-box reference if available.

## Typical workflow

1. **Project**: select a new project folder and locate AutoGrid, AutoDock, Meeko, and Open Babel.
2. **Receptor & grid**: choose raw PDB, treated PDB, or prepared PDBQT mode and define the grid box. The box may be typed directly or calculated from a co-crystallized/reference ligand plus padding.
3. **Ligands**: add SDF/MOL/MOL2 files, choose 3D generation and MMFF94/MMFF94s/UFF minimization settings, then prepare the PDBQT files. SIDock records failures without discarding successful molecules.
4. **Screen**: choose the number of AutoDock runs and parallel processes, generate the common grids, run the screen, and open the ranked results.
5. **Analyze**: choose how many top poses receive contact analysis. SIDock automatically creates energy plots, ligand-efficiency rankings, cluster summaries, best-pose PDBQT files, and receptor-contact tables. **Analyze existing results** rebuilds the report without rerunning docking.

## Receptor preparation warning

The input receptor should have the intended residues, cofactors, and coordination state. Treated-PDB mode can add hydrogens and assigns Gasteiger charges during conversion, but it deliberately trusts the supplied geometry and bypasses Meeko's residue-template checks. SIDock does not repair missing atoms, clashes, metal coordination, or crystallographic alternatives.

For **Box from reference ligand**, select a file containing only the isolated bound ligand. Selecting the entire receptor makes the requested box exceed AutoGrid's 126-point-per-axis limit; SIDock now detects this and asks for a ligand-only file instead of silently clipping the box.

## Project layout

```text
project/
  project.json
  receptor/
  ligands/source/
    geometry_summary.csv
  ligands/prepared/
  grid/
  docking/dpf/
  docking/dlg/
  logs/
  results/results.csv
  analysis/report.html
  analysis/ranking.csv
  analysis/comparison.csv
  analysis/clusters.csv
  analysis/contacts.csv
  analysis/activity.csv
  analysis/activity_statistics.json
  analysis/activity_scatter.svg
  analysis/plip_interactions.csv
  analysis/plip_status.csv
  analysis/evidence.json
  analysis/CODEX_DISCUSSION_PROMPT.md
  analysis/poses/
  analysis/complexes/
  analysis/plip_maps/
```

## Building the Windows installer

On a 64-bit Windows 10 version 1809 or newer, or Windows 11, double-click
`Build-Installer.bat`. The build script creates an isolated build environment,
runs the tests, freezes the application, and compiles the setup wizard. The
finished file is written to:

```text
dist\installer\SIDock_AD4_Setup_v0.7.9.exe
```

Conda or Miniforge must already be installed for this one-time developer build.
If Inno Setup is absent, the script can install it through Windows Package
Manager (`winget`). End users need none of these build tools.

See `BUILD_INSTALLER.md` for troubleshooting and release checks.

## Development and tests

```powershell
pip install -e .[dev]
pytest
```

The test suite exercises 3D embedding, force-field convergence and energy
auditing, SDF splitting, atom-type collection, GPF/DPF generation, DLG parsing,
ranking, and mock command execution without requiring licensed/proprietary
software or real docking runs.

## Scope

This release targets rigid-receptor AutoDock4 Lamarckian genetic-algorithm screening. Contact annotations are distance-based screening aids, not free-energy decomposition. Flexible residues, covalent docking, hydrated docking, Zn-specific parameters, and embedded 3D pose visualization remain outside the current scope.
