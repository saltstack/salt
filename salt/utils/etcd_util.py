"""
Utilities for working with etcd

.. versionadded:: 2014.7.0

:depends:  - python-etcd or etcd3-py

This library sets up a client object for etcd, using the configuration passed
into the get_conn() function. Normally, this is __opts__. Optionally, a profile
may be passed in. The following configurations are both valid:

.. code-block:: yaml

    # No profile name
    etcd.host: 127.0.0.1
    etcd.port: 2379
    etcd.username: larry  # Optional; requires etcd.password to be set
    etcd.password: 123pass  # Optional; requires etcd.username to be set
    etcd.ca: /path/to/your/ca_cert/ca.pem # Optional
    etcd.client_key: /path/to/your/client_key/client-key.pem # Optional; requires etcd.ca and etcd.client_cert to be set
    etcd.client_cert: /path/to/your/client_cert/client.pem # Optional; requires etcd.ca and etcd.client_key to be set
    etcd.require_v2: True # Optional; defaults to True
    etcd.encode_keys: False # Optional (v3 ONLY); defaults to False
    etcd.encode_values: True # Optional (v3 ONLY); defaults to True
    etcd.raw_keys: False # Optional (v3 ONLY); defaults to False
    etcd.raw_values: False # Optional (v3 ONLY); defaults to False
    etcd.unicode_errors: "surrogateescape" # Optional (v3 ONLY); defaults to "surrogateescape"

    # One or more profiles defined
    my_etcd_config:
      etcd.host: 127.0.0.1
      etcd.port: 2379
      etcd.username: larry  # Optional; requires etcd.password to be set
      etcd.password: 123pass  # Optional; requires etcd.username to be set
      etcd.ca: /path/to/your/ca_cert/ca.pem # Optional
      etcd.client_key: /path/to/your/client_key/client-key.pem # Optional; requires etcd.ca and etcd.client_cert to be set
      etcd.client_cert: /path/to/your/client_cert/client.pem # Optional; requires etcd.ca and etcd.client_key to be set
      etcd.require_v2: True # Optional; defaults to True
      etcd.encode_keys: False # Optional (v3 ONLY); defaults to False
      etcd.encode_values: True # Optional (v3 ONLY); defaults to True
      etcd.raw_keys: False # Optional (v3 ONLY); defaults to False
      etcd.raw_values: False # Optional (v3 ONLY); defaults to False
      etcd.unicode_errors: "surrogateescape" # Optional (v3 ONLY); defaults to "surrogateescape"

Encoding keys for etcd v3 allows a differentiation within etcd between byte and string keys.
It is worth noting that if you chose to encode keys, due to the way encoding pre-etcd with msgpack works,
all recursive functionality will not work as intended. This includes tree and ls along
with all methods that have recurse kwargs.  Thus, enabling this option is not recommended.

Once configured, the client() function is passed a set of opts, and optionally,
the name of a profile to be used.

.. code-block:: python

    import salt.utils.etcd_utils
    client = salt.utils.etcd_utils.get_conn(__opts__, profile='my_etcd_config')

You may also use the newer syntax and bypass the generator function.

V2 API
.. code-block:: python

    import salt.utils.etcd_utils
    client = salt.utils.etcd_utils.EtcdClient(__opts__, profile='my_etcd_config')

V3 API
.. versionadded:: 3005

.. code-block:: python

    import salt.utils.etcd_utils
    client = salt.utils.etcd_utils.EtcdClientV3(__opts__, profile='my_etcd_config')

It should be noted that some usages of etcd require a profile to be specified,
rather than top-level configurations. This being the case, it is better to
always use a named configuration profile, as shown above.
"""

import logging

import salt.utils.msgpack
import salt.utils.versions
from salt.exceptions import SaltException

try:
    import etcd
    from urllib3.exceptions import MaxRetryError, ReadTimeoutError

    HAS_ETCD_V2 = True
except ImportError:
    HAS_ETCD_V2 = False

try:
    import etcd3

    HAS_ETCD_V3 = True
except ImportError:
    HAS_ETCD_V3 = False

# Set up logging
log = logging.getLogger(__name__)


