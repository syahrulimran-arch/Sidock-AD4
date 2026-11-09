from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QThread, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QSpinBox, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from .core import (
    BUNDLED_MEEKO, BUNDLED_OPENBABEL, box_from_reference, box_from_receptor_residue,
    bundled_openbabel_path, check_tool_setup,
    normalize_meeko_command,
)
from .model import Project
from .gpu import analysis_directory, dlg_directory, results_directory
from .worker import WorkflowWorker


APP_STYLE = """
QMainWindow { background: #f4f7fb; }
QTabWidget::pane { border: 1px solid #d7dfeb; background: white; border-radius: 7px; }
QTabBar::tab { padding: 11px 19px; color: #4d5b70; }
QTabBar::tab:selected { color: #123d70; font-weight: 600; border-bottom: 3px solid #2f79c5; }
QGroupBox { font-weight: 600; border: 1px solid #d7dfeb; border-radius: 7px; margin-top: 12px; padding: 13px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { padding: 6px; border: 1px solid #bdc9d8; border-radius: 4px; }
QPushButton { padding: 8px 14px; border-radius: 5px; border: 1px solid #aebdce; background: #f8fafc; }
QPushButton:hover { background: #eef4fa; }
QPushButton[primary="true"] { color: white; background: #2268aa; border-color: #2268aa; font-weight: 600; }
QPushButton[primary="true"]:disabled { background: #a8b7c7; }
QTableWidget { border: 1px solid #d7dfeb; gridline-color: #e7ecf2; }
"""


