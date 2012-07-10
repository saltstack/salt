'''
Manages configuration files via augeas
'''


def __virtual__():
    ''' Only run this module if the augeas python module is installed '''
    try:
        from augeas import Augeas
        _ = Augeas
    except ImportError:
        return False
    else:
        return "augeas"


def _recurmatch(path, aug):
    '''
    recursive generator providing the infrastructure for
    augtools print behaviour.

    This function is based on test_augeas.py from
    Harald Hoyer <harald@redhat.com>  in the python-augeas
    repository
    '''
    if path:
        clean_path = path.rstrip('/*')
        yield (clean_path, aug.get(path))

        for i in aug.match(clean_path + "/*"):
            i = i.replace('!', '\!')  # escape some dirs
            for x in _recurmatch(i, aug):
                yield x


def _lstrip_word(string, prefix):
    '''
    Return a copy of the string after the specified prefix was removed
    from the beginning of the string
    '''

    if string.startswith(prefix):
        return string[len(prefix):]
    return string


def get(path, value=''):
    '''
    Get a value for a specific augeas path

    CLI Example::

        salt '*' augeas.get /files/etc/hosts/1/ ipaddr
    '''

    from augeas import Augeas
    aug = Augeas()

    ret = {}

    path = path.rstrip('/')
    if value:
        path += "/{0}".format(value.strip('/'))

    try:
        _match = aug.match(path)
    except RuntimeError as err:
        return {'error': str(err)}

    if _match:
        ret[path] = aug.get(path)
    else:
        ret[path] = ''  # node does not exist

    return ret


def setvalue(*args):
    '''
    Set a value for a specific augeas path

    CLI Example::

        salt '*' augeas.setvalue /files/etc/hosts/1/canonical localhost

    This will set the first entry in /etc/hosts to localhost

    CLI Example::

        salt '*' augeas.setvalue /files/etc/hosts/01/ipaddr 192.168.1.1 \\
                                 /files/etc/hosts/01/canonical test

    Adds a new host to /etc/hosts the ip address 192.168.1.1 and hostname test

    CLI Example::

        salt '*' augeas.setvalue prefix=/files/etc/sudoers/ \\
                 "spec[user = '%wheel']/user" "%wheel" \\
                 "spec[user = '%wheel']/host_group/host" 'ALL' \\
                 "spec[user = '%wheel']/host_group/command[1]" 'ALL' \\
                 "spec[user = '%wheel']/host_group/command[1]/tag" 'PASSWD' \\
                 "spec[user = '%wheel']/host_group/command[2]" '/usr/bin/apt-get' \\
                 "spec[user = '%wheel']/host_group/command[2]/tag" NOPASSWD

    Ensures that the following line is present in /etc/sudoers::

        %wheel ALL = PASSWD : ALL , NOPASSWD : /usr/bin/apt-get , /usr/bin/aptitude
    '''


    from augeas import Augeas
    aug = Augeas()

    ret = {'retval': False}

    prefix = None


    tuples = filter(lambda x: not x.startswith('prefix='), args)
    prefix = filter(lambda x: x.startswith('prefix='), args)
    if prefix:
        prefix = prefix[0].split('=', 1)[1]

    if len(tuples) % 2 != 0:
        return ret  # ensure we have multiple of twos

    tuple_iter = iter(tuples)

    for path, value in zip(tuple_iter, tuple_iter):
        target_path = path
        if prefix:
            target_path = "{0}/{1}".format(prefix.rstrip('/'), path.lstrip('/'))
        try:
            aug.set(target_path, str(value))
        except ValueError as err:
            ret['error'] = "Multiple values: " + str(err)

    try:
        aug.save()
        ret['retval'] = True
    except IOError as err:
        ret['error'] = str(err)
    return ret


def match(path, value=''):
    '''
    Get matches for path expression

    CLI Example::

        salt '*' augeas.match /files/etc/services/service-name ssh
    '''

    from augeas import Augeas
    aug = Augeas()

    ret = {}

    try:
        matches = aug.match(path)
    except RuntimeError:
        return ret

    for _match in matches:
        if value and aug.get(_match) == value:
            ret[_match] = value
        elif not value:
            ret[_match] = aug.get(_match)
    return ret


def remove(path):
    '''
    Get matches for path expression

    CLI Example::

        salt '*' augeas.remove /files/etc/sysctl.conf/net.ipv4.conf.all.log_martians
    '''
    from augeas import Augeas
    aug = Augeas()

    ret = {'retval': False}
    try:
        count = aug.remove(path)
        aug.save()
        if count == -1:
            ret['error'] = 'Invalid node'
        else:
            ret['retval'] = True
    except (RuntimeError, IOError) as err:
        ret['error'] = str(err)

    ret['count'] = count

    return ret


def ls(path):
    '''
    List the direct children of a node

    CLI Example::

        salt '*' augeas.ls /files/etc/passwd
    '''

    def _match(path):
        ''' Internal match function '''
        try:
            matches = aug.match(path)
        except RuntimeError:
            return {}

        ret = {}
        for _ma in matches:
            ret[_ma] = aug.get(_ma)
        return ret

    from augeas import Augeas
    aug = Augeas()

    path = path.rstrip('/') + '/'
    match_path = path + '*'

    matches = _match(match_path)
    ret = {}

    for key, value in matches.iteritems():
        name = _lstrip_word(key, path)
        if _match(key + '/*'):
            ret[name + '/'] = value  # has sub nodes, e.g. directory
        else:
            ret[name] = value
    return ret


def tree(path):

    '''
    Returns recursively the complete tree of a node

    CLI Example::

        salt '*' augeas.tree /files/etc/
    '''

    from augeas import Augeas
    aug = Augeas()

    path = path.rstrip('/') + '/'
    match_path = path
    return dict([i for i in _recurmatch(match_path, aug)])
