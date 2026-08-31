from math import hypot

from orthovideo.projection.result2d import Polyline2D, Projection2D


def _quantize(value: float, tolerance: float) -> int:
    return round(value / tolerance)


def _canonical_cycle(points: tuple[tuple[int, int], ...]):
    """Return a direction/start-independent key for a closed polyline."""

    if not points:
        return points

    rotations = (
        points[index:] + points[:index]
        for index in range(len(points))
    )
    reversed_points = tuple(reversed(points))
    reversed_rotations = (
        reversed_points[index:] + reversed_points[:index]
        for index in range(len(reversed_points))
    )
    return min(*rotations, *reversed_rotations)


def polyline_key(
    polyline: Polyline2D,
    *,
    tolerance: float = 1e-5,
):
    """Build a stable key for identical HLR edges.

    STEP assemblies can contain coincident edges contributed by adjacent or
    repeated solids.  OCCT correctly classifies them, but drawing the same
    curve several times makes the technical line look incorrectly heavy.
    """

    if tolerance <= 0:
        raise ValueError("La tolleranza deve essere positiva.")

    quantized: list[tuple[int, int]] = []

    for x, y in polyline:
        point = (_quantize(x, tolerance), _quantize(y, tolerance))
        if not quantized or point != quantized[-1]:
            quantized.append(point)

    if len(quantized) < 2:
        return None

    is_closed = hypot(
        polyline[0][0] - polyline[-1][0],
        polyline[0][1] - polyline[-1][1],
    ) <= tolerance

    if is_closed:
        if quantized[0] == quantized[-1]:
            quantized.pop()
        if len(quantized) < 2:
            return None
        return "closed", _canonical_cycle(tuple(quantized))

    points = tuple(quantized)
    return "open", min(points, tuple(reversed(points)))


def _polyline_shape_key(
    polyline: Polyline2D,
    *,
    tolerance: float,
):
    """Sampling-independent signature for coincident CAD curves."""

    if len(polyline) < 2:
        return None
    xs = [point[0] for point in polyline]
    ys = [point[1] for point in polyline]
    length = sum(
        hypot(second[0] - first[0], second[1] - first[1])
        for first, second in zip(polyline, polyline[1:])
    )
    closed = hypot(
        polyline[0][0] - polyline[-1][0],
        polyline[0][1] - polyline[-1][1],
    ) <= tolerance
    bounds = tuple(
        _quantize(value, tolerance)
        for value in (min(xs), min(ys), max(xs), max(ys), length)
    )
    if closed:
        return "closed-shape", bounds

    endpoints = tuple(
        sorted(
            (
                (_quantize(polyline[0][0], tolerance), _quantize(polyline[0][1], tolerance)),
                (_quantize(polyline[-1][0], tolerance), _quantize(polyline[-1][1], tolerance)),
            )
        )
    )
    return "open-shape", endpoints, bounds


def _unique_polylines(
    polylines: list[Polyline2D],
    *,
    excluded: set,
    tolerance: float,
) -> tuple[list[Polyline2D], set]:
    unique: list[Polyline2D] = []
    keys: set = set()

    for polyline in polylines:
        point_key = polyline_key(polyline, tolerance=tolerance)
        shape_key = _polyline_shape_key(polyline, tolerance=tolerance)
        candidate_keys = {
            ("points", point_key),
            ("shape", shape_key),
        }
        if (
            point_key is None
            or shape_key is None
            or candidate_keys & excluded
            or candidate_keys & keys
        ):
            continue
        keys.update(candidate_keys)
        unique.append(polyline)

    return unique, keys


def clean_projection(
    projection: Projection2D,
    *,
    tolerance: float = 1e-5,
) -> Projection2D:
    """Remove coincident curves and prevent hidden-over-visible overdraw."""

    visible, visible_keys = _unique_polylines(
        projection.visible,
        excluded=set(),
        tolerance=tolerance,
    )
    tangent, tangent_keys = _unique_polylines(
        projection.tangent,
        excluded=visible_keys,
        tolerance=tolerance,
    )
    hidden, _ = _unique_polylines(
        projection.hidden,
        excluded=visible_keys | tangent_keys,
        tolerance=tolerance,
    )
    return Projection2D(
        visible=visible,
        hidden=hidden,
        tangent=tangent,
    )
