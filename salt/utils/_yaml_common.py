import collections
import contextvars
import logging
import warnings

import salt.utils.versions
import salt.version
from salt.utils.decorators import classproperty
from salt.version import SaltStackVersion

__opts__ = {
    "yaml_compatibility": None,
}
__salt_loader__ = None

log = logging.getLogger(__name__)

_compat_opt = contextvars.ContextVar(f"{__name__}._compat_opt")
_compat_ver = contextvars.ContextVar(f"{__name__}._compat_ver")

# Current Salt release.  Changing this value potentially changes the default
# behavior of the YAML loader/dumper logic (the behavior when the
# `yaml_compatibility` option is left unset).  This should be kept in sync with
# `SaltStackVersion.current_release()` (modulo
# https://github.com/saltstack/salt/issues/62972).
#
# This variable could be initialized to `SaltStackVersion.current_release()` to
# avoid the need to manually keep it in sync, but updating it separately has a
# few advantages:
#   * It is easier to create a new release because doing so can't trigger YAML
#     behavior changes that cause test failures that are difficult to root
#     cause.
#   * Updating this in a separate commit makes it possible for `git bisect` to
#     reveal that a mysterious new bug is caused by a YAML behavior change.
#   * Updating this in a separate PR provides a good opportunity to mention in
#     the changelog that previously announced opt-in YAML behavior changes are
#     now opt-out.
_current_ver = SaltStackVersion(3006)


class OverrideNotice(UserWarning):
    pass


class UnsupportedValueWarning(UserWarning):
    pass


# Delayed import of salt.loader.context to avoid a circular import error.
def _init():
    global __salt_loader__, __opts__
    if __salt_loader__ is None:
        import salt.loader.context
        __salt_loader__ = salt.loader.context.LoaderContext()
        __opts__ = __salt_loader__.named_context("__opts__", __opts__)


def compat_ver():
    """Gets the Salt version the YAML loader/dumper should try to match

    Occasionally, the behavior of :py:mod:`~salt.utils.yaml` is changed in ways
    that can subtly break backwards compatibility.  This function returns a
    :py:class:`salt.version.SaltStackVersion` object that represents the parsed
    and validated value of the ``yaml_compatibility`` configuration option.
    That option provides a way for users to force the behavior of the YAML
    loader/dumper to match that of a specific version of Salt until they work
    out any compatibility issues.
    """
    _init()
    v = _compat_ver.get(None)
    opt = __opts__.get("yaml_compatibility")
    # This function is called very early during start-up -- before the config is
    # loaded -- so __opts__["yaml_compatibility"] might not be populated yet.
    if v is None or opt != _compat_opt.get(None):
        _compat_opt.set(opt)

        def _warn(msg, category):
            log.warning(msg)
            warnings.warn(msg, category)

        # Warn devs to update _current_ver after each release.
        actual_current_ver = SaltStackVersion.current_release()
        # TODO: This loop can be removed after fixing
        # https://github.com/saltstack/salt/issues/62972
        for v in salt.version.SaltVersionsInfo.versions():
            if not v.released:
                actual_current_ver = SaltStackVersion(*v.info)
                break
        if _current_ver < actual_current_ver:
            _warn(
                f"{__name__}._current_ver is behind ({_current_ver}); please "
                f"update it to the current release ({actual_current_ver})",
                RuntimeWarning,
            )

        v = _current_ver
        if opt:
            if isinstance(opt, SaltStackVersion):
                v = opt
            elif isinstance(opt, int):
                v = SaltStackVersion(opt)
            else:
                v = SaltStackVersion.parse(opt)
        opt_supported = True  # Whether the value in opt is supported.
        for changev, dropv in [
            # List of version pairs.  The first version in the pair indicates
            # when a change in the default behavior took (or will take) effect.
            # The second version in the pair indicates when support for
            # yaml_compatibility values less than the first version will be
            # dropped.
            (3006, 3006),  # Versions < 3006 have never been supported.
            (3007, 3011),  # Support for < 3007 will be dropped in 3011.
        ]:
            changev = SaltStackVersion(changev)
            dropv = SaltStackVersion(dropv)
            if v < changev:
                if _current_ver >= dropv:
                    opt_supported = False
                    v = changev
                elif opt:
                    _warn(
                        "support for yaml_compatibility option values less "
                        f"than {changev} will be removed in Salt {dropv}",
                        FutureWarning,
                    )
            if not opt and changev > _current_ver and v < changev:
                _warn(
                    "Salt's default YAML processing behavior will change in "
                    f"version {changev}; to preview the changes set the "
                    f"yaml_compatibility option to {changev} or higher",
                    FutureWarning,
                )
        if not opt_supported:
            # This is a bug in the user's config (or in Salt tests).
            _warn(
                f"the value of the yaml_compatibility option is less than the "
                f"minimum supported value {v}: {opt!r}",
                UnsupportedValueWarning,
            )
        if opt:
            _warn(
                f"forcing YAML processing behavior to match Salt version {v} "
                "due to yaml_compatibility option",
                OverrideNotice,
            )
        log.debug(f"YAML compatibility version: {v}")
        _compat_ver.set(v)
    return v


