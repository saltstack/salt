# -*- coding: utf-8 -*-

"""
Tests for the cron state
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import Salt libs
import salt.utils.platform

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf

log = logging.getLogger(__name__)


@skipIf(salt.utils.platform.is_windows(), "minion is windows")
class CronTest(ModuleCase):
    """
    Validate the file state
    """

    def setUp(self):
        """
        Setup
        """
        self.run_state("user.present", name="test_cron_user")

        self.user_primary_group = self.run_function('user.primary_group',
                                                    name='test_cron_user')

    def tearDown(self):
        """
        Teardown
        """
        # Remove cron file
        self.run_function("cmd.run", cmd="crontab -u test_cron_user -r")

        # Delete user
        self.run_state("user.absent", name="test_cron_user")

<<<<<<< HEAD
    def test_46881(self):
        user_id = 'test_cron_user'
        _expected = {
            'changes': {
                'diff': '--- \n+++ \n@@ -1 +1,2 @@\n-\n+# Lines below here are managed by Salt, do not edit\n+@hourly touch /tmp/test-file\n',
                'group': self.user_primary_group,
                'user': user_id,
            },
        }
        ret = self.run_state(
            'cron.file',
            name='salt://issue-46881/cron',
            user=user_id,
        )
        # There are several keys that do not really matter to this test.
        # We could just delete them, but then we lose their contents to
        # aid in debugging (see https://github.com/saltstack/salt/issues/52079)
        ignored_keys = (
            '__id__',
            '__sls__',
            '__run_num__',
            'comment',
            'duration',
            'name',
            'start_time',
            'result',
        )
        id_ = 'cron_|-salt://issue-46881/cron_|-salt://issue-46881/cron_|-file'
        for key in ignored_keys:
            _expected[key] = ret[id_].get(key)
        retchanges = ret[id_].get('changes', {}).get('attrs', None)
        if retchanges is not None:
            _expected['changes']['attrs'] = retchanges
        self.assertDictEqual(
            _expected,
            ret[id_],
=======
    @skipIf(True, "SLOWTEST skip")
    def test_managed(self):
        """
        file.managed
        """
        ret = self.run_state(
            "cron.file", name="salt://issue-46881/cron", user="test_cron_user"
        )
        _expected = "--- \n+++ \n@@ -1 +1,2 @@\n-\n+# Lines below here are managed by Salt, do not edit\n+@hourly touch /tmp/test-file\n"
        self.assertIn(
            "changes",
            ret["cron_|-salt://issue-46881/cron_|-salt://issue-46881/cron_|-file"],
        )
        self.assertIn(
            "diff",
            ret["cron_|-salt://issue-46881/cron_|-salt://issue-46881/cron_|-file"][
                "changes"
            ],
        )
        self.assertEqual(
            _expected,
            ret["cron_|-salt://issue-46881/cron_|-salt://issue-46881/cron_|-file"][
                "changes"
            ]["diff"],
>>>>>>> 8d70836c614efff36c045d0a87f7a94614409610
        )
