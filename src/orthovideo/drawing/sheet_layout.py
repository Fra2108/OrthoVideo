from dataclasses import dataclass

from orthovideo.projection.centerlines import CenterLine2D
from orthovideo.projection.result2d import Projection2D
from orthovideo.projection.annotations import TechnicalAnnotation2D, TechnicalLabel2D
from orthovideo.drawing.technical_styles import LineRole, coerce_line_role


Point2D = tuple[float, float]
Polyline2D = list[Point2D]


@dataclass(frozen=True)
class SheetPolyline:
    view: str
    layer: LineRole | str
    points: Polyline2D

    @property
    def role(self) -> LineRole:
        """Semantic role, while keeping the legacy ``layer`` API intact."""

        return coerce_line_role(self.layer)


@dataclass(frozen=True)
class SheetLabel:
    text: str
    position: Point2D
    font_size_mm: float = 4.0
    anchor: str = "middle"
    color_rgb: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass(frozen=True)
class ViewPlacement:
    name: str
    origin: Point2D
    width: float
    height: float
    bounds: tuple[float, float, float, float]


@dataclass(frozen=True)
class FirstAngleLayout:
    page_width: float
    page_height: float
    drawing_scale: float
    placements: dict[str, ViewPlacement]
    polylines: list[SheetPolyline]
    labels: list[SheetLabel]


VIEW_ORDER = (
    "right",
    "front",
    "left",
    "rear",
    "bottom",
    "top",
)


def projection_bounds(
    projection: Projection2D,
) -> tuple[float, float, float, float]:
    lines = projection.visible + projection.hidden

    if not lines:
        raise RuntimeError("La proiezione non contiene geometria.")

    points = [point for line in lines for point in line]

    if not points:
        raise RuntimeError("La proiezione contiene solo polilinee vuote.")

    xmin = min(point[0] for point in points)
    ymin = min(point[1] for point in points)
    xmax = max(point[0] for point in points)
    ymax = max(point[1] for point in points)

    if xmax - xmin <= 1e-9 or ymax - ymin <= 1e-9:
        raise RuntimeError("Bounding box 2D non valido.")

    return xmin, ymin, xmax, ymax


