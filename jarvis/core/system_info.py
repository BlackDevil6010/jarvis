"""System information collector for hardware, memory, disk, and OS diagnostics."""

import os
import sys
import platform
import time
from datetime import datetime
from typing import Dict, Any

try:
    import psutil
except ImportError:
    psutil = None


def format_bytes(bytes_value: int) -> str:
    """Format byte counts into human-readable GB/MB strings."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"


class SystemInfoCollector:
    """Retrieves diagnostic and health metrics for the host Windows system."""

    @staticmethod
    def get_system_summary() -> Dict[str, Any]:
        """Collect comprehensive system metrics."""
        boot_time_ts = psutil.boot_time() if psutil else None
        uptime_str = "Unavailable"
        if boot_time_ts:
            uptime_seconds = int(time.time() - boot_time_ts)
            hours, remainder = divmod(uptime_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime_str = f"{hours}h {minutes}m {seconds}s"

        # CPU info
        cpu_percent = psutil.cpu_percent(interval=0.1) if psutil else 0.0
        cpu_count_logical = psutil.cpu_count(logical=True) if psutil else os.cpu_count() or 1
        cpu_count_physical = psutil.cpu_count(logical=False) if psutil else 1

        # Memory info
        memory_data = {}
        if psutil:
            mem = psutil.virtual_memory()
            memory_data = {
                "total": format_bytes(mem.total),
                "used": format_bytes(mem.used),
                "available": format_bytes(mem.available),
                "percent": mem.percent
            }
        else:
            memory_data = {"percent": 0, "total": "N/A", "used": "N/A", "available": "N/A"}

        # Disk info (Primary system drive)
        disk_data = {}
        system_drive = os.environ.get("SystemDrive", "C:") + "\\"
        if psutil:
            try:
                disk = psutil.disk_usage(system_drive)
                disk_data = {
                    "drive": system_drive,
                    "total": format_bytes(disk.total),
                    "used": format_bytes(disk.used),
                    "free": format_bytes(disk.free),
                    "percent": disk.percent
                }
            except Exception:
                disk_data = {"drive": system_drive, "percent": 0, "free": "N/A"}

        return {
            "os_name": platform.system(),
            "os_release": platform.release(),
            "os_version": platform.version(),
            "os_architecture": platform.machine(),
            "hostname": platform.node(),
            "username": os.environ.get("USERNAME", "User"),
            "uptime": uptime_str,
            "cpu_percent": cpu_percent,
            "cpu_cores_physical": cpu_count_physical,
            "cpu_cores_logical": cpu_count_logical,
            "memory": memory_data,
            "disk": disk_data,
            "python_version": platform.python_version(),
            "python_path": sys.executable,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    @classmethod
    def get_formatted_report(cls) -> str:
        """Format metrics into a cybernetic HUD report."""
        data = cls.get_system_summary()
        mem = data["memory"]
        disk = data["disk"]

        report = [
            "================= [ SYSTEM DIAGNOSTICS ] =================",
            f" HOSTNAME       : {data['hostname']} (User: {data['username']})",
            f" OPERATING SYS  : {data['os_name']} {data['os_release']} ({data['os_architecture']})",
            f" KERNEL BUILD   : {data['os_version']}",
            f" SYSTEM UPTIME  : {data['uptime']}",
            "----------------------------------------------------------",
            f" CPU UTILIZATION: {data['cpu_percent']}% across {data['cpu_cores_logical']} cores ({data['cpu_cores_physical']} physical)",
            f" MEMORY USAGE   : {mem.get('percent', 0)}% [{mem.get('used', '0')} / {mem.get('total', '0')}]",
            f" SYSTEM DISK ({disk.get('drive', 'C:')}): {disk.get('percent', 0)}% used [{disk.get('free', '0')} free of {disk.get('total', '0')}]",
            "----------------------------------------------------------",
            f" PYTHON CORE    : v{data['python_version']}",
            f" RUNTIME PATH   : {data['python_path']}",
            "=========================================================="
        ]
        return "\n".join(report)
