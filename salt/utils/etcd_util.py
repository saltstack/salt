"""
Utilities for working with etcd

.. versionadded:: 2014.7.0

:depends:  - etcd3gw

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
    etcd.encode_keys: False # Optional; defaults to False
    etcd.encode_values: True # Optional; defaults to True
    etcd.raw_keys: False # Optional; defaults to False
    etcd.raw_values: False # Optional; defaults to False
    etcd.unicode_errors: "surrogateescape" # Optional; defaults to "surrogateescape"

    # One or more profiles defined
    my_etcd_config:
      etcd.host: 127.0.0.1
      etcd.port: 2379
      etcd.username: larry  # Optional; requires etcd.password to be set
      etcd.password: 123pass  # Optional; requires etcd.username to be set
      etcd.ca: /path/to/your/ca_cert/ca.pem # Optional
      etcd.client_key: /path/to/your/client_key/client-key.pem # Optional; requires etcd.ca and etcd.client_cert to be set
      etcd.client_cert: /path/to/your/client_cert/client.pem # Optional; requires etcd.ca and etcd.client_key to be set
      etcd.encode_keys: False # Optional; defaults to False
      etcd.encode_values: True # Optional; defaults to True
      etcd.raw_keys: False # Optional; defaults to False
      etcd.raw_values: False # Optional; defaults to False
      etcd.unicode_errors: "surrogateescape" # Optional; defaults to "surrogateescape"

Encoding keys for etcd v3 allows a differentiation within etcd between byte and string keys.
It is worth noting that if you chose to encode keys, due to the way encoding pre-etcd with msgpack works,
all recursive functionality will not work as intended. This includes tree and ls along
with all methods that have recurse kwargs.  Thus, enabling this option is not recommended.

Once configured, the client() function is passed a set of opts, and optionally,
the name of a profile to be used.

.. code-block:: python

    import salt.utils.etcd_util
    client = salt.utils.etcd_util.get_conn(__opts__, profile='my_etcd_config')

You may also use the newer syntax and bypass the generator function.

V3 API
.. versionadded:: 3005

.. code-block:: python

    import salt.utils.etcd_util
    client = salt.utils.etcd_util.EtcdClientV3(__opts__, profile='my_etcd_config')

It should be noted that some usages of etcd require a profile to be specified,
rather than top-level configurations. This being the case, it is better to
always use a named configuration profile, as shown above.

.. versionchanged:: 3009.0

    The etcd v2 API client (``EtcdClient``) and the ``etcd.require_v2`` option
    were removed. ``get_conn`` now always returns an :class:`EtcdClientV3`.

.. versionchanged:: 3009.0

    The client library changed from ``etcd3-py`` to ``etcd3gw``. Install
    ``etcd3gw`` (``salt-pip install etcd3gw`` on onedir installs) in place of
    ``etcd3-py``. ``etcd.username``/``etcd.password``, ``etcd.ca`` and the
    client certificate options work as before.
"""

import inspect
import logging
import threading

import requests

import salt.exceptions
import salt.utils.msgpack
from salt.exceptions import SaltException

try:
    import etcd3gw.exceptions
    from etcd3gw.client import Etcd3Client

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


class _KeyValue:
    """
    An etcd key-value pair, with the attribute names that callers of
    :meth:`EtcdClientV3.read` have used since 3005.
    """

    __slots__ = ("key", "value", "create_revision", "mod_revision", "version", "lease")

    def __init__(
        self, key, value=None, create_revision=0, mod_revision=0, version=0, lease=0
    ):
        self.key = key
        self.value = value
        self.create_revision = create_revision
        self.mod_revision = mod_revision
        self.version = version
        self.lease = lease

    @classmethod
    def from_etcd(cls, kv, value=None):
        """
        Build from an etcd ``KeyValue`` dict as returned by etcd3gw, whose
        integer fields arrive as strings.
        """
        return cls(
            kv.get("key"),
            value if value is not None else kv.get("value"),
            int(kv.get("create_revision", 0)),
            int(kv.get("mod_revision", 0)),
            int(kv.get("version", 0)),
            int(kv.get("lease", 0)),
        )


