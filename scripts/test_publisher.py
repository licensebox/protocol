"""Publisher startup must preserve the metadata-only clean-worktree guard."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class PublisherStartupTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='licensebox-publisher-')
        self.root=Path(self.temp.name)
        scripts=self.root/'.github/scripts';scripts.mkdir(parents=True)
        for name in ('open_sync_pr.py','registry.py'):
            shutil.copy(Path(__file__).with_name(name),scripts/name)
        (self.root/'protocol-lock.json').write_text(json.dumps({'repository':'licensebox/protocol','ref':'a'*40,'revision':1})+'\n')
        subprocess.run(['git','init','-q'],cwd=self.root,check=True)
        subprocess.run(['git','config','core.excludesFile',os.devnull],cwd=self.root,check=True)
        subprocess.run(['git','add','.'],cwd=self.root,check=True)
        self.env=dict(os.environ,GITHUB_REPOSITORY='licensebox/fortran')
        self.env.pop('PYTHONDONTWRITEBYTECODE',None)
        self.env.pop('PYTHONPYCACHEPREFIX',None)
        self.env.pop('GH_TOKEN',None);self.env.pop('GITHUB_TOKEN',None)
    def tearDown(self):self.temp.cleanup()
    def publisher(self,bytecode_disabled=True):
        command=[sys.executable]+(['-B'] if bytecode_disabled else [])+['.github/scripts/open_sync_pr.py']
        return subprocess.run(command,cwd=self.root,env=self.env,text=True,capture_output=True,timeout=15)
    def test_noop_publisher_with_B_does_not_create_untracked_files(self):
        result=self.publisher()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.strip(),'Already current')
        files=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=self.root,text=True)
        self.assertEqual(files,'')
    def test_plain_python_demonstrates_the_import_bytecode_regression(self):
        result=self.publisher(False)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('unexpected untracked files',result.stderr)
        self.assertTrue(list((self.root/'.github/scripts/__pycache__').glob('registry*.pyc')))
    def test_guard_still_refuses_unexpected_files(self):
        (self.root/'unexpected.txt').write_text('synthetic test only\n')
        result=self.publisher()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('unexpected untracked files',result.stderr)
    def test_guard_still_refuses_source_edits(self):
        path=self.root/'.github/scripts/registry.py'
        path.write_text(path.read_text()+'\n# unexpected source edit\n')
        result=self.publisher()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('unexpected tracked changes',result.stderr)


if __name__=='__main__':unittest.main()
