from __future__ import annotations

import asyncio
import logging
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from typing import Any

try:
    from winrm.protocol import Protocol
    HAS_WINRM = True
except ImportError:
    HAS_WINRM = False

logger = logging.getLogger(__name__)


class DeviceActivityService:
    """Track detailed activity via Windows Event Logs for company device owners.
    
    Integrates with Windows Event Log via WinRM to track:
    - User logon/logoff times
    - Application execution (Event ID 1 in Sysmon or AppLocker)
    - System idle periods
    - Suspicious activity patterns
    """

    def __init__(self) -> None:
        """Initialize device activity service with WinRM support."""
        from app.core.config import get_settings
        
        self.settings = get_settings()
        self.winrm_protocol = None
        self.is_available = False
        
        if not HAS_WINRM:
            logger.warning("pywinrm not installed. Install with: pip install pywinrm")
            return
        
        if not self.settings.winrm_enabled:
            logger.info("WinRM device tracking is disabled in settings")
            return
        
        try:
            self.winrm_protocol = Protocol(
                endpoint=self.settings.winrm_endpoint,
                transport="basic",
                username=self.settings.winrm_username or None,
                password=self.settings.winrm_password or None,
            )
            self.is_available = True
            logger.info(f"WinRM initialized: {self.settings.winrm_endpoint}")
        except Exception as e:
            logger.error(f"Failed to initialize WinRM: {e}")

    async def _run_powershell_command(self, command: str) -> str | None:
        """Execute PowerShell command via WinRM."""
        if not self.winrm_protocol:
            return None
        
        try:
            shell_id = self.winrm_protocol.open_shell()
            command_id = self.winrm_protocol.run_command(shell_id, command)
            std_out, std_err, return_code = self.winrm_protocol.get_command_output(shell_id, command_id)
            self.winrm_protocol.cleanup_command(shell_id, command_id)
            self.winrm_protocol.close_shell(shell_id)
            
            if return_code != 0:
                logger.error(f"PowerShell error: {std_err}")
                return None
            return std_out.decode("utf-8") if isinstance(std_out, bytes) else std_out
        except Exception as e:
            logger.error(f"WinRM command failed: {e}")
            return None

    async def get_device_activity(
        self,
        device_id: str,
        employee_email: str,
        activity_date: date,
    ) -> dict[str, Any]:
        """Fetch detailed device activity from Windows Event Logs."""
        activity = {
            "device_id": device_id,
            "employee_email": employee_email,
            "activity_date": activity_date.isoformat(),
            "app_usage": [],
            "idle_periods": [],
            "logon_logoff": [],
            "total_active_seconds": 0,
            "data_source": "Windows Event Logs (Not Available)" if not self.is_available else "Windows Event Logs",
        }
        
        if not self.is_available:
            return activity
        
        try:
            # Fetch logon/logoff events
            logon_events = await self._get_logon_events(activity_date)
            activity["logon_logoff"] = logon_events
            
            # Fetch application execution events (if Sysmon/AppLocker enabled)
            app_events = await self._get_app_execution_events(activity_date)
            activity["app_usage"] = app_events
            
            # Calculate idle periods from last activity
            idle = await self._calculate_idle_periods(activity_date, logon_events)
            activity["idle_periods"] = idle
            
            # Calculate total active time
            total_active = sum(e.get("duration_seconds", 0) for e in app_events)
            activity["total_active_seconds"] = total_active
            
            # Detect suspicious patterns
            suspicious = await self._detect_suspicious_activity(activity_date, logon_events, app_events)
            activity["suspicious_activity"] = suspicious
            
        except Exception as e:
            logger.error(f"Error fetching device activity: {e}")
        
        return activity

    async def _get_logon_events(self, activity_date: date) -> list[dict[str, Any]]:
        """Get user logon/logoff events from Windows Security log."""
        # Event IDs: 4624 (logon), 4647 (logoff), 4625 (failed logon)
        date_str = activity_date.isoformat()
        date_start = f"{date_str}T00:00:00"
        date_end = f"{date_str}T23:59:59"
        
        ps_script = f"""
        Get-WinEvent -FilterHashtable @{{
            LogName='Security'
            ID=4624,4647,4625
            StartTime='{date_start}'
            EndTime='{date_end}'
        }} -ErrorAction SilentlyContinue | 
        Select-Object -Property @{{
            Name='EventID'; Expression={{$_.Id}}
            Name='Timestamp'; Expression={{$_.TimeCreated}}
            Name='UserName'; Expression={{$_.Properties[1].Value}}
            Name='LogonType'; Expression={{$_.Properties[8].Value}}
            Name='SourceIP'; Expression={{$_.Properties[18].Value}}
        }} | ConvertTo-Json
        """
        
        output = await self._run_powershell_command(ps_script)
        if not output:
            return []
        
        try:
            import json
            events = json.loads(output) if output.strip() else []
            if not isinstance(events, list):
                events = [events]
            
            return [
                {
                    "event_id": e.get("EventID"),
                    "timestamp": e.get("Timestamp"),
                    "username": e.get("UserName"),
                    "logon_type": e.get("LogonType"),
                    "source_ip": e.get("SourceIP"),
                }
                for e in events
            ]
        except Exception as e:
            logger.error(f"Error parsing logon events: {e}")
            return []

    async def _get_app_execution_events(self, activity_date: date) -> list[dict[str, Any]]:
        """Get application execution events from Sysmon or AppLocker logs.
        
        Requires:
        - Sysmon installed (free from Microsoft/SysInternals)
        - Event ID 1 = Process Creation
        OR
        - AppLocker event logs with execution events
        """
        date_str = activity_date.isoformat()
        date_start = f"{date_str}T00:00:00"
        date_end = f"{date_str}T23:59:59"
        
        ps_script = f"""
        $events = @()
        # Try Sysmon first
        try {{
            $sysmon = Get-WinEvent -FilterHashtable @{{
                LogName='Microsoft-Windows-Sysmon/Operational'
                ID=1
                StartTime='{date_start}'
                EndTime='{date_end}'
            }} -ErrorAction SilentlyContinue
            $events += $sysmon
        }} catch {{ }}
        
        # Fall back to AppLocker
        try {{
            $applocker = Get-WinEvent -FilterHashtable @{{
                LogName='Microsoft-Windows-AppLocker/EXE and DLL'
                ID=8002
                StartTime='{date_start}'
                EndTime='{date_end}'
            }} -ErrorAction SilentlyContinue
            $events += $applocker
        }} catch {{ }}
        
        $events |
        Select-Object -Property @{{
            Name='EventID'; Expression={{$_.Id}}
            Name='Timestamp'; Expression={{$_.TimeCreated}}
            Name='ImageName'; Expression={{
                if ($_.Id -eq 1) {{ 
                    ([xml]$_.toXml()).Event.EventData.Data | Where-Object {{$_.Name -eq 'Image'}} | Select-Object -ExpandProperty '#text'
                }} else {{
                    $_.Properties[0].Value
                }}
            }}
            Name='ProcessID'; Expression={{
                if ($_.Id -eq 1) {{ 
                    ([xml]$_.toXml()).Event.EventData.Data | Where-Object {{$_.Name -eq 'ProcessId'}} | Select-Object -ExpandProperty '#text'
                }} else {{
                    $_.Properties[2].Value
                }}
            }}
        }} | ConvertTo-Json
        """
        
        output = await self._run_powershell_command(ps_script)
        if not output:
            return []
        
        try:
            import json
            events = json.loads(output) if output.strip() else []
            if not isinstance(events, list):
                events = [events] if events else []
            
            # Group by app and calculate duration
            app_times = {}
            for e in sorted(events, key=lambda x: x.get("Timestamp", "")):
                app_name = e.get("ImageName", "Unknown").split("\\")[-1] if e.get("ImageName") else "Unknown"
                if app_name not in app_times:
                    app_times[app_name] = {"count": 0, "first_time": e.get("Timestamp"), "last_time": e.get("Timestamp")}
                app_times[app_name]["count"] += 1
                app_times[app_name]["last_time"] = e.get("Timestamp")
            
            # Convert to duration format
            result = []
            total_duration = sum(max(1, (datetime.fromisoformat(v["last_time"]) - datetime.fromisoformat(v["first_time"])).total_seconds()) if v["first_time"] and v["last_time"] else 0 for v in app_times.values())
            
            for app_name, times in app_times.items():
                duration = max(1, (datetime.fromisoformat(times["last_time"]) - datetime.fromisoformat(times["first_time"])).total_seconds()) if times["first_time"] and times["last_time"] else 0
                result.append({
                    "app_name": app_name,
                    "execution_count": times["count"],
                    "duration_seconds": duration,
                    "percentage": round((duration / total_duration * 100) if total_duration > 0 else 0, 2),
                })
            
            return sorted(result, key=lambda x: x["duration_seconds"], reverse=True)
        except Exception as e:
            logger.error(f"Error parsing app execution events: {e}")
            return []

    async def _calculate_idle_periods(
        self,
        activity_date: date,
        logon_events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Calculate idle periods from logon/logoff events."""
        idle_periods = []
        
        # Sort by timestamp
        logon_events_sorted = sorted(logon_events, key=lambda x: x.get("timestamp", ""))
        
        logon_time = None
        for event in logon_events_sorted:
            event_id = event.get("event_id")
            timestamp = event.get("timestamp")
            
            if event_id == 4624 and not logon_time:  # Logon
                logon_time = timestamp
            elif event_id == 4647 and logon_time:  # Logoff
                logoff_time = timestamp
                try:
                    logon_dt = datetime.fromisoformat(logon_time)
                    logoff_dt = datetime.fromisoformat(logoff_time)
                    duration = (logoff_dt - logon_dt).total_seconds()
                    idle_periods.append({
                        "logon_time": logon_time,
                        "logoff_time": logoff_time,
                        "duration_seconds": duration,
                        "hours": round(duration / 3600, 2),
                    })
                except:
                    pass
                logon_time = None
        
        return idle_periods

    async def _detect_suspicious_activity(
        self,
        activity_date: date,
        logon_events: list[dict[str, Any]],
        app_events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Detect unusual activity patterns."""
        suspicious = []
        
        # Check for failed logon attempts
        failed_logons = [e for e in logon_events if e.get("event_id") == 4625]
        if len(failed_logons) > 5:
            suspicious.append({
                "type": "Multiple Failed Logons",
                "confidence": 0.9,
                "details": f"{len(failed_logons)} failed logon attempts detected",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        
        # Check for logon outside normal hours (7 AM - 7 PM)
        for event in logon_events:
            if event.get("event_id") == 4624:
                try:
                    ts = datetime.fromisoformat(event.get("timestamp", ""))
                    if ts.hour < 7 or ts.hour > 19:
                        suspicious.append({
                            "type": "Off-Hours Logon",
                            "confidence": 0.7,
                            "details": f"Logon at {ts.strftime('%H:%M')}",
                            "timestamp": event.get("timestamp"),
                        })
                except:
                    pass
        
        # Check for unusual app execution (system tools, admin tools)
        suspicious_apps = ["cmd.exe", "powershell.exe", "taskmgr.exe", "regedit.exe", "certmgr.exe"]
        for app in app_events:
            if any(suspicious_app in app.get("app_name", "").lower() for suspicious_app in suspicious_apps):
                suspicious.append({
                    "type": "Suspicious App Execution",
                    "confidence": 0.8,
                    "details": f"{app.get('app_name')} executed {app.get('execution_count', 1)} times",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
        
        return suspicious

    async def get_app_usage(
        self,
        device_id: str,
        activity_date: date,
    ) -> list[dict[str, Any]]:
        """Get application usage breakdown for a device."""
        activity = await self.get_device_activity(device_id, "", activity_date)
        return activity.get("app_usage", [])

    async def get_idle_periods(
        self,
        device_id: str,
        activity_date: date,
        min_idle_minutes: int = 15,
    ) -> list[dict[str, Any]]:
        """Get idle periods when no keyboard/mouse activity occurred."""
        activity = await self.get_device_activity(device_id, "", activity_date)
        idle_periods = activity.get("idle_periods", [])
        return [p for p in idle_periods if p.get("duration_seconds", 0) / 60 >= min_idle_minutes]

    async def detect_suspicious_activity(
        self,
        device_id: str,
        employee_email: str,
        activity_date: date,
    ) -> list[dict[str, Any]]:
        """Detect unusual activity patterns."""
        activity = await self.get_device_activity(device_id, employee_email, activity_date)
        return activity.get("suspicious_activity", [])
