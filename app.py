from flask import Flask, jsonify

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
    # We'll connect your scanner.py here next.
    return jsonify({
        "status": "success",
        "message": "Scanner endpoint is working.",
        "results": []
    })
