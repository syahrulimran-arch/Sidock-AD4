import hashlib
import re
from pathlib import Path

from sidock import __version__


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTALLER_SCRIPT = PROJECT_ROOT / "packaging" / "installer" / "SIDock.iss"
SPEC_FILE = PROJECT_ROOT / "packaging" / "SIDock.spec"
GPU_RUNTIME = PROJECT_ROOT / "packaging" / "runtime" / "libomp140.x86_64.dll"


def installer_text() -> str:
    return INSTALLER_SCRIPT.read_text(encoding="utf-8")


def directive(text: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}=(.+)$", text, re.MULTILINE)
    assert match, f"Missing Inno Setup directive: {name}"
    return match.group(1).strip()


def test_installer_requires_supported_64_bit_windows():
    text = installer_text()
    assert directive(text, "MinVersion") == "10.0.17763"
    assert directive(text, "ArchitecturesAllowed") == "x64compatible"
    assert directive(text, "ArchitecturesInstallIn64BitMode") == "x64compatible"


def test_installer_release_version_matches_package():
    text = installer_text()
    assert f'#define MyAppVersion "{__version__}"' in text
    assert directive(text, "OutputBaseFilename") == f"SIDock_AD4_Setup_v{__version__}"
    assert directive(text, "VersionInfoVersion") == f"{__version__}.0"


def test_installer_uses_sidock_product_names_and_cleans_legacy_shortcuts():
    text = installer_text()
    assert '#define MyAppName "SIDock AD4"' in text
    assert '#define MyAppExeName "SIDock.exe"' in text
    assert "DockFlow AD4.lnk" in text


def test_autodock_gpu_openmp_runtime_is_packaged():
    assert GPU_RUNTIME.is_file()
    assert GPU_RUNTIME.stat().st_size > 1_000_000
    assert hashlib.sha256(GPU_RUNTIME.read_bytes()).hexdigest() == (
        "009b3aabfad6c4ccdd395b1befff744c141e51b2c124ca24c36f6d4631365cef"
    )
    assert "tools/autodock-gpu-runtime" in SPEC_FILE.read_text(encoding="utf-8")


def test_plip_runtime_is_collected_for_the_installer():
    text = SPEC_FILE.read_text(encoding="utf-8")
    assert 'collect_submodules("plip")' in text
    assert 'collect_all("plip")' in text


def test_openbabel_obf_format_plugins_are_collected():
    text = SPEC_FILE.read_text(encoding="utf-8")
    assert 'glob("*.obf")' in text
    assert "Open Babel format plugins (*.obf) were not found" in text
    assert '"tools/openbabel"' in text
    assert '"tools/openbabel/plugins"' not in text
