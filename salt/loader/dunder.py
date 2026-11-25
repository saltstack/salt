"""
Salt dunders.
"""

import salt.loader.context

loader_context = salt.loader.context.LoaderContext()


# The mapping-typed dunders advertise themselves as
# ``collections.abc.MutableMapping`` via ``NamedLoaderContext``.  If one of
# them slips into a value that ``salt.payload.dumps`` is asked to encode
# while no loader is bound to the current thread, msgpack calls
# ``dict(obj)`` on it, which iterates via ``__iter__`` -> ``value()``.
# Default to an empty dict so ``value()`` never returns ``None`` for the
# mapping shapes and the ``MutableMapping`` contract is honored even
# off-context.  ``__file_client__`` is deliberately not a mapping; ``None``
# is its documented "no file client" sentinel and is left alone.
__file_client__ = loader_context.named_context("__file_client__", default=None)
__opts__ = loader_context.named_context("__opts__", default={})
__context__ = loader_context.named_context("__context__", default={})
__pillar__ = loader_context.named_context("__pillar__", default={})
__grains__ = loader_context.named_context("__grains__", default={})
