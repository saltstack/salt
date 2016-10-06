class Stub(object):
    '''
    Class that returns stub message on anything.
    This shouldn't be happening to the end-user
    and indicates always a programming error.
    '''

    def __getattr__(self, item):
        def stub(*args, **kwargs):
            return {'error': 'If you got here, your method is missing and you are in nowhere. :)'}

        return stub
