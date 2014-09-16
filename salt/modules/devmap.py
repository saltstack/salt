log = logging.getLogger(__name__)

'''
Device-Mapper Multipath module
 CLI Example:
 .. code-block:: bash
     salt '*' devmap.multipath list
     salt '*' devmap.multipath flush mpath1
'''


def multipath():
    ret = {}
    if ret[0] == 'list':
        cmd = 'multipath -l'
    elif ret[0] == "flush":
        try:
            cmd = 'multipath -f {0}'.format(ret[1])
        except ValueError:
            return 'Error: No device to flush has been provided!'
    else:
        return 'Error: Unknown option provided!'
    return __salt__['cmd.run'](cmd).splitlines()