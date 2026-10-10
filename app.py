"""Q-Energy: start the app.

    python app.py

Opens http://localhost:5000 in your browser. Press Ctrl+C here to stop.
"""
from __future__ import annotations

import os
import threading
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from qenergy import household as hh
from qenergy.grover import search

WEB = Path(__file__).parent / "web"
app = Flask(__name__)


@app.get("/")
def index():
    return send_from_directory(WEB, "index.html")


@app.get("/app.js")
def script():
    return send_from_directory(WEB, "app.js")


@app.get("/api/household")
def household():
    """Default appliances and time slots, so the page and Python share one source."""
    return jsonify({"slots": hh.SLOTS, "appliances": hh.APPLIANCES})


@app.post("/api/search")
def api_search():
    body = request.get_json(force=True, silent=True) or {}
    try:
        appliances = body.get("appliances") or hh.APPLIANCES
        max_bill = float(body.get("max_bill", 45))
        max_peak = float(body.get("max_peak", 4))
        result = search(appliances, max_bill, max_peak, shots=1000)
    except (ValueError, TypeError, KeyError) as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    url = f"http://localhost:{port}"
    print(f"\n  Q-Energy is running at {url}\n  Press Ctrl+C to stop.\n")
    if not os.environ.get("QENERGY_NO_BROWSER"):
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(port=port, debug=False)
