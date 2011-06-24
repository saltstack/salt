'''
Module for gathering and managing information about MooseFS
'''

def dirinfo(path, opts=None):
    '''
    Return information on a directory located on the Moose

    CLI Example:
    salt '*' moosefs.dirinfo /path/to/dir/ [-[n][h|H]]
    '''
    cmd = 'mfsdirinfo'
    ret = {}
    if opts:
        cmd += ' -' + opts
    cmd += ' ' + path
    out = __salt__['cmd.run_all'](cmd)

    output = out['stdout'].split('\n')
    for line in output:
        if not line.count(' '):
            continue
        comps = line.split(':')
        ret[comps[0].strip()] = comps[1].strip()
    return ret

def fileinfo(path):
    '''
    Return information on a file located on the Moose

    CLI Example:
    salt '*' moosefs.fileinfo /path/to/dir/
    '''
    cmd = 'mfsfileinfo ' + path
    ret = {}
    chunknum = ''
    out = __salt__['cmd.run_all'](cmd)
                    
    output = out['stdout'].split('\n')
    for line in output:
        if not line.count(' '):
            continue
        if '/' in line:
            comps = line.split('/')

            chunknum = comps[0].strip().split(':')
            meta     = comps[1].strip().split(' ')

            chunk = chunknum[0].replace('chunk ', '') 
            loc   = chunknum[1].strip()
            id    = meta[0].replace('(id:', '') 
            ver   = meta[1].replace(')', '').replace('ver:', '') 

            ret[chunknum[0]] = { 
                'chunk': chunk,
                'loc':   loc,
                'id':    id, 
                'ver':   ver,
            }   
        if 'copy' in line:
            copyinfo = line.strip().split(':')
            ret[chunknum[0]][copyinfo[0]] = { 
                'copy': copyinfo[0].replace('copy ', ''),
                'ip':   copyinfo[1].strip(),
                'port': copyinfo[2],
            }   
    return ret

