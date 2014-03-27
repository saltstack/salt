import logging

log = logging.getLogger(__name__)


def __virtual__():
    return 'openssl'


def _get_subj(CN, **kwargs):
    fields = ['CN=' + CN]
    map = {
        'C': 'country',
        'L': 'city',
        'O': 'company'
    }

    for var, field in map.items():
        if field in kwargs:
            fields.append('{0}={1}'.format(var, kwargs[field]))

    subj = '/' + '/'.join(fields)

    return subj


def generate(file, **kwargs):
    '''
    Generate a private key that can be used to request a certificate.
    '''
    algo = kwargs.pop('algorithm', 'RSA')
    len = kwargs.pop('length', 4096)

    if algo not in ['RSA', 'DSA']:
        return False

    if algo == 'RSA':
        opts = 'rsa_keygen_bits:{0}'.format(len)
    elif algo == 'DSA':
        opts = 'dsa_paramgen_bits:{0}'.format(len)

    cmd = "openssl genpkey -algorithm {0} -out {1} -pkeyopt {2}".format(
        algo, file, opts
    )
    out = __salt__['cmd.run'](cmd)
    return cmd + "\n" + out


def gen_req(file, req_file, CN, **kwargs):
    '''
    Generate a csr (certificate signing request) file to be able to get a
    signed certificate from a certificate authority.
    '''
    subj = _get_subj(CN, **kwargs)
    cmd = "openssl req -new -key {0} -subj '{1}' -out {2}".format(
        file, subj, req_file
    )
    out = __salt__['cmd.run'](cmd)
    # TODO: Error handling...
    return cmd + "\n" + out


def gen_pem(file, private_key, certificate):
    '''
    Merge a certificate file and a private key file into a single pem file.
    '''
    cmd = '{0} {1} > {2}'.format(private_key, certificate, file)
    # TODO: Check for existence of file first.
    out = __salt__['cmd.run'](cmd)
    return out


def sign(config, csr, crt, passfile=None):
    '''
    Create a certificate based on a certificate signing request. Optionally
    accepts a passfile which contains the password for the certificate
    authority specified in the config file.
    '''
    if passfile:
        passfile = '-passin file:{0}'.format(passfile)
    cmd = 'openssl ca -config {0} -batch -in {1} -out {2} {3}'.format(
        config, csr, crt, passfile
    )
    out = __salt__['cmd.run'](cmd)
    return out
