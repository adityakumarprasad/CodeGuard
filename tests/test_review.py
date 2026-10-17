from app.review import is_grounded


def test_grounded_issue_is_kept():
    lines = ["x = 1", "eval(user_input)"]
    assert is_grounded({"line": 2, "evidence": "eval(user_input)"}, lines)


def test_made_up_line_number_is_rejected():
    lines = ["x = 1", "eval(user_input)"]
    assert not is_grounded({"line": 99, "evidence": "eval(user_input)"}, lines)


def test_made_up_code_is_rejected():
    lines = ["x = 1", "eval(user_input)"]
    assert not is_grounded({"line": 1, "evidence": "os.system(cmd)"}, lines)
