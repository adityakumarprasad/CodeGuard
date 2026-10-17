import os
import shlex
from flask import Flask, request

app = Flask(__name__)


@app.route("/ping")
def ping():
    host = request.args.get("host", "")
    os.system("ping -c 1 " + shlex.quote(host))
    return "done"
