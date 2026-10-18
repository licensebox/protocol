#!/usr/bin/env python3
"""Prepare a compatibility-only PR when stable SDK releases advance."""
import json
from pathlib import Path
import re
import subprocess
import tempfile

root=Path(__file__).resolve().parent.parent
path=root/"contract.json"
contract=json.loads(path.read_text())
changed=[]
for language,client in contract["clients"].items():
    repo=client["repository"]
    if repo not in {"licensebox/go","licensebox/python","licensebox/javascript","licensebox/c","licensebox/cpp"}:
        raise SystemExit("unexpected SDK repository")
    result=subprocess.run(["gh","api",f"repos/{repo}/releases/latest"],text=True,capture_output=True)
    if result.returncode:continue  # a first release may not exist yet
    release=json.loads(result.stdout)
    tag=release["tag_name"]
    if release["draft"] or release["prerelease"] or not re.fullmatch(r"v\d+\.\d+\.\d+",tag):continue
    numeric=lambda value:tuple(map(int,value[1:].split(".")))
    if numeric(tag)>numeric(client["release"]):
        changed.append(f"{language}: {client['release']} → {tag}")
        client["release"]=tag
        if language=="go":contract["reference_go"]=tag
if not changed:
    print("No new stable SDK releases");raise SystemExit(0)
contract["revision"]+=1
path.write_text(json.dumps(contract,indent=2)+"\n")
branch="automation/sdk-releases-"+str(contract["revision"])
def run(*args):return subprocess.check_output(args,cwd=root,text=True).strip()
if run("git","ls-remote","--heads","origin",branch):
    print("Compatibility update branch already exists");raise SystemExit(0)
run("git","config","user.name","github-actions[bot]")
run("git","config","user.email","41898282+github-actions[bot]@users.noreply.github.com")
run("git","switch","-c",branch)
run("git","add","contract.json")
run("git","commit","-m","Update SDK release compatibility map")
run("git","push","origin",f"HEAD:refs/heads/{branch}")
body="Update the compatibility map for new stable SDK releases.\n\n"+"\n".join("- "+item for item in changed)+"\n\nReview the corresponding shared scenarios and ports before merging.\n"
with tempfile.NamedTemporaryFile(mode="w",suffix=".md") as file:
    file.write(body);file.flush()
    print(run("gh","pr","create","--repo","licensebox/protocol","--head",branch,"--base","main","--title","Update SDK release compatibility map","--body-file",file.name))
run("gh","workflow","run","test.yml","--repo","licensebox/protocol","--ref",branch)
