# SIDock AD4 Software Documentation

## User Manual Scientific Guidance Technical Reference and Release Guide

**Product:** SIDock AD4  
**Meaning:** Streamlined Interface for Docking  
**Pronunciation:** sigh-dock  
**Version:** 0.7.1  
**Platform:** 64-bit Windows 10 version 1809 or newer and Windows 11  
**Developer:** Dr Syahrul Imran  
**Document date:** 11 September 2026

## Document Purpose

This manual explains how to install, configure, use, validate, troubleshoot, build, and interpret SIDock AD4. It is written for researchers who conduct rigid-receptor virtual screening with AutoGrid4 and AutoDock4, as well as developers or laboratory administrators who prepare the Windows installer.

SIDock AD4 provides a guided interface around established molecular preparation and AutoDock4 workflows. It does not replace scientific judgment. Users remain responsible for receptor quality, ligand identity and protonation, grid placement, search adequacy, control selection, pose inspection, and interpretation of docking scores.

## Contents

1. Product overview and scope
2. System requirements and compatibility
3. Installation upgrade and removal
4. First run and tool configuration
5. Project model and workflow
6. Receptor preparation
7. Grid box definition
8. Ligand preparation and geometry minimization
9. Virtual screening with AutoGrid4 and AutoDock4
10. Post docking analysis and compound comparison
11. Scientific interpretation and quality control
12. Project files and data dictionary
13. Troubleshooting
14. Reproducibility data integrity and security
15. Developer installation and Windows build
16. Test and release requirements
17. Limitations
18. External documentation
19. Appendices

## 1 Product Overview and Scope

### 1.1 Product identity

SIDock AD4 means Streamlined Interface for Docking with AutoDock4. The product name contains no personal name. Developer attribution appears separately in the About dialog, installer publisher information, and this manual.

Version 0.7.0 is the first release under the SIDock AD4 name. Earlier releases used the name DockFlow AD4. Existing project folders remain compatible because the `project.json` structure and project directories are retained. Saved tool paths are copied from the former application settings when SIDock AD4 is started for the first time.

Version 0.7.1 adds a visualization-ready receptor-ligand PDB complex for every extracted best pose. The HTML report provides separate controls to open the complex and download it, while retaining the ligand-only PDBQT pose for compatibility and auditability.

### 1.2 Intended use

SIDock AD4 supports batch rigid-receptor docking and screening. It coordinates ligand normalization, receptor conversion, grid generation, AutoDock4 job execution, result collection, ranking, pose extraction, cluster reporting, and geometry-based contact annotation.

The application is intended for research, teaching, method development, and preliminary prioritization. It is not a clinical diagnostic system, a validated regulatory decision system, or a substitute for experimental binding measurements.

### 1.3 Main capabilities

- Accepts multi-molecule SDF files and single-molecule MOL or MOL2 files.
- Adds explicit ligand hydrogens and generates missing three-dimensional coordinates.
- Generates an ETKDGv3 conformer ensemble and minimizes candidates with MMFF94, MMFF94s, or UFF.
- Requires force-field convergence and selects the lowest-energy converged conformer.
- Records ligand energy and convergence evidence in SDF properties and `geometry_summary.csv`.
- Prepares ligand PDBQT files with bundled Meeko.
- Supports four receptor input modes, including direct prepared PDBQT use.
- Defines the grid manually or from an isolated or receptor-bound reference ligand.
- Generates one AutoGrid calculation from the union of ligand atom types.
- Runs multiple AutoDock4 ligand jobs in parallel.
- Preserves completed work when a run is cancelled and can retry failed ligands only.
- Produces binding-energy, ligand-efficiency, cluster-support, and consensus rankings.
- Extracts best-pose PDBQT files and creates a self-contained HTML report.
- Reports geometry-based receptor contacts for a user-selected number of top poses.

### 1.4 Components and responsibilities

| Component | Role in SIDock AD4 | Distribution status |
| --- | --- | --- |
| SIDock interface | Project management, workflow control, file generation, parsing, ranking, and reporting | Included |
| Python runtime | Runs the installed application | Included |
| PySide6 and Qt | Desktop interface | Included |
| RDKit | Ligand parsing, hydrogen addition, conformer generation, and force-field minimization | Included |
| Meeko | Ligand and raw-PDB receptor preparation for AutoDock | Included |
| Open Babel | Structure-preserving treated-PDB conversion | Included |
| SciPy and Gemmi | Scientific runtime dependencies | Included |
| AutoGrid4 | Generates affinity and electrostatic maps | User supplied |
| AutoDock4 | Performs docking searches | User supplied |
| AutoDockTools and MGLTools | Optional receptor preparation for HEM, metals, or established ADT workflows | User supplied and optional |

### 1.5 Scientific boundary

SIDock automates a transparent AutoDock4 workflow. It does not alter the AutoDock4 scoring function, search algorithm, map calculation, DLG format, or PDBQT format. Generated GPF and DPF files remain accessible for audit and manual inspection.

## 2 System Requirements and Compatibility

### 2.1 Supported operating systems

| Requirement | Supported value |
| --- | --- |
| Architecture | 64-bit x86 compatible Windows |
| Minimum operating system | Windows 10 version 1809 build 17763 |
| Also supported | Newer 64-bit Windows 10 builds and Windows 11 |
| Not supported | Windows 7, Windows 8, Windows 8.1, 32-bit Windows, and Windows 10 builds older than 17763 |

The installer performs operating-system and architecture checks before copying files. This prevents installation on systems that cannot load the bundled Qt and scientific runtime. Installing individual DLL files on Windows 7 is not a supported workaround.

### 2.2 Recommended hardware

- A modern multi-core 64-bit processor.
- At least 8 GB RAM for routine small or medium screens; larger libraries may benefit from more memory.
- Several gigabytes of free disk space for the application, grids, logs, DLG files, and extracted poses.
- An SSD is recommended for large screens because many small map, work, and log files are created.
- A GPU is not required by this SIDock AD4 and AutoDock4 workflow.

