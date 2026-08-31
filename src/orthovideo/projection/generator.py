from dataclasses import dataclass
from math import atan2, hypot, pi
from typing import Any

from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box

from orthovideo.features.cylinders import extract_cylinders
from orthovideo.io.obj_loader import load_obj
from orthovideo.io.step_loader import load_step
from orthovideo.project_config import ProjectConfig
from orthovideo.projection.centerlines import (
    CenterLine2D,
    build_centerlines_for_view,
    clip_centerlines_to_projection,
    detect_four_hole_pattern,
)
from orthovideo.projection.hlr import project_shape
from orthovideo.projection.mesh_adapter import mesh_visibility_to_projection2d
from orthovideo.projection.mesh_projection import project_mesh_edges
from orthovideo.projection.mesh_visibility import resolve_mesh_visibility
from orthovideo.projection.annotations import (
    TechnicalAnnotation2D,
    TechnicalLabel2D,
    circle_annotation,
)
from orthovideo.projection.cleanup import clean_projection
from orthovideo.projection.result2d import Projection2D
from orthovideo.projection.section import (
    build_mesh_section_mesh,
    build_mesh_section_annotations,
    build_section_reference,
    build_step_section_shape,
    build_step_section_annotations,
)
from orthovideo.projection.step_adapter import hlr_to_projection2d
from orthovideo.projection.view_system import ViewDefinition, build_six_views


@dataclass
class ProjectionBundle:
    source_type: str
    views: dict[str, ViewDefinition]
    projections: dict[str, Projection2D]
    centerlines: dict[str, list[CenterLine2D]]
    annotations: dict[str, list[TechnicalAnnotation2D]]
    source_geometry: Any
    section_name: str | None
    section_projection: Projection2D | None
    section_centerlines: list[CenterLine2D]
    section_annotations: list[TechnicalAnnotation2D]
    section_reference_annotations: dict[str, list[TechnicalAnnotation2D]]
    section_reference_labels: dict[str, list[TechnicalLabel2D]]


def _polyline_length(points) -> float:
    return sum(
        hypot(second[0] - first[0], second[1] - first[1])
        for first, second in zip(points, points[1:])
    )


def _is_nearly_straight(points, *, tolerance: float) -> bool:
    if len(points) <= 2:
        return True
    start = points[0]
    end = points[-1]
    chord_x = end[0] - start[0]
    chord_y = end[1] - start[1]
    chord = hypot(chord_x, chord_y)
    if chord <= tolerance:
        return False
    return max(
        abs(
            (point[0] - start[0]) * chord_y
            - (point[1] - start[1]) * chord_x
        ) / chord
        for point in points[1:-1]
    ) <= tolerance


def _consolidate_axis_hidden(lines, visible, *, diagonal: float):
    """Merge duplicate HLR generators and discard visible/isolated fragments."""

    coordinate_tolerance = max(0.15, diagonal * 0.001)
    merge_gap = max(0.25, diagonal * 0.0015)

    def descriptor(points):
        start, end = points[0], points[-1]
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = hypot(dx, dy)
        if length <= 1.0e-9:
            return None
        if abs(dy) / length <= 0.035:
            return ("H", (start[1] + end[1]) / 2.0, min(start[0], end[0]), max(start[0], end[0]))
        if abs(dx) / length <= 0.035:
            return ("V", (start[0] + end[0]) / 2.0, min(start[1], end[1]), max(start[1], end[1]))
        return None

    descriptors = [item for line in lines if (item := descriptor(line)) is not None]
    groups: list[list[tuple[str, float, float, float]]] = []
    for item in sorted(descriptors, key=lambda value: (value[0], value[1])):
        group = next(
            (
                candidate
                for candidate in groups
                if candidate[0][0] == item[0]
                and abs(candidate[0][1] - item[1]) <= coordinate_tolerance
            ),
            None,
        )
        if group is None:
            groups.append([item])
        else:
            group.append(item)

    merged: list[tuple[str, float, float, float]] = []
    for group in groups:
        orientation = group[0][0]
        coordinate = sum(item[1] for item in group) / len(group)
        intervals = sorted((item[2], item[3]) for item in group)
        low, high = intervals[0]
        for next_low, next_high in intervals[1:]:
            if next_low <= high + merge_gap:
                high = max(high, next_high)
            else:
                merged.append((orientation, coordinate, low, high))
                low, high = next_low, next_high
        merged.append((orientation, coordinate, low, high))

    visible_descriptors = [
        item
        for line in visible
        if len(line) >= 2
        and _is_nearly_straight(line, tolerance=coordinate_tolerance)
        and (item := descriptor(line)) is not None
    ]

    def hidden_behind_visible(item) -> bool:
        orientation, coordinate, low, high = item
        length = high - low
        return any(
            other_orientation == orientation
            and abs(other_coordinate - coordinate) <= coordinate_tolerance
            and max(0.0, min(high, other_high) - max(low, other_low))
            >= length * 0.72
            for other_orientation, other_coordinate, other_low, other_high
            in visible_descriptors
        )

    merged = [item for item in merged if not hidden_behind_visible(item)]

    def coherent(item) -> bool:
        orientation, coordinate, low, high = item
        length = high - low
        if length >= diagonal * 0.08:
            return True
        return any(
            other is not item
            and other[0] == orientation
            and coordinate_tolerance < abs(other[1] - coordinate) <= diagonal * 0.16
            and max(0.0, min(high, other[3]) - max(low, other[2]))
            >= min(length, other[3] - other[2]) * 0.45
            for other in merged
        )

    result = []
    for orientation, coordinate, low, high in filter(coherent, merged):
        result.append(
            [(low, coordinate), (high, coordinate)]
            if orientation == "H"
            else [(coordinate, low), (coordinate, high)]
        )
    return result


