'''
Minion side functions for salt-ftp
'''
import os

def recv(files, dest):
    '''
    Used with salt-ftp, pass the files dict, and the destination
    '''
    if not os.path.isdir(dest) or not os.path.isdir(os.path.dirname(dest)):
        return 'Destination not available'
    ret = {}
    for path, data in files.items():
        final = ''
        if os.path.basename(path) == os.path.basename(dest)\
                and not os.path.isdir(dest):
            final = dest
        elif os.path.isdir(dest):
            final = os.path.join(dest, os.path.basename(path))
        elif os.path.isdir(os.path.dirname(dest)):
            final = dest
        else:
            return 'Destination not available'

        try:
            open(final, 'w+').write(data)
            ret[final] = True
        except IOError:
            ret[final] = False

    return ret