### 2.3 Required external programs

End users must provide `autogrid4.exe` and `autodock4.exe`. SIDock does not redistribute them. MGLTools is required only when the AutoDockTools receptor mode is selected. Normal ligand preparation uses bundled Meeko, and treated-PDB conversion can use bundled Open Babel.

### 2.4 File and folder considerations

Use a project folder to which the current Windows account has write permission. A location under Documents or another research-data drive is normally suitable. Avoid read-only network shares. Long paths and spaces are supported because SIDock resolves project and tool paths to absolute paths and invokes commands without shell-string concatenation.

## 3 Installation Upgrade and Removal

### 3.1 Normal installation

1. Obtain `SIDock_AD4_Setup_v0.7.1.exe` from the trusted distributor.
2. Confirm that the computer meets the operating-system requirement.
3. Double-click the installer.
4. Review the destination folder.
5. Leave **Create a desktop shortcut** selected if a desktop shortcut is wanted. It is selected by default.
6. Complete the wizard and launch SIDock AD4.

The installer creates a Start Menu shortcut, an optional desktop shortcut, and an uninstaller. Administrative rights are not normally required because the default installation is under the current user's local application data directory.

### 3.2 SmartScreen and unsigned installers

An unsigned installer may display a Microsoft Defender SmartScreen warning stating that the publisher is unrecognized. This warning concerns code-signing reputation and is not by itself evidence of malware. Users should obtain the installer through a trusted channel and verify its supplied SHA-256 checksum. Broad distribution should use an Authenticode code-signing certificate.

### 3.3 Upgrade from DockFlow AD4

SIDock AD4 v0.7.1 uses the same installer application identity as the previous product. An upgrade can therefore replace the earlier installation. The upgrade removes the obsolete DockFlow executable and shortcuts, creates SIDock shortcuts, and retains existing project folders.

The first SIDock run imports saved AutoGrid4, AutoDock4, Meeko, Open Babel, and optional AutoDockTools paths from the former application settings when a SIDock value is not already present. Project-specific paths are also stored in each project's `project.json` file.

### 3.4 Uninstallation

Use **Settings > Apps > Installed apps > SIDock AD4 > Uninstall**, or use the Start Menu uninstaller. User-created project folders are research data and are not removed automatically. Delete them manually only after confirming that their inputs, logs, DLG files, reports, and results have been archived.

## 4 First Run and Tool Configuration

### 4.1 Project tab fields

| Field | Normal value | Required for |
| --- | --- | --- |
| AutoGrid4 executable | Full path to `autogrid4.exe` | All new screens |
| AutoDock4 executable | Full path to `autodock4.exe` | All docking jobs |
| Meeko ligand command | Bundled Meeko automatic | Ligand PDBQT preparation |
| Meeko receptor command | Bundled Meeko automatic | Raw PDB receptor mode |
| Open Babel executable | Bundled Open Babel | Treated PDB Open Babel mode |
| MGLTools Python executable | Full path to MGLTools Python or Pythonsh | AutoDockTools receptor mode only |
| AutoDockTools prepare receptor script | Full path to `prepare_receptor4.py` | AutoDockTools receptor mode only |

### 4.2 Recommended setup sequence

1. Browse to `autogrid4.exe` and `autodock4.exe`.
2. Keep both Meeko fields at **Bundled Meeko automatic**.
3. Keep Open Babel at **Bundled Open Babel** unless a specific external installation is required.
4. Leave the two MGLTools fields blank unless the AutoDockTools receptor mode will be used.
5. Click **Save tool paths**.
6. Click **Check tool setup**.

The tool check imports bundled Meeko directly inside the application rather than starting a second SIDock process. For a manually selected Meeko script or executable, it runs a 20-second help probe. Open Babel is reported separately because it is required only for treated-PDB conversion. AutoGrid4 and AutoDock4 checks confirm that the selected executable can be resolved.

### 4.3 Expected check results

An operational setup normally reports `OK` for AutoGrid4, AutoDock4, bundled Open Babel, Meeko ligand preparation, and Meeko receptor preparation. MGLTools is not part of the general tool check; its paths are validated when the AutoDockTools receptor mode is used.

## 5 Project Model and Workflow

### 5.1 Project concept

Every screen is stored in a self-contained project folder. The project file stores user inputs and settings, while subfolders preserve generated molecular files, grid maps, docking controls, raw outputs, logs, and reports. This design supports resuming a screen and auditing how a result was produced.

### 5.2 Four tab workflow

| Stage | Tab | Main action | Key output |
| --- | --- | --- | --- |
| 1 | Project | Create or open project and configure tools | `project.json` |
| 2 | Receptor and grid | Prepare receptor and define search box | `receptor.pdbqt` and grid settings |
| 3 | Ligands | Normalize geometry and prepare ligand PDBQT files | Normalized SDF and prepared PDBQT files |
| 4 | Screen and results | Run maps, docking, ranking, and analysis | DLG, CSV, poses, and HTML report |

### 5.3 Creating a project

Choose an empty or new folder and click **Create project**. If the folder already contains `project.json`, use **Open existing**. SIDock converts the project root to an absolute path, creates the required folder structure, and persists changes after each major stage.

### 5.4 Resuming work

Use **Open existing** and select the project folder. The interface restores receptor, ligand, grid, docking, analysis, and tool settings. Existing results are loaded into the results table. The **Retry failed only** option skips DLG files that already contain a parsable binding energy.

## 6 Receptor Preparation

### 6.1 Choosing a receptor mode

