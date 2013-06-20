# Import salt libs
from salt.utils.winservice import Service, instart
import salt

# Import third party libs
import win32serviceutil
import win32service
import winerror
import win32api

# Import python libs
import sys


class MinionService(Service):

    def start(self):
        self.runflag = True
        self.log("Starting the Salt Minion")
        minion = salt.Minion()
        minion.start()
        while self.runflag:
            pass
            #self.sleep(10)
            #self.log("I'm alive ...")

    def stop(self):
        self.runflag = False
        self.log("Shutting down the Salt Minion")

def console_event_handler(event):
    if event == 5:
        # Do nothing on CTRL_LOGOFF_EVENT
        return True
    return False

def _main():
    win32api.SetConsoleCtrlHandler(console_event_handler, 1)
    servicename = 'salt-minion'
    try:
        status = win32serviceutil.QueryServiceStatus(servicename)
    except win32service.error as details:
        if details[0] == winerror.ERROR_SERVICE_DOES_NOT_EXIST:
            instart(MinionService, servicename, 'Salt Minion')
            sys.exit(0)
    if status[1] == win32service.SERVICE_RUNNING:
        win32serviceutil.StopServiceWithDeps(servicename)
        win32serviceutil.StartService(servicename)
    else:
        win32serviceutil.StartService(servicename)


if __name__ == '__main__':
    _main()
