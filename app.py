import os
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
TRIGGER_KEY = os.environ.get("TRIGGER_KEY")

GITHUB_URL = (
    "https://api.github.com/repos/"
    "j-man-21/ma-crossover-scanner/"
    "actions/workflows/scanner.yml/dispatches"
)


@app.get("/")
def home():
    return jsonify({
        "app": "MA Crossover Scanner Trigger",
        "status": "online"
    })


@app.post("/scan")
def scan():

    supplied_key = request.headers.get("X-Trigger-Key")

    if not TRIGGER_KEY or supplied_key != TRIGGER_KEY:
        return jsonify({
            "status": "error",
            "message": "Unauthorized"
        }), 401

    if not GITHUB_TOKEN:
        return jsonify({
            "status": "error",
            "message": "GitHub token not configured"
        }), 500

    response = requests.post(
        GITHUB_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "X-GitHub-Api-Version": "2026-03-10"
        },
        json={
            "ref": "main"
        },
        timeout=30
    )

    if response.status_code not in (200, 201, 204):
        return jsonify({
            "status": "error",
            "github_status": response.status_code,
            "message": response.text
        }), 502

    return jsonify({
        "status": "started"
    }), 202
