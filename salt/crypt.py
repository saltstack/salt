'''
The crypt module manages all of the cyptogophy functions for minions and
masters, encrypting and decrypting payloads, preparing messages, and
authenticating peers
'''

# Import python libs
import os
# Import pycrypto libs
import Crypto.PublicKey.RSA as RSA

def prep_keys(keydir, name):
    '''
    Generate an rsa key pair and save it in the specified directory, return
    the rsa object.
    '''
    rsa = None
    if not os.path.exists(keydir):
        os.makedirs(keydir)
    key = os.path.join(keydir, name)
    if os.path.isfile(key):
        # The key exists, load it and return it
        rsa = RSA.importKey(open(key, 'r').read())
        if not os.path.isfile(key + '.pub'):
            open(key + '.pub', 'w+').write(rsa.publickey().exportKey())
    else:
        # The key needs to be generated and saved
        rsa = RSA.generate(1024)
        open(key, 'w+').write(rsa.exportKey())
        open(key + '.pub', 'w+').write(rsa.publickey().exportKey())

    return rsa
