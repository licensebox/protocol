#!/usr/bin/env python3
"""Update only the public contract pin and C++'s declared C release dependency."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("sdk",type=Path)
    parser.add_argument("contract",type=Path)
    parser.add_argument("--ref",required=True)
    parser.add_argument("--language",required=True,choices=["go","python","javascript","c","cpp"])
    args=parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}",args.ref):
        parser.error("contract ref must be a full commit SHA")
    actual=subprocess.check_output(["git","rev-parse","HEAD"],cwd=args.contract,text=True).strip()
    if actual!=args.ref:
        parser.error("contract checkout does not match requested commit")
    contract=json.loads((args.contract/"contract.json").read_text())
    if contract["protocol"]!=2 or not isinstance(contract["revision"],int) or contract["revision"]<1:
        parser.error("unsupported contract; implement and review the protocol transition first")
    reference=contract["reference_go"]
    if not re.fullmatch(r"v\d+\.\d+\.\d+",reference):
        parser.error("invalid Go reference release")
    lock={"repository":"licensebox/protocol","ref":args.ref,"protocol":contract["protocol"],
          "revision":contract["revision"],"reference_go":reference,
          "vectors_sha256":hashlib.sha256((args.contract/"vectors.json").read_bytes()).hexdigest()}
    (args.sdk/"protocol-lock.json").write_text(json.dumps(lock,indent=2)+"\n")
    if args.language=="cpp":
        dependency=contract["clients"]["c"]["release"]
        if not re.fullmatch(r"v\d+\.\d+\.\d+",dependency):
            parser.error("invalid C dependency release")
        (args.sdk/"c-version.cmake").write_text(f'set(LICENSEBOX_C_VERSION "{dependency}")\n')

if __name__=="__main__":main()
