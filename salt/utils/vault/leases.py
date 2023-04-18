import copy
import fnmatch
import logging
import time

from salt.utils.vault.exceptions import (
    VaultException,
    VaultInvocationError,
    VaultNotFoundError,
    VaultPermissionDeniedError,
)
from salt.utils.vault.helpers import iso_to_timestamp, timestring_map

log = logging.getLogger(__name__)


class DurationMixin:
    """
    Mixin that handles expiration with time
    """

    def __init__(
        self,
        renewable=False,
        duration=0,
        creation_time=None,
        expire_time=None,
        **kwargs,
    ):
        if "lease_duration" in kwargs:
            duration = kwargs.pop("lease_duration")
        self.renewable = renewable
        self.duration = duration
        creation_time = (
            creation_time if creation_time is not None else round(time.time())
        )
        try:
            creation_time = int(creation_time)
        except ValueError:
            creation_time = iso_to_timestamp(creation_time)
        self.creation_time = creation_time

        expire_time = (
            expire_time if expire_time is not None else round(time.time()) + duration
        )
        try:
            expire_time = int(expire_time)
        except ValueError:
            expire_time = iso_to_timestamp(expire_time)
        self.expire_time = expire_time
        super().__init__(**kwargs)

    def is_renewable(self):
        """
        Checks whether the lease is renewable
        """
        return self.renewable

    def is_valid_for(self, valid_for=0, blur=0):
        """
        Checks whether the entity is valid

        valid_for
            Check whether the entity will still be valid in the future.
            This can be an integer, which will be interpreted as seconds, or a
            time string using the same format as Vault does:
            Suffix ``s`` for seconds, ``m`` for minutes, ``h`` for hours, ``d`` for days.
            Defaults to 0.

        blur
            Allow undercutting ``valid_for`` for this amount of seconds.
            Defaults to 0.
        """
        if not self.duration:
            return True
        delta = self.expire_time - time.time() - timestring_map(valid_for)
        if delta >= 0:
            return True
        return abs(delta) <= blur


class UseCountMixin:
    """
    Mixin that handles expiration with number of uses
    """

    def __init__(self, num_uses=0, use_count=0, **kwargs):
        self.num_uses = num_uses
        self.use_count = use_count
        super().__init__(**kwargs)

    def used(self):
        """
        Increment the use counter by one.
        """
        self.use_count += 1

    def has_uses_left(self, uses=1):
        """
        Check whether this entity has uses left.
        """
        return self.num_uses == 0 or self.num_uses - (self.use_count + uses) >= 0


