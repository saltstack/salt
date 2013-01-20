'''
Management of package repos
===========================

Package repositories can be managed with the pkgrepo state:

.. code-block:: yaml

    base:
      pkgrepo.managed:
        - human_name: CentOS-$releasever - Base
        - mirrorlist: http://mirrorlist.centos.org/?release=$releasever&arch=$basearch&repo=os
        - comments:
            - #http://mirror.centos.org/centos/$releasever/os/$basearch/
        - gpgcheck: 1
        - gpgkey: file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-6
'''


def __virtual__():
    '''
    Only load if modifying repos is available for this package type
    '''
    return 'pkgrepo' if 'pkg.mod_repo' in __salt__ else False


def managed(name, **kwargs):
    '''
    This function manages the configuration on a system that points to the
    repositories for the system's package manager.

    name
        The name of the package repo, as it would be referred to when running
        the regular package manager commands.


    For yum-based systems, take note of the following configuration values:

    humanname
        On yum-based systems, this is stored as the "name" value in the .repo
        file in /etc/yum.repos.d/. On yum-based systems, this is required.

    baseurl
        On yum-based systems, baseurl refers to a direct URL to be used for
        this yum repo.
        One of baseurl or mirrorlist is required.

    mirrorlist
        a URL which contains a collection of baseurls to choose from. On
        yum-based systems.
        One of baseurl or mirrorlist is required.

    comments
        Sometimes you want to supply additional information, but not as
        enabled configuration. Anything supplied for this list will be saved
        in the repo configuration with a comment marker (#) in front.
    

    For apt-based systems, take note of the following configuration vaolues:

    uri
        On apt-based systems, uri refers to a direct URL to be used for the 
        apt repo.

    disabled
        On apt-based systems, disabled toggles whether or not the repo is 
        used for resolving dependancies and/or installing packages

    comps
        On apt-based systems, comps dictate the types of packages to be
        installed from the repository (e.g. main, nonfree, ...).  For 
        purposes of this, comps should be a comma-separated list.

    file
       The filename for the .list that the repository is configured in.
       It is important to include the full-path AND make sure it is in
       a directory that APT will look in when handling packages
  
    dist
       This dictates the release of the distro the packages should be built
       for.  (e.g. unstable)    
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    repo = {}
    try:
        repo = __salt__['pkg.get_repo'](name)
    except:
        pass

    # pkg.mod_repo has conflicting kwargs, so move 'em around
    repokwargs = {}
    for kwarg in kwargs.keys():
        if kwarg == 'name':
            repokwargs['repo'] = kwargs[kwarg]
        elif kwarg == 'humanname':
            repokwargs['name'] = kwargs[kwarg]
        elif kwarg in ('__id__', 'fun', 'state', '__env__', '__sls__', 'order'):
            pass
        else:
            repokwargs[kwarg] = kwargs[kwarg]

    if repo:
        notset = False
        for kwarg in repokwargs:
            if kwarg not in repo.keys():
                notset = True
            else:
                if repokwargs[kwarg] != repo[kwarg]:
                    notset = True
        if notset is False:
            ret['comment'] = 'Package repo {0} already configured'.format(name)
            return ret
    if __opts__['test']:
        ret['comment'] = 'Package repo {0} needs to be configured'.format(name)
        return ret


    __salt__['pkg.mod_repo'](repo=name, **repokwargs)
    try:
        repodict = __salt__['pkg.get_repo'](name)
        if repo:
            for kwarg in repokwargs:
                if repodict[kwarg] != repo.get(kwarg):
                    change = { 'new': repodict[kwarg],
                               'old': repo.get(kwarg) }
                    ret['changes'][kwarg] = change
        else:
            ret['changes'] = { 'repo': name }
        ret['result'] = True
        ret['comment'] = 'Configured package repo {0}'.format(name)
        return ret
    except:
        pass
    ret['result'] = False
    ret['comment'] = 'Failed to configure repo {0}'.format(name)
    return ret

def absent(name):
    '''
    This function deletes the specified repo on the system, if it exists. It
    is essentially a wrapper around pkg.del_repo.

    name
        The name of the package repo, as it would be referred to when running
        the regular package manager commands.
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    repo = {}
    try:
        repo = __salt__['pkg.get_repo'](name)
    except:
        pass
    if not repo:
        ret['comment'] = 'Package repo {0} is absent'.format(name)
        ret['result'] = True
        return ret
    if __opts__['test']:
        ret['comment'] = 'Package repo {0} needs to be removed'.format(name)
        return ret
    __salt__['pkg.del_repo'](repo=name)
    repos = __salt__['pkg.list_repos']()
    if name not in repos.keys():
        ret['changes'] = {'repo': name}
        ret['result'] = True
        ret['comment'] = 'Removed package repo {0}'.format(name)
        return ret
    ret['result'] = False
    ret['comment'] = 'Failed to remove repo {0}'.format(name)
    return ret

