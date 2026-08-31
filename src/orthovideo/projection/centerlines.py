from dataclasses import dataclass
from math import atan2, cos, pi, sqrt
from typing import TYPE_CHECKING

from orthovideo.features.cylinders import CylinderFeature
from orthovideo.projection.view_system import (
    ViewDefinition,
    cross,
    dot,
    normalize,
)

if TYPE_CHECKING:
    from orthovideo.projection.result2d import Projection2D


Point2D = tuple[float, float]
Vector3 = tuple[float, float, float]


@dataclass(frozen=True)
class CenterLine2D:
    start: Point2D
    end: Point2D


@dataclass(frozen=True)
class HolePattern2D:
    """Four equally-spaced hole centres around one principal centre."""

    center: Point2D
    radius: float
    holes: tuple[Point2D, ...]


@dataclass(frozen=True)
class _CylinderAxis:
    radius: float
    radii: tuple[float, ...]
    origin: Vector3
    direction: Vector3
    start: Vector3
    end: Vector3


def _subtract_2d(
    a: Point2D,
    b: Point2D,
) -> Point2D:

    return (
        a[0] - b[0],
        a[1] - b[1],
    )


def _length_2d(
    v: Point2D,
) -> float:

    return sqrt(
        v[0] * v[0]
        + v[1] * v[1]
    )


def _project_point(
    point: Vector3,
    view: ViewDefinition,
) -> Point2D:
    """
    Proietta un punto 3D nel sistema 2D della vista.

    Questa base coincide con quella utilizzata
    dal nostro HLRAlgo_Projector:
        X vista = cross(up, normal)
        Y vista = up
    """

    n = normalize(
        view.normal
    )

    up = normalize(
        view.up
    )

    screen_x = normalize(
        cross(
            up,
            n,
        )
    )

    return (
        dot(point, screen_x),
        dot(point, up),
    )


def _midpoint_3d(
    a: Vector3,
    b: Vector3,
) -> Vector3:

    return (
        (a[0] + b[0]) / 2.0,
        (a[1] + b[1]) / 2.0,
        (a[2] + b[2]) / 2.0,
    )


def _merge_collinear_lines(
    lines: list[CenterLine2D],
    *,
    tolerance: float,
) -> list[CenterLine2D]:
    """Merge coincident/overlapping projected axes using CAD tolerance."""

    groups = []

    for line in lines:
        delta = _subtract_2d(line.end, line.start)
        length = _length_2d(delta)
        if length < 1.0e-10:
            continue

        direction = (delta[0] / length, delta[1] / length)
        if (
            direction[0] < -1.0e-10
            or (
                abs(direction[0]) <= 1.0e-10
                and direction[1] < 0.0
            )
        ):
            direction = (-direction[0], -direction[1])

        normal = (-direction[1], direction[0])
        offset = (
            line.start[0] * normal[0]
            + line.start[1] * normal[1]
        )
        interval = sorted(
            (
                line.start[0] * direction[0]
                + line.start[1] * direction[1],
                line.end[0] * direction[0]
                + line.end[1] * direction[1],
            )
        )

        matching_group = None
        for group in groups:
            if (
                direction[0] * group["direction"][0]
                + direction[1] * group["direction"][1]
                >= 1.0 - 1.0e-8
                and abs(offset - group["offset"]) <= tolerance
            ):
                matching_group = group
                break

        if matching_group is None:
            groups.append(
                {
                    "direction": direction,
                    "normal": normal,
                    "offset": offset,
                    "intervals": [interval],
                }
            )
        else:
            matching_group["intervals"].append(interval)

    result = []
    for group in groups:
        intervals = sorted(group["intervals"])
        merged = []
        for start, end in intervals:
            if merged and start <= merged[-1][1] + tolerance:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])

        direction = group["direction"]
        normal = group["normal"]
        offset = group["offset"]
        for start, end in merged:
            result.append(
                CenterLine2D(
                    start=(
                        direction[0] * start + normal[0] * offset,
                        direction[1] * start + normal[1] * offset,
                    ),
                    end=(
                        direction[0] * end + normal[0] * offset,
                        direction[1] * end + normal[1] * offset,
                    ),
                )
            )

    return result


