'''
Sceduling routines are located here. To activate the scheduler make the schedule
option available to the master or minion configurations (master config file or
for the minion via config or pillar)

code-block:: yaml

    schedule:
      state.sls:
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

    def option(self, opt):
        '''
        Return the schedule data structure
        '''
        if 'config.option' in self.functions:
            return self.functions['config.option'](opt, {})
        return self.opts.get(opt, {})

    def handle_func(self, func, data):
        '''
        Execute this method in a multiprocess or thread
        '''
        ret = {'id': self.opts['id'],
               'fun': func,
               'jid': '{0:%Y%m%d%H%M%S%f}'.format(datetime.datetime.now())}
        if 'args' in data:
            if 'kwargs' in data:
                ret['return'] = self.functions[func](
                        *data['args'],
                        **data['kwargs'])
            else:
                ret['return'] = self.functions[func](
                        *data['args'],
                        **data['kwargs'])
        else:
            ret['return'] = self.functions[func]()
        if 'returner' in data:
            if data['returner'] in self.returners:
                self.returners[data['returner']](ret)

    def eval(self):
        '''
        Evaluate and execute the schedule
        '''
        schedule = self.option('schedule')
        for func, data in schedule.items():
            if func not in self.functions:
                continue
            # Add up how many seconds between now and then
            seconds = 0
            seconds += int(data.get('seconds', 0))
            seconds += int(data.get('minutes', 0)) * 60
            seconds += int(data.get('hours', 0)) * 3600
            seconds += int(data.get('days', 0)) * 86400
            now = int(time.time())
            run = False
            if func in self.intervals:
                if now - self.intervals[func] > seconds:
                    run = True
            else:
                run = True
            if not run:
                continue
            if self.opts['multiprocessing']:
                thread_cls = multiprocessing.Process
            else:
                thread_cls = threading.Thread
            thread_cls(target=self.handle_func, args=(func, data)).start()
