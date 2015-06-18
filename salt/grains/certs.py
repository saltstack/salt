#!/usr/bin/python
import salt.log
import salt.utils
import salt.utils.network
import salt.modules.cmdmod
import re
import subprocess
from datetime import datetime


def get_cert_info():
    grains = {}
    grains['cert'] = {}
    p1 = subprocess.Popen(['echo'], stdout=subprocess.PIPE)
    p2 = subprocess.Popen(['openssl', 's_client', '-connect', 'localhost:443'], stdin=p1.stdout, stdout=subprocess.PIPE)
    p3 = subprocess.Popen(['openssl', 'x509', '-noout', '-startdate'], stdin=p2.stdout, stdout=subprocess.PIPE)
    out = p3.communicate()
    print(len(out[0]))
    startdate = out[0].split('=')[1] if len(out[0]) > 0 else ''
    grains['cert']['start'] = startdate
    p1 = subprocess.Popen(['echo'], stdout=subprocess.PIPE)
    p2 = subprocess.Popen(['openssl', 's_client', '-connect', 'localhost:443'], stdin=p1.stdout, stdout=subprocess.PIPE)
    p3 = subprocess.Popen(['openssl', 'x509', '-noout', '-enddate'], stdin=p2.stdout, stdout=subprocess.PIPE)
    out = p3.communicate()
    enddate = out[0].split('=')[1] if len(out[0]) > 0 else ''
    grains['cert']['end'] = enddate
    p1 = subprocess.Popen(['echo'], stdout=subprocess.PIPE)
    p2 = subprocess.Popen(['openssl', 's_client', '-connect', 'localhost:443'], stdin=p1.stdout, stdout=subprocess.PIPE)
    p3 = subprocess.Popen(['openssl', 'x509', '-noout', '-fingerprint'], stdin=p2.stdout, stdout=subprocess.PIPE)
    out = p3.communicate()
    fingerprint = out[0].split('=')[1] if len(out[0]) > 0 else ''
    grains['cert']['fingerprint'] = fingerprint
    p1 = subprocess.Popen(['echo'], stdout=subprocess.PIPE)
    p2 = subprocess.Popen(['openssl', 's_client', '-connect', 'localhost:443'], stdin=p1.stdout, stdout=subprocess.PIPE)
    p3 = subprocess.Popen(['openssl', 'x509', '-noout', '-subject'], stdin=p2.stdout, stdout=subprocess.PIPE)
    out = p3.communicate()
    subject = out[0].split('subject=')[1] if len(out[0]) > 0 else ''
    grains['cert']['subject'] = subject
    p1 = subprocess.Popen(['echo'], stdout=subprocess.PIPE)
    p2 = subprocess.Popen(['openssl', 's_client', '-connect', 'localhost:443'], stdin=p1.stdout, stdout=subprocess.PIPE)
    p3 = subprocess.Popen(['openssl', 'x509', '-noout', '-serial'], stdin=p2.stdout, stdout=subprocess.PIPE)
    out = p3.communicate()
    serial = out[0].split('=')[1] if len(out[0]) > 0 else ''
    grains['cert']['serial'] = serial
    p1 = subprocess.Popen(['echo'], stdout=subprocess.PIPE)
    p2 = subprocess.Popen(['openssl', 's_client', '-connect', 'localhost:443'], stdin=p1.stdout, stdout=subprocess.PIPE)
    p3 = subprocess.Popen(['openssl', 'x509', '-noout', '-subject'], stdin=p2.stdout, stdout=subprocess.PIPE)
    out = p3.communicate()
    cn = out[0].split('=')[-1] if len(out[0]) > 0 else ''
    grains['cert']['cn'] = cn
    p1 = subprocess.Popen(['echo'], stdout=subprocess.PIPE)
    p2 = subprocess.Popen(['openssl', 's_client', '-connect', 'localhost:443'], stdin=p1.stdout, stdout=subprocess.PIPE)
    p3 = subprocess.Popen(['openssl', 'x509', '-noout', '-enddate'], stdin=p2.stdout, stdout=subprocess.PIPE)
    out = p3.communicate()
    enddate = out[0].split('=')[1] if len(out[0]) > 0 else ''
    print("enddate: ", enddate)
    if enddate != '':
        cert_end_date = datetime.strptime(enddate.strip(), '%b %d %H:%M:%S %Y %Z').date()
        now = datetime.now().date()
        base = datetime(1970, 1, 1)
        base_date = base.date()
        cert_end_days = (cert_end_date - base_date).days
        now_days = (now - base_date).days
        expired = True if now_days > cert_end_days else False
        grains['cert']['expired'] = expired
    return grains