class EtcdLibraryNotInstalled(SaltException):
    """
    We didn't find the required etcd library
    """


class IncompatibleEtcdRequirements(SaltException):
    """
    A user is explicitly creating a client class, but requires a different version
    """


class Etcd3DirectoryException(SaltException):
    """
    We didn't find the required etcd library
    """


class EtcdUtilWatchTimeout(Exception):
    """
    A watch timed out without returning a result
    """


class EtcdBase:
    """
    Base class for the different versions of etcd clients.

    This also serves as a documentation hub for all superclasses.
    """

    def __init__(
        self,
        opts,
        profile=None,
        host=None,
        port=None,
        username=None,
        password=None,
        ca=None,
        client_key=None,
        client_cert=None,
        **kwargs,
    ):
        if not kwargs.get("has_etcd_opts", False):
            etcd_opts = _get_etcd_opts(opts, profile)
        else:
            etcd_opts = opts

        self.conf = etcd_opts
        self.host = host or self.conf.get("etcd.host", "127.0.0.1")
        self.port = port or self.conf.get("etcd.port", 2379)

        if self.host == "127.0.0.1" and self.port == 2379:
            log.warning("Using default etcd host and port, use a profile if needed.")

        username = username or self.conf.get("etcd.username")
        password = password or self.conf.get("etcd.password")
        ca_cert = ca or self.conf.get("etcd.ca")
        cli_key = client_key or self.conf.get("etcd.client_key")
        cli_cert = client_cert or self.conf.get("etcd.client_cert")

        auth = {}
        if username and password:
            auth = {
                "username": str(username),
                "password": str(password),
            }

        certs = {}
        if ca_cert and not (cli_cert or cli_key):
            certs = {"ca_cert": str(ca_cert), "protocol": "https"}

        if ca_cert and cli_cert and cli_key:
            cert = (cli_cert, cli_key)
            certs = {
                "ca_cert": str(ca_cert),
                "cert": cert,
                "protocol": "https",
            }

        self.xargs = auth.copy()
        self.xargs.update(certs)

    def watch(self, key, recurse=False, timeout=0, start_revision=None, **kwargs):
        raise NotImplementedError()

    def get(self, key, recurse=False):
        """
        Get the value of a specific key.  If recurse is true, defer to EtcdBase.tree() instead.
        """
        raise NotImplementedError()

    def read(
        self,
        key,
        recurse=False,
        wait=False,
        timeout=None,
        start_revision=None,
        **kwargs,
    ):
        """
        Read a value of a key.

        This method also provides the ability to wait for changes after a given index and/or
        within a certain timeout.
        """
        raise NotImplementedError()

    def _flatten(self, data, path=""):
        """
        Take a data dictionary and flatten it to a dictionary with values that are all strings.

        If path is given, prepend it to all keys.

        For example, given path="/salt" it will convert...

        {
            "key1": "value1",
            "key2": {
                "subkey1": "subvalue1",
                "subkey2": "subvalue2",
            }
        }

        to...

        {
            "/salt/key1": "value1",
            "/salt/key2/subkey1": "subvalue1",
            "/salt/key2/subkey2": "subvalue2",
        }
        """
        if not data:
            return {path: {}}
        path = path.strip("/")
        flat = {}
        for k, v in data.items():
            k = k.strip("/")
            if path:
                p = f"/{path}/{k}"
            else:
                p = f"/{k}"
            if isinstance(v, dict):
                ret = self._flatten(v, p)
                flat.update(ret)
            else:
                flat[p] = v
        return flat

    def update(self, fields, path=""):
        """
        Update etcd according to the layout of fields.

        Given etcd with this layout...
        {
            ...
            "/salt/key1": "OLDvalue1",
            "/salt/key2/subkey1": "OLDsubvalue1",
            "/salt/key2/subkey2": "OLDsubvalue2",
            ...
        }

        fields = {
            "key1": "value1",
            "key2": {
                "subkey1": "subvalue1",
                "subkey2": "subvalue2",
            }
        }

        will update etcd to look like the following...
        {
            ...
            "/salt/key1": "value1",
            "/salt/key2/subkey1": "subvalue1",
            "/salt/key2/subkey2": "subvalue2",
            ...
        }

        """
        raise NotImplementedError()

    def set(self, key, value, ttl=None, directory=False):
        """
        Write a file or directory, a higher interface to write
        """
        return self.write(key, value, ttl=ttl, directory=directory)

    def write(self, key, value, ttl=None, directory=False):
        """
        Write a file or directory depending on directory flag
        """
        if directory:
            return self.write_directory(key, value, ttl)
        return self.write_file(key, value, ttl)

    def write_file(self, key, value, ttl=None):
        """
        Write a file (key: value pair) to etcd
        """
        raise NotImplementedError()

    def write_directory(self, key, value, ttl=None):
        """
        Write a directory (key: {}) to etcd
        """
        raise NotImplementedError()

    def ls(self, path):
        """
        Get all the top level keys and their values at the given path.

        If the key is a directory, its value is an empty dictionary.
        """
        raise NotImplementedError()

    def rm(self, key, recurse=False):
        """
        An alias for delete
        """
        return self.delete(key, recurse)

    def delete(self, key, recurse=False, **kwargs):
        """
        Delete keys or (recursively) whole directories
        """
        raise NotImplementedError()

    def tree(self, path):
        """
        .. versionadded:: 2014.7.0

        Recurse through etcd and return all values
        """
        raise NotImplementedError()


