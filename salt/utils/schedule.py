'''
Sceduling routines are located here. To activate the scheduler make the schedule
option available to the master or minion configurations (master config file or
for the minion via config or pillar)

code-block:: yaml

    schedule:
      job1:
        function: state.sls
        seconds: 3600
        args:
          - httpd
        kwargs:
          test: True

This will schedule the command: state.sls httpd test=True every 3600 seconds 
(every hour)
'''

# Import python libs
import time
import datetime
import multiprocessing
import threading
import sys


class Schedule(object):
    '''
    Create a Schedule object, pass in the opts and the functions dict to use 
    '''
    def __init__(self, opts, functions, returners=None, intervals=None):
        self.opts = opts
        self.functions = functions
        if isinstance(intervals, dict):
            self.intervals = intervals
        else:
            self.intervals = {}
        if isinstance(returners, dict):
            self.returners = returners
        else:
            self.returners = {}
        self.schedule_returner = self.option('schedule_returner')
        # Keep track of the lowest loop interval needed in this variable
        self.loop_interval = sys.maxint

    def option(self, opt):
        '''
        Return the schedule data structure
        '''
        if 'config.option' in self.functions:
            return self.functions['config.option'](opt, {}, omit_master=True)
        return self.opts.get(opt, {})

    def handle_func(self, func, data):
        '''
        Execute this method in a multiprocess or thread
        '''
        ret = {'id': self.opts.get('id', 'master'),
               'fun': func,
               'jid': '{0:%Y%m%d%H%M%S%f}'.format(datetime.datetime.now())}
        if 'args' in data:
            if 'kwargs' in data:
                ret['return'] = self.functions[func](
                        *data['args'],
                        **data['kwargs'])
            else:
                ret['return'] = self.functions[func](
                        *data['args'])
        else:
            ret['return'] = self.functions[func]()
        if 'returner' in data or self.schedule_returner:
            rets = []
            if isinstance(data['returner'], str):
                rets.append(data['returner'])
            elif isinstance(data['returner'], list):
                for returner in data['returner']:
                    if not returner in rets:
                        rets.append(returner)
            if isinstance(self.schedule_returner, list):
                for returner in self.schedule_returner:
                    if not returner in rets:
                        rets.append(returner)
            if isinstance(self.schedule_returner, str):
                if not self.schedule_returner in rets:
                    rets.append(self.schedule_returner)
            for returner in rets:
                if returner in self.returners:
                    self.returners[returner](ret)

    def eval(self):
        '''
        Evaluate and execute the schedule
        '''
        schedule = self.option('schedule')
        if not isinstance(schedule, dict):
            return
        for job, data in schedule.items():
            if 'function' in data:
                func = data['function']
            elif 'func' in data:
                func = data['func']
            elif 'fun' in data:
                func = data['fun']
            else:
                func = None
            if func not in self.functions:
                continue
            # Add up how many seconds between now and then
            seconds = 0
            seconds += int(data.get('seconds', 0))
            seconds += int(data.get('minutes', 0)) * 60
            seconds += int(data.get('hours', 0)) * 3600
            seconds += int(data.get('days', 0)) * 86400
            # Check if the seconds variable is lower than current lowest
            # loop interval needed. If it is lower then overwrite variable
            # external loops using can then check this variable for how often
            # they need to reschedule themselves
            if seconds < self.loop_interval:
                self.loop_interval = seconds
            now = int(time.time())
            run = False
            if job in self.intervals:
                if now - self.intervals[job] > seconds:
                    run = True
            else:
                run = True
            if not run:
                continue
            if self.opts.get('multiprocessing', True):
                thread_cls = multiprocessing.Process
            else:
                thread_cls = threading.Thread
            thread_cls(target=self.handle_func, args=(func, data)).start()
            self.intervals[job] = int(time.time())
