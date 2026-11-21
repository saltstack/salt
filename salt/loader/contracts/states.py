"""
Return contract for ``salt.states.*`` functions.
"""

from salt.utils.versions import reqs

if reqs.pydantic:
    from pydantic import BaseModel, ConfigDict


if reqs.pydantic:
    _CFG = ConfigDict(
        arbitrary_types_allowed=True,
        strict=False,
        extra="ignore",
    )

    class StateReturn(BaseModel):
        """Universal return contract for ``salt.states.*`` functions.

        Every state function must return a dict satisfying this shape.
        A specific state module may declare a more-specific return via
        ``-> SomeSubclass`` where ``SomeSubclass(StateReturn)`` adds
        module-specific fields (e.g. structured ``changes`` or
        ``pchanges``). The loader honors the refinement and validates
        against the more-specific model.
        """

        model_config = _CFG

        name: str
        changes: dict
        result: bool | None
        comment: str | list
        warnings: list | None = None
        pchanges: dict | None = None

else:  # pragma: no cover
    StateReturn = None  # type: ignore[misc,assignment]


__all__ = ["StateReturn"]
