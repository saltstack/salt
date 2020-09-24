from collections.abc import Iterable, Mapping

try:
    from marshmallow import ValidationError
    from marshmallow.fields import (  # pylint: disable=unused-import
        Str,
        Bool,
        Dict,
        Field,
        Raw,
    )
except ModuleNotFoundError:
    marshmallow = None


class FileMode(Field):
    def _deserialize(self, value, attr, data, **kwargs):
        if isinstance(value, (int, str)):
            return value
        raise ValidationError("Value must be str or int")


class StringList(Field):
    def _deserialize(self, value, attr, data, **kwargs):
        if isinstance(value, (bytes, str, Iterable)) and not isinstance(value, Mapping):
            return value
        raise ValidationError("Value must be str or int")


class Charset(Field):
    def __init__(self, charset, **kwargs):
        super().__init__(**kwargs)
        self.charset = set(charset)

    def _deserialize(self, value, attr, data, **kwargs):
        if isinstance(value, (bytes, str)) and all(
            (char in self.charset for char in value)
        ):
            return value
        raise ValidationError("Value must be str or bytes")
