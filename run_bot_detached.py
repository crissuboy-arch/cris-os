import subprocess, sys, os, time

os.chdir(r"C:\Users\Evand\Documents\cris-os")
sys.path.insert(0, r"C:\Users\Evand\Documents\cris-os")

from config.settings import settings
token = settings.TELEGRAM_BOT_TOKEN
if not token or token == "coloque_aqui_o_token_do_botfather":
    print("TOKEN nao configurado", file=sys.stderr)
    sys.exit(1)

print(f"Starting CRIS OS bot...", flush=True)
proc = subprocess.Popen(
    [sys.executable, "main.py"],
    cwd=r"C:\Users\Evand\Documents\cris-os",
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
)
print(f"Bot started with PID {proc.pid}", flush=True)
time.sleep(2)
print(f"Bot process alive: {proc.poll() is None}", flush=True)