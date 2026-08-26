import subprocess, sys, os
os.chdir(r"C:\Users\Evand\Documents\cris-os")
python = os.path.join(os.path.dirname(__file__) or ".", "venv", "Scripts", "python.exe")
if not os.path.exists(python):
    python = sys.executable
DETACHED_PROCESS = 0x00000008
proc = subprocess.Popen(
    [python, "main.py"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    creationflags=DETACHED_PROCESS,
)
print("PID:", proc.pid)
