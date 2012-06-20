# winservice.py

from os.path import splitext, abspath
from sys import modules

import win32serviceutil
import win32service
import win32event
import win32api


class Service(win32serviceutil.ServiceFramework):

    _svc_name_ = '_unNamed'
    _svc_display_name_ = '_Service Template'

    def __init__(self, *args):
        win32serviceutil.ServiceFramework.__init__(self, *args)
        self.log('init')
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)

    def log(self, msg):
        import servicemanager
        servicemanager.LogInfoMsg(str(msg))

    def sleep(self, sec):
        win32api.Sleep(sec * 1000, True)

    def SvcDoRun(self):
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
        try:
            self.ReportServiceStatus(win32service.SERVICE_RUNNING)
            self.log('start')
            self.start()
            self.log('wait')
            win32event.WaitForSingleObject(self.stop_event,
                                            win32event.INFINITE)
            self.log('done')
        except Exception as x:
            self.log('Exception : %s' % x)
            self.SvcStop()

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.log('stopping')
        self.stop()
        self.log('stopped')
        win32event.SetEvent(self.stop_event)
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)

    # to be overridden
    def start(self):
        pass

    # to be overridden
    def stop(self):
        pass


def instart(cls, name, display_name=None, stay_alive=True):
    '''Install and  Start (auto) a Service

    cls : the class (derived from Service) that implement the Service
    name : Service name
    display_name : the name displayed in the service manager
    stay_alive : Service will stop on logout if False
    '''
    cls._svc_name_ = name
    cls._svc_display_name_ = display_name or name
    try:
        module_path = modules[cls.__module__].__file__
    except AttributeError:
        # maybe py2exe went by
        from sys import executable
        module_path = executable
    module_file = splitext(abspath(module_path))[0]
    cls._svc_reg_class_ = '%s.%s' % (module_file, cls.__name__)
    if stay_alive:
        win32api.SetConsoleCtrlHandler(lambda x: True, True)
    try:
        win32serviceutil.InstallService(
                cls._svc_reg_class_,
                cls._svc_name_,
                cls._svc_display_name_,
                startType=win32service.SERVICE_AUTO_START
                )
        print('Install ok')
        win32serviceutil.StartService(
                cls._svc_name_
                )
        print('Start ok')
    except Exception as x:
        print(str(x))
