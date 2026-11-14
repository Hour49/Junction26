"""A service model's elements as a graph: which element connects to which (the model's own port
connections) and which system each belongs to. Ids in, plain typed results out: no geometry, no
file, so the edit follow-up (follow.py) and read-only questions ("what feeds this radiator")
ask the same graph.

Connections are asked per system where it matters: a fixture bridges its systems (a urinal is
on cold water and on waste), so "still connected" has no answer without naming the system.
"""

from collections.abc import Iterable, Set
from typing import Final

from app.core.services.model import ServiceElement

NO_ONE: Final[frozenset[str]] = frozenset()


class ServiceGraph:
    def __init__(self, elements: Iterable[ServiceElement]) -> None:
        self._by_guid = {element.guid: element for element in elements}
        members: dict[str, set[str]] = {}
        for element in self._by_guid.values():
            for system in element.systems:
                members.setdefault(system, set()).add(element.guid)
        self._members = {system: frozenset(guids) for system, guids in members.items()}

    def get(self, guid: str) -> ServiceElement | None:
        return self._by_guid.get(guid)

    def systems(self) -> tuple[str, ...]:
        return tuple(sorted(self._members))

    def members(self, system: str) -> frozenset[str]:
        """The elements of a system; empty for a name the model does not have."""
        return self._members.get(system, NO_ONE)

    def neighbours(self, guid: str, system: str | None = None) -> tuple[str, ...]:
        """The elements `guid`'s ports connect to; with `system`, only those in that system."""
        element = self._by_guid.get(guid)
        if element is None:
            return ()
        allowed = None if system is None else self.members(system)
        return tuple(
            other
            for other in element.neighbours
            if other in self._by_guid and (allowed is None or other in allowed)
        )

    def part(
        self, guid: str, system: str | None = None, without: Set[str] = NO_ONE
    ) -> frozenset[str]:
        """Everything connected to `guid` (itself included), staying inside `system` when one
        is named and never passing through an element of `without`. Empty when `guid` is
        unknown, not in the system or itself in `without`."""
        allowed = None if system is None else self.members(system)
        if (
            guid not in self._by_guid
            or guid in without
            or (allowed is not None and guid not in allowed)
        ):
            return NO_ONE
        found = {guid}
        edge = [guid]
        while edge:
            for other in self.neighbours(edge.pop(), system):
                if other not in found and other not in without:
                    found.add(other)
                    edge.append(other)
        return frozenset(found)

    def largest(self, system: str, without: Set[str] = NO_ONE) -> frozenset[str]:
        """The largest connected part of a system once the elements of `without` are gone: what
        "the rest of the system" means after a cut. Ties go to the part with the lowest id."""
        best: frozenset[str] = NO_ONE
        left = set(self.members(system)) - set(without)
        while left:
            part = self.part(min(left), system, without)
            left -= part
            if len(part) > len(best):
                best = part
        return best

    def path(self, start: str, end: str, system: str | None = None) -> tuple[str, ...]:
        """The fewest-connections path from `start` to `end`, both included; empty: none."""
        if start not in self.part(end, system):
            return ()
        came: dict[str, str | None] = {start: None}
        edge = [start]
        while edge and end not in came:
            following: list[str] = []
            for guid in edge:
                for other in self.neighbours(guid, system):
                    if other not in came:
                        came[other] = guid
                        following.append(other)
            edge = following
        found: list[str] = []
        at: str | None = end
        while at is not None:
            found.append(at)
            at = came[at]
        return tuple(reversed(found))

    def terminals(self, guids: Iterable[str]) -> tuple[ServiceElement, ...]:
        """The terminals among `guids` (fixtures, radiators, air terminals), in id order."""
        found = (self._by_guid.get(guid) for guid in sorted(guids))
        return tuple(element for element in found if element is not None and element.is_terminal)
