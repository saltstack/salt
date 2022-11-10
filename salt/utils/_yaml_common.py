import collections


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
