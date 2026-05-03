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
        return self.get_secret_value() == other

    def __instancecheck__(self, instance: Any) -> bool:
        return isinstance(instance, self.__class__) or isinstance(instance, self.get_secret_value().__class__)

    def __hash__(self) -> int:
        return hash(self.get_secret_value())

    def __str__(self) -> str:
        return str(self._display())

    def __contains__(self, item: Any) -> bool:
        return item in self._secret_value

    def __bool__(self) -> bool:
        return bool(self._secret_value)

    def __len__(self) -> int:
        return len(self._secret_value)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._display()!r})"

    def _display(self):
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

    def _display(self) -> bytes:
        return REDACT_PLACEHOLDER.encode() if self._secret_value else b""


class SecretIterable(Secret[SecretType_co]):
    def __contains__(self, item: Any) -> bool:
        return item in self._secret_value

    def __iter__(self):
        return iter(self._secret_value)

    def __getitem__(self, key):
        return self._secret_value[key]

    def __setitem__(self, key, value):
        self._secret_value[key] = hide(value)

    def __delitem__(self, key):
        del self._secret_value[key]

    def _display(self):
        return [v._display() if isinstance(v, Secret) else v for v in self]


class SecretDict(SecretIterable[dict], MutableMapping[str, Any]):
    def __init__(self, secret_value: dict, exclude: tuple[str, ...] = ()):
        self._exclude = exclude
        for k, v in secret_value.items():
            if k not in exclude:
                secret_value[k] = hide(v)
        super().__init__(secret_value)

    def __setitem__(self, key: str, value: Any) -> None:
        if key in self._exclude:
            self._secret_value[key] = value
        else:
            self._secret_value[key] = hide(value)

    def setdefault(self, key, default=None):
        return self._secret_value.setdefault(key, hide(default))

    def _display(self) -> dict:
        return {
            k: v._display() if isinstance(v, Secret) else v for k, v in self.items()
        }


class SecretList(SecretIterable[list], MutableSequence[Any]):
    def __init__(self, secret_value: list):
        for i, v in enumerate(secret_value):
            secret_value[i] = hide(v)
        super().__init__(secret_value)

    def insert(self, index: int, value):
        self._secret_value.insert(index, hide(value))


class SecretTuple(SecretIterable[tuple]):
    def __init__(self, secret_value: tuple):
        super().__init__(tuple(hide(v) for v in secret_value))

    def _display(self) -> tuple:
        return tuple(v._display() if isinstance(v, Secret) else v for v in self)


def hide(value: Any, exclude: tuple[str, ...] = ()) -> Secret:
    """
    Morph a leaf value into a secret-safe container.
    Args:
        value: The value to morph.
        exclude: A list of keys to exclude from redaction.
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
        return SecretDict(value, exclude=exclude)
    elif isinstance(value, tuple):
        return SecretTuple(value)
    elif isinstance(value, Iterable):
        return SecretList(value)
    else:
        return value


def expose(value: Secret, _seen: set[int] = None) -> Any:
    """
    If the value is a secret, return the secret value.
    """
    if isinstance(value, Secret):
        value = value.get_secret_value()
    if isinstance(value, (str, bytes, int, float, bool)):
        return value
    if not value:
        return value
    if isinstance(value, Iterable):
        if _seen is None:
            _seen = set()
        object_id = id(value)
        if object_id in _seen:
            return f"<Recursion on {type(value).__name__} with id={object_id}>"
        _seen.add(object_id)
        if isinstance(value, Mapping):
            if _seen is None:
                _seen = {object_id}
            return {k: expose(v, _seen) for k, v in value.items()}
        else:
            return [expose(v, _seen) for v in value]
    return value


def serial(value, _seen: set[int] = None):
    """
    Keep secrets redacted while serializing the structure to native python types.
    """
    if isinstance(value, Secret):
        value = value._display()
    if isinstance(value, (str, bytes, int, float, bool)):
        return value
    if not value:
        return value
    if isinstance(value, Iterable):
        if _seen is None:
            _seen = set()
        object_id = id(value)
        if object_id in _seen:
            return f"<Recursion on {type(value).__name__} with id={object_id}>"
        _seen.add(object_id)
        if isinstance(value, Mapping):
            return {k: serial(v) for k, v in value.items()}
        else:
            return [serial(v) for v in value]
    return value


def no_log_mask(state_ret: dict[str, Any]):
    """
    Replace comment and changes in a state return dict when no_log is enabled.
    Mutates ret in place.
    """
    state_ret["comment"] = serial(hide(state_ret["comment"]))
    state_ret["changes"] = serial(hide(state_ret["changes"]))
