#!/usr/bin/env python3
"""Update only the public contract pin and C++'s declared C release dependency."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from registry import registered

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("sdk",type=Path)
    parser.add_argument("contract",type=Path)
    parser.add_argument("--ref",required=True)
    parser.add_argument("--language",required=True)
    parser.add_argument("--preview",action="store_true")
    args=parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}",args.ref):
        parser.error("contract ref must be a full commit SHA")
    actual=subprocess.check_output(["git","rev-parse","HEAD"],cwd=args.contract,text=True).strip()
    if actual!=args.ref:
        parser.error("contract checkout does not match requested commit")
    contract=json.loads((args.contract/"contract.json").read_text())
    if contract["protocol"]!=2 or not isinstance(contract["revision"],int) or contract["revision"]<1:
        parser.error("unsupported contract; implement and review the protocol transition first")
    client=registered(contract,args.language,allow_preview=args.preview)
    if args.preview and (args.language!="wolfram" or args.language not in contract.get("previews",{})):
        parser.error("only the declared Wolfram source preview can use bridge-only validation")
    reference=contract["reference_go"]
    if not re.fullmatch(r"v\d+\.\d+\.\d+",reference):
        parser.error("invalid Go reference release")
    lock={"repository":"licensebox/protocol","ref":args.ref,"protocol":contract["protocol"],
          "revision":contract["revision"],"reference_go":reference,
          "validation_profile":"bridge-only-unvalidated" if args.preview else "linux-native",
          "vectors_sha256":hashlib.sha256((args.contract/"vectors.json").read_bytes()).hexdigest()}
    (args.sdk/"protocol-lock.json").write_text(json.dumps(lock,indent=2)+"\n")
    if client.get("native_c",False):
        dependency=contract["clients"]["c"]["release"]
        if not re.fullmatch(r"v\d+\.\d+\.\d+",dependency):
            parser.error("invalid C dependency release")
        (args.sdk/"native-version.txt").write_text(dependency+"\n")
    if args.language=="wasm":
        python_release=contract["clients"]["python"]["release"]
        runtime=client["wasmtime_version"]
        if not re.fullmatch(r"v\d+\.\d+\.\d+",python_release) or not re.fullmatch(r"\d+\.\d+\.\d+",runtime):
            parser.error("invalid Wasm host dependency release")
        (args.sdk/"host-dependencies.txt").write_text(f"wasmtime=={runtime}\nlicensebox @ git+https://github.com/licensebox/python.git@{python_release}\n")
    if args.language=="cpp":
        dependency=contract["clients"]["c"]["release"]
        if not re.fullmatch(r"v\d+\.\d+\.\d+",dependency):
            parser.error("invalid C dependency release")
        (args.sdk/"c-version.cmake").write_text(f'set(LICENSEBOX_C_VERSION "{dependency}")\n')

if __name__=="__main__":main()
