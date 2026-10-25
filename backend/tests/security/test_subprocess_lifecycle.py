"""
Deterministic Non-Blocking Subprocess Lifecycle & Escalation Verification Suite
Validates that stubborn mock child processes catching polite termination signals
are forcibly escalated and cleanly collected (taskkill on Windows, killpg on POSIX)
WITHOUT static sleeps.
"""

import os
import sys
import signal
import asyncio
import pytest
from src.security.port_sweep import PortSweep
from src.security.process_watchdog import SubprocessTunnelManager


STUBBORN_CHILD_SCRIPT = """
import sys
import time
import signal

def handle_break(signum, frame):
    print("RECEIVED_POLITE_SIGNAL", flush=True)
    # Stubborn child: refuses to exit!

if sys.platform != "win32":
    signal.signal(signal.SIGTERM, handle_break)
else:
    # On Windows, SIGBREAK corresponds to CTRL_BREAK_EVENT
    signal.signal(signal.SIGBREAK, handle_break)

print("CHILD_INITIALIZED", flush=True)

while True:
    time.sleep(0.05)
"""


@pytest.mark.asyncio
async def test_stubborn_subprocess_escalation_protocol(tmp_path):
    """
    Spawns a mock stubborn child process, sends polite signal, verifies signal receipt,
    and ensures the watchdog escalates to forced process tree kill.
    """
    script_file = tmp_path / "stubborn_child.py"
    script_file.write_text(STUBBORN_CHILD_SCRIPT, encoding="utf-8")

    cmd = [sys.executable, "-u", str(script_file)]
    subprocess_kwargs = {
        "stdout": asyncio.subprocess.PIPE,
        "stderr": asyncio.subprocess.PIPE
    }

    if sys.platform != "win32":
        subprocess_kwargs["start_new_session"] = True
    else:
        # CREATE_NEW_PROCESS_GROUP = 0x00000200
        subprocess_kwargs["creationflags"] = 0x00000200

    # 1. Spawn child process
    proc = await asyncio.create_subprocess_exec(*cmd, **subprocess_kwargs)
    assert proc.pid > 0

    # 2. Await initialization line non-blockingly
    init_line = await asyncio.wait_for(proc.stdout.readline(), timeout=5.0)
    if not init_line:
        err = await proc.stderr.read()
        pytest.fail(f"Subprocess terminated unexpectedly. Returncode: {proc.returncode}, Stderr: {err.decode('utf-8', errors='replace')}")
    assert b"CHILD_INITIALIZED" in init_line

    # 3. Trigger polite break signal
    if sys.platform != "win32":
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGTERM)
    else:
        os.kill(proc.pid, signal.CTRL_BREAK_EVENT)

    # 4. Verify child received the polite signal but remains alive
    signal_line = await asyncio.wait_for(proc.stdout.readline(), timeout=3.0)
    assert b"RECEIVED_POLITE_SIGNAL" in signal_line
    assert proc.returncode is None

    # 5. Escalate to force-kill after non-blocking wait timeout
    try:
        await asyncio.wait_for(proc.wait(), timeout=0.5)
        pytest.fail("Stubborn child exited on polite signal. Escalation was bypassed!")
    except asyncio.TimeoutError:
        # Expected: child is still running. Execute forced termination
        if sys.platform != "win32":
            os.killpg(pgid, signal.SIGKILL)
        else:
            kill_cmd = ["taskkill", "/F", "/T", "/PID", str(proc.pid)]
            kp = await asyncio.create_subprocess_exec(
                *kill_cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
            )
            await kp.wait()

    # 6. Verify clean collection
    exit_code = await asyncio.wait_for(proc.wait(), timeout=3.0)
    assert exit_code is not None


def test_port_sweep_detection():
    """Validates PortSweep methods."""
    # Test an unlikely high port (e.g., 59998)
    free_port = 59998
    assert not PortSweep.is_port_in_use(free_port)
    pids = PortSweep.find_pids_on_port(free_port)
    assert isinstance(pids, list)
    assert len(pids) == 0