| Mode | Input | Processing | Appropriate use |
| --- | --- | --- | --- |
| Raw PDB prepare and validate with Meeko | PDB | Chain and residue cleanup followed by Meeko receptor preparation | Standard protein structures supported by Meeko templates |
| Treated PDB AutoDockTools | PDB | Cleanup followed by `prepare_receptor4.py` with hydrogens and standard cleanup | HEM, metal-containing systems, or established MGLTools workflows |
| Treated PDB preserve structure with Open Babel | PDB | Direct rigid conversion, optional hydrogen addition, Gasteiger charges | User-curated structures that should not undergo Meeko residue-template processing |
| Prepared PDBQT use directly | PDBQT | Validates AutoDock atom types and copies the file | Expert-prepared receptor that requires no conversion |

### 6.2 Cleanup options

**Protein chain** limits ATOM, HETATM, ANISOU, TER, and relevant LINK records to the selected chain. Leave it blank to keep all chains.

**Remove crystallographic waters** removes residues named HOH, WAT, H2O, and DOD. This option is enabled by default. Retain a structurally important water only when its role and parameterization have been considered deliberately.

**Remove HETATM except retained residue names** removes nonstandard residues unless their three-letter residue names appear in **Retain HETATM**. The retain field accepts comma, semicolon, or whitespace-separated values such as `HEM`.

After atom filtering, CONECT records are omitted because they may refer to deleted atoms. Raw-PDB Meeko processing reconstructs chemistry from templates and LINK records.

### 6.3 Raw PDB Meeko mode

The selected PDB is cleaned and written as `receptor/receptor_clean.pdb`. SIDock invokes the bundled Meeko receptor module internally and requests a receptor PDBQT plus box information. If Meeko fails, the dialog shows the final log lines and the complete log path.

Use this mode only when residue names and atoms are compatible with the installed Meeko templates. Missing residues, incomplete side chains, unusual protonation, metals, covalent cofactors, or nonstandard residues may require external treatment.

### 6.4 AutoDockTools mode

The cleaned input is written as `receptor/receptor_adt_input.pdb`. SIDock runs the selected MGLTools Python interpreter and `prepare_receptor4.py` with `-A hydrogens -U nphs_lps_waters`. This retains nonstandard residues such as HEM when they were retained during cleanup.

The quality of the outcome still depends on the user-supplied MGLTools installation and the chemically correct input structure. Inspect charges, atom types, metal handling, and cofactor connectivity.

### 6.5 Treated PDB Open Babel mode

This mode trusts the geometry supplied by the user and converts it to one rigid PDBQT. SIDock requests explicit PDB and PDBQT formats, optional hydrogen addition, Gasteiger partial charges, and rigid output.

Three conversion attempts may be made. The first uses standard input. If that output cannot be validated, the second ignores PDB CONECT records. If a retained metalloporphyrin still causes aromatic kekulization failure, the final compatibility attempt reads PDB bonds as single bonds. The preparation log records which output was accepted. A single-bond compatibility result should be reviewed carefully because aromatic and cofactor connectivity may have been simplified.

### 6.6 Prepared PDBQT mode

This mode copies an existing PDBQT without chemical conversion. SIDock verifies that at least one AutoDock atom type can be read. The user is responsible for every charge, atom type, hydrogen, residue, and connectivity decision in the supplied file.

### 6.7 Receptor validation checklist

- The intended chain or biological assembly is present.
- Missing atoms and residues have been addressed.
- Alternate locations have been resolved.
- Cofactors and metals are retained or removed intentionally.
- Waters are retained only with a scientific justification.
- Protonation and tautomeric states match the intended model.
- The final PDBQT contains plausible atom types and charges.
- The grid is centered on the intended binding region.

## 7 Grid Box Definition

### 7.1 Manual grid values

Enter the X, Y, and Z center coordinates, the point count for each axis, and the grid spacing. Point counts must be even and between 2 and 126. Spacing must be from 0.05 to 1.0 angstrom. The default is 60 points on each axis with 0.375 angstrom spacing.

The physical span of an axis is approximately the point count multiplied by the spacing. Increasing the box covers more space but increases map size and the ligand search region. It does not increase the structural detail of the receptor surface. Decreasing the spacing samples the energy grid more finely but increases computational and storage requirements for a fixed physical volume.

### 7.2 Box from reference ligand

Choose an isolated reference ligand in PDB or PDBQT format. SIDock calculates its coordinate bounds, adds 5 angstrom padding on every side, and converts the required lengths to even grid-point counts. The values remain editable.

Do not select an entire receptor file as the reference ligand. Its dimensions commonly exceed the 126-point AutoGrid limit. Extract the bound ligand into a separate coordinate file.

### 7.3 Box from bound ligand in receptor

Enter a residue name, such as `VT1`, and optionally select a receptor chain. SIDock finds that residue in the original receptor PDB, calculates the same 5 angstrom padded box, and leaves the resulting values editable. This operation reads the original coordinates and does not remove atoms.

### 7.4 Grid output

SIDock writes a GPF containing the grid dimensions, center, spacing, receptor atom types, the union of ligand atom types, one affinity map per ligand atom type, the electrostatic map, the desolvation map, smoothing of 0.5, and dielectric value of -0.1465. AutoGrid is run once before the ligand docking tasks begin.

## 8 Ligand Preparation and Geometry Minimization

### 8.1 Accepted formats

| Format | Handling |
| --- | --- |
| SDF | Every readable molecule record is processed separately |
| MOL | One molecule is read and processed |
| MOL2 | One molecule is read and processed |

Unreadable molecules are recorded as failures without discarding other molecules that can be processed. Names are sanitized for Windows-safe filenames and limited to 80 characters. Duplicate output names receive numeric suffixes.

### 8.2 Recommended default settings

| Setting | Default | Meaning |
| --- | --- | --- |
| Generate 3D coordinates when missing | Enabled | Generates coordinates only when the input lacks a 3D conformer |
| Optimize or minimize geometry | Enabled | Applies the selected force field |
| Force field | MMFF94 | Uses MMFF94 when all atom parameters are available |
| Generated conformers | 10 | Maximum requested candidates when 3D generation is needed |
| Maximum iterations per conformer | 500 | Ceiling for each minimization, not a mandatory step count |

