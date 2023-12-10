import logging

from salt.utils.stringutils import camel_to_snake_case

log = logging.getLogger(__name__)

try:
    from testinfra import modules

    TESTINFRA_PRESENT = True
except ImportError:
    TESTINFRA_PRESENT = False

__all__ = []
__virtualname__ = "testinfra"


def __virtual__():
    if TESTINFRA_PRESENT:
        return __virtualname__
    return False, "The Testinfra package is not available"


def _wrap_module_function(func_name):
    def _module_function_wrapper(name, **methods):
        func = __salt__[func_name]
        result, passes, fails = func(name, **methods)
        comment = "\n".join(passes + fails)
        if __opts__["test"] and not result:
            result = None
        return {"name": name, "comment": comment, "result": result, "changes": {}}

    return _module_function_wrapper


def _generate_functions():
    try:
        modules_ = [camel_to_snake_case(module_) for module_ in modules.__all__]
    except AttributeError:
        modules_ = [module_ for module_ in modules.modules]

    for module_name in modules_:
        func_name = "testinfra.{}".format(module_name)
        __all__.append(module_name)
        log.debug(
            "Generating state for module %s as function %s", module_name, func_name
        )
        globals()[module_name] = _wrap_module_function(func_name)


if TESTINFRA_PRESENT:
    _generate_functions()
