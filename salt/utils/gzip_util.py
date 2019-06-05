# -*- coding: utf-8 -*-
'''
    salt.utils.gzip
    ~~~~~~~~~~~~~~~
    Helper module for handling gzip consistently between 2.7+ and 2.6-
'''

from __future__ import absolute_import, unicode_literals, print_function

# Import python libs
import gzip

# Import Salt libs
import salt.utils.files

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six import BytesIO


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
    buf = BytesIO()
    with open_fileobj(buf, 'wb', compresslevel) as ogz:
        if six.PY3 and not isinstance(data, bytes):
            data = data.encode(__salt_system_encoding__)
        ogz.write(data)
    compressed = buf.getvalue()
    return compressed


def uncompress(data):
    buf = BytesIO(data)
    with open_fileobj(buf, 'rb') as igz:
        unc = igz.read()
        return unc


def compress_file(fh_, compresslevel=9, chunk_size=1048576):
    '''
    Generator that reads chunk_size bytes at a time from a file/filehandle and
    yields the compressed result of each read.

    .. note::
        Each chunk is compressed separately. They cannot be stitched together
        to form a compressed file. This function is designed to break up a file
        into compressed chunks for transport and decompression/reassembly on a
        remote host.
    '''
    try:
        bytes_read = int(chunk_size)
        if bytes_read != chunk_size:
            raise ValueError
    except ValueError:
        raise ValueError('chunk_size must be an integer')
    try:
        while bytes_read == chunk_size:
            buf = BytesIO()
            with open_fileobj(buf, 'wb', compresslevel) as ogz:
                try:
                    bytes_read = ogz.write(fh_.read(chunk_size))
                except AttributeError:
                    # Open the file and re-attempt the read
                    fh_ = salt.utils.files.fopen(fh_, 'rb')
                    bytes_read = ogz.write(fh_.read(chunk_size))
            yield buf.getvalue()
    finally:
        try:
            fh_.close()
        except AttributeError:
            pass