### 8.3 Geometry workflow

1. RDKit reads the molecule and adds explicit hydrogens.
2. If no 3D coordinates are present and generation is enabled, existing two-dimensional conformers are removed.
3. ETKDGv3 generates up to the requested number of conformers with a deterministic random seed and 0.5 angstrom pruning threshold.
4. SIDock verifies that the selected force field has parameters for every atom.
5. A force-field object is initialized for each candidate.
6. The initial energy is calculated in kilocalories per mole.
7. Minimization runs with a force tolerance of 0.0001, energy tolerance of 0.000001, and the selected iteration ceiling.
8. The final energy and coordinate root-mean-square displacement are calculated.
9. A candidate is eligible only when RDKit returns successful convergence and the final energy is finite and does not increase beyond numerical tolerance.
10. The lowest final-energy converged conformer is retained and all other conformers are removed.
11. The audited SDF is passed to Meeko for PDBQT preparation.

If the input already contains 3D coordinates, SIDock does not replace them with newly generated conformers. It minimizes the available supplied conformer or conformers and retains the lowest-energy converged result.

### 8.4 Why minimization may finish quickly

The maximum iteration value is an upper limit. A small molecule or a structure already close to a local minimum can converge after relatively few steps. Runtime alone is therefore not a valid test of whether minimization occurred. SIDock verifies the RDKit return status and records the initial energy, final energy, energy change, coordinate displacement, conformer counts, and elapsed time.

### 8.5 Force field choice

MMFF94 is the normal starting choice for many drug-like organic molecules. MMFF94s is a related variant often used when static structures are of interest. UFF offers broader element coverage but is a different parameterization and should not be treated as an identical substitute.

SIDock never silently changes the selected force field. If MMFF parameters are unavailable, the molecule fails with a message suggesting UFF. The user must decide whether UFF is scientifically appropriate and repeat preparation.

### 8.6 Convergence policy

A return status indicating that more iterations are required is not accepted as success. If no candidate converges, no normalized SDF is sent to Meeko for that molecule. Increase the iteration ceiling, inspect the molecular structure, select a justified alternative force field, or prepare the ligand externally.

This policy prevents a technically generated but non-converged structure from entering docking without an explicit warning.

### 8.7 Geometry audit fields

The normalized SDF contains the following SIDock properties when optimization is enabled.

| SDF property | Meaning |
| --- | --- |
| `SIDock_3D_Generated` | Whether SIDock generated missing 3D coordinates |
| `SIDock_Optimization_Method` | MMFF94, MMFF94s, UFF, or None |
| `SIDock_Optimization_Status` | Converged or not requested |
| `SIDock_Max_Iterations` | Iteration ceiling per conformer |
| `SIDock_Conformers_Attempted` | Number of conformers minimized |
| `SIDock_Conformers_Converged` | Number that returned successful convergence |
| `SIDock_Selected_Conformer` | Identifier of the selected candidate |
| `SIDock_Initial_Energy_kcal_mol` | Initial force-field energy for the selected conformer |
| `SIDock_Final_Energy_kcal_mol` | Final force-field energy for the selected conformer |
| `SIDock_Energy_Change_kcal_mol` | Final energy minus initial energy |
| `SIDock_Coordinate_RMSD_A` | Root-mean-square atomic coordinate displacement during minimization |
| `SIDock_Geometry_Preparation_Seconds` | Elapsed geometry preparation time |

`ligands/source/geometry_summary.csv` records the same audit data in a tabular form. Failed geometry preparations are included with `status` set to `failed` and an explanatory `error` field.

### 8.8 Scientific limitations of ligand minimization

Force-field minimization locates a nearby local minimum. It does not prove that the selected conformer is the global minimum, the dominant solution conformer, or the bioactive conformation. The calculated MMFF or UFF energy is not an AutoDock binding energy and should never be compared directly with the docking score.

Before screening, verify molecular identity, stereochemistry, formal charge, protonation state, tautomer, salt handling, covalent structure, and suitability of the chosen force field. SIDock does not enumerate alternative stereoisomers, protonation states, or tautomers.

## 9 Virtual Screening with AutoGrid4 and AutoDock4

### 9.1 Screen settings

| Interface setting | Range or default | Effect |
| --- | --- | --- |
| GA runs per ligand | 1 to 1000 with default 10 | Number of independent Lamarckian genetic algorithm runs |
| Maximum evaluations | 1000 to 100000000 with default 2500000 | Search evaluation ceiling per run |
| Parallel AutoDock processes | 1 to detected CPU count | Number of ligand jobs executed concurrently |
| Top poses for contact analysis | 1 to 500 with default 20 | Number of energy-ranked ligands receiving contact annotation |

More GA runs and evaluations normally improve search sampling but increase runtime. Convergence should be evaluated through repeated poses, cluster populations, energy consistency, and control behavior rather than by assuming that one parameter setting is sufficient for every system.

### 9.2 Generated docking parameters

SIDock writes one DPF per ligand using AutoDock parameter version 4.2. Ligand translation, quaternion, and dihedrals start randomly. The ligand center is calculated from its PDBQT coordinates. The default population size is 150, maximum generations is 27000, RMS clustering tolerance is 2.0 angstrom, mutation rate is 0.02, crossover rate is 0.80, local-search frequency is 0.06, and the Solis-Wets local-search maximum is 300 iterations.

The interface exposes GA runs and maximum evaluations because these are the most common user adjustments. Other generated values are visible in the DPF and can be audited. Editing a generated DPF manually does not update `project.json` and may be overwritten by a later SIDock run.

### 9.3 Execution sequence

