# -*- coding: utf-8 -*-
'''
Tests to try out nacling. Potentially ephemeral

'''
# pylint: skip-file
import struct

from ioflo.base.odicting import odict
from salt.transport.road.raet import nacling


def test():
    print "Bob Signer"
    signerBob = nacling.Signer()
    print len(signerBob.keyhex), signerBob.keyhex
    print len(signerBob.keyraw), signerBob.keyraw
    print len(signerBob.verhex), signerBob.verhex
    print len(signerBob.verraw), signerBob.verraw

    print "Pam Verifier"
    verferPam = nacling.Verifier(signerBob.verhex)
    print len(verferPam.keyhex), verferPam.keyhex
    print len(verferPam.keyraw), verferPam.keyraw

    print "Signed by Bod"
    msg = "Hello This is Bob, how are you Pam?"
    print len(msg), msg
    signature = signerBob.signature(msg)
    print len(signature), signature

    print "Verified by Pam"
    verified = verferPam.verify(signature, msg)
    print verified

    print "Pam Verifier"
    verferPam = nacling.Verifier(signerBob.verraw)
    print len(verferPam.keyhex), verferPam.keyhex
    print len(verferPam.keyraw), verferPam.keyraw

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
    print len(priverBob.keyraw), priverBob.keyraw
    print len(priverBob.pubhex), priverBob.pubhex
    print len(priverBob.pubraw), priverBob.pubraw

    print "Bob Publican"
    pubberBob = nacling.Publican(priverBob.pubhex)
    print len(pubberBob.keyhex), pubberBob.keyhex
    print len(pubberBob.keyraw), pubberBob.keyraw

    print "Pam Privateer"
    priverPam = nacling.Privateer()
    print len(priverPam.keyhex), priverPam.keyhex
    print len(priverPam.keyraw), priverPam.keyraw
    print len(priverPam.pubhex), priverPam.pubhex
    print len(priverPam.pubraw), priverPam.pubraw

    print "Pam Publican"
    pubberPam = nacling.Publican(priverPam.pubhex)
    print len(pubberPam.keyhex), pubberPam.keyhex
    print len(pubberPam.keyraw), pubberPam.keyraw

    print "Encrypted by Bob private Pam public key object"
    msg = "Hello its me Bob, Did you get my last message Alice?"
    print len(msg),  msg

    cipher, nonce = priverBob.encrypt(msg, pubberPam.key)
    print "cipher"
    print len(cipher), cipher
    print "nonce"
    print len(nonce), nonce

    print "Decrypted by Pam private Bob public key object"
    msg = priverPam.decrypt(cipher, nonce, pubberBob.key)
    print len(msg), msg

    cipher, nonce = priverBob.encrypt(msg, pubberPam.keyhex)
    print "cipher"
    print len(cipher), cipher
    print "nonce"
    print len(nonce), nonce

    print "Decrypted by Pam private Bob public keyhex "
    msg = priverPam.decrypt(cipher, nonce, pubberBob.keyhex)
    print len(msg), msg

    cipher, nonce = priverBob.encrypt(msg, pubberPam.keyraw)
    print "cipher"
    print len(cipher), cipher
    print "nonce"
    print len(nonce), nonce

    print "Decrypted by Pam private Bob public keyraw"
    msg = priverPam.decrypt(cipher, nonce, pubberBob.keyraw)
    print len(msg), msg

    print "Encrypted by Bob private Pam public key aw"
    msg = "Hello its me Bob, Did you get my last message Alice?"
    print len(msg),  msg

    cipher, nonce = priverBob.encrypt(msg, pubberPam.keyraw)
    print "cipher"
    print len(cipher), cipher
    print "nonce"
    print len(nonce), nonce

    print "Decrypted by Pam private Bob public keyraw"
    msg = priverPam.decrypt(cipher, nonce, pubberBob.keyraw)
    print len(msg), msg

    print "Blank"
    msg = "".rjust(64, '\x00')
    print len(msg), msg
    cipher, nonce = priverBob.encrypt(msg, pubberPam.keyhex)
    print "cipher"
    print len(cipher), cipher
    print "nonce"
    print len(nonce), nonce

    print "Cookie"
    fmt = '<32sLL32s'
    msg = struct.pack(fmt, pubberPam.keyraw, 45000, 63000, pubberBob.keyraw)
    print "Packed"
    print len(msg), msg
    cipher, nonce = priverBob.encrypt(msg, pubberPam.keyhex)
    print "cipher"
    print len(cipher), cipher
    print "nonce"
    print len(nonce), nonce

    print "Cookie again"
    fmt = '<32sLL32s'
    msg = struct.pack(fmt, pubberPam.keyraw, 1, 2, pubberBob.keyraw)
    print "Packed"
    print len(msg), msg
    cipher, nonce = priverBob.encrypt(msg, pubberPam.keyhex)
    print "cipher"
    print len(cipher), cipher
    print "nonce"
    print len(nonce), nonce

    print "Cookie Good"
    fmt = '<32sLL24s'
    cookie = priverBob.nonce()
    msg = struct.pack(fmt, pubberPam.keyraw, 1, 2, cookie)
    print "Packed"
    print len(msg), msg
    cipher, nonce = priverBob.encrypt(msg, pubberPam.keyhex)
    print "cipher"
    print len(cipher), cipher
    print "nonce"
    print len(nonce), nonce


    print "Initiate"
    msg = priverBob.keyraw
    vcipher, vnonce = priverBob.encrypt(msg, pubberPam.key)
    print "vcipher"
    print len(vcipher), vcipher
    print "vnonce"
    print len(nonce), nonce

    fqdn = "10.0.2.30".ljust(128, ' ')
    print "fqdn"
    print len(fqdn), fqdn
    fmt = '<32s48s24s128s'
    stuff = struct.pack(fmt, priverBob.keyraw,vcipher,vnonce,fqdn)
    print "stuff"
    print len(stuff), stuff

    cipher, nonce = priverBob.encrypt(stuff, pubberPam.keyhex)
    print "cipher"
    print len(cipher), cipher
    print "nonce"
    print len(nonce), nonce




if __name__ == "__main__":
    test()
