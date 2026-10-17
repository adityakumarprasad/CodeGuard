from evaluation.run_eval import load_case, score


def test_load_case_hides_markers(tmp_path):
    case = tmp_path / "case.py"
    case.write_text("a = 1\neval(x)  # VULN: code-injection\n")
    code, truth = load_case(str(case))
    assert "VULN" not in code
    assert truth == {2}


def test_score_counts_hits_and_false_alarms():
    # bug on line 10; predictions on line 11 (hit, within tolerance) and 30 (false alarm)
    assert score([11, 30], {10}) == (1, 1, 1)
