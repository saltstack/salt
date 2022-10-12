"""
Default values, to be imported elsewhere in Salt code

Do NOT, import any salt modules (salt.utils, salt.config, etc.) into this file,
as this may result in circular imports.
"""


class _Constant:
    """
    This class implements a way to create constants in python.

    NOTE:

      - This is not really a constant, ie, the `is` check will not work, you'll
        have to use `==`.
      - This class SHALL NOT be considered public API and might change or even
        go away at any given time.
    """

    __slots__ = ("name", "value")

    def __init__(self, name, value=None):
        self.name = name
        self.value = value

    def __hash__(self):
        return hash((self.name, self.value))

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        if self.name != other.name:
            return False
        return self.value == other.value

    def __get_state__(self):
        return {
            "name": self.name,
            "value": self.value,
        }

    def __set_state__(self, state):
        return self.__class__(state["name"], state["value"])

    def __repr__(self):
        if self.value:
            return "<Constant.{} value={}>".format(self.name, self.value)
        return "<Constant.{}>".format(self.name)


# Default delimiter for multi-level traversal in targeting
DEFAULT_TARGET_DELIM = ":"


"""
Used in functions to define that a keyword default is not set.

It's used to differentiate from `None`, `True`, `False` which, in some
cases are proper defaults and are also proper values to pass.
"""
NOT_SET = _Constant("NOT_SET")
