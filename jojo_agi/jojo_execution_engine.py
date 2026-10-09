"""
⚡ JoJo AGI: Execution Engine
Provides safe, robust local computer execution capabilities:
- PowerShell & CMD execution with timeout and output capture
- Isolated Python code runner with stdout/stderr capture
- Hardware and OS diagnostics
"""

import subprocess
import sys
import os
import time
import tempfile
try:
    import psutil
except ImportError:
    psutil = None

# Safe workspace root
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def execute_powershell(command: str, timeout: int = 30) -> str:
    """Executes a PowerShell command on the host Windows system and returns the output."""
    timeout = max(1, min(int(timeout), 60))
    try:
        # Wrap execution with UTF-8 encoding support
        ps_script = f"""
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        $OutputEncoding = [System.Text.Encoding]::UTF8
        {command}
        """
        process = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=WORKSPACE_ROOT
        )
        out = process.stdout.strip()
        err = process.stderr.strip()
        if process.returncode != 0:
            return f"❌ Exit Code {process.returncode}:\n{err or out or 'Command failed with no output.'}"
        return out if out else "(Command executed successfully with no output)"
    except subprocess.TimeoutExpired:
        return f"⏱️ Execution timed out after {timeout} seconds."
    except Exception as e:
        return f"⚠️ Error executing PowerShell: {str(e)}"

def execute_cmd(command: str, timeout: int = 30) -> str:
    """Executes a Windows Command Prompt (cmd.exe) command and returns output."""
    try:
        process = subprocess.run(
            f"chcp 65001 > nul && {command}",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=WORKSPACE_ROOT
        )
        out = process.stdout.strip()
        err = process.stderr.strip()
        if process.returncode != 0:
            return f"❌ Exit Code {process.returncode}:\n{err or out}"
        return out if out else "(Command executed successfully with no output)"
    except subprocess.TimeoutExpired:
        return f"⏱️ Execution timed out after {timeout} seconds."
    except Exception as e:
        return f"⚠️ Error executing CMD: {str(e)}"

def execute_python_code(code: str, timeout: int = 30) -> str:
    """Executes a snippet of Python code in the current Python environment and returns stdout/stderr."""
    timeout = max(1, min(int(timeout), 60))
    # Write to a temporary file
    temp_dir = os.path.join(WORKSPACE_ROOT, "scratch")
    os.makedirs(temp_dir, exist_ok=True)
    
    temp_file = os.path.join(temp_dir, f"_agent_exec_{int(time.time()*1000)}.py")
    try:
        # Prepend UTF-8 reconfiguration so console doesn't crash on Devanagari
        full_code = (
            "import sys\n"
            "if hasattr(sys.stdout, 'reconfigure'):\n"
            "    sys.stdout.reconfigure(encoding='utf-8', errors='replace')\n"
            "if hasattr(sys.stderr, 'reconfigure'):\n"
            "    sys.stderr.reconfigure(encoding='utf-8', errors='replace')\n"
            + code
        )
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(full_code)

        process = subprocess.run(
            [sys.executable, temp_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=WORKSPACE_ROOT
        )
        out = process.stdout.strip()
        err = process.stderr.strip()
        if process.returncode != 0:
            return f"❌ Python Error (Exit {process.returncode}):\n{err or out}"
        return out if out else "(Python code executed successfully with no output)"
    except subprocess.TimeoutExpired:
        return f"⏱️ Python script timed out after {timeout} seconds."
    except Exception as e:
        return f"⚠️ Python Execution Error: {str(e)}"
    finally:
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except Exception:
            pass

def get_system_diagnostics() -> str:
    """Retrieves live system diagnostics: CPU, Memory, Disk, and top processes."""
    diag = []
    # Try using psutil if installed, or powershell
    try:
        import psutil
        cpu_pct = psutil.cpu_percent(interval=0.2)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('C:\\')
        diag.append(f"💻 CPU Usage: {cpu_pct}%")
        diag.append(f"🧠 RAM Usage: {mem.percent}% ({mem.used // (1024**2)}MB / {mem.total // (1024**2)}MB)")
        diag.append(f"💾 C: Drive: {disk.percent}% used ({disk.free // (1024**3)}GB free)")
        
        # Battery if available
        battery = psutil.sensors_battery()
        if battery:
            diag.append(f"🔋 Battery: {battery.percent}% ({'Charging' if battery.power_plugged else 'Discharging'})")
            
        # Top 5 CPU processes
        procs = sorted(
            [p for p in psutil.process_iter(['name', 'cpu_percent']) if p.info['name']],
            key=lambda p: p.info.get('cpu_percent') or 0,
            reverse=True
        )[:5]
        top_str = ", ".join([f"{p.info['name']} ({p.info['cpu_percent']}%)" for p in procs if p.info.get('cpu_percent')])
        if top_str:
            diag.append(f"📊 Top Processes: {top_str}")
    except Exception:
        # Fallback to PowerShell
        ps_out = execute_powershell("Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize, FreePhysicalMemory")
        diag.append(f"OS Diagnostics: {ps_out}")
        
    return "\n".join(diag)