1. SIDock validates that the prepared receptor and at least one prepared ligand exist.
2. Receptor and ligand PDBQT files are copied into the grid workspace.
3. The union of all ligand atom types is collected.
4. One GPF is written and AutoGrid4 generates the required maps.
5. Maps are copied to the docking work folder.
6. One DPF is written for each ligand.
7. AutoDock4 jobs run concurrently up to the selected process limit.
8. Standard output and errors are captured in ligand-specific logs.
9. DLG files are parsed and `results/results.csv` is rebuilt from every available DLG.
10. Post-docking analysis runs automatically.

### 9.4 Cancellation and retry

Click **Cancel** to request termination. A running external process is first terminated and then killed if it does not exit within five seconds. Completed DLG files and results are preserved.

**Retry failed only** skips a ligand when its existing DLG contains a parsable binding energy. Failed, incomplete, or missing results are submitted again. Results are rebuilt from all DLG files after the retry.

### 9.5 Basic result status

`complete` means a binding energy was found and the DLG includes Successful Completion. `complete_with_warning` means an energy was found but the completion marker is missing. `failed` means no binding energy was found or AutoDock explicitly reported unsuccessful completion. Inspect the DLG and log for every warning or failure.

## 10 Post Docking Analysis and Compound Comparison

### 10.1 Automatic outputs

When docking ends, SIDock analyzes all DLG files. The same analysis can be rerun without docking by clicking **Analyze existing results**. The analysis produces:

- `analysis/report.html`
- `analysis/ranking.csv`
- `analysis/comparison.csv`
- `analysis/clusters.csv`
- `analysis/contacts.csv`
- one best-pose PDBQT per successfully parsed ligand under `analysis/poses`
- one visualization-ready receptor-ligand PDB complex per successfully parsed ligand under `analysis/complexes`

### 10.2 Binding energy ranking

The best reported AutoDock binding energy is selected for each ligand. More negative energy ranks higher. `ranking.csv` also reports the selected run, heavy-atom count, ligand efficiency, cluster rank and size when available, the ligand-only pose path, the receptor-ligand complex path, and source DLG.

The complex PDB contains all atoms from the prepared receptor together with the selected best-pose ligand coordinates. Protein and retained receptor cofactors keep their receptor residue information; the ligand is written as residue `LIG` in chain `L`. The complex is intended for visualization and pose inspection. Continue to use the source receptor PDBQT, ligand PDBQT, and DLG for AutoDock-specific charges, atom types, torsion records, and auditing.

Ligand efficiency is calculated as the negative of the best binding energy divided by the number of ligand heavy atoms. It is a size-normalized screening descriptor, not an experimental efficiency measurement.

### 10.3 Cluster parsing

SIDock reads AutoDock cluster-representative pose records and clustering histograms, including unprefixed records written after the docked pose blocks. Cluster size, best energy, and mean energy are written to `clusters.csv` when available.

An empty `clusters.csv` data section means that no usable cluster annotations were found. It does not necessarily mean that no binding energy was present. Confirm that the DLG completed its analysis section and contains clustering output.

### 10.4 Consensus comparison

The overall comparison normalizes available metrics and applies these weights:

| Component | Weight | Better direction |
| --- | --- | --- |
| Binding energy | 65 percent | More negative |
| Ligand efficiency | 25 percent | Higher |
| Cluster support | 10 percent | Larger cluster size |

Missing ligand-efficiency or cluster values are excluded and the remaining weights are renormalized. Contact counts are shown for comparison but do not increase the consensus score. Ties are resolved by energy and ligand name after the score ordering.

The consensus score is a transparent prioritization aid created by SIDock. It is not part of AutoDock4, has not been calibrated as a probability of activity, and should not be presented as a validated predictive model without independent evaluation.

### 10.5 Contact annotation

Contacts are grouped by receptor residue for the selected number of top-ranked poses.

| Contact label | Geometry rule |
| --- | --- |
| Close contact | Ligand and receptor heavy atoms at 4.0 angstrom or less |
| Hydrophobic | Compatible hydrophobic atom types at 4.5 angstrom or less |
| Polar contact | Acceptor-like atom types at 3.5 angstrom or less |
| Metal coordination | Ligand acceptor to receptor metal at 3.0 angstrom or less |
| Putative hydrogen bond | Explicit polar hydrogen to acceptor at 2.5 angstrom or less and donor heavy atom to acceptor at 3.5 angstrom or less |

These are distance-based annotations. They do not evaluate full angular geometry, solvation, entropic effects, electronic structure, or energetic decomposition. Putative hydrogen bonds depend on explicit polar hydrogens in the PDBQT. Inspect each pose with an appropriate molecular-visualization program before reporting an interaction.

### 10.6 HTML report

The self-contained report shows summary counts, best and central energy statistics, an energy bar chart, an energy histogram, overall comparison, binding-energy ranking, cluster table, and receptor-contact table. In the ranking and comparison tables, **Open complex** opens the receptor-ligand PDB in a new browser tab or the program associated with PDB files. **Download PDB** saves the same complete complex. Ligand-only PDBQT poses remain available under `analysis/poses`.

## 11 Scientific Interpretation and Quality Control

### 11.1 Minimum validation strategy

- Redock a co-crystallized ligand when a suitable structure is available.
- Compare the predicted pose with the crystallographic pose using a justified RMSD method.
- Include known active, inactive, or decoy compounds where possible.
- Confirm that the grid includes the intended pocket without unnecessary space.
- Check that receptor and ligand protonation states are appropriate for the modeled conditions.
- Inspect top poses for clashes, unrealistic torsions, buried charge, metal coordination, and key residue geometry.
- Examine cluster size and convergence across independent runs.
- Repeat uncertain results with increased sampling or an independent method.
- Treat docking results as hypotheses for experimental or higher-level computational evaluation.

### 11.2 Interpreting AutoDock energy

