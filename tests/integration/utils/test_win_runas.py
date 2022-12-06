import inspect
import logging
import os
import socket
import subprocess
import sys
import textwrap
import threading
import time
import traceback

import pytest
import yaml

import salt.utils.files
import salt.utils.win_runas
from tests.support.case import ModuleCase
from tests.support.helpers import with_system_user
from tests.support.mock import Mock
from tests.support.runtests import RUNTIME_VARS

try:
    import servicemanager
    import win32api
    import win32event
    import win32service
    import win32serviceutil

    CODE_DIR = win32api.GetLongPathName(RUNTIME_VARS.CODE_DIR)
    HAS_WIN32 = True
except ImportError:
    # Mock win32serviceutil object to avoid
    # a stacktrace in the _ServiceManager class
    win32serviceutil = Mock()
    HAS_WIN32 = False

logger = logging.getLogger(__name__)

PASSWORD = "P@ssW0rd"
NOPRIV_STDERR = "ERROR: Logged-on user does not have administrative privilege.\n"
PRIV_STDOUT = (
    "\nINFO: The system global flag 'maintain objects list' needs\n      "
    "to be enabled to see local opened files.\n      See Openfiles "
    "/? for more information.\n\n\nFiles opened remotely via local share "
    "points:\n---------------------------------------------\n\n"
    "INFO: No shared open files found.\n"
)
if HAS_WIN32:
    RUNAS_PATH = os.path.abspath(os.path.join(CODE_DIR, "runas.py"))
    RUNAS_OUT = os.path.abspath(os.path.join(CODE_DIR, "runas.out"))


def default_target(service, *args, **kwargs):
    while service.active:
        time.sleep(service.timeout)


class _ServiceManager(win32serviceutil.ServiceFramework):
    """
    A windows service manager
    """

    _svc_name_ = "Service Manager"
    _svc_display_name_ = "Service Manager"
    _svc_description_ = "A Service Manager"
    run_in_foreground = False
    target = default_target

    def __init__(self, args, target=None, timeout=60, active=True):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.timeout = timeout
        self.active = active
        if target is not None:
            self.target = target

    @classmethod
    def log_error(cls, msg):
        if cls.run_in_foreground:
            logger.error(msg)
        servicemanager.LogErrorMsg(msg)

    @classmethod
    def log_info(cls, msg):
        if cls.run_in_foreground:
            logger.info(msg)
        servicemanager.LogInfoMsg(msg)

    @classmethod
    def log_exception(cls, msg):
        if cls.run_in_foreground:
            logger.exception(msg)
        exc_info = sys.exc_info()
        tb = traceback.format_tb(exc_info[2])
        servicemanager.LogErrorMsg("{} {} {}".format(msg, exc_info[1], tb))

    @property
    def timeout_ms(self):
        return self.timeout * 1000

    def SvcStop(self):
        """
        Stop the service by; terminating any subprocess call, notify
        windows internals of the stop event, set the instance's active
        attribute to 'False' so the run loops stop.
        """
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.active = False

    def SvcDoRun(self):
        """
        Run the monitor in a separete thread so the main thread is
        free to react to events sent to the windows service.
        """
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )
        self.log_info("Starting Service {}".format(self._svc_name_))
        monitor_thread = threading.Thread(target=self.target_thread)
        monitor_thread.start()
        while self.active:
            rc = win32event.WaitForSingleObject(self.hWaitStop, self.timeout_ms)
            if rc == win32event.WAIT_OBJECT_0:
                # Stop signal encountered
                self.log_info("Stopping Service")
                break
            if not monitor_thread.is_alive():
                self.log_info("Update Thread Died, Stopping Service")
                break

    def target_thread(self, *args, **kwargs):
        """
        Target Thread, handles any exception in the target method and
        logs them.
        """
        self.log_info("Monitor")
        try:
            self.target(self, *args, **kwargs)
        except Exception as exc:  # pylint: disable=broad-except
            # TODO: Add traceback info to windows event log objects
            self.log_exception("Exception In Target")

    @classmethod
    def install(cls, username=None, password=None, start_type=None):
        if hasattr(cls, "_svc_reg_class_"):
            svc_class = cls._svc_reg_class_
        else:
            svc_class = win32serviceutil.GetServiceClassString(cls)
        win32serviceutil.InstallService(
            svc_class,
            cls._svc_name_,
            cls._svc_display_name_,
            description=cls._svc_description_,
            userName=username,
            password=password,
            startType=start_type,
        )

    @classmethod
    def remove(cls):
        win32serviceutil.RemoveService(cls._svc_name_)

    @classmethod
    def start(cls):
        win32serviceutil.StartService(cls._svc_name_)

    @classmethod
    def restart(cls):
        win32serviceutil.RestartService(cls._svc_name_)

    @classmethod
    def stop(cls):
        win32serviceutil.StopService(cls._svc_name_)


