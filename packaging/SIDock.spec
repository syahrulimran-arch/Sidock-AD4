# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules


project_root = Path(SPECPATH).parent
conda_prefix = Path(sys.prefix)

datas = [(str(project_root / "THIRD_PARTY_NOTICES.txt"), ".")]
binaries = []
hiddenimports = collect_submodules("meeko") + collect_submodules("plip")

# AutoDock-GPU is supplied by the user, but common official Windows builds
# require Visual Studio's LLVM OpenMP runtime. Ship the verified x64 runtime in
# SIDock's private directory and add that directory to child-process PATH in
# sidock.core.external_tool_environment().
gpu_runtime = project_root / "packaging" / "runtime" / "libomp140.x86_64.dll"
if not gpu_runtime.is_file():
    raise SystemExit("AutoDock-GPU runtime libomp140.x86_64.dll was not found")
binaries.append((str(gpu_runtime), "tools/autodock-gpu-runtime"))

# Meeko reads package data and metadata at runtime. collect_all keeps its CLI
# behavior identical to the source installation.
meeko_datas, meeko_binaries, meeko_hidden = collect_all("meeko")
datas += meeko_datas
binaries += meeko_binaries
hiddenimports += meeko_hidden

# PLIP is optional at analysis time but bundled with the installer so users do
# not need a separate Python/Conda setup. Its Open Babel dependency is already
# collected below for ligand preparation.
plip_datas, plip_binaries, plip_hidden = collect_all("plip")
datas += plip_datas
binaries += plip_binaries
hiddenimports += plip_hidden

# Bundle Open Babel's CLI, format plugins, and data. PyInstaller recursively
# resolves the DLL dependencies of every executable and plugin listed here.
library_dir = conda_prefix / "Library"
obabel_candidates = [
    library_dir / "bin" / "obabel.exe",
    conda_prefix / "Scripts" / "obabel.exe",
]
obabel = next((path for path in obabel_candidates if path.is_file()), None)
if obabel is None:
    raise SystemExit("Open Babel obabel.exe was not found in the build environment")
binaries.append((str(obabel), "tools/openbabel"))

plugin_roots = [
    library_dir / "lib" / "openbabel",
    library_dir / "bin" / "openbabel",
]
for plugin_root in plugin_roots:
    if plugin_root.is_dir():
        for plugin in plugin_root.rglob("*.dll"):
            binaries.append((str(plugin), "tools/openbabel/plugins"))

data_root = library_dir / "share" / "openbabel"
if data_root.is_dir():
    version_dirs = [path for path in data_root.iterdir() if path.is_dir()]
    selected_data = max(version_dirs, default=data_root)
    datas.append((str(selected_data), "tools/openbabel/data"))

a = Analysis(
    [str(project_root / "packaging" / "launcher.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=sorted(set(hiddenimports)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tkinter"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SIDock",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SIDock",
)
