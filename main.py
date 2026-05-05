import subprocess
import threading
import sys
import os
import time

def install_requirements():
    print("Checking dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("Dependencies checked/installed.")
    except Exception as e:
        print(f"Error installing dependencies: {e}")

def run_process(command, prefix, cwd=None):
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=True,
        text=True,
        cwd=cwd
    )
    
    for line in iter(process.stdout.readline, ""):
        print(f"{prefix} {line}", end="")
    
    process.stdout.close()
    return_code = process.wait()
    print(f"{prefix} Process exited with code {return_code}")

def main():
    # 1. Install/Verify Requirements
    install_requirements()

    # 2. Start Processes
    threads = []
    
    # Start Discord Bot
    bot_cmd = f"\"{sys.executable}\" -m bot.run_bot"
    t_bot = threading.Thread(target=run_process, args=(bot_cmd, "[BOT]"), name="BotThread")
    threads.append(t_bot)
    
    # Start Reflex Web App
    # Explicitly set host and port to avoid auto-jumping to 8001
    web_cmd = f"\"{sys.executable}\" -m reflex run --backend-port 8000 --frontend-port 3000 --backend-host 0.0.0.0"
    t_web = threading.Thread(target=run_process, args=(web_cmd, "[WEB]", "web"), name="WebThread")
    threads.append(t_web)

    print("Starting all components...")
    for t in threads:
        t.daemon = True
        t.start()

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")

if __name__ == "__main__":
    main()
