"""AutoDock-GPU command construction and engine-specific project paths."""

from pathlib import Path

from .model import DockingParameters, Project


def is_gpu(project: Project) -> bool:
    engine = project.docking.engine
    if engine not in {"autodock4", "autodock_gpu"}:
        raise ValueError(f"Unknown docking engine: {engine}")
    return engine == "autodock_gpu"


def dlg_directory(project: Project) -> Path:
    return project.path / ("docking/gpu/dlg" if is_gpu(project) else "docking/dlg")


def results_directory(project: Project) -> Path:
    return project.path / ("results/gpu" if is_gpu(project) else "results")


def analysis_directory(project: Project) -> Path:
    return project.path / ("analysis/gpu" if is_gpu(project) else "analysis")


def gpu_command(executable: str, fld: Path, ligand: Path, output_base: Path,
                params: DockingParameters) -> list[str]:
    """Use GPU native arguments; AD4 DPF import supports only a subset of DPFs.

    Explicitly disable GPU's adaptive evaluation heuristic and early stop so
    the user-entered limits are honored. Its local search remains GPU's own
    default ADADELTA method; scores need not match CPU AutoDock4 runs.
    """
    if params.gpu_device < 1:
        raise ValueError("GPU device number must start at 1.")
    return [
        executable, "--ffile", str(fld.resolve()), "--lfile", str(ligand.resolve()),
        "--resnam", str(output_base.resolve()), "--devnum", str(params.gpu_device),
        "--nrun", str(params.ga_runs), "--nev", str(params.ga_num_evals),
        "--ngen", str(params.ga_num_generations), "--psize", str(params.ga_pop_size),
        "--rmstol", str(params.rmstol), "--heuristics", "0", "--autostop", "0",
        "--dlgoutput", "1", "--clustering", "1", "--xmloutput", "1",
    ]
