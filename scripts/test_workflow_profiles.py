#!/usr/bin/env python3
"""Exercise the actual reusable-workflow capability code, including old locks."""
import contextlib
import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
LEGACY_REF='abb8a6f1ae4c4874b431ce38dc1d53ca3d6ce77d'
LEGACY={'protocol':2,'revision':1,'clients':{name:{'repository':'licensebox/'+name,'release':'v0.1.0'} for name in ('go','python','javascript','c','cpp')}}
CODE=textwrap.dedent(re.search(r"python3 -B - <<'PYCODE'\n(.*?)\n          PYCODE",(ROOT/'.github/workflows/sdk.yml').read_text(),re.S)[1])

class Profiles(unittest.TestCase):
    def invoke(self,language,contract=LEGACY,ref=LEGACY_REF,modern=False):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);(root/'protocol/scripts').mkdir(parents=True)
            (root/'protocol/contract.json').write_text(json.dumps(contract))
            if modern:shutil.copy(ROOT/'scripts/registry.py',root/'protocol/scripts/registry.py')
            with contextlib.chdir(root),patch.dict(os.environ,{'SDK_LANGUAGE':language,'CONTRACT_REF':ref,'GITHUB_OUTPUT':str(root/'output')}):
                # Separate process keeps imported registry modules isolated.
                result=subprocess.run(['python3','-B','-c',CODE],capture_output=True,text=True)
            return result.returncode,(root/'output').read_text() if (root/'output').exists() else ''
    def test_original_five_contract(self):
        for language in ('go','python','javascript','c','cpp'):
            with self.subTest(language=language):self.assertEqual(self.invoke(language),(0,'native=false\ncustom=false\n'))
    def test_unknown_legacy_ref_rejected(self):self.assertNotEqual(self.invoke('python',ref='a'*40)[0],0)
    def test_unknown_language_rejected(self):self.assertNotEqual(self.invoke('private-server')[0],0)
    def test_repository_substitution_rejected(self):
        contract=copy.deepcopy(LEGACY);contract['clients']['python']['repository']='other/python'
        self.assertNotEqual(self.invoke('python',contract)[0],0)
    def test_extra_client_rejected(self):
        contract=copy.deepcopy(LEGACY);contract['clients']['private-server']={'repository':'licensebox/private-server'}
        self.assertNotEqual(self.invoke('python',contract)[0],0)
    def test_legacy_capability_escalation_rejected(self):
        for key in ('native_c','custom_ci'):
            contract=copy.deepcopy(LEGACY);contract['clients']['python'][key]=True
            with self.subTest(key=key):self.assertNotEqual(self.invoke('python',contract)[0],0)
    def test_wrong_legacy_revision_rejected(self):
        contract=copy.deepcopy(LEGACY);contract['revision']=2
        self.assertNotEqual(self.invoke('python',contract)[0],0)
    def test_current_registry_profiles_preserved(self):
        contract=json.loads((ROOT/'contract.json').read_text())
        for language,expected in [('python','native=false\ncustom=false\n'),('rust','native=true\ncustom=false\n'),('wasm','native=false\ncustom=true\n')]:
            with self.subTest(language=language):self.assertEqual(self.invoke(language,contract,'b'*40,True),(0,expected))
        self.assertNotEqual(self.invoke('private-server',contract,'b'*40,True)[0],0)

if __name__=='__main__':unittest.main()
