# -*- coding: utf-8 -*-
'''
Utilities for working with etcd

.. versionadded:: 2014.7.0

:depends:  - python-etcd

This library sets up a client object for etcd, using the configuration passed
into the client() function. Normally, this is __opts__. Optionally, a profile
may be passed in. The following configurations are both valid:

.. code-block:: yaml

    # No profile name
    etcd.host: 127.0.0.1
    etcd.port: 4001
    etcd.username: larry  # Optional; requires etcd.password to be set
    etcd.password: 123pass  # Optional; requires etcd.username to be set
    etcd.ca: /path/to/your/ca_cert/ca.pem # Optional
    etcd.client_key: /path/to/your/client_key/client-key.pem # Optional; requires etcd.ca and etcd.client_cert to be set
    etcd.client_cert: /path/to/your/client_cert/client.pem # Optional; requires etcd.ca and etcd.client_key to be set

    # One or more profiles defined
    my_etcd_config:
      etcd.host: 127.0.0.1
      etcd.port: 4001
      etcd.username: larry  # Optional; requires etcd.password to be set
      etcd.password: 123pass  # Optional; requires etcd.username to be set
      etcd.ca: /path/to/your/ca_cert/ca.pem # Optional
      etcd.client_key: /path/to/your/client_key/client-key.pem # Optional; requires etcd.ca and etcd.client_cert to be set
      etcd.client_cert: /path/to/your/client_cert/client.pem # Optional; requires etcd.ca and etcd.client_key to be set

Once configured, the client() function is passed a set of opts, and optionally,
the name of a profile to be used.

.. code-block:: python

    import salt.utils.etcd_utils
    client = salt.utils.etcd_utils.client(__opts__, profile='my_etcd_config')

You may also use the newer syntax and bypass the generator function.

.. code-block:: python

    import salt.utils.etcd_utils
    client = salt.utils.etcd_utils.EtcdClient(__opts__, profile='my_etcd_config')

It should be noted that some usages of etcd require a profile to be specified,
rather than top-level configurations. This being the case, it is better to
always use a named configuration profile, as shown above.
'''
from __future__ import absolute_import, unicode_literals, print_function

# Import python libs
import logging

# Import salt libs
from salt.ext import six
from salt.exceptions import CommandExecutionError

# Import third party libs
try:
    import etcd
    from urllib3.exceptions import ReadTimeoutError, MaxRetryError
    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

# Set up logging
log = logging.getLogger(__name__)


class EtcdUtilWatchTimeout(Exception):
    """
    A watch timed out without returning a result
    """
    pass


