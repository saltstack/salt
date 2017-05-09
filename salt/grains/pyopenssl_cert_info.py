#!/usr/bin/python
# -*- coding: utf-8 -*-

import OpenSSL
import socket
from datetime import datetime


def get_cert_info():
    grains = {'cert': {}}

    context = OpenSSL.SSL.Context(OpenSSL.SSL.TLSv1_METHOD)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    connection = OpenSSL.SSL.Connection(context, s)
    connection.connect(("localhost", 443))

    connection.setblocking(1)

    print("Connected to ", connection.getpeername())
    print("Sate ", connection.state_string())

    try:
        connection.do_handshake()
    except OpenSSL.SSL.WantReadError:
        print("Timeout")
        quit()

    start = datetime.strftime(datetime.strptime(connection.get_peer_certificate().get_notAfter()[:-1], '%Y%m%d%H%M%S'), '%b %d %H:%M:%S %Y %Z')
    end = datetime.strftime(datetime.strptime(connection.get_peer_certificate().get_notBefore()[:-1], '%Y%m%d%H%M%S'), '%b %d %H:%M:%S %Y %Z')
    subject_components = []
    for x, y in connection.get_peer_certificate().get_subject().get_components():
        subject_components.append('/' + x + '=')
        subject_components.append(y)

    subject = "".join(subject_components)
    cn = subject_components[-1]
    expired = True if connection.get_peer_certificate().has_expired() == 1 else False
    fingerprint = connection.get_peer_certificate().digest('sha1')
    serial = connection.get_peer_certificate().get_serial_number()
    grains['cert']['start'] = start
    grains['cert']['end'] = end
    grains['cert']['subject'] = subject
    grains['cert']['cn'] = cn
    grains['cert']['expired'] = expired
    grains['cert']['fingerprint'] = fingerprint
    grains['cert']['serial'] = serial
    return grains
