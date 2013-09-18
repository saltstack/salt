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
            'W9902': ('PEP263: Parser and PEP263 encoding mismatch',
                      'encoding-mismatch-in-file',
                      ('The pylint parser and the PEP263 file encoding in file '
                       'does not match.')),
            'W9903': ('PEP263: Use UTF-8 file encoding',
                      'no-encoding-in-file',
                      ('There is no PEP263 compliant file encoding in file.')),
            'W9904': ('PEP263: Use UTF-8 file encoding',
                      'wrongly-encoded-file',
                      ('Change file encoding and PEP263 header in file.')),
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
        pep263_encoding = [m.group(1).lower() for l in twolines for m in [pep263.search(l)] if m]

        # - If the file has an UTF-8 BOM and yet uses any other
        #   encoding, it will be caught by F0002
        # - If the file has a PEP263 UTF-8 encoding and yet uses any
        #   other encoding, it will be caught by W0512
        # - If there are non-ASCII characters and no PEP263, or UTF-8
        #   BOM, it will be caught by W0512
        # - If there are ambiguous PEP263 encodings it will be caught
        #   by E0001, we still test for this
        if len(pep263_encoding) > 1:
            self.add_message('W9901', line=1)
        if node.file_encoding:
            pylint_encoding = node.file_encoding.lower()
            if pep263_encoding and pylint_encoding not in pep263_encoding:
                self.add_message('W9902', line=1)
        if not pep263_encoding:
            self.add_message('W9903', line=1)
        elif self.REQ_ENCOD not in pep263_encoding:
            self.add_message('W9904', line=1)


def register(linter):
    '''
    required method to auto register this checker
    '''
    linter.register_checker(FileEncodingChecker(linter))
