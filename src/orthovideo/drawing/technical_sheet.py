from dataclasses import dataclass
from math import floor
from pathlib import Path

from orthovideo.drawing.sheet_layout import build_first_angle_layout
from orthovideo.drawing.svg_exporter import export_layout_svg
from orthovideo.drawing.technical_styles import (
    DEFAULT_TECHNICAL_STYLE_PRESET,
    TechnicalStylePreset,
)
from orthovideo.projection.centerlines import CenterLine2D
from orthovideo.projection.result2d import Projection2D
from orthovideo.projection.annotations import TechnicalAnnotation2D, TechnicalLabel2D


Point2D = tuple[float, float]
Polyline = list[Point2D]


@dataclass
class View2D:
    name: str
    visible: list[Polyline]
    hidden: list[Polyline]
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    @property
    def width(self) -> float:
        return self.xmax - self.xmin

    @property
    def height(self) -> float:
        return self.ymax - self.ymin


def projection_to_view2d(
    name: str,
    result: Projection2D,
) -> View2D:
    """Adapt the common projection result to the legacy sizing API."""

    visible = result.visible
    hidden = result.hidden
    all_lines = visible + hidden

    if not all_lines:
        raise RuntimeError(f"La vista '{name}' non contiene geometria.")

    points = [point for line in all_lines for point in line]

    if not points:
        raise RuntimeError(f"La vista '{name}' contiene solo polilinee vuote.")

    return View2D(
        name=name,
        visible=visible,
        hidden=hidden,
        xmin=min(point[0] for point in points),
        ymin=min(point[1] for point in points),
        xmax=max(point[0] for point in points),
        ymax=max(point[1] for point in points),
    )


def export_first_angle_sheet(
    projections: dict[str, Projection2D],
    output_file: str | Path,
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
    style_preset: TechnicalStylePreset = DEFAULT_TECHNICAL_STYLE_PRESET,
) -> Path:
    """Export the six-view first-angle drawing through the common layout."""

    layout = build_first_angle_layout(
        projections,
        centerlines=centerlines,
        annotations=annotations,
        view_labels=view_labels,
        page_width=page_width,
        page_height=page_height,
        margin=margin,
        gap=gap,
        drawing_scale=drawing_scale,
        show_labels=show_labels,
    )
    result = export_layout_svg(
        layout,
        output_file,
        style_preset=style_preset,
    )

    print()
    print("Tavola primo diedro creata:")
    print(result)
    print()
    print(f"Formato: {page_width:.0f} x {page_height:.0f} mm")
    print(f"Scala geometrica: {drawing_scale}:1")
    return result


def choose_iso_scale(
    projections: dict[str, Projection2D],
    *,
    page_width: float,
    page_height: float,
    margin: float,
    gap: float,
) -> float:
    """Select the largest preferred ISO scale that fits all six views."""

    names = ("front", "rear", "top", "bottom", "right", "left")
    views = {
        name: projection_to_view2d(name, projections[name])
        for name in names
    }
    front = views["front"]
    rear = views["rear"]
    top = views["top"]
    bottom = views["bottom"]
    right = views["right"]
    left = views["left"]
    available_geometry_width = page_width - 2.0 * margin - 3.0 * gap
    available_geometry_height = page_height - 2.0 * margin - 2.0 * gap

    if available_geometry_width <= 0 or available_geometry_height <= 0:
        raise RuntimeError("Margini/gap troppo grandi per il foglio.")

    raw_width = right.width + front.width + left.width + rear.width
    raw_height = bottom.height + front.height + top.height
    max_scale = min(
        available_geometry_width / raw_width,
        available_geometry_height / raw_height,
    )

    # Include 1:2.5 and 1:4.  Without these intermediate reductions a layout
    # that misses 1:2 by a fraction jumps all the way down to 1:5 and wastes
    # most of an A3 sheet.
    for scale in (
        10.0,
        5.0,
        2.0,
        1.0,
        0.5,
        0.4,
        0.25,
        0.2,
        0.1,
        0.05,
        0.02,
        0.01,
    ):
        if scale <= max_scale + 1e-9:
            return scale

    raise RuntimeError(
        "Il modello è troppo grande anche alla minima scala disponibile."
    )