def prefix_range_end(prefix):
    """
    Return the etcd ``range_end`` that selects every key starting with
    ``prefix``.
    """
    if isinstance(prefix, str):
        prefix = prefix.encode("utf-8")
    end = bytearray(prefix)
    while end:
        if end[-1] < 0xFF:
            end[-1] += 1
            return bytes(end)
        end.pop()
    # An empty prefix, or one made only of 0xff bytes: run to the end of the
    # keyspace.
    return b"\0"


def _token_rejected(exc):
    """
    Whether etcd rejected the request's auth token as invalid or expired
    (HTTP 401, gRPC Unauthenticated).
    """
    return exc.args[:1] == ("Unauthorized",) or "invalid auth token" in (
        getattr(exc, "detail_text", None) or ""
    )


def _client_class():
    """
    Return the etcd3gw client class to use.

    etcd3gw releases without the ``username`` and ``password`` client
    arguments cannot authenticate, so :class:`_AuthEtcd3Client` adds that.
    Once Salt requires an etcd3gw release that has them, remove
    ``_AuthEtcd3Client`` and use ``Etcd3Client`` directly.
    """
    if "username" in inspect.signature(Etcd3Client.__init__).parameters:
        return Etcd3Client
    return _AuthEtcd3Client


if HAS_ETCD_V3:

    class _AuthEtcd3Client(Etcd3Client):
        """
        etcd3gw client with user name and password authentication.

        The token is set on the client's session, so it is also sent with
        watch requests, which do not go through ``post``. A token etcd
        rejects is replaced and the request sent once more.
        """

        def __init__(self, *args, username=None, password=None, **kwargs):
            super().__init__(*args, **kwargs)
            self._salt_username = username
            self._salt_password = password
            self._salt_token = None
            self._salt_auth_lock = threading.Lock()

        def _salt_authenticate(self, rejected_token=None):
            with self._salt_auth_lock:
                if self._salt_token is not None and self._salt_token != rejected_token:
                    # Another thread has already replaced the rejected token.
                    return
                # Send no token with the request: older etcd releases refuse
                # to authenticate a request that carries an invalid one.
                try:
                    resp = self.session.post(
                        self.get_url("/auth/authenticate"),
                        json={
                            "name": self._salt_username,
                            "password": self._salt_password,
                        },
                        headers={"Authorization": None},
                        timeout=self.timeout,
                    )
                except requests.exceptions.Timeout as exc:
                    raise etcd3gw.exceptions.ConnectionTimeoutError(str(exc))
                except requests.exceptions.ConnectionError as exc:
                    raise etcd3gw.exceptions.ConnectionFailedError(str(exc))
                if resp.status_code != requests.codes["ok"]:
                    raise etcd3gw.exceptions.Etcd3Exception(resp.text, resp.reason)
                self._salt_token = resp.json()["token"]
                self.session.headers["Authorization"] = self._salt_token

        def post(self, url, *args, **kwargs):
            if self._salt_username is None:
                return super().post(url, *args, **kwargs)
            if self._salt_token is None:
                self._salt_authenticate()
            token = self._salt_token
            try:
                return super().post(url, *args, **kwargs)
            except etcd3gw.exceptions.Etcd3Exception as exc:
                if not _token_rejected(exc):
                    raise
                self._salt_authenticate(rejected_token=token)
                return super().post(url, *args, **kwargs)

        def watch_once(self, key, *args, **kwargs):
            if self._salt_username is not None:
                # etcd cancels a watch created with an expired token instead
                # of returning an error, so it would never see an event. A
                # read of the watched key first replaces an expired token; it
                # needs only the permission the watch itself needs.
                self.get(key, count_only=True)
            return super().watch_once(key, *args, **kwargs)


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
            raise EtcdLibraryNotInstalled("Don't have etcd3gw, need to install it.")
        log.debug("etcd_util has the libraries needed for etcd v3")

        super().__init__(opts, **kwargs)

        self.encode_keys = encode_keys or self.conf.get("etcd.encode_keys", False)
        self.encode_values = encode_values or self.conf.get("etcd.encode_values", True)
        self.raw_keys = raw_keys or self.conf.get("etcd.raw_keys", False)
        self.raw_values = raw_values or self.conf.get("etcd.raw_values", False)
        self.unicode_errors = unicode_errors or self.conf.get(
            "etcd.unicode_errors", "surrogateescape"
        )

        client_kwargs = {"host": self.host, "port": int(self.port)}
        if "protocol" in self.xargs:
            client_kwargs["protocol"] = self.xargs["protocol"]
        if "ca_cert" in self.xargs:
            client_kwargs["ca_cert"] = self.xargs["ca_cert"]
        if "cert" in self.xargs:
            client_kwargs["cert_cert"], client_kwargs["cert_key"] = self.xargs["cert"]
        if self.xargs.get("username") and self.xargs.get("password"):
            client_kwargs["username"] = self.xargs["username"]
            client_kwargs["password"] = self.xargs["password"]
        self.client = _client_class()(**client_kwargs)

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
            # A delete event carries no value.
            if kv.value is not None:
                kv.value = self._maybe_decode_value(kv.value)
        except AttributeError as err:
            log.error("etcd3 decoding error: %s", err)
        return kv

    def _range(self, key, recurse=False):
        """
        Return the key-value pairs at ``key``, or under it if ``recurse``.
        """
        key = self._maybe_encode_key(key)
        kwargs = {"metadata": True}
        if recurse:
            kwargs["range_end"] = prefix_range_end(key)
        items = list(self.client.get(key, **kwargs))
        return [_KeyValue.from_etcd(kv, value) for value, kv in items]

    def watch(self, key, recurse=False, timeout=0, start_revision=None, **kwargs):
        if "index" in kwargs:
            raise salt.exceptions.SaltInvocationError(
                "The `index` kwarg was removed in 3009.0. Use `start_revision` instead."
            )
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
        if "recursive" in kwargs:
            raise salt.exceptions.SaltInvocationError(
                "The `recursive` kwarg was removed in 3009.0. Use `recurse` instead."
            )
        if "waitIndex" in kwargs:
            raise salt.exceptions.SaltInvocationError(
                "The `waitIndex` kwarg was removed in 3009.0. Use `start_revision` instead."
            )
        if kwargs:
            log.warning("Invalid kwargs passed in will not be used: %s", kwargs)

        if not wait:
            try:
                kvs = self._range(key, recurse=recurse)
                if not kvs:
                    log.error("etcd3 read: No values found for key %s", key)
                    return None
                return [self._decode_kv(kv) for kv in kvs]
            except Exception as err:  # pylint: disable=W0703
                log.error("etcd3 read: %s", err)
                return None
        else:
            try:
                encoded_key = self._maybe_encode_key(key)
                watch_kwargs = {}
                if recurse:
                    watch_kwargs["range_end"] = prefix_range_end(encoded_key)
                if start_revision is not None:
                    watch_kwargs["start_revision"] = start_revision
                event = self.client.watch_once(
                    encoded_key, timeout=timeout, **watch_kwargs
                )
                return self._decode_kv(_KeyValue.from_etcd(event["kv"]))
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
            self.client.put(
                self._maybe_encode_key(key),
                self._maybe_encode_value(value),
                lease=self.client.lease(ttl=ttl),
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
        if "recursive" in kwargs:
            raise salt.exceptions.SaltInvocationError(
                "The `recursive` kwarg was removed in 3009.0. Use `recurse` instead."
            )

        if kwargs:
            log.warning("Invalid kwargs passed in will not be used: %s", kwargs)
        key = self._maybe_encode_key(key)
        kwargs = {}
        if recurse:
            kwargs["range_end"] = prefix_range_end(key)
        return True if self.client.delete(key, **kwargs) else None

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

    if conf.get("etcd.require_v2") is True:
        raise salt.exceptions.CommandExecutionError(
            "etcd API v2 was removed in 3009.0. Set `etcd.require_v2: False` "
            "or remove the key."
        )

    return EtcdClientV3(conf, has_etcd_opts=True, **kwargs)


def tree(client, path):
    """
    Module level find tree at the given path.
    """
    return client.tree(path)
