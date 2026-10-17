import os
import sqlite3
from flask import Flask, request

app = Flask(__name__)


@app.route("/user")
def get_user():
    name = request.args.get("name")
    conn = sqlite3.connect("app.db")
    return {"rows": conn.execute(f"SELECT * FROM users WHERE name = '{name}'").fetchall()}


@app.route("/ping")
def ping():
    host = request.args.get("host", "")
    os.system("ping -c 1 " + host)
    return "done"


@app.route("/admin/reset", methods=["POST"])
def reset_database():
    os.remove("app.db")
    return "reset"