def path_row(line: QLineEdit, browse) -> QWidget:
    widget = QWidget()
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(line, 1)
    button = QPushButton("Browse…")
    button.clicked.connect(browse)
    layout.addWidget(button)
    return widget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SIDock AD4 0.7.7 — Virtual Screening")
        self.resize(1100, 760)
        self.project: Project | None = None
        self.thread: QThread | None = None
        self.worker: WorkflowWorker | None = None
        self.settings = QSettings("SIDock", "SIDockAD4")
        legacy_settings = QSettings("DockFlow", "DockFlowAD4")
        for key in (
            "autogrid", "autodock", "prepare_ligand", "prepare_receptor",
            "openbabel", "adt_python", "adt_prepare_receptor",
        ):
            if not self.settings.contains(key) and legacy_settings.contains(key):
                self.settings.setValue(key, legacy_settings.value(key))
        help_menu = self.menuBar().addMenu("&Help")
        about_action = help_menu.addAction("&About SIDock AD4")
        about_action.triggered.connect(self.show_about)
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self._build_project_tab()
        self._build_receptor_tab()
        self._build_ligand_tab()
        self._build_screen_tab()
        self.statusBar().showMessage("Create or open a project to begin.")
        self._set_project_enabled(False)

    def _build_project_tab(self):
        page = QWidget(); layout = QVBoxLayout(page)
        title = QLabel("Start with a self-contained screening project")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.DemiBold)); layout.addWidget(title)
        layout.addWidget(QLabel("All generated files and logs stay inside this folder, so a screening run can be resumed or audited later."))
        project_group = QGroupBox("Project folder"); form = QFormLayout(project_group)
        self.project_path = QLineEdit()
        form.addRow("Folder", path_row(self.project_path, self.choose_project))
        buttons = QHBoxLayout(); self.new_btn = QPushButton("Create project"); self.open_btn = QPushButton("Open existing")
        self.new_btn.setProperty("primary", True); self.new_btn.clicked.connect(self.create_project); self.open_btn.clicked.connect(self.open_project)
        buttons.addWidget(self.new_btn); buttons.addWidget(self.open_btn); buttons.addStretch(); form.addRow(buttons)
        layout.addWidget(project_group)
        tools = QGroupBox("External tools"); tf = QFormLayout(tools)
        self.autogrid_path = QLineEdit(str(self.settings.value("autogrid", "")))
        self.autodock_path = QLineEdit(str(self.settings.value("autodock", "")))
        self.autodock_gpu_path = QLineEdit(str(self.settings.value("autodock_gpu", "")))
        self.prep_ligand_path = QLineEdit(normalize_meeko_command(str(self.settings.value("prepare_ligand", BUNDLED_MEEKO))))
        self.prep_receptor_path = QLineEdit(normalize_meeko_command(str(self.settings.value("prepare_receptor", BUNDLED_MEEKO))))
        openbabel_default = BUNDLED_OPENBABEL if bundled_openbabel_path() else "obabel"
        self.openbabel_path = QLineEdit(str(self.settings.value("openbabel", openbabel_default)))
        self.adt_python_path = QLineEdit(str(self.settings.value("adt_python", "")))
        self.adt_receptor_path = QLineEdit(str(self.settings.value("adt_prepare_receptor", "")))
        tf.addRow("AutoGrid4 executable", path_row(self.autogrid_path, lambda: self.choose_exe(self.autogrid_path)))
        tf.addRow("AutoDock4 executable", path_row(self.autodock_path, lambda: self.choose_exe(self.autodock_path)))
        tf.addRow("AutoDock-GPU executable (optional)", path_row(self.autodock_gpu_path, lambda: self.choose_exe(self.autodock_gpu_path)))
        tf.addRow("Meeko ligand command", path_row(self.prep_ligand_path, lambda: self.choose_command(self.prep_ligand_path)))
        tf.addRow("Meeko receptor command", path_row(self.prep_receptor_path, lambda: self.choose_command(self.prep_receptor_path)))
        tf.addRow("Open Babel executable", path_row(self.openbabel_path, lambda: self.choose_exe(self.openbabel_path)))
        tf.addRow("MGLTools Python executable", path_row(self.adt_python_path, lambda: self.choose_exe(self.adt_python_path)))
        tf.addRow("AutoDockTools prepare_receptor4.py", path_row(self.adt_receptor_path, lambda: self.choose_command(self.adt_receptor_path)))
        tool_buttons = QHBoxLayout()
        save_tools = QPushButton("Save tool paths"); save_tools.clicked.connect(self.save_tool_paths)
        check_tools = QPushButton("Check tool setup"); check_tools.clicked.connect(self.check_tools)
        tool_buttons.addWidget(save_tools); tool_buttons.addWidget(check_tools); tool_buttons.addStretch(); tf.addRow(tool_buttons)
        layout.addWidget(tools); layout.addStretch(); self.tabs.addTab(page, "1  Project")

    def _build_receptor_tab(self):
        page = QWidget(); layout = QVBoxLayout(page)
        source = QGroupBox("Receptor source"); sf = QFormLayout(source)
        self.receptor_mode = QComboBox()
        self.receptor_mode.addItem("Raw PDB — prepare and validate with Meeko", "meeko")
        self.receptor_mode.addItem("Treated PDB — AutoDockTools (recommended for HEM/metals)", "adt")
        self.receptor_mode.addItem("Treated PDB — preserve structure, convert with Open Babel", "treated")
        self.receptor_mode.addItem("Prepared PDBQT — use directly", "pdbqt")
        sf.addRow("Input mode", self.receptor_mode)
        self.receptor_path = QLineEdit(); sf.addRow("Receptor file", path_row(self.receptor_path, self.choose_receptor))
        self.ob_add_h = QCheckBox("Add hydrogens during treated-PDB conversion"); self.ob_add_h.setChecked(True)
        sf.addRow(self.ob_add_h)
        self.receptor_chain = QLineEdit(); self.receptor_chain.setPlaceholderText("Blank = all chains; e.g. B")
        sf.addRow("Protein chain", self.receptor_chain)
        self.remove_waters = QCheckBox("Remove crystallographic waters (HOH/WAT/H2O/DOD)"); self.remove_waters.setChecked(True)
        self.remove_hetero = QCheckBox("Remove HETATM except retained residue names")
        self.keep_hetero = QLineEdit(); self.keep_hetero.setPlaceholderText("Comma-separated, e.g. HEM")
        sf.addRow(self.remove_waters); sf.addRow(self.remove_hetero); sf.addRow("Retain HETATM", self.keep_hetero); layout.addWidget(source)
        grid_group = QGroupBox("Grid box"); grid = QGridLayout(grid_group)
        grid.addWidget(QLabel("Axis"), 0, 0); grid.addWidget(QLabel("Center (Å)"), 0, 1); grid.addWidget(QLabel("Points"), 0, 2)
        self.centers = []; self.npts = []
        for row, axis in enumerate("XYZ", start=1):
            center = QDoubleSpinBox(); center.setRange(-9999, 9999); center.setDecimals(3)
            points = QSpinBox(); points.setRange(2, 126); points.setSingleStep(2); points.setValue(60)
            self.centers.append(center); self.npts.append(points)
            grid.addWidget(QLabel(axis), row, 0); grid.addWidget(center, row, 1); grid.addWidget(points, row, 2)
        self.spacing = QDoubleSpinBox(); self.spacing.setRange(0.05, 1.0); self.spacing.setDecimals(3); self.spacing.setValue(0.375)
        grid.addWidget(QLabel("Spacing (Å)"), 4, 0); grid.addWidget(self.spacing, 4, 1)
        self.reference_path = QLineEdit(); ref_button = QPushButton("Box from reference ligand…"); ref_button.clicked.connect(self.reference_box)
        grid.addWidget(ref_button, 5, 0, 1, 2)
        grid.addWidget(QLabel("Uses ligand bounds + 5 Å padding; values remain editable."), 5, 2)
        self.bound_resname = QLineEdit(); self.bound_resname.setPlaceholderText("PDB residue name, e.g. VT1")
        bound_button = QPushButton("Box from bound ligand in receptor"); bound_button.clicked.connect(self.bound_ligand_box)
        grid.addWidget(self.bound_resname, 6, 0); grid.addWidget(bound_button, 6, 1); grid.addWidget(QLabel("Uses selected chain and removes no atoms."), 6, 2)
        layout.addWidget(grid_group)
        self.prepare_receptor_btn = QPushButton("Prepare receptor"); self.prepare_receptor_btn.setProperty("primary", True); self.prepare_receptor_btn.clicked.connect(self.start_receptor)
        layout.addWidget(self.prepare_receptor_btn); layout.addStretch(); self.tabs.addTab(page, "2  Receptor & grid")

    def _build_ligand_tab(self):
        page = QWidget(); layout = QVBoxLayout(page)
        bar = QHBoxLayout(); add = QPushButton("Add SDF/MOL/MOL2 files…"); clear = QPushButton("Clear list")
        add.clicked.connect(self.add_ligands); clear.clicked.connect(lambda: self.source_table.setRowCount(0))
        bar.addWidget(add); bar.addWidget(clear); bar.addStretch(); layout.addLayout(bar)
        geometry = QGroupBox("Ligand geometry preparation"); gf = QFormLayout(geometry)
        self.ligand_generate_3d = QCheckBox("Generate 3D coordinates when missing"); self.ligand_generate_3d.setChecked(True)
        self.ligand_optimize = QCheckBox("Optimize/minimize geometry"); self.ligand_optimize.setChecked(True)
        self.ligand_forcefield = QComboBox(); self.ligand_forcefield.addItems(["MMFF94", "MMFF94s", "UFF"])
        self.ligand_num_conformers = QSpinBox(); self.ligand_num_conformers.setRange(1, 100); self.ligand_num_conformers.setValue(10)
        self.ligand_max_iters = QSpinBox(); self.ligand_max_iters.setRange(10, 10000); self.ligand_max_iters.setValue(500); self.ligand_max_iters.setSingleStep(100)
        gf.addRow(self.ligand_generate_3d); gf.addRow(self.ligand_optimize); gf.addRow("Force field", self.ligand_forcefield); gf.addRow("Generated conformers (missing 3D only)", self.ligand_num_conformers); gf.addRow("Maximum iterations per conformer", self.ligand_max_iters)
        layout.addWidget(geometry)
        self.source_table = QTableWidget(0, 2); self.source_table.setHorizontalHeaderLabels(["Input file", "Format"])
        self.source_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch); layout.addWidget(self.source_table)
        self.prepare_ligands_btn = QPushButton("Prepare ligand library"); self.prepare_ligands_btn.setProperty("primary", True); self.prepare_ligands_btn.clicked.connect(self.start_ligands)
        layout.addWidget(self.prepare_ligands_btn)
        self.ligand_table = QTableWidget(0, 3); self.ligand_table.setHorizontalHeaderLabels(["Ligand", "Status", "Details"])
        self.ligand_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch); layout.addWidget(self.ligand_table)
        self.ligand_progress = QProgressBar(); layout.addWidget(self.ligand_progress); self.tabs.addTab(page, "3  Ligands")

    def _build_screen_tab(self):
        page = QWidget(); layout = QVBoxLayout(page)
        params = QGroupBox("Docking engine and search settings"); form = QFormLayout(params)
        self.engine = QComboBox(); self.engine.addItem("AutoDock4 (CPU)", "autodock4"); self.engine.addItem("AutoDock-GPU (external executable)", "autodock_gpu")
        self.engine.currentIndexChanged.connect(self.load_results)
        self.gpu_device = QSpinBox(); self.gpu_device.setRange(1, 32); self.gpu_device.setValue(1)
        self.ga_runs = QSpinBox(); self.ga_runs.setRange(1, 1000); self.ga_runs.setValue(10)
        self.ga_evals = QSpinBox(); self.ga_evals.setRange(1000, 100_000_000); self.ga_evals.setValue(2_500_000); self.ga_evals.setSingleStep(100000)
        self.parallel = QSpinBox(); self.parallel.setRange(1, max(1, os.cpu_count() or 1)); self.parallel.setValue(max(1, min(2, (os.cpu_count() or 2) // 2)))
        form.addRow("Engine", self.engine); form.addRow("GPU device (starts at 1)", self.gpu_device)
        form.addRow("GA runs per ligand", self.ga_runs); form.addRow("Maximum evaluations", self.ga_evals); form.addRow("Parallel AutoDock4 processes (GPU runs sequentially)", self.parallel)
        layout.addWidget(params)
        analysis = QGroupBox("Automatic post-docking analysis"); af = QFormLayout(analysis)
        self.analysis_top_n = QSpinBox(); self.analysis_top_n.setRange(1, 500); self.analysis_top_n.setValue(20)
        self.analysis_use_plip = QCheckBox("Run PLIP profiling and create 2D interaction maps"); self.analysis_use_plip.setChecked(True)
        af.addRow("Top poses for receptor-contact analysis", self.analysis_top_n)
        af.addRow(self.analysis_use_plip); layout.addWidget(analysis)
        buttons = QHBoxLayout(); self.run_btn = QPushButton("Run virtual screening"); self.run_btn.setProperty("primary", True); self.run_btn.clicked.connect(lambda: self.start_screen(False))
        self.retry_btn = QPushButton("Retry failed only"); self.retry_btn.clicked.connect(lambda: self.start_screen(True))
        self.cancel_btn = QPushButton("Cancel"); self.cancel_btn.setEnabled(False); self.cancel_btn.clicked.connect(self.cancel_work)
        self.open_results_btn = QPushButton("Open comparison CSV"); self.open_results_btn.clicked.connect(self.open_results)
        self.analyze_btn = QPushButton("Analyze existing results"); self.analyze_btn.clicked.connect(self.start_analysis)
        self.open_report_btn = QPushButton("Open analysis report"); self.open_report_btn.clicked.connect(self.open_report)
        buttons.addWidget(self.run_btn); buttons.addWidget(self.retry_btn); buttons.addWidget(self.cancel_btn); buttons.addWidget(self.analyze_btn); buttons.addWidget(self.open_results_btn); buttons.addWidget(self.open_report_btn); buttons.addStretch(); layout.addLayout(buttons)
        self.screen_progress = QProgressBar(); layout.addWidget(self.screen_progress)
        self.result_table = QTableWidget(0, 5); self.result_table.setHorizontalHeaderLabels(["Rank", "Ligand", "Energy (kcal/mol)", "Best run", "Status"])
        self.result_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch); layout.addWidget(self.result_table)
        self.tabs.addTab(page, "4  Screen & results")

    def _set_project_enabled(self, enabled: bool):
        for index in range(1, 4): self.tabs.setTabEnabled(index, enabled)
        # Explicitly restore action buttons as well as their parent tabs. This
        # matters when an existing project is opened after a previous worker
        # disabled the controls or after a project-load signal changed tabs.
        for button in (
            self.prepare_receptor_btn, self.prepare_ligands_btn, self.run_btn,
            self.retry_btn, self.analyze_btn, self.open_results_btn,
            self.open_report_btn,
        ):
            button.setEnabled(enabled)
        if not enabled:
            self.cancel_btn.setEnabled(False)

    def choose_project(self):
        path = QFileDialog.getExistingDirectory(self, "Select project folder")
        if path: self.project_path.setText(path)

    def choose_exe(self, line):
        path, _ = QFileDialog.getOpenFileName(self, "Select executable", filter="Executables (*.exe);;All files (*)")
        if path: line.setText(path)

    def choose_command(self, line):
        path, _ = QFileDialog.getOpenFileName(self, "Select command or script", filter="Python scripts and commands (*.py *.exe *.bat);;All files (*)")
        if path: line.setText(path)

    def save_tool_paths(self):
        for key, line in (("autogrid", self.autogrid_path), ("autodock", self.autodock_path), ("autodock_gpu", self.autodock_gpu_path), ("prepare_ligand", self.prep_ligand_path), ("prepare_receptor", self.prep_receptor_path), ("openbabel", self.openbabel_path), ("adt_python", self.adt_python_path), ("adt_prepare_receptor", self.adt_receptor_path)):
            self.settings.setValue(key, line.text().strip())
        if self.project:
            self._sync_project(); self.project.save()
        self.statusBar().showMessage("Tool paths saved.")

    def check_tools(self):
        messages = check_tool_setup(
            self.autogrid_path.text(), self.autodock_path.text(),
            self.prep_ligand_path.text(), self.prep_receptor_path.text(), self.openbabel_path.text(),
            self.autodock_gpu_path.text(), self.engine.currentData(),
        )
        missing = any(line.startswith("MISSING:") for line in messages)
        dialog = QMessageBox.warning if missing else QMessageBox.information
        dialog(self, "SIDock tool check", "\n\n".join(messages))

    def create_project(self):
        path = self.project_path.text().strip()
        if not path: return self.warn("Choose a project folder first.")
        root = Path(path).expanduser().resolve(); root.mkdir(parents=True, exist_ok=True)
        if (root / "project.json").exists(): return self.warn("This folder already contains a project. Use Open existing.")
        self.project = Project(str(root)); self._sync_project(); self.project.save(); self._loaded()

    def open_project(self):
        path = self.project_path.text().strip()
        if not path: return self.warn("Choose an existing project folder first.")
        try: self.project = Project.load(path)
        except Exception as exc: return self.warn(f"Could not open project: {exc}")
        self._populate_project(); self._loaded()

    def _loaded(self):
        self._set_project_enabled(True)
        self.statusBar().showMessage(f"Project loaded and workflow enabled: {self.project.root}")

    def _sync_project(self):
        if not self.project: return
        self.project.tools.autogrid = self.autogrid_path.text().strip(); self.project.tools.autodock = self.autodock_path.text().strip(); self.project.tools.autodock_gpu = self.autodock_gpu_path.text().strip()
        self.project.tools.prepare_ligand = self.prep_ligand_path.text().strip(); self.project.tools.prepare_receptor = self.prep_receptor_path.text().strip()
        self.project.tools.openbabel = self.openbabel_path.text().strip()
        self.project.tools.adt_python = self.adt_python_path.text().strip(); self.project.tools.adt_prepare_receptor = self.adt_receptor_path.text().strip()
        self.project.receptor_source = self.receptor_path.text().strip(); self.project.remove_waters = self.remove_waters.isChecked(); self.project.remove_hetero = self.remove_hetero.isChecked()
        self.project.receptor_chain = self.receptor_chain.text().strip(); self.project.keep_hetero_resnames = self.keep_hetero.text().strip(); self.project.box_reference_resname = self.bound_resname.text().strip()
        self.project.receptor_input_mode = self.receptor_mode.currentData(); self.project.openbabel_add_hydrogens = self.ob_add_h.isChecked()
        self.project.ligand_generate_3d = self.ligand_generate_3d.isChecked(); self.project.ligand_optimize = self.ligand_optimize.isChecked(); self.project.ligand_forcefield = self.ligand_forcefield.currentText(); self.project.ligand_num_conformers = self.ligand_num_conformers.value(); self.project.ligand_max_iters = self.ligand_max_iters.value()
        self.project.analysis_top_n = self.analysis_top_n.value()
        self.project.analysis_use_plip = self.analysis_use_plip.isChecked()
        for spin, value in zip(self.centers, ("center_x", "center_y", "center_z")): setattr(self.project.grid, value, spin.value())
        for spin, value in zip(self.npts, ("npts_x", "npts_y", "npts_z")): setattr(self.project.grid, value, spin.value() + spin.value() % 2)
        self.project.grid.spacing = self.spacing.value(); self.project.docking.ga_runs = self.ga_runs.value(); self.project.docking.ga_num_evals = self.ga_evals.value(); self.project.docking.parallel_jobs = self.parallel.value()
        self.project.docking.engine = self.engine.currentData(); self.project.docking.gpu_device = self.gpu_device.value()
        self.project.ligand_sources = [self.source_table.item(r, 0).text() for r in range(self.source_table.rowCount())]

    def _populate_project(self):
        p = self.project; self.project_path.setText(p.root); self.receptor_path.setText(p.receptor_source)
        self.autogrid_path.setText(p.tools.autogrid); self.autodock_path.setText(p.tools.autodock); self.autodock_gpu_path.setText(p.tools.autodock_gpu); self.prep_ligand_path.setText(normalize_meeko_command(p.tools.prepare_ligand)); self.prep_receptor_path.setText(normalize_meeko_command(p.tools.prepare_receptor)); self.openbabel_path.setText(p.tools.openbabel); self.adt_python_path.setText(p.tools.adt_python); self.adt_receptor_path.setText(p.tools.adt_prepare_receptor)
        mode_index = self.receptor_mode.findData(p.receptor_input_mode); self.receptor_mode.setCurrentIndex(max(0, mode_index)); self.ob_add_h.setChecked(p.openbabel_add_hydrogens)
        self.ligand_generate_3d.setChecked(p.ligand_generate_3d); self.ligand_optimize.setChecked(p.ligand_optimize); ff_index = self.ligand_forcefield.findText(p.ligand_forcefield); self.ligand_forcefield.setCurrentIndex(max(0, ff_index)); self.ligand_num_conformers.setValue(p.ligand_num_conformers); self.ligand_max_iters.setValue(p.ligand_max_iters)
        self.analysis_top_n.setValue(p.analysis_top_n)
        self.analysis_use_plip.setChecked(p.analysis_use_plip)
        self.remove_waters.setChecked(p.remove_waters); self.remove_hetero.setChecked(p.remove_hetero)
        self.receptor_chain.setText(p.receptor_chain); self.keep_hetero.setText(p.keep_hetero_resnames); self.bound_resname.setText(p.box_reference_resname)
        for spin, val in zip(self.centers, (p.grid.center_x, p.grid.center_y, p.grid.center_z)): spin.setValue(val)
        for spin, val in zip(self.npts, (p.grid.npts_x, p.grid.npts_y, p.grid.npts_z)): spin.setValue(val)
        self.spacing.setValue(p.grid.spacing); self.ga_runs.setValue(p.docking.ga_runs); self.ga_evals.setValue(p.docking.ga_num_evals); self.parallel.setValue(p.docking.parallel_jobs)
        self.gpu_device.setValue(p.docking.gpu_device); self.engine.setCurrentIndex(max(0, self.engine.findData(p.docking.engine)))
        self.source_table.setRowCount(0)
        for source in p.ligand_sources: self._add_source(source)
        self.load_results()

    def choose_receptor(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select receptor", filter="Receptor (*.pdb *.pdbqt);;All files (*)")
        if path: self.receptor_path.setText(path)

    def reference_box(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select reference ligand", filter="PDB coordinates (*.pdb *.pdbqt);;All files (*)")
        if not path: return
        try: box = box_from_reference(Path(path), 5.0, self.spacing.value())
        except Exception as exc: return self.warn(str(exc))
        for spin, val in zip(self.centers, (box.center_x, box.center_y, box.center_z)): spin.setValue(val)
        for spin, val in zip(self.npts, (box.npts_x, box.npts_y, box.npts_z)): spin.setValue(val)

    def bound_ligand_box(self):
        receptor = Path(self.receptor_path.text().strip())
        if not receptor.exists(): return self.warn("Select the original receptor PDB first.")
        try:
            box = box_from_receptor_residue(
                receptor, self.bound_resname.text(), self.receptor_chain.text(),
                5.0, self.spacing.value(),
            )
        except Exception as exc: return self.warn(str(exc))
        for spin, val in zip(self.centers, (box.center_x, box.center_y, box.center_z)): spin.setValue(val)
        for spin, val in zip(self.npts, (box.npts_x, box.npts_y, box.npts_z)): spin.setValue(val)

    def add_ligands(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Add ligand files", filter="Ligands (*.sdf *.mol *.mol2);;All files (*)")
        existing = {self.source_table.item(r, 0).text() for r in range(self.source_table.rowCount())}
        for path in paths:
            if path not in existing: self._add_source(path)

    def _add_source(self, path):
        row = self.source_table.rowCount(); self.source_table.insertRow(row); self.source_table.setItem(row, 0, QTableWidgetItem(path)); self.source_table.setItem(row, 1, QTableWidgetItem(Path(path).suffix.upper().lstrip(".")))

    def start_receptor(self):
        if not self.project: return self.warn("Create or open a project first.")
        self._sync_project(); self.project.save(); self._start_worker("prepare_receptor")

    def start_ligands(self):
        if not self.project: return self.warn("Create or open a project first.")
        self._sync_project(); self.project.save(); self.ligand_table.setRowCount(0); self._start_worker("prepare_ligands")

    def start_screen(self, failed_only):
        self._sync_project(); self.project.save()
        engine_tool = self.project.tools.autodock_gpu if self.project.docking.engine == "autodock_gpu" else self.project.tools.autodock
        if not self.project.tools.autogrid or not engine_tool: return self.warn("Set AutoGrid4 and the selected docking engine executable in Project.")
        self._start_worker("screen", failed_only)

    def start_analysis(self):
        self._sync_project(); self.project.save()
        if not Path(self.project.receptor_pdbqt).exists(): return self.warn("Prepare the receptor before analysis.")
        if not any(dlg_directory(self.project).glob("*.dlg")): return self.warn("No DLG files exist for the selected engine yet.")
        self._start_worker("analyze")

    def _start_worker(self, action, failed_only=False):
        if self.thread and self.thread.isRunning(): return self.warn("A task is already running.")
        self.thread = QThread(); self.worker = WorkflowWorker(self.project, action, failed_only); self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run); self.worker.message.connect(self.statusBar().showMessage); self.worker.progress.connect(self.update_progress); self.worker.ligand_status.connect(self.update_ligand_status); self.worker.finished.connect(self.task_finished); self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater); self.thread.finished.connect(self.thread.deleteLater)
        self.cancel_btn.setEnabled(True); self.run_btn.setEnabled(False); self.analyze_btn.setEnabled(False); self.prepare_receptor_btn.setEnabled(False); self.prepare_ligands_btn.setEnabled(False); self.thread.start()

    def cancel_work(self):
        if self.worker: self.worker.cancel(); self.statusBar().showMessage("Cancelling after the active process stops…")

    def update_progress(self, done, total):
        progress = self.screen_progress if self.tabs.currentIndex() == 3 else self.ligand_progress
        progress.setMaximum(max(1, total)); progress.setValue(done)

    def update_ligand_status(self, ligand, status, details):
        table = self.ligand_table
        match = next((r for r in range(table.rowCount()) if table.item(r, 0).text() == ligand), None)
        row = match if match is not None else table.rowCount()
        if match is None: table.insertRow(row); table.setItem(row, 0, QTableWidgetItem(ligand))
        table.setItem(row, 1, QTableWidgetItem(status)); table.setItem(row, 2, QTableWidgetItem(details))
        color = QColor("#dff2e3") if status in {"prepared", "complete"} else QColor("#fde3e3") if status == "failed" else QColor("#fff3cf")
        for col in range(3):
            if table.item(row, col): table.item(row, col).setBackground(color)

    def task_finished(self, success, message):
        self.cancel_btn.setEnabled(False); self._set_project_enabled(self.project is not None)
        self.statusBar().showMessage(message); self.load_results()
        (QMessageBox.information if success else QMessageBox.warning)(self, "SIDock", message)
        self.worker = None; self.thread = None

    def load_results(self):
        self.result_table.setRowCount(0)
        if not self.project: return
        comparison = analysis_directory(self.project) / "comparison.csv"
        if comparison.exists():
            fields = (
                ("consensus_rank", "Overall rank"), ("ligand", "Ligand"),
                ("consensus_score", "Consensus score"), ("energy_kcal_mol", "Energy (kcal/mol)"),
                ("energy_rank", "Energy rank"), ("ligand_efficiency_rank", "LE rank"),
                ("cluster_support", "Cluster support"),
            )
            self.result_table.setColumnCount(len(fields)); self.result_table.setHorizontalHeaderLabels([label for _, label in fields])
            self.result_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            with comparison.open(encoding="utf-8") as handle:
                for item in csv.DictReader(handle):
                    row = self.result_table.rowCount(); self.result_table.insertRow(row)
                    for col, (key, _) in enumerate(fields): self.result_table.setItem(row, col, QTableWidgetItem(item.get(key, "")))
            return
        path = results_directory(self.project) / "results.csv"
        if not path.exists(): return
        self.result_table.setColumnCount(6); self.result_table.setHorizontalHeaderLabels(["Rank", "Ligand", "Energy (kcal/mol)", "Best run", "Status", "Error/details"])
        self.result_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.result_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        with path.open(encoding="utf-8") as handle:
            for item in csv.DictReader(handle):
                row = self.result_table.rowCount(); self.result_table.insertRow(row)
                for col, key in enumerate(("rank", "ligand", "best_energy_kcal_mol", "best_run", "status", "error")): self.result_table.setItem(row, col, QTableWidgetItem(item.get(key, "")))

    def open_results(self):
        if not self.project: return
        path = analysis_directory(self.project) / "comparison.csv"
        if not path.exists(): path = results_directory(self.project) / "results.csv"
        if path.exists(): QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else: self.warn("No comparison or ranked results exist yet.")

    def open_report(self):
        if not self.project: return
        path = analysis_directory(self.project) / "report.html"
        if path.exists(): QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else: self.warn("No analysis report exists yet. Run screening or Analyze existing results.")

    def warn(self, message): QMessageBox.warning(self, "SIDock", message)

    def show_about(self):
        QMessageBox.about(
            self,
            "About SIDock AD4",
            "<h2>SIDock AD4</h2>"
            "<p><b>Version 0.7.7</b></p>"
            "<p>Streamlined Interface for Docking with AutoDock4.</p>"
            "<p>Guided virtual screening and post-docking analysis.</p>"
            "<p><b>Developed by Dr Syahrul Imran</b></p>",
        )


def main():
    app = QApplication(sys.argv); app.setApplicationName("SIDock AD4"); app.setApplicationDisplayName("SIDock AD4"); app.setOrganizationName("Dr Syahrul Imran"); app.setStyleSheet(APP_STYLE)
    window = MainWindow(); window.show(); sys.exit(app.exec())


if __name__ == "__main__":
    main()