def _deduplicate_lines(
    lines: list[CenterLine2D],
    *,
    tolerance: float,
) -> list[CenterLine2D]:
    """Remove exact/reversed duplicates without merging distinct center marks."""

    result: list[CenterLine2D] = []
    keys = set()
    scale = 1.0 / max(tolerance, 1.0e-9)

    for line in lines:
        a = (round(line.start[0] * scale), round(line.start[1] * scale))
        b = (round(line.end[0] * scale), round(line.end[1] * scale))
        key = tuple(sorted((a, b)))
        if key in keys:
            continue
        keys.add(key)
        result.append(line)

    return result


def _consolidate_center_marks(
    lines: list[CenterLine2D],
    *,
    tolerance: float,
) -> list[CenterLine2D]:
    """Collapse near-coaxial STEP counterbores into one clean centre mark."""

    marks: list[tuple[Point2D, float]] = []
    for index in range(0, len(lines) - 1, 2):
        first = lines[index]
        second = lines[index + 1]
        first_center = (
            (first.start[0] + first.end[0]) / 2.0,
            (first.start[1] + first.end[1]) / 2.0,
        )
        second_center = (
            (second.start[0] + second.end[0]) / 2.0,
            (second.start[1] + second.end[1]) / 2.0,
        )
        if _length_2d(_subtract_2d(first_center, second_center)) > tolerance:
            continue
        center = (
            (first_center[0] + second_center[0]) / 2.0,
            (first_center[1] + second_center[1]) / 2.0,
        )
        half_length = max(
            _length_2d(_subtract_2d(first.end, first.start)),
            _length_2d(_subtract_2d(second.end, second.start)),
        ) / 2.0
        marks.append((center, half_length))

    groups: list[list[tuple[Point2D, float]]] = []
    for mark in marks:
        group = next(
            (
                candidate
                for candidate in groups
                if _length_2d(_subtract_2d(candidate[0][0], mark[0]))
                <= tolerance
            ),
            None,
        )
        if group is None:
            groups.append([mark])
        else:
            group.append(mark)

    result: list[CenterLine2D] = []
    for group in groups:
        # A heavily stepped coaxial group is the principal bore: its technical
        # centre mark belongs to the smallest functional opening, not every
        # surrounding shoulder. Ordinary counterbores retain the largest mark.
        selector = min if len(group) >= 3 else max
        center, half_length = selector(group, key=lambda item: item[1])
        cx, cy = center
        result.extend(
            [
                CenterLine2D((cx - half_length, cy), (cx + half_length, cy)),
                CenterLine2D((cx, cy - half_length), (cx, cy + half_length)),
            ]
        )

    return result


def _visible_circle_radius(
    center: Point2D,
    radii: tuple[float, ...],
    projection: "Projection2D",
    *,
    tolerance: float,
    preferred_max_radius: float | None = None,
    prefer_smallest: bool = False,
) -> float | None:
    """Find the largest full visible circular edge on one consolidated axis.

    OCCT commonly returns a circle as two or more open HLR arcs.  We therefore
    combine angular samples from all visible arcs instead of requiring one
    closed polyline.  Cylinders that belong only to the opposite face do not
    reach the required angular coverage and receive no center mark.
    """

    visible_radii: list[float] = []

    for radius in sorted(radii, reverse=True):
        radial_tolerance = max(tolerance * 2.0, 0.15, radius * 0.025)
        angles: list[float] = []

        for line in projection.visible:
            if len(line) < 2:
                continue

            matching = [
                point
                for point in line
                if abs(
                    sqrt(
                        (point[0] - center[0]) ** 2
                        + (point[1] - center[1]) ** 2
                    )
                    - radius
                )
                <= radial_tolerance
            ]

            # Reject incidental crossings from unrelated edges.
            if len(matching) < 2 or len(matching) / len(line) < 0.65:
                continue

            angles.extend(
                atan2(point[1] - center[1], point[0] - center[0]) % (2.0 * pi)
                for point in matching
            )

        if len(angles) < 8:
            continue

        angles.sort()
        gaps = [
            second - first
            for first, second in zip(angles, angles[1:])
        ]
        gaps.append(angles[0] + 2.0 * pi - angles[-1])
        angular_coverage = 2.0 * pi - max(gaps)

        # A counterbore can legitimately hide part of the circular edge while
        # still defining an unambiguous hole center.  Slightly more than a
        # semicircle is sufficient; rear-face cylinders normally contribute no
        # visible radial arc at all.
        if angular_coverage >= 1.05 * pi:
            visible_radii.append(radius)

    if preferred_max_radius is not None:
        for radius in visible_radii:
            if radius <= preferred_max_radius:
                return radius

    if not visible_radii:
        return None
    return visible_radii[-1] if prefer_smallest else visible_radii[0]


