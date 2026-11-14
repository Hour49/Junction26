"""The services of an IFC model as plain data (spec services-follow, SF-14): places, port
places, connections, systems, storeys and space centres, in metres whatever the file's unit."""

from typing import Any

import ifcopenshell
import ifcopenshell.guid
import pytest
from ifc_models import IfcFile, box

import app.adapters.ifc_services as ifc_services
from app.adapters.ifc_services import (
    ServiceFiles,
    read_apart,
    read_service_file,
    service_file,
)
from app.core.errors import InvalidInputError


class _Model:
    """A synthetic model in millimetres with placed elements and ports."""

    def __init__(self) -> None:
        self.file: Any = ifcopenshell.file(schema="IFC4")
        mm = self.file.create_entity(
            "IfcSIUnit", UnitType="LENGTHUNIT", Prefix="MILLI", Name="METRE"
        )
        self.project = self._rooted(
            "IfcProject", UnitsInContext=self.file.create_entity("IfcUnitAssignment", [mm])
        )
        self.storeys = [
            self._rooted("IfcBuildingStorey", Name=name, Elevation=height)
            for name, height in (("Upper", 3000.0), ("Ground", 0.0))
        ]
        self._rooted("IfcRelAggregates", RelatingObject=self.project, RelatedObjects=self.storeys)

    def _rooted(self, ifc_class: str, **attrs: Any) -> Any:
        return self.file.create_entity(ifc_class, GlobalId=ifcopenshell.guid.new(), **attrs)

    def _placed(self, x: float, y: float, z: float, relative_to: Any = None) -> Any:
        point = self.file.create_entity("IfcCartesianPoint", Coordinates=(x, y, z))
        axes = self.file.create_entity("IfcAxis2Placement3D", Location=point)
        return self.file.create_entity(
            "IfcLocalPlacement", PlacementRelTo=relative_to, RelativePlacement=axes
        )

    def add(self, ifc_class: str, at: tuple[float, float, float], **attrs: Any) -> Any:
        element = self._rooted(ifc_class, ObjectPlacement=self._placed(*at), **attrs)
        self._rooted(
            "IfcRelContainedInSpatialStructure",
            RelatingStructure=self.storeys[1],
            RelatedElements=[element],
        )
        return element

    def port(self, element: Any, offset: tuple[float, float, float]) -> Any:
        port = self._rooted(
            "IfcDistributionPort", ObjectPlacement=self._placed(*offset, element.ObjectPlacement)
        )
        self._rooted("IfcRelNests", RelatingObject=element, RelatedObjects=[port])
        return port

    def connect(self, a: Any, b: Any) -> None:
        self._rooted("IfcRelConnectsPorts", RelatingPort=a, RelatedPort=b)

    def system(self, name: str, members: list[Any]) -> None:
        group = self._rooted("IfcDistributionSystem", Name=name)
        self._rooted("IfcRelAssignsToGroup", RelatedObjects=members, RelatingGroup=group)


def _heating() -> tuple[Any, Any, Any, Any]:
    built = _Model()
    pipe = built.add("IfcPipeSegment", (1000.0, 2000.0, 200.0), Name="Pipe:Copper:1")
    start, end = built.port(pipe, (0.0, 0.0, 0.0)), built.port(pipe, (1500.0, 0.0, 0.0))
    radiator = built.add(
        "IfcSpaceHeater", (2500.0, 2100.0, 500.0), Name="Radiator:R:2", PredefinedType="RADIATOR"
    )
    built.connect(end, built.port(radiator, (0.0, -100.0, -300.0)))
    built.add("IfcSpaceHeater", (9000.0, 9000.0, 500.0), Name="Radiator:R:3")  # unconnected
    built.system("Heating flow", [pipe, radiator])
    del start
    return built.file, pipe, radiator, built