def build_first_angle_layout(
    projections: dict[str, Projection2D],
    *,
    centerlines: dict[str, list[CenterLine2D]] | None = None,
    annotations: dict[str, list[TechnicalAnnotation2D]] | None = None,
    view_labels: dict[str, list[TechnicalLabel2D]] | None = None,
    page_width: float = 420.0,
    page_height: float = 297.0,
    margin: float = 15.0,
    gap: float = 20.0,
    drawing_scale: float = 1.0,
    show_labels: bool = True,
) -> FirstAngleLayout:
    """Build the common page-space layout used by SVG, PDF and DXF.

    Page coordinates follow SVG convention: X grows right and Y grows down.
    In first-angle projection the right view is therefore left of FRONT, while
    BOTTOM is above FRONT and TOP is below it.
    """
    required = {"front", "rear", "top", "bottom", "right", "left"}
    missing = required - projections.keys()

    if missing:
        raise ValueError(f"Viste mancanti: {sorted(missing)}")

    if page_width <= 0 or page_height <= 0:
        raise ValueError("Le dimensioni del foglio devono essere positive.")

    if drawing_scale <= 0:
        raise ValueError("drawing_scale deve essere positivo.")

    centerlines = centerlines or {}
    annotations = annotations or {}
    view_labels = view_labels or {}
    bounds = {name: projection_bounds(projections[name]) for name in required}

    def width(name: str) -> float:
        xmin, _, xmax, _ = bounds[name]
        return xmax - xmin

    def height(name: str) -> float:
        _, ymin, _, ymax = bounds[name]
        return ymax - ymin

    s = drawing_scale
    middle_width = sum(width(name) * s for name in ("right", "front", "left", "rear")) + 3.0 * gap
    total_height = sum(height(name) * s for name in ("bottom", "front", "top")) + 2.0 * gap

    if middle_width > page_width - 2.0 * margin + 1e-9:
        raise RuntimeError("Le viste non entrano orizzontalmente nel foglio.")

    if total_height > page_height - 2.0 * margin + 1e-9:
        raise RuntimeError("Le viste non entrano verticalmente nel foglio.")

    group_x = (page_width - middle_width) / 2.0
    group_y = (page_height - total_height) / 2.0
    front_x = group_x + width("right") * s + gap
    front_y = group_y + height("bottom") * s + gap

    origins = {
        "right": (group_x, front_y),
        "front": (front_x, front_y),
        "left": (front_x + width("front") * s + gap, front_y),
        "rear": (
            front_x
            + width("front") * s
            + gap
            + width("left") * s
            + gap,
            front_y,
        ),
        "bottom": (front_x, group_y),
        "top": (front_x, front_y + height("front") * s + gap),
    }

    placements = {
        name: ViewPlacement(
            name=name,
            origin=origins[name],
            width=width(name) * s,
            height=height(name) * s,
            bounds=bounds[name],
        )
        for name in required
    }

    def transform(name: str, point: Point2D) -> Point2D:
        xmin, _, _, ymax = bounds[name]
        origin_x, origin_y = origins[name]
        return (
            origin_x + (point[0] - xmin) * s,
            origin_y + (ymax - point[1]) * s,
        )

    polylines: list[SheetPolyline] = []

    for name in VIEW_ORDER:
        for annotation in annotations.get(name, []):
            if len(annotation.points) >= 2:
                polylines.append(
                    SheetPolyline(
                        view=name,
                        layer=annotation.role,
                        points=[transform(name, point) for point in annotation.points],
                    )
                )

        for centerline in centerlines.get(name, []):
            polylines.append(
                SheetPolyline(
                    view=name,
                    layer=LineRole.CENTER,
                    points=[transform(name, centerline.start), transform(name, centerline.end)],
                )
            )

        for layer, lines in (
            (LineRole.TANGENT, projections[name].tangent),
            (LineRole.HIDDEN, projections[name].hidden),
            (LineRole.VISIBLE, projections[name].visible),
        ):
            for line in lines:
                if len(line) >= 2:
                    polylines.append(
                        SheetPolyline(
                            view=name,
                            layer=layer,
                            points=[transform(name, point) for point in line],
                        )
                    )

    labels: list[SheetLabel] = []

    for name in VIEW_ORDER:
        for label in view_labels.get(name, []):
            labels.append(
                SheetLabel(
                    text=label.text,
                    position=transform(name, label.position),
                )
            )

    if show_labels:
        for name in VIEW_ORDER:
            placement = placements[name]
            labels.append(
                SheetLabel(
                    text=name.upper(),
                    position=(
                        placement.origin[0] + placement.width / 2.0,
                        placement.origin[1] + placement.height + 6.0,
                    ),
                )
            )

    return FirstAngleLayout(
        page_width=page_width,
        page_height=page_height,
        drawing_scale=drawing_scale,
        placements=placements,
        polylines=polylines,
        labels=labels,
    )


def _centerline_duplicates_annotation(
    centerline: CenterLine2D,
    annotations: list[TechnicalAnnotation2D],
    *,
    tolerance: float = 0.25,
) -> bool:
    ax = centerline.end[0] - centerline.start[0]
    ay = centerline.end[1] - centerline.start[1]
    a_length = (ax * ax + ay * ay) ** 0.5
    if a_length <= 1.0e-9:
        return True

    for annotation in annotations:
        if annotation.role.upper() != "CENTER" or len(annotation.points) != 2:
            continue
        start, end = annotation.points
        bx = end[0] - start[0]
        by = end[1] - start[1]
        b_length = (bx * bx + by * by) ** 0.5
        if b_length <= 1.0e-9:
            continue
        if abs(ax * by - ay * bx) / (a_length * b_length) > 1.0e-4:
            continue
        distance = abs(
            (centerline.start[0] - start[0]) * by
            - (centerline.start[1] - start[1]) * bx
        ) / b_length
        if distance > tolerance:
            continue
        ux, uy = bx / b_length, by / b_length
        parameters = [
            (point[0] - start[0]) * ux + (point[1] - start[1]) * uy
            for point in (centerline.start, centerline.end)
        ]
        overlap = min(max(parameters), b_length) - max(min(parameters), 0.0)
        # Collinearity alone is not duplication: pitch-circle radials can share
        # an infinite line with a principal axis without covering that axis.
        if overlap >= a_length - tolerance:
            return True
    return False


