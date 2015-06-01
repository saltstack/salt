.. _ext_processes:

===============================
Running Custom Master Processes
===============================

In addition to the processes that the Salt Master automatically spawns,
it is possible to configure it to start additional custom processes.

This is useful if a dedicated process is needed that should run throughout
the life of the Salt Master. For periodic independent tasks, a
:doc:`scheduled runner <../jobs/schedule.rst>` may be more appropriate.

Processes started in this way will be restarted if they die and will be
killed when the Salt Master is shut down.


Example Configuration
======================

Processes are declared in the master config file with the `ext_processes`
option. Processes will be started in the order they are declared.

.. code-block:: yaml

    ext_processes:
      - mymodule.TestProcess
      - mymodule.AnotherProcess


Example Process Class
=====================

.. code-block:: python

    # Import python libs
    import time
    import logging
    from multiprocessing import Process

    # Import Salt libs
    from salt.utils.event import SaltEvent


    log = logging.getLogger(__name__)


    class TestProcess(Process):
        def __init__(self, opts):
            Process.__init__(self)
            self.opts = opts

        def run(self):
            self.event = SaltEvent('master', self.opts['sock_dir'])
            i = 0

            while True:
                self.event.fire_event({'iteration': i}, 'ext_processes/test{0}')
                time.sleep(60)
