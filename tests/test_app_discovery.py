"""Automated tests for Windows General Application Discovery engine."""

import pytest
from jarvis.core.app_discovery import AppDiscovery, DiscoveredApp, COMMON_PROTOCOLS


def test_discovered_app_exact_and_alias_matching():
    """Verify exact, alias, and fuzzy matching for DiscoveredApp."""
    app = DiscoveredApp(
        name="Visual Studio Code",
        target="C:\\Tools\\Code.exe",
        source="app_paths",
        aliases=["vscode", "vs code", "code editor"]
    )

    # Exact name match
    assert app.matches_query("Visual Studio Code") == 1.0
    assert app.matches_query("visual studio code") == 1.0

    # Alias matches
    assert app.matches_query("vscode") == 1.0
    assert app.matches_query("code editor") == 1.0

    # Substring match
    assert app.matches_query("visual") >= 0.85

    # Non-match
    assert app.matches_query("Spotify Player") == 0.0


def test_app_discovery_scan_and_indexing():
    """Verify that AppDiscovery indexes host applications without errors."""
    discovery = AppDiscovery()
    discovery.refresh()

    apps = discovery.list_all()
    assert len(apps) > 0

    # Common Windows utilities should be discovered
    names = [a.clean_name for a in apps]
    assert any("chrome" in n or "edge" in n or "notepad" in n or "calc" in n for n in names)


def test_app_discovery_resolution_category_intents():
    """Verify that category intents (e.g., 'code editor', 'music player', 'browser') resolve."""
    discovery = AppDiscovery()
    discovery.refresh()

    # Search by category intent
    matches = discovery.find_applications("code editor")
    assert len(matches) > 0
    top_match, score = matches[0]
    assert score >= 0.85

    browser_matches = discovery.find_applications("browser")
    assert len(browser_matches) > 0


def test_app_discovery_missing_app_website_suggestion():
    """Verify that requesting an uninstalled known tool returns its official website."""
    discovery = AppDiscovery()
    # Query something not installed or protocol
    app, candidates, website = discovery.resolve_application("nonexistent_phantom_tool_xyz")
    assert app is None
    assert candidates == []

    # Known tool protocol lookup
    app, candidates, website = discovery.resolve_application("spotify")
    if not app:
        assert website == "https://open.spotify.com"
