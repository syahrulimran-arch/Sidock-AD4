# Building the SIDock AD4 Windows installer

The build is intentionally separate from normal use. Only the person producing
a release needs to perform these steps; every end user receives one Setup EXE.

## Requirements

- 64-bit Windows 10 version 1809 (build 17763) or newer, or Windows 11
- Miniforge, Miniconda, Anaconda, or another working `conda` installation
- Internet access during the first build
- About 8 GB free disk space for the temporary build environment

## One-click build

1. Extract the SIDock source package to a normal local folder.
2. Double-click `Build-Installer.bat`.
3. Approve the Inno Setup installation if Windows Package Manager prompts for it.
4. Wait for the dependency installation, tests, freezing, and installer compilation.
5. Retrieve `dist\installer\SIDock_AD4_Setup_v0.7.10.exe`.

AutoDock-GPU is an optional external executable. SIDock now includes its
required x64 LLVM OpenMP runtime in a private application folder and supplies
that folder automatically whenever an external tool is launched. End users do
not need to install `libomp140.x86_64.dll`, copy a DLL into System32, or modify
the separate AutoDock directory. The installer still does not include the
AutoDock-GPU executable or GPU drivers. To verify GPU functionality, install a
compatible upstream Windows binary separately and run a one-ligand smoke test
on the target Windows GPU machine. See
`documentation/AutoDock_GPU_Guide_v0.7.2.md`.

The first build can take 10–30 minutes because RDKit, PySide6, Open Babel, and
their libraries are downloaded. Later builds reuse `.build\conda-env`.

The build script calls `.build\conda-env\python.exe` directly after creating
the environment. This is deliberate: it remains reliable when the SIDock
folder is located in a path containing spaces, such as `D:\Sniper game\...`.

The builder copies Conda's `Library\bin` runtime DLLs into the frozen
application before compiling Setup. It then runs a packaged-runtime self-test
covering PySide6/Shiboken, RDKit, Meeko, SciPy, Gemmi, and bundled Open Babel.
This prevents a Setup EXE from being produced when an essential DLL is absent.
The pre-freeze test suite also runs a real RDKit MMFF94 minimization and checks
that it converges, does not increase the energy, and writes the geometry audit
fields and CSV report.

## What the Setup EXE contains

- SIDock AD4 0.7.10
- Python 3.11 runtime
- PySide6 interface runtime
- RDKit, Meeko, SciPy, and Gemmi
- Open Babel command-line runtime for treated-PDB conversion
- LLVM OpenMP x64 runtime required by common AutoDock-GPU Windows builds
- Start Menu shortcut, optional Desktop shortcut, and uninstaller

The Setup EXE checks for 64-bit Windows 10 version 1809 (build 17763) or newer
before it installs any application files. Unsupported Windows versions stop at
the compatibility check instead of installing an application that cannot run.

AutoGrid4, AutoDock4, and optional MGLTools are not redistributed. Users select
their existing executables on SIDock's Project tab.

## Release checks

Before distributing the installer, test it on a clean Windows account:

1. Install without Conda on that account.
2. Open SIDock from the Start Menu.
3. Click **Check tool setup**. Bundled Meeko and Open Babel should show `OK`.
4. Select AutoGrid4 and AutoDock4 and confirm they show `OK`.
5. Prepare one small ligand and confirm that the ligand row reports initial and
   final energy plus a converged conformer count.
6. Open `ligands\source\geometry_summary.csv`, then prepare a receptor and run a
   minimal docking job.
7. Uninstall SIDock from Windows Settings.

The setup file is unsigned. Windows SmartScreen may therefore show an
"unrecognized app" warning. Code-signing the installer with an Authenticode
certificate is the normal way to remove that warning for wider distribution.

## Optional GitHub build

The included `.github/workflows/build-windows-installer.yml` can build the same
Setup EXE on a GitHub Windows runner. Push this source to a repository, open the
repository's **Actions** tab, select **Build Windows installer**, and choose
**Run workflow**. Download the completed installer from the workflow's
Artifacts section. This avoids configuring the build tools on your own PC.

## Common build failures

- **`conda was not found`**: open Miniforge Prompt, change to this folder, and
  run `Build-Installer.bat` there; or add Conda to the current user's PATH.
- **`winget was not found`**: install Inno Setup 6 manually from the official
  website and rerun the build.
- **Antivirus locks a file**: close SIDock and exclude the source folder only
  for the duration of the trusted local build.
- **Tests fail**: do not distribute the generated Setup EXE. Preserve the full
  console output for diagnosis.
