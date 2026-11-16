"""Shared pytest fixtures for JARVIS test suite."""

import os
import sys
import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    """Ensure a single QApplication instance exists for offscreen/GUI testing."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app
