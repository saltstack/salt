'''
State enforcement for mount points
'''

def mounted(
        name,
        device,
        fstype,
        mkmnt=False,
        opts=['defaults'],
        dump=0,
        pass_num=0,
        config='/etc/fstab',
        remount=True,
        persist=True,
        ):
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    # Make sure that opts is correct, it can be a list or a comma delimited
    # string
    if type(opts) == type(str()):
        opts = opts.split(',')
    # Get the active data
    active = __salt__['mount.active']()
    if active.has_key(name):
        # The mount point is mounted!
        # Check to see if it is the right setup
        remnt = False
        if not active[name]['device'] == device\
                or not active[name]['fstype'] == fstype:
            remnt = True
        # check the mount options, don't care if the desired behavior is
        # defaults
        if not opts == ['defaults']:
            if not set(active[name]['opts']) == set(opts):
                remnt = True
        if remnt:
            # The fstype has a remount opt, try it!
            out = __salt__['mount.remount'](name, device, mkmnt, fstype, opts)
            if type(out) == type(str()):
                # Failed to remount, the state has failed!
                ret['comment'] = out
                ret['result'] = False
                return ret
            elif out == True:
                # Remount worked!
                ret['changes']['mount'] = True
    else:
        # The mount is not present! Mount it
            out = __salt__['mount.mount'](name, device, mkmnt, fstype, opts)
            if type(out) == type(str()):
                # Failed to remount, the state has failed!
                ret['comment'] = out
                ret['result'] = False
                return ret
            elif out == True:
                # Remount worked!
                ret['changes']['mount'] = True
    if persist:
        # present, new, change, bad config
        # Make sure the entry is in the fstab
        out = __salt__['mount.set_fstab'](
                name,
                device,
                fstype,
                opts,
                dump,
                pass_num,
                config)
        if out == 'present':
            return ret
        if out == 'new':
            ret['changes']['persist'] = 'new'
            ret['comment'] += ' and added new entry to the fstab'
            return ret
        if out == 'change':
            ret['changes']['persist'] = 'update'
            ret['comment'] += ' and updated the entry in the fstab'
            return ret
        if out == 'bad config':
            ret['result'] = False
            ret['comment'] += ' but the fstab was not found'
            return ret


