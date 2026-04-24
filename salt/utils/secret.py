"""
Pillar containers that wrap string/bytes leaves with secret-safe types
(:class:`SecretStr` / :class:`SecretBytes`) and use SecretDict/SecretList so later
mutations stay protected.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, MutableMapping, MutableSequence
from typing import Any, ClassVar, Generic, Mapping, TypeVar

log = logging.getLogger(__name__)

REDACT_PLACEHOLDER = "**********"

SecretType_co = TypeVar("SecretType_co", covariant=True)


class Secret(Generic[SecretType_co]):
    def __init__(self, secret_value) -> None:
        self._secret_value = secret_value

    def get_secret_value(self) -> Any:
        """Get the secret value.

        Returns:
            The secret value.
        """
        return self._secret_value

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, self.__class__)
            and self.get_secret_value() == other.get_secret_value()
        )

    def __hash__(self) -> int:
        return hash(self.get_secret_value())

    def __str__(self) -> str:
        return str(self._display())

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._display()!r})"

    def _display(self) -> str | bytes:
        raise NotImplementedError


class SecretStr(Secret[str]):
    """A string used for storing sensitive information that you do not want to be visible in logging or tracebacks.

    When the secret value is nonempty, it is displayed as `'**********'` instead of the underlying value in
    calls to `repr()` and `str()`. If the value _is_ empty, it is displayed as `''`.

    ```python
    from pydantic import BaseModel, SecretStr

    class User(BaseModel):
        username: str
        password: SecretStr

    user = User(username='scolvin', password='password1')

    print(user)
    #> username='scolvin' password=SecretStr('**********')
    print(user.password.get_secret_value())
    #> password1
    print((SecretStr('password'), SecretStr('')))
    #> (SecretStr('**********'), SecretStr(''))
    ```

    As seen above, by default, [`SecretStr`][pydantic.types.SecretStr] (and [`SecretBytes`][pydantic.types.SecretBytes])
    will be serialized as `**********` when serializing to json.

    You can use the [`field_serializer`][pydantic.functional_serializers.field_serializer] to dump the
    secret as plain-text when serializing to json.

    ```python
    from pydantic import BaseModel, SecretBytes, SecretStr, field_serializer

    class Model(BaseModel):
        password: SecretStr
        password_bytes: SecretBytes

        @field_serializer('password', 'password_bytes', when_used='json')
        def dump_secret(self, v):
            return v.get_secret_value()

    model = Model(password='IAmSensitive', password_bytes=b'IAmSensitiveBytes')
    print(model)
    #> password=SecretStr('**********') password_bytes=SecretBytes(b'**********')
    print(model.password)
    #> **********
    print(model.model_dump())
    '''
    {
        'password': SecretStr('**********'),
        'password_bytes': SecretBytes(b'**********'),
    }
    '''
    print(model.model_dump_json())
    #> {"password":"IAmSensitive","password_bytes":"IAmSensitiveBytes"}
    ```
    """

    _error_kind: ClassVar[str] = "string_type"

    def __len__(self) -> int:
        return len(self._secret_value)

    def _display(self) -> str:
        return REDACT_PLACEHOLDER if self._secret_value else ""


class SecretBytes(Secret[bytes]):
    """A bytes used for storing sensitive information that you do not want to be visible in logging or tracebacks.

    It displays `b'**********'` instead of the string value on `repr()` and `str()` calls.
    When the secret value is nonempty, it is displayed as `b'**********'` instead of the underlying value in
    calls to `repr()` and `str()`. If the value _is_ empty, it is displayed as `b''`.

    ```python
    from pydantic import BaseModel, SecretBytes

    class User(BaseModel):
        username: str
        password: SecretBytes

    user = User(username='scolvin', password=b'password1')
    #> username='scolvin' password=SecretBytes(b'**********')
    print(user.password.get_secret_value())
    #> b'password1'
    print((SecretBytes(b'password'), SecretBytes(b'')))
    #> (SecretBytes(b'**********'), SecretBytes(b''))
    ```
    """

    _error_kind: ClassVar[str] = "bytes_type"

    def __len__(self) -> int:
        return len(self._secret_value)

    def _display(self) -> bytes:
        return REDACT_PLACEHOLDER.encode() if self._secret_value else b""


class SecretIterable(Secret[SecretType_co]):
    def get_secret_value(self):
        cast = type(self._secret_value)
        return cast(expose(v) for v in self._secret_value)

    def __len__(self):
        return len(self._secret_value)

    def __iter__(self):
        return iter(self._secret_value)

    def __getitem__(self, key):
        return self._secret_value[key]

    def __setitem__(self, key, value):
        self._secret_value[key] = hide(value)

    def __delitem__(self, key):
        del self._secret_value[key]

    def _display(self):
        cast = type(self._secret_value)
        return cast(v._display() if isinstance(v, Secret) else v for v in self)


class SecretDict(SecretIterable[dict], MutableMapping[str, Any]):
    def __init__(self, secret_value: dict):
        super().__init__({})
        self._secret_value.update({k: hide(v) for k, v in secret_value.items()})

    def get_secret_value(self):
        return {k: expose(v) for k, v in self._secret_value.items()}

    def _display(self) -> dict:
        return {
            k: v._display() if isinstance(v, Secret) else v
            for k, v in self.items()
        }


class SecretList(SecretIterable[list], MutableSequence[Any]):
    def __init__(self, secret_value: list):
        super().__init__([])
        self._secret_value.extend(hide(item) for item in secret_value)

    def insert(self, index: int, value):
        self._secret_value.insert(index, hide(value))


def hide(value: Any) -> Secret:
    """
    Morph a leaf value into a secret-safe container.
    Args:
        value: The value to morph.
    Returns:
        The morphed value.
    """
    if isinstance(value, Secret):
        return value
    elif isinstance(value, str):
        return SecretStr(value)
    elif isinstance(value, bytes):
        return SecretBytes(value)
    elif isinstance(value, dict):
        return SecretDict(value)
    elif isinstance(value, Iterable):
        return SecretList(value)
    else:
        return value


def expose(value: Secret) -> Any:
    """
    If the value is a secret, return the secret value.
    """
    if isinstance(value, (str, bytes)):
        return value
    elif isinstance(value, Secret):
        return value.get_secret_value()
    elif isinstance(value, dict):
        return {k: expose(v) for k, v in value.items()}
    elif isinstance(value, Iterable):
        cast = type(value)
        return cast(expose(v) for v in value)
    else:
        return value


def serial(value):
    """
    Keep secrets redacted while serializing the structure to native python types.
    """
    if isinstance(value, (str, bytes)):
        return value
    elif isinstance(value, Secret):
        return value._display()
    elif isinstance(value, Mapping):
        return {k: serial(v) for k, v in value.items()}
    elif isinstance(value, Iterable):
        return [serial(v) for v in value]
    else:
        return value


def no_log_mask(state_ret: dict[str, Any]):
    """
    Replace comment and changes in a state return dict when no_log is enabled.
    Mutates ret in place.
    """
    state_ret["comment"] = REDACT_PLACEHOLDER
    state_ret["changes"] = {REDACT_PLACEHOLDER: REDACT_PLACEHOLDER}


def _gather(obj: Secret) -> list[str | bytes]:
    """
    Gather all the secret values from the object from longest to shortest.
    """
    secrets = set()
    if isinstance(obj, SecretDict):
        for v in obj.values():
            secrets.update(_gather(v))
    elif isinstance(obj, SecretIterable):
        for v in obj:
            secrets.update(_gather(v))
    elif isinstance(obj, Secret):
        secrets.add(obj.get_secret_value())

    return sorted(secrets, key=len, reverse=True)


def redact(value, secrets: Secret, known: list[str | bytes] = None) -> str:
    """
    If any secrets are found in the value, replace them with the placeholder.
    """
    if known is None:
        known = _gather(secrets)

    # If the value contains a known secret, replace the secret substring with the secret placeholder. value could be any type
    if isinstance(value, str):
        for secret in known:
            if isinstance(secret, bytes):
                secret_str = secret.decode()
            else:
                secret_str = secret
            if secret_str in value:
                value = value.replace(secret_str, "*" * len(secret_str))
    elif isinstance(value, bytes):
        for secret in known:
            if isinstance(secret, str):
                secret_bytes = secret.encode()
            else:
                secret_bytes = secret
            if secret_bytes in value:
                value = value.replace(secret_bytes, b"*" * len(secret_bytes))
    elif isinstance(value, dict):
        value = {k: redact(v, secrets, known) for k, v in value.items()}
    elif isinstance(value, Iterable):
        value = [redact(v, secrets, known) for v in value]

    return value
