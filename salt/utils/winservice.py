# -*- coding: utf-8 -*-
# winservice.py

# Import python libs
from __future__ import print_function
from __future__ import absolute_import
from os.path import splitext, abspath
from sys import modules

# Import third party libs
try:
    import win32serviceutil
    import win32service
    import win32event
    import win32api
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


# Although utils are often directly imported, it is also possible to use the
# loader.
def __virtual__():
    '''
    Only load if Win32 Libraries are installed
    '''
    if not HAS_WIN32:
        return False, 'This utility requires pywin32'

    return 'winservice'


def service(instantiated=True):
    '''
    Helper function to return an instance of the ServiceFramework class

    Args:
        instantiated (bool): True to return an instantiated object, False to
            return the object definition. Use False if inherited by another
            class. Default is True.

    Returns:
        class: An instance of the ServiceFramework class
    '''
    if not HAS_WIN32:
        return

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

        def SvcDoRun(self):  # pylint: disable=C0103
            self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
            try:
                self.ReportServiceStatus(win32service.SERVICE_RUNNING)
                self.log('start')
                self.start()
                self.log('wait')
                win32event.WaitForSingleObject(self.stop_event,
                                               win32event.INFINITE)
                self.log('done')
            except Exception as err:
                self.log('Exception: {0}'.format(err))
                self.SvcStop()

        def SvcStop(self):  # pylint: disable=C0103
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

    return Service() if instantiated else Service


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
    cls._svc_reg_class_ = '{0}.{1}'.format(module_file, cls.__name__)
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
    except Exception as err:
        print(str(err))
