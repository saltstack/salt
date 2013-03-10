# -*- coding: utf-8 -*-
'''
    salt.utils.multiprocess
    ~~~~~~~~~~~~~~~~~~~~~~~

    Work around some known bugs of python's multiprocessing module under 2.6

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import os
import sys
import errno
from multiprocessing import active_children, Process


if sys.version_info < (2, 7):
    # Until salt supports python 2.6 we need to work around some know bugs of
    # the multiprocessing module. For additional information, see:
    #   http://bugs.python.org/issue1731717

    from multiprocessing.forking import Popen as _Popen

    class Popen(_Popen):
        # Let's patch the offending code using the fix provided on python's
        # source code repository
        def poll(self, flag=os.WNOHANG):
            if self.returncode is None:
                while True:
                    try:
                        pid, sts = os.waitpid(self.pid, flag)
                    except OSError as e:
                        if e.errno == errno.EINTR:
                            continue
                        # Child process not yet created. See #1731717
                        # e.errno == errno.ECHILD == 10
                        return None
                    else:
                        break
                if pid == self.pid:
                    if os.WIFSIGNALED(sts):
                        self.returncode = -os.WTERMSIG(sts)
                    else:
                        assert os.WIFEXITED(sts)
                        self.returncode = os.WEXITSTATUS(sts)
            return self.returncode

    Process._Popen = Popen
