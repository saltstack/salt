# -*- coding: utf-8 -*-
'''
Tests to try out nacling. Potentially ephemeral

'''
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






if __name__ == "__main__":
    test()
