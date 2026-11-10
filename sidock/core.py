from __future__ import annotations

import csv
import contextlib
from importlib import import_module
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
import sysconfig
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .model import DockingParameters, GridBox


SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]+")
ENERGY_RE = re.compile(
    r"Estimated Free Energy of Binding\s*=\s*([-+]?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
RUN_RE = re.compile(r"Run\s*=\s*(\d+)", re.IGNORECASE)
BUNDLED_OPENBABEL = "Bundled Open Babel"
BUNDLED_MEEKO = "Bundled Meeko (automatic)"
LEGACY_MEEKO_WRAPPERS = {
    "mk_prepare_ligand",
    "mk_prepare_ligand.exe",
    "mk_prepare_ligand.py",
    "mk_prepare_receptor",
    "mk_prepare_receptor.exe",
    "mk_prepare_receptor.py",
}
_DLL_DIRECTORY_HANDLES: list[object] = []
_REGISTERED_DLL_DIRECTORIES: set[str] = set()


def is_frozen() -> bool:
    """Return True when SIDock is running from a PyInstaller build."""
    return bool(getattr(sys, "frozen", False))


def bundled_resource_dir() -> Path:
    """Locate files collected by PyInstaller without affecting source runs."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def bundled_openbabel_path() -> Path | None:
    candidate = bundled_resource_dir() / "tools" / "openbabel" / "obabel.exe"
    return candidate if candidate.is_file() else None


def bundled_autodock_gpu_runtime_path() -> Path | None:
    """Locate the LLVM OpenMP runtime shipped for external AutoDock-GPU.

    Frozen builds collect the DLL below ``tools/autodock-gpu-runtime``. Source
    builds use the checked-in copy below ``packaging/runtime``. Keeping this
    runtime inside SIDock avoids modifying System32 or the user's separate
    AutoDock installation.
    """
    resource_dir = bundled_resource_dir()
    candidates = (
        resource_dir / "tools" / "autodock-gpu-runtime" / "libomp140.x86_64.dll",
        resource_dir / "packaging" / "runtime" / "libomp140.x86_64.dll",
    )
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def is_automatic_meeko_command(command: str) -> bool:
    """Recognize current and legacy values that mean bundled Meeko.

    Projects created by SIDock or its predecessor can contain
    ``Auto (installed Meeko)`` or even the path to SIDock.exe or DockFlow.exe
    after the frozen executable was mistaken for Python.
    Treat those values as internal Meeko so opening an old project cannot
    relaunch the GUI.
    """
    value = command.strip().strip('"')
    lowered = value.lower()
    if not value or lowered.startswith("auto") or lowered.startswith("bundled meeko"):
        return True
    # Early source releases stored these pip wrapper names in QSettings. They
    # are not separate files in the installed application; the equivalent
    # Meeko modules are bundled and must be called internally.
    if lowered in LEGACY_MEEKO_WRAPPERS:
        return True
    if is_frozen():
        try:
            if Path(value).resolve() == Path(sys.executable).resolve():
                return True
        except (OSError, ValueError):
            pass
        if Path(value).name.lower() in {"sidock.exe", "dockflow.exe"}:
            return True
    return False


def normalize_meeko_command(command: str) -> str:
    """Return the stable display/persistence value for automatic Meeko."""
    return BUNDLED_MEEKO if is_automatic_meeko_command(command) else command.strip()


def external_tool_environment() -> dict[str, str]:
    """Supply bundled runtime locations to external command-line tools."""
    environment = os.environ.copy()
    resource_dir = bundled_resource_dir()
    root = resource_dir / "tools" / "openbabel"
    data_dir = bundled_openbabel_data_path(root)
    # Open Babel's MSVC/Conda Windows build installs .obf modules beside the
    # executable and core DLL. Retaining that layout is required for the
    # Windows loader to initialize the modules reliably.
    plugin_dir = root
    if data_dir:
        environment["BABEL_DATADIR"] = str(data_dir) + os.sep
    if plugin_dir.is_dir():
        # Open Babel's Windows plugin loader concatenates this directory with
        # its *.obf search pattern and requires the final path separator.
        environment["BABEL_LIBDIR"] = str(plugin_dir) + os.sep
    path_entries: list[str] = []
    gpu_runtime = bundled_autodock_gpu_runtime_path()
    if gpu_runtime:
        # AutoDock-GPU Windows builds linked with Visual Studio's LLVM OpenMP
        # runtime import libomp140.x86_64.dll. Child processes receive this
        # private runtime directory through PATH, so no administrator action
        # or global DLL installation is needed.
        path_entries.append(str(gpu_runtime.parent))
    if is_frozen():
        # PyInstaller collects DLL dependencies at the resource root. Child
        # processes do not consistently inherit the bootloader's DLL search
        # configuration, so make that location explicit for obabel.exe.
        path_entries.append(str(resource_dir))
    if path_entries:
        environment["PATH"] = os.pathsep.join(path_entries + [environment.get("PATH", "")])
    return environment


def bundled_openbabel_data_path(root: Path | None = None) -> Path | None:
    """Return the directory containing Open Babel's chemistry databases.

    Releases already installed in the field may contain either a flat data
    directory or an extra version directory.  Resolve the marker itself so a
    harmless packaging-layout change cannot silently break receptor parsing.
    """
    root = root or (bundled_resource_dir() / "tools" / "openbabel")
    direct = root / "data" / "space-groups.txt"
    if direct.is_file():
        return direct.parent
    data_root = root / "data"
    if data_root.is_dir():
        matches = sorted(data_root.rglob("space-groups.txt"))
        if matches:
            return matches[0].parent
    return None


def configure_bundled_runtime() -> None:
    """Configure bundled tools for both this process and child processes.

    Updating PATH is sufficient for a new ``obabel.exe`` child, but modern
    Windows/Python DLL loading does not reliably consult a PATH changed after
    the frozen process started. Register the Open Babel and PyInstaller DLL
    directories explicitly before PLIP imports the Python Open Babel binding.
    The returned handles must stay alive for the lifetime of the application.
    """
    os.environ.update(external_tool_environment())
    add_directory = getattr(os, "add_dll_directory", None)
    if not is_frozen() or not callable(add_directory):
        return
    resource_dir = bundled_resource_dir()
    for directory in (resource_dir / "tools" / "openbabel", resource_dir):
        key = str(directory.resolve())
        if directory.is_dir() and key not in _REGISTERED_DLL_DIRECTORIES:
            _DLL_DIRECTORY_HANDLES.append(add_directory(key))
            _REGISTERED_DLL_DIRECTORIES.add(key)


def safe_stem(value: str, fallback: str = "ligand") -> str:
    cleaned = SAFE_NAME.sub("_", value.strip()).strip("._")
    return cleaned[:80] or fallback


def unique_path(folder: Path, stem: str, suffix: str) -> Path:
    candidate = folder / f"{stem}{suffix}"
    index = 2
    while candidate.exists():
        candidate = folder / f"{stem}_{index}{suffix}"
        index += 1
    return candidate


def clean_receptor_pdb(
    source: Path,
    destination: Path,
    remove_waters: bool,
    remove_hetero: bool,
    chain: str = "",
    keep_hetero_resnames: str = "",
) -> None:
    waters = {"HOH", "WAT", "H2O", "DOD"}
    chain = chain.strip()
    keep_hetero = {
        value.strip().upper()
        for value in re.split(r"[,;\s]+", keep_hetero_resnames)
        if value.strip()
    }
    lines: list[str] = []
    for line in source.read_text(encoding="utf-8", errors="replace").splitlines(True):
        record = line[:6].strip()
        residue = line[17:20].strip().upper() if len(line) >= 20 else ""
        atom_chain = line[21].strip() if len(line) > 21 else ""
        if record in {"ATOM", "HETATM", "ANISOU", "TER"} and chain and atom_chain != chain:
            continue
        if remove_waters and record in {"ATOM", "HETATM"} and residue in waters:
            continue
        if remove_hetero and record == "HETATM" and residue not in keep_hetero:
            continue
        if record == "LINK" and chain:
            link_chains = {
                line[21].strip() if len(line) > 21 else "",
                line[51].strip() if len(line) > 51 else "",
            }
            if any(value and value != chain for value in link_chains):
                continue
        # CONECT records are intentionally omitted after atom filtering because
        # they can reference deleted chains/ligands. Meeko rebuilds chemistry
        # from residue templates and LINK records.
        if record in {"ATOM", "HETATM", "ANISOU", "TER", "MODEL", "ENDMDL", "END", "LINK"}:
            lines.append(line)
    if not any(line.startswith(("ATOM  ", "HETATM")) for line in lines):
        raise ValueError("No receptor atoms remain after cleanup.")
    destination.write_text("".join(lines), encoding="utf-8")


def command_parts(command: str, meeko_module: str | None = None) -> list[str]:
    command = command.strip().strip('"')
    automatic = is_automatic_meeko_command(command) if meeko_module else not command
    path = Path(command)
    if path.suffix.lower() == ".py" and path.exists():
        return [sys.executable, str(path)]
    if path.exists() and path.is_file():
        return [str(path)]
    if not automatic:
        resolved = shutil.which(command)
        if resolved:
            return [resolved]
        # pip/conda place Python command wrappers here on Windows, even when the
        # environment's Scripts folder was not added to PATH by the launcher.
        scripts_dir = Path(sysconfig.get_path("scripts"))
        base = path.name
        candidates = [base]
        if not Path(base).suffix:
            candidates.extend([f"{base}.exe", f"{base}.py", f"{base}.bat"])
        for candidate in candidates:
            installed = scripts_dir / candidate
            if installed.exists():
                return [sys.executable, str(installed)] if installed.suffix.lower() == ".py" else [str(installed)]
    if meeko_module:
        if automatic:
            raise RuntimeError(
                "Automatic Meeko must run inside SIDock; it cannot be converted "
                "to an external command."
            )
        raise FileNotFoundError(
            f"Cannot find Meeko command '{command}'. Use {BUNDLED_MEEKO}, or "
            "select the full path to a Meeko script or executable."
        )
    if automatic:
        raise FileNotFoundError("No automatic command is available for this tool.")
    raise FileNotFoundError(
        f"Cannot find '{command}'. Select its full path on the Project tab."
    )


def resolve_executable(command: str, label: str) -> str:
    """Resolve an AutoDock executable and return a user-readable error."""
    command = command.strip().strip('"')
    if command.lower() in {"obabel", "obabel.exe", BUNDLED_OPENBABEL.lower()}:
        bundled = bundled_openbabel_path()
        if bundled:
            return str(bundled)
    if not command:
        raise FileNotFoundError(f"{label} has not been selected on the Project tab.")
    path = Path(command)
    if path.exists() and path.is_file():
        return str(path)
    resolved = shutil.which(command)
    if resolved:
        return resolved
    raise FileNotFoundError(
        f"Cannot find {label}: '{command}'. Select the full .exe path on the Project tab."
    )


def check_tool_setup(
    autogrid: str, autodock: str, prepare_ligand_cmd: str,
    prepare_receptor_cmd: str, openbabel: str = "obabel",
    autodock_gpu: str = "", engine: str = "autodock4",
) -> list[str]:
    messages: list[str] = []
    engine_tool = (autodock_gpu, "AutoDock-GPU") if engine == "autodock_gpu" else (autodock, "AutoDock4")
    for value, label in ((autogrid, "AutoGrid4"), engine_tool):
        try:
            executable = resolve_executable(value, label)
            suffix = ""
            if engine == "autodock_gpu" and label == "AutoDock-GPU":
                creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                probe = subprocess.run(
                    [executable, "--help"], capture_output=True, text=True, timeout=20,
                    creationflags=creationflags, env=external_tool_environment(),
                )
                fatal_code = (probe.returncode & 0xFFFFFFFF) in {
                    0xC0000005, 0xC000001D, 0xC000007B,
                    0xC0000135, 0xC0000142, 0xC0000409,
                }
                if fatal_code or (probe.returncode != 0 and not (probe.stdout or probe.stderr).strip()):
                    raise RuntimeError(
                        "executable could not start: exit code "
                        + format_process_exit(probe.returncode)
                    )
                suffix = " (launch verified; GPU/device checked during docking)"
            messages.append(f"OK: {label} -> {executable}{suffix}")
        except subprocess.TimeoutExpired:
            messages.append(f"MISSING: {label} launch check timed out after 20 seconds")
        except Exception as exc:
            messages.append(f"MISSING: {exc}")
    try:
        executable = resolve_executable(openbabel, "Open Babel")
        verify_openbabel_formats(executable)
        messages.append(f"OK: Open Babel -> {executable} (PDB/PDBQT formats verified)")
    except Exception as exc:
        messages.append(f"MISSING: {exc} (needed only for treated PDB input)")
    for value, label, module in (
        (prepare_ligand_cmd, "Meeko ligand preparation", "meeko.cli.mk_prepare_ligand"),
        (prepare_receptor_cmd, "Meeko receptor preparation", "meeko.cli.mk_prepare_receptor"),
    ):
        try:
            automatic = is_automatic_meeko_command(value)
            if automatic:
                imported = import_module(module)
                if not callable(getattr(imported, "main", None)):
                    raise RuntimeError(f"{module}.main is unavailable")
                source = "bundled Meeko" if is_frozen() else "installed Meeko"
                messages.append(f"OK: {label} -> {source}")
                continue
            parts = command_parts(value, module)
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            probe = subprocess.run(
                parts + ["--help"], capture_output=True, text=True, timeout=20,
                creationflags=creationflags, env=external_tool_environment(),
            )
            if probe.returncode != 0:
                detail = (probe.stderr or probe.stdout or "unknown import failure").strip().splitlines()[-1]
                raise RuntimeError(detail)
            messages.append(f"OK: {label} -> {' '.join(parts[:2])}")
        except Exception as exc:
            messages.append(f"MISSING: {label}: {exc}")
    return messages


def verify_openbabel_formats(executable: str) -> None:
    """Require the two format plugins used by treated-receptor conversion."""
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    probe = subprocess.run(
        [executable, "-L", "formats"], capture_output=True, text=True, timeout=20,
        creationflags=creationflags, env=external_tool_environment(),
    )
    output = "\n".join(part for part in (probe.stdout, probe.stderr) if part)
    formats = {
        match.group(1).lower()
        for match in re.finditer(r"(?m)^\s*([A-Za-z0-9_+-]+)\s+--", output)
    }
    missing = sorted({"pdb", "pdbqt"} - formats)
    if probe.returncode != 0 or missing:
        detail = f"missing format plugins: {', '.join(missing)}" if missing else f"exit code {probe.returncode}"
        raise RuntimeError(
            f"Open Babel cannot load the required PDB/PDBQT plugins ({detail}). "
            "Reinstall the current SIDock package."
        )


def run_command(
    args: list[str], cwd: Path, log_path: Path, cancel_check: Callable[[], bool] | None = None
) -> int:
    cwd = cwd.resolve()
    log_path = log_path.resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        log.write("COMMAND: " + subprocess.list2cmdline(args) + "\n\n")
        log.flush()
        try:
            process = subprocess.Popen(
                args, cwd=str(cwd), stdout=log, stderr=subprocess.STDOUT,
                text=True, creationflags=creationflags,
                env=external_tool_environment(),
            )
        except FileNotFoundError as exc:
            log.write(f"LAUNCH ERROR: {exc}\n")
            raise FileNotFoundError(
                f"Windows cannot find the program '{args[0]}'. Check its path on the Project tab."
            ) from exc
        except OSError as exc:
            log.write(f"LAUNCH ERROR: {exc}\n")
            detail = f" (Windows error {exc.winerror})" if getattr(exc, "winerror", None) else ""
            raise RuntimeError(
                f"Windows could not start '{args[0]}'{detail}: {exc}"
            ) from exc
        return_code = 0
        while process.poll() is None:
            if cancel_check and cancel_check():
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                return_code = 130
                break
            try:
                process.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                pass
        else:
            return_code = int(process.returncode or 0)
        log.write(f"\nEXIT CODE: {format_process_exit(return_code)}\n")
        log.flush()
        return return_code


def format_process_exit(code: int) -> str:
    """Make silent Windows process-loader failures understandable to users."""
    unsigned = code & 0xFFFFFFFF
    windows_errors = {
        0xC0000005: "access violation",
        0xC000001D: "illegal CPU instruction",
        0xC000007B: "invalid executable/DLL architecture (32/64-bit mismatch)",
        0xC0000135: "missing DLL dependency (commonly OpenCL.dll or a Visual C++ runtime)",
        0xC0000142: "DLL initialization failed",
        0xC0000409: "fatal runtime or stack error",
    }
    if unsigned in windows_errors:
        return f"{code} (0x{unsigned:08X}: {windows_errors[unsigned]})"
    return str(code)


def command_failure_detail(log_path: Path, code: int, tool_name: str) -> str:
    """Combine a process exit code with the useful tail of its captured output."""
    summary = f"{tool_name} exit code {format_process_exit(code)}"
    try:
        lines = [
            line.strip() for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip() and not line.startswith(("COMMAND:", "EXIT CODE:"))
        ]
    except OSError:
        lines = []
    if lines:
        summary += "; " + " | ".join(lines[-3:])
    else:
        summary += "; the executable produced no diagnostic output (likely a Windows loader/runtime failure)"
    return summary


def run_meeko(
    command: str, module_name: str, cli_args: list[str], cwd: Path,
    log_path: Path, cancel_check: Callable[[], bool] | None = None,
) -> int:
    """Run automatic Meeko internally or a manually selected command externally.

    A PyInstaller GUI executable is not a Python interpreter, so it must never
    be launched with Python's ``-c`` option. Using the same internal path for
    source and packaged runs also makes automatic preparation independent of
    fragile frozen-runtime detection.
    """
    cwd = cwd.resolve()
    log_path = log_path.resolve()
    automatic = is_automatic_meeko_command(command)
    if not automatic:
        return run_command(
            command_parts(command, module_name) + cli_args,
            cwd, log_path, cancel_check,
        )

    if cancel_check and cancel_check():
        return 130
    log_path.parent.mkdir(parents=True, exist_ok=True)
    previous_argv = sys.argv[:]
    previous_cwd = Path.cwd()
    try:
        module = import_module(module_name)
        entry_point = getattr(module, "main")
        with log_path.open("w", encoding="utf-8", errors="replace") as log:
            log.write(f"INTERNAL MODULE: {module_name}\n")
            log.write("ARGUMENTS: " + subprocess.list2cmdline(cli_args) + "\n\n")
            log.flush()
            sys.argv = [module_name, *cli_args]
            os.chdir(cwd)
            try:
                with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                    result = entry_point()
                return int(result or 0)
            except SystemExit as exc:
                return int(exc.code or 0) if isinstance(exc.code, int) else 1
            except Exception:
                import traceback
                traceback.print_exc(file=log)
                return 1
    finally:
        sys.argv = previous_argv
        os.chdir(previous_cwd)


def split_and_normalize_ligands(
    sources: Iterable[Path], output_dir: Path, generate_3d: bool = True,
    optimize: bool = True, forcefield: str = "MMFF94", max_iters: int = 500,
    num_conformers: int = 10,
    stage_callback: Callable[[str, str], None] | None = None,
) -> tuple[list[Path], list[str]]:
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem
    except ImportError as exc:
        raise RuntimeError("RDKit is required for SDF/MOL2 ligand preparation.") from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    errors: list[str] = []
    summary_rows: list[dict[str, str | int | float]] = []
    for source in sources:
        suffix = source.suffix.lower()
        if suffix == ".sdf":
            molecules = list(Chem.SDMolSupplier(str(source), removeHs=False))
        elif suffix == ".mol":
            molecules = [Chem.MolFromMolFile(str(source), removeHs=False)]
        elif suffix == ".mol2":
            molecules = [Chem.MolFromMol2File(str(source), removeHs=False)]
        else:
            errors.append(f"{source.name}: unsupported format")
            continue
        for index, molecule in enumerate(molecules, start=1):
            if molecule is None:
                errors.append(f"{source.name} molecule {index}: RDKit could not parse it")
                continue
            title = molecule.GetProp("_Name") if molecule.HasProp("_Name") else f"{source.stem}_{index}"
            stem = safe_stem(title, f"{safe_stem(source.stem)}_{index}")
            try:
                started = time.perf_counter()
                if stage_callback:
                    stage_callback(stem, "Reading molecule and adding explicit hydrogens")
                molecule = Chem.AddHs(molecule, addCoords=True)
                missing_3d = molecule.GetNumConformers() == 0 or not molecule.GetConformer().Is3D()
                if missing_3d and not generate_3d:
                    raise ValueError("molecule has no 3D coordinates and 3D generation is disabled")
                if missing_3d:
                    if stage_callback:
                        stage_callback(stem, f"Generating up to {num_conformers if optimize else 1} 3D conformers with ETKDGv3")
                    molecule.RemoveAllConformers()
                    params = AllChem.ETKDGv3()
                    params.randomSeed = 0xD0C4
                    params.useRandomCoords = True
                    params.pruneRmsThresh = 0.5
                    requested = min(100, max(1, int(num_conformers))) if optimize else 1
                    conformer_ids = list(AllChem.EmbedMultipleConfs(
                        molecule, numConfs=requested, params=params,
                    ))
                    if not conformer_ids:
                        raise ValueError("3D embedding failed")
                else:
                    conformer_ids = [conformer.GetId() for conformer in molecule.GetConformers()]
                optimization_status = "not requested"
                method = forcefield.upper()
                selected_conf_id = conformer_ids[0]
                initial_energy: float | None = None
                final_energy: float | None = None
                coordinate_rmsd: float | None = None
                converged_count = 0
                if optimize:
                    if method in {"MMFF94", "MMFF94S"}:
                        variant = "MMFF94s" if method == "MMFF94S" else "MMFF94"
                        if not AllChem.MMFFHasAllMoleculeParams(molecule):
                            raise ValueError(f"{variant} parameters are unavailable for one or more atoms; select UFF")
                        properties = AllChem.MMFFGetMoleculeProperties(
                            molecule, mmffVariant=variant,
                        )
                        if properties is None:
                            raise ValueError(f"{variant} force-field setup failed")

                        def make_forcefield(conf_id: int):
                            return AllChem.MMFFGetMoleculeForceField(
                                molecule, properties, confId=conf_id,
                            )
                    elif method == "UFF":
                        if not AllChem.UFFHasAllMoleculeParams(molecule):
                            raise ValueError("UFF parameters are unavailable for one or more atoms")

                        def make_forcefield(conf_id: int):
                            return AllChem.UFFGetMoleculeForceField(molecule, confId=conf_id)
                    else:
                        raise ValueError(f"unsupported force field: {forcefield}")

                    candidates: list[tuple[float, int, float, float]] = []
                    for position, conf_id in enumerate(conformer_ids, start=1):
                        if stage_callback:
                            stage_callback(
                                stem,
                                f"Minimizing conformer {position}/{len(conformer_ids)} with {forcefield}",
                            )
                        conformer = molecule.GetConformer(conf_id)
                        before = [
                            (point.x, point.y, point.z)
                            for point in (conformer.GetAtomPosition(atom_index)
                                          for atom_index in range(molecule.GetNumAtoms()))
                        ]
                        ff = make_forcefield(conf_id)
                        if ff is None:
                            raise ValueError(f"{forcefield} force-field setup failed")
                        ff.Initialize()
                        energy_before = float(ff.CalcEnergy())
                        result = int(ff.Minimize(
                            maxIts=max_iters, forceTol=1.0e-4, energyTol=1.0e-6,
                        ))
                        energy_after = float(ff.CalcEnergy())
                        if not math.isfinite(energy_before) or not math.isfinite(energy_after):
                            raise ValueError(f"{forcefield} produced a non-finite energy")
                        if energy_after > energy_before + 1.0e-4:
                            raise ValueError(
                                f"{forcefield} energy increased during minimization "
                                f"({energy_before:.6f} to {energy_after:.6f} kcal/mol)"
                            )
                        displacement_sq = 0.0
                        for atom_index, start in enumerate(before):
                            end = conformer.GetAtomPosition(atom_index)
                            displacement_sq += (
                                (end.x - start[0]) ** 2
                                + (end.y - start[1]) ** 2
                                + (end.z - start[2]) ** 2
                            )
                        rmsd = math.sqrt(displacement_sq / max(1, molecule.GetNumAtoms()))
                        if result == 0:
                            converged_count += 1
                            candidates.append((energy_after, conf_id, energy_before, rmsd))

                    if not candidates:
                        raise ValueError(
                            f"{forcefield} did not converge within {max_iters} iterations "
                            f"for any of {len(conformer_ids)} conformer(s); increase Maximum iterations"
                        )
                    final_energy, selected_conf_id, initial_energy, coordinate_rmsd = min(candidates)
                    optimization_status = "converged"

                # Keep exactly the audited conformer that is written to SDF and
                # subsequently passed to Meeko.
                selected_conformer = Chem.Conformer(molecule.GetConformer(selected_conf_id))
                molecule.RemoveAllConformers()
                molecule.AddConformer(selected_conformer, assignId=True)
                molecule.SetProp("_Name", stem)
                molecule.SetProp("SIDock_3D_Generated", str(missing_3d and generate_3d))
                molecule.SetProp("SIDock_Optimization_Method", forcefield if optimize else "None")
                molecule.SetProp("SIDock_Optimization_Status", optimization_status)
                molecule.SetProp("SIDock_Max_Iterations", str(max_iters))
                molecule.SetProp("SIDock_Conformers_Attempted", str(len(conformer_ids)))
                molecule.SetProp("SIDock_Conformers_Converged", str(converged_count))
                molecule.SetProp("SIDock_Selected_Conformer", str(selected_conf_id))
                if optimize and initial_energy is not None and final_energy is not None:
                    molecule.SetProp("SIDock_Initial_Energy_kcal_mol", f"{initial_energy:.6f}")
                    molecule.SetProp("SIDock_Final_Energy_kcal_mol", f"{final_energy:.6f}")
                    molecule.SetProp(
                        "SIDock_Energy_Change_kcal_mol",
                        f"{final_energy - initial_energy:.6f}",
                    )
                    molecule.SetProp("SIDock_Coordinate_RMSD_A", f"{coordinate_rmsd:.6f}")
                elapsed = time.perf_counter() - started
                molecule.SetProp("SIDock_Geometry_Preparation_Seconds", f"{elapsed:.6f}")
                destination = unique_path(output_dir, stem, ".sdf")
                if stage_callback:
                    stage_callback(stem, "Writing and verifying optimized SDF")
                writer = Chem.SDWriter(str(destination))
                writer.write(molecule)
                writer.close()
                outputs.append(destination)
                summary_rows.append({
                    "source": source.name,
                    "molecule": title,
                    "output": destination.name,
                    "generated_3d": str(missing_3d and generate_3d),
                    "method": forcefield if optimize else "None",
                    "status": optimization_status,
                    "conformers_attempted": len(conformer_ids),
                    "conformers_converged": converged_count,
                    "selected_conformer": selected_conf_id,
                    "initial_energy_kcal_mol": "" if initial_energy is None else f"{initial_energy:.6f}",
                    "final_energy_kcal_mol": "" if final_energy is None else f"{final_energy:.6f}",
                    "energy_change_kcal_mol": "" if final_energy is None or initial_energy is None else f"{final_energy - initial_energy:.6f}",
                    "coordinate_rmsd_A": "" if coordinate_rmsd is None else f"{coordinate_rmsd:.6f}",
                    "max_iterations": max_iters,
                    "elapsed_seconds": f"{elapsed:.6f}",
                    "error": "",
                })
            except Exception as exc:
                errors.append(f"{source.name} molecule {index} ({title}): {exc}")
                summary_rows.append({
                    "source": source.name,
                    "molecule": title,
                    "status": "failed",
                    "max_iterations": max_iters,
                    "elapsed_seconds": f"{time.perf_counter() - started:.6f}",
                    "error": str(exc),
                })
    summary_path = output_dir / "geometry_summary.csv"
    fieldnames = [
        "source", "molecule", "output", "generated_3d", "method", "status",
        "conformers_attempted", "conformers_converged", "selected_conformer",
        "initial_energy_kcal_mol", "final_energy_kcal_mol",
        "energy_change_kcal_mol", "coordinate_rmsd_A", "max_iterations",
        "elapsed_seconds", "error",
    ]
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)
    return outputs, errors


def validate_ligand_geometry(source_sdf: Path, optimization_required: bool) -> str:
    """Verify the exact normalized structure that will be submitted to Meeko."""
    try:
        from rdkit import Chem
    except ImportError as exc:
        raise RuntimeError("RDKit is required to verify ligand minimization.") from exc
    supplier = Chem.SDMolSupplier(str(source_sdf), removeHs=False)
    molecule = supplier[0] if supplier and len(supplier) else None
    if molecule is None:
        raise ValueError(f"RDKit could not reopen normalized ligand {source_sdf.name}")
    required = (
        "SIDock_Optimization_Method", "SIDock_Optimization_Status",
        "SIDock_Conformers_Attempted", "SIDock_Conformers_Converged",
    )
    missing = [name for name in required if not molecule.HasProp(name)]
    if missing:
        raise ValueError(f"geometry audit fields are missing: {', '.join(missing)}")
    status = molecule.GetProp("SIDock_Optimization_Status")
    method = molecule.GetProp("SIDock_Optimization_Method")
    if optimization_required:
        if status != "converged" or method == "None":
            raise ValueError("requested geometry minimization was not completed")
        for name in ("SIDock_Initial_Energy_kcal_mol", "SIDock_Final_Energy_kcal_mol"):
            if not molecule.HasProp(name):
                raise ValueError(f"geometry audit field is missing: {name}")
        initial = float(molecule.GetProp("SIDock_Initial_Energy_kcal_mol"))
        final = float(molecule.GetProp("SIDock_Final_Energy_kcal_mol"))
        if not math.isfinite(initial) or not math.isfinite(final) or final > initial + 1.0e-4:
            raise ValueError("the minimized geometry failed its energy audit")
    return ligand_geometry_summary(source_sdf)


def ligand_geometry_summary(source_sdf: Path) -> str:
    """Return the auditable optimization result stored in a normalized SDF."""
    try:
        from rdkit import Chem
    except ImportError:
        return "Ready"
    molecule = Chem.SDMolSupplier(str(source_sdf), removeHs=False)[0]
    if molecule is None or not molecule.HasProp("SIDock_Optimization_Status"):
        return "Ready"
    status = molecule.GetProp("SIDock_Optimization_Status")
    method = molecule.GetProp("SIDock_Optimization_Method")
    if status == "not requested":
        return "Ready; geometry minimization disabled"
    initial = float(molecule.GetProp("SIDock_Initial_Energy_kcal_mol"))
    final = float(molecule.GetProp("SIDock_Final_Energy_kcal_mol"))
    attempted = molecule.GetProp("SIDock_Conformers_Attempted")
    converged = molecule.GetProp("SIDock_Conformers_Converged")
    return (
        f"Ready; {method} converged; {converged}/{attempted} conformers; "
        f"energy {initial:.3f} -> {final:.3f} kcal/mol "
        f"(change {final - initial:+.3f})"
    )


def prepare_ligand(command: str, source_sdf: Path, destination: Path, log: Path, cancel_check=None) -> int:
    source_sdf = source_sdf.resolve()
    destination = destination.resolve()
    log = log.resolve()
    args = ["-i", str(source_sdf), "-o", str(destination)]
    return run_meeko(
        command, "meeko.cli.mk_prepare_ligand", args,
        destination.parent, log, cancel_check,
    )


def prepare_receptor(
    command: str, source_pdb: Path, output_basename: Path, grid: GridBox, log: Path, cancel_check=None
) -> tuple[int, Path]:
    # Meeko writes <basename>.pdbqt when -p is requested. GPF generation is handled
    # by SIDock after the complete ligand atom-type union is known.
    source_pdb = source_pdb.resolve()
    output_basename = output_basename.resolve()
    log = log.resolve()
    args = [
        "--read_pdb", str(source_pdb), "-o", str(output_basename), "-p",
        "--box_center", str(grid.center_x), str(grid.center_y), str(grid.center_z),
        "--box_size",
        str(grid.npts_x * grid.spacing), str(grid.npts_y * grid.spacing), str(grid.npts_z * grid.spacing),
    ]
    code = run_meeko(
        command, "meeko.cli.mk_prepare_receptor", args,
        output_basename.parent, log, cancel_check,
    )
    return code, output_basename.with_suffix(".pdbqt")


def prepare_receptor_openbabel(
    command: str, source_pdb: Path, destination: Path, log: Path,
    add_hydrogens: bool = True, cancel_check=None,
) -> int:
    """Convert a user-treated PDB to a single rigid receptor PDBQT."""
    source_pdb = source_pdb.resolve()
    destination = destination.resolve()
    log = log.resolve()
    executable = resolve_executable(command, "Open Babel")

    def command_for(output: Path, pdb_read_option: str = "") -> list[str]:
        # State both formats explicitly. This avoids format inference failures
        # on Windows when paths contain spaces or an output already exists.
        args = [executable, "-ipdb", str(source_pdb), "-opdbqt", "-O", str(output)]
        if pdb_read_option:
            args.append(pdb_read_option)
        if add_hydrogens:
            args.append("-h")
        args.extend(["--partialcharge", "gasteiger", "-xr", "-xc", "-xn", "-xh"])
        return args

    standard_output = destination.with_name(f"{destination.stem}_standard{destination.suffix}")
    standard_log = log.with_name(f"{log.stem}_standard{log.suffix}")
    standard_code = run_command(
        command_for(standard_output), destination.parent, standard_log, cancel_check
    )
    standard_valid = False
    if standard_code == 0 and standard_output.exists():
        try:
            pdbqt_atom_types(standard_output)
            standard_valid = True
        except ValueError:
            pass
    if standard_valid:
        shutil.copy2(standard_output, destination)
        shutil.copy2(standard_log, log)
        return 0

    # First ignore CONECT records. This is less invasive than changing bond
    # orders and fixes PDBs containing duplicated or inconsistent connectivity.
    conect_output = destination.with_name(f"{destination.stem}_ignore_conect{destination.suffix}")
    conect_log = log.with_name(f"{log.stem}_ignore_conect{log.suffix}")
    conect_code = run_command(
        command_for(conect_output, pdb_read_option="-ac"),
        destination.parent, conect_log, cancel_check,
    )
    conect_valid = False
    if conect_code == 0 and conect_output.exists():
        try:
            pdbqt_atom_types(conect_output)
            conect_valid = True
        except ValueError:
            pass
    if conect_valid:
        log.write_text(
            "STANDARD OPEN BABEL ATTEMPT\n"
            + standard_log.read_text(encoding="utf-8", errors="replace")
            + "\nCOMPATIBILITY ATTEMPT (IGNORE PDB CONECT RECORDS)\n"
            + conect_log.read_text(encoding="utf-8", errors="replace")
            + "\nRESULT: IGNORE-CONECT OUTPUT ACCEPTED\n",
            encoding="utf-8",
        )
        shutil.copy2(conect_output, destination)
        return 0

    # A retained metalloporphyrin can still fail aromatic kekulization after
    # CONECT records are ignored. As a last resort, use Open Babel's documented
    # PDB single-bond input mode rather than silently discarding the cofactor.
    compatibility_output = destination.with_name(f"{destination.stem}_compatibility{destination.suffix}")
    compatibility_log = log.with_name(f"{log.stem}_compatibility{log.suffix}")
    compatibility_code = run_command(
        command_for(compatibility_output, pdb_read_option="-as"),
        destination.parent, compatibility_log, cancel_check,
    )
    sections = [
        "STANDARD OPEN BABEL ATTEMPT\n" + standard_log.read_text(encoding="utf-8", errors="replace"),
        "\nCOMPATIBILITY ATTEMPT (IGNORE PDB CONECT RECORDS)\n"
        + conect_log.read_text(encoding="utf-8", errors="replace"),
        "\nCOMPATIBILITY ATTEMPT (PDB SINGLE-BOND INPUT MODE)\n"
        + compatibility_log.read_text(encoding="utf-8", errors="replace"),
    ]
    log.write_text("\n".join(sections), encoding="utf-8")
    if compatibility_code == 0 and compatibility_output.exists():
        try:
            pdbqt_atom_types(compatibility_output)
            shutil.copy2(compatibility_output, destination)
            with log.open("a", encoding="utf-8") as handle:
                handle.write("\nRESULT: SINGLE-BOND COMPATIBILITY OUTPUT ACCEPTED\n")
            return 0
        except ValueError:
            pass
    return compatibility_code or conect_code or standard_code or 1


def prepare_receptor_autodocktools(
    python_command: str, script_command: str, source_pdb: Path,
    destination: Path, log: Path, cancel_check=None,
) -> int:
    """Prepare an AD4 receptor with the MGLTools/AutoDockTools utility."""
    source_pdb = source_pdb.resolve()
    destination = destination.resolve()
    log = log.resolve()
    python_executable = resolve_executable(python_command, "MGLTools Python")
    script = Path(script_command.strip().strip('"')).resolve()
    if not script.exists() or not script.is_file():
        raise FileNotFoundError(
            "Cannot find AutoDockTools prepare_receptor4.py. Select it on the Project tab."
        )
    args = [
        python_executable, str(script), "-r", str(source_pdb), "-o", str(destination),
        "-A", "hydrogens", "-U", "nphs_lps_waters",
    ]
    return run_command(args, destination.parent, log, cancel_check)


def pdbqt_atom_types(path: Path) -> list[str]:
    types: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        # Some PDBQT writers use non-canonical spacing after ATOM. Testing the
        # six-column record field accepts Meeko, AutoDockTools and Open Babel.
        if re.match(r"^(?:ATOM|HETATM)(?:\s|$)", line, re.IGNORECASE):
            atom_type = line[77:79].strip() if len(line) >= 78 else ""
            if not atom_type:
                parts = line.split()
                atom_type = parts[-1] if parts else ""
            if atom_type:
                types.add(atom_type)
    if not types:
        preview = " | ".join(
            line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[:4]
        )
        detail = f" First lines: {preview}" if preview else " The file is empty."
        raise ValueError(
            f"No AutoDock atom types found in {path.name}.{detail} "
            "Return to Receptor & grid and prepare the receptor again."
        )
    return sorted(types)


def pdbqt_center(path: Path) -> tuple[float, float, float]:
    coords: list[tuple[float, float, float]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith(("ATOM  ", "HETATM")):
            try:
                coords.append((float(line[30:38]), float(line[38:46]), float(line[46:54])))
            except ValueError:
                pass
    if not coords:
        raise ValueError(f"No coordinates found in {path.name}.")
    return tuple(sum(v[i] for v in coords) / len(coords) for i in range(3))  # type: ignore[return-value]


def _box_from_coords(coords: list[tuple[float, float, float]], padding: float, spacing: float) -> GridBox:
    if not coords:
        raise ValueError("No readable atom coordinates were found for the grid reference.")
    mins = [min(v[i] for v in coords) for i in range(3)]
    maxs = [max(v[i] for v in coords) for i in range(3)]
    center = [(mins[i] + maxs[i]) / 2 for i in range(3)]
    npts = []
    for i in range(3):
        n = math.ceil((maxs[i] - mins[i] + 2 * padding) / spacing)
        if n % 2:
            n += 1
        if n > 126:
            axis = "XYZ"[i]
            raise ValueError(
                f"The reference requires {n} grid points on {axis}, above AutoGrid's 126-point limit. "
                "Select an isolated bound ligand PDB/PDBQT, not the complete protein structure, "
                "or define the grid manually."
            )
        npts.append(max(2, n))
    return GridBox(*center, *npts, spacing)


def box_from_reference(path: Path, padding: float, spacing: float = 0.375) -> GridBox:
    coords: list[tuple[float, float, float]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith(("ATOM  ", "HETATM")):
            try:
                coords.append((float(line[30:38]), float(line[38:46]), float(line[46:54])))
            except ValueError:
                continue
    return _box_from_coords(coords, padding, spacing)


def box_from_receptor_residue(
    path: Path, residue_name: str, chain: str = "", padding: float = 5.0, spacing: float = 0.375
) -> GridBox:
    residue_name = residue_name.strip().upper()
    chain = chain.strip()
    if not residue_name:
        raise ValueError("Enter the bound-ligand residue name, for example VT1.")
    coords: list[tuple[float, float, float]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("HETATM"):
            continue
        if line[17:20].strip().upper() != residue_name:
            continue
        if chain and line[21].strip() != chain:
            continue
        try:
            coords.append((float(line[30:38]), float(line[38:46]), float(line[46:54])))
        except ValueError:
            continue
    if not coords:
        where = f" in chain {chain}" if chain else ""
        raise ValueError(f"No HETATM residue named {residue_name}{where} was found in the receptor PDB.")
    return _box_from_coords(coords, padding, spacing)


def write_gpf(receptor: Path, ligand_types: Iterable[str], grid: GridBox, destination: Path) -> None:
    grid.validate()
    ligand_types = sorted(set(ligand_types))
    receptor_types = pdbqt_atom_types(receptor)
    stem = receptor.stem
    lines = [
        f"npts {grid.npts_x} {grid.npts_y} {grid.npts_z}",
        f"gridfld {stem}.maps.fld",
        f"spacing {grid.spacing:.3f}",
        f"receptor_types {' '.join(receptor_types)}",
        f"ligand_types {' '.join(ligand_types)}",
        f"receptor {receptor.name}",
        f"gridcenter {grid.center_x:.3f} {grid.center_y:.3f} {grid.center_z:.3f}",
        "smooth 0.5",
    ]
    lines.extend(f"map {stem}.{atom_type}.map" for atom_type in ligand_types)
    lines.extend([f"elecmap {stem}.e.map", f"dsolvmap {stem}.d.map", "dielectric -0.1465"])
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def torsdof(path: Path) -> int:
    match = re.search(r"^TORSDOF\s+(\d+)", path.read_text(encoding="utf-8", errors="replace"), re.MULTILINE)
    return int(match.group(1)) if match else 0


def write_dpf(
    receptor_stem: str, ligand: Path, ligand_types: Iterable[str], params: DockingParameters, destination: Path
) -> None:
    atom_types = sorted(set(ligand_types))
    cx, cy, cz = pdbqt_center(ligand)
    lines = [
        "autodock_parameter_version 4.2", "outlev 1", "intelec", "seed pid time",
        f"ligand_types {' '.join(atom_types)}", f"fld {receptor_stem}.maps.fld",
    ]
    lines.extend(f"map {receptor_stem}.{atom_type}.map" for atom_type in atom_types)
    lines.extend([
        f"elecmap {receptor_stem}.e.map", f"desolvmap {receptor_stem}.d.map",
        f"move {ligand.name}", f"about {cx:.3f} {cy:.3f} {cz:.3f}",
        "tran0 random", "quaternion0 random", "dihe0 random", f"torsdof {torsdof(ligand)}",
        f"rmstol {params.rmstol:.2f}", "extnrg 1000.0", "e0max 0.0 10000",
        f"ga_pop_size {params.ga_pop_size}", f"ga_num_evals {params.ga_num_evals}",
        f"ga_num_generations {params.ga_num_generations}", "ga_elitism 1",
        "ga_mutation_rate 0.02", "ga_crossover_rate 0.80", "ga_window_size 10",
        "ga_cauchy_alpha 0.0", "ga_cauchy_beta 1.0", "set_ga",
        "sw_max_its 300", "sw_max_succ 4", "sw_max_fail 4", "sw_rho 1.0",
        "sw_lb_rho 0.01", "ls_search_freq 0.06", "set_psw1",
        f"ga_run {params.ga_runs}", "analysis",
    ])
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


@dataclass
class DockingResult:
    ligand: str
    best_energy: float | None
    run: int | None
    status: str
    dlg: str
    error: str = ""


def parse_dlg(path: Path, ligand: str | None = None) -> DockingResult:
    if not path.exists():
        return DockingResult(ligand or path.stem, None, None, "failed", str(path), "DLG file missing")
    text = path.read_text(encoding="utf-8", errors="replace")
    energies = [(float(m.group(1)), m.start()) for m in ENERGY_RE.finditer(text)]
    if not energies:
        message = "AutoDock did not report a binding energy"
        if "Unsuccessful Completion" in text:
            message = "AutoDock reported unsuccessful completion"
        return DockingResult(ligand or path.stem, None, None, "failed", str(path), message)
    best_energy, position = min(energies, key=lambda pair: pair[0])
    before = text[max(0, position - 250):position]
    run_matches = list(RUN_RE.finditer(before))
    run = int(run_matches[-1].group(1)) if run_matches else None
    status = "complete" if "Successful Completion" in text else "complete_with_warning"
    return DockingResult(ligand or path.stem, best_energy, run, status, str(path))


def write_results(results: Iterable[DockingResult], destination: Path) -> None:
    ranked = sorted(results, key=lambda r: (r.best_energy is None, r.best_energy or 0.0, r.ligand.lower()))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["rank", "ligand", "best_energy_kcal_mol", "best_run", "status", "dlg", "error"])
        writer.writeheader()
        rank = 0
        for result in ranked:
            if result.best_energy is not None:
                rank += 1
            writer.writerow({
                "rank": rank if result.best_energy is not None else "",
                "ligand": result.ligand,
                "best_energy_kcal_mol": result.best_energy if result.best_energy is not None else "",
                "best_run": result.run or "", "status": result.status,
                "dlg": result.dlg, "error": result.error,
            })


def copy_grid_inputs(receptor: Path, ligands: Iterable[Path], grid_dir: Path) -> tuple[Path, list[Path]]:
    grid_dir.mkdir(parents=True, exist_ok=True)
    receptor_copy = grid_dir / receptor.name
    shutil.copy2(receptor, receptor_copy)
    ligand_copies = []
    for ligand in ligands:
        target = grid_dir / ligand.name
        shutil.copy2(ligand, target)
        ligand_copies.append(target)
    return receptor_copy, ligand_copies
