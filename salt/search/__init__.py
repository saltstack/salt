'''
Set up the correct search system
'''

# Import python libs
import os

# Import salt libs
import salt.minion
import salt.loader
import salt.utils


def iter_ret(opts, ret):
    '''
    Yield returner data if the external job cache is enabled
    '''
    if not opts['ext_job_cache']:
        raise StopIteration
    get_load = '{0}.get_load'.format(opts['ext_job_cache'])
    get_jid = '{0}.get_jid'.format(opts['ext_job_cache'])
    get_jids = '{0}.get_jids'.format(opts['ext_job_cache'])
    if get_load not in ret:
        raise StopIteration
    else:
        get_load = ret[get_load]
    if get_jid not in ret:
        raise StopIteration
    else:
        get_jid = ret[get_jid]
    if get_jids not in ret:
        raise StopIteration
    else:
        get_jids = ret[get_jids]
    for jid in get_jids():
        jids = {}
        jids['load'] = get_load(jid)
        jids['ret'] = get_jid(jid)
        jids['jid'] = jid
        yield jids


def _iter_dir(dir_, env):
    ret = []
    for fn_ in os.listdir(dir_):
        path = os.path.join(dir_, fn_)
        if os.path.isdir(path):
            yield _iter_dir(path, env)
        elif os.path.isfile(path):
            with open(path) as fp_:
                if salt.utils.istextfile(fp_):
                    ret.append(
                        {'path': unicode(path),
                         'env': unicode(env),
                         'content': unicode(fp_.read())}
                        )
                else:
                    ret.append(
                        {'path': unicode(path),
                         'env': unicode(env),
                         'content': u'bin'}
                        )
    yield ret


def iter_roots(roots):
    '''
    Accepts the file_roots or the pillar_roots structures and yields
    {'path': <path>,
     'env': <env>,
     'cont': <contents>}
    '''
    for env, dirs in roots.items():
        for dir_ in dirs:
            if not os.path.isdir(dir_):
                continue
            for ret in _iter_dir(dir_, env):
                yield ret

class Search(object):
    '''
    Set up the object than manages search operations
    '''
    def __init__(self, opts):
        self.opts = opts
        self.mminion = salt.minion.MasterMinion(
                self.opts,
                states=False,
                rend=False,
                matcher=False)
        self.search = salt.loader.search(self.opts, self.mminion.returners)

    def index(self):
        '''
        Execute a search index run
        '''
        ifun = '{0}.index'.format(self.opts.get('search', ''))
        if ifun not in self.search:
            return
        return self.search[ifun]()

    def query(self, term):
        '''
        Search the index for the given term
        '''
        qfun = '{0}.query'.format(self.opts.get('search', ''))
        if qfun not in self.search:
            return
        return self.search[qfun](term)
