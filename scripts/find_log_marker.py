#!/usr/bin/env python3
"""Wait a bounded time for one application access record in Fluentd files."""

import argparse
import json
import re
import sys
import time
from pathlib import Path


CRI_LINE = re.compile(r"^\S+ (?:stdout|stderr) [FP] (.*)$")


def record_matches(line, request_id, version):
    line = line.rstrip("\r\n")
    if not line:
        return False
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        match = CRI_LINE.match(line)
        if not match:
            return False
        try:
            record = json.loads(match.group(1))
        except json.JSONDecodeError:
            return False

    if not isinstance(record, dict):
        return False
    for key in ("message", "log"):
        nested = record.get(key)
        if isinstance(nested, str):
            try:
                nested = json.loads(nested)
            except json.JSONDecodeError:
                continue
            if isinstance(nested, dict):
                record = nested
                break
    return (
        record.get("event") == "access"
        and record.get("request_id") == request_id
        and record.get("version") == version
    )


def find_marker(directory, request_id, version):
    for path in Path(directory).glob("trafficops*.log"):
        try:
            with path.open(encoding="utf-8") as records:
                if any(record_matches(line, request_id, version) for line in records):
                    return True
        except (OSError, UnicodeDecodeError):
            continue
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", default="/logs")
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--version", required=True, choices=("v1", "v2"))
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    if args.timeout <= 0 or args.timeout > 30:
        parser.error("--timeout must be greater than 0 and no more than 30 seconds")

    deadline = time.monotonic() + args.timeout
    while True:
        if find_marker(args.directory, args.request_id, args.version):
            print(f"Fluentd log verified: request_id={args.request_id} version={args.version}")
            return 0
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            print(
                f"ERROR: request_id={args.request_id} version={args.version} "
                f"was not found in Fluentd logs within {args.timeout:g}s",
                file=sys.stderr,
            )
            return 1
        time.sleep(min(1.0, remaining))


if __name__ == "__main__":
    raise SystemExit(main())
