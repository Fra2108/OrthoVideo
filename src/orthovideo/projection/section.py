from math import ceil, cos, floor, hypot, log10, radians, sin

from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRep import BRep_Builder
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.Bnd import Bnd_Box
from OCP.GCPnts import GCPnts_QuasiUniformDeflection
from OCP.TopAbs import TopAbs_EDGE, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Compound, TopoDS_Shape
from OCP.BRepPrimAPI import BRepPrimAPI_MakeHalfSpace
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt
import numpy as np
import trimesh

from orthovideo.projection.annotations import TechnicalAnnotation2D, TechnicalLabel2D
from orthovideo.projection.result2d import Projection2D
from orthovideo.projection.view_system import ViewDefinition, cross, dot, normalize


Point2D = tuple[float, float]
Segment2D = tuple[Point2D, Point2D]


def _step_section_plane(shape: TopoDS_Shape, view: ViewDefinition, offset_mm: float):
    normal = normalize(view.normal)
    bbox = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, bbox)
    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
    center = (
        (xmin + xmax) / 2.0 + normal[0] * offset_mm,
        (ymin + ymax) / 2.0 + normal[1] * offset_mm,
        (zmin + zmax) / 2.0 + normal[2] * offset_mm,
    )
    diagonal = hypot(hypot(xmax - xmin, ymax - ymin), zmax - zmin)
    extent = max(diagonal * 2.0, 1.0)
    plane = gp_Pln(gp_Pnt(*center), gp_Dir(*normal))
    cutting_face = BRepBuilderAPI_MakeFace(
        plane, -extent, extent, -extent, extent
    ).Face()
    return normal, center, diagonal, cutting_face


def build_step_section_shape(
    shape: TopoDS_Shape,
    view: ViewDefinition,
    *,
    offset_mm: float = 0.0,
) -> TopoDS_Shape:
    """Remove the half of a STEP model between the cut plane and observer.

    The retained B-Rep is authoritative geometry for the section projection;
    it is not the ordinary exterior view with a hatch drawn on top.
    Assemblies are clipped solid by solid so touching components are preserved.
    """

    if shape.IsNull():
        raise ValueError("Impossibile sezionare una shape nulla.")

    normal, center, diagonal, cutting_face = _step_section_plane(
        shape, view, offset_mm
    )
    reference_distance = max(diagonal, 1.0) * 2.0
    retained_point = gp_Pnt(
        center[0] - normal[0] * reference_distance,
        center[1] - normal[1] * reference_distance,
        center[2] - normal[2] * reference_distance,
    )
    half_space = BRepPrimAPI_MakeHalfSpace(
        cutting_face, retained_point
    ).Solid()
    operands: list[TopoDS_Shape] = []
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)

    while explorer.More():
        operands.append(explorer.Current())
        explorer.Next()

    operands = operands or [shape]
    compound = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(compound)
    added = 0

    for operand in operands:
        operation = BRepAlgoAPI_Common(operand, half_space)
        operation.SetFuzzyValue(1e-7)
        operation.Build()

        if not operation.IsDone():
            raise RuntimeError("Clipping B-Rep della vista in sezione fallito.")

        clipped = operation.Shape()
        if clipped.IsNull():
            continue
        builder.Add(compound, clipped)
        added += 1

    if not added:
        raise RuntimeError("Il piano di sezione non interseca il modello.")

    return compound


def _project_point(point, screen_x, screen_y) -> Point2D:
    xyz = (point.X(), point.Y(), point.Z())
    return dot(xyz, screen_x), dot(xyz, screen_y)


