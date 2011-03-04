'''
The crypt module manages all of the cyptogophy functions for minions and
masters, encrypting and decrypting payloads, preparing messages, and
authenticating peers
'''

# Import python libs
import os
import tempfile
# Import M2Crypto libs
from M2Crypto import RSA
# Import zeromq libs
import zmq
# Import salt utils
import salt.utils
import salt.payload

class Auth(object):
    '''
    The Auth class provides the sequence for setting up communication with the
    master server from a minion.
    '''
    def __init__(self, opts):
        self.opts = opts
        self.rsa_path = os.path.join(self.opts['pki_dir'], 'minion.pem')

    def __foo_pass(self):
        '''
        used as a workaround for the no-passphrase issue in M2Crypto.RSA
        '''
        return 'foo'

    def get_priv_key(self):
        '''
        Retruns a private key object derived from the passed host key
        '''
        if not os.path.isfile(self.rsa_path):
            gen = RSA.gen_key(2048, 1)
            gen.save_key(self.rsa_path, callback=self.__foo_pass)
            pub_path = os.path.join(self.opts['pki_dir'], 'minion.pub')
            gen.save_pub_key(pub_path)
        key = RSA.load_key(self.rsa_path, callback=self.__foo_pass)
        return key

    def minion_sign_in_payload(self):
        '''
        Generates the payload used to autnenticate with the master server. This
        payload consists of the passed in id_ and the ssh public key to encrypt
        the AES key sent back form the master.
        '''
        payload = {}
        key = self.get_priv_key()
        tmp_pub = tempfile.mktemp()
        key.save_pub_key(tmp_pub)
        payload['id'] = self.opts['id']
        payload['pub'] = open(tmp_pub, 'r').read()
        return payload

    def decrypt_master_aes(self, enc_aes):
        '''
        This function is used to decrypt the aes seed phrase returned from the
        master server, the seed phrase is decrypted with the ssh rsa host key.
        Pass in the encrypted aes key.
        Returns the decrypted aes seed key, a string
        '''
        key = self.get_priv_key()
        return key.private_decrypt(enc_aes, 4)
    
    def verify_master(self, master_pub, token):
        '''
        Takes the master pubkey and compares it to the saved master pubkey,
        the token is encrypted with the master private key and must be
        decrypted sucessfully to verify that the master has been connected to.
        The token must decrypt with the public key, and it must say:
        'salty bacon'
        returns a bool
        '''
        tmp_pub = tempfile.mktemp()
        open(tmp_pub, 'w+').write(master_pub)
        m_pub_fn = os.path.join(self.opts['pki_dir'], 'master.pub')
        if os.path.isfile(m_pub_fn):
            local_master_pub = open(m_pub_fn).read()
            if not master_pub == local_master_pub:
                # This is not the last master we connected to
                return False
        else:
            open(m_pub_fn, 'w+').write(master_pub)
        pub = RSA.load_pub_key(tmp_pub)
        if pub.private_decrypt(token) == 'salty bacon':
            return True
        return False

    def sign_in(self):
        '''
        Send a sign in request to the master, sets the key information and
        returns a dict containing the master publish interface to bind to
        and the decrypted aes key for transport decryption.
        '''
        auth = {}
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.connect(self.opts['master_uri'])
        payload = salt.payload.package(self.minion_sign_in_payload())
        socket.send(payload)
        ret = salt.utils.unpackage(socket.recv())
        if not self.verify_master(ret['pub_key'], ret['token']):
            return auth
        auth['aes'] = self.decrypt_master_aes(ret['aes'])
        auth['master_publish_port'] = ret['master_publish_port']
        return auth

