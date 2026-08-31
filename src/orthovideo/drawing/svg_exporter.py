from pathlib import Path
from xml.sax.saxutils import escape

from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GCPnts import GCPnts_QuasiUniformDeflection
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Shape

from orthovideo.drawing.sheet_layout import FirstAngleLayout
from orthovideo.drawing.technical_styles import (
    DEFAULT_TECHNICAL_STYLE_PRESET,
    LineRole,
    TechnicalStylePreset,
)


Point2D = tuple[float, float]


def export_layout_svg(
    layout: FirstAngleLayout,
    output_file: str | Path,
    *,
    style_preset: TechnicalStylePreset = DEFAULT_TECHNICAL_STYLE_PRESET,
) -> Path:
    """Write a millimetre-based SVG from the common sheet layout.

    A group is emitted for every known semantic role, even when it is empty.
    This keeps the SVG layer structure stable and means new roles such as
    section cuts and hatching work without exporter-specific changes.
    """

    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    by_role: dict[LineRole, list] = {role: [] for role in LineRole}

    for polyline in layout.polylines:
        if len(polyline.points) >= 2:
            by_role[polyline.role].append(polyline)

    groups = []

    for role in style_preset.draw_order:
        style = style_preset.style_for(role)
        dash_attribute = ""

        if style.dash_pattern_mm:
            dash = " ".join(f"{length:g}" for length in style.dash_pattern_mm)
            dash_attribute = f' stroke-dasharray="{dash}"'

        polylines = []

        for polyline in by_role[role]:
            points = " ".join(
                f"{x_mm:.4f},{y_top_down_mm:.4f}"
                for x_mm, y_top_down_mm in polyline.points
            )
            polylines.append(
                f'<polyline data-view="{escape(polyline.view)}" points="{points}" />'
            )

        groups.append(
            f"""    <g
        id="layer-{role.value.lower()}"
        data-role="{role.value}"
        fill="none"
        stroke="black"
        stroke-width="{style.width_mm:g}"
        stroke-linecap="{style.line_cap}"
        stroke-linejoin="{style.line_join}"{dash_attribute}
    >
        {''.join(polylines)}
    </g>"""
        )

    labels = []

    for label in layout.labels:
        x_mm, y_top_down_mm = label.position
        labels.append(
            f'<text x="{x_mm:.3f}" y="{y_top_down_mm:.3f}" '
            f'text-anchor="middle">{escape(label.text)}</text>'
        )

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg
    xmlns="http://www.w3.org/2000/svg"
    width="{layout.page_width:g}mm"
    height="{layout.page_height:g}mm"
    viewBox="0 0 {layout.page_width:g} {layout.page_height:g}"
>
    <rect
        x="0"
        y="0"
        width="{layout.page_width:g}"
        height="{layout.page_height:g}"
        fill="white"
    />
{chr(10).join(groups)}
    <g
        id="layer-label"
        font-family="Arial, sans-serif"
        font-size="4"
        fill="#777"
    >
        {''.join(labels)}
    </g>
