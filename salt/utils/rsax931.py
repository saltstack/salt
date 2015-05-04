'''
Create and verify ANSI X9.31 RSA signatures using OpenSSL libcrypto
'''

from __future__ import absolute_import

from ctypes import CDLL, c_char_p, c_int, c_void_p, pointer, create_string_buffer

libcrypto = CDLL('libcrypto.so')

libcrypto.RSA_new.argtypes = ()
libcrypto.RSA_new.restype = c_void_p
libcrypto.RSA_free.argtypes = (c_void_p, )
libcrypto.RSA_size.argtype = (c_void_p)
libcrypto.BIO_new_mem_buf.argtypes = (c_char_p, c_int)
libcrypto.BIO_new_mem_buf.restype = c_void_p
libcrypto.BIO_free.argtypes = (c_void_p, )
libcrypto.PEM_read_bio_RSAPrivateKey.argtypes = (c_void_p, c_void_p, c_void_p, c_void_p)
libcrypto.PEM_read_bio_RSAPrivateKey.restype = c_void_p
libcrypto.PEM_read_bio_RSA_PUBKEY.argtypes = (c_void_p, c_void_p, c_void_p, c_void_p)
libcrypto.PEM_read_bio_RSA_PUBKEY.restype = c_void_p
libcrypto.RSA_private_encrypt.argtypes = (c_int, c_char_p, c_char_p, c_void_p, c_int)
libcrypto.RSA_public_decrypt.argtypes = (c_int, c_char_p, c_char_p, c_void_p, c_int)

libcrypto.OPENSSL_no_config()
libcrypto.OPENSSL_add_all_algorithms_noconf()

# openssl/rsa.h:#define RSA_X931_PADDING 5
RSA_X931_PADDING = 5

class RSAX931Signer:
    '''
    Create ANSI X9.31 RSA signatures using OpenSSL libcrypto
    '''
    def __init__(self, keydata):
        '''
        Init an RSAX931Signer instance

        :param str keydata: The RSA private key in PEM format
        '''
        self.__bio = libcrypto.BIO_new_mem_buf(keydata, len(keydata))
        self.__rsa = c_void_p(libcrypto.RSA_new())
        if not libcrypto.PEM_read_bio_RSAPrivateKey(self.__bio, pointer(self.__rsa), None, None):
            raise ValueError('invalid RSA private key')

    def __del__(self):
        libcrypto.BIO_free(self.__bio)
        libcrypto.RSA_free(self.__rsa)

    def sign(self, msg):
        '''
        Sign a message (digest) using the private key

        :param str msg: The message (digest) to sign
        :rtype: str
        :return: The signature, or an empty string if the encryption failed
        '''
        # Allocate a buffer large enough for the signature. Freed by ctypes.
        buf = create_string_buffer(libcrypto.RSA_size(self.__rsa))
        size = libcrypto.RSA_private_encrypt(len(msg), msg, buf, self.__rsa, RSA_X931_PADDING)
        if size < 0:
            raise ValueError('Unable to encrypt message')
        return buf[0:size]


class RSAX931Verifier:
    '''
    Verify ANSI X9.31 RSA signatures using OpenSSL libcrypto
    '''
    def __init__(self, pubdata):
        '''
        Init an RSAX931Verifier instance

        :param str pubdata: The RSA public key in PEM format
        '''
        self.__bio = libcrypto.BIO_new_mem_buf(pubdata, len(pubdata))
        self.__rsa = c_void_p(libcrypto.RSA_new())
        if not libcrypto.PEM_read_bio_RSA_PUBKEY(self.__bio, pointer(self.__rsa), None, None):
            raise ValueError('invalid RSA public key')

    def __del__(self):
        libcrypto.BIO_free(self.__bio)
        libcrypto.RSA_free(self.__rsa)

    def verify(self, signed):
        '''
        Recover the message (digest) from the signature using the public key

        :param str signed: The signature created with the private key
        :rtype: str
        :return: The message (digest) recovered from the signature, or an empty
            string if the decryption failed
        '''
        # Allocate a buffer large enough for the signature. Freed by ctypes.
        buf = create_string_buffer(libcrypto.RSA_size(self.__rsa))
        size = libcrypto.RSA_public_decrypt(len(signed), signed, buf, self.__rsa, RSA_X931_PADDING)
        if size < 0:
            raise ValueError('Unable to decrypt message')
        return buf[0:size]