class DropInitKwargsMixin:
    """
    Mixin that breaks the chain of passing unhandled kwargs up the MRO.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args)


class AccessorMixin:
    """
    Mixin that manages accessor information relevant for tokens/secret IDs
    """

    def __init__(self, accessor=None, wrapped_accessor=None, **kwargs):
        self.accessor = accessor if wrapped_accessor is None else wrapped_accessor
        self.wrapping_accessor = accessor if wrapped_accessor is not None else None
        super().__init__(**kwargs)

    def accessor_payload(self):
        if self.accessor is not None:
            return {"accessor": self.accessor}
        raise VaultInvocationError("No accessor information available")


class BaseLease(DurationMixin, DropInitKwargsMixin):
    """
    Base class for leases that expire with time.
    """

    def __init__(self, lease_id, **kwargs):
        self.id = self.lease_id = lease_id
        super().__init__(**kwargs)

    def __str__(self):
        return self.id

    def __repr__(self):
        return repr(self.to_dict())

    def __eq__(self, other):
        try:
            data = other.__dict__
        except AttributeError:
            data = other
        return data == self.__dict__

    def with_renewed(self, **kwargs):
        """
        Partially update the contained data after lease renewal
        """
        attrs = copy.copy(self.__dict__)
        # ensure expire_time is reset properly
        attrs.pop("expire_time")
        attrs.update(kwargs)
        return type(self)(**attrs)

    def to_dict(self):
        """
        Return a dict of all contained attributes
        """
        return self.__dict__


class VaultLease(BaseLease):
    """
    Data object representing a Vault lease.
    """

    def __init__(self, lease_id, data, **kwargs):
        # save lease-associated data
        self.data = data
        super().__init__(lease_id, **kwargs)

    def is_valid(self, valid_for=0, blur=0):
        """
        Checks whether the lease is valid for an amount of time

        valid_for
            Check whether the token will still be valid in the future.
            This can be an integer, which will be interpreted as seconds, or a
            time string using the same format as Vault does:
            Suffix ``s`` for seconds, ``m`` for minutes, ``h`` for hours, ``d`` for days.
            Defaults to 0.

        blur
            Allow undercutting ``valid_for`` for this amount of seconds.
            Defaults to 0.
        """
        return self.is_valid_for(valid_for, blur=blur)


class VaultToken(UseCountMixin, AccessorMixin, BaseLease):
    """
    Data object representing an authentication token
    """

    def __init__(self, **kwargs):
        if "client_token" in kwargs:
            # Ensure response data from Vault is accepted as well
            kwargs["lease_id"] = kwargs.pop("client_token")
        super().__init__(**kwargs)

    def is_valid(self, valid_for=0, uses=1):
        """
        Checks whether the token is valid for an amount of time and number of uses

        valid_for
            Check whether the token will still be valid in the future.
            This can be an integer, which will be interpreted as seconds, or a
            time string using the same format as Vault does:
            Suffix ``s`` for seconds, ``m`` for minutes, ``h`` for hours, ``d`` for days.
            Defaults to 0.

        uses
            Check whether the token has at least this number of uses left. Defaults to 1.
        """
        return self.is_valid_for(valid_for) and self.has_uses_left(uses)

    def is_renewable(self):
        """
        Check whether the token is renewable, which requires it
        to be currently valid for at least two uses and renewable
        """
        # Renewing a token deducts a use, hence it does not make sense to
        # renew a token on the last use
        return self.renewable and self.is_valid(uses=2)

    def payload(self):
        """
        Return the payload to use for POST requests using this token
        """
        return {"token": str(self)}

    def serialize_for_minion(self):
        """
        Serialize all necessary data to recreate this object
        into a dict that can be sent to a minion.
        """
        return {
            "client_token": self.id,
            "renewable": self.renewable,
            "lease_duration": self.duration,
            "num_uses": self.num_uses,
            "creation_time": self.creation_time,
            "expire_time": self.expire_time,
        }


class VaultSecretId(UseCountMixin, AccessorMixin, BaseLease):
    """
    Data object representing an AppRole secret ID.
    """

    def __init__(self, **kwargs):
        if "secret_id" in kwargs:
            # Ensure response data from Vault is accepted as well
            kwargs["lease_id"] = kwargs.pop("secret_id")
            kwargs["lease_duration"] = kwargs.pop("secret_id_ttl")
            kwargs["num_uses"] = kwargs.pop("secret_id_num_uses", 0)
            kwargs["accessor"] = kwargs.pop("secret_id_accessor", None)
        super().__init__(**kwargs)

    def is_valid(self, valid_for=0, uses=1):
        """
        Checks whether the secret ID is valid for an amount of time and number of uses

        valid_for
            Check whether the secret ID will still be valid in the future.
            This can be an integer, which will be interpreted as seconds, or a
            time string using the same format as Vault does:
            Suffix ``s`` for seconds, ``m`` for minutes, ``h`` for hours, ``d`` for days.
            Defaults to 0.

        uses
            Check whether the secret ID has at least this number of uses left. Defaults to 1.
        """
        return self.is_valid_for(valid_for) and self.has_uses_left(uses)

    def payload(self):
        """
        Return the payload to use for POST requests using this secret ID
        """
        return {"secret_id": str(self)}

    def serialize_for_minion(self):
        """
        Serialize all necessary data to recreate this object
        into a dict that can be sent to a minion.
        """
        return {
            "secret_id": self.id,
            "secret_id_ttl": self.duration,
            "secret_id_num_uses": self.num_uses,
            "creation_time": self.creation_time,
            "expire_time": self.expire_time,
        }


class VaultWrappedResponse(AccessorMixin, BaseLease):
    """
    Data object representing a wrapped response
    """

    def __init__(
        self,
        token,
        ttl,
        creation_path,
        wrapped_accessor=None,
        **kwargs,
    ):
        super().__init__(lease_id=token, lease_duration=ttl, renewable=False, **kwargs)
        self.creation_path = creation_path
        self.wrapped_accessor = wrapped_accessor

    def serialize_for_minion(self):
        """
        Serialize all necessary data to recreate this object
        into a dict that can be sent to a minion.
        """
        return {
            "wrap_info": {
                "token": self.id,
                "ttl": self.duration,
                "creation_time": self.creation_time,
                "creation_path": self.creation_path,
            },
        }


class LeaseStore:
    """
    Caches leases and handles lease operations
    """

    def __init__(self, client, cache):
        self.client = client
        self.cache = cache
        # to update cached leases after renewal/revocation, we need a mapping id => ckey
        self.lease_id_ckey_cache = {}

    def get(
        self,
        ckey,
        valid_for=0,
        renew=True,
        renew_increment=None,
        renew_blur=2,
        revoke=True,
    ):
        """
        Return cached lease or None.

        ckey
            Cache key the lease has been saved in.

        valid_for
            Ensure the returned lease is valid for at least this amount of time.
            This can be an integer, which will be interpreted as seconds, or a
            time string using the same format as Vault does:
            Suffix ``s`` for seconds, ``m`` for minutes, ``h`` for hours, ``d`` for days.
            Defaults to 0.

            .. note::

                This does not take into account token validity, which active leases
                are bound to as well.

        renew
            If the lease is still valid, but not valid for ``valid_for``, attempt to
            renew it. Defaults to true.

        renew_increment
            When renewing, request the lease to be valid for this amount of time from
            the current point of time onwards.
            If unset, will renew the lease by its default validity period and, if
            the renewed lease does not pass ``valid_for``, will try to renew it
            by ``valid_for``.

        renew_blur
            When checking validity after renewal, allow this amount of seconds in leeway
            to account for latency. Especially important when renew_increment is unset
            and the default validity period is less than ``valid_for``.
            Defaults to 2.

        revoke
            If the lease is invalid or not valid for ``valid_for`` and renewals
            are disabled or impossible, attempt to revoke the lease if possible
            and flush the cache. Defaults to true.
        """
        if renew_increment is not None and timestring_map(valid_for) > timestring_map(
            renew_increment
        ):
            raise VaultInvocationError(
                "When renew_increment is set, it must be at least valid_for to make sense"
            )

        def check_revoke(lease):
            if revoke:
                self.revoke(lease)
            return None

        # Since we can renew leases, do not check for future validity in cache
        lease = self.cache.get(ckey, flush=revoke)
        if lease is not None:
            self.lease_id_ckey_cache[str(lease)] = ckey
        if lease is None or lease.is_valid(valid_for):
            return lease
        if not renew:
            return check_revoke(lease)
        lease = self.renew(lease, increment=renew_increment, raise_error=False)
        if not lease.is_valid(valid_for, blur=renew_blur):
            if renew_increment is not None:
                # valid_for cannot possibly be respected
                return check_revoke(lease)
            # Maybe valid_for is greater than the default validity period, so check if
            # the lease can be renewed by valid_for
            lease = self.renew(lease, increment=valid_for, raise_error=False)
            if not lease.is_valid(valid_for, blur=renew_blur):
                return check_revoke(lease)
        return lease

    def list(self):
        """
        List all cached leases.
        """
        return self.cache.list()

    def lookup(self, lease):
        """
        Lookup lease meta information.

        lease
            A lease ID or VaultLease object to look up.
        """
        endpoint = "sys/leases/lookup"
        payload = {"lease_id": str(lease)}
        return self.client.post(endpoint, payload=payload)

    def renew(self, lease, increment=None, raise_error=True):
        """
        Renew a lease.

        lease
            A lease ID or VaultLease object to renew.

        increment
            Request the lease to be valid for this amount of time from the current
            point of time onwards. Can also be used to reduce the validity period.
            The server might not honor this increment.
            Can be an integer (seconds) or a time string like ``1h``. Optional.

        raise_error
            When ``lease`` is a VaultLease and the renewal does not succeed,
            do not catch exceptions. If this is false, the lease will be returned
            unmodified. Defaults to true.
        """
        endpoint = "sys/leases/renew"
        payload = {"lease_id": str(lease)}
        if increment is not None:
            payload["increment"] = int(timestring_map(increment))
        if not isinstance(lease, VaultLease) and lease in self.lease_id_ckey_cache:
            lease = self.cache.get(self.lease_id_ckey_cache[lease], flush=False)
            if lease is None:
                raise VaultNotFoundError("Lease is already expired")
        try:
            ret = self.client.post(endpoint, payload=payload)
        except VaultException:
            if raise_error or not isinstance(lease, VaultLease):
                raise
            return lease

        if isinstance(lease, VaultLease):
            # Do not overwrite data of renewed leases!
            ret.pop("data", None)
            new_lease = lease.with_renewed(**ret)
            if str(new_lease) in self.lease_id_ckey_cache:
                self.store(self.lease_id_ckey_cache[str(new_lease)], new_lease)
            return new_lease
        return ret

    def renew_cached(self, match, increment=None):
        """
        Renew cached leases.

        match
            Only renew cached leases whose ckey matches this glob pattern.
            Defaults to ``*``.

        increment
            Request the leases to be valid for this amount of time from the current
            point of time onwards. Can also be used to reduce the validity period.
            The server might not honor this increment.
            Can be an integer (seconds) or a time string like ``1h``. Optional.
        """
        failed = []
        for ckey in self.list():
            if not fnmatch.fnmatch(ckey, match):
                continue
            lease = self.cache.get(ckey, flush=True)
            if lease is None:
                continue
            self.lease_id_ckey_cache[str(lease)] = ckey
            try:
                self.renew(lease, increment=increment)
            except (VaultPermissionDeniedError, VaultNotFoundError) as err:
                log.warning(f"Failed renewing cached lease: {type(err).__name__}")
                log.debug(f"Lease ID was: {lease}")
                failed.append(ckey)
        if failed:
            raise VaultException(f"Failed renewing some leases: {list(failed)}")
        return True

    def revoke(self, lease, sync=False, allow_validity_reduction=True):
        """
        Revoke a lease. Will also remove the cached lease,
        if it has been requested from this LeaseStore before.

        lease
            A lease ID or VaultLease object to revoke.

        sync
            Only return once the lease has been revoked. Defaults to false.

        allow_validity_reduction
            If a revocation is denied on the grounds of missing permissions,
            instead reduce the lease validity to 1 second.
            The default policy does not include the necessary permissions for
            revocation, hence this switch. Defaults to true.
        """
        endpoint = "sys/leases/revoke"
        payload = {"lease_id": str(lease), "sync": sync}
        try:
            self.client.post(endpoint, payload=payload)
        except VaultNotFoundError:
            pass
        except VaultPermissionDeniedError:
            if not allow_validity_reduction:
                raise
            self.renew(lease, increment=1)

        if str(lease) in self.lease_id_ckey_cache:
            self.cache.flush(self.lease_id_ckey_cache.pop(str(lease)))
        return True

    def revoke_cached(
        self,
        match="*",
        sync=False,
        allow_validity_reduction=True,
        flush_on_failure=True,
    ):
        """
        Revoke cached leases.

        match
            Only revoke cached leases whose ckey matches this glob pattern.
            Defaults to ``*``.

        sync
            Wait for revocation success of all leases. Defaults to false.

        allow_validity_reduction
            If a revocation is denied on the grounds of missing permissions,
            instead reduce the lease validity to 1 second.
            The default policy does not include the necessary permissions for
            revocation, hence this switch. Defaults to true.

        flush_on_failure
            If a revocation fails, remove the lease from cache anyways.
            Defaults to true.
        """
        failed = []
        for ckey in self.list():
            if not fnmatch.fnmatch(ckey, match):
                continue
            lease = self.cache.get(ckey, flush=True)
            if lease is None:
                continue
            self.lease_id_ckey_cache[str(lease)] = ckey
            try:
                self.revoke(
                    lease, sync=sync, allow_validity_reduction=allow_validity_reduction
                )
            except VaultPermissionDeniedError:
                failed.append(ckey)
                if flush_on_failure:
                    # Forget the lease and let Vault's automatic revocation handle it
                    self.cache.flush(self.lease_id_ckey_cache.pop(str(lease)))
        if failed:
            raise VaultException(f"Failed revoking some leases: {list(failed)}")
        return True

    def store(self, ckey, lease):
        """
        Cache a lease.

        ckey
            The cache key the lease should be saved in.

        lease
            A lease ID or VaultLease object to store.
        """
        self.cache.store(ckey, lease)
        self.lease_id_ckey_cache[str(lease)] = ckey
        return True
