# -*- coding: utf-8 -*-
'''
    :copyright: © 2017 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    tests.support.helpers
    ~~~~~~~~~~~~~~~~~~~~~

    Test support helpers
'''

# Import python libs
from __future__ import absolute_import
import time
import inspect
import logging
import functools

# Import 3rd-party libs
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin


log = logging.getLogger(__name__)


def flaky(caller=None, condition=True):
    '''
    Mark a test as flaky. The test will attempt to run five times,
    looking for a successful run. After an immediate second try,
    it will use an exponential backoff starting with one second.

    .. code-block:: python

        class MyTestCase(TestCase):

        @flaky
        def test_sometimes_works(self):
            pass
    '''
    if caller is None:
        return functools.partial(flaky, condition=condition)

    if isinstance(condition, bool) and condition is False:
        # Don't even decorate
        return caller
    elif callable(condition):
        if condition() is False:
            # Don't even decorate
            return caller

    if inspect.isclass(caller):
        attrs = [n for n in dir(caller) if n.startswith('test_')]
        for attrname in attrs:
            try:
                function = getattr(caller, attrname)
                if not inspect.isfunction(function) and not inspect.ismethod(function):
                    continue
                setattr(caller, attrname, flaky(caller=function, condition=condition))
            except Exception as exc:
                log.exception(exc)
                continue
        return caller

    @functools.wraps(caller)
    def wrap(cls):
        for attempt in range(0, 4):
            try:
                return caller(cls)
            except AssertionError as exc:
                if attempt == 4:
                    raise exc
                backoff_time = attempt ** 2
                log.info('Found AssertionError. Waiting %s seconds to retry.', backoff_time)
                time.sleep(backoff_time)
        return cls
    return wrap
