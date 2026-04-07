"""Lance le bot Telegram et l'API web en parallele."""

import multiprocessing
import subprocess
import sys


def run_bot():
    subprocess.run([sys.executable, "bot.py"])


def run_api():
    subprocess.run([sys.executable, "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080"])


if __name__ == "__main__":
    p1 = multiprocessing.Process(target=run_bot)
    p2 = multiprocessing.Process(target=run_api)
    p1.start()
    p2.start()
    p1.join()
    p2.join()