def build_section_reference(
    model_bounds: tuple[float, float, float, float, float, float],
    section_view: ViewDefinition,
    parent_view: ViewDefinition,
    parent_projection: Projection2D,
    *,
    offset_mm: float = 0.0,
) -> tuple[list[TechnicalAnnotation2D], list[TechnicalLabel2D]]:
    """Build the A-A cutting-plane line, arrows and labels on a parent view."""

    xmin, ymin, zmin, xmax, ymax, zmax = model_bounds
    normal = normalize(section_view.normal)
    center = (
        (xmin + xmax) / 2.0 + normal[0] * offset_mm,
        (ymin + ymax) / 2.0 + normal[1] * offset_mm,
        (zmin + zmax) / 2.0 + normal[2] * offset_mm,
    )
    parent_y = normalize(parent_view.up)
    parent_x = normalize(cross(parent_y, parent_view.normal))
    plane_center = (
        dot(center, parent_x),
        dot(center, parent_y),
    )
    # ViewDefinition.normal points from the model towards the observer.  A
    # cutting-plane arrow indicates the opposite direction: from the parent
    # view into the material towards the generated section.
    arrow_direction = (
        -dot(normal, parent_x),
        -dot(normal, parent_y),
    )
    direction_length = hypot(*arrow_direction)

    if direction_length <= 1e-8:
        raise ValueError("La vista di richiamo deve essere ortogonale alla sezione.")

    arrow_direction = (
        arrow_direction[0] / direction_length,
        arrow_direction[1] / direction_length,
    )
    line_direction = (-arrow_direction[1], arrow_direction[0])
    all_points = [
        point
        for line in parent_projection.visible + parent_projection.hidden
        for point in line
    ]

    if not all_points:
        raise RuntimeError("La vista di richiamo A-A non contiene geometria.")

    width = max(point[0] for point in all_points) - min(
        point[0] for point in all_points
    )
    height = max(point[1] for point in all_points) - min(
        point[1] for point in all_points
    )
    overall_span = max(width, height)
    line_parameters = [
        (point[0] - plane_center[0]) * line_direction[0]
        + (point[1] - plane_center[1]) * line_direction[1]
        for point in all_points
    ]
    margin = overall_span * 0.06
    end_parameters = [
        min(line_parameters) - margin,
        max(line_parameters) + margin,
    ]
    ends = [
        (
            plane_center[0] + line_direction[0] * parameter,
            plane_center[1] + line_direction[1] * parameter,
        )
        for parameter in end_parameters
    ]
    annotations = [
        TechnicalAnnotation2D(role="CENTER", points=ends)
    ]
    labels: list[TechnicalLabel2D] = []
    shaft_length = overall_span * 0.12
    head_length = overall_span * 0.0315
    head_width = head_length * 0.55
    terminal_length = overall_span * 0.055

    for index, tip in enumerate(ends):
        outward = (
            line_direction[0] * (-1.0 if index == 0 else 1.0),
            line_direction[1] * (-1.0 if index == 0 else 1.0),
        )
        terminal_inner = (
            tip[0] - outward[0] * terminal_length,
            tip[1] - outward[1] * terminal_length,
        )
        shaft_start = (
            tip[0] - arrow_direction[0] * shaft_length,
            tip[1] - arrow_direction[1] * shaft_length,
        )
        head_base = (
            tip[0] - arrow_direction[0] * head_length,
            tip[1] - arrow_direction[1] * head_length,
        )
        annotations.extend(
            [
                TechnicalAnnotation2D(
                    role="SECTION_CUT", points=[terminal_inner, tip]
                ),
                TechnicalAnnotation2D(
                    role="SECTION_CUT", points=[shaft_start, tip]
                ),
                TechnicalAnnotation2D(
                    role="SECTION_CUT",
                    points=[
                        (
                            head_base[0] + line_direction[0] * head_width,
                            head_base[1] + line_direction[1] * head_width,
                        ),
                        tip,
                        (
                            head_base[0] - line_direction[0] * head_width,
                            head_base[1] - line_direction[1] * head_width,
                        ),
                        (
                            head_base[0] + line_direction[0] * head_width,
                            head_base[1] + line_direction[1] * head_width,
                        ),
                    ],
                ),
            ]
        )
        labels.append(
            TechnicalLabel2D(
                text="A",
                position=(
                    tip[0]
                    + outward[0] * head_length * 3.0
                    - arrow_direction[0] * head_length * 4.0,
                    tip[1]
                    + outward[1] * head_length * 3.0
                    - arrow_direction[1] * head_length * 4.0,
                ),
            )
        )

    return annotations, labels


def _discretize_section_edge(edge, screen_x, screen_y, deflection: float):
    curve = BRepAdaptor_Curve(edge)
    first = curve.FirstParameter()
    last = curve.LastParameter()
    sampler = GCPnts_QuasiUniformDeflection()
    sampler.Initialize(curve, deflection, first, last)

    if not sampler.IsDone():
        raise RuntimeError("Discretizzazione del contorno di sezione fallita.")

    return [
        _project_point(curve.Value(sampler.Parameter(index)), screen_x, screen_y)
        for index in range(1, sampler.NbPoints() + 1)
    ]


