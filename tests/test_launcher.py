import importlib.util
import sys
from pathlib import Path


LAUNCHER_PATH = Path(__file__).resolve().parents[1] / "packaging" / "launcher.py"


def load_launcher():
    spec = importlib.util.spec_from_file_location("sidock_launcher_test", LAUNCHER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_legacy_meeko_command_runs_module_without_gui(monkeypatch):
    launcher = load_launcher()

    class FakeModule:
        called = False

        @classmethod
        def main(cls):
            cls.called = True
            return 0

    monkeypatch.setattr(launcher.importlib, "import_module", lambda _: FakeModule)
    monkeypatch.setattr(sys, "argv", [
        "SIDock.exe", "-c",
        "from meeko.cli.mk_prepare_ligand import main; main()",
        "-i", "ligand.sdf",
    ])
    assert launcher.run_legacy_meeko_command() == 0
    assert FakeModule.called
    assert sys.argv == ["meeko.cli.mk_prepare_ligand", "-i", "ligand.sdf"]


def test_unknown_command_is_not_treated_as_legacy_meeko(monkeypatch):
    launcher = load_launcher()
    monkeypatch.setattr(sys, "argv", ["SIDock.exe", "--unexpected"])
    assert launcher.run_legacy_meeko_command() is None
