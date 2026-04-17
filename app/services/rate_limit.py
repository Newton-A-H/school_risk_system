from collections import defaultdict, deque
from time import time

from flask import current_app, jsonify, render_template, request


REQUEST_BUCKETS = defaultdict(deque)


def check_rate_limit():
    endpoint = request.endpoint or ""
    if endpoint.startswith("static") or request.path in {"/health", "/healthz"}:
        return None

    window = int(current_app.config.get("RATE_LIMIT_WINDOW_SECONDS", 60))
    max_requests = int(current_app.config.get("RATE_LIMIT_MAX_REQUESTS", 180))
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "anonymous")
    bucket_key = f"{client_ip}:{endpoint}"

    now = time()
    bucket = REQUEST_BUCKETS[bucket_key]

    while bucket and now - bucket[0] >= window:
        bucket.popleft()

    if len(bucket) >= max_requests:
        message = "Too many requests were sent in a short time. Please wait a moment and try again."
        if request.path.startswith("/health"):
            return jsonify({"status": "rate_limited", "error": message}), 429
        return (
            render_template("errors/429.html", message=message),
            429,
            {"Content-Type": "text/html; charset=utf-8"},
        )

    bucket.append(now)
    return None
