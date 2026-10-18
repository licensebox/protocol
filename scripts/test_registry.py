import unittest
from registry import registered

class RegistryTest(unittest.TestCase):
    def test_only_approved_registered_repositories(self):
        self.assertEqual(registered({'clients':{'rust':{'repository':'licensebox/rust','native_c':True}}},'rust')['native_c'],True)
        for client in ({'repository':'licensebox/server'}, {'repository':'attacker/rust'}, {'repository':'licensebox/rust','native_c':'false'}):
            with self.assertRaises(ValueError): registered({'clients':{'rust':client}},'rust')
        with self.assertRaises(ValueError): registered({'clients':{}},'ruby')
        with self.assertRaises(ValueError): registered({'clients':{'server':{'repository':'licensebox/server'}}},'server')

if __name__=='__main__': unittest.main()