def _projection_bounds(projection: "Projection2D"):
    points = [
        point
        for line in projection.visible + projection.hidden + projection.tangent
        for point in line
    ]
    if not points:
        return None
    return (
        min(point[0] for point in points),
        min(point[1] for point in points),
        max(point[0] for point in points),
        max(point[1] for point in points),
    )


def _axis_intersects_section_plane(
    cylinder: _CylinderAxis,
    plane_normal: Vector3,
    plane_point: Vector3,
    *,
    tolerance: float,
) -> bool:
    normal = normalize(plane_normal)
    plane_distance = dot(plane_point, normal)
    start_distance = dot(cylinder.start, normal) - plane_distance
    end_distance = dot(cylinder.end, normal) - plane_distance
    if start_distance * end_distance <= 0.0:
        return True
    return min(abs(start_distance), abs(end_distance)) <= cylinder.radius + tolerance


def build_centerlines_for_view(
    cylinders: list[CylinderFeature],
    view: ViewDefinition,
    *,
    extension: float,
    parallel_threshold: float = 0.9999,
    visible_projection: "Projection2D | None" = None,
    section_plane_normal: Vector3 | None = None,
    section_plane_point: Vector3 | None = None,
    include_longitudinal: bool = True,
    front_feature_only: bool = False,
    principal_radius_mode: str = "largest_internal",
) -> list[CenterLine2D]:
    """
    Genera gli assi CENTER relativi alle superfici
    cilindriche per una determinata vista.

    extension:
        Estensione oltre la geometria espressa
        nelle unità del modello.

    Se l'asse del cilindro è parallelo alla
    direzione di osservazione, il cilindro appare
    frontalmente e viene generata una croce CENTER.

    Negli altri casi viene proiettato l'asse
    longitudinale del cilindro.
    """

    if principal_radius_mode not in {"largest_internal", "smallest"}:
        raise ValueError("principal_radius_mode non valido.")

    center_marks: list[CenterLine2D] = []
    longitudinal_lines: list[CenterLine2D] = []

    if not cylinders:
        return []

    tolerance = _technical_tolerance(cylinders)
    axes = _consolidate_infinite_axes(
        cylinders,
        tolerance=tolerance,
    )

    n = normalize(
        view.normal
    )

    axial_front_depths = [
        max(dot(cylinder.start, n), dot(cylinder.end, n))
        for cylinder in axes
        if abs(dot(normalize(cylinder.direction), n)) >= parallel_threshold
    ]
    frontmost_depth = max(axial_front_depths) if axial_front_depths else None
    depth_span = (
        max(axial_front_depths) - min(axial_front_depths)
        if axial_front_depths
        else 0.0
    )
    front_depth_band = max(3.0, min(12.0, depth_span * 0.10))

    projection_bounds = (
        _projection_bounds(visible_projection)
        if visible_projection is not None
        else None
    )

    for cylinder in axes:

        if (section_plane_normal is None) != (section_plane_point is None):
            raise ValueError(
                "section_plane_normal e section_plane_point vanno forniti insieme."
            )

        if (
            section_plane_normal is not None
            and section_plane_point is not None
            and not _axis_intersects_section_plane(
                cylinder,
                section_plane_normal,
                section_plane_point,
                tolerance=tolerance,
            )
        ):
            continue

        axis = normalize(
            cylinder.direction
        )

        alignment = abs(
            dot(
                axis,
                n,
            )
        )

        # -----------------------------------------
        # CILINDRO VISTO LUNGO IL PROPRIO ASSE
        # -----------------------------------------

        if alignment >= parallel_threshold:

            if front_feature_only and frontmost_depth is not None:
                cylinder_front_depth = max(
                    dot(cylinder.start, n),
                    dot(cylinder.end, n),
                )
                if frontmost_depth - cylinder_front_depth > front_depth_band:
                    continue

            center_3d = _midpoint_3d(
                cylinder.start,
                cylinder.end,
            )

            cx, cy = _project_point(
                center_3d,
                view,
            )

            visible_radius = cylinder.radius

            if visible_projection is not None:
                preferred_max_radius = None
                prefer_smallest = False
                if projection_bounds is not None:
                    xmin, ymin, xmax, ymax = projection_bounds
                    width = xmax - xmin
                    height = ymax - ymin
                    view_center = ((xmin + xmax) / 2.0, (ymin + ymax) / 2.0)
                    view_diagonal = sqrt(width * width + height * height)
                    if (
                        view_diagonal > 1.0e-9
                        and _length_2d(_subtract_2d((cx, cy), view_center))
                        <= view_diagonal * 0.06
                    ):
                        if principal_radius_mode == "smallest":
                            prefer_smallest = True
                        else:
                            # The outer silhouette is not a centre-mark feature.
                            preferred_max_radius = min(width, height) * 0.38

                visible_radius = _visible_circle_radius(
                    (cx, cy),
                    cylinder.radii,
                    visible_projection,
                    tolerance=tolerance,
                    preferred_max_radius=preferred_max_radius,
                    prefer_smallest=prefer_smallest,
                )
                if visible_radius is None:
                    continue

            # Small holes need a compact center mark, while the main concentric
            # feature may retain the full configured extension.
            mark_extension = min(
                extension * 0.35,
                max(0.8, visible_radius * 0.12),
            )
            half_length = visible_radius + mark_extension

            # Asse CENTER orizzontale
            center_marks.append(
                CenterLine2D(
                    start=(
                        cx - half_length,
                        cy,
                    ),
                    end=(
                        cx + half_length,
                        cy,
                    ),
                )
            )

            # Asse CENTER verticale
            center_marks.append(
                CenterLine2D(
                    start=(
                        cx,
                        cy - half_length,
                    ),
                    end=(
                        cx,
                        cy + half_length,
                    ),
                )
            )

            continue

        # -----------------------------------------
        # CILINDRO VISTO LATERALMENTE / OBLIQUAMENTE
        # -----------------------------------------

        if not include_longitudinal:
            continue

        p1 = _project_point(
            cylinder.start,
            view,
        )

        p2 = _project_point(
            cylinder.end,
            view,
        )

        delta = _subtract_2d(
            p2,
            p1,
        )

        length = _length_2d(
            delta
        )

        # Se la proiezione dell'asse collassa,
        # non abbiamo una linea longitudinale utile.
        if length < 1e-8:
            continue

        dx = delta[0] / length
        dy = delta[1] / length

        start = (
            p1[0] - dx * extension,
            p1[1] - dy * extension,
        )

        end = (
            p2[0] + dx * extension,
            p2[1] + dy * extension,
        )

        longitudinal_lines.append(
            CenterLine2D(
                start=start,
                end=end,
            )
        )

    if visible_projection is None:
        # Preserve the legacy API for diagnostic callers that do not provide
        # HLR visibility information.
        return _merge_collinear_lines(
            center_marks + longitudinal_lines,
            tolerance=tolerance,
        )

    center_marks = _consolidate_center_marks(
        center_marks,
        tolerance=max(tolerance * 6.0, 0.6),
    )
    merged_longitudinal = _merge_collinear_lines(
        longitudinal_lines,
        tolerance=tolerance,
    )
    if visible_projection is not None:
        # Longitudinal hole axes may extend beyond their local cylinder, but
        # never beyond the overall visible envelope of the component. This
        # removes construction tails below bases and outside side flanges.
        merged_longitudinal = clip_centerlines_to_projection(
            merged_longitudinal,
            visible_projection,
        )

    return _deduplicate_lines(
        center_marks,
        tolerance=tolerance,
    ) + merged_longitudinal


