# coding=utf-8
'''
Internal functions.
'''
# Maybe this needs to be a modules in a future?

from __future__ import absolute_import, print_function, unicode_literals
import os
from salt.cli.support.console import MessagesOutput
import salt.utils.files


out = MessagesOutput()


def filetree(collector, path):
    '''
    Add all files in the tree. If the "path" is a file,
    only that file will be added.

    :param path: File or directory
    :return:
    '''
    if not path:
        out.error('Path not defined', ident=2)
    else:
        if os.path.isfile(path):
            filename = os.path.basename(path)
            try:
                file_ref = salt.utils.files.fopen(path)
                out.put('Add {}'.format(filename), indent=2)
                collector.add(filename)
                collector.link(title=path, path=file_ref)
            except Exception as err:
                out.error(err, ident=4)
        else:
            for fname in os.listdir(path):
                fname = os.path.join(path, fname)
                filetree(collector, fname)
