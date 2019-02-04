# coding=utf-8
'''
Internal functions.
'''
# Maybe this needs to be a modules in a future?

from __future__ import absolute_import, print_function, unicode_literals
import os
import glob
from salt.cli.support.console import MessagesOutput
import salt.utils.files


out = MessagesOutput()


def filetree(collector, *paths):
    '''
    Add all files in the tree. If the "path" is a file,
    only that file will be added.

    :param path: File or directory
    :return:
    '''
    _paths = []
    # Unglob
    for path in paths:
        _paths += glob.glob(path)
    for path in set(_paths):
        if not path:
            out.error('Path not defined', ident=2)
        elif not os.path.exists(path):
            out.warning('Path {} does not exists'.format(path))
        else:
            # The filehandler needs to be explicitly passed here, so PyLint needs to accept that.
            # pylint: disable=W8470
            if os.path.isfile(path):
                filename = os.path.basename(path)
                try:
                    file_ref = salt.utils.files.fopen(path)  # pylint: disable=W
                    out.put('Add {}'.format(filename), indent=2)
                    collector.add(filename)
                    collector.link(title=path, path=file_ref)
                except Exception as err:
                    out.error(err, ident=4)
            # pylint: enable=W8470
            else:
                try:
                    for fname in os.listdir(path):
                        fname = os.path.join(path, fname)
                        filetree(collector, [fname])
                except Exception as err:
                    out.error(err, ident=4)