class EtcdClient(EtcdBase):
    def __init__(self, opts, **kwargs):
        if not HAS_ETCD_V2:
            raise EtcdLibraryNotInstalled("Don't have python-etcd, need to install it.")
        log.debug("etcd_util has the libraries needed for etcd v2")

        super().__init__(opts, **kwargs)

        if not self.conf.get("etcd.require_v2", True):
            raise IncompatibleEtcdRequirements("Can't create v2 with a v3 requirement")

        self.client = etcd.Client(host=self.host, port=self.port, **self.xargs)

    def watch(self, key, recurse=False, timeout=0, start_revision=None, **kwargs):
        index = kwargs.pop("index", None)
        if index is not None:
            salt.utils.versions.warn_until(
                "Argon",
                "The index kwarg has been deprecated, and will be removed "
                "in the Argon release. Please use start_revision instead.",
            )
            start_revision = index
        if kwargs:
            log.warning("Invalid kwargs passed in will not be used: %s", kwargs)

        ret = {"key": key, "value": None, "changed": False, "mIndex": 0, "dir": False}
        try:
            result = self.read(
                key,
                recurse=recurse,
                wait=True,
                timeout=timeout,
                start_revision=start_revision,
            )
        except EtcdUtilWatchTimeout:
            try:
                result = self.read(key)
            except etcd.EtcdKeyNotFound:
                log.debug("etcd: key was not created while watching")
                return ret
            except ValueError:
                return {}
            if result and getattr(result, "dir"):
                ret["dir"] = True
            ret["value"] = getattr(result, "value")
            ret["mIndex"] = getattr(result, "modifiedIndex")
            return ret
        except MaxRetryError:
            # This gets raised when we can't contact etcd at all
            log.error(
                "etcd: failed to perform 'watch' operation on key %s due to connection"
                " error",
                key,
            )
            return {}
        except etcd.EtcdConnectionFailed as err:
            log.error("etcd: %s", err)
            return None
        except ValueError:
            return {}

        if result is None:
            return {}

        if recurse:
            ret["key"] = getattr(result, "key", None)
        ret["value"] = getattr(result, "value", None)
        ret["dir"] = getattr(result, "dir", None)
        ret["changed"] = True
        ret["mIndex"] = getattr(result, "modifiedIndex")
        return ret

    def get(self, key, recurse=False):
        if not recurse:
            try:
                result = self.read(key)
            except etcd.EtcdKeyNotFound:
                # etcd already logged that the key wasn't found, no need to do
                # anything here but return
                return None
            except etcd.EtcdConnectionFailed:
                log.error(
                    "etcd: failed to perform 'get' operation on key %s due to connection"
                    " error",
                    key,
                )
                return None
            except ValueError:
                return None

            return getattr(result, "value", None)

        return self.tree(key)

    def read(
        self,
        key,
        recurse=False,
        wait=False,
        timeout=None,
        start_revision=None,
        **kwargs,
    ):
        recursive = kwargs.pop("recursive", None)
        wait_index = kwargs.pop("waitIndex", None)
        if recursive is not None:
            salt.utils.versions.warn_until(
                "Argon",
                "The recursive kwarg has been deprecated, and will be removed "
                "in the Argon release. Please use recurse instead.",
            )
            recurse = recursive
        if wait_index is not None:
            salt.utils.versions.warn_until(
                "Argon",
                "The waitIndex kwarg has been deprecated, and will be removed "
                "in the Argon release. Please use start_revision instead.",
            )
            start_revision = wait_index
        if kwargs:
            log.warning("Invalid kwargs passed in will not be used: %s", kwargs)

        try:
            if start_revision:
                result = self.client.read(
                    key,
                    recursive=recurse,
                    wait=wait,
                    timeout=timeout,
                    waitIndex=start_revision,
                )
            else:
                result = self.client.read(
                    key, recursive=recurse, wait=wait, timeout=timeout
                )
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
                raise EtcdUtilWatchTimeout(f"Watch on {key} timed out")
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
            log.error("etcd: %s", err)
            raise
        except ValueError:
            # python-etcd doesn't fully support python 2.6 and ends up throwing this for *any* exception because
            # it uses the newer {} format syntax
            log.error(
                "etcd: error. python-etcd does not fully support python 2.6, no error"
                " information available"
            )
            raise
        except Exception as err:  # pylint: disable=broad-except
            log.error("etcd: uncaught exception %s", err)
            raise
        return result

    def update(self, fields, path=""):
        if not isinstance(fields, dict):
            log.error("etcd.update: fields is not type dict")
            return None
        fields = self._flatten(fields, path)
        keys = {}
        for k, v in fields.items():
            is_dir = False
            if isinstance(v, dict):
                is_dir = True
            keys[k] = self.write(k, v, directory=is_dir)
            if keys[k] is None:
                return None
        return keys

    def write(self, key, value, ttl=None, directory=False):
        """
        Write a file or directory depending on directory flag
        """
        try:
            if directory:
                return self.write_directory(key, value, ttl)
            return self.write_file(key, value, ttl)
        except etcd.EtcdConnectionFailed as err:
            log.error("etcd: %s", err)
            return None

    def write_file(self, key, value, ttl=None):
        try:
            result = self.client.write(key, value, ttl=ttl, dir=False)
        except (etcd.EtcdNotFile, etcd.EtcdRootReadOnly, ValueError) as err:
            # If EtcdNotFile is raised, then this key is a directory and
            # really this is a name collision.
            log.error("etcd: %s", err)
            return None
        except MaxRetryError as err:
            log.error("etcd: Could not connect to etcd server: %s", err)
            return None
        except Exception as err:  # pylint: disable=broad-except
            log.error("etcd: uncaught exception %s", err)
            raise

        return getattr(result, "value")

    def write_directory(self, key, value, ttl=None):
        if value is not None:
            log.info("etcd: non-empty value passed for directory: %s", value)
        try:
            # directories can't have values, but have to have it passed
            result = self.client.write(key, None, ttl=ttl, dir=True)
        except etcd.EtcdNotFile:
            # When a directory already exists, python-etcd raises an EtcdNotFile
            # exception. In this case, we just catch and return True for success.
            log.info("etcd: directory already exists: %s", key)
            return True
        except (etcd.EtcdNotDir, etcd.EtcdRootReadOnly, ValueError) as err:
            # If EtcdNotDir is raised, then the specified path is a file and
            # thus this is an error.
            log.error("etcd: %s", err)
            return None
        except MaxRetryError as err:
            log.error("etcd: Could not connect to etcd server: %s", err)
            return None
        except Exception as err:  # pylint: disable=broad-except
            log.error("etcd: uncaught exception %s", err)
            raise

        return getattr(result, "dir")

    def ls(self, path):
        ret = {}
        try:
            items = self.read(path)
        except (etcd.EtcdKeyNotFound, ValueError):
            return {}
        except etcd.EtcdConnectionFailed:
            log.error(
                "etcd: failed to perform 'ls' operation on path %s due to connection"
                " error",
                path,
            )
            return None

        # This will find the top level keys only since it's not recursive
        for item in items.children:
            if item.dir is True:
                if item.key == path:
                    continue
                dir_name = f"{item.key}/"
                ret[dir_name] = {}
            else:
                ret[item.key] = item.value
        return {path: ret}

    def delete(self, key, recurse=False, **kwargs):
        recursive = kwargs.pop("recursive", None)
        if recursive is not None:
            salt.utils.versions.warn_until(
                "Argon",
                "The recursive kwarg has been deprecated, and will be removed "
                "in the Argon release. Please use recurse instead.",
            )
            recurse = recursive
        if kwargs:
            log.warning("Invalid kwargs passed in will not be used: %s", kwargs)

        try:
            if self.client.delete(key, recursive=recurse):
                return True
            else:
                return False
        except (
            etcd.EtcdNotFile,
            etcd.EtcdRootReadOnly,
            etcd.EtcdDirNotEmpty,
            etcd.EtcdKeyNotFound,
            etcd.EtcdConnectionFailed,
            ValueError,
        ) as err:
            log.error("etcd: %s", err)
            return None
        except MaxRetryError as err:
            log.error("etcd: Could not connect to etcd server: %s", err)
            return None
        except Exception as err:  # pylint: disable=broad-except
            log.error("etcd: uncaught exception %s", err)
            raise

    def tree(self, path):
        ret = {}
        try:
            items = self.read(path)
        except (etcd.EtcdKeyNotFound, ValueError):
            return None
        except etcd.EtcdConnectionFailed as err:
            log.error("etcd: %s", err)
            return None

        for item in items.children:
            comps = str(item.key).split("/")
            if item.dir is True:
                if item.key == path:
                    continue
                ret[comps[-1]] = self.tree(item.key)
            else:
                ret[comps[-1]] = item.value
        return ret


