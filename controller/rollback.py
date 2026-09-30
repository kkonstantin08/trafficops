import math


def evaluate_canary(snapshot, policy, previous_breaches, started_at, now):
    """Return observe/rollback/unknown using only fresh source sample timestamps."""
    required = ("requests", "errors", "sample_time", "target_up")
    try:
        values = {key: float(snapshot[key]) for key in required}
        started_at, now = float(started_at), float(now)
        window = float(policy["window_seconds"])
        minimum = int(policy["min_requests"])
        threshold = float(policy["error_threshold"])
        max_age = float(policy["max_sample_age_seconds"])
        consecutive = int(policy["required_breaches"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return {"state": "unknown", "breaches": 0, "reason": "invalid metrics or policy"}
    if not all(math.isfinite(value) for value in (*values.values(), started_at, now, window, threshold, max_age)):
        return {"state": "unknown", "breaches": 0, "reason": "non-finite metrics"}
    requests, errors, sample_time, target_up = (values[key] for key in required)
    if window <= 0 or minimum < 1 or not 0 <= threshold <= 1 or consecutive < 1:
        return {"state": "unknown", "breaches": 0, "reason": "invalid policy"}
    if now < started_at + window:
        return {"state": "unknown", "breaches": 0, "reason": "canary window is not complete"}
    if target_up != 1:
        return {"state": "unknown", "breaches": 0, "reason": "v2 target is down"}
    if sample_time < started_at or sample_time > now + 5 or now - sample_time > max_age:
        return {"state": "unknown", "breaches": 0, "reason": "source sample is stale or outside this canary"}
    if requests < minimum or requests <= 0 or errors < 0 or errors > requests:
        return {"state": "unknown", "breaches": 0, "reason": "insufficient or invalid v2 requests"}
    ratio = errors / requests
    breaches = previous_breaches + 1 if ratio > threshold else 0
    state = "rollback" if breaches >= consecutive else "observe"
    return {"state": state, "breaches": breaches, "reason": "5xx threshold exceeded" if ratio > threshold else "within error threshold",
            "requests": int(requests), "errors": int(errors), "error_ratio": ratio,
            "sample_time": sample_time, "target_up": True}
