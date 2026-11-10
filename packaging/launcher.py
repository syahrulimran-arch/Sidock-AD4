"""PyInstaller entry point kept outside the importable SIDock package."""

import importlib
from multiprocessing import freeze_support
import os
import sys
import tempfile
from pathlib import Path


LEGACY_MEEKO_COMMANDS = {
    "from meeko.cli.mk_prepare_ligand import main; main()": "meeko.cli.mk_prepare_ligand",
    "from meeko.cli.mk_prepare_receptor import main; main()": "meeko.cli.mk_prepare_receptor",
}


def run_legacy_meeko_command() -> int | None:
    """Handle commands produced by early 0.6.1 frozen builds without a GUI."""
    if len(sys.argv) < 3 or sys.argv[1] != "-c":
        return None
    module_name = LEGACY_MEEKO_COMMANDS.get(sys.argv[2].strip())
    if module_name is None:
        return 2
    module = importlib.import_module(module_name)
    sys.argv = [module_name, *sys.argv[3:]]
    try:
        result = module.main()
        return int(result or 0)
    except SystemExit as exc:
        return int(exc.code or 0) if isinstance(exc.code, int) else 1


def packaged_runtime_self_test() -> int:
    """Return failure before Setup compilation if a runtime is incomplete."""
    try:
        import gemmi  # noqa: F401
        import meeko  # noqa: F401
        import scipy  # noqa: F401
        from plip.structure.preparation import PDBComplex
        import shiboken6  # noqa: F401
        from PySide6 import QtCore, QtGui, QtWidgets  # noqa: F401
        from rdkit import Chem
        from meeko.cli.mk_prepare_ligand import main as ligand_main
        from meeko.cli.mk_prepare_receptor import main as receptor_main

        from sidock.app import MainWindow
        from sidock.core import (
            bundled_autodock_gpu_runtime_path,
            bundled_openbabel_path,
            split_and_normalize_ligands,
            validate_ligand_geometry,
            verify_openbabel_formats,
        )
        from sidock.model import Project
        if (
            not bundled_openbabel_path()
            or not bundled_autodock_gpu_runtime_path()
            or not callable(ligand_main)
            or not callable(receptor_main)
            or not callable(PDBComplex)
        ):
            return 1
        verify_openbabel_formats(str(bundled_openbabel_path()))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "self_test.mol"
            Chem.MolToMolFile(Chem.MolFromSmiles("CCO"), str(source))
            outputs, errors = split_and_normalize_ligands(
                [source], root / "normalized", generate_3d=True,
                optimize=True, forcefield="MMFF94", max_iters=500,
                num_conformers=3,
            )
            if errors or len(outputs) != 1 or "converged" not in validate_ligand_geometry(outputs[0], True):
                return 1

            # Catch the installed-GUI regression where Open existing loaded a
            # project but left the receptor and ligand actions disabled.
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
            app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(["SIDock-self-test"])
            project = Project(str(root / "project")); project.save()
            window = MainWindow()
            window.project_path.setText(project.root)
            window.open_project()
            gui_ok = (
                window.tabs.isTabEnabled(1)
                and window.prepare_receptor_btn.isEnabled()
                and window.prepare_ligands_btn.isEnabled()
            )
            window.close()
            app.processEvents()
            return 0 if gui_ok else 1
    except BaseException:
        return 1


if __name__ == "__main__":
    freeze_support()
    if "--self-test" in sys.argv:
        raise SystemExit(packaged_runtime_self_test())

    legacy_result = run_legacy_meeko_command()
    if legacy_result is not None:
        raise SystemExit(legacy_result)

    # A shortcut starts SIDock with no arguments. Silently opening a second
    # window for an accidental subprocess call hides the real error and can
    # multiply GUI instances, so reject all other command-line invocations.
    if len(sys.argv) != 1:
        raise SystemExit(2)

    from sidock.app import main
    main()