def build_sectioned_first_angle_layout(
    projections: dict[str, Projection2D],
    section_projection: Projection2D,
    *,
    centerlines: dict[str, list[CenterLine2D]] | None = None,
    annotations: dict[str, list[TechnicalAnnotation2D]] | None = None,
    view_labels: dict[str, list[TechnicalLabel2D]] | None = None,
    section_centerlines: list[CenterLine2D] | None = None,
    section_annotations: list[TechnicalAnnotation2D] | None = None,
    page_width: float = 420.0,
    page_height: float = 297.0,
    margin: float = 8.0,
    horizontal_gap: float = 45.0,
    horizontal_gap_before: float | None = None,
    horizontal_gap_after: float | None = None,
    central_axis_offset: float = 0.0,
    vertical_gap: float = 10.0,
    vertical_gap_above: float | None = None,
    vertical_gap_below: float | None = None,
    drawing_scale: float = 0.5,
) -> FirstAngleLayout:
    """Build the sectioned first-angle cross used by production drawings.

    FRONT is replaced by its A-A section. RIGHT, LEFT, BOTTOM and TOP retain
    their exact projected datums around it; FRONT and REAR ordinary views are
    intentionally omitted because they are redundant once the section exists.
    """

    required = {"right", "left", "bottom", "top"}
    missing = required - projections.keys()
    if missing:
        raise ValueError(f"Viste mancanti: {sorted(missing)}")
    gap_above = vertical_gap if vertical_gap_above is None else vertical_gap_above
    gap_below = vertical_gap if vertical_gap_below is None else vertical_gap_below
    gap_before = (
        horizontal_gap if horizontal_gap_before is None else horizontal_gap_before
    )
    gap_after = horizontal_gap if horizontal_gap_after is None else horizontal_gap_after
    if (
        drawing_scale <= 0
        or gap_before <= 0
        or gap_after <= 0
        or gap_above <= 0
        or gap_below <= 0
    ):
        raise ValueError("Scala e gap della tavola sezionata devono essere positivi.")

    centerlines = centerlines or {}
    annotations = annotations or {}
    view_labels = view_labels or {}
    section_centerlines = section_centerlines or []
    section_annotations = section_annotations or []
    section_key = "section_A-A"
    source_projections = {
        "right": projections["right"],
        section_key: section_projection,
        "left": projections["left"],
        "bottom": projections["bottom"],
        "top": projections["top"],
    }
    bounds = {
        name: projection_bounds(projection)
        for name, projection in source_projections.items()
    }
    s = drawing_scale
    sxmin, symin, sxmax, symax = bounds[section_key]

    # Raw anchors use the actual projected zero datum. Middle views share Y=0;
    # end views share X=0. This is true first-angle correspondence and remains
    # correct for asymmetric models.
    anchors = {
        section_key: (0.0, 0.0),
        "right": (
            sxmin * s - gap_before - bounds["right"][2] * s,
            0.0,
        ),
        "left": (
            sxmax * s + gap_after - bounds["left"][0] * s,
            0.0,
        ),
        "bottom": (
            0.0,
            -symax * s - gap_above + bounds["bottom"][1] * s,
        ),
        "top": (
            0.0,
            -symin * s + gap_below + bounds["top"][3] * s,
        ),
    }

    def transform(name: str, point: Point2D) -> Point2D:
        anchor_x, anchor_y = anchors[name]
        return anchor_x + point[0] * s, anchor_y - point[1] * s

    raw_placements: dict[str, ViewPlacement] = {}
    for name, (xmin, ymin, xmax, ymax) in bounds.items():
        anchor_x, anchor_y = anchors[name]
        raw_placements[name] = ViewPlacement(
            name=name,
            origin=(anchor_x + xmin * s, anchor_y - ymax * s),
            width=(xmax - xmin) * s,
            height=(ymax - ymin) * s,
            bounds=(xmin, ymin, xmax, ymax),
        )

    polylines: list[SheetPolyline] = []

    def emit_view(
        name: str,
        projection: Projection2D,
        view_centerlines: list[CenterLine2D],
        view_annotations: list[TechnicalAnnotation2D],
    ) -> None:
        for annotation in view_annotations:
            if len(annotation.points) >= 2:
                polylines.append(
                    SheetPolyline(
                        view=name,
                        layer=annotation.role,
                        points=[transform(name, point) for point in annotation.points],
                    )
                )
        for centerline in view_centerlines:
            if _centerline_duplicates_annotation(centerline, view_annotations):
                continue
            polylines.append(
                SheetPolyline(
                    view=name,
                    layer=LineRole.CENTER,
                    points=[transform(name, centerline.start), transform(name, centerline.end)],
                )
            )
        for role, lines in (
            (LineRole.TANGENT, projection.tangent),
            (LineRole.HIDDEN, projection.hidden),
            (LineRole.VISIBLE, projection.visible),
        ):
            for line in lines:
                if len(line) >= 2:
                    polylines.append(
                        SheetPolyline(
                            view=name,
                            layer=role,
                            points=[transform(name, point) for point in line],
                        )
                    )

    for name in ("right", "left", "bottom", "top"):
        emit_view(
            name,
            source_projections[name],
            centerlines.get(name, []),
            annotations.get(name, []),
        )
    emit_view(
        section_key,
        section_projection,
        section_centerlines,
        section_annotations,
    )

    labels: list[SheetLabel] = []
    for name in ("right", "left", "bottom", "top"):
        for label in view_labels.get(name, []):
            label_position = transform(name, label.position)
            font_size_mm = 8.0 if label.text == "A" else 7.0
            if label.text == "A":
                # ReportLab positions text on its baseline. This converts the
                # technical label point to a visual centre, keeping the two A
                # labels symmetric above and below the cutting-plane termini.
                label_position = (
                    label_position[0],
                    label_position[1] + font_size_mm * 0.35,
                )
            labels.append(
                SheetLabel(
                    text=label.text,
                    position=label_position,
                    font_size_mm=font_size_mm,
                    color_rgb=(0.0, 0.0, 0.0),
                )
            )

    section_placement = raw_placements[section_key]
    title_y = section_placement.origin[1] + section_placement.height * 0.72
    labels.extend(
        [
            SheetLabel(
                text="SEZIONE",
                position=(section_placement.origin[0] - 16.0, title_y),
                font_size_mm=7.5,
            ),
            SheetLabel(
                text="A-A",
                position=(section_placement.origin[0] + 6.0, title_y + 0.8),
                font_size_mm=3.2,
            ),
        ]
    )

    extent_points = [
        point
        for placement in raw_placements.values()
        for point in (
            placement.origin,
            (
                placement.origin[0] + placement.width,
                placement.origin[1] + placement.height,
            ),
        )
    ]
    extent_points.extend(point for polyline in polylines for point in polyline.points)
    for label in labels:
        estimated_width = max(1.0, len(label.text) * label.font_size_mm * 0.52)
        extent_points.extend(
            [
                (
                    label.position[0] - estimated_width / 2.0,
                    label.position[1] - label.font_size_mm,
                ),
                (
                    label.position[0] + estimated_width / 2.0,
                    label.position[1] + label.font_size_mm * 0.35,
                ),
            ]
        )

    xmin = min(point[0] for point in extent_points)
    ymin = min(point[1] for point in extent_points)
    xmax = max(point[0] for point in extent_points)
    ymax = max(point[1] for point in extent_points)
    content_width = xmax - xmin
    content_height = ymax - ymin
    if content_width > page_width - 2.0 * margin + 1.0e-9:
        raise RuntimeError("La tavola sezionata non entra orizzontalmente nel foglio.")
    if content_height > page_height - 2.0 * margin + 1.0e-9:
        raise RuntimeError("La tavola sezionata non entra verticalmente nel foglio.")

    # The projected X=0 datum is authoritative. Anchoring it to the page makes
    # unequal title/view corridors deterministic instead of recentring their
    # combined bounding box after every model change.
    shift_x = page_width / 2.0 + central_axis_offset
    shift_y = (page_height - content_height) / 2.0 - ymin

    def shifted(point: Point2D) -> Point2D:
        return point[0] + shift_x, point[1] + shift_y

    placements = {
        name: ViewPlacement(
            name=placement.name,
            origin=shifted(placement.origin),
            width=placement.width,
            height=placement.height,
            bounds=placement.bounds,
        )
        for name, placement in raw_placements.items()
    }
    translated_polylines = [
        SheetPolyline(
            view=polyline.view,
            layer=polyline.layer,
            points=[shifted(point) for point in polyline.points],
        )
        for polyline in polylines
    ]
    translated_labels = [
        SheetLabel(
            text=label.text,
            position=shifted(label.position),
            font_size_mm=label.font_size_mm,
            anchor=label.anchor,
            color_rgb=label.color_rgb,
        )
        for label in labels
    ]

    return FirstAngleLayout(
        page_width=page_width,
        page_height=page_height,
        drawing_scale=drawing_scale,
        placements=placements,
        polylines=translated_polylines,
        labels=translated_labels,
    )


