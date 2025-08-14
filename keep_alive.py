# keep_alive.py
import os
import threading
from flask import Flask

app = Flask(__name__)

@app.route("/health")
def health():
    return "OK", 200

@app.route("/")
def home():
    return "OK", 200

@app.route("/favicon.ico")
def favicon():
    return "", 204

def _run():
    # Render daje port w env PORT
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    threading.Thread(target=_run, daemon=True).start()