def clip_centerlines_to_projection(
    lines: list[CenterLine2D],
    projection: "Projection2D",
    *,
    margin: float = 0.0,
) -> list[CenterLine2D]:
    """Clip construction axes to the actual section/view envelope."""

    bounds = _projection_bounds(projection)
    if bounds is None:
        return []
    xmin, ymin, xmax, ymax = bounds
    xmin -= margin
    ymin -= margin
    xmax += margin
    ymax += margin

    result: list[CenterLine2D] = []
    for line in lines:
        x0, y0 = line.start
        dx = line.end[0] - x0
        dy = line.end[1] - y0
        t0 = 0.0
        t1 = 1.0
        accepted = True

        for p, q in (
            (-dx, x0 - xmin),
            (dx, xmax - x0),
            (-dy, y0 - ymin),
            (dy, ymax - y0),
        ):
            if abs(p) <= 1.0e-12:
                if q < 0.0:
                    accepted = False
                    break
                continue
            ratio = q / p
            if p < 0.0:
                t0 = max(t0, ratio)
            else:
                t1 = min(t1, ratio)
            if t0 > t1:
                accepted = False
                break

        if not accepted:
            continue
        start = (x0 + dx * t0, y0 + dy * t0)
        end = (x0 + dx * t1, y0 + dy * t1)
        if _length_2d(_subtract_2d(end, start)) > 1.0e-8:
            result.append(CenterLine2D(start=start, end=end))

    return result