def test_sf14_elements_carry_places_ports_neighbours_and_systems_in_metres() -> None:
    file, pipe, radiator, _ = _heating()
    read = service_file(file)
    by_guid = {element.guid: element for element in read.elements}
    assert len(by_guid) == 3 and read.lanes == ("heating",)
    run = by_guid[pipe.GlobalId]
    assert run.lane == "heating" and run.kind == "pipe_segment" and run.is_run  # not "plumbing"
    assert run.at == (1.0, 2.0, 0.2) and run.ports == ((1.0, 2.0, 0.2), (2.5, 2.0, 0.2))
    assert run.neighbours == (radiator.GlobalId,) and run.systems == ("Heating flow",)
    heater = by_guid[radiator.GlobalId]
    assert heater.is_terminal and heater.predefined == "RADIATOR"
    assert heater.ports == ((2.5, 2.0, 0.2),) and heater.neighbours == (pipe.GlobalId,)
    assert read.storeys == (("Ground", 0.0), ("Upper", 3.0))  # lowest first, in metres
    assert read.spaces == {}


def test_sf14_a_model_without_services_has_no_elements_and_gives_its_space_centres() -> None:
    model = IfcFile()
    ground = model.storey("Ground")
    room = model.space(ground, "1.01", "Office", (box(2.0, 1.0, 6.0, 4.0), 0.0, 2.7))
    model.element("IfcWall", storey=ground)
    read = read_service_file(model.ifc())
    assert read.elements == () and read.lanes == ()
    assert read.spaces == {room: pytest.approx((4.0, 2.5))}


def test_sf14_what_is_no_model_or_too_large_is_refused() -> None:
    with pytest.raises(InvalidInputError):
        read_service_file(b"not an ifc file")
    with pytest.raises(InvalidInputError, match="MB"):
        read_service_file(b" " * 150_000_001)


def test_sf14_a_model_is_read_once_per_content() -> None:
    reads: list[bytes] = []
    file, *_ = _heating()

    def read(data: bytes) -> Any:
        reads.append(data)
        return service_file(file)

    files = ServiceFiles(read)
    first = files.file("abc", lambda: b"1")
    assert files.file("abc", lambda: b"never asked for") is first and reads == [b"1"]


def test_s2_a_model_is_read_apart_and_the_plain_data_comes_back() -> None:
    """review-333 S2: the read runs in a child process (ifcopenshell keeps what it parsed until
    its process ends); what comes back is what an in-process read gives."""
    model = IfcFile()
    ground = model.storey("Ground")
    room = model.space(ground, "1.01", "Office", (box(2.0, 1.0, 6.0, 4.0), 0.0, 2.7))
    data = model.ifc()
    read = ServiceFiles().file("abc", lambda: data)
    assert read == read_service_file(data)
    assert type(read) is ifc_services.ServiceFile and read.spaces == {
        room: pytest.approx((4.0, 2.5))
    }
    with pytest.raises(InvalidInputError, match="not an IFC file"):
        ServiceFiles().file("bad", lambda: b"not an ifc file")  # the child's words come back


@pytest.mark.parametrize("scope", [True, False], ids=["systemd-scope", "rlimit"])
def test_s2_a_read_is_held_to_its_memory_and_time_budget(
    scope: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The API's reader (ServiceFiles' default) has a budget: a model that needs more is not
    followed, and the API process is not the one that grows. A capped scope where systemd runs
    one, an address-space limit where it does not (CI)."""
    if scope and not ifc_services.has_systemd_scope():
        pytest.skip("no systemd user manager here")
    monkeypatch.setattr(ifc_services, "has_systemd_scope", lambda: scope)
    data = IfcFile().ifc()
    monkeypatch.setattr(ifc_services, "READ_MEMORY_MB", 1)  # less than Python itself
    with pytest.raises(InvalidInputError, match="needs more than 1 MB"):
        ServiceFiles().file("big", lambda: data)
    with pytest.raises(InvalidInputError, match=r"more than 0\.001 s"):
        read_apart(data, memory_mb=3000, timeout_s=0.001)
