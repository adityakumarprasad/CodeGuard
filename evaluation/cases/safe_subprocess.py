import subprocess


def disk_usage():
    return subprocess.run("df -h", shell=True, capture_output=True, text=True).stdout
