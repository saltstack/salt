import salt.exceptions
import salt.utils
import datetime
import os


def private_key_managed(name,
                        bits=2048,
                        new=False,
                        backup=False):
    '''
    Manage a private key
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    current = {'bits': 0}
    if os.path.isfile(name):
        try:
            current['bits'] = __salt__['x509.get_private_key_size'](private_key=name)
        except ValueError:
            current['comment'] = '{0} is not a valid Private Key.'.format(name)
    else:
        current['comment'] = '{0} does not exist and will be created.'.format(name)

    if current['bits'] == bits and not new:
        ret['result'] = True
        ret['comment'] = 'The Private key is already in the correct state'
        return ret

    ret['changes'] = {
            'old': current,
            'new': {'bits': bits}}

    if __opts__['test'] == True:
        ret['comment'] = 'The Private Key "{0}" will be updated.'.format(name)
        return ret

    if backup:
        bkroot = os.path.join(__opts__['cachedir'], 'file_backup')
        salt.utils.backup_minion(name, bkroot)

    ret['comment'] = __salt__['x509.create_private_key'](path=name, bits=bits)
    ret['result'] = True

    return ret


def certificate_managed(name,
                        subject,
                        signing_private_key,
                        signing_cert=None,
                        public_key=None,
                        extensions=None,
                        days_valid=365,
                        days_remaining=90,
                        version=3,
                        serial_number=None,
                        serial_bits=64,
                        algorithm='sha256',
                        backup=False,):
    # delete notbefore notafter serial and fingerprint fields
    # then compare read_certificate
    return None
