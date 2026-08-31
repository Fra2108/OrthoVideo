from pathlib import Path

from orthovideo.projection.mesh_projection import (
    MeshProjectedEdge,
)


def export_mesh_view_svg(
    edges: list[MeshProjectedEdge],
    output_file: str | Path,
    *,
    width: int = 1000,
    height: int = 700,
    margin: int = 80,
    title: str = "",
):

    output_file = Path(
        output_file
    )

    if not edges:
        raise RuntimeError(
            "Nessun edge da esportare."
        )

    points = []

    for edge in edges:

        points.append(
            edge.start_2d
        )

        points.append(
            edge.end_2d
        )

    xmin = min(
        p[0]
        for p in points
    )

    xmax = max(
        p[0]
        for p in points
    )

    ymin = min(
        p[1]
        for p in points
    )

    ymax = max(
        p[1]
        for p in points
    )

    geometry_width = (
        xmax - xmin
    )

    geometry_height = (
        ymax - ymin
    )

    if (
        geometry_width <= 0
        or geometry_height <= 0
    ):
        raise RuntimeError(
            "Bounding box 2D non valido."
        )

    scale = min(
        (
            width
            - 2 * margin
        )
        / geometry_width,

        (
            height
            - 2 * margin
        )
        / geometry_height,
    )

    rendered_width = (
        geometry_width
        * scale
    )

    rendered_height = (
        geometry_height
        * scale
    )

    offset_x = (
        width
        - rendered_width
    ) / 2.0

    offset_y = (
        height
        - rendered_height
    ) / 2.0

    def transform(point):

        x, y = point

        return (
            offset_x
            + (x - xmin) * scale,

            offset_y
            + (ymax - y) * scale,
        )

    lines = []

    for edge in edges:

        x1, y1 = transform(
            edge.start_2d
        )

        x2, y2 = transform(
            edge.end_2d
        )

        lines.append(
            f"""
            <line
                x1="{x1:.4f}"
                y1="{y1:.4f}"
                x2="{x2:.4f}"
                y2="{y2:.4f}"
            />
            """
        )

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

    <text
        x="{width / 2}"
        y="40"
        text-anchor="middle"
        font-family="Arial, sans-serif"
        font-size="20"
    >
        {title}
    </text>

    <g
        fill="none"
        stroke="black"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
    >
        {"".join(lines)}
    </g>

</svg>
"""

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file.write_text(
        svg,
        encoding="utf-8",
    )

    print(
        f"SVG OBJ creato: {output_file}"
    )


from orthovideo.projection.mesh_visibility import (
    MeshVisibilityResult,
)

def export_mesh_visibility_svg(
    result: MeshVisibilityResult,
    output_file: str | Path,
    *,
    width: int = 1000,
    height: int = 700,
    margin: int = 80,
    title: str = "",
):

    output_file = Path(
        output_file
    )

    all_segments = (
        result.visible
        + result.hidden
    )

    if not all_segments:

        raise RuntimeError(
            "Nessun segmento da esportare."
        )

    points = []

    for segment in all_segments:

        points.append(
            segment.start
        )

        points.append(
            segment.end
        )

    xmin = min(
        p[0]
        for p in points
    )

    xmax = max(
        p[0]
        for p in points
    )

    ymin = min(
        p[1]
        for p in points
    )

    ymax = max(
        p[1]
        for p in points
    )

    geometry_width = (
        xmax - xmin
    )

    geometry_height = (
        ymax - ymin
    )

    if (
        geometry_width <= 0
        or geometry_height <= 0
    ):
        raise RuntimeError(
            "Bounding box 2D non valido."
        )

    scale = min(
        (
            width - 2 * margin
        )
        / geometry_width,

        (
            height - 2 * margin
        )
        / geometry_height,
    )

    rendered_width = (
        geometry_width
        * scale
    )

    rendered_height = (
        geometry_height
        * scale
    )

    offset_x = (
        width - rendered_width
    ) / 2.0

    offset_y = (
        height - rendered_height
    ) / 2.0

    def transform(point):

        x, y = point

        return (
            offset_x
            + (x - xmin) * scale,

            offset_y
            + (ymax - y) * scale,
        )

    def make_line(segment):

        x1, y1 = transform(
            segment.start
        )

        x2, y2 = transform(
            segment.end
        )

        return (
            f'<line '
            f'x1="{x1:.4f}" '
            f'y1="{y1:.4f}" '
            f'x2="{x2:.4f}" '
            f'y2="{y2:.4f}" />'
        )

    hidden_svg = "\n".join(
        make_line(segment)
        for segment in result.hidden
    )

    visible_svg = "\n".join(
        make_line(segment)
        for segment in result.visible
    )

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

    <text
        x="{width / 2}"
        y="40"
        text-anchor="middle"
        font-family="Arial, sans-serif"
        font-size="20"
    >
        {title}
    </text>

    <!-- HIDDEN -->
    <g
        fill="none"
        stroke="black"
        stroke-width="1.2"
        stroke-dasharray="8 5"
        stroke-linecap="butt"
    >
        {hidden_svg}
    </g>

    <!-- VISIBLE -->
    <g
        fill="none"
        stroke="black"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
    >
        {visible_svg}
    </g>

</svg>
"""

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file.write_text(
        svg,
        encoding="utf-8",
    )

    print(
        f"SVG OBJ HLR creato: {output_file}"
    )