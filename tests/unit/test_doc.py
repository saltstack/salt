# -*- coding: utf-8 -*-
'''
    tests.unit.doc_test
    ~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import
import os
import re
import logging

# Import Salt Testing libs
from tests.support.paths import CODE_DIR
from tests.support.unit import TestCase

# Import Salt libs
import salt.modules.cmdmod
import salt.utils.platform


log = logging.getLogger(__name__)


class DocTestCase(TestCase):
    '''
    Unit test case for testing doc files and strings.
    '''

    def test_check_for_doc_inline_markup(self):
        '''
        We should not be using the ``:doc:`` inline markup option when
        cross-referencing locations. Use ``:ref:`` or ``:mod:`` instead.

        This test checks for reference to ``:doc:`` usage.

        See Issue #12788 for more information.

        https://github.com/saltstack/salt/issues/12788
        '''
        salt_dir = CODE_DIR

        if salt.utils.platform.is_windows():
            if salt.utils.path.which('bash'):
                # Use grep from git-bash when it exists.
                cmd = 'bash -c \'grep -r :doc: ./salt/'
                grep_call = salt.modules.cmdmod.run_stdout(cmd=cmd, cwd=salt_dir).split(os.linesep)
            else:
                # No grep in Windows, use findstr
                # findstr in windows doesn't prepend 'Binary` to binary files, so
                # use the '/P' switch to skip files with unprintable characters
                cmd = 'findstr /C:":doc:" /S /P {0}\\*'.format(salt_dir)
                grep_call = salt.modules.cmdmod.run_stdout(cmd=cmd).split(os.linesep)
        else:
            salt_dir += '/'
            cmd = 'grep -r :doc: ' + salt_dir
            grep_call = salt.modules.cmdmod.run_stdout(cmd=cmd).split(os.linesep)

        test_ret = {}
        for line in grep_call:
            # Skip any .pyc files that may be present
            if line.startswith('Binary'):
                continue

            # Only split on colons not followed by a '\' as is the case with
            # Windows Drives
            regex = re.compile(r':(?!\\)')
            try:
                key, val = regex.split(line, 1)
            except ValueError:
                log.error("Could not split line: %s", line)
                continue

            # Don't test man pages, this file, the tox or nox virtualenv files,
            # the page that documents to not use ":doc:", the doc/conf.py file
            # or the artifacts directory on nox CI test runs
            if 'man' in key \
                    or '.tox{}'.format(os.sep) in key \
                    or '.nox{}'.format(os.sep) in key \
                    or 'artifacts{}'.format(os.sep) in key \
                    or key.endswith('test_doc.py') \
                    or key.endswith(os.sep.join(['doc', 'conf.py'])) \
                    or key.endswith(os.sep.join(['conventions', 'documentation.rst'])) \
                    or key.endswith(os.sep.join(['doc', 'topics', 'releases', '2016.11.2.rst'])) \
                    or key.endswith(os.sep.join(['doc', 'topics', 'releases', '2016.11.3.rst'])) \
                    or key.endswith(os.sep.join(['doc', 'topics', 'releases', '2016.3.5.rst'])):
                continue

            # Set up test return dict
            if test_ret.get(key) is None:
                test_ret[key] = [val.strip()]
            else:
                test_ret[key].append(val.strip())

        # Allow test results to show files with :doc: ref, rather than truncating
        self.maxDiff = None

        # test_ret should be empty, otherwise there are :doc: references present
        self.assertEqual(test_ret, {})

    def _check_doc_files(self, module_skip, module_dir, doc_skip, module_doc_dir):
        '''
        Ensure various salt modules have associated documentation
        '''

        salt_dir = RUNTIME_VARS.CODE_DIR

        # Build list of module files
        module_files = []
        skip_module_files = module_skip
        full_module_dir = os.path.join(salt_dir, *module_dir)
        for file in os.listdir(full_module_dir):
            if file.endswith(".py"):
                module_name = os.path.splitext(file)[0]
                if module_name not in skip_module_files:
                    module_files.append(module_name)

        # Build list of beacon documentation files
        module_docs = []
        skip_doc_files = doc_skip
        full_module_doc_dir = os.path.join(salt_dir, *module_doc_dir)
        doc_prefix = '.'.join(module_dir) + '.'
        for file in os.listdir(full_module_doc_dir):
            if file.endswith(".rst"):
                doc_name = os.path.splitext(file)[0]
                if doc_name.startswith(doc_prefix):
                    doc_name = doc_name[len(doc_prefix):]
                if doc_name not in skip_doc_files:
                    module_docs.append(doc_name)

        # Check that every beacon has associated documentaiton file
        for module in module_files:
            self.assertIn(module,
                          module_docs,
                          'module file {0} is missing documentation in {1}'.format(module,
                                                                                   full_module_doc_dir))

        for doc_file in module_docs:
            self.assertIn(doc_file,
                          module_files,
                          'Doc file {0} is missing associated module in {1}'.format(doc_file,
                                                                                    full_module_dir))

    def test_auth_doc_files(self):
        '''
        Ensure auth modules have associated documentation

        doc example: doc/ref/auth/all/salt.auth.rest.rst
        auth module example: salt/auth/rest.py
        '''

        skip_files = ['__init__']
        module_dir = ['salt', 'auth']
        skip_doc_files = ['index', 'all']
        doc_dir = ['doc', 'ref', 'auth', 'all']
        self._check_doc_files(skip_files, module_dir, skip_doc_files, doc_dir)

    def test_beacon_doc_files(self):
        '''
        Ensure beacon modules have associated documentation

        doc example: doc/ref/beacons/all/salt.beacon.rest.rst
        beacon module example: salt/beacons/rest.py
        '''

        skip_files = ['__init__']
        module_dir = ['salt', 'beacons']
        skip_doc_files = ['index', 'all']
        doc_dir = ['doc', 'ref', 'beacons', 'all']
        self._check_doc_files(skip_files, module_dir, skip_doc_files, doc_dir)

    def test_cache_doc_files(self):
        '''
        Ensure cache modules have associated documentation

        doc example: doc/ref/cache/all/salt.cache.consul.rst
        cache module example: salt/cache/consul.py
        '''

        skip_module_files = ['__init__']
        module_dir = ['salt', 'cache']
        skip_doc_files = ['index', 'all']
        doc_dir = ['doc', 'ref', 'cache', 'all']
        self._check_doc_files(skip_module_files, module_dir, skip_doc_files, doc_dir)

    def test_cloud_doc_files(self):
        '''
        Ensure cloud modules have associated documentation

        doc example: doc/ref/clouds/all/salt.cloud.gce.rst
        cloud module example: salt/cloud/clouds/gce.py
        '''

        skip_module_files = ['__init__']
        module_dir = ['salt', 'cloud', 'clouds']
        skip_doc_files = ['index', 'all']
        doc_dir = ['doc', 'ref', 'clouds', 'all']
        self._check_doc_files(skip_module_files, module_dir, skip_doc_files, doc_dir)

    def test_engine_doc_files(self):
        '''
        Ensure engine modules have associated documentation

        doc example: doc/ref/engines/all/salt.engines.docker_events.rst
        engine module example: salt/engines/docker_events.py
        '''

        skip_module_files = ['__init__']
        module_dir = ['salt', 'engines']
        skip_doc_files = ['index', 'all']
        doc_dir = ['doc', 'ref', 'engines', 'all']
        self._check_doc_files(skip_module_files, module_dir, skip_doc_files, doc_dir)

    def test_fileserver_doc_files(self):
        '''
        Ensure fileserver modules have associated documentation

        doc example: doc/ref/fileserver/all/salt.fileserver.gitfs.rst
        module example: salt/fileserver/gitfs.py
        '''

        skip_module_files = ['__init__']
        module_dir = ['salt', 'fileserver']
        skip_doc_files = ['index', 'all']
        doc_dir = ['doc', 'ref', 'file_server', 'all']
        self._check_doc_files(skip_module_files, module_dir, skip_doc_files, doc_dir)

    def test_grain_doc_files(self):
        '''
        Ensure grain modules have associated documentation

        doc example: doc/ref/grains/all/salt.grains.core.rst
        module example: salt/grains/core.py
        '''

        skip_module_files = ['__init__']
        module_dir = ['salt', 'grains']
        skip_doc_files = ['index', 'all']
        doc_dir = ['doc', 'ref', 'grains', 'all']
        self._check_doc_files(skip_module_files, module_dir, skip_doc_files, doc_dir)

    def test_module_doc_files(self):
        '''
        Ensure modules have associated documentation

        doc example: doc/ref/modules/all/salt.modules.zabbix.rst
        execution module example: salt/modules/zabbix.py
        '''

        skip_module_files = ['__init__']
        module_dir = ['salt', 'modules']
        skip_doc_files = ['index', 'group', 'inspectlib', 'inspectlib.collector', 'inspectlib.dbhandle',
                          'inspectlib.entities', 'inspectlib.exceptions', 'inspectlib.fsdb',
                          'inspectlib.kiwiproc', 'inspectlib.query', 'kernelpkg', 'pkg', 'user']
        doc_dir = ['doc', 'ref', 'modules', 'all']
        self._check_doc_files(skip_module_files, module_dir, skip_doc_files, doc_dir)

    def test_output_doc_files(self):
        '''
        Ensure output modules have associated documentation

        doc example: doc/ref/output/all/salt.output.highstate.rst
        module example: salt/output/highstate.py
        '''

        skip_module_files = ['__init__']
        module_dir = ['salt', 'output']
        skip_doc_files = ['index', 'all']
        doc_dir = ['doc', 'ref', 'output', 'all']
        self._check_doc_files(skip_module_files, module_dir, skip_doc_files, doc_dir)

    def test_pillar_doc_files(self):
        '''
        Ensure pillar modules have associated documentation

        doc example: doc/ref/pillar/all/salt.pillar.cobbler.rst
        module example: salt/pillar/cobbler.py
        '''

        skip_module_files = ['__init__']
        module_dir = ['salt', 'pillar']
        skip_doc_files = ['index', 'all']
        doc_dir = ['doc', 'ref', 'pillar', 'all']
        self._check_doc_files(skip_module_files, module_dir, skip_doc_files, doc_dir)

    def test_proxy_doc_files(self):
        '''
        Ensure proxy modules have associated documentation

        doc example: doc/ref/proxy/all/salt.proxy.docker.rst
        module example: salt/proxy/docker.py
        '''

        skip_module_files = ['__init__']
        module_dir = ['salt', 'proxy']
        skip_doc_files = ['index', 'all']
        doc_dir = ['doc', 'ref', 'proxy', 'all']
        self._check_doc_files(skip_module_files, module_dir, skip_doc_files, doc_dir)

    def test_queues_doc_files(self):
        '''
        Ensure queue modules have associated documentation

        doc example: doc/ref/queues/all/salt.queues.sqlite_queue.rst
        module example: salt/queues/sqlite_queue.py
        '''

        skip_module_files = ['__init__']
        module_dir = ['salt', 'queues']
        skip_doc_files = ['index', 'all']
        doc_dir = ['doc', 'ref', 'queues', 'all']
        self._check_doc_files(skip_module_files, module_dir, skip_doc_files, doc_dir)

    def test_renderers_doc_files(self):
        '''
        Ensure render modules have associated documentation

        doc example: doc/ref/renderers/all/salt.renderers.json.rst
        module example: salt/renderers/json.py
        '''

        skip_module_files = ['__init__']
        module_dir = ['salt', 'renderers']
        skip_doc_files = ['index', 'all']
        doc_dir = ['doc', 'ref', 'renderers', 'all']
        self._check_doc_files(skip_module_files, module_dir, skip_doc_files, doc_dir)

    def test_returners_doc_files(self):
        '''
        Ensure return modules have associated documentation

        doc example: doc/ref/returners/all/salt.returners.cassandra_return.rst
        module example: salt/returners/cassandra_return.py
        '''

        skip_module_files = ['__init__']
        module_dir = ['salt', 'returners']
        skip_doc_files = ['index', 'all']
        doc_dir = ['doc', 'ref', 'returners', 'all']
        self._check_doc_files(skip_module_files, module_dir, skip_doc_files, doc_dir)

    def test_runners_doc_files(self):
        '''
        Ensure runner modules have associated documentation

        doc example: doc/ref/runners/all/salt.runners.auth.rst
        module example: salt/runners/auth.py
        '''

        skip_module_files = ['__init__']
        module_dir = ['salt', 'runners']
        skip_doc_files = ['index', 'all']
        doc_dir = ['doc', 'ref', 'runners', 'all']
        self._check_doc_files(skip_module_files, module_dir, skip_doc_files, doc_dir)

    def test_sdb_doc_files(self):
        '''
        Ensure sdb modules have associated documentation

        doc example: doc/ref/sdb/all/salt.sdb.rest.rst
        module example: salt/sdb/rest.py
        '''

        skip_module_files = ['__init__']
        module_dir = ['salt', 'sdb']
        skip_doc_files = ['index', 'all']
        doc_dir = ['doc', 'ref', 'sdb', 'all']
        self._check_doc_files(skip_module_files, module_dir, skip_doc_files, doc_dir)

    def test_serializers_doc_files(self):
        '''
        Ensure serializer modules have associated documentation

        doc example: doc/ref/serializers/all/salt.serializers.yaml.rst
        module example: salt/serializers/yaml.py
        '''

        skip_module_files = ['__init__']
        module_dir = ['salt', 'serializers']
        skip_doc_files = ['index', 'all']
        doc_dir = ['doc', 'ref', 'serializers', 'all']
        self._check_doc_files(skip_module_files, module_dir, skip_doc_files, doc_dir)

    def test_states_doc_files(self):
        '''
        Ensure states have associated documentation

        doc example: doc/ref/states/all/salt.states.zabbix_host.rst
        module example: salt/states/zabbix_host.py
        '''

        skip_module_files = ['__init__']
        module_dir = ['salt', 'states']
        skip_doc_files = ['index', 'all']
        doc_dir = ['doc', 'ref', 'states', 'all']
        self._check_doc_files(skip_module_files, module_dir, skip_doc_files, doc_dir)

    def test_thorium_doc_files(self):
        '''
        Ensure thorium modules have associated documentation

        doc example: doc/ref/thorium/all/salt.thorium.calc.rst
        module example: salt/thorium/calc.py
        '''

        skip_module_files = ['__init__']
        module_dir = ['salt', 'thorium']
        skip_doc_files = ['index', 'all']
        doc_dir = ['doc', 'ref', 'thorium', 'all']
        self._check_doc_files(skip_module_files, module_dir, skip_doc_files, doc_dir)

    def test_tops_doc_files(self):
        '''
        Ensure top modules have associated documentation

        doc example: doc/ref/tops/all/salt.tops.saltclass.rst
        module example: salt/tops/saltclass.py
        '''

        skip_module_files = ['__init__']
        module_dir = ['salt', 'tops']
        skip_doc_files = ['index', 'all']
        doc_dir = ['doc', 'ref', 'tops', 'all']
        self._check_doc_files(skip_module_files, module_dir, skip_doc_files, doc_dir)

    def test_wheel_doc_files(self):
        '''
        Ensure wheel modules have associated documentation

        doc example: doc/ref/wheel/all/salt.wheel.key.rst
        module example: salt/wheel/key.py
        '''

        skip_module_files = ['__init__']
        module_dir = ['salt', 'wheel']
        skip_doc_files = ['index', 'all']
        doc_dir = ['doc', 'ref', 'wheel', 'all']
        self._check_doc_files(skip_module_files, module_dir, skip_doc_files, doc_dir)