The reported value is an AutoDock scoring estimate used to rank poses under the chosen model. It is not a direct experimental Gibbs free energy. Differences of small magnitude may not be meaningful given scoring-function error, receptor rigidity, protonation uncertainty, and incomplete sampling.

Do not convert rankings directly into claims of potency or selectivity. A compound with a favorable score can still be inactive, insoluble, unstable, reactive, inaccessible to the binding site, or incorrectly modeled.

### 11.3 Comparing compounds

Use binding energy, ligand efficiency, cluster support, pose plausibility, and interaction consistency together. A large ligand can receive a favorable raw score through size alone, which is why ligand efficiency is displayed separately. A large cluster can support search consistency but does not prove biological relevance.

### 11.4 Reporting recommendations

A reproducible report should state the SIDock version, AutoDock4 and AutoGrid4 versions, receptor source and preparation method, retained cofactors and waters, ligand preparation method, force field, conformer count, iteration ceiling, grid center and dimensions, spacing, GA runs, evaluations, clustering tolerance, number of successful ligands, ranking rule, and pose-inspection method.

## 12 Project Files and Data Dictionary

### 12.1 Project directory

```text
project
  project.json
  receptor
    receptor.pdbqt
    receptor_clean.pdb or receptor_adt_input.pdb
  ligands
    source
      normalized ligand SDF files
      geometry_summary.csv
    prepared
      ligand PDBQT files
  grid
    receptor and ligand copies
    GPF GLG map and field files
  docking
    dpf
      ligand DPF files
    dlg
      ligand DLG files
    work
      runtime maps ligands and DPF files
  logs
    receptor ligand AutoGrid and AutoDock logs
  results
    results.csv
  analysis
    report.html
    ranking.csv
    comparison.csv
    clusters.csv
    contacts.csv
    poses
      best pose PDBQT files
    complexes
      receptor-ligand best-pose PDB files
```

### 12.2 Key CSV files

| File | Primary purpose | Important fields |
| --- | --- | --- |
| `geometry_summary.csv` | Ligand geometry audit | source, molecule, method, status, energies, coordinate displacement, conformer counts, elapsed time, error |
| `results.csv` | Basic AutoDock result collection | rank, ligand, best energy, best run, status, DLG, error |
| `ranking.csv` | Energy ranking and pose metadata | energy rank, ligand, energy, ligand efficiency, heavy atoms, run, cluster, pose, complex |
| `comparison.csv` | Multi-metric prioritization | consensus rank and score, component ranks, contact counts, pose and DLG paths |
| `clusters.csv` | Cluster summary | ligand, cluster rank, members, best energy, mean energy |
| `contacts.csv` | Residue-level geometric contacts | ligand, rank, residue, chain, distance, interaction types, atom names |

### 12.3 Project JSON groups

`project.json` stores the absolute project root, receptor paths and mode, ligand source and prepared paths, grid dimensions, docking parameters, tool paths, cleanup settings, ligand geometry settings, and analysis depth. It is human-readable JSON but should normally be edited through SIDock. Manual edits should be made only after closing the application and retaining a backup.

## 13 Troubleshooting

### 13.1 Application does not start because of a missing DLL

Use the current installer built by the supplied build process. The build copies the Conda scientific and Qt DLL set into the frozen runtime and runs `SIDock.exe --self-test` before compiling Setup. Do not distribute an installer if this self-test fails.

The Windows 7 error mentioning `api-ms-win-core-path-l1-1-0.dll` indicates an unsupported operating system. Use 64-bit Windows 10 version 1809 or newer. Do not download individual system DLL files from third-party websites.

### 13.2 No desktop or Start Menu shortcut

The Start Menu shortcut is always created. The desktop task is selected by default but can be cleared in the installer. Search for SIDock AD4 in the Start Menu. If an upgrade left an old shortcut, uninstall the former version and reinstall v0.7.1; the current installer also removes known old shortcut names during upgrade.

### 13.3 Tool check reports AutoGrid4 or AutoDock4 missing

Browse to the exact `.exe` file rather than its containing folder. Avoid a broken shortcut. Click **Save tool paths**, then repeat **Check tool setup**. AutoGrid4 and AutoDock4 are external and are not installed by SIDock.

### 13.4 Tool check reports Meeko missing

Restore both Meeko fields to **Bundled Meeko automatic**. Do not select `SIDock.exe`, a Conda activation script, or an obsolete `mk_prepare_ligand.py` wrapper unless an external Meeko installation is intentionally being used. Legacy automatic values and old application-executable paths are normalized automatically.

### 13.5 A button opens another SIDock window

This behavior was caused in early builds by starting the frozen GUI executable as if it were Python. Version 0.7.0 and later invoke bundled Meeko in-process and reject unexpected command-line arguments. Confirm that the installed version is 0.7.1 or later and that both Meeko fields use the bundled automatic value.

### 13.6 Receptor preparation fails with file not found

Open the displayed full log path and verify the input path recorded at the top. SIDock resolves current project paths absolutely. If an older project was moved, reselect the receptor source and prepare it again. For a raw PDB Meeko failure, inspect residue-template errors. For HEM or metals, consider the justified AutoDockTools or treated-PDB route.

### 13.7 Open Babel receptor output is invalid

Inspect `logs/prepare_receptor.log` and the standard or compatibility logs. Confirm that the treated PDB has valid fixed-column PDB records and intentional connectivity. A single-bond compatibility result requires manual review. If conversion remains inappropriate, prepare the receptor externally and use prepared PDBQT mode.

### 13.8 Ligand minimization appears too fast

Check the ligand row and `geometry_summary.csv`. A converged status with finite energies and a non-increasing final energy demonstrates that the minimizer completed successfully even when runtime is short. The iteration value is a ceiling. If coordinate displacement and energy change are very small, the input may already be near a local minimum.

### 13.9 Ligand minimization does not converge

