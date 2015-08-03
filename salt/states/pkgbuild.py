# -*- coding: utf-8 -*-
'''
The pkgbuild state is the front of Salt package building backend. It
automatically

.. versionadded:: 2015.8.0

.. code-block:: yaml

    salt_2015.5.2:
      pkgbuild.built:
        - runas: thatch
        - results:
          - salt-2015.5.2-2.el7.centos.noarch.rpm
          - salt-api-2015.5.2-2.el7.centos.noarch.rpm
          - salt-cloud-2015.5.2-2.el7.centos.noarch.rpm
          - salt-master-2015.5.2-2.el7.centos.noarch.rpm
          - salt-minion-2015.5.2-2.el7.centos.noarch.rpm
          - salt-ssh-2015.5.2-2.el7.centos.noarch.rpm
          - salt-syndic-2015.5.2-2.el7.centos.noarch.rpm
        - dest_dir: /tmp/pkg
        - spec: salt://pkg/salt/spec/salt.spec
        - template: jinja
        - tgt: epel-7-x86_64
        - sources:
          - salt://pkg/salt/sources/logrotate.salt
          - salt://pkg/salt/sources/README.fedora
          - salt://pkg/salt/sources/salt-2015.5.2.tar.gz
          - salt://pkg/salt/sources/salt-2015.5.2-tests.patch
          - salt://pkg/salt/sources/salt-api
          - salt://pkg/salt/sources/salt-api.service
          - salt://pkg/salt/sources/salt-master
          - salt://pkg/salt/sources/salt-master.service
          - salt://pkg/salt/sources/salt-minion
          - salt://pkg/salt/sources/salt-minion.service
          - salt://pkg/salt/sources/saltpkg.sls
          - salt://pkg/salt/sources/salt-syndic
          - salt://pkg/salt/sources/salt-syndic.service
          - salt://pkg/salt/sources/SaltTesting-2015.5.8.tar.gz
    /tmp/pkg:
      pkgbuild.repo
'''
# Import python libs
from __future__ import absolute_import, print_function
import os


def built(
        name,
        runas,
        dest_dir,
        spec,
        sources,
        template,
        tgt,
        deps=None,
        results=None,
        always=False,
        saltenv='base'):
    '''
    Ensure that the named package is built and exists in the named directory

    name
        The name to track the build, the name value is otherwise unused

    runas
        The user to run the build process as

    dest_dir
        The directory on the minion to place the built package(s)

    spec
        The location of the spec file (used for rpms)

    sources
        The list of package sources

    template
        Set to run the spec file through a templating engine

    tgt
        The target platform to run the build on

    deps
        Packages required to ensure that the named package is built
        can be hosted on either the salt master server or on an HTTP
        or FTP server.  Both HTTPS and HTTP are supported as well as
        downloading directly from Amazon S3 compatible URLs with both
        pre-configured and automatic IAM credentials

    results
        The names of the expected rpms that will be built

    always
        Build with every run (good if the package is for continuous or
        nightly package builds)

    saltenv
        The saltenv to use for files downloaded from the salt filesever
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
                present.add(fn_)
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
        deps,
        template,
        saltenv)
    ret['comment'] = 'Packages Built'
    return ret


def repo(name):
    '''
    Make a package repository, the name is directoty to turn into a repo.
    This state is best used with onchanges linked to your package building
    states

    name
        The directory to find packages that will be in the repository
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': True}
    if __opts__['test'] is True:
        ret['result'] = None
        ret['comment'] = 'Package repo at {0} will be rebuilt'.format(name)
        return ret
    __salt__['pkgbuild.make_repo'](name)
    ret['changes'] = {'refresh': True}
    return ret
