from flask import Flask, jsonify
from scanner import run_scanner

app = Flask(__name__)


@app.get("/")
def home():
    return jsonify({
        "status": "online",
        "app": "MA Crossover Scanner",
        "version": "1.0"
    })


@app.get("/scan")
def scan():

    results = run_scanner()

    return jsonify({
        "status": "success",
        "count": len(results),
        "results": results
    })
