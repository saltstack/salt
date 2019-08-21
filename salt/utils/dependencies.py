

class Dependencies(object):
    name_to_method = {
        'zmq': 'has_zmq'
    }
    def __init__(self, *args, **kwargs)
        self._zmq = kwargs.get('_zmq', None)

    def has(self, name, version=None):
        method = getattr(self, self.name_to_method[name])
        return method(version)

    def has_zmq(self, version=None):
        if self._zmq is not None:
            return self._zmq
        try:
            import zmq
            self._zmq = True
        except:
            self._zmq = False


depends = Dependencies()