def _hidden_lines_for_view(
    config: ProjectConfig,
    view_name: str,
    hidden,
    visible,
):
    if config.projection.show_hidden:
        return hidden
    if view_name not in config.projection.hidden_views:
        return []
    if config.projection.hidden_line_mode == "all":
        return hidden

    visible_points = [point for line in visible for point in line]
    if not visible_points:
        return []
    width = max(point[0] for point in visible_points) - min(
        point[0] for point in visible_points
    )
    height = max(point[1] for point in visible_points) - min(
        point[1] for point in visible_points
    )
    diagonal = hypot(width, height)
    minimum_length = max(2.0, diagonal * 0.02)
    straight_tolerance = max(0.08, diagonal * 0.0008)

    # When a section already explains the interior, lateral views retain only
    # useful straight hidden generators/steps. Closed circles and curved rear
    # details create the illegible "radiograph" rejected by ISO practice.
    result = []
    for line in hidden:
        if (
            len(line) < 2
            or _polyline_length(line) < minimum_length
            or not _is_nearly_straight(line, tolerance=straight_tolerance)
        ):
            continue
        dx = line[-1][0] - line[0][0]
        dy = line[-1][1] - line[0][1]
        chord = hypot(dx, dy)
        # Functional hidden generators in orthographic lateral views are
        # horizontal/vertical. Small rear-face arc fragments are HLR noise.
        if chord <= 1.0e-9 or min(abs(dx), abs(dy)) / chord > 0.035:
            continue
        result.append(line)
    return _consolidate_axis_hidden(result, visible, diagonal=diagonal)


def _section_reference_parent(config: ProjectConfig, section_name: str) -> str:
    if config.projection.section_reference_view:
        return config.projection.section_reference_view

    # A longitudinal FRONT/REAR section is clearest on the square-flange side
    # view. TOP/BOTTOM and lateral sections retain the conventional FRONT callout.
    return {
        "front": "left",
        "rear": "right",
        "top": "front",
        "bottom": "front",
        "right": "front",
        "left": "front",
    }[section_name]


def _add_pitch_circle_annotations(
    annotations: dict[str, list[TechnicalAnnotation2D]],
    centerlines: dict[str, list[CenterLine2D]],
    view_names: tuple[str, ...],
) -> None:
    for view_name in view_names:
        pattern = detect_four_hole_pattern(centerlines.get(view_name, []))
        if pattern is None:
            continue
        annotations[view_name].append(
            circle_annotation(
                role="PITCH",
                center=pattern.center,
                radius=pattern.radius,
                segments=128,
            )
        )
        suppression_tolerance = max(0.8, pattern.radius * 0.02)
        centerlines[view_name] = [
            line
            for line in centerlines.get(view_name, [])
            if all(
                hypot(
                    (line.start[0] + line.end[0]) / 2.0 - hole_center[0],
                    (line.start[1] + line.end[1]) / 2.0 - hole_center[1],
                )
                > suppression_tolerance
                for hole_center in pattern.holes
            )
        ]
        radial_extension = max(2.0, pattern.radius * 0.045)
        diameter_directions: list[tuple[float, float]] = []
        for hole_center in sorted(
            pattern.holes,
            key=lambda point: atan2(
                point[1] - pattern.center[1], point[0] - pattern.center[0]
            ),
        ):
            dx = hole_center[0] - pattern.center[0]
            dy = hole_center[1] - pattern.center[1]
            length = hypot(dx, dy)
            if length <= 1.0e-9:
                continue
            ux, uy = dx / length, dy / length
            angle = atan2(uy, ux) % pi
            if any(
                abs(((angle - atan2(vy, vx) + pi / 2.0) % pi) - pi / 2.0)
                <= 0.03
                for vx, vy in diameter_directions
            ):
                continue
            diameter_directions.append((ux, uy))

        reach = pattern.radius + radial_extension
        annotations[view_name].extend(
            TechnicalAnnotation2D(
                role="CENTER",
                points=[
                    (pattern.center[0] - ux * reach, pattern.center[1] - uy * reach),
                    (pattern.center[0] + ux * reach, pattern.center[1] + uy * reach),
                ],
            )
            for ux, uy in diameter_directions[:2]
        )
        tick_half_length = max(1.8, min(3.0, pattern.radius * 0.045))
        for hole_center in pattern.holes:
            dx = hole_center[0] - pattern.center[0]
            dy = hole_center[1] - pattern.center[1]
            length = hypot(dx, dy)
            if length <= 1.0e-9:
                continue
            tx, ty = -dy / length, dx / length
            annotations[view_name].append(
                TechnicalAnnotation2D(
                    role="CENTER",
                    points=[
                        (
                            hole_center[0] - tx * tick_half_length,
                            hole_center[1] - ty * tick_half_length,
                        ),
                        (
                            hole_center[0] + tx * tick_half_length,
                            hole_center[1] + ty * tick_half_length,
                        ),
                    ],
                )
            )