Increase **Maximum iterations per conformer**, inspect valence and formal charges, or select a scientifically justified force field. If MMFF parameters are unavailable, evaluate UFF rather than assuming it is interchangeable. A failed ligand is not passed to Meeko.

### 13.10 Meeko ligand preparation fails after successful minimization

Open `logs/prepare_ligandname.log`. Check unsupported elements, unusual valence, disconnected fragments, charge state, stereochemistry, and the normalized SDF. Geometry convergence and PDBQT parameterization are separate checks; success in one does not guarantee success in the other.

### 13.11 AutoGrid fails

Inspect `logs/autogrid.log` and the GPF. Common causes include an incorrect executable, unsupported or missing atom-type parameters, an oversized grid, missing receptor maps, a malformed receptor PDBQT, or a non-writable project location.

### 13.12 AutoDock result or report is missing

Inspect the ligand-specific AutoDock log and DLG. `results.csv` includes failures even when no energy is available. The HTML report requires at least one DLG and a readable prepared receptor. If docking completed previously, use **Analyze existing results**.

### 13.13 Cluster table is empty

Open the DLG and confirm that AutoDock wrote its clustering analysis or histogram. An energy can be parsed even when cluster annotations are absent. Current SIDock parses both standard prefixed pose records and unprefixed cluster-representative records, but it cannot reconstruct clustering information that the DLG does not contain.

### 13.14 Complex open or download control does not work

Confirm that the corresponding file exists under `analysis/complexes` and that the whole project folder has not been partially moved. Re-run **Analyze existing results** to regenerate complex PDB files and relative links. Browser handling of **Open complex** depends on the local PDB file association; **Download PDB** remains available when the browser displays the PDB as text.

## 14 Reproducibility Data Integrity and Security

### 14.1 Audit trail

SIDock preserves input-derived files, normalized structures, prepared PDBQT files, GPF, DPF, GLG, DLG, logs, CSV reports, extracted poses, and receptor-ligand complex PDB files. Keep the entire project folder, not only the final ranking table.

### 14.2 Recommended archive contents

- Original receptor and ligand sources.
- Complete SIDock project folder.
- SIDock installer version and checksum.
- AutoGrid4 and AutoDock4 version information.
- Any external MGLTools version and scripts.
- Experimental control information and pose-validation results.
- A human-readable methods record explaining manual structure treatment.

### 14.3 File replacement and reruns

Repeated ligand preparation can create a numeric suffix rather than overwrite an existing normalized SDF with the same sanitized name. Confirm which outputs are referenced by `project.json`. A new screen rebuilds summary CSV files from current parsed outputs while preserving underlying DLG files.

### 14.4 Security considerations

Only select executables and scripts from trusted installations. A manually selected tool is executed with the current user's permissions. Project files may contain confidential structures and results; store and share them according to institutional policy. SIDock does not require cloud transfer for its local workflow.

## 15 Developer Installation and Windows Build

### 15.1 Source environment

The recommended development environment uses Python 3.11 and Conda Forge packages for RDKit, PySide6, NumPy, SciPy, Gemmi, Open Babel, pytest, PyInstaller, and build support. Meeko is installed through pip with the supported range `0.6` to below `0.8` in the Windows build script.

```powershell
conda env create -f environment.yml
conda activate sidock
pip install -e .
python -m sidock.app
```

For development tests:

```powershell
pip install -e .[dev]
pytest
```

### 15.2 One-click installer build

On a supported 64-bit Windows build computer with Conda or Miniforge installed, extract the source package and double-click `Build-Installer.bat`. The PowerShell builder:

1. Locates Conda.
2. Creates or reuses `.build/conda-env`.
3. Installs scientific, GUI, test, and packaging dependencies.
4. Installs Meeko and SIDock.
5. Runs the test suite.
6. Freezes the application with `packaging/SIDock.spec`.
7. Copies Conda DLLs from `Library/bin` into `dist/SIDock/_internal`.
8. Runs the packaged runtime self-test.
9. Locates or installs Inno Setup 6.
10. Compiles `SIDock_AD4_Setup_v0.7.1.exe`.

PyInstaller is not a cross-compiler. The Windows executable must be built on Windows.

### 15.3 Build output

The finished installer is written to:

```text
dist\installer\SIDock_AD4_Setup_v0.7.1.exe
```

Do not distribute an installer produced with tests skipped unless equivalent testing has been completed and documented. The `SkipTests` switch is for controlled developer troubleshooting, not normal release production.

### 15.4 GitHub Actions build

The included workflow can build the installer on a Windows runner when the source is placed in a GitHub repository. It creates a Conda environment, runs tests, freezes SIDock, performs the runtime self-test, compiles with Inno Setup, and uploads the Setup executable as an artifact.

## 16 Test and Release Requirements

### 16.1 Automated test coverage

The test suite covers safe filenames, PDBQT atom-type parsing, receptor cleanup, reference boxes, GPF and DPF generation, AutoDockTools command formation, command logging, bundled Meeko in-process execution, legacy setting normalization, prevention of duplicate GUI subprocesses, DLG energy and cluster parsing, pose extraction, receptor-ligand complex export, ranking and consensus logic, contact annotation, ligand geometry convergence, energy auditing, failure rejection, Windows compatibility directives, and version consistency.

### 16.2 Packaged runtime self-test

Before Setup compilation, the frozen executable imports Gemmi, Meeko, SciPy, Shiboken6, PySide6, and RDKit; verifies Meeko ligand and receptor entry points; and confirms the bundled Open Babel executable. A nonzero result stops the build.

### 16.3 Clean-machine release checklist

