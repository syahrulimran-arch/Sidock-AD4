from __future__ import annotations

import shutil
import threading
from dataclasses import asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from .core import (
    DockingResult, clean_receptor_pdb, command_failure_detail, copy_grid_inputs, parse_dlg, pdbqt_atom_types,
    prepare_ligand, prepare_receptor, prepare_receptor_autodocktools,
    prepare_receptor_openbabel, resolve_executable,
    run_command, split_and_normalize_ligands, validate_ligand_geometry,
    write_dpf, write_gpf, write_results,
)
from .model import Project
from .analysis import analyze_docking_results, parse_dlg_poses
from .gpu import analysis_directory, dlg_directory, gpu_command, is_gpu, results_directory


class WorkflowWorker(QObject):
    message = Signal(str)
    progress = Signal(int, int)
    ligand_status = Signal(str, str, str)
    finished = Signal(bool, str)

    def __init__(self, project: Project, action: str, failed_only: bool = False):
        super().__init__()
        self.project = project
        self.action = action
        self.failed_only = failed_only
        self.cancelled = threading.Event()

    def cancel(self) -> None:
        self.cancelled.set()

    def is_cancelled(self) -> bool:
        return self.cancelled.is_set()

    @Slot()
    def run(self) -> None:
        try:
            if self.action == "prepare_receptor":
                self._prepare_receptor()
            elif self.action == "prepare_ligands":
                self._prepare_ligands()
            elif self.action == "screen":
                self._screen()
            elif self.action == "analyze":
                self._analyze()
            else:
                raise ValueError(f"Unknown action: {self.action}")
        except Exception as exc:
            self.finished.emit(False, str(exc))

    def _prepare_receptor(self) -> None:
        source = Path(self.project.receptor_source)
        if not source.exists():
            raise FileNotFoundError("Select an existing receptor PDB or PDBQT file.")
        self.project.grid.validate()
        pdbqt = self.project.path / "receptor" / "receptor.pdbqt"
        log_path = self.project.path / "logs" / "prepare_receptor.log"
        mode = self.project.receptor_input_mode
        if mode == "pdbqt":
            if source.suffix.lower() != ".pdbqt":
                raise ValueError("Prepared-PDBQT mode requires a .pdbqt receptor file.")
            pdbqt_atom_types(source)
            if source.resolve() != pdbqt.resolve():
                shutil.copy2(source, pdbqt)
            log_path.write_text(
                f"Accepted prepared receptor PDBQT without conversion:\n{source}\n",
                encoding="utf-8",
            )
            code = 0
            self.message.emit("Using the supplied prepared receptor PDBQT…")
        elif mode == "adt":
            if source.suffix.lower() != ".pdb":
                raise ValueError("AutoDockTools mode requires a .pdb receptor file.")
            clean = self.project.path / "receptor" / "receptor_adt_input.pdb"
            clean_receptor_pdb(
                source, clean, self.project.remove_waters, self.project.remove_hetero,
                self.project.receptor_chain, self.project.keep_hetero_resnames,
            )
            self.message.emit("Preparing receptor with AutoDockTools (MGLTools)…")
            code = prepare_receptor_autodocktools(
                self.project.tools.adt_python, self.project.tools.adt_prepare_receptor,
                clean, pdbqt, log_path, self.is_cancelled,
            )
        elif mode == "treated":
            if source.suffix.lower() != ".pdb":
                raise ValueError("Treated-PDB mode requires a .pdb receptor file.")
            self.message.emit("Converting treated PDB to rigid PDBQT with Open Babel…")
            code = prepare_receptor_openbabel(
                self.project.tools.openbabel, source, pdbqt, log_path,
                self.project.openbabel_add_hydrogens, self.is_cancelled,
            )
        else:
            clean = self.project.path / "receptor" / "receptor_clean.pdb"
            clean_receptor_pdb(
                source, clean, self.project.remove_waters, self.project.remove_hetero,
                self.project.receptor_chain, self.project.keep_hetero_resnames,
            )
            self.message.emit("Preparing receptor PDBQT with Meeko…")
            code, pdbqt = prepare_receptor(
                self.project.tools.prepare_receptor, clean,
                self.project.path / "receptor" / "receptor", self.project.grid,
                log_path, self.is_cancelled,
            )
        if code != 0 or not pdbqt.exists():
            detail = ""
            if log_path.exists():
                lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
                detail = "\n\nLast log lines:\n" + "\n".join(lines[-12:])
            raise RuntimeError(
                f"Receptor preparation failed (exit code {code}).{detail}\n\n"
                f"Full log: {log_path}"
            )
        # Do not accept a zero-exit conversion that produced an empty, plain
        # PDB, or otherwise unusable PDBQT. Previously this was detected only
        # after the user started screening.
        try:
            receptor_types = pdbqt_atom_types(pdbqt)
        except ValueError as exc:
            detail = ""
            if log_path.exists():
                lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
                detail = "\n\nLast log lines:\n" + "\n".join(lines[-12:])
            raise RuntimeError(f"Receptor PDBQT validation failed: {exc}{detail}\n\nFull log: {log_path}") from exc
        self.project.receptor_pdbqt = str(pdbqt)
        self.project.save()
        compatibility_note = ""
        if log_path.exists() and "RESULT: SINGLE-BOND COMPATIBILITY OUTPUT ACCEPTED" in log_path.read_text(
            encoding="utf-8", errors="replace"
        ):
            compatibility_note = " Compatibility mode was required for HEM/aromatic connectivity; review the preparation log."
        self.finished.emit(
            True,
            f"Receptor prepared: {pdbqt.name} ({len(receptor_types)} AutoDock atom types).{compatibility_note}",
        )

    def _prepare_ligands(self) -> None:
        sources = [Path(p) for p in self.project.ligand_sources]
        if not sources:
            raise ValueError("Add at least one SDF or MOL2 ligand file.")
        normalized_dir = self.project.path / "ligands" / "source"
        self.message.emit("Reading molecules and generating missing 3D coordinates…")
        normalized, errors = split_and_normalize_ligands(
            sources, normalized_dir, self.project.ligand_generate_3d,
            self.project.ligand_optimize, self.project.ligand_forcefield,
            self.project.ligand_max_iters, self.project.ligand_num_conformers,
            lambda ligand, detail: self.ligand_status.emit(ligand, "optimizing", detail),
        )
        for error in errors:
            self.ligand_status.emit("Input", "failed", error)
        prepared: list[str] = []
        total = len(normalized)
        for index, source in enumerate(normalized, start=1):
            if self.is_cancelled():
                self.finished.emit(False, "Ligand preparation cancelled.")
                return
            destination = self.project.path / "ligands" / "prepared" / f"{source.stem}.pdbqt"
            try:
                audit = validate_ligand_geometry(source, self.project.ligand_optimize)
                self.ligand_status.emit(source.stem, "preparing", f"{audit}; preparing PDBQT with Meeko")
                code = prepare_ligand(
                    self.project.tools.prepare_ligand, source, destination,
                    self.project.path / "logs" / f"prepare_{source.stem}.log", self.is_cancelled,
                )
            except Exception as exc:
                self.ligand_status.emit(source.stem, "failed", f"Geometry audit failed: {exc}")
                self.progress.emit(index, total)
                continue
            if code == 0 and destination.exists():
                try:
                    pdbqt_atom_types(destination)
                    prepared.append(str(destination))
                    self.ligand_status.emit(source.stem, "prepared", audit)
                except Exception as exc:
                    self.ligand_status.emit(source.stem, "failed", str(exc))
            else:
                self.ligand_status.emit(source.stem, "failed", f"Meeko exit code {code}")
            self.progress.emit(index, total)
        self.project.prepared_ligands = prepared
        self.project.save()
        self.finished.emit(bool(prepared), f"Prepared {len(prepared)} of {total} ligands.")

    def _screen(self) -> None:
        receptor = Path(self.project.receptor_pdbqt)
        ligands = [Path(p) for p in self.project.prepared_ligands if Path(p).exists()]
        if not receptor.exists():
            raise FileNotFoundError("Prepare the receptor before screening.")
        if not ligands:
            raise ValueError("Prepare at least one ligand before screening.")
        gpu = is_gpu(self.project)
        docking_exe = resolve_executable(
            self.project.tools.autodock_gpu if gpu else self.project.tools.autodock,
            "AutoDock-GPU" if gpu else "AutoDock4",
        )
        grid_dir = self.project.path / "grid"
        receptor_grid, ligand_grid = copy_grid_inputs(receptor, ligands, grid_dir)
        all_types = sorted({t for ligand in ligand_grid for t in pdbqt_atom_types(ligand)})
        gpf = grid_dir / f"{receptor_grid.stem}.gpf"
        write_gpf(receptor_grid, all_types, self.project.grid, gpf)
        self.message.emit(f"Running AutoGrid for {len(all_types)} ligand atom types…")
        glg = grid_dir / f"{receptor_grid.stem}.glg"
        code = run_command(
            [resolve_executable(self.project.tools.autogrid, "AutoGrid4"), "-p", gpf.name, "-l", glg.name],
            grid_dir, self.project.path / "logs" / "autogrid.log", self.is_cancelled,
        )
        if code != 0:
            raise RuntimeError(f"AutoGrid failed (exit code {code}). See logs/autogrid.log.")

        dpf_dir = self.project.path / "docking" / "dpf"
        dlg_dir = dlg_directory(self.project)
        work_dir = self.project.path / "docking" / ("gpu/work" if gpu else "work")
        work_dir.mkdir(parents=True, exist_ok=True)
        dlg_dir.mkdir(parents=True, exist_ok=True)
        map_files = list(grid_dir.glob(f"{receptor_grid.stem}*.map*")) + [grid_dir / f"{receptor_grid.stem}.maps.fld"]
        for map_file in map_files:
            if map_file.exists():
                shutil.copy2(map_file, work_dir / map_file.name)

        fld = work_dir / f"{receptor_grid.stem}.maps.fld"
        if not fld.is_file():
            raise FileNotFoundError(f"AutoGrid did not produce the required map descriptor: {fld}")
        tasks: list[tuple[Path, Path | None, Path]] = []
        for ligand in ligands:
            dlg = dlg_dir / f"{ligand.stem}.dlg"
            if self.failed_only and dlg.exists() and self._read_dlg(dlg, gpu).best_energy is not None:
                continue
            ligand_work = work_dir / ligand.name
            shutil.copy2(ligand, ligand_work)
            dpf = None
            if not gpu:
                dpf = dpf_dir / f"{ligand.stem}.dpf"
                write_dpf(receptor_grid.stem, ligand_work, pdbqt_atom_types(ligand_work), self.project.docking, dpf)
            tasks.append((ligand_work, dpf, dlg))

        def dock(task: tuple[Path, Path | None, Path]) -> DockingResult:
            ligand, dpf, dlg = task
            if self.is_cancelled():
                return DockingResult(ligand.stem, None, None, "cancelled", str(dlg), "Cancelled")
            # A failed rerun must never be reported as the previous run's success.
            dlg.unlink(missing_ok=True)
            if gpu:
                args = gpu_command(docking_exe, fld, ligand, dlg.with_suffix(""), self.project.docking)
            else:
                assert dpf is not None
                local_dpf = work_dir / dpf.name
                shutil.copy2(dpf, local_dpf)
                args = [docking_exe, "-p", local_dpf.name, "-l", str(dlg.resolve())]
            self.ligand_status.emit(ligand.stem, "running", "AutoDock-GPU running" if gpu else "AutoDock4 running")
            log_path = self.project.path / "logs" / f"{'autodock_gpu' if gpu else 'autodock'}_{ligand.stem}.log"
            code = run_command(
                args, work_dir, log_path, self.is_cancelled,
            )
            result = self._read_dlg(dlg, gpu)
            if code != 0:
                result.best_energy = None
                result.status = "cancelled" if code == 130 else "failed"
                result.error = command_failure_detail(
                    log_path, code, "AutoDock-GPU" if gpu else "AutoDock4"
                )
            self.ligand_status.emit(ligand.stem, result.status, result.error or f"{result.best_energy:.2f} kcal/mol")
            return result

        completed: list[DockingResult] = []
        total = len(tasks)
        # Multiple simultaneous processes on one GPU compete for the same memory.
        with ThreadPoolExecutor(max_workers=1 if gpu else max(1, self.project.docking.parallel_jobs)) as pool:
            futures = [pool.submit(dock, task) for task in tasks]
            for index, future in enumerate(as_completed(futures), start=1):
                completed.append(future.result())
                self.progress.emit(index, total)

        # Always rebuild results from all DLG files, including successful earlier runs.
        results_by_ligand = {
            dlg.stem: self._read_dlg(dlg, gpu) for dlg in sorted(dlg_dir.glob("*.dlg"))
        }
        results_by_ligand.update({result.ligand: result for result in completed})
        results = list(results_by_ligand.values())
        write_results(results, results_directory(self.project) / "results.csv")
        self.project.save()
        if self.is_cancelled():
            self.finished.emit(False, "Screening cancelled. Completed results were preserved.")
        else:
            successful = sum(r.best_energy is not None for r in results)
            self.message.emit("Generating post-docking analysis…")
            try:
                analysis = self._run_analysis()
                message = (
                    f"Screening complete: {successful}/{len(results)} ligands ranked. "
                    f"Analysis report created with {analysis['poses']} best poses."
                )
            except Exception as exc:
                message = (
                    f"Screening complete: {successful}/{len(results)} ligands ranked. "
                    f"Automatic analysis could not be completed: {exc}"
                )
            if successful:
                self.finished.emit(True, message)
            else:
                first_error = next((r.error for r in results if r.error), "No usable DLG file was generated.")
                self.finished.emit(False, f"{message}\n\nFirst failure: {first_error}")

    def _run_analysis(self) -> dict[str, object]:
        return analyze_docking_results(
            Path(self.project.receptor_pdbqt),
            dlg_directory(self.project),
            analysis_directory(self.project),
            self.project.analysis_top_n,
            lambda done, total: self.progress.emit(done, total),
            engine=self.project.docking.engine,
            ligand_sdf_dir=self.project.path / "ligands" / "source",
            grid_metadata=asdict(self.project.grid),
            run_plip=self.project.analysis_use_plip,
        )

    @staticmethod
    def _read_dlg(path: Path, gpu: bool) -> DockingResult:
        result = parse_dlg(path, path.stem)
        if gpu and result.best_energy is not None:
            if "Unsuccessful Completion" in path.read_text(encoding="utf-8", errors="replace"):
                result.best_energy = None
                result.status = "failed"
                result.error = "GPU DLG reports unsuccessful completion"
            elif not parse_dlg_poses(path):
                result.best_energy = None
                result.status = "failed"
                result.error = "GPU DLG has no readable docked poses; inspect the GPU log and DLG"
            else:
                result.status = "complete"
        return result

    def _analyze(self) -> None:
        self.message.emit("Analyzing existing AutoDock results…")
        analysis = self._run_analysis()
        self.project.save()
        self.finished.emit(
            True,
            f"Analysis complete: {analysis['successful']}/{analysis['total']} ligands ranked, "
            f"{analysis['poses']} best poses extracted, {analysis['plip_completed']} PLIP profiles completed. "
            f"Report: {analysis['report']}",
        )
