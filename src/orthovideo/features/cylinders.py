from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, isfinite, pi, sin, sqrt, tau

from OCP.Bnd import Bnd_Box
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBndLib import BRepBndLib
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Shape


Vector3 = tuple[float, float, float]
AngularInterval = tuple[float, float]


@dataclass(frozen=True)
class CylinderFeature:
    """A complete cylindrical feature reconstructed from one or more faces.

    STEP writers commonly split a cylinder into two half-faces or four
    quarter-faces. ``source_face_count`` records how many B-Rep faces were
    consolidated, while ``angular_coverage`` records their combined coverage
    around the infinite axis.

    ``axis_origin`` is the point of the canonical infinite axis nearest the
    global origin. ``v_min`` and ``v_max`` are consequently global signed
    distances along ``axis_direction`` rather than the local V parameters of
    an arbitrary source face.
    """

    radius: float

    axis_origin: Vector3
    axis_direction: Vector3

    start: Vector3
    end: Vector3

    v_min: float
    v_max: float

    angular_coverage: float = tau
    source_face_count: int = 1


@dataclass(frozen=True)
class _CylinderPatch:
    radius: float
    axis_origin: Vector3
    axis_direction: Vector3
    v_min: float
    v_max: float
    angular_intervals: tuple[AngularInterval, ...]


def _dot(a: Vector3, b: Vector3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vector3, b: Vector3) -> Vector3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _subtract(a: Vector3, b: Vector3) -> Vector3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _multiply(v: Vector3, value: float) -> Vector3:
    return (v[0] * value, v[1] * value, v[2] * value)


def _add(a: Vector3, b: Vector3) -> Vector3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _length(v: Vector3) -> float:
    return sqrt(_dot(v, v))


def _normalize(v: Vector3) -> Vector3:
    length = _length(v)
    if length < 1.0e-15:
        raise ValueError("Cylinder axis cannot be null.")
    return _multiply(v, 1.0 / length)


def _canonical_direction(v: Vector3) -> Vector3:
    direction = _normalize(v)
    for component in direction:
        if abs(component) <= 1.0e-10:
            continue
        if component < 0.0:
            return _multiply(direction, -1.0)
        break
    return direction


def _canonical_axis_origin(origin: Vector3, direction: Vector3) -> Vector3:
    """Return the point of the infinite axis nearest the global origin."""

    return _subtract(origin, _multiply(direction, _dot(origin, direction)))


def _point_on_axis(
    origin: Vector3,
    direction: Vector3,
    parameter: float,
) -> Vector3:
    return _add(origin, _multiply(direction, parameter))


def _canonical_radial_basis(direction: Vector3) -> tuple[Vector3, Vector3]:
    reference: Vector3
    if abs(direction[0]) < 0.8:
        reference = (1.0, 0.0, 0.0)
    else:
        reference = (0.0, 1.0, 0.0)

    basis_x = _normalize(_cross(reference, direction))
    basis_y = _normalize(_cross(direction, basis_x))
    return basis_x, basis_y


def _split_circular_interval(
    start: float,
    length: float,
) -> tuple[AngularInterval, ...]:
    if length >= tau - 1.0e-10:
        return ((0.0, tau),)

    start %= tau
    end = start + max(0.0, length)
    if end <= tau:
        return ((start, end),)
    return ((start, tau), (0.0, end - tau))


def _angular_intervals(
    cylinder,
    u_min: float,
    u_max: float,
    canonical_axis: Vector3,
) -> tuple[AngularInterval, ...]:
    """Map a face U range into one stable global angular coordinate system."""

    span = min(tau, abs(u_max - u_min))
    if span >= tau - 1.0e-10:
        return ((0.0, tau),)

    position = cylinder.Position()
    x_direction = position.XDirection()
    y_direction = position.YDirection()
    local_x = (x_direction.X(), x_direction.Y(), x_direction.Z())
    local_y = (y_direction.X(), y_direction.Y(), y_direction.Z())

    radial = _add(
        _multiply(local_x, cos(u_min)),
        _multiply(local_y, sin(u_min)),
    )
    basis_x, basis_y = _canonical_radial_basis(canonical_axis)
    start = atan2(_dot(radial, basis_y), _dot(radial, basis_x))

    # Reversing a cylinder axis reverses the positive U direction. Express
    # every patch as a positive interval around the canonical axis.
    orientation = _dot(_cross(local_x, local_y), canonical_axis)
    if orientation < 0.0:
        start -= span

    return _split_circular_interval(start, span)


def _shape_linear_tolerance(shape: TopoDS_Shape) -> float:
    """Technical clustering tolerance, capped at 0.1 mm for normal-size CAD."""

    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box)
    xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
    diagonal = sqrt(
        (xmax - xmin) ** 2
        + (ymax - ymin) ** 2
        + (zmax - zmin) ** 2
    )
    return max(1.0e-4, min(0.1, diagonal * 1.0e-3))


def _axis_distance(a: _CylinderPatch, b: _CylinderPatch) -> float:
    delta = _subtract(a.axis_origin, b.axis_origin)
    return max(
        _length(_cross(delta, a.axis_direction)),
        _length(_cross(delta, b.axis_direction)),
    )


def _same_cylindrical_region(
    a: _CylinderPatch,
    b: _CylinderPatch,
    *,
    axis_tolerance: float,
    radius_tolerance: float,
    direction_cosine: float,
) -> bool:
    return (
        _dot(a.axis_direction, b.axis_direction) >= direction_cosine
        and _axis_distance(a, b) <= axis_tolerance
        and abs(a.radius - b.radius) <= radius_tolerance
        and abs(a.v_min - b.v_min) <= axis_tolerance
        and abs(a.v_max - b.v_max) <= axis_tolerance
    )


