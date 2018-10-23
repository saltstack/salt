# -*- coding: utf-8 -*-
'''
Store key/value pairs in a CSV file

.. versionadded:: 2016.11.0

Example configuration:

.. code-block:: yaml

    ext_pillar:
      - csv: /path/to/file.csv

    # or

    ext_pillar:
      - csv:
          path: /path/to/file.csv
          namespace: 'subkey'
          fieldnames:
          - col1
          - col2
          - col2

The first column must be minion IDs and the first row must be dictionary keys.
E.g.:

==========  =========   ======
id          role        env
==========  =========   ======
jerry       web         prod
stuart      web         stage
dave        web         qa
phil        db          prod
kevin       db          stage
mike        db          qa
==========  =========   ======

Will produce the following Pillar values for a minion named "jerry":

.. code-block:: python

    {
        'role': 'web',
        'env': 'prod',
    }
'''
from __future__ import absolute_import, print_function, unicode_literals
import csv

import salt.utils.files

__virtualname__ = 'csv'


def __virtual__():
    return __virtualname__


def ext_pillar(
        mid,
        pillar,
        path,
        idkey='id',
        namespace=None,
        fieldnames=None,
        restkey=None,
        restval=None,
        dialect='excel'):
    '''
    Read a CSV into Pillar

    :param str path: Absolute path to a CSV file.
    :param str idkey: (Optional) The column name of minion IDs.
    :param str namespace: (Optional) A pillar key to namespace the values under.
    :param list fieldnames: (Optional) if the first row of the CSV is not
        column names they may be specified here instead.
    '''
    with salt.utils.files.fopen(path, 'rb') as f:
        sheet = csv.DictReader(f, fieldnames,
                restkey=restkey, restval=restval, dialect=dialect)

        for row in sheet:
            if row[idkey] == mid:
                if namespace:
                    return {namespace: row}
                else:
                    return row

    return {}
