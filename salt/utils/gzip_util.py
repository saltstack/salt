# -*- coding: utf-8 -*-
'''
    salt.utils.gzip
    ~~~~~~~~~~~~~~~
    Helper module for handling gzip consistently between 2.7+ and 2.6-
'''

# Import python libs
import gzip
import StringIO


class GzipFile(gzip.GzipFile):
    def __init__(self, filename=None, mode=None,
                 compresslevel=9, fileobj=None):
        gzip.GzipFile.__init__(self, filename, mode, compresslevel, fileobj)

    ### Context manager (stolen from Python 2.7)###
    def __enter__(self):
        """Context management protocol.  Returns self."""
        return self

    def __exit__(self, *args):
        """Context management protocol.  Calls close()"""
        self.close()


def open(filename, mode="rb", compresslevel=9):
    if hasattr(gzip.GzipFile, '__enter__'):
        return gzip.open(filename, mode, compresslevel)
    else:
        return GzipFile(filename, mode, compresslevel)


def open_fileobj(fileobj, mode='rb', compresslevel=9):
    if hasattr(gzip.GzipFile, '__enter__'):
        return gzip.GzipFile(
            filename='', mode=mode, fileobj=fileobj,
            compresslevel=compresslevel
        )
    return GzipFile(
        filename='', mode=mode, fileobj=fileobj, compresslevel=compresslevel
    )


def compress(data, compresslevel=9):
    '''
    Returns the data compressed at gzip level compression.
    '''
    buf = StringIO.StringIO()
    with open_fileobj(buf, 'wb', compresslevel) as ogz:
        ogz.write(data)
    compressed = buf.getvalue()
    return compressed


def uncompress(data):
    buf = StringIO.StringIO(data)
    with open_fileobj(buf, 'rb') as igz:
        unc = igz.read()
        return unc
