'''
Salt module to manage unix mounts and the fstab file
'''
# Import python libs
import os

def active():
    '''
    List the active mounts.

    CLI Example:
    salt '*' mount.active
    '''
    ret = {}
    for line in __salt__['cmd.run_stdout']('mount').split('\n'):
        comps = line.split()
        if not len(comps) == 6:
            # Invalid entry
            continue
        ret{comps[2]} = {'device': comps[0],
                         'fstype': comps[4],
                         'opts': comps[5][1:-1].split(',')}
    return ret

def fstab(config='/etc/fstab'):
    '''
    List the contents of the fstab

    CLI Example:
    salt '*' mount.fstab
    '''
    ret = {}
    if not os.path.isfile(config):
        return ret
    for line in open(config).readlines():
        if line.startswith('#'):
            # Commented
            continue
        if not line.strip():
            # Blank line
            continue
        comps = line.split()
        if not len(comps) == 6:
            # Invalid entry
            continue
        ret[comps[1]] = {'device': comps[0],
                         'fstype': comps[2],
                         'opts': comps[3].split(','),
                         'dump': comps[4],
                         'pass': comps[5]}
    return ret

def mount(name, device, mkmnt=False, fstype='', opts='defaults'):
    '''
    Mound a device

    CLI Example:
    salt '*' mount.mount /mnt/foo /dev/sdz1 True
    '''
    if not os.path.isfile(device):
        return False
    if not stat.S_ISBLK(os.stat(device).st_mode):
        return False
    if not os.path.exists(name) and mkmnt:
        os.makedirs(name)
    cmd = 'mount -o {0} {1} {2} '.format(opts, device, name)
    if fstype:
        cmd += ' -t {0}'.format(fstype)
    out = __salt__['cmd.run_all'](cmd)
    if out['retcode']:
        return out['stderr']
    return True