</svg>
"""
    output_file.write_text(svg, encoding="utf-8")
    return output_file


def discretize_edge(
    edge,
    deflection: float = 0.05,
) -> list[Point2D]:
    """
    Trasforma un edge OpenCascade proiettato
    in una sequenza di punti 2D.

    deflection più piccola = curve più precise.
    """

    curve = BRepAdaptor_Curve(edge)

    first = curve.FirstParameter()
    last = curve.LastParameter()

    discretizer = GCPnts_QuasiUniformDeflection()

    discretizer.Initialize(
        curve,
        deflection,
        first,
        last,
    )

    if not discretizer.IsDone():
        raise RuntimeError(
            "Discretizzazione dell'edge fallita."
        )

    points: list[Point2D] = []

    for i in range(
        1,
        discretizer.NbPoints() + 1,
    ):
        parameter = discretizer.Parameter(i)

        point = curve.Value(parameter)

        # Dopo HLR, X e Y costituiscono
        # il sistema 2D della vista.
        points.append(
            (
                point.X(),
                point.Y(),
            )
        )

    return points


def shape_to_polylines(
    shapes: list[TopoDS_Shape],
    deflection: float = 0.05,
) -> list[list[Point2D]]:
    """
    Estrae tutti gli edge dai compound HLR.
    """

    polylines = []

    for shape in shapes:

        explorer = TopExp_Explorer(
            shape,
            TopAbs_EDGE,
        )

        while explorer.More():

            edge = TopoDS.Edge_s(
                explorer.Current()
            )

            points = discretize_edge(
                edge,
                deflection=deflection,
            )

            if len(points) >= 2:
                polylines.append(points)

            explorer.Next()

    return polylines


def export_projection_svg(
    visible_shapes: list[TopoDS_Shape],
    hidden_shapes: list[TopoDS_Shape],
    output_file: str | Path,
    *,
    width: int = 1000,
    height: int = 700,
    margin: int = 70,
    title: str = "",
):
    """
    Esporta una proiezione HLR in SVG.

    Visibili -> linea continua.
    Nascoste -> linea tratteggiata.
    """

    output_file = Path(output_file)

    visible = shape_to_polylines(
        visible_shapes
    )

    hidden = shape_to_polylines(
        hidden_shapes
    )

    all_lines = visible + hidden

    if not all_lines:
        raise RuntimeError(
            "La proiezione non contiene geometria."
        )

    all_points = [
        point
        for line in all_lines
        for point in line
    ]

    xmin = min(p[0] for p in all_points)
    xmax = max(p[0] for p in all_points)

    ymin = min(p[1] for p in all_points)
    ymax = max(p[1] for p in all_points)

    model_width = xmax - xmin
    model_height = ymax - ymin

    if model_width <= 0 or model_height <= 0:
        raise RuntimeError(
            "Bounding box 2D non valido."
        )

    available_width = width - 2 * margin
    available_height = height - 2 * margin

    scale = min(
        available_width / model_width,
        available_height / model_height,
    )

    # Centriamo il disegno nella pagina.
    rendered_width = model_width * scale
    rendered_height = model_height * scale

    offset_x = (
        width - rendered_width
    ) / 2

    offset_y = (
        height - rendered_height
    ) / 2

    def transform(
        point: Point2D,
    ) -> Point2D:

        x, y = point

        sx = (
            offset_x
            + (x - xmin) * scale
        )

        # SVG ha asse Y verso il basso:
        # dobbiamo invertirlo.
        sy = (
            offset_y
            + (ymax - y) * scale
        )

        return sx, sy

    def polyline_svg(
        points: list[Point2D],
    ) -> str:

        transformed = [
            transform(p)
            for p in points
        ]

        data = " ".join(
            f"{x:.3f},{y:.3f}"
            for x, y in transformed
        )

        return (
            f'<polyline points="{data}" />'
        )

    visible_content = "\n".join(
        polyline_svg(line)
        for line in visible
    )

    hidden_content = "\n".join(
        polyline_svg(line)
        for line in hidden
    )

    title_svg = ""

    if title:
        title_svg = f"""
        <text
            x="{width / 2}"
            y="35"
            text-anchor="middle"
            font-family="Arial, sans-serif"
            font-size="20"
            fill="black"
        >{escape(title)}</text>
        """

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg
    xmlns="http://www.w3.org/2000/svg"
    width="{width}"
    height="{height}"
    viewBox="0 0 {width} {height}"
>

    <rect
        x="0"
        y="0"
        width="{width}"
        height="{height}"
        fill="white"
    />

    {title_svg}

    <!-- LINEE NASCOSTE -->
    <g
        fill="none"
        stroke="black"
        stroke-width="1.2"
        stroke-dasharray="8 5"
        stroke-linecap="butt"
        stroke-linejoin="round"
    >
        {hidden_content}
    </g>

    <!-- LINEE VISIBILI -->
    <g
        fill="none"
        stroke="black"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
    >
        {visible_content}
    </g>

</svg>
"""

    output_file.write_text(
        svg,
        encoding="utf-8",
    )

    print(
        f"SVG creato: {output_file}"
    )
