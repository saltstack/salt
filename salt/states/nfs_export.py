# -*- coding: utf-8 -*-
'''
Management of NFS exports 
===============================================

.. code-block:: yaml

To ensure an NFS export exists:

    add_export:
      nfs_export.present:
        - name: '/srv/nfs'
        - hosts:
          - '10.0.2.0/24'
        - options:
          - 'rw'

To have different options for different hosts on the same export, define a separate state.

To ensure an NFS export is absent:

    delete_export:
      nfs_export.absent:
        - name: '/srv/nfs'

'''

#from __future__ import absolute_import
