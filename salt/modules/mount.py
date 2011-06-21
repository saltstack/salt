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
        ret[comps[2]] = {'device': comps[0],
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

def rm_fstab(name, config='/etc/fstab'):
    '''
    Remove the mount point from the fstab

    CLI Example:
    salt '*' /mnt/foo
    '''
    contents = fstab(config)
    if not contents.has_key(name):
        return True
    # The entry is present, get rid of it
    

def set_fstab(
        name,
        device,
        fstype,
        opts='defaults',
        dump=0,
        pass_num=0,
        config='/etc/fstab',
        ):
    '''
    Verify that this mount is represented in the fstab, chage the mount point
    to match the data passed, or add the mount if it is not present.

    CLI Example:
    salt '*' mount.set_fstab /mnt/foo /dev/sdz1 ext4
    '''
    # Fix the opts type if it is a list
    if type(opts) == type(list()):
        opts = ','.join(opts)
    lines = []
    change = False
    present = False
    if not os.path.isfile(config):
        return False
    for line in open(config).readlines():
        if line.startswith('#'):
            # Commented
            lines.append(line)
            continue
        if not line.strip():
            # Blank line
            lines.append(line)
            continue
        comps = line.split()
        if not len(comps) == 6:
            # Invalid entry
            lines.append(line)
            continue
        if comps[1] == name:
            # check to see if there are changes and fix them if there are
            present = True
            if comps[0] != device:
                change = True
                comps[0] = device
            if comps[2] != fstype:
                change = True
                comps[2] = fstype
            if comps[3] != opts:
                change = True
                comps[3] = opts
            if comps[4] != str(dump):
                change = True
                comps[4] = str(dump)
            if comps[5] != str(pass_num):
                change = True
                comps[5] = str(pass_num)
            if change:
                log.debug('fstab entry for mount point {0} is being updated'.format(name))
                newline = '{0}\t\t{1}\t{2}\t{3}\t{4} {5}'.format(
                        name,
                        device,
                        fstype,
                        opts,
                        dump,
                        pass_num)
                lines.append(newline)
    if not change and not present:
        # The entry is new, add it to the end of the fstab
        newline = '{0}\t\t{1}\t{2}\t{3}\t{4} {5}'.format(
                name,
                device,
                fstype,
                opts,
                dump,
                pass_num)
        lines.append(newline)
        open(config, 'w+').writelines(lines)
    return True

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