def detect_four_hole_pattern(
    lines: list[CenterLine2D],
) -> HolePattern2D | None:
    """Recognise a symmetric four-hole bolt circle from compact centre marks."""

    if len(lines) < 10:
        return None

    coordinates = [value for line in lines for point in (line.start, line.end) for value in point]
    span = max(coordinates) - min(coordinates) if coordinates else 1.0
    tolerance = max(1.0e-5, span * 1.0e-6)
    midpoint_groups: list[dict] = []

    for line in lines:
        delta = _subtract_2d(line.end, line.start)
        length = _length_2d(delta)
        if length <= tolerance:
            continue
        midpoint = (
            (line.start[0] + line.end[0]) / 2.0,
            (line.start[1] + line.end[1]) / 2.0,
        )
        direction = (delta[0] / length, delta[1] / length)
        group = next(
            (
                item
                for item in midpoint_groups
                if _length_2d(_subtract_2d(item["center"], midpoint)) <= tolerance
            ),
            None,
        )
        if group is None:
            group = {"center": midpoint, "members": []}
            midpoint_groups.append(group)
        group["members"].append((direction, length))

    marks: list[tuple[Point2D, float]] = []
    for group in midpoint_groups:
        members = group["members"]
        perpendicular = any(
            abs(a[0][0] * b[0][0] + a[0][1] * b[0][1]) <= 0.1
            for index, a in enumerate(members)
            for b in members[index + 1 :]
        )
        if perpendicular:
            marks.append(
                (group["center"], max(member[1] for member in members) / 2.0)
            )

    if len(marks) < 5:
        return None

    main_center, _ = max(marks, key=lambda item: item[1])
    radial_marks = [
        (center, half_length, _length_2d(_subtract_2d(center, main_center)))
        for center, half_length in marks
        if _length_2d(_subtract_2d(center, main_center)) > tolerance
    ]
    candidates: list[tuple[float, list[tuple[Point2D, float, float]]]] = []

    for _, _, seed_radius in radial_marks:
        radial_tolerance = max(0.2, seed_radius * 0.02)
        group = [
            item for item in radial_marks
            if abs(item[2] - seed_radius) <= radial_tolerance
        ]
        if len(group) == 4:
            radius = sum(item[2] for item in group) / 4.0
            candidates.append((radius, group))

    # If two opposite-face patterns project close together, the front-face
    # counterbores have the larger visible centre-mark extent. Prefer that
    # ring instead of blindly choosing the numerically smaller pitch radius.
    for radius, group in sorted(
        candidates,
        key=lambda item: sum(mark[1] for mark in item[1]) / len(item[1]),
        reverse=True,
    ):
        if radius <= tolerance:
            continue
        vectors = [_subtract_2d(item[0], main_center) for item in group]
        residual = _length_2d(
            (sum(vector[0] for vector in vectors), sum(vector[1] for vector in vectors))
        )
        angles = sorted(atan2(vector[1], vector[0]) % (2.0 * pi) for vector in vectors)
        gaps = [
            angles[(index + 1) % 4] - angles[index]
            if index < 3
            else angles[0] + 2.0 * pi - angles[3]
            for index in range(4)
        ]
        if residual > radius * 0.08:
            continue
        if any(abs(gap - pi / 2.0) > 0.12 for gap in gaps):
            continue
        holes = tuple(item[0] for item in sorted(group, key=lambda item: atan2(
            item[0][1] - main_center[1], item[0][0] - main_center[0]
        )))
        return HolePattern2D(center=main_center, radius=radius, holes=holes)

    return None


