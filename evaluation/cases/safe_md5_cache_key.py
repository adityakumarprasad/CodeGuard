import hashlib
import os

CACHE_DIR = "/tmp/page-cache"


def cache_path(url):
    return os.path.join(CACHE_DIR, hashlib.md5(url.encode()).hexdigest() + ".html")