1. Build on supported 64-bit Windows.
2. Confirm every automated test passes.
3. Confirm the packaged self-test passes.
4. Install using a Windows account without Conda.
5. Launch from the Start Menu and desktop shortcut.
6. Run **Check tool setup**.
7. Prepare a small ligand and inspect the energy audit.
8. Prepare a representative receptor through every claimed mode available for the release.
9. Run a minimal AutoGrid and AutoDock job.
10. Confirm results, clusters, best pose, contacts, and HTML report.
11. Test **Analyze existing results**, cancellation, and **Retry failed only**.
12. Upgrade from the previous product and confirm old shortcuts are removed.
13. Uninstall and confirm that user project data remains.
14. Calculate and publish the installer SHA-256 checksum.
15. Code-sign the installer before broad distribution when possible.

## 17 Limitations

- Rigid receptor only.
- AutoDock4 Lamarckian genetic algorithm workflow only.
- No embedded AutoGrid4 or AutoDock4 executable distribution.
- No covalent, hydrated, or flexible-residue docking workflow.
- No automatic metal-specific or zinc-specific potential.
- No automatic receptor repair or missing-residue modeling.
- No automatic ligand tautomer, protonation, stereoisomer, or salt enumeration.
- No explicit solvent docking model.
- No molecular dynamics or free-energy calculation.
- No built-in three-dimensional pose viewer.
- Contact annotations are distance-based and not energetic.
- Consensus ranking is a heuristic prioritization tool.
- MMFF and UFF minimization does not establish a bioactive or global-minimum conformer.
- Windows 7 and 32-bit Windows are unsupported.

## 18 External Documentation

- AutoDock4 project information, downloads, and documentation: https://autodock.scripps.edu/
- Meeko documentation: https://meeko.readthedocs.io/
- RDKit documentation: https://www.rdkit.org/docs/
- RDKit force-field API: https://www.rdkit.org/docs/source/rdkit.ForceField.rdForceField.html
- Open Babel documentation: https://openbabel.org/docs/
- Qt for Python documentation: https://doc.qt.io/qtforpython-6/
- PyInstaller manual: https://pyinstaller.org/en/stable/
- Inno Setup help: https://jrsoftware.org/ishelp/

These upstream resources govern the behavior and licensing of their respective components. The versions installed during a build should be recorded with the release.

## 19 Appendices

### Appendix A Default Parameters

| Parameter | Default |
| --- | --- |
| Grid points X Y Z | 60 60 60 |
| Grid spacing | 0.375 angstrom |
| Reference ligand padding | 5 angstrom per side |
| Generate missing ligand 3D | Yes |
| Ligand optimization | Yes |
| Ligand force field | MMFF94 |
| Generated ligand conformers | 10 |
| Maximum minimization iterations | 500 per conformer |
| GA runs | 10 per ligand |
| Maximum GA evaluations | 2500000 |
| GA population size | 150 |
| Maximum GA generations | 27000 |
| RMS clustering tolerance | 2.0 angstrom |
| Parallel docking jobs | 1 in the project model with interface default based on CPU count |
| Top poses for contact analysis | 20 |

### Appendix B Interaction Distance Rules

| Interaction | Maximum distance |
| --- | --- |
| Close heavy-atom contact | 4.0 angstrom |
| Hydrophobic contact | 4.5 angstrom |
| Polar contact | 3.5 angstrom |
| Metal coordination | 3.0 angstrom |
| Polar hydrogen to acceptor | 2.5 angstrom |
| Hydrogen-bond donor heavy atom to acceptor | 3.5 angstrom |

### Appendix C Glossary

| Term | Meaning |
| --- | --- |
| AD4 | AutoDock4 |
| AutoGrid | Program that calculates receptor interaction maps used by AutoDock |
| DLG | AutoDock docking log containing run poses, scores, and analysis |
| DPF | AutoDock docking parameter file |
| GPF | AutoGrid parameter file |
| GLG | AutoGrid log file |
| ETKDG | RDKit distance-geometry method with experimental torsion-angle knowledge |
| MMFF94 | Merck Molecular Force Field 1994 |
| UFF | Universal Force Field |
| PDBQT | PDB-like format containing partial charges and AutoDock atom types |
| Ligand efficiency | Negative docking energy divided by ligand heavy-atom count in SIDock |
| Cluster support | Population of the selected AutoDock pose cluster |
| Consensus score | SIDock normalized weighted prioritization score |

### Appendix D Version History

| Version | Main change |
| --- | --- |
| 0.7.1 | Added visualization-ready receptor-ligand PDB complexes with open and download controls in the HTML report |
| 0.7.0 | Renamed product to SIDock AD4; comprehensive user and technical documentation; preserved earlier project and tool-setting compatibility |
| 0.6.7 | Added multi-conformer ligand minimization, convergence enforcement, energy and coordinate auditing, and geometry summary CSV |
| 0.6.6 | Enforced 64-bit Windows 10 build 17763 or newer |
| 0.6.5 | Improved parsing of unprefixed AutoDock cluster representatives and histograms |
| 0.6.4 | Made project and tool input and output paths absolute |
| 0.6.3 | Migrated legacy Meeko wrapper settings to bundled automatic execution |
| 0.6.2 | Fixed bundled Meeko execution and duplicate application windows |
| 0.6.1 | Added automatic post-docking analysis and compound comparison |

### Appendix E Quick Methods Record

For each study, record the following information alongside the archived project:

- SIDock AD4 version
- AutoGrid4 and AutoDock4 versions
- Receptor structure identifier and source
- Receptor preparation mode
- Selected chain
- Removed and retained residues, cofactors, metals, and waters
- Ligand sources and preparation state
- Force field and conformer settings
- Geometry convergence results
- Grid center, point counts, spacing, and physical dimensions
- GA runs, evaluations, and parallel processes
- Number of successful, warned, and failed ligands
- Energy, ligand-efficiency, cluster, and consensus ranking criteria
- Control or redocking validation
- Manual pose-inspection software and version
- Date, operator, and project archive location

## End of Document

SIDock AD4 0.7.1  
Streamlined Interface for Docking with AutoDock4  
Developed by Dr Syahrul Imran
