# -*- coding: utf-8 -*-

import re
import itertools

from pylint.interfaces import IRawChecker
from pylint.checkers import BaseChecker


class FileEncodingChecker(BaseChecker):
    '''
    Check for PEP263 compliant file encoding in file.
    '''

    __implements__ = IRawChecker

    name = 'pep263'
    msgs = {'W9901': ('PEP263: Multiple file encodings',
                      'multiple-encoding-in-file',
                      ('There are multiple encodings in file.')),
            'W9902': ('PEP263: Use UTF-8 file encoding',
                      'no-encoding-in-file',
                      ('There is no PEP263 compliant file encoding in file.')),
            }
    priority = -1
    options = ()

    RE_PEP263 = r'coding[:=]\s*([-\w.]+)'
    REQ_ENCOD = 'utf-8'

    def process_module(self, node):
        '''
        process a module

        the module's content is accessible via node.file_stream object
        '''
        pep263 = re.compile(self.RE_PEP263)

        twolines = list(itertools.islice(node.file_stream, 2))
        encoding = [m.group(1) for l in twolines for m in [pep263.search(l)] if m]
        # If there are ambiguous encodings it will be caught by E0001
        if len(encoding) > 1:
            self.add_message('W9901', line=1)
        if self.REQ_ENCOD not in encoding:
            self.add_message('W9902', line=1)


def register(linter):
    '''
    required method to auto register this checker
    '''
    linter.register_checker(FileEncodingChecker(linter))
