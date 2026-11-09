"""Engine integration checks; run with unittest even without pytest or Qt."""

import csv
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from sidock.gpu import analysis_directory, dlg_directory, gpu_command, results_directory
from sidock.model import DockingParameters, Project


RECEPTOR = "ATOM      1  C1  PHE A 100       4.000   0.000   0.000  1.00  0.00     0.000 C\n"
LIGAND = "ATOM      1  O1  LIG A   1       2.500   0.000   0.000  1.00  0.00    -0.200 OA\n"
DLG = (
    "DOCKED: MODEL        1\n"
    "DOCKED: USER    Run = 1\n"
    "DOCKED: USER    Estimated Free Energy of Binding = -8.00 kcal/mol\n"
    "DOCKED: ATOM      1  O1  LIG A   1       2.500   0.000   0.000  1.00  0.00    -0.200 OA\n"
    "DOCKED: ENDMDL\nSuccessful Completion\n"
)


class EngineTests(unittest.TestCase):
    def test_old_project_and_native_gpu_arguments(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Project(folder)
            p.save()
            loaded = Project.load(folder)
            self.assertEqual(loaded.docking.engine, "autodock4")
            self.assertEqual(loaded.tools.autodock_gpu, "")
            loaded.docking.engine = "autodock_gpu"
            loaded.docking.gpu_device = 2
            loaded.save()
            gpu = Project.load(folder)
            self.assertEqual(gpu.docking.gpu_device, 2)
            self.assertEqual(dlg_directory(gpu), gpu.path / "docking/gpu/dlg")
            cmd = gpu_command("gpu.exe", gpu.path / "receptor.maps.fld", gpu.path / "ligand.pdbqt", gpu.path / "ligand", gpu.docking)
            self.assertEqual(cmd[cmd.index("--devnum") + 1], "2")
            self.assertEqual(cmd[cmd.index("--heuristics") + 1], "0")
            self.assertEqual(cmd[cmd.index("--nrun") + 1], str(DockingParameters().ga_runs))
            self.assertNotIn("--import_dpf", cmd)

    def test_gpu_screen_and_report_do_not_mix_cpu_dlg(self):
        # Only Qt's worker signal API is needed; the run is simulated.
        try:
            import PySide6.QtCore  # noqa: F401
        except ImportError:
            core = types.ModuleType("PySide6.QtCore")
            core.QObject = type("QObject", (), {})
            core.Signal = lambda *args: types.SimpleNamespace(emit=lambda *items: None)
            core.Slot = lambda *args: lambda method: method
            qt = types.ModuleType("PySide6")
            qt.QtCore = core
            sys.modules["PySide6"] = qt
            sys.modules["PySide6.QtCore"] = core
        from sidock import worker

        with tempfile.TemporaryDirectory() as folder:
            p = Project(folder)
            p.ensure_layout()
            receptor = p.path / "receptor/receptor.pdbqt"
            ligand = p.path / "ligands/prepared/ligand_1.pdbqt"
            receptor.write_text(RECEPTOR)
            ligand.write_text(LIGAND)
            p.receptor_pdbqt = str(receptor)
            p.prepared_ligands = [str(ligand)]
            p.docking.engine = "autodock_gpu"
            grid_exe = p.path / "autogrid.exe"
            gpu_exe = p.path / "gpu.exe"
            grid_exe.touch(); gpu_exe.touch()
            p.tools.autogrid = str(grid_exe)
            p.tools.autodock_gpu = str(gpu_exe)
            cpu_dlg = p.path / "docking/dlg/ligand_1.dlg"
            cpu_dlg.write_text(DLG.replace("-8.00", "-20.00"))
            calls = []

            def fake_run(args, cwd, log, cancel_check=None):
                calls.append(args)
                if "--ffile" in args:
                    Path(args[args.index("--resnam") + 1] + ".dlg").write_text(DLG)
                else:
                    (cwd / "receptor.maps.fld").write_text("AutoGrid map descriptor\n")
                return 0

            with patch.object(worker, "run_command", side_effect=fake_run):
                worker.WorkflowWorker(p, "screen")._screen()

            self.assertIn("--ffile", calls[1])
            self.assertEqual(cpu_dlg.read_text().count("-20.00"), 1)
            self.assertEqual((dlg_directory(p) / "ligand_1.dlg").read_text(), DLG)
            with (results_directory(p) / "results.csv").open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(float(rows[0]["best_energy_kcal_mol"]), -8.0)
            report = (analysis_directory(p) / "report.html").read_text()
            self.assertIn("-8.000", report)
            self.assertNotIn("-20.000", report)
            self.assertTrue((analysis_directory(p) / "complexes/ligand_1_best_complex.pdb").is_file())
            # An energy line alone is not a usable GPU result: no pose means
            # no receptor complex or scientific contact interpretation.
            gpu_dlg = dlg_directory(p) / "ligand_1.dlg"
            gpu_dlg.write_text("Estimated Free Energy of Binding = -15.0\n")
            invalid = worker.WorkflowWorker._read_dlg(gpu_dlg, True)
            self.assertEqual(invalid.status, "failed")
            self.assertIsNone(invalid.best_energy)
            with patch.object(worker, "run_command", side_effect=fake_run):
                worker.WorkflowWorker(p, "screen", failed_only=True)._screen()
            self.assertEqual(gpu_dlg.read_text(), DLG)


if __name__ == "__main__":
    unittest.main()
