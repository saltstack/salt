from salt.utils.winservice import Service, instart
import win32serviceutil
import win32service
import winerror
import salt
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

if __name__ == '__main__':
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
