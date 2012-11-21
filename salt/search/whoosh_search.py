'''
Routines to manage interactions with the whoosh search system
'''

# Import python libs
import os

# Import salt libs
import salt.search

# Import whoosh libs
has_whoosh = False
try:
    import whoosh.index
    import whoosh.fields
    import whoosh.store
    import whoosh.qparser
    has_whoosh = True
except ImportError:
    pass


def __virtual__():
    '''
    Only load if the whoosh libs are available
    '''
    return 'whoosh' if has_whoosh else False


def index():
    '''
    Build the search index
    '''
    schema = whoosh.fields.Schema(
            path=whoosh.fields.TEXT, # Path for sls files
            content=whoosh.fields.TEXT, # All content is indexed here
            env=whoosh.fields.ID, # The environment associated with a file
            fn_type=whoosh.fields.ID, # Set to pillar or state
            minion=whoosh.fields.ID, # The minion id associated with the content
            jid=whoosh.fields.ID, # The job id
            load=whoosh.fields.ID, # The load data
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
    qobj = qp_.parse(unicode(qstr), limit)
    with ix_.searcher() as searcher:
        return searcher.search(qobj)
