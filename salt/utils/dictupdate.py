'''
Alex Martelli's soulution for recursive dict update from
http://stackoverflow.com/a/3233356
'''

# Import python libs
import collections


def update(dest, upd):
    for key, val in upd.iteritems():
        if isinstance(val, collections.Mapping):
            ret = update(dest.get(key, {}), val)
            dest[key] = ret
        else:
            dest[key] = upd[key]
    return dest