class EtcdClientV3(EtcdBase):
    """
    .. versionadded:: 3005

    Since etcd3 has no concept of directories, this class leaves write_directory unimplemented.
    """

    def __init__(
        self,
        opts,
        encode_keys=None,
        encode_values=None,
        raw_keys=False,
        raw_values=False,
        unicode_errors=None,
        **kwargs,
    ):
        if not HAS_ETCD_V3:
            raise EtcdLibraryNotInstalled("Don't have etcd3-py, need to install it.")
        log.debug("etcd_util has the libraries needed for etcd v3")

        super().__init__(opts, **kwargs)

        if self.conf.get("etcd.require_v2", True):
            raise IncompatibleEtcdRequirements("Can't create v3 with a v2 requirement")

        self.encode_keys = encode_keys or self.conf.get("etcd.encode_keys", False)
        self.encode_values = encode_values or self.conf.get("etcd.encode_values", True)
        self.raw_keys = raw_keys or self.conf.get("etcd.raw_keys", False)
        self.raw_values = raw_values or self.conf.get("etcd.raw_values", False)
        self.unicode_errors = unicode_errors or self.conf.get(
            "etcd.unicode_errors", "surrogateescape"
        )

        # etcd3-py uses verify instead of ca_cert
        self.xargs["verify"] = self.xargs.pop("ca_cert", None)
        self.client = etcd3.Client(host=self.host, port=self.port, **self.xargs)

    def _maybe_decode_key(self, key, **extra_kwargs):
        extra_kwargs.setdefault("unicode_errors", self.unicode_errors)
        if self.encode_keys:
            key = salt.utils.msgpack.loads(key, raw=self.raw_keys, **extra_kwargs)
        elif not self.raw_keys and isinstance(key, bytes):
            key = key.decode(encoding="UTF-8", errors=self.unicode_errors)
        return key

    def _maybe_encode_key(self, key, **extra_kwargs):
        extra_kwargs.setdefault("unicode_errors", self.unicode_errors)
        if self.encode_keys:
            key = salt.utils.msgpack.dumps(key, **extra_kwargs)
        return key

    def _maybe_decode_value(self, value, **extra_kwargs):
        extra_kwargs.setdefault("unicode_errors", self.unicode_errors)
        if self.encode_values:
            value = salt.utils.msgpack.loads(value, raw=self.raw_values, **extra_kwargs)
        elif not self.raw_values and isinstance(value, bytes):
            value = value.decode(encoding="UTF-8", errors=self.unicode_errors)
        return value

    def _maybe_encode_value(self, value, **extra_kwargs):
        extra_kwargs.setdefault("unicode_errors", self.unicode_errors)
        if self.encode_values:
            value = salt.utils.msgpack.dumps(value, **extra_kwargs)
        return value

    def _decode_kv(self, kv):
        try:
            kv.key = self._maybe_decode_key(kv.key)
            kv.value = self._maybe_decode_value(kv.value)
        except AttributeError as err:
            log.error("etcd3 decoding error: %s", err)
        return kv

    def watch(self, key, recurse=False, timeout=0, start_revision=None, **kwargs):
        index = kwargs.pop("index", None)
        if index is not None:
            salt.utils.versions.warn_until(
                "Argon",
                "The index kwarg has been deprecated, and will be removed "
                "in the Argon release. Please use start_revision instead.",
            )
            start_revision = index
        if kwargs:
            log.warning("Invalid kwargs passed in will not be used: %s", kwargs)

        ret = {"key": key, "value": None, "changed": False, "mIndex": 0, "dir": False}
        result = self.read(
            key,
            recurse=recurse,
            wait=True,
            timeout=timeout,
            start_revision=start_revision,
        )
        if result is not None:
            ret["key"] = result.key
            ret["value"] = result.value
            ret["mIndex"] = getattr(result, "mod_revision", 0)
            ret["changed"] = True
        else:
            return None
        return ret

    def get(self, key, recurse=False):
        if not recurse:
            result = self.read(key)
            if isinstance(result, list):
                return result.pop().value
            return None
        return self.tree(key)

    def read(
        self,
        key,
        recurse=False,
        wait=False,
        timeout=None,
        start_revision=None,
        **kwargs,
    ):
        recursive = kwargs.pop("recursive", None)
        wait_index = kwargs.pop("waitIndex", None)
        if recursive is not None:
            salt.utils.versions.warn_until(
                "Argon",
                "The recursive kwarg has been deprecated, and will be removed "
                "in the Argon release. Please use recurse instead.",
            )
            recurse = recursive
        if wait_index is not None:
            salt.utils.versions.warn_until(
                "Argon",
                "The waitIndex kwarg has been deprecated, and will be removed "
                "in the Argon release. Please use start_revision instead.",
            )
            start_revision = wait_index
        if kwargs:
            log.warning("Invalid kwargs passed in will not be used: %s", kwargs)

        if not wait:
            try:
                result = self.client.range(self._maybe_encode_key(key), prefix=recurse)
                kvs = getattr(result, "kvs", None)
                if kvs is None:
                    log.error("etcd3 read: No values found for key %s", key)
                else:
                    for kv in kvs:
                        kv = self._decode_kv(kv)
                return kvs
            except Exception as err:  # pylint: disable=W0703
                log.error("etcd3 read: %s", err)
                return None
        else:
            try:
                watcher = self.client.Watcher(
                    key=self._maybe_encode_key(key),
                    prefix=recurse,
                    start_revision=start_revision,
                )
                watch_event = watcher.watch_once(timeout=timeout)
                return self._decode_kv(watch_event)
            except Exception as err:  # pylint: disable=W0703
                log.error("etcd3 watch: %s", err)
                return None

    def update(self, fields, path=""):
        if not isinstance(fields, dict):
            log.error("etcd.update: fields is not type dict")
            return None
        fields = self._flatten(fields, path)
        keys = {}
        for k, v in fields.items():
            if isinstance(v, dict):
                # Not hard failing here so we don't get a partial update
                log.warning("etcd3 has no concept of directories, skipping key %s", k)
                continue
            keys[k] = self.write(k, v)
        return keys

    def write_file(self, key, value, ttl=None):
        if ttl:
            lease = self.client.Lease(ttl=ttl)
            lease.grant()  # We need to explicitly grant the lease
            self.client.put(
                self._maybe_encode_key(key),
                self._maybe_encode_value(value),
                lease=lease.ID,
            )
        else:
            self.client.put(
                self._maybe_encode_key(key), self._maybe_encode_value(value)
            )
        return self.get(key)

    def write_directory(self, key, value, ttl=None):
        raise Etcd3DirectoryException("etcd3 does not have directories")

    def ls(self, path):
        ret = {}
        tree = self.tree(path)

        # Here we will simulate directories because v3 does not have them
        if tree is None:
            return {}
        else:
            sep = "/" if not self.raw_keys else b"/"
            path = (
                path
                if not self.raw_keys or isinstance(path, bytes)
                else path.encode("UTF-8", errors=self.unicode_errors)
            )

            for key, value in tree.items():
                if not path.endswith(sep):
                    ret_key = path + sep + key
                else:
                    ret_key = path + key
                if isinstance(value, dict):
                    ret[ret_key + sep] = {}
                else:
                    ret[ret_key] = value

        return {path: ret}

    def delete(self, key, recurse=False, **kwargs):
        recursive = kwargs.pop("recursive", None)
        if recursive is not None:
            salt.utils.versions.warn_until(
                "Argon",
                "The recursive kwarg has been deprecated, and will be removed "
                "in the Argon release. Please use recurse instead.",
            )
            recurse = recursive

        if kwargs:
            log.warning("Invalid kwargs passed in will not be used: %s", kwargs)
        result = self.client.delete_range(self._maybe_encode_key(key), prefix=recurse)
        if hasattr(result, "deleted"):
            return True if result.deleted else None
        return False

    def _expand_recurse(self, key, value, dest):
        """
        Helper for _expand
        """
        sep = "/" if not self.raw_keys else b"/"
        outer, *inner = key.lstrip(sep).split(sep, 1)
        if inner:
            if outer not in dest:
                dest[outer] = {}
            self._expand_recurse(inner[0], value, dest[outer])
        else:
            dest[outer] = value

    def _expand(self, kvs):
        """
        This does the opposite of EtcdBase._flatten

        For example, it will convert...

        {
            "/key1": "value1",
            "/key2/subkey1": "subvalue1",
            "/key2/subkey2": "subvalue2",
        }

        to...

        {
            "key1": "value1",
            "key2": {
                "subkey1": "subvalue1",
                "subkey2": "subvalue2",
            }
        }
        """
        dest = {}
        for key, value in kvs.items():
            self._expand_recurse(key, value, dest)
        return dest

    def tree(self, path):
        items = self.read(path, recurse=True)
        if items is None:
            return None
        sep = "/" if not self.raw_keys else b"/"
        if len(items) == 1 and items[0].key == path:
            kv = items.pop()
            return {kv.key.split(sep)[-1]: kv.value}
        kvs = {kv.key[len(path) :]: kv.value for kv in items}
        return self._expand(kvs)


