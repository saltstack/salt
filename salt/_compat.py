# -*- coding: utf-8 -*-
'''
Salt compatibility code
'''
# pylint: disable=import-error,unused-import,invalid-name

# Import python libs
from __future__ import absolute_import
import sys
import types
import subprocess

# Import 3rd-party libs
from salt.ext.six import binary_type, string_types, text_type
from salt.ext.six.moves import cStringIO, StringIO

try:
    # Python >2.5
    import xml.etree.cElementTree as ElementTree
except Exception:
    try:
        # Python >2.5
        import xml.etree.ElementTree as ElementTree
    except Exception:
        try:
            # normal cElementTree install
            import elementtree.cElementTree as ElementTree
        except Exception:
            try:
                # normal ElementTree install
                import elementtree.ElementTree as ElementTree
            except Exception:
                raise


# True if we are running on Python 3.
PY3 = sys.version_info[0] == 3


if PY3:
    import builtins
    exceptions = builtins
else:
    import exceptions


if not hasattr(ElementTree, 'ParseError'):
    class ParseError(Exception):
        '''
        older versions of ElementTree do not have ParseError
        '''
        pass

    ElementTree.ParseError = ParseError


def text_(s, encoding='latin-1', errors='strict'):
    '''
    If ``s`` is an instance of ``binary_type``, return
    ``s.decode(encoding, errors)``, otherwise return ``s``
    '''
    if isinstance(s, binary_type):
        return s.decode(encoding, errors)
    return s


def bytes_(s, encoding='latin-1', errors='strict'):
    '''
    If ``s`` is an instance of ``text_type``, return
    ``s.encode(encoding, errors)``, otherwise return ``s``
    '''
    if isinstance(s, text_type):
        return s.encode(encoding, errors)
    return s


if PY3:
    def ascii_native_(s):
        if isinstance(s, text_type):
            s = s.encode('ascii')
        return str(s, 'ascii', 'strict')
else:
    def ascii_native_(s):
        if isinstance(s, text_type):
            s = s.encode('ascii')
        return str(s)

ascii_native_.__doc__ = '''
Python 3: If ``s`` is an instance of ``text_type``, return
``s.encode('ascii')``, otherwise return ``str(s, 'ascii', 'strict')``

Python 2: If ``s`` is an instance of ``text_type``, return
``s.encode('ascii')``, otherwise return ``str(s)``
'''


if PY3:
    def native_(s, encoding='latin-1', errors='strict'):
        '''
        If ``s`` is an instance of ``text_type``, return
        ``s``, otherwise return ``str(s, encoding, errors)``
        '''
        if isinstance(s, text_type):
            return s
        return str(s, encoding, errors)
else:
    def native_(s, encoding='latin-1', errors='strict'):
        '''
        If ``s`` is an instance of ``text_type``, return
        ``s.encode(encoding, errors)``, otherwise return ``str(s)``
        '''
        if isinstance(s, text_type):
            return s.encode(encoding, errors)
        return str(s)

native_.__doc__ = '''
Python 3: If ``s`` is an instance of ``text_type``, return ``s``, otherwise
return ``str(s, encoding, errors)``

Python 2: If ``s`` is an instance of ``text_type``, return
``s.encode(encoding, errors)``, otherwise return ``str(s)``
'''


def string_io(data=None):  # cStringIO can't handle unicode
    '''
    Pass data through to stringIO module and return result
    '''
    try:
        return cStringIO(bytes(data))
    except (UnicodeEncodeError, TypeError):
        return StringIO(data)


if sys.version_info < (2, 7):

    # Backport of Python's 2.7 subprocess methods not found in 2.6
    # This code comes directly from the 2.7 subprocess module

    def check_output(*popenargs, **kwargs):
        r"""Run command with arguments and return its output as a byte string.

        If the exit code was non-zero it raises a CalledProcessError.  The
        CalledProcessError object will have the return code in the returncode
        attribute and output in the output attribute.

        The arguments are the same as for the Popen constructor.  Example:

        >>> check_output(["ls", "-l", "/dev/null"])
        'crw-rw-rw- 1 root root 1, 3 Oct 18  2007 /dev/null\n'

        The stdout argument is not allowed as it is used internally.
        To capture standard error in the result, use stderr=STDOUT.

        >>> check_output(["/bin/sh", "-c",
        ...               "ls -l non_existent_file ; exit 0"],
        ...              stderr=STDOUT)
        'ls: non_existent_file: No such file or directory\n'
        """
        if 'stdout' in kwargs:
            raise ValueError('stdout argument not allowed, it will be overridden.')
        process = subprocess.Popen(stdout=subprocess.PIPE, *popenargs, **kwargs)
        output, unused_err = process.communicate()
        retcode = process.poll()
        if retcode:
            cmd = kwargs.get("args")
            if cmd is None:
                cmd = popenargs[0]
            raise subprocess.CalledProcessError(retcode, cmd, output=output)
        return output
    subprocess.check_output = check_output


if PY3:
    import ipaddress
else:
    import salt.ext.ipaddress as ipaddress
