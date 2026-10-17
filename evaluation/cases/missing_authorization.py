from flask import Flask, session

app = Flask(__name__)
USERS = {1: {"name": "alice", "is_admin": True}, 2: {"name": "bob", "is_admin": False}}


@app.route("/profile/<int:user_id>")
def profile(user_id):
    if "user_id" not in session:
        return "login required", 401
    return USERS[user_id]  # VULN: idor


@app.route("/admin/delete/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    USERS.pop(user_id, None)  # VULN: missing-authorization
    return "deleted"
