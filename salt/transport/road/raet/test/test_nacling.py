# -*- coding: utf-8 -*-
'''
Tests to try out nacling. Potentially ephemeral

'''
import struct

from ioflo.base.odicting import odict
from salt.transport.road.raet import nacling


def test():
    print "Bob Signer"
    signerBob = nacling.Signer()
    print len(signerBob.keyhex),  signerBob.keyhex
    print len(signerBob.verhex), signerBob.verhex

    print "Pam Verifier"
    verferPam = nacling.Verifier(signerBob.verhex)
    print len(verferPam.keyhex), verferPam.keyhex

    print "Signed by Bod"
    msg = "Hello This is Bob, how are you Pam?"
    print len(msg), msg
    signature = signerBob.signature(msg)
    print len(signature), signature

    print "Verified by Pam"
    verified = verferPam.verify(signature, msg)
    print verified


    print "Bob Privateer"
    priverBob = nacling.Privateer()
    print len(priverBob.keyhex), priverBob.keyhex
    print len(priverBob.pubhex), priverBob.pubhex

    print "Bob Publican"
    pubberBob = nacling.Publican(priverBob.pubhex)
    print len(pubberBob.keyhex), pubberBob.keyhex

    print "Pam Privateer"
    priverPam = nacling.Privateer()
    print len(priverPam.keyhex), priverPam.keyhex
    print len(priverPam.pubhex), priverPam.pubhex

    print "Pam Publican"
    pubberPam = nacling.Publican(priverPam.pubhex)
    print len(pubberPam.keyhex), pubberPam.keyhex

    print "Encrypted by Bob private Pam public"
    msg = "Hello its me Bob, Did you get my last message Alice?"
    print len(msg),  msg

    cipher, nonce = priverBob.encrypt(msg, pubberPam.key)
    print "cipher"
    print len(cipher), cipher
    print "nonce"
    print len(nonce), nonce

    print "Decrypted by Pam private Bob public"
    msg = priverPam.decrypt(cipher, nonce, pubberBob.key)
    print len(msg), msg

    cipher, nonce = priverBob.encrypt(msg, pubberPam.keyhex)
    print "cipher"
    print len(cipher), cipher
    print "nonce"
    print len(nonce), nonce

    print "Decrypted by Pam private Bob public"
    msg = priverPam.decrypt(cipher, nonce, pubberBob.keyhex)
    print len(msg), msg

    #print "Decrypted by Pam private Bob public"
    #ciphernonce = cipher + nonce
    #msg = priverPam.decrypt(ciphernonce, None, pubberBob.key)
    #print len(msg), msg

    print "Blank"
    msg = "".rjust(64, '\x00')
    print len(msg), msg
    cipher, nonce = priverBob.encrypt(msg, pubberPam.keyhex)
    print "cipher"
    print len(cipher), cipher
    print "nonce"
    print len(nonce), nonce

    print "Cookie"
    fmt = '<64sLL64s'
    msg = struct.pack(fmt, pubberPam.keyhex, 45000, 63000, pubberBob.keyhex)
    print "Packed"
    print len(msg), msg
    cipher, nonce = priverBob.encrypt(msg, pubberPam.keyhex)
    print "cipher"
    print len(cipher), cipher
    print "nonce"
    print len(nonce), nonce

    print "Cookie again"
    fmt = '<64sLL64s'
    msg = struct.pack(fmt, pubberPam.keyhex, 1, 2, pubberBob.keyhex)
    print "Packed"
    print len(msg), msg
    cipher, nonce = priverBob.encrypt(msg, pubberPam.keyhex)
    print "cipher"
    print len(cipher), cipher
    print "nonce"
    print len(nonce), nonce

    print "Cookie more"
    fmt = '<64sLL24s'
    cookie = priverBob.nonce()
    msg = struct.pack(fmt, pubberPam.keyhex, 1, 2, cookie)
    print "Packed"
    print len(msg), msg
    cipher, nonce = priverBob.encrypt(msg, pubberPam.keyhex)
    print "cipher"
    print len(cipher), cipher
    print "nonce"
    print len(nonce), nonce


    print "Initiate"
    msg = priverBob.keyhex
    vcipher, vnonce = priverBob.encrypt(msg, pubberPam.keyhex)
    print "vcipher"
    print len(vcipher), vcipher
    print "vnonce"
    print len(nonce), nonce

    fqdn = "10.0.2.30".ljust(128, ' ')
    print "fqdn"
    print len(fqdn), fqdn
    fmt = '<64s80s24s128s'
    stuff = struct.pack(fmt, priverBob.keyhex,vcipher,vnonce,fqdn)
    print "stuff"
    print len(stuff), stuff

    cipher, nonce = priverBob.encrypt(stuff, pubberPam.keyhex)
    print "cipher"
    print len(cipher), cipher
    print "nonce"
    print len(nonce), nonce




if __name__ == "__main__":
    test()