class EtcdClient(object):
    def __init__(self, opts, profile=None,
                 host=None, port=None, username=None, password=None, ca=None, client_key=None, client_cert=None, **kwargs):
        opts_pillar = opts.get('pillar', {})
        opts_master = opts_pillar.get('master', {})

        opts_merged = {}
        opts_merged.update(opts_master)
        opts_merged.update(opts_pillar)
        opts_merged.update(opts)

        if profile:
            self.conf = opts_merged.get(profile, {})
        else:
            self.conf = opts_merged

        host = host or self.conf.get('etcd.host', '127.0.0.1')
        port = port or self.conf.get('etcd.port', 4001)
        username = username or self.conf.get('etcd.username')
        password = password or self.conf.get('etcd.password')
        ca_cert = ca or self.conf.get('etcd.ca')
        cli_key = client_key or self.conf.get('etcd.client_key')
        cli_cert = client_cert or self.conf.get('etcd.client_cert')

        auth = {}
        if username and password:
            auth = {
                'username': six.text_type(username),
                'password': six.text_type(password)
            }

        certs = {}
        if ca_cert and not (cli_cert or cli_key):
            certs = {
                'ca_cert': six.text_type(ca_cert),
                'protocol': 'https'
            }

        if ca_cert and cli_cert and cli_key:
            cert = (cli_cert, cli_key)
            certs = {
                'ca_cert': six.text_type(ca_cert),
                'cert': cert,
                'protocol': 'https'
            }

        xargs = auth.copy()
        xargs.update(certs)

        if HAS_LIBS:
            self.client = etcd.Client(host, port, **xargs)
        else:
            raise CommandExecutionError(
                '(unable to import etcd, '
                'module most likely not installed)'
            )

    def watch(self, key, recurse=False, timeout=0, index=None):
        ret = {
            'key': key,
            'value': None,
            'changed': False,
            'mIndex': 0,
            'dir': False
        }
        try:
            result = self.read(key, recursive=recurse, wait=True, timeout=timeout, waitIndex=index)
        except EtcdUtilWatchTimeout:
            try:
                result = self.read(key)
            except etcd.EtcdKeyNotFound:
                log.debug("etcd: key was not created while watching")
                return ret
            except ValueError:
                return {}
            if result and getattr(result, "dir"):
                ret['dir'] = True
            ret['value'] = getattr(result, 'value')
            ret['mIndex'] = getattr(result, 'modifiedIndex')
            return ret
        except (etcd.EtcdConnectionFailed, MaxRetryError):
            # This gets raised when we can't contact etcd at all
            log.error("etcd: failed to perform 'watch' operation on key %s due to connection error", key)
            return {}
        except ValueError:
            return {}

        if result is None:
            return {}

        if recurse:
            ret['key'] = getattr(result, 'key', None)
        ret['value'] = getattr(result, 'value', None)
        ret['dir'] = getattr(result, 'dir', None)
        ret['changed'] = True
        ret['mIndex'] = getattr(result, 'modifiedIndex')
        return ret

    def get(self, key, recurse=False):
        try:
            result = self.read(key, recursive=recurse)
        except etcd.EtcdKeyNotFound:
            # etcd already logged that the key wasn't found, no need to do
            # anything here but return
            return None
        except etcd.EtcdConnectionFailed:
            log.error("etcd: failed to perform 'get' operation on key %s due to connection error", key)
            return None
        except ValueError:
            return None

        return getattr(result, 'value', None)

    def read(self, key, recursive=False, wait=False, timeout=None, waitIndex=None):
        try:
            if waitIndex:
                result = self.client.read(key, recursive=recursive, wait=wait, timeout=timeout, waitIndex=waitIndex)
            else:
                result = self.client.read(key, recursive=recursive, wait=wait, timeout=timeout)
        except (etcd.EtcdConnectionFailed, etcd.EtcdKeyNotFound) as err:
            log.error("etcd: %s", err)
            raise
        except ReadTimeoutError:
            # For some reason, we have to catch this directly.  It falls through
            # from python-etcd because it's trying to catch
            # urllib3.exceptions.ReadTimeoutError and strangely, doesn't catch.
            # This can occur from a watch timeout that expires, so it may be 'expected'
            # behavior. See issue #28553
            if wait:
                # Wait timeouts will throw ReadTimeoutError, which isn't bad
                log.debug("etcd: Timed out while executing a wait")
                raise EtcdUtilWatchTimeout("Watch on {0} timed out".format(key))
            log.error("etcd: Timed out")
            raise etcd.EtcdConnectionFailed("Connection failed")
        except MaxRetryError as err:
            # Same issue as ReadTimeoutError.  When it 'works', python-etcd
            # throws EtcdConnectionFailed, so we'll do that for it.
            log.error("etcd: Could not connect")
            raise etcd.EtcdConnectionFailed("Could not connect to etcd server")
        except etcd.EtcdException as err:
            # EtcdValueError inherits from ValueError, so we don't want to accidentally
            # catch this below on ValueError and give a bogus error message
            log.error("etcd: {0}".format(err))
            raise
        except ValueError:
            # python-etcd doesn't fully support python 2.6 and ends up throwing this for *any* exception because
            # it uses the newer {} format syntax
            log.error("etcd: error. python-etcd does not fully support python 2.6, no error information available")
            raise
        except Exception as err:
            log.error('etcd: uncaught exception %s', err)
            raise
        return result

    def _flatten(self, data, path=''):
        if len(data.keys()) == 0:
            return {path: {}}
        path = path.strip('/')
        flat = {}
        for k, v in six.iteritems(data):
            k = k.strip('/')
            if path:
                p = '/{0}/{1}'.format(path, k)
            else:
                p = '/{0}'.format(k)
            if isinstance(v, dict):
                ret = self._flatten(v, p)
                flat.update(ret)
            else:
                flat[p] = v
        return flat

    def update(self, fields, path=''):
        if not isinstance(fields, dict):
            log.error('etcd.update: fields is not type dict')
            return None
        fields = self._flatten(fields, path)
        keys = {}
        for k, v in six.iteritems(fields):
            is_dir = False
            if isinstance(v, dict):
                is_dir = True
            keys[k] = self.write(k, v, directory=is_dir)
        return keys

    def set(self, key, value, ttl=None, directory=False):
        return self.write(key, value, ttl=ttl, directory=directory)

    def write(self, key, value, ttl=None, directory=False):
        # directories can't have values, but have to have it passed
        if directory:
            value = None
        try:
            result = self.client.write(key, value, ttl=ttl, dir=directory)
        except (etcd.EtcdNotFile, etcd.EtcdNotDir, etcd.EtcdRootReadOnly, ValueError) as err:
            log.error('etcd: %s', err)
            return None
        except MaxRetryError as err:
            log.error("etcd: Could not connect to etcd server: %s", err)
            return None
        except Exception as err:
            log.error('etcd: uncaught exception %s', err)
            raise

        if directory:
            return getattr(result, 'dir')
        else:
            return getattr(result, 'value')

    def ls(self, path):
        ret = {}
        try:
            items = self.read(path)
        except (etcd.EtcdKeyNotFound, ValueError):
            return {}
        except etcd.EtcdConnectionFailed:
            log.error("etcd: failed to perform 'ls' operation on path %s due to connection error", path)
            return None

        for item in items.children:
            if item.dir is True:
                if item.key == path:
                    continue
                dir_name = '{0}/'.format(item.key)
                ret[dir_name] = {}
            else:
                ret[item.key] = item.value
        return {path: ret}

    def rm(self, key, recurse=False):
        return self.delete(key, recurse)

    def delete(self, key, recursive=False):
        try:
            if self.client.delete(key, recursive=recursive):
                return True
            else:
                return False
        except (etcd.EtcdNotFile, etcd.EtcdRootReadOnly, etcd.EtcdDirNotEmpty, etcd.EtcdKeyNotFound, ValueError) as err:
            log.error('etcd: %s', err)
            return None
        except MaxRetryError as err:
            log.error('etcd: Could not connect to etcd server: %s', err)
            return None
        except Exception as err:
            log.error('etcd: uncaught exception %s', err)
            raise

    def tree(self, path):
        '''
        .. versionadded:: 2014.7.0

        Recurse through etcd and return all values
        '''
        ret = {}
        try:
            items = self.read(path)
        except (etcd.EtcdKeyNotFound, ValueError):
            return None
        except etcd.EtcdConnectionFailed:
            log.error("etcd: failed to perform 'tree' operation on path %s due to connection error", path)
            return None

        for item in items.children:
            comps = six.text_type(item.key).split('/')
            if item.dir is True:
                if item.key == path:
                    continue
                ret[comps[-1]] = self.tree(item.key)
            else:
                ret[comps[-1]] = item.value
        return ret


def get_conn(opts, profile=None, **kwargs):
    client = EtcdClient(opts, profile, **kwargs)
    return client


def tree(client, path):
    return client.tree(path)