def generate_projections(
    config: ProjectConfig,
    *,
    centerline_extension: float,
) -> ProjectionBundle:
    """Generate the authoritative six-view Projection2D data set."""
    if config.projection.method != "first_angle":
        raise ValueError("OrthoVideo supporta solo il metodo first_angle.")

    views = build_six_views(
        config.main_view.normal,
        config.main_view.up,
    )
    suffix = config.model.suffix.lower()
    projections: dict[str, Projection2D] = {}
    centerlines: dict[str, list[CenterLine2D]] = {}
    annotations: dict[str, list[TechnicalAnnotation2D]] = {
        name: [] for name in views
    }
    section_name: str | None = None
    section_projection: Projection2D | None = None
    section_centerlines: list[CenterLine2D] = []
    section_annotations: list[TechnicalAnnotation2D] = []
    section_reference_annotations: dict[str, list[TechnicalAnnotation2D]] = {
        name: [] for name in views
    }
    section_reference_labels: dict[str, list[TechnicalLabel2D]] = {
        name: [] for name in views
    }

    if suffix in {".step", ".stp"}:
        source_type = "STEP"
        geometry = load_step(config.model)
        cylinders = []

        for name, view in views.items():
            result = hlr_to_projection2d(
                project_shape(geometry, view),
                deflection=0.03,
            )
            tangent = result.tangent
            visible = result.visible

            if config.projection.tangent_edges == "full":
                visible = visible + tangent
                tangent = []
            elif config.projection.tangent_edges == "omit":
                tangent = []

            projections[name] = clean_projection(
                Projection2D(
                    visible=visible,
                    hidden=_hidden_lines_for_view(
                        config, name, result.hidden, visible
                    ),
                    tangent=tangent,
                )
            )

        if config.projection.show_centerlines:
            cylinders = extract_cylinders(geometry)
            centerlines = {
                name: build_centerlines_for_view(
                    cylinders,
                    view,
                    extension=centerline_extension,
                    visible_projection=projections[name],
                    include_longitudinal=(
                        name not in config.projection.center_mark_only_views
                    ),
                    front_feature_only=(
                        name in config.projection.center_mark_only_views
                    ),
                    principal_radius_mode=(
                        "largest_internal"
                        if name in config.projection.pitch_circle_views
                        else "smallest"
                    ),
                )
                for name, view in views.items()
            }
            _add_pitch_circle_annotations(
                annotations,
                centerlines,
                config.projection.pitch_circle_views,
            )

        if config.projection.section_view:
            section_name = config.projection.section_view
            section_view = views[section_name]
            section_shape = build_step_section_shape(
                geometry,
                section_view,
                offset_mm=config.projection.section_offset_mm,
            )
            section_result = hlr_to_projection2d(
                project_shape(section_shape, section_view),
                deflection=0.03,
            )
            section_tangent = (
                section_result.tangent
                if config.projection.tangent_edges == "thin"
                else []
            )
            section_visible = section_result.visible
            if config.projection.tangent_edges == "full":
                section_visible = section_visible + section_result.tangent
            section_projection = clean_projection(Projection2D(
                visible=section_visible,
                hidden=[],
                tangent=section_tangent,
            ))
            bbox = Bnd_Box()
            BRepBndLib.AddOptimal_s(geometry, bbox)
            model_bounds = bbox.Get()
            xmin, ymin, zmin, xmax, ymax, zmax = model_bounds
            section_plane_point = (
                (xmin + xmax) / 2.0
                + section_view.normal[0] * config.projection.section_offset_mm,
                (ymin + ymax) / 2.0
                + section_view.normal[1] * config.projection.section_offset_mm,
                (zmin + zmax) / 2.0
                + section_view.normal[2] * config.projection.section_offset_mm,
            )
            if config.projection.show_centerlines:
                section_centerlines = build_centerlines_for_view(
                    cylinders,
                    section_view,
                    extension=0.0,
                    visible_projection=section_projection,
                    section_plane_normal=section_view.normal,
                    section_plane_point=section_plane_point,
                )
                section_centerlines = clip_centerlines_to_projection(
                    section_centerlines,
                    section_projection,
                )
            section_annotations = build_step_section_annotations(
                geometry,
                section_view,
                offset_mm=config.projection.section_offset_mm,
                hatch_angle_deg=config.projection.hatch_angle_deg,
                hatch_spacing_mm=config.projection.hatch_spacing_mm,
                include_contours=False,
            )
            parent_name = _section_reference_parent(config, section_name)
            reference_annotations, reference_labels = build_section_reference(
                model_bounds,
                section_view,
                views[parent_name],
                projections[parent_name],
                offset_mm=config.projection.section_offset_mm,
            )
            section_reference_annotations[parent_name].extend(
                reference_annotations
            )
            section_reference_labels[parent_name].extend(reference_labels)

    elif suffix == ".obj":
        source_type = "OBJ"
        geometry = load_obj(config.model)

        for name, view in views.items():
            candidates = project_mesh_edges(
                geometry,
                view,
                feature_angle_deg=30.0,
            )
            visibility = resolve_mesh_visibility(
                geometry,
                candidates,
                view,
                samples_per_diagonal=150,
                max_segments_per_edge=128,
            )
            result = mesh_visibility_to_projection2d(visibility)
            projections[name] = clean_projection(
                Projection2D(
                    visible=result.visible,
                    hidden=_hidden_lines_for_view(
                        config, name, result.hidden, result.visible
                    ),
                )
            )

        if config.projection.section_view:
            section_name = config.projection.section_view
            section_view = views[section_name]
            section_mesh = build_mesh_section_mesh(
                geometry,
                section_view,
                offset_mm=config.projection.section_offset_mm,
            )
            section_candidates = project_mesh_edges(
                section_mesh,
                section_view,
                feature_angle_deg=30.0,
            )
            section_visibility = resolve_mesh_visibility(
                section_mesh,
                section_candidates,
                section_view,
                samples_per_diagonal=150,
                max_segments_per_edge=128,
            )
            section_result = mesh_visibility_to_projection2d(section_visibility)
            section_projection = clean_projection(Projection2D(
                visible=section_result.visible,
                hidden=[],
            ))
            section_annotations = build_mesh_section_annotations(
                geometry,
                section_view,
                offset_mm=config.projection.section_offset_mm,
                hatch_angle_deg=config.projection.hatch_angle_deg,
                hatch_spacing_mm=config.projection.hatch_spacing_mm,
                include_contours=False,
            )
            parent_name = _section_reference_parent(config, section_name)
            mesh_min, mesh_max = geometry.bounds
            model_bounds = (
                float(mesh_min[0]),
                float(mesh_min[1]),
                float(mesh_min[2]),
                float(mesh_max[0]),
                float(mesh_max[1]),
                float(mesh_max[2]),
            )
            reference_annotations, reference_labels = build_section_reference(
                model_bounds,
                section_view,
                views[parent_name],
                projections[parent_name],
                offset_mm=config.projection.section_offset_mm,
            )
            section_reference_annotations[parent_name].extend(
                reference_annotations
            )
            section_reference_labels[parent_name].extend(reference_labels)

    else:
        raise ValueError("Formato non supportato. Sono ammessi STEP, STP e OBJ.")

    for item in config.technical_annotations:
        if item.points:
            annotation = TechnicalAnnotation2D(
                role=item.role,
                points=list(item.points),
            )
        else:
            annotation = circle_annotation(
                role=item.role,
                center=item.center,
                radius=item.radius,
            )
        annotations[item.view].append(annotation)

    return ProjectionBundle(
        source_type=source_type,
        views=views,
        projections=projections,
        centerlines=centerlines,
        annotations=annotations,
        source_geometry=geometry,
        section_name=section_name,
        section_projection=section_projection,
        section_centerlines=section_centerlines,
        section_annotations=section_annotations,
        section_reference_annotations=section_reference_annotations,
        section_reference_labels=section_reference_labels,
    )
