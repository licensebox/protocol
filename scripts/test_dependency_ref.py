#!/usr/bin/env python3
import copy
import json
from pathlib import Path
import unittest
from dependency_ref import resolve

CONTRACT=json.loads((Path(__file__).resolve().parents[1]/'contract.json').read_text())
class DependencyRefs(unittest.TestCase):
    def test_release_and_fallback(self):
        for name in ('go','c','python'):
            contract=copy.deepcopy(CONTRACT)
            contract['clients'][name].pop('candidate_ref',None)
            self.assertRegex(resolve(contract,name),r'^v\d+\.\d+\.\d+$')
            self.assertEqual(resolve(contract,name,'v1.2.3'),'v1.2.3')
    def test_only_full_sha_candidate(self):
        for candidate in ('main','v0.1.0','../secrets','a'*39,'A'*40,False):
            contract=copy.deepcopy(CONTRACT);contract['clients']['c']['candidate_ref']=candidate
            with self.subTest(candidate=candidate),self.assertRaises(ValueError):resolve(contract,'c')
        contract=copy.deepcopy(CONTRACT);contract['clients']['c']['candidate_ref']='a'*40
        self.assertEqual(resolve(contract,'c','v0.1.0'),'a'*40)
    def test_fixed_public_repository(self):
        contract=copy.deepcopy(CONTRACT);contract['clients']['c']['repository']='other/private'
        with self.assertRaises(ValueError):resolve(contract,'c')
        with self.assertRaises(ValueError):resolve(CONTRACT,'private-server')
if __name__=='__main__':unittest.main()
