import salt.exceptions
import salt.utils
import datetime
import os


def _subject_to_dict(subject):
    _dict = {}
    for item in subject:
        for name, val in item.iteritems():
            _dict[name] = val

    return _dict


def _exts_to_list(exts):
    _list = []
    for item in exts:
        for name, data in item.iteritems():
            ext = {'name': name}
            for vals in data:
                for val_name, value in vals.iteritems():
                    ext[val_name] = value
        _list.append(ext)
    return _list
                  

def private_key_managed(name,
                        bits=2048,
                        new=False,
                        backup=False):
    '''
    Manage a private key
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    current_bits = 0
    if os.path.isfile(name):
        try:
            current_bits = __salt__['x509.get_private_key_size'](private_key=name)
            current = "{0} bit private key".format(current_bits)
        except salt.exceptions.SaltInvocationError:
            current = '{0} is not a valid Private Key.'.format(name)
    else:
        current = '{0} does not exist.'.format(name)

    if current_bits == bits and not new:
        ret['result'] = True
        ret['comment'] = 'The Private key is already in the correct state'
        return ret

    ret['changes'] = {
            'old': current,
            'new': "{0} bit private key".format(bits)}

    if __opts__['test'] == True:
        ret['comment'] = 'The Private Key "{0}" will be updated.'.format(name)
        return ret

    if os.path.isfile(name) and backup:
        bkroot = os.path.join(__opts__['cachedir'], 'file_backup')
        salt.utils.backup_minion(name, bkroot)

    ret['comment'] = __salt__['x509.create_private_key'](path=name, bits=bits)
    ret['result'] = True

    return ret


def csr_managed(name,
                public_key,
                subject=[],
                extensions=[],
                version=3,
                backup=False):
    '''
    Manage a CSR
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    subject = _subject_to_dict(subject)
    extensions = _exts_to_list(extensions)
    if os.path.isfile(name):
        try:
            current = __salt__['x509.read_csr'](csr=name)
        except salt.exceptions.SaltInvocationError:
            current = '{0} is not a valid CSR.'.format(name)
    else:
        current = '{0} does not exist.'.format(name)

    new_csr = __salt__['x509.create_csr'](text=True, subject=subject,
            public_key=public_key, extensions=extensions, version=version)
    new = __salt__['x509.read_csr'](csr=new_csr)

    if current == new:
        ret['result'] = True
        ret['comment'] = 'The CSR is already in the correct state'
        return ret

    ret['changes'] = {
            'old': current,
            'new': new,}

    if __opts__['test'] == True:
        ret['comment'] = 'The CSR {0} will be updated.'.format(name)

    if os.path.isfile(name) and backup:
        bkroot = os.path.join(__opts__['cachedir'], 'file_backup')
        salt.utils.backup_minion(name, bkroot)

    ret['comment'] = __salt__['x509.write_pem'](text=new_csr, path=name, pem_type="CERTIFICATE REQUEST")
    ret['result'] = True

    return ret


def certificate_managed(name,
                        signing_private_key,
                        subject=[],
                        signing_cert=None,
                        public_key=None,
                        csr=None,
                        extensions=[],
                        days_valid=365,
                        days_remaining=90,
                        version=3,
                        serial_number=None,
                        serial_bits=64,
                        algorithm='sha256',
                        backup=False,):
    '''
    Manage certificates
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    subject = _subject_to_dict(subject)
    extensions = _exts_to_list(extensions)

    current_days_remaining = 0
    current_comp = {}

    if os.path.isfile(name):
        try:
            current = __salt__['x509.read_certificate'](certificate=name)
            current_comp = current.copy()
            if not serial_number:
                current_comp.pop('Serial Number')
            current_comp.pop('Not Before')
            current_comp.pop('MD5 Finger Print')
            current_comp.pop('SHA1 Finger Print')
            current_comp.pop('SHA-256 Finger Print')
            current_notafter = current_comp.pop('Not After')
            current_days_remaining = (datetime.datetime.strptime(current_notafter, '%Y-%m-%d %H:%M:%S') -
                    datetime.datetime.now()).days
        except salt.exceptions.SaltInvocationError:
            current = '{0} is not a valid Certificate.'.format(name)
    else:
        current = '{0} does not exist.'.format(name)

    new_cert = __salt__['x509.create_certificate'](text=True, subject=subject,
            signing_private_key=signing_private_key, signing_cert=signing_cert,
            public_key=public_key, csr=csr, extensions=extensions,
            days_valid=days_valid, version=version,
            serial_number=serial_number, serial_bits=serial_bits,
            algorithm=algorithm)

    new = __salt__['x509.read_certificate'](certificate=new_cert)
    new_comp = new.copy()
    if not serial_number:
        new_comp.pop('Serial Number')
    new_comp.pop('Not Before')
    new_comp.pop('Not After')
    new_comp.pop('MD5 Finger Print')
    new_comp.pop('SHA1 Finger Print')
    new_comp.pop('SHA-256 Finger Print')

    if current_comp == new_comp and current_days_remaining > days_remaining:
        ret['result'] = True
        ret['comment'] = 'The certificate is already in the correct state'
        return ret

    ret['changes'] = {
            'old': current,
            'new': new,}

    if __opts__['test'] == True:
        ret['comment'] = 'The certificate {0} will be updated.'.format(name)
        return ret

    if os.path.isfile(name) and backup:
        bkroot = os.path.join(__opts__['cachedir'], 'file_backup')
        salt.utils.backup_minion(name, bkroot)

    ret['comment'] = __salt__['x509.write_pem'](text=new_cert, path=name, pem_type="CERTIFICATE")
    ret['result'] = True

    return ret
