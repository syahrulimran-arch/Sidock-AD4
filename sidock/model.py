from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GridBox:
    center_x: float = 0.0
    center_y: float = 0.0
    center_z: float = 0.0
    npts_x: int = 60
    npts_y: int = 60
    npts_z: int = 60
    spacing: float = 0.375

    def validate(self) -> None:
        if any(n < 2 or n > 126 for n in (self.npts_x, self.npts_y, self.npts_z)):
            raise ValueError("Grid points must be between 2 and 126 on every axis.")
        if any(n % 2 for n in (self.npts_x, self.npts_y, self.npts_z)):
            raise ValueError("AutoGrid point counts must be even.")
        if not 0.05 <= self.spacing <= 1.0:
            raise ValueError("Grid spacing must be between 0.05 and 1.0 Å.")


@dataclass
class DockingParameters:
    ga_runs: int = 10
    ga_num_evals: int = 2_500_000
    ga_pop_size: int = 150
    ga_num_generations: int = 27_000
    rmstol: float = 2.0
    parallel_jobs: int = 1
    engine: str = "autodock4"
    gpu_device: int = 1


@dataclass
class ToolPaths:
    autogrid: str = ""
    autodock: str = ""
    autodock_gpu: str = ""
    prepare_ligand: str = "Bundled Meeko (automatic)"
    prepare_receptor: str = "Bundled Meeko (automatic)"
    openbabel: str = "obabel"
    adt_python: str = ""
    adt_prepare_receptor: str = ""


@dataclass
class Project:
    root: str
    receptor_source: str = ""
    receptor_pdbqt: str = ""
    ligand_sources: list[str] = field(default_factory=list)
    prepared_ligands: list[str] = field(default_factory=list)
    grid: GridBox = field(default_factory=GridBox)
    docking: DockingParameters = field(default_factory=DockingParameters)
    tools: ToolPaths = field(default_factory=ToolPaths)
    remove_waters: bool = True
    remove_hetero: bool = False
    receptor_chain: str = ""
    keep_hetero_resnames: str = ""
    box_reference_resname: str = ""
    receptor_input_mode: str = "meeko"
    openbabel_add_hydrogens: bool = True
    ligand_generate_3d: bool = True
    ligand_optimize: bool = True
    ligand_forcefield: str = "MMFF94"
    ligand_max_iters: int = 500
    ligand_num_conformers: int = 10
    analysis_top_n: int = 20

    def __post_init__(self) -> None:
        # A relative project name such as "testing" used to make tool paths
        # depend on the application's working directory. Persist one absolute
        # root so every later preparation and docking stage is deterministic.
        self.root = str(Path(self.root).expanduser().resolve())

    @property
    def path(self) -> Path:
        return Path(self.root)

    def ensure_layout(self) -> None:
        for relative in (
            "receptor", "ligands/source", "ligands/prepared", "grid",
            "docking/dpf", "docking/dlg", "logs", "results",
            "analysis", "analysis/poses", "analysis/complexes",
            "docking/gpu/dlg", "docking/gpu/work", "results/gpu", "analysis/gpu",
        ):
            (self.path / relative).mkdir(parents=True, exist_ok=True)

    def save(self) -> None:
        self.ensure_layout()
        (self.path / "project.json").write_text(
            json.dumps(asdict(self), indent=2), encoding="utf-8"
        )

    @classmethod
    def load(cls, root: str | Path) -> "Project":
        root = Path(root).expanduser().resolve()
        data: dict[str, Any] = json.loads((root / "project.json").read_text(encoding="utf-8"))
        data["root"] = str(root)
        data["grid"] = GridBox(**data.get("grid", {}))
        data["docking"] = DockingParameters(**data.get("docking", {}))
        data["tools"] = ToolPaths(**data.get("tools", {}))
        project = cls(**data)
        project.ensure_layout()
        return project