def _canonical_segment(a: Point2D, b: Point2D, tolerance: float):
    digits = max(0, int(round(-log10(tolerance))))
    qa = (round(a[0], digits), round(a[1], digits))
    qb = (round(b[0], digits), round(b[1], digits))
    return tuple(sorted((qa, qb)))


def _boundary_segments(polylines, tolerance: float = 1e-6) -> list[Segment2D]:
    unique: dict[tuple, Segment2D] = {}

    for polyline in polylines:
        for a, b in zip(polyline, polyline[1:]):
            if hypot(b[0] - a[0], b[1] - a[1]) <= tolerance:
                continue
            unique.setdefault(_canonical_segment(a, b, tolerance), (a, b))

    return list(unique.values())


def _hatch_segments(
    boundaries: list[Segment2D],
    *,
    angle_deg: float,
    spacing: float,
    tolerance: float = 1e-7,
) -> list[Segment2D]:
    if not boundaries:
        return []

    angle = radians(angle_deg)
    direction = (cos(angle), sin(angle))
    perpendicular = (-direction[1], direction[0])
    points = [point for segment in boundaries for point in segment]
    dot2 = lambda a, b: a[0] * b[0] + a[1] * b[1]
    q_values = [dot2(point, perpendicular) for point in points]
    q_start = floor(min(q_values) / spacing) * spacing
    q_end = ceil(max(q_values) / spacing) * spacing
    result: list[Segment2D] = []
    line_count = int(round((q_end - q_start) / spacing)) + 1

    for line_index in range(line_count):
        q = q_start + line_index * spacing
        intersections: list[float] = []

        for a, b in boundaries:
            qa = dot2(a, perpendicular)
            qb = dot2(b, perpendicular)

            # Half-open crossing rule prevents double counting at vertices.
            if not ((qa <= q < qb) or (qb <= q < qa)):
                continue

            factor = (q - qa) / (qb - qa)
            point = (
                a[0] + factor * (b[0] - a[0]),
                a[1] + factor * (b[1] - a[1]),
            )
            intersections.append(dot2(point, direction))

        intersections.sort()
        unique_t: list[float] = []

        for value in intersections:
            if not unique_t or abs(value - unique_t[-1]) > tolerance:
                unique_t.append(value)

        for start, end in zip(unique_t[0::2], unique_t[1::2]):
            if end - start <= tolerance:
                continue
            result.append(
                (
                    (
                        direction[0] * start + perpendicular[0] * q,
                        direction[1] * start + perpendicular[1] * q,
                    ),
                    (
                        direction[0] * end + perpendicular[0] * q,
                        direction[1] * end + perpendicular[1] * q,
                    ),
                )
            )

    return result


def build_step_section_annotations(
    shape: TopoDS_Shape,
    view: ViewDefinition,
    *,
    offset_mm: float = 0.0,
    hatch_angle_deg: float = 45.0,
    hatch_spacing_mm: float = 4.0,
    deflection: float = 0.05,
    include_contours: bool = True,
) -> list[TechnicalAnnotation2D]:
    """Intersect a STEP B-Rep with a plane and hatch only solid material.

    The finite planar face is intersected with the exact B-Rep. Its boundary
    loops include holes; the even/odd hatch clipping rule therefore leaves
    bores and other voids unhatched.
    """
    if shape.IsNull():
        raise ValueError("Impossibile sezionare una shape nulla.")

    if hatch_spacing_mm <= 0:
        raise ValueError("Il passo della campitura deve essere positivo.")

    normal = normalize(view.normal)
    screen_y = normalize(view.up)
    screen_x = normalize(cross(screen_y, normal))
    _, _, _, cutting_face = _step_section_plane(shape, view, offset_mm)
    solids: list[TopoDS_Shape] = []
    solid_explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while solid_explorer.More():
        solids.append(solid_explorer.Current())
        solid_explorer.Next()

    # Boolean operations on an assembly compound may discard overlapping or
    # merely touching members. Slice each solid independently so all assembly
    # components receive their own material hatch.
    operands = solids or [shape]
    annotations: list[TechnicalAnnotation2D] = []

    for operand in operands:
        operation = BRepAlgoAPI_Common(operand, cutting_face)
        operation.SetFuzzyValue(1e-7)
        operation.Build()

        if not operation.IsDone():
            raise RuntimeError("Intersezione B-Rep del piano di sezione fallita.")

        section_shape = operation.Shape()
        if section_shape.IsNull():
            continue

        contours: list[list[Point2D]] = []
        explorer = TopExp_Explorer(section_shape, TopAbs_EDGE)

        while explorer.More():
            edge = TopoDS.Edge_s(explorer.Current())
            points = _discretize_section_edge(
                edge, screen_x, screen_y, deflection
            )
            if len(points) >= 2:
                contours.append(points)
            explorer.Next()

        boundaries = _boundary_segments(contours)
        hatches = _hatch_segments(
            boundaries,
            angle_deg=hatch_angle_deg,
            spacing=hatch_spacing_mm,
        )
        if include_contours:
            annotations.extend(
                TechnicalAnnotation2D(role="SECTION_CUT", points=points)
                for points in contours
            )
        annotations.extend(
            TechnicalAnnotation2D(role="HATCH", points=[start, end])
            for start, end in hatches
        )

    if not annotations:
        raise RuntimeError("Il piano di sezione non interseca il modello.")

    return annotations


