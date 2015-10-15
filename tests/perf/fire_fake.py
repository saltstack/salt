# -*- encoding: utf-8 -**

from __future__ import absolute_import
# Import system libs
import sys
import time
import datetime

# Import salt libs
import salt.config
import salt.client.raet


try:
    opts = salt.config.master_config('/etc/salt/master')
except OSError:
    print 'Could not open master config. Do you need to be root?'
    sys.exit(1)


class SwarmController(object):
    '''
    A controlling class for instantiating and controlling worker procs
    '''
    def __init__(self, opts):
        self.opts = opts
        self.client = salt.client.raet.LocalClient(mopts=opts)
        self.total_complete = 0

        self.run_time = 90  # The number of seconds to run for
        self.reqs_sec = 5000  # The number of requests / second to shoot for
        self.granularity = 200  # Re-calibrate once for this many runs
        self.period_sleep = 0.01  # The number of seconds to initially sleep between pubs
        self.ramp_sleep = 0.001  # The number of seconds to ramp up up or down by per calibration
        self.start_time = None  # The timestamp for the initiation of the test run

    def run(self):
        '''
        Run the sequence in a loop
        '''
        last_check = 0
        self.start_time = datetime.datetime.now()
        goal = self.reqs_sec * self.run_time
        while True:
            self.fire_it()
            last_check += 1
            if last_check > self.granularity:
                self.calibrate()
                last_check = 0
            if self.total_complete > goal:
                print 'Test complete'
                break

    def fire_it(self):
        '''
        Send the pub!
        '''
        self.client.pub('silver', 'test.ping')
        self.total_complete += 1

    def calibrate(self):
        '''
        Re-calibrate the speed
        '''
        elapsed_time = datetime.datetime.now() - self.start_time
        #remaining_time = self.run_time - elapsed_time
        #remaining_requests = (self.reqs_sec * self.run_time) - self.total_complete
        # Figure out what the reqs/sec has been up to this point and then adjust up or down
        runtime_reqs_sec = self.total_complete / elapsed_time.total_seconds()
        print 'Recalibrating. Current reqs/sec: {0}'.format(runtime_reqs_sec)
        return

controller = SwarmController(opts)
controller.run()