def service_class_factory(
    cls_name,
    name,
    target=default_target,
    display_name="",
    description="",
    run_in_foreground=False,
):
    frm = inspect.stack()[1]
    mod = inspect.getmodule(frm[0])
    return type(
        cls_name,
        (_ServiceManager, object),
        {
            "__module__": mod.__name__,
            "_svc_name_": name,
            "_svc_display_name_": display_name or name,
            "_svc_description_": description,
            "run_in_foreground": run_in_foreground,
            "target": target,
        },
    )


if HAS_WIN32:
    test_service = service_class_factory("test_service", "test service")


SERVICE_SOURCE = """
from __future__ import absolute_import, unicode_literals
import logging
logger = logging.getLogger()
logging.basicConfig(level=logging.DEBUG, format="%(message)s")

from tests.integration.utils.test_win_runas import service_class_factory
import salt.utils.win_runas
import sys
import yaml

OUTPUT = {}
USERNAME = '{}'
PASSWORD = '{}'


def target(service, *args, **kwargs):
    service.log_info("target start")
    if PASSWORD:
        ret = salt.utils.win_runas.runas(
            'cmd.exe /C OPENFILES',
            username=USERNAME,
            password=PASSWORD,
        )
    else:
        ret = salt.utils.win_runas.runas(
            'cmd.exe /C OPENFILES',
            username=USERNAME,
        )

    service.log_info("win_runas returned %s" % ret)
    with salt.utils.files.fopen(OUTPUT, 'w') as fp:
        yaml.dump(ret, fp)
    service.log_info("target stop")


# This class will get imported and run as the service
test_service = service_class_factory('test_service', 'test service', target=target)

if __name__ == '__main__':
    try:
        test_service.stop()
    except Exception as exc:  # pylint: disable=broad-except
        logger.debug("stop service failed, this is ok.")
    try:
        test_service.remove()
    except Exception as exc:  # pylint: disable=broad-except
        logger.debug("remove service failed, this os ok.")
    test_service.install()
    sys.exit(0)
"""


def wait_for_service(name, timeout=200):
    start = time.time()
    while True:
        status = win32serviceutil.QueryServiceStatus(name)
        if status[1] == win32service.SERVICE_STOPPED:
            break
        if time.time() - start > timeout:
            raise TimeoutError(
                "Timeout waiting for service"
            )  # pylint: disable=undefined-variable

        time.sleep(0.3)


