# -*- coding: utf-8 -*-
'''
Management of NFS exports 
===============================================

To ensure an NFS export exists:

.. code-block:: yaml

    add_export:
      nfs_export.present:
        - name: '/srv/nfs'
        - exports:
          - hosts:
            - '10.0.2.0/24'
          - options:
            - 'rw'

This creates the following in /etc/exports:

.. code-block:: bash
    /srv/nfs 10.0.2.0/24(rw)

Any export of the given path will be modified to match the one specified.

To ensure an NFS export is absent:

.. code-block:: yaml

    delete_export:
      nfs_export.absent:
        - name: '/srv/nfs'

'''

#from __future__ import absolute_import
