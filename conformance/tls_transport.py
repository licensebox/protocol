#!/usr/bin/env python3
"""Synthetic loopback TLS tests for native clients with CA-bundle support."""
import argparse
from datetime import datetime,timedelta,timezone
import ipaddress,json,ssl,subprocess,tempfile,threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from run import Handler,State,START,PUBLIC,HOST_A

def authority(name):
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,name)])
    now=datetime.now(timezone.utc)
    cert=(x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
          .public_key(key.public_key()).serial_number(x509.random_serial_number())
          .not_valid_before(now-timedelta(days=1)).not_valid_after(now+timedelta(days=1))
          .add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True)
          .sign(key,hashes.SHA256()))
    return key,cert

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--adapter',nargs=argparse.REMAINDER,required=True);args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='licensebox-tls-') as temporary:
        folder=Path(temporary);key,ca=authority('Synthetic Licensebox TLS CA')
        _,wrong_ca=authority('Wrong synthetic CA')
        for name,cert in [('ca.pem',ca),('wrong.pem',wrong_ca)]:
            (folder/name).write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        server_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        now=datetime.now(timezone.utc)
        cert=(x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Synthetic loopback server')]))
              .issuer_name(ca.subject).public_key(server_key.public_key()).serial_number(x509.random_serial_number())
              .not_valid_before(now-timedelta(hours=1)).not_valid_after(now+timedelta(hours=1))
              .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False)
              .sign(key,hashes.SHA256()))
        (folder/'server.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        (folder/'server.key').write_bytes(server_key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        (folder/'server.key').chmod(0o600)
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(folder/'server.pem',folder/'server.key')
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);state=State();server.state=state
        server.socket=context.wrap_socket(server.socket,server_side=True)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            def run(name,host,ca_bundle=None):
                request={'op':'require','product':'demo','keys':{'test-key':PUBLIC},'binding':HOST_A,'now':START,
                         'server':f'https://{host}:{server.server_port}','directory':str(folder/name)}
                if ca_bundle is not None:request['ca_bundle']=str(folder/ca_bundle)
                process=subprocess.run(args.adapter,input=json.dumps(request),text=True,capture_output=True,timeout=30)
                if process.returncode:raise RuntimeError(f'adapter failed: {process.stderr}')
                return json.loads(process.stdout)
            assert not run('untrusted','127.0.0.1')['ok'],'untrusted TLS server authorized access'
            assert not run('wrong-ca','127.0.0.1','wrong.pem')['ok'],'wrong CA authorized access'
            assert not run('wrong-host','localhost','ca.pem')['ok'],'hostname mismatch authorized access'
            assert state.calls==0,'unverified TLS reached the licensing API'
            trusted=run('trusted','127.0.0.1','ca.pem')
            assert trusted['ok'],f'trusted loopback TLS did not activate: {trusted}; API calls={state.calls}'
        finally:server.shutdown();server.server_close()
    print('PASS: untrusted CA, wrong CA and hostname mismatch refused; trusted TLS activation succeeds')

if __name__=='__main__':main()
