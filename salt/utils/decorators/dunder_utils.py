import inspect
import sys
from collections.abc import Sequence
from functools import partial, wraps

from salt.utils.versions import warn_until


class LoadIterable(Sequence):
    """
    This class is implemented to defer the __load__ module attribute
    populating to only when it's required.

    The reason being that, when python is importing a module, the decorators
    are immediatly applied, without the full module being loaded.
    So, we're not guarantted to be able to get all module attributes when
    calling `dir(module)`` at that stage, which could mean we would leave
    valid function names out of ``__load__``.

    Since we defer it, only when the salt loader tries to iterate this
    class will we look at what should be in this list or not, and by this
    time, the module was fully loaded.
    """

    def __init__(self, module, load_list=None):
        self._module = module
        self._list = load_list or []
        self._loaded = False

    def _load_list(self):
        for name in dir(self._module):
            attr = getattr(self._module, name)
            if not inspect.isfunction(attr) and not isinstance(attr, partial):
                # Not a function!? Skip it!!!
                continue
            if not attr.__module__.startswith(self._module.__name__):
                # It's a function, but it's not defined(or namespaced) to
                # the module in question, skip it
                continue
            try:
                # Functions with the __deprecates__ attribute are meant to be
                # imported and used direcly, they are not meant to be loaded
                # by the salt loader.
                attr.__deprecates__
            except AttributeError:
                if name not in self._list:
                    self._list.append(name)
        self._loaded = True

    # Sized - Abstract method implementation
    def __len__(self):
        if not self._loaded:
            self._load_list()
        return len(self._list)

    # Iterable - Abstract method implementation
    def __iter__(self):
        if not self._loaded:
            self._load_list()
        return iter(self._list)

    # Container - Abstract method implementation
    def __contains__(self, name):
        if not self._loaded:
            self._load_list()
        return name in self._list

    # Sequence - Abstract method implementation
    def __getitem__(self, idx):
        if not self._loaded:
            self._loaded()
        return self._list[idx]


def deprecated(*args, by=None, func_alias_dict=None, load_list=None):
    """
    Deprecate a ``__utils__`` enabled function in ``salt/utils/``.

    Arguments:
        by:
            The function instance which is deprecating the decorated function.
        func_alias_dict:
            If not provided, we will discover the calling module and will add
            a ``__func_alias__`` attribute if not present and will add the
            deprecated function as an alias with the name of the deprecating
            function.
        load_list:
            The existing ``__load__`` list. If not provided, we will discover the
            calling module and will define the module level ``__load__`` attribute.
    """
    if args and len(args) > 1:
        raise RuntimeError(
            "Only keyword arguments are acceptable when calling this function"
        )

    if args:
        func = args[0]
        if not callable(func):
            raise RuntimeError(
                "Only keyword arguments are acceptable when calling this function"
            )
    else:
        func = None

    if by is None:
        raise RuntimeError(
            "The 'by' argument is mandatory and shall be passed as a keyword argument'"
        )

    if not callable(by):
        raise RuntimeError(
            "The 'by' argument needs to be passed the function reference that "
            "deprecates the decorated function"
        )

    if func is None:
        return partial(deprecated, by=by, func_alias_dict=func_alias_dict)

    module = None
    if func_alias_dict is None:
        frame = inspect.currentframe().f_back
        caller_module_name = frame.f_globals["__name__"]
        module = sys.modules[caller_module_name]
        try:
            func_alias_dict = module.__func_alias__
        except AttributeError:
            func_alias_dict = module.__func_alias__ = {}

    if load_list is None:
        if module is None:
            frame = inspect.currentframe().f_back
            caller_module_name = frame.f_globals["__name__"]
            module = sys.modules[caller_module_name]
        try:
            load_list = module.__load__
        except AttributeError:
            load_list = []

    if not isinstance(load_list, LoadIterable):
        if module is None:
            frame = inspect.currentframe().f_back
            caller_module_name = frame.f_globals["__name__"]
            module = sys.modules[caller_module_name]
        load_list = module.__load__ = LoadIterable(module, load_list[:])

    module_name = by.__module__.split(".")[-1]

    import_comment = (
        "Please import 'salt.utils.{mod}' and call "
        "'salt.utils.{mod}.{func}()' directly. Please note any required "
        "argument changes for this new function call.".format(
            mod=module_name, func=by.__name__
        )
    )
    new_doc = """
    This function is deprecated.

    {}

    ------------

    {}
    """.format(
        import_comment, by.__doc__
    )

    # Register a function alias so the salt loader still uses the deprecated version
    func_alias_dict[func.__name__] = by.__name__

    # Define an attribute declaring the function being deprecated
    by.__deprecates__ = func.__name__
    # Define an attribute decalting which function is deprecating
    func.__deprecated_by__ = by.__name__

    # Define our decorator wrapper, which, when called, will issue a deprecation warning.
    @wraps(func)
    def wrapped(*args, **kwargs):
        warn_until(
            3008,
            "The __utils__ loader functionality will be removed in version "
            "{{version}}. {}".format(import_comment),
            stacklevel=3,
        )
        return func(*args, **kwargs)

    # Replace the __doc__ with the one that additionally shows our deprecation message.
    wrapped.__doc__ = new_doc
    return wrapped
