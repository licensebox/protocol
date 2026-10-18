#!/usr/bin/env python3
"""Shared MATLAB/Octave MEX regression for length-aware native ID strings."""
import argparse,json,subprocess
from run import binding
p=argparse.ArgumentParser();p.add_argument('--adapter',nargs=argparse.REMAINDER,required=True);args=p.parse_args()
raw='00112233445566778899aabbccddeeff'
def call(value):
 r={'op':'derive','product':'demo','source':'linux-machine-id','raw_id':value}
 result=subprocess.run(args.adapter,input=json.dumps(r),text=True,capture_output=True,timeout=60)
 if result.returncode:raise RuntimeError(result.stderr)
 return json.loads(result.stdout)
assert call(raw+'\0\0')=={'ok':True,'value':binding(raw)},'terminal NUL normalization differs'
answer=call(raw+'\0suffix')
assert not answer['ok'] and answer['error']=='identity_unavailable','embedded NUL truncated into valid identity'
print('PASS: terminal NUL normalization and embedded NUL rejection across MEX string conversion')
