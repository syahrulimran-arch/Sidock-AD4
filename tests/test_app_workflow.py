"""Regression tests for complete project-opening GUI behavior."""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from sidock.app import MainWindow
from sidock.model import Project


def test_open_existing_project_unlocks_receptor_and_ligand_tabs(tmp_path: Path):
    app = QApplication.instance() or QApplication(["SIDock-GUI-test"])
    root = tmp_path / "existing_project"
    Project(str(root)).save()
    window = MainWindow()
    assert not window.tabs.isTabEnabled(1)
    assert not window.prepare_receptor_btn.isEnabled()

    window.project_path.setText(str(root))
    window.open_project()

    assert window.project is not None
    assert window.tabs.isTabEnabled(1)
    assert window.tabs.isTabEnabled(2)
    assert window.tabs.isTabEnabled(3)
    assert window.prepare_receptor_btn.isEnabled()
    assert window.prepare_ligands_btn.isEnabled()
    assert "workflow enabled" in window.statusBar().currentMessage()
    window.close()
    app.processEvents()