@pytest.mark.skipif(not HAS_WIN32, reason="This test runs only on windows.")
class RunAsTest(ModuleCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.hostname = socket.gethostname()

    @with_system_user(
        "test-runas", on_existing="delete", delete=True, password=PASSWORD
    )
    def test_runas(self, username):
        ret = salt.utils.win_runas.runas("cmd.exe /C OPENFILES", username, PASSWORD)
        self.assertEqual(ret["stdout"], "")
        self.assertEqual(ret["stderr"], NOPRIV_STDERR)
        self.assertEqual(ret["retcode"], 1)

    @with_system_user(
        "test-runas", on_existing="delete", delete=True, password=PASSWORD
    )
    def test_runas_no_pass(self, username):
        ret = salt.utils.win_runas.runas("cmd.exe /C OPENFILES", username)
        self.assertEqual(ret["stdout"], "")
        self.assertEqual(ret["stderr"], NOPRIV_STDERR)
        self.assertEqual(ret["retcode"], 1)

    @with_system_user(
        "test-runas-admin",
        on_existing="delete",
        delete=True,
        password=PASSWORD,
        groups=["Administrators"],
    )
    def test_runas_admin(self, username):
        ret = salt.utils.win_runas.runas("cmd.exe /C OPENFILES", username, PASSWORD)
        self.assertEqual(ret["stdout"], PRIV_STDOUT)
        self.assertEqual(ret["stderr"], "")
        self.assertEqual(ret["retcode"], 0)

    @with_system_user(
        "test-runas-admin",
        on_existing="delete",
        delete=True,
        password=PASSWORD,
        groups=["Administrators"],
    )
    def test_runas_admin_no_pass(self, username):
        ret = salt.utils.win_runas.runas("cmd.exe /C OPENFILES", username)
        self.assertEqual(ret["stdout"], PRIV_STDOUT)
        self.assertEqual(ret["stderr"], "")
        self.assertEqual(ret["retcode"], 0)

    def test_runas_system_user(self):
        ret = salt.utils.win_runas.runas("cmd.exe /C OPENFILES", "SYSTEM")
        self.assertEqual(ret["stdout"], PRIV_STDOUT)
        self.assertEqual(ret["stderr"], "")
        self.assertEqual(ret["retcode"], 0)

    def test_runas_network_service(self):
        ret = salt.utils.win_runas.runas("cmd.exe /C OPENFILES", "NETWORK SERVICE")
        self.assertEqual(ret["stdout"], "")
        self.assertEqual(ret["stderr"], NOPRIV_STDERR)
        self.assertEqual(ret["retcode"], 1)

    def test_runas_local_service(self):
        ret = salt.utils.win_runas.runas("cmd.exe /C OPENFILES", "LOCAL SERVICE")
        self.assertEqual(ret["stdout"], "")
        self.assertEqual(ret["stderr"], NOPRIV_STDERR)
        self.assertEqual(ret["retcode"], 1)

    @with_system_user(
        "test-runas", on_existing="delete", delete=True, password=PASSWORD
    )
    def test_runas_winrs(self, username):
        runaspy = textwrap.dedent(
            """
        import sys
        import salt.utils.win_runas
        username = '{}'
        password = '{}'
        sys.exit(salt.utils.win_runas.runas('cmd.exe /C OPENFILES', username, password)['retcode'])
        """.format(
                username, PASSWORD
            )
        )
        with salt.utils.files.fopen(RUNAS_PATH, "w") as fp:
            fp.write(runaspy)
        ret = subprocess.call(
            [
                "cmd.exe",
                "/C",
                "winrs",
                "/r:{}".format(self.hostname),
                "python",
                RUNAS_PATH,
            ]
        )
        self.assertEqual(ret, 1)

    @with_system_user(
        "test-runas", on_existing="delete", delete=True, password=PASSWORD
    )
    def test_runas_winrs_no_pass(self, username):
        runaspy = textwrap.dedent(
            """
        import sys
        import salt.utils.win_runas
        username = '{}'
        sys.exit(salt.utils.win_runas.runas('cmd.exe /C OPENFILES', username)['retcode'])
        """.format(
                username
            )
        )
        with salt.utils.files.fopen(RUNAS_PATH, "w") as fp:
            fp.write(runaspy)
        ret = subprocess.call(
            [
                "cmd.exe",
                "/C",
                "winrs",
                "/r:{}".format(self.hostname),
                "python",
                RUNAS_PATH,
            ]
        )
        self.assertEqual(ret, 1)

    @with_system_user(
        "test-runas-admin",
        on_existing="delete",
        delete=True,
        password=PASSWORD,
        groups=["Administrators"],
    )
    def test_runas_winrs_admin(self, username):
        runaspy = textwrap.dedent(
            """
        import sys
        import salt.utils.win_runas
        username = '{}'
        password = '{}'
        sys.exit(salt.utils.win_runas.runas('cmd.exe /C OPENFILES', username, password)['retcode'])
        """.format(
                username, PASSWORD
            )
        )
        with salt.utils.files.fopen(RUNAS_PATH, "w") as fp:
            fp.write(runaspy)
        ret = subprocess.call(
            [
                "cmd.exe",
                "/C",
                "winrs",
                "/r:{}".format(self.hostname),
                "python",
                RUNAS_PATH,
            ]
        )
        self.assertEqual(ret, 0)

    @with_system_user(
        "test-runas-admin",
        on_existing="delete",
        delete=True,
        password=PASSWORD,
        groups=["Administrators"],
    )
    def test_runas_winrs_admin_no_pass(self, username):
        runaspy = textwrap.dedent(
            """
        import sys
        import salt.utils.win_runas
        username = '{}'
        sys.exit(salt.utils.win_runas.runas('cmd.exe /C OPENFILES', username)['retcode'])
        """.format(
                username
            )
        )
        with salt.utils.files.fopen(RUNAS_PATH, "w") as fp:
            fp.write(runaspy)
        ret = subprocess.call(
            [
                "cmd.exe",
                "/C",
                "winrs",
                "/r:{}".format(self.hostname),
                "python",
                RUNAS_PATH,
            ]
        )
        self.assertEqual(ret, 0)

    def test_runas_winrs_system_user(self):
        runaspy = textwrap.dedent(
            """
        import sys
        import salt.utils.win_runas
        sys.exit(salt.utils.win_runas.runas('cmd.exe /C OPENFILES', 'SYSTEM')['retcode'])
        """
        )
        with salt.utils.files.fopen(RUNAS_PATH, "w") as fp:
            fp.write(runaspy)
        ret = subprocess.call(
            [
                "cmd.exe",
                "/C",
                "winrs",
                "/r:{}".format(self.hostname),
                "python",
                RUNAS_PATH,
            ]
        )
        self.assertEqual(ret, 0)

    def test_runas_winrs_network_service_user(self):
        runaspy = textwrap.dedent(
            """
        import sys
        import salt.utils.win_runas
        sys.exit(salt.utils.win_runas.runas('cmd.exe /C OPENFILES', 'NETWORK SERVICE')['retcode'])
        """
        )
        with salt.utils.files.fopen(RUNAS_PATH, "w") as fp:
            fp.write(runaspy)
        ret = subprocess.call(
            [
                "cmd.exe",
                "/C",
                "winrs",
                "/r:{}".format(self.hostname),
                "python",
                RUNAS_PATH,
            ]
        )
        self.assertEqual(ret, 1)

    def test_runas_winrs_local_service_user(self):
        runaspy = textwrap.dedent(
            """
        import sys
        import salt.utils.win_runas
        sys.exit(salt.utils.win_runas.runas('cmd.exe /C OPENFILES', 'LOCAL SERVICE')['retcode'])
        """
        )
        with salt.utils.files.fopen(RUNAS_PATH, "w") as fp:
            fp.write(runaspy)
        ret = subprocess.call(
            [
                "cmd.exe",
                "/C",
                "winrs",
                "/r:{}".format(self.hostname),
                "python",
                RUNAS_PATH,
            ]
        )
        self.assertEqual(ret, 1)

    @with_system_user(
        "test-runas", on_existing="delete", delete=True, password=PASSWORD
    )
    def test_runas_powershell_remoting(self, username):
        runaspy = textwrap.dedent(
            """
        import sys
        import salt.utils.win_runas
        username = '{}'
        password = '{}'
        sys.exit(salt.utils.win_runas.runas('cmd.exe /C OPENFILES', username, password)['retcode'])
        """.format(
                username, PASSWORD
            )
        )
        with salt.utils.files.fopen(RUNAS_PATH, "w") as fp:
            fp.write(runaspy)
        ret = subprocess.call(
            [
                "powershell",
                "Invoke-Command",
                "-ComputerName",
                self.hostname,
                "-ScriptBlock",
                "{{ python.exe {} }}".format(RUNAS_PATH),
            ]
        )
        self.assertEqual(ret, 1)

    @with_system_user(
        "test-runas", on_existing="delete", delete=True, password=PASSWORD
    )
    def test_runas_powershell_remoting_no_pass(self, username):
        runaspy = textwrap.dedent(
            """
        import sys
        import salt.utils.win_runas
        username = '{}'
        sys.exit(salt.utils.win_runas.runas('cmd.exe /C OPENFILES', username)['retcode'])
        """.format(
                username
            )
        )
        with salt.utils.files.fopen(RUNAS_PATH, "w") as fp:
            fp.write(runaspy)
        ret = subprocess.call(
            [
                "powershell",
                "Invoke-Command",
                "-ComputerName",
                self.hostname,
                "-ScriptBlock",
                "{{ python.exe {} }}".format(RUNAS_PATH),
            ]
        )
        self.assertEqual(ret, 1)

    @with_system_user(
        "test-runas-admin",
        on_existing="delete",
        delete=True,
        password=PASSWORD,
        groups=["Administrators"],
    )
    def test_runas_powershell_remoting_admin(self, username):
        psrp_wrap = (
            "powershell Invoke-Command -ComputerName {} -ScriptBlock {{ {} }}; exit"
            " $LASTEXITCODE"
        )
        runaspy = textwrap.dedent(
            """
        import sys
        import salt.utils.win_runas
        username = '{}'
        password = '{}'
        ret = salt.utils.win_runas.runas('cmd.exe /C OPENFILES', username, password)
        sys.exit(ret['retcode'])
        """.format(
                username, PASSWORD
            )
        )
        with salt.utils.files.fopen(RUNAS_PATH, "w") as fp:
            fp.write(runaspy)
        cmd = "python.exe {}; exit $LASTEXITCODE".format(RUNAS_PATH)
        ret = subprocess.call(psrp_wrap.format(self.hostname, cmd), shell=True)  # nosec
        self.assertEqual(ret, 0)

    @with_system_user(
        "test-runas-admin",
        on_existing="delete",
        delete=True,
        password=PASSWORD,
        groups=["Administrators"],
    )
    def test_runas_powershell_remoting_admin_no_pass(self, username):
        psrp_wrap = (
            "powershell Invoke-Command -ComputerName {} -ScriptBlock {{ {} }}; exit"
            " $LASTEXITCODE"
        )
        runaspy = textwrap.dedent(
            """
        import sys
        import salt.utils.win_runas
        username = '{}'
        sys.exit(salt.utils.win_runas.runas('cmd.exe /C OPENFILES', username)['retcode'])
        """.format(
                username
            )
        )
        with salt.utils.files.fopen(RUNAS_PATH, "w") as fp:
            fp.write(runaspy)
        cmd = "python.exe {}; exit $LASTEXITCODE".format(RUNAS_PATH)
        ret = subprocess.call(psrp_wrap.format(self.hostname, cmd), shell=True)  # nosec
        self.assertEqual(ret, 0)

    @with_system_user(
        "test-runas", on_existing="delete", delete=True, password=PASSWORD
    )
    def test_runas_service(self, username, timeout=200):
        if os.path.exists(RUNAS_OUT):
            os.remove(RUNAS_OUT)
        assert not os.path.exists(RUNAS_OUT)
        runaspy = SERVICE_SOURCE.format(repr(RUNAS_OUT), username, PASSWORD)
        with salt.utils.files.fopen(RUNAS_PATH, "w", encoding="utf-8") as fp:
            fp.write(runaspy)
        ret = subprocess.call(["python.exe", RUNAS_PATH])
        self.assertEqual(ret, 0)
        win32serviceutil.StartService("test service")
        wait_for_service("test service")
        with salt.utils.files.fopen(RUNAS_OUT, "r") as fp:
            ret = yaml.load(fp)
        assert ret["retcode"] == 1, ret

    @with_system_user(
        "test-runas", on_existing="delete", delete=True, password=PASSWORD
    )
    def test_runas_service_no_pass(self, username, timeout=200):
        if os.path.exists(RUNAS_OUT):
            os.remove(RUNAS_OUT)
        assert not os.path.exists(RUNAS_OUT)
        runaspy = SERVICE_SOURCE.format(repr(RUNAS_OUT), username, "")
        with salt.utils.files.fopen(RUNAS_PATH, "w", encoding="utf-8") as fp:
            fp.write(runaspy)
        ret = subprocess.call(["python.exe", RUNAS_PATH])
        self.assertEqual(ret, 0)
        win32serviceutil.StartService("test service")
        wait_for_service("test service")
        with salt.utils.files.fopen(RUNAS_OUT, "r") as fp:
            ret = yaml.load(fp)
        assert ret["retcode"] == 1, ret

    @with_system_user(
        "test-runas-admin",
        on_existing="delete",
        delete=True,
        password=PASSWORD,
        groups=["Administrators"],
    )
    def test_runas_service_admin(self, username, timeout=200):
        if os.path.exists(RUNAS_OUT):
            os.remove(RUNAS_OUT)
        assert not os.path.exists(RUNAS_OUT)
        runaspy = SERVICE_SOURCE.format(repr(RUNAS_OUT), username, PASSWORD)
        with salt.utils.files.fopen(RUNAS_PATH, "w", encoding="utf-8") as fp:
            fp.write(runaspy)
        ret = subprocess.call(["python.exe", RUNAS_PATH])
        self.assertEqual(ret, 0)
        win32serviceutil.StartService("test service")
        wait_for_service("test service")
        with salt.utils.files.fopen(RUNAS_OUT, "r") as fp:
            ret = yaml.load(fp)
        assert ret["retcode"] == 0, ret

    @with_system_user(
        "test-runas-admin",
        on_existing="delete",
        delete=True,
        password=PASSWORD,
        groups=["Administrators"],
    )
    def test_runas_service_admin_no_pass(self, username, timeout=200):
        if os.path.exists(RUNAS_OUT):
            os.remove(RUNAS_OUT)
        assert not os.path.exists(RUNAS_OUT)
        runaspy = SERVICE_SOURCE.format(repr(RUNAS_OUT), username, "")
        with salt.utils.files.fopen(RUNAS_PATH, "w", encoding="utf-8") as fp:
            fp.write(runaspy)
        ret = subprocess.call(["python.exe", RUNAS_PATH])
        self.assertEqual(ret, 0)
        win32serviceutil.StartService("test service")
        wait_for_service("test service")
        with salt.utils.files.fopen(RUNAS_OUT, "r") as fp:
            ret = yaml.load(fp)
        assert ret["retcode"] == 0, ret

    def test_runas_service_system_user(self):
        if os.path.exists(RUNAS_OUT):
            os.remove(RUNAS_OUT)
        assert not os.path.exists(RUNAS_OUT)
        runaspy = SERVICE_SOURCE.format(repr(RUNAS_OUT), "SYSTEM", "")
        with salt.utils.files.fopen(RUNAS_PATH, "w", encoding="utf-8") as fp:
            fp.write(runaspy)
        ret = subprocess.call(["python.exe", RUNAS_PATH])
        self.assertEqual(ret, 0)
        win32serviceutil.StartService("test service")
        wait_for_service("test service")
        with salt.utils.files.fopen(RUNAS_OUT, "r") as fp:
            ret = yaml.load(fp)
        assert ret["retcode"] == 0, ret
