"""Automated tests for system diagnostic information collector."""

from jarvis.core.system_info import SystemInfoCollector, format_bytes


def test_format_bytes():
    assert format_bytes(500) == "500.0 B"
    assert format_bytes(1024) == "1.0 KB"
    assert format_bytes(1024 * 1024) == "1.0 MB"
    assert format_bytes(1024 * 1024 * 1024) == "1.0 GB"


def test_get_system_summary_structure():
    summary = SystemInfoCollector.get_system_summary()
    assert isinstance(summary, dict)

    expected_keys = [
        "os_name", "os_release", "os_version", "hostname", "username",
        "cpu_percent", "cpu_cores_logical", "memory", "disk", "python_version"
    ]
    for key in expected_keys:
        assert key in summary

    assert isinstance(summary["memory"], dict)
    assert "percent" in summary["memory"]
    assert isinstance(summary["disk"], dict)
    assert "percent" in summary["disk"]


def test_get_formatted_report():
    report = SystemInfoCollector.get_formatted_report()
    assert isinstance(report, str)
    assert "SYSTEM DIAGNOSTICS" in report
    assert "CPU UTILIZATION" in report
    assert "MEMORY USAGE" in report
    assert "PYTHON CORE" in report
