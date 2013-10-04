# -*- coding: utf-8 -*-

# Import python libs
import logging
import pythoncom
import threading

log = logging.getLogger(__name__)


class Com(object):
    def __init__(self):
        self.need_com_init = not self._is_main_thread()

    def _is_main_thread(self):
        return threading.current_thread().name == 'MainThread'

    def __enter__(self):
        if self.need_com_init:
            log.debug('Initializing COM library')
            pythoncom.CoInitialize()

    def __exit__(self, exc_type, exc_value, traceback):
        if self.need_com_init:
            log.debug('Uninitializing COM library')
            pythoncom.CoUninitialize()
