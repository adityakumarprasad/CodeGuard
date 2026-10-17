import pickle
from flask import Flask, request

app = Flask(__name__)


@app.route("/load", methods=["POST"])
def load():
    data = pickle.loads(request.data)  # VULN: insecure-deserialization
    return {"items": len(data)}
