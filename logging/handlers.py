#

class LoggingHandler(object):
    def __init__(self, level):
        pass

    def setLevel(self, x):
        pass

    def setFormatter(self, x):
        pass

class TemporaryLoggingHandler(LoggingHandler):
    def __init__(self, level):
        pass


class StreamHandler(LoggingHandler):
    pass

class SysLogHandler(LoggingHandler):
    LOG_USER=10

class WatchedFileHandler(LoggingHandler):
    def __init__(self, log_path, mode, encoding, delay):
        pass

class FileHandler(LoggingHandler):
    def __init__(self, filename=None, log_path=None, mode=None, encoding=None, delay=None):
        pass

class MemoryHandler(LoggingHandler):
    pass

class DatagramHandler(LoggingHandler):
    pass