def _get_etcd_opts(opts, profile=None):
    opts_pillar = opts.get("pillar", {})
    opts_master = opts_pillar.get("master", {})

    opts_merged = {}
    opts_merged.update(opts_master)
    opts_merged.update(opts_pillar)
    opts_merged.update(opts)

    if profile:
        return opts_merged.pop(profile, {})
    else:
        return opts_merged


def get_conn(opts, profile=None, **kwargs):
    """
    Client creation at the module level.

    This is the way users are meant to instantiate a client
    """

    conf = _get_etcd_opts(opts, profile=profile)

    # Figure out which API version they are using...
    use_v2 = conf.get("etcd.require_v2", True)
    if use_v2:
        salt.utils.versions.warn_until(
            "Potassium",
            "etcd API v2 has been deprecated.  It will be removed in "
            "the Potassium release, and etcd API v3 will be the default.",
        )
        client = EtcdClient(conf, has_etcd_opts=True, **kwargs)
        log.debug("etcd_util will be attempting to use etcd API v2: python-etcd")
    else:
        client = EtcdClientV3(conf, has_etcd_opts=True, **kwargs)
        log.debug("etcd_util will be attempting to use etcd API v3: etcd3-py")

    return client


def tree(client, path):
    """
    Module level find tree at the given path.
    """
    return client.tree(path)
