# -*- coding: utf-8 -*-
'''
Utilities for managing YAST

.. versionadded:: Beryllium
'''
from __future__ import absolute_import, print_function, unicode_literals
from salt._compat import ElementTree as ET
import salt.utils.xmlutil as xml
import salt.utils.files
import salt.utils.yaml


def mksls(src, dst=None):
    '''
    Convert an AutoYAST file to an SLS file
    '''
    with salt.utils.files.fopen(src, 'r') as fh_:
        ps_opts = xml.to_dict(ET.fromstring(fh_.read()))

    if dst is not None:
        with salt.utils.files.fopen(dst, 'w') as fh_:
            salt.utils.yaml.safe_dump(ps_opts, fh_, default_flow_style=False)
    else:
        return salt.utils.yaml.safe_dump(ps_opts, default_flow_style=False)