def _combined_angular_coverage(patches: list[_CylinderPatch]) -> float:
    intervals = sorted(
        interval
        for patch in patches
        for interval in patch.angular_intervals
    )
    if not intervals:
        return 0.0

    coverage = 0.0
    current_start, current_end = intervals[0]
    for start, end in intervals[1:]:
        if start <= current_end + 1.0e-10:
            current_end = max(current_end, end)
            continue
        coverage += current_end - current_start
        current_start, current_end = start, end
    coverage += current_end - current_start
    return min(tau, coverage)


def _average_vector(vectors: list[Vector3]) -> Vector3:
    total = (0.0, 0.0, 0.0)
    for vector in vectors:
        total = _add(total, vector)
    return _normalize(total)


def _feature_from_group(
    patches: list[_CylinderPatch],
    angular_coverage: float,
) -> CylinderFeature:
    direction = _canonical_direction(
        _average_vector([patch.axis_direction for patch in patches])
    )
    origin_mean = tuple(
        sum(patch.axis_origin[index] for patch in patches) / len(patches)
        for index in range(3)
    )
    origin = _canonical_axis_origin(origin_mean, direction)
    radius = sum(patch.radius for patch in patches) / len(patches)
    v_min = min(patch.v_min for patch in patches)
    v_max = max(patch.v_max for patch in patches)

    return CylinderFeature(
        radius=radius,
        axis_origin=origin,
        axis_direction=direction,
        start=_point_on_axis(origin, direction, v_min),
        end=_point_on_axis(origin, direction, v_max),
        v_min=v_min,
        v_max=v_max,
        angular_coverage=angular_coverage,
        source_face_count=len(patches),
    )


def _extract_cylinder_patches(shape: TopoDS_Shape) -> list[_CylinderPatch]:
    patches: list[_CylinderPatch] = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)

    while explorer.More():
        face = TopoDS.Face_s(explorer.Current())
        adaptor = BRepAdaptor_Surface(face)

        if adaptor.GetType() == GeomAbs_Cylinder:
            cylinder = adaptor.Cylinder()
            axis = cylinder.Axis()
            location = axis.Location()
            source_direction = axis.Direction()
            source_origin = (location.X(), location.Y(), location.Z())
            source_axis = (
                source_direction.X(),
                source_direction.Y(),
                source_direction.Z(),
            )
            direction = _canonical_direction(source_axis)
            origin = _canonical_axis_origin(source_origin, direction)

            v1 = float(adaptor.FirstVParameter())
            v2 = float(adaptor.LastVParameter())
            u1 = float(adaptor.FirstUParameter())
            u2 = float(adaptor.LastUParameter())

            if all(isfinite(value) for value in (v1, v2, u1, u2)):
                source_start = _point_on_axis(source_origin, source_axis, v1)
                source_end = _point_on_axis(source_origin, source_axis, v2)
                global_v = sorted(
                    (_dot(source_start, direction), _dot(source_end, direction))
                )
                patches.append(
                    _CylinderPatch(
                        radius=float(cylinder.Radius()),
                        axis_origin=origin,
                        axis_direction=direction,
                        v_min=global_v[0],
                        v_max=global_v[1],
                        angular_intervals=_angular_intervals(
                            cylinder,
                            u1,
                            u2,
                            direction,
                        ),
                    )
                )

        explorer.Next()

    return patches


def extract_cylinders(
    shape: TopoDS_Shape,
    *,
    linear_tolerance: float | None = None,
    include_partial: bool = False,
) -> list[CylinderFeature]:
    """Extract complete cylinders, consolidating split co-cylindrical faces.

    Faces are grouped by canonical infinite axis, radius and axial interval.
    A group is promoted to a centerline feature only when its union covers the
    complete circumference. This excludes ordinary cylindrical fillets and
    prevents STEP face splitting from producing hundreds of duplicate axes.

    ``include_partial`` is intended for diagnostics; the production default is
    deliberately conservative.
    """

    if shape.IsNull():
        return []

    patches = _extract_cylinder_patches(shape)
    if not patches:
        return []

    axis_tolerance = (
        _shape_linear_tolerance(shape)
        if linear_tolerance is None
        else max(float(linear_tolerance), 1.0e-8)
    )
    radius_tolerance = max(1.0e-6, axis_tolerance * 0.01)
    direction_cosine = cos(1.0e-4)

    groups: list[list[_CylinderPatch]] = []
    for patch in patches:
        matching_group = next(
            (
                group
                for group in groups
                if _same_cylindrical_region(
                    patch,
                    group[0],
                    axis_tolerance=axis_tolerance,
                    radius_tolerance=radius_tolerance,
                    direction_cosine=direction_cosine,
                )
            ),
            None,
        )
        if matching_group is None:
            groups.append([patch])
        else:
            matching_group.append(patch)

    minimum_coverage = tau - pi / 180.0
    features = []
    for group in groups:
        coverage = _combined_angular_coverage(group)
        if include_partial or coverage >= minimum_coverage:
            features.append(_feature_from_group(group, coverage))

    features.sort(
        key=lambda feature: (
            tuple(round(value, 8) for value in feature.axis_direction),
            tuple(round(value, 6) for value in feature.axis_origin),
            round(feature.radius, 6),
            round(feature.v_min, 6),
            round(feature.v_max, 6),
        )
    )
    return features
