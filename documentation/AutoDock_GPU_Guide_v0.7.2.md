# SIDock AD4 0.7.2: AutoDock-GPU guide

## Requirements and setup

The existing AutoGrid4 installation remains required. Obtain a compatible
Windows AutoDock-GPU executable and its required CUDA or OpenCL drivers from
the [official AutoDock-GPU project](https://github.com/ccsb-scripps/AutoDock-GPU)
and [releases](https://github.com/ccsb-scripps/AutoDock-GPU/releases).
SIDock does not include the GPU program or drivers, and checking a path in
SIDock cannot prove that a GPU or its driver will work. Keep AutoDock4 installed
if you want to run CPU docking as well.

1. Open or create a SIDock project. On **Project**, select `autogrid4.exe` and
   the installed AutoDock-GPU `.exe` under **AutoDock-GPU executable (optional)**.
   Leave the bundled Meeko and Open Babel defaults in place unless your input
   workflow requires other tools.
2. On **Screen & results**, choose **AutoDock-GPU (external executable)**.
   Set **GPU device** to 1 for the first available device. AutoDock-GPU numbers
   devices starting at 1. Configure the GA runs and search limits as desired.
3. Click **Check tool setup**, then **Save tool paths**. SIDock verifies that
   the GPU executable can launch and reports recognizable Windows loader/DLL
   errors. GPU hardware, the selected device and docking inputs are verified
   only when a docking job starts.
4. Prepare the receptor and ligands as described in the SIDock user manual,
   set the grid, then click **Run virtual screening**. Start with a small test
   ligand and inspect the log and report before screening a library.

## Files and processing

AutoGrid4 creates the grid and its `.maps.fld` descriptor. SIDock passes that
descriptor and each prepared ligand `.pdbqt` to AutoDock-GPU through its native
`--ffile` and `--lfile` arguments. It writes `.dlg` output, clusters and XML;
SIDock reads the DLG to generate rankings, best poses, receptor–ligand PDB
complexes, contacts and an HTML report. A DLG with no readable docked pose is
marked failed even if it contains a binding energy. Consult the relevant GPU
log and DLG when a ligand fails.

| Engine | DLGs | Ranked CSV | Analysis report | Command logs |
| --- | --- | --- | --- | --- |
| AutoDock4 | `docking/dlg` | `results/results.csv` | `analysis/report.html` | `logs/autodock_<ligand>.log` |
| AutoDock-GPU | `docking/gpu/dlg` | `results/gpu/results.csv` | `analysis/gpu/report.html` | `logs/autodock_gpu_<ligand>.log` |

The selected engine controls **Analyze existing results**, **Retry failed
only**, and the displayed report. GPU ligands are processed one at a time
per selected device; the CPU parallel-process control applies to AutoDock4.
The GPU program uses its ADADELTA local search by default. SIDock passes your
run, evaluation, generation, population and clustering settings, and disables
GPU adaptive heuristics and autostop so the configured evaluation limits are
used. These settings do not make CPU and GPU search algorithms identical;
record which engine was used and assess scores within the appropriate protocol.

## Troubleshooting and verification

- **Check tool setup is OK but docking fails:** inspect
  the **Error/details** column and `logs/autodock_gpu_<ligand>.log` for the
  recorded exit code and driver, runtime or device errors; run the GPU vendor's
  driver check separately. The installer cannot supply these.
- **Log reports `0xC0000135`:** Windows could not load a required DLL. Update
  the GPU driver/OpenCL runtime and install the Microsoft Visual C++ x64
  redistributable required by the selected AutoDock-GPU build. SIDock 0.7.6
  supplies `libomp140.x86_64.dll` privately when it starts AutoDock-GPU, so
  that DLL should not be copied into System32 or the AutoDock directory. If the
  error persists, inspect the log because another dependency is missing. Do not
  download individual DLL files from third-party DLL sites.
- **No ranked result:** verify AutoGrid generated the `.maps.fld` and map files,
  and that `docking/gpu/dlg/<ligand>.dlg` contains docking energy and `DOCKED:`
  pose coordinates. A nonzero GPU process exit is a failure even if it left a
  partial DLG.
- **Old CPU report shown:** choose the CPU engine to view CPU results or GPU
  to view GPU results. The folders and UI views are intentionally separate.
- **Switching devices:** use device 1 first, then choose a different number if
  the upstream GPU executable enumerates multiple devices.

Before distributing, build the Windows installer with `Build-Installer.bat`
and smoke-test the packaged app on a machine with the target GPU and driver.
The source tests simulate GPU output but cannot prove execution on your GPU.

Upstream argument names, device numbering, format defaults and adaptive
search behavior: [AutoDock-GPU documentation](https://github.com/ccsb-scripps/AutoDock-GPU#readme).
