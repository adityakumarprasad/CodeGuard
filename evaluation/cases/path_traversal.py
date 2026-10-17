import os
from flask import Flask, request, send_file

app = Flask(__name__)
BASE_DIR = "/srv/files"


@app.route("/download")
def download():
    name = request.args.get("name")
    return send_file(os.path.join(BASE_DIR, name))  # VULN: path-traversal
