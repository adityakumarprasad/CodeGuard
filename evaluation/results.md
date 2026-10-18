# Evaluation results

Model: `gemini-3.5-flash-lite` · cases: 15 · time: 485s · LLM usage: {'api_calls': 43, 'cache_hits': 0, 'retries': 0, 'quota_exhausted': False}

| Metric | Semgrep alone | Semgrep + AI |
|---|---|---|
| Precision (findings that are real) | 83% | 95% |
| Recall (real bugs found) | 58% | 92% |
| False alarms | 3 | 1 |
| Fixes verified | - | 7/7 (100%) |

## Per case (real bugs found / false alarms)

| Case | Real bugs | Semgrep | Semgrep + AI | Fixes verified |
|---|---|---|---|---|
| code_injection.py | 1 | 1 / 0 | 1 / 0 | 1/1 |
| command_injection.py | 1 | 1 / 0 | 1 / 0 | 1/1 |
| debug_mode.py | 1 | 1 / 0 | 1 / 0 | 1/1 |
| hardcoded_secret.py | 1 | 0 / 0 | 1 / 0 | 0/0 |
| insecure_deserialization.py | 1 | 0 / 0 | 0 / 0 | 0/0 |
| missing_authorization.py | 2 | 0 / 0 | 2 / 0 | 0/0 |
| path_traversal.py | 1 | 0 / 0 | 1 / 0 | 0/0 |
| prompt_injection.py | 1 | 1 / 0 | 1 / 0 | 1/1 |
| safe_md5_cache_key.py | 0 | 0 / 1 | 0 / 0 | 0/0 |
| safe_shell_quote.py | 0 | 0 / 2 | 0 / 0 | 0/0 |
| safe_sql.py | 0 | 0 / 0 | 0 / 1 | 0/0 |
| safe_subprocess.py | 0 | 0 / 0 | 0 / 0 | 0/0 |
| sql_injection.py | 1 | 1 / 0 | 1 / 0 | 1/1 |
| unsafe_yaml.py | 1 | 1 / 0 | 1 / 0 | 1/1 |
| weak_hash.py | 1 | 1 / 0 | 1 / 0 | 1/1 |
