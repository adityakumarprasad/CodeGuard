import yaml
from flask import Flask, request

app = Flask(__name__)


@app.route("/config", methods=["POST"])
def upload_config():
    settings = yaml.load(request.data, Loader=yaml.Loader)  # VULN: unsafe-yaml
    return {"keys": list(settings)}
