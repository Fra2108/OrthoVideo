from orthovideo.drawing.sheet_layout import build_sectioned_first_angle_layout
from orthovideo.drawing.technical_sheet import choose_sectioned_fit_scale
from orthovideo.projection.result2d import Projection2D


def rectangle(xmin, ymin, xmax, ymax):
    return Projection2D(
        visible=[
            [(xmin, ymin), (xmax, ymin)],
            [(xmax, ymin), (xmax, ymax)],
            [(xmax, ymax), (xmin, ymax)],
            [(xmin, ymax), (xmin, ymin)],
        ],
        hidden=[],
    )


def main():
    projections = {
        "right": rectangle(-10.0, -20.0, 30.0, 20.0),
        "left": rectangle(-25.0, -20.0, 15.0, 20.0),
        "bottom": rectangle(-40.0, -40.0, 40.0, 40.0),
        "top": rectangle(-40.0, -40.0, 40.0, 40.0),
    }
    section = rectangle(-15.0, -20.0, 35.0, 20.0)
    scale = choose_sectioned_fit_scale(
        projections,
        section,
        page_width=420.0,
        page_height=297.0,
        margin=2.0,
        horizontal_gap=45.0,
        horizontal_gap_before=51.0,
        horizontal_gap_after=38.5,
        vertical_gap=12.0,
        vertical_gap_above=13.0,
        vertical_gap_below=17.0,
    )
    assert scale > 0.0

    layout = build_sectioned_first_angle_layout(
        projections,
        section,
        page_width=420.0,
        page_height=297.0,
        margin=2.0,
        horizontal_gap=45.0,
        horizontal_gap_before=51.0,
        horizontal_gap_after=38.5,
        central_axis_offset=3.5,
        vertical_gap=12.0,
        vertical_gap_above=13.0,
        vertical_gap_below=17.0,
        drawing_scale=scale,
    )

    def datum_x(name):
        placement = layout.placements[name]
        return placement.origin[0] - placement.bounds[0] * scale

    def datum_y(name):
        placement = layout.placements[name]
        return placement.origin[1] + placement.bounds[3] * scale

    for name in ("section_A-A", "bottom", "top"):
        assert abs(datum_x(name) - 213.5) < 1.0e-9
    row_y = datum_y("section_A-A")
    assert abs(datum_y("right") - row_y) < 1.0e-9
    assert abs(datum_y("left") - row_y) < 1.0e-9

    right = layout.placements["right"]
    section_placement = layout.placements["section_A-A"]
    left = layout.placements["left"]
    bottom = layout.placements["bottom"]
    top = layout.placements["top"]
    assert abs(section_placement.origin[0] - (right.origin[0] + right.width) - 51.0) < 1.0e-9
    assert abs(left.origin[0] - (section_placement.origin[0] + section_placement.width) - 38.5) < 1.0e-9
    assert abs(section_placement.origin[1] - (bottom.origin[1] + bottom.height) - 13.0) < 1.0e-9
    assert abs(top.origin[1] - (section_placement.origin[1] + section_placement.height) - 17.0) < 1.0e-9
    assert {label.text for label in layout.labels} == {"SEZIONE", "A-A"}
    assert set(layout.placements) == {"right", "left", "bottom", "top", "section_A-A"}
    print("SECTIONED_FIRST_ANGLE_LAYOUT_OK")


if __name__ == "__main__":
    main()
