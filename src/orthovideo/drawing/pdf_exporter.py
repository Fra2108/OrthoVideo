from pathlib import Path

from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from orthovideo.drawing.sheet_layout import FirstAngleLayout
from orthovideo.drawing.technical_styles import (
    DEFAULT_TECHNICAL_STYLE_PRESET,
    LineRole,
    TechnicalStylePreset,
)


def export_layout_pdf(
    layout: FirstAngleLayout,
    output_file: str | Path,
    *,
    style_preset: TechnicalStylePreset = DEFAULT_TECHNICAL_STYLE_PRESET,
) -> Path:
    """Write a vector PDF in physical millimetre scale with ReportLab."""
    return export_layouts_pdf(
        [layout],
        output_file,
        style_preset=style_preset,
    )


def export_layouts_pdf(
    layouts: list[FirstAngleLayout],
    output_file: str | Path,
    *,
    style_preset: TechnicalStylePreset = DEFAULT_TECHNICAL_STYLE_PRESET,
    style_presets: list[TechnicalStylePreset] | None = None,
) -> Path:
    """Write one or more technical layouts as a vector, multi-page PDF."""

    if not layouts:
        raise ValueError("È richiesta almeno una pagina PDF.")

    if style_presets is None:
        style_presets = [style_preset] * len(layouts)
    elif len(style_presets) != len(layouts):
        raise ValueError("Ogni pagina PDF richiede il proprio preset grafico.")

    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    first_layout = layouts[0]
    canvas = Canvas(
        str(output_file),
        pagesize=(first_layout.page_width * mm, first_layout.page_height * mm),
        pageCompression=1,
    )
    canvas.setTitle("OrthoVideo - First-angle orthographic sheet")
    canvas.setAuthor("OrthoVideo")

    for layout, page_style in zip(layouts, style_presets):
        if hasattr(canvas, "setPageSize"):
            canvas.setPageSize((layout.page_width * mm, layout.page_height * mm))
        _draw_layout_page(canvas, layout, page_style)
        canvas.showPage()

    canvas.save()
    return output_file


def _draw_layout_page(
    canvas: Canvas,
    layout: FirstAngleLayout,
    style_preset: TechnicalStylePreset,
) -> None:
    canvas.setFillColorRGB(*style_preset.pdf_background_rgb)
    canvas.rect(
        0,
        0,
        layout.page_width * mm,
        layout.page_height * mm,
        stroke=0,
        fill=1,
    )

    by_role: dict[LineRole, list] = {role: [] for role in LineRole}

    for polyline in layout.polylines:
        if len(polyline.points) >= 2:
            by_role[polyline.role].append(polyline)

    cap_codes = {"butt": 0, "round": 1, "square": 2}
    join_codes = {"miter": 0, "round": 1, "bevel": 2}

    for role in style_preset.draw_order:
        style = style_preset.style_for(role)
        canvas.setStrokeColorRGB(*style.pdf_color_rgb)
        canvas.setFillColorRGB(*style.pdf_color_rgb)
        canvas.setLineCap(cap_codes[style.line_cap])
        canvas.setLineJoin(join_codes[style.line_join])
        canvas.setLineWidth(style.width_mm * mm)
        canvas.setDash([length * mm for length in style.dash_pattern_mm])

        for polyline in by_role[role]:

            path = canvas.beginPath()

            for index, (x_mm, y_top_down_mm) in enumerate(polyline.points):
                x = x_mm * mm
                y = (layout.page_height - y_top_down_mm) * mm

                if index == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)

            closed_section_arrow = (
                role == LineRole.SECTION_CUT
                and len(polyline.points) == 4
                and abs(polyline.points[0][0] - polyline.points[-1][0]) <= 1.0e-8
                and abs(polyline.points[0][1] - polyline.points[-1][1]) <= 1.0e-8
            )
            canvas.drawPath(path, stroke=1, fill=1 if closed_section_arrow else 0)

    canvas.setDash([])

    for label in layout.labels:
        x_mm, y_top_down_mm = label.position
        canvas.setFillColorRGB(*label.color_rgb)
        canvas.setFont("Helvetica", label.font_size_mm * mm)
        draw = {
            "start": canvas.drawString,
            "middle": canvas.drawCentredString,
            "end": canvas.drawRightString,
        }.get(label.anchor)
        if draw is None:
            raise ValueError(f"Anchor etichetta non valido: {label.anchor!r}.")
        draw(x_mm * mm, (layout.page_height - y_top_down_mm) * mm, label.text)
