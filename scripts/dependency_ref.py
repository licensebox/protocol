#!/usr/bin/env python3
"""Resolve a fixed public dependency to a release or an immutable CI candidate."""
import argparse
import json
from pathlib import Path
import re
from registry import registered

def resolve(contract, language, fallback=None):
    if language not in ("go", "c", "python"):
        raise ValueError("unsupported shared dependency")
    client = registered(contract, language)
    candidate = client.get("candidate_ref")
    if candidate is not None:
        if not isinstance(candidate, str) or not re.fullmatch(r"[0-9a-f]{40}", candidate):
            raise ValueError("candidate must be a full immutable commit")
        return candidate
    release = fallback if fallback is not None else (contract["reference_go"] if language == "go" else client["release"])
    if not isinstance(release, str) or not re.fullmatch(r"v\d+\.\d+\.\d+", release):
        raise ValueError("dependency must be a semantic release")
    return release

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("language", choices=("go", "c", "python"))
    parser.add_argument("fallback_file", nargs="?")
    args = parser.parse_args()
    contract = json.loads((Path(__file__).resolve().parents[1]/"contract.json").read_text())
    fallback = Path(args.fallback_file).read_text().strip() if args.fallback_file else None
    print(resolve(contract, args.language, fallback))
