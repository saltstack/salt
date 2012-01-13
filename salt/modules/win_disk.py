'''
Module for gathering disk information on Windows
'''
is_windows = True
try:
    import ctypes
    import string
    import win32api
except ImportError:
    is_windows = False

def __virtual__():
    '''
    Only works on Windows systems
    '''
    if not is_windows:
        return False
    return 'disk'

def usage():
    '''
    Return usage information for volumes mounted on this minion

    CLI Example::

        salt '*' disk.usage
    '''
    if __grains__['kernel'] == 'Windows':
        drives = []
        ret = {}
        drive_bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in string.uppercase:
            if drive_bitmask & 1:
                drives.append(letter)
            drive_bitmask >>= 1
        for drive in drives:
            try:
                sectorspercluster, bytespersector, freeclusters, totalclusters =\
                        win32api.GetDiskFreeSpace('{0}:\\'.format(drive))
                totalsize = sectorspercluster * bytespersector * totalclusters 
                available_space = sectorspercluster * bytespersector * freeclusters 
                used = totalsize - available_space
                capacity = int(used / float(totalsize) * 100)
                ret['{0}:\\'.format(drive)] = {
                    'filesystem': '{0}:\\'.format(drive),
                    '1K-blocks': totalsize, 
                    'used': used, 
                    'available': available_space,
                    'capacity': '{0}%'.format(capacity),
                }
            except:
                ret['{0}:\\'.format(drive)] = {
                    'filesystem': '{0}:\\'.format(drive),
                    '1K-blocks': None, 
                    'used': None, 
                    'available': None,
                    'capacity': None, 
                }
        return ret

