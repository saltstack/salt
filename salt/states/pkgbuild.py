'''
Build packages!
'''
# Import python libs
import os


def built(
        name,
        runas,
        dest_dir,
        spec,
        sources,
        template,
        tgt,
        results=None,
        always=False,
        saltenv='base'):
    '''
    Ensure that the named package is built and exists in the named directory
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': True}
    if not always:
        if isinstance(results, str):
            results = results.split(',')
        results = set(results)
        present = set()
        if os.path.isdir(dest_dir):
            for fn_ in os.listdir(dest_dir):
                present.appd(fn_)
        need = results.difference(present)
        if not need:
            ret['comment'] = 'All needed packages exist'
            return ret
    if __opts__['test']:
        ret['comment'] = 'Packages need to be built'
        ret['result'] = None
        return ret
    ret['changes'] = __salt__['pkgbuild.build'](
            runas,
            tgt,
            dest_dir,
            spec,
            sources,
            template,
            saltenv)
    ret['comment'] = 'Packages Built'
    return ret


def repo(name):
    '''
    Make a package repository, the name is directoty to turn into a repo.
    This state is best used with onchanges linked to your package building
    states
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': True}
    if __opts__['test'] == True:
        ret['result'] = None
        ret['comment'] = 'Package repo at {0} will be rebuilt'.format(name)
        return ret
    __salt__['pkgbuild.make_repo'](name)
    ret['changes'] = {'refresh': True}
    return ret