def choose_sectioned_iso_scale(
    projections: dict[str, Projection2D],
    section_projection: Projection2D,
    *,
    page_width: float,
    page_height: float,
    margin: float,
    horizontal_gap: float,
    horizontal_gap_before: float | None = None,
    horizontal_gap_after: float | None = None,
    vertical_gap: float,
    vertical_gap_above: float | None = None,
    vertical_gap_below: float | None = None,
    annotation_clearance: float = 7.0,
) -> float:
    """Choose one common ISO scale for the five-view sectioned cross."""

    views = {
        name: projection_to_view2d(name, projections[name])
        for name in ("right", "left", "bottom", "top")
    }
    section = projection_to_view2d("section_A-A", section_projection)
    width_sum = views["right"].width + section.width + views["left"].width
    height_sum = views["bottom"].height + section.height + views["top"].height
    gap_before = horizontal_gap if horizontal_gap_before is None else horizontal_gap_before
    gap_after = horizontal_gap if horizontal_gap_after is None else horizontal_gap_after
    available_width = page_width - 2.0 * margin - gap_before - gap_after
    gap_above = vertical_gap if vertical_gap_above is None else vertical_gap_above
    gap_below = vertical_gap if vertical_gap_below is None else vertical_gap_below
    available_height = (
        page_height
        - 2.0 * margin
        - gap_above
        - gap_below
        - annotation_clearance
    )
    if available_width <= 0 or available_height <= 0:
        raise RuntimeError("Margini/gap troppo grandi per la tavola sezionata.")

    max_scale = min(
        available_width / width_sum,
        available_height / height_sum,
    )
    for scale in (
        10.0,
        5.0,
        2.0,
        1.0,
        0.5,
        0.4,
        0.25,
        0.2,
        0.1,
        0.05,
        0.02,
        0.01,
    ):
        if scale <= max_scale + 1.0e-9:
            return scale

    raise RuntimeError("Il modello è troppo grande per la tavola sezionata.")


def choose_sectioned_fit_scale(
    projections: dict[str, Projection2D],
    section_projection: Projection2D,
    *,
    page_width: float,
    page_height: float,
    margin: float,
    horizontal_gap: float,
    horizontal_gap_before: float | None = None,
    horizontal_gap_after: float | None = None,
    vertical_gap: float,
    vertical_gap_above: float | None = None,
    vertical_gap_below: float | None = None,
    maximum_scale: float = 2.0,
) -> float:
    """Fill the five-view cross with one undistorted common scale.

    This presentation mode uses the page efficiently while preserving exact
    first-angle correspondence. The result is rounded down to a hundredth so
    PDF/raster rounding cannot push geometry beyond the requested margins.
    """

    views = {
        name: projection_to_view2d(name, projections[name])
        for name in ("right", "left", "bottom", "top")
    }
    section = projection_to_view2d("section_A-A", section_projection)
    width_sum = views["right"].width + section.width + views["left"].width
    height_sum = views["bottom"].height + section.height + views["top"].height
    gap_before = horizontal_gap if horizontal_gap_before is None else horizontal_gap_before
    gap_after = horizontal_gap if horizontal_gap_after is None else horizontal_gap_after
    available_width = page_width - 2.0 * margin - gap_before - gap_after
    gap_above = vertical_gap if vertical_gap_above is None else vertical_gap_above
    gap_below = vertical_gap if vertical_gap_below is None else vertical_gap_below
    available_height = page_height - 2.0 * margin - gap_above - gap_below
    if available_width <= 0 or available_height <= 0:
        raise RuntimeError("Margini/gap troppo grandi per la tavola sezionata.")

    raw_scale = min(
        maximum_scale,
        available_width / width_sum,
        available_height / height_sum,
    )
    scale = floor((raw_scale + 1.0e-10) * 100.0) / 100.0
    if scale < 0.01:
        raise RuntimeError("Il modello è troppo grande per la tavola sezionata.")
    return scale


def choose_single_view_iso_scale(
    projection: Projection2D,
    *,
    page_width: float,
    page_height: float,
    margin: float,
    label_clearance: float = 12.0,
) -> float:
    """Select the largest preferred ISO scale for an auxiliary/section view."""

    view = projection_to_view2d("auxiliary", projection)
    available_width = page_width - 2.0 * margin
    available_height = page_height - 2.0 * margin - label_clearance

    if available_width <= 0 or available_height <= 0:
        raise RuntimeError("Margini troppo grandi per il foglio di sezione.")

    max_scale = min(
        available_width / view.width,
        available_height / view.height,
    )

    for scale in (10.0, 5.0, 2.0, 1.0, 0.5, 0.2, 0.1, 0.05, 0.02, 0.01):
        if scale <= max_scale + 1e-9:
            return scale

    raise RuntimeError("La sezione è troppo grande per il foglio disponibile.")


def scale_to_text(scale: float) -> str:
    if scale >= 1.0:
        return f"{scale:g}:1"

    return f"1:{1.0 / scale:g}"