def build_mesh_section_annotations(
    mesh: trimesh.Trimesh,
    view: ViewDefinition,
    *,
    offset_mm: float = 0.0,
    hatch_angle_deg: float = 45.0,
    hatch_spacing_mm: float = 4.0,
    include_contours: bool = True,
) -> list[TechnicalAnnotation2D]:
    """Slice a watertight OBJ mesh and hatch the resulting material loops."""
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        raise ValueError("Mesh OBJ vuota o non valida per la sezione.")

    if not mesh.is_watertight:
        raise RuntimeError(
            "La campitura OBJ richiede una mesh chiusa (watertight)."
        )

    normal = normalize(view.normal)
    screen_y = normalize(view.up)
    screen_x = normalize(cross(screen_y, normal))
    center = np.asarray(mesh.bounds, dtype=float).mean(axis=0)
    plane_origin = center + np.asarray(normal, dtype=float) * offset_mm
    segments_3d = trimesh.intersections.mesh_plane(
        mesh,
        plane_normal=np.asarray(normal, dtype=float),
        plane_origin=plane_origin,
    )

    if len(segments_3d) == 0:
        raise RuntimeError("Il piano di sezione non interseca la mesh OBJ.")

    boundaries = [
        (
            (dot(tuple(segment[0]), screen_x), dot(tuple(segment[0]), screen_y)),
            (dot(tuple(segment[1]), screen_x), dot(tuple(segment[1]), screen_y)),
        )
        for segment in segments_3d
    ]
    boundaries = _boundary_segments(
        [[start, end] for start, end in boundaries]
    )
    hatches = _hatch_segments(
        boundaries,
        angle_deg=hatch_angle_deg,
        spacing=hatch_spacing_mm,
    )
    annotations = []
    if include_contours:
        annotations.extend(
            TechnicalAnnotation2D(role="SECTION_CUT", points=[start, end])
            for start, end in boundaries
        )
    annotations.extend(
        TechnicalAnnotation2D(role="HATCH", points=[start, end])
        for start, end in hatches
    )
    return annotations


def build_mesh_section_mesh(
    mesh: trimesh.Trimesh,
    view: ViewDefinition,
    *,
    offset_mm: float = 0.0,
) -> trimesh.Trimesh:
    """Return the OBJ half-model behind the section plane.

    OBJ remains a sampled mesh pipeline.  The open boundary is intentional:
    the exact/sampled cut contour and its hatch are supplied separately by
    ``build_mesh_section_annotations``.
    """

    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        raise ValueError("Mesh OBJ vuota o non valida per la sezione.")

    normal = np.asarray(normalize(view.normal), dtype=float)
    center = np.asarray(mesh.bounds, dtype=float).mean(axis=0)
    plane_origin = center + normal * offset_mm
    vertices, faces, _ = trimesh.intersections.slice_faces_plane(
        vertices=np.asarray(mesh.vertices),
        faces=np.asarray(mesh.faces),
        plane_origin=plane_origin,
        plane_normal=-normal,
    )
    clipped = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)

    if clipped is None or len(clipped.faces) == 0:
        raise RuntimeError("Il piano di sezione non interseca la mesh OBJ.")

    return clipped
