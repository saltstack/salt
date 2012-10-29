'''
Read in files from the file_root and save files to the file root
'''

# Import salt libs
import salt.utils


def find(path, env='base'):
    '''
    Return a dict of the files located with the given path and environment
    '''
    # Return a list of paths + text or bin
    ret = []
    if env not in __opts__['file_roots']:
        return ret
    for root in __opts__['file_roots'][env]:
        full = os.path.join(root, path)
        if os.path.isfile(full):
            # Add it to the dict
            with open(path, 'rb') as fp_:
                if salt.utils.istextfile(fp_):
                    ret.append({full: 'txt'})
                else:
                    ret.append({full: 'bin'})
    return ret


def read(path, env='base'):
    '''
    Read the contents of a text file, if the file is binary then 
    '''
    # Return a dict of paths + content
    ret = []
    files = find(path, env)
    for fn_ in files:
        if fn_ == 'txt':
            with open(fn_, 'rb') as fp_:
                ret.append({fn_: fp_.read()})
    return ret


def write(data, path, env='base', index=0):
    '''
    Write the named file, by default the first file found is written, but the
    index of the file can be specified to write to a lower priority file root
    '''
