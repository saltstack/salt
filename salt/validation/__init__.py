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
            if len(args) > len(fun_args):
                if aspec.varargs:
                    data[aspec.varargs] = fun_args[len(args) :]
                else:
                    # kwargs passed positionally
                    kws = aspec.args[len(fun_args) :]
                    for name, value in zip(kws, args[len(fun_args) :]):
                        data[name] = value

            data.update(kwargs)

            # Do validate, data may be updated
            try:
                data = schema().load(data)
            except ValidationError as ex:
                msg = "Arguments validation failed for '{}.{}': ".format(
                    function.__module__, function.__name__
                )
                if isinstance(ex.messages, dict):
                    for arg, err in ex.messages.items():
                        msg += "{}: {}".format(arg, ", ".join(err))
                elif isinstance(ex.messages, list):
                    for err in ex.messages:
                        msg += ", ".join(err)
                raise SaltInvocationError(msg)
            # Extract args and kwargs from data dict
            args = [data.pop(arg) for arg in fun_args]
            # Call the function
            return function(*args, **data)

        # Set __validator__ attribute to mark the function as self-validated.
        # This also allows to use the schema in circumversion of the wrapper.
        setattr(wrapped, "__validator__", schema)
        return wrapped

    return wrapper