class VersionedSubclassesMixin:
    """Automatically adds version-specific subclasses as class attributes.

    For each main type that inherits this mixin, an additional subclass per
    supported ``yaml_compatibility`` version range is automatically defined and
    saved as an attribute of the main type.  Each of these version-specific
    subtypes has multiple base classes: the associated main type, and the
    version-specific subtypes associated with the main type's base types.  For
    example, with types Foo◀─Bar◀─Baz and versions 3006 and 3007, the
    inheritance DAG will look like this::

        VersionedSubclassesMixin
         ▲
         │
        Foo◀─────╮──────────╮
         ▲       │          │
         │   Foo.V3006  Foo.V3007
         │       ▲          ▲
        Bar◀───╮─│────────╮ │
         ▲     ╰─┤        ╰─┤
         │   Bar.V3006  Bar.V3007
         │       ▲          ▲
        Baz◀───╮─│────────╮ │
               ╰─┤        ╰─┤
             Baz.V3006  Baz.V3007

    """

    @classmethod
    def __init_subclass__(
        cls, *, versioned_properties=(), _versioned_subclass=False, **kwargs
    ):
        """Automatically adds version-specific subclasses as class attributes.

        :param versioned_properties:
            Optional iterable of names that refer to getters decorated by
            :py:func:`~salt.utils.decorators.classproperty`.  For each name, a
            new ``classproperty``-decorated getter is defined that uses the
            return value of :py:func:`compat_ver` to automatically select the
            getter from the appropriate versioned subclass.

        """
        super().__init_subclass__(**kwargs)
        if _versioned_subclass:
            return

        for name in versioned_properties:

            def make_getter(name):  # Capture the loop value in the closure.
                def getter(cls):
                    # This getter is inherited by the versioned subclasses.
                    if getattr(cls, "_versioned_subclass_for", None):
                        return getattr(super(), name)
                    elif compat_ver() < SaltStackVersion(3007):
                        return getattr(cls.V3006, name)
                    else:
                        return getattr(cls.V3007, name)

                getter.__name__ = name
                getter.__qualname__ = f"{cls.__qualname__}.{name}"
                return getter

            setattr(cls, name, classproperty(make_getter(name)))

        def add_versioned_subclass(attr):
            bases = tuple(
                [cls]
                + [
                    getattr(b, attr)
                    for b in cls.__bases__
                    if (
                        issubclass(b, VersionedSubclassesMixin)
                        and not issubclass(VersionedSubclassesMixin, b)
                    )
                ]
            )
            subcls = type(
                f"{cls.__name__}.{attr}",
                bases,
                {"_versioned_subclass_for": cls},
                # This new type is derived from VersionedSubclassesMixin, so we
                # need to prevent infinite recursion (versioned subclasses
                # should not have their own nested versioned subclasses).
                _versioned_subclass=True,
            )
            setattr(cls, attr, subcls)

        add_versioned_subclass("V3006")
        add_versioned_subclass("V3007")


class InheritMapMixin:
    """Adds :py:class:`collections.ChainMap` class attributes based on MRO.

    The added class attributes provide each subclass with its own mapping that
    works just like method resolution: each ancestor type in ``__mro__`` is
    visited until an entry is found in the ancestor-owned map.

    For example, for an inheritance DAG of ``InheritMapMixin`` <- ``Foo`` <-
    ``Bar`` <- ``Baz`` and a desired attribute name of ``"_m"``:

    1. ``Foo._m`` is set to ``ChainMap({})``.
    2. ``Bar._m`` is set to ``ChainMap({}, Foo._m.maps[0])``.
    3. ``Baz._m`` is set to ``ChainMap({}, Bar._m.maps[0], Foo._m.maps[0])``.

    This mixin makes it possible to improve PyYAML's representer and constructor
    registration APIs.  Currently, the PyYAML
    :py:class:`yaml.representer.BaseRepresenter` and
    :py:class:`yaml.constructor.BaseConstructor` classes do not use base class
    inheritance of registered representers/constructors.  Instead, the base
    class's registrations are copied to the subclass's registration dict the
    first time a registration is added to the subclass.  (Before the first
    registration is added to the subclass, MRO lookup finds the base class's
    registration dict.)  This means that any registrations added to a base class
    after a registration is added to a subclass do not automatically appear in
    the subclass.  This results in the need to either add all registrations
    before any subclass registrations are added, or manually add registrations
    to each subclass in addition to the base class.

    If this mixin is used to provide ``yaml_representers`` and
    ``yaml_multi_representers`` class attributes for PyYAML dumper classes,
    then registered representers are truly inherited, not copied, from their
    base classes.  The same goes for constructors registered in the
    ``yaml_constructors`` and ``yaml_multi_constructors`` class attributes for
    PyYAML loader classes.

    """

    @classmethod
    def __init_subclass__(cls, *, inherit_map_attrs=None, **kwargs):
        """Adds :py:class:`collections.ChainMap` class attributes based on MRO.

        :param inherit_map_attrs:
            Optional mapping:

            * Each key in the mapping is the name of a class attribute that will
              be set to a :py:class:`~collections.ChainMap` containing the
              MRO-based list of ancestor maps.
            * Each value is an optional (may be ``None``) fallback class
              attribute name to try if an ancestor class in the MRO does not
              have a chain map provided by ``InheritMapMixin``.  For such
              ancestor classes, if it has a non-``None`` attribute with that
              name, the value is added to the chain if it is not already
              present.

        """
        super().__init_subclass__(**kwargs)
        attrs = getattr(cls, "_inherit_map_attrs", {})
        if inherit_map_attrs:
            attrs = {**attrs, **inherit_map_attrs}
            cls._inherit_map_attrs = attrs
        for name, fallback_name in attrs.items():
            maps = [{}]
            for c in cls.__mro__[1:]:  # cls.__mro__[0] is cls itself.
                if issubclass(InheritMapMixin, c):
                    continue  # Ignore InheritMapMixin itself and object.
                c_attrs = getattr(c, "_inherit_map_attrs", {})
                if issubclass(c, InheritMapMixin) and name in c_attrs:
                    maps.append(getattr(c, name).maps[0])
                elif fallback_name:
                    m = getattr(c, fallback_name, None)
                    if m is not None and m not in maps:
                        maps.append(m)
            setattr(cls, name, collections.ChainMap(*maps))
