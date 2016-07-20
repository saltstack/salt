# -*- coding: utf-8 -*-
'''
Routines to manage interactions with the whoosh search system
'''
from __future__ import absolute_import

# Import python libs
import os

# Import salt libs
import salt.search
import salt.ext.six as six

# Import third party libs
HAS_WHOOSH = False
try:
    import whoosh.index
    import whoosh.fields
    import whoosh.store
    import whoosh.qparser
    HAS_WHOOSH = True
except ImportError:
    pass

# Define the module's virtual name
__virtualname__ = 'whoosh'


def __virtual__():
    '''
    Only load if the whoosh libs are available
    '''
    return __virtualname__ if HAS_WHOOSH else False


def index():
    '''
    Build the search index
    '''
    schema = whoosh.fields.Schema(
            path=whoosh.fields.TEXT,  # Path for sls files
            content=whoosh.fields.TEXT,  # All content is indexed here
            env=whoosh.fields.ID,  # The environment associated with a file
            fn_type=whoosh.fields.ID,  # Set to pillar or state
            minion=whoosh.fields.ID,  # The minion id associated with the content
            jid=whoosh.fields.ID,  # The job id
            load=whoosh.fields.ID,  # The load data
            )
    index_dir = os.path.join(__opts__['cachedir'], 'whoosh')
    if not os.path.isdir(index_dir):
        os.makedirs(index_dir)
    if whoosh.index.exists_in(index_dir):
        ix_ = whoosh.index.open_dir(index_dir)
    else:
        ix_ = whoosh.index.create_in(index_dir, schema)

    try:
        writer = ix_.writer()
    except whoosh.store.LockError:
        return False

    for data in salt.search.iter_roots(__opts__['file_roots']):
        for chunk in data:
            writer.add_document(fn_type=u'file', **chunk)

    for data in salt.search.iter_roots(__opts__['pillar_roots']):
        for chunk in data:
            writer.add_document(fn_type=u'pillar', **chunk)

    for data in salt.search.iter_ret(__opts__, __ret__):
        writer.add_document(jid=data['jid'], load=data['load'])
        for minion in data['ret']:
            writer.add_document(
                    jid=data['jid'],
                    minion=minion,
                    content=data['ret'][minion])
    writer.commit()


def query(qstr, limit=10):
    '''
    Execute a query
    '''
    index_dir = os.path.join(__opts__['cachedir'], 'whoosh')
    if whoosh.index.exists_in(index_dir):
        ix_ = whoosh.index.open_dir(index_dir)
    else:
        return {}
    qp_ = whoosh.qparser.QueryParser(u'content', schema=ix_.schema)
    qobj = qp_.parse(six.text_type(qstr), limit)
    with ix_.searcher() as searcher:
        return searcher.search(qobj)