def _add_3d(
    a: Vector3,
    b: Vector3,
) -> Vector3:
    return (
        a[0] + b[0],
        a[1] + b[1],
        a[2] + b[2],
    )


def _subtract_3d(
    a: Vector3,
    b: Vector3,
) -> Vector3:
    return (
        a[0] - b[0],
        a[1] - b[1],
        a[2] - b[2],
    )


def _multiply_3d(
    v: Vector3,
    value: float,
) -> Vector3:
    return (
        v[0] * value,
        v[1] * value,
        v[2] * value,
    )


def _length_3d(v: Vector3) -> float:
    return sqrt(dot(v, v))


def _canonical_direction(v: Vector3) -> Vector3:
    direction = normalize(v)
    for component in direction:
        if abs(component) <= 1.0e-10:
            continue
        if component < 0.0:
            return _multiply_3d(direction, -1.0)
        break
    return direction


def _axis_origin_nearest_global_origin(
    point: Vector3,
    direction: Vector3,
) -> Vector3:
    return _subtract_3d(
        point,
        _multiply_3d(direction, dot(point, direction)),
    )


def _axis_distance(
    a_origin: Vector3,
    a_direction: Vector3,
    b_origin: Vector3,
    b_direction: Vector3,
) -> float:
    delta = _subtract_3d(a_origin, b_origin)
    return max(
        _length_3d(cross(delta, a_direction)),
        _length_3d(cross(delta, b_direction)),
    )


def _technical_tolerance(
    cylinders: list[CylinderFeature],
) -> float:
    points = [
        point
        for cylinder in cylinders
        for point in (cylinder.start, cylinder.end)
    ]
    if not points:
        return 1.0e-4

    extents = [
        max(point[index] for point in points)
        - min(point[index] for point in points)
        for index in range(3)
    ]
    diagonal = sqrt(sum(extent * extent for extent in extents))
    return max(1.0e-4, min(0.1, diagonal * 1.0e-3))


def _consolidate_infinite_axes(
    cylinders: list[CylinderFeature],
    *,
    tolerance: float,
) -> list[_CylinderAxis]:
    """Collapse concentric stepped cylinders into one technical axis."""

    groups: list[list[CylinderFeature]] = []
    direction_cosine = cos(1.0e-4)

    def canonical_geometry(cylinder: CylinderFeature):
        direction = _canonical_direction(cylinder.axis_direction)
        origin = _axis_origin_nearest_global_origin(
            cylinder.axis_origin,
            direction,
        )
        return origin, direction

    for cylinder in cylinders:
        origin, direction = canonical_geometry(cylinder)
        matching_group = None

        for group in groups:
            candidate_origin, candidate_direction = canonical_geometry(group[0])
            if (
                dot(direction, candidate_direction) >= direction_cosine
                and _axis_distance(
                    origin,
                    direction,
                    candidate_origin,
                    candidate_direction,
                )
                <= tolerance
            ):
                matching_group = group
                break

        if matching_group is None:
            groups.append([cylinder])
        else:
            matching_group.append(cylinder)

    axes = []
    for group in groups:
        directions = [canonical_geometry(cylinder)[1] for cylinder in group]
        direction = _canonical_direction(
            tuple(
                sum(vector[index] for vector in directions)
                for index in range(3)
            )
        )
        origins = [canonical_geometry(cylinder)[0] for cylinder in group]
        mean_origin = tuple(
            sum(origin[index] for origin in origins) / len(origins)
            for index in range(3)
        )
        origin = _axis_origin_nearest_global_origin(mean_origin, direction)

        parameters = [
            dot(point, direction)
            for cylinder in group
            for point in (cylinder.start, cylinder.end)
        ]
        v_min = min(parameters)
        v_max = max(parameters)
        axes.append(
            _CylinderAxis(
                radius=max(cylinder.radius for cylinder in group),
                radii=tuple(
                    sorted(
                        {round(cylinder.radius, 8) for cylinder in group},
                        reverse=True,
                    )
                ),
                origin=origin,
                direction=direction,
                start=_add_3d(origin, _multiply_3d(direction, v_min)),
                end=_add_3d(origin, _multiply_3d(direction, v_max)),
            )
        )

    return axes
