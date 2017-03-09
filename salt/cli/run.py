# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import absolute_import

from salt.utils import parsers
from salt.utils import activate_profile
from salt.utils import output_profile
from salt.utils.verify import check_user, verify_log
from salt.exceptions import SaltClientError
import salt.defaults.exitcodes  # pylint: disable=W0611


class SaltRun(parsers.SaltRunOptionParser):
    '''
    Used to execute Salt runners
    '''

    def run(self):
        '''
        Execute salt-run
        '''
        import salt.runner
        self.parse_args()

        # Setup file logging!
        self.setup_logfile_logger()
        verify_log(self.config)
        profiling_enabled = self.options.profiling_enabled

        runner = salt.runner.Runner(self.config)
        if self.options.doc:
            runner.print_docs()
            self.exit(salt.defaults.exitcodes.EX_OK)

        # Run this here so SystemExit isn't raised anywhere else when
        # someone tries to use the runners via the python API
        try:
            if check_user(self.config['user']):
                pr = activate_profile(profiling_enabled)
                try:
                    ret = runner.run()
                    # In older versions ret['data']['retcode'] was used
                    # for signaling the return code. This has been
                    # changed for the orchestrate runner, but external
                    # runners might still use it. For this reason, we
                    # also check ret['data']['retcode'] if
                    # ret['retcode'] is not available.
                    if isinstance(ret, dict) and 'retcode' in ret:
                        self.exit(ret['retcode'])
                    elif isinstance(ret, dict) and 'retcode' in ret.get('data', {}):
                        self.exit(ret['data']['retcode'])
                finally:
                    output_profile(
                        pr,
                        stats_path=self.options.profiling_path,
                        stop=True)

        except SaltClientError as exc:
            raise SystemExit(str(exc))