def build_single_view_layout(
    name: str,
    projection: Projection2D,
    *,
    centerlines: list[CenterLine2D] | None = None,
    annotations: list[TechnicalAnnotation2D] | None = None,
    label: str | None = None,
    page_width: float = 420.0,
    page_height: float = 297.0,
    margin: float = 15.0,
    drawing_scale: float = 1.0,
) -> FirstAngleLayout:
    """Place a real section (or another auxiliary view) on its own page."""

    if page_width <= 0 or page_height <= 0:
        raise ValueError("Le dimensioni del foglio devono essere positive.")
    if drawing_scale <= 0:
        raise ValueError("drawing_scale deve essere positivo.")

    bounds = projection_bounds(projection)
    xmin, ymin, xmax, ymax = bounds
    width = (xmax - xmin) * drawing_scale
    height = (ymax - ymin) * drawing_scale

    if width > page_width - 2.0 * margin + 1e-9:
        raise RuntimeError("La sezione non entra orizzontalmente nel foglio.")
    if height > page_height - 2.0 * margin - 10.0 + 1e-9:
        raise RuntimeError("La sezione non entra verticalmente nel foglio.")

    origin = (
        (page_width - width) / 2.0,
        (page_height - height) / 2.0 - 3.0,
    )
    placement = ViewPlacement(
        name=name,
        origin=origin,
        width=width,
        height=height,
        bounds=bounds,
    )

    def transform(point: Point2D) -> Point2D:
        return (
            origin[0] + (point[0] - xmin) * drawing_scale,
            origin[1] + (ymax - point[1]) * drawing_scale,
        )

    polylines: list[SheetPolyline] = []

    for annotation in annotations or []:
        if len(annotation.points) >= 2:
            polylines.append(
                SheetPolyline(
                    view=name,
                    layer=annotation.role,
                    points=[transform(point) for point in annotation.points],
                )
            )

    for centerline in centerlines or []:
        polylines.append(
            SheetPolyline(
                view=name,
                layer=LineRole.CENTER,
                points=[transform(centerline.start), transform(centerline.end)],
            )
        )

    for role, lines in (
        (LineRole.TANGENT, projection.tangent),
        (LineRole.HIDDEN, projection.hidden),
        (LineRole.VISIBLE, projection.visible),
    ):
        for line in lines:
            if len(line) >= 2:
                polylines.append(
                    SheetPolyline(
                        view=name,
                        layer=role,
                        points=[transform(point) for point in line],
                    )
                )

    labels = []
    if label:
        labels.append(
            SheetLabel(
                text=label,
                position=(page_width / 2.0, origin[1] + height + 9.0),
            )
        )

    return FirstAngleLayout(
        page_width=page_width,
        page_height=page_height,
        drawing_scale=drawing_scale,
        placements={name: placement},
        polylines=polylines,
        labels=labels,
    )
