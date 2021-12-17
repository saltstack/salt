# pylint: skip-file
from __future__ import absolute_import, division, print_function
from salt.ext.tornado.ioloop import IOLoop
from salt.ext.tornado.netutil import ThreadedResolver

# When this module is imported, it runs getaddrinfo on a thread. Since
# the hostname is unicode, getaddrinfo attempts to import encodings.idna
# but blocks on the import lock. Verify that ThreadedResolver avoids
# this deadlock.

resolver = ThreadedResolver()
IOLoop.current().run_sync(lambda: resolver.resolve(u'localhost', 80))
