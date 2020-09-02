import functools

import salt.utils.args
from salt.exceptions import SaltInvocationError

try:
    from marshmallow import ValidationError
except ModuleNotFoundError:
    marshmallow = None


def validator(schema):
    """
    Decorator wrapper for validating functions
    """

    def wrapper(function):
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            aspec = salt.utils.args.get_function_argspec(function)
            arg_data = salt.utils.args.arg_lookup(function, aspec)

            fun_args = arg_data["args"]
            data = arg_data["kwargs"]
            for name, value in zip(fun_args, args):
                data[name] = value
            if aspec.varargs and len(args) > len(fun_args):
                data[aspec.varargs] = fun_args[len(args) :]
            data.update(kwargs)

            # Do validate, data may be updated
            try:
                data = schema().load(data)
            except ValidationError as ex:
                raise SaltInvocationError(ex)
            # Extract args and kwargs from data dict
            args = [data.pop(arg) for arg in fun_args]
            # Call the funciton
            return function(*args, **data)

        # Set __validator__ attribute to mark the function as self-validated.
        # This also allows to use the schema in circumversion of the wrapper.
        setattr(wrapped, "__validator__", schema)
        return wrapped

    return wrapper
