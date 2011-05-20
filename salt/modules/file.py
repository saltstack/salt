'''
Manage information about files on the minion, set/read user, group, and mode
data
'''

def gid_to_group(gid):
    '''
    Convert the group id to the group name on this system
    '''

def group_to_gid(group):
    '''
    Convert the group to the gid on this system
    '''

def get_mode(path):
    '''
    Return the mode of a file
    '''
    if not os.path.isfile(path):
        return False
    return oct(os.stat(path).st_mode)[-4:]

def set_mode(path, mode):
    '''
    Set the more of a file
    '''
    if not os.path.isfile(path):
        return 'File not found'
    try:
        os.chmod(path, int(mode, 8))
    except:
        return 'Invalid Mode ' + mode
    return get_mode(path)


