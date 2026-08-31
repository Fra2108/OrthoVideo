from math import isclose
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from xml.etree import ElementTree

from reportlab.lib.units import mm

from orthovideo.drawing.dxf_exporter import export_layout_dxf
from orthovideo.drawing.pdf_exporter import export_layout_pdf, export_layouts_pdf
from orthovideo.drawing.sheet_layout import (
    FirstAngleLayout,
    SheetLabel,
    SheetPolyline,
)
from orthovideo.drawing.svg_exporter import export_layout_svg
from orthovideo.drawing.technical_sheet import export_first_angle_sheet
from orthovideo.drawing.technical_styles import (
    DEFAULT_TECHNICAL_STYLE_PRESET,
    LineRole,
    ORTHOGRAPHIC_LIGHT_STYLE_PRESET,
)
from orthovideo.projection.result2d import Projection2D


def make_layout(roles=tuple(LineRole)) -> FirstAngleLayout:
    return FirstAngleLayout(
        page_width=100.0,
        page_height=80.0,
        drawing_scale=1.0,
        placements={},
        polylines=[
            SheetPolyline(
                view="front",
                layer=role,
                points=[(10.0, 10.0 + index * 5.0), (40.0, 10.0 + index * 5.0)],
            )
            for index, role in enumerate(roles)
        ],
        labels=[SheetLabel(text="FRONT", position=(50.0, 75.0))],
    )


def rectangle(width: float, height: float) -> Projection2D:
    return Projection2D(
        visible=[
            [(0.0, 0.0), (width, 0.0)],
            [(width, 0.0), (width, height)],
            [(width, height), (0.0, height)],
            [(0.0, height), (0.0, 0.0)],
        ],
        hidden=[],
    )


def split_dxf_records(text: str):
    lines = text.splitlines()
    assert len(lines) % 2 == 0
    pairs = list(zip(lines[::2], lines[1::2]))
    records = []
    current = []

    for pair in pairs:
        if pair[0] == "0":
            if current:
                records.append(current)
            current = [pair]
        else:
            current.append(pair)

    if current:
        records.append(current)

    return pairs, records


def values(record, code: int):
    return [value for item_code, value in record if item_code == str(code)]


class RecordingPath:
    def __init__(self):
        self.points = []

    def moveTo(self, x, y):
        self.points.append(("M", x, y))

    def lineTo(self, x, y):
        self.points.append(("L", x, y))


class RecordingCanvas:
    def __init__(self, *args, **kwargs):
        self.width = None
        self.dash = None
        self.cap = None
        self.join = None
        self.draws = []

    def setTitle(self, value):
        pass

    def setAuthor(self, value):
        pass

    def setStrokeColorRGB(self, *value):
        pass

    def setLineCap(self, value):
        self.cap = value

    def setLineJoin(self, value):
        self.join = value

    def setLineWidth(self, value):
        self.width = value

    def setDash(self, value):
        self.dash = tuple(value)

    def beginPath(self):
        return RecordingPath()

    def drawPath(self, path, **kwargs):
        self.draws.append((self.width, self.dash, self.cap, self.join, path.points))

    def setFillColorRGB(self, *value):
        pass

    def rect(self, *args, **kwargs):
        pass

    def setFont(self, *value):
        pass

    def drawCentredString(self, *value):
        pass

    def drawString(self, *value):
        pass

    def drawRightString(self, *value):
        pass

    def showPage(self):
        pass

    def save(self):
        pass


def assert_style_invariants():
    preset = DEFAULT_TECHNICAL_STYLE_PRESET
    assert set(preset.styles) == set(LineRole)
    assert len(preset.draw_order) == len(LineRole)
    assert preset.style_for(LineRole.VISIBLE).width_mm > preset.style_for(LineRole.HIDDEN).width_mm
    assert preset.style_for(LineRole.SECTION_CUT).width_mm > preset.style_for(LineRole.VISIBLE).width_mm
    assert preset.style_for(LineRole.HIDDEN).dash_pattern_mm == (3.5, 2.0)

    center_pattern = (8.0, 2.0, 1.5, 2.0)

    for role in (LineRole.CENTER, LineRole.SYMMETRY, LineRole.PITCH):
        assert preset.style_for(role).dash_pattern_mm == center_pattern

    for role in (LineRole.VISIBLE, LineRole.SECTION_CUT, LineRole.HATCH, LineRole.TANGENT):
        assert preset.style_for(role).dash_pattern_mm == ()

    light = ORTHOGRAPHIC_LIGHT_STYLE_PRESET
    assert light.style_for(LineRole.VISIBLE).width_mm == 0.25
    assert light.style_for(LineRole.CENTER).width_mm == 0.13
    assert light.style_for(LineRole.SECTION_CUT).width_mm == 0.40
    assert light.style_for(LineRole.VISIBLE).width_mm < preset.style_for(
        LineRole.VISIBLE
    ).width_mm


def assert_svg(path: Path, *, expect_every_role_to_have_geometry: bool):
    preset = DEFAULT_TECHNICAL_STYLE_PRESET
    root = ElementTree.parse(path).getroot()
    namespace = {"svg": "http://www.w3.org/2000/svg"}

    for role in LineRole:
        group = root.find(f".//svg:g[@data-role='{role.value}']", namespace)
        assert group is not None, role
        style = preset.style_for(role)
        assert isclose(float(group.attrib["stroke-width"]), style.width_mm)
        actual_dash = tuple(float(value) for value in group.attrib.get("stroke-dasharray", "").split())
        assert actual_dash == style.dash_pattern_mm
        children = group.findall("svg:polyline", namespace)

        if expect_every_role_to_have_geometry:
            assert len(children) == 1, role


def assert_dxf(path: Path, *, expected_entity_roles: set[LineRole]):
    preset = DEFAULT_TECHNICAL_STYLE_PRESET
    pairs, records = split_dxf_records(path.read_text(encoding="ascii"))
    assert ("9", "$LTSCALE") in pairs
    assert ("9", "$CELTSCALE") in pairs

    linetypes = {
        values(record, 2)[0]: record
        for record in records
        if record[0] == ("0", "LTYPE")
    }
    assert {"BYBLOCK", "BYLAYER", "CONTINUOUS", "DASHED", "CENTER"} <= set(linetypes)
    assert values(linetypes["DASHED"], 49) == ["3.500000", "-2.000000"]
    assert values(linetypes["CENTER"], 49) == [
        "8.000000",
        "-2.000000",
        "1.500000",
        "-2.000000",
    ]
    assert values(linetypes["DASHED"], 73) == ["2"]
    assert values(linetypes["CENTER"], 73) == ["4"]

    layers = {
        values(record, 2)[0]: record
        for record in records
        if record[0] == ("0", "LAYER")
    }
    assert {role.value for role in LineRole} <= set(layers)

    for role in LineRole:
        style = preset.style_for(role)
        assert values(layers[role.value], 6) == [style.dxf_linetype]
        assert values(layers[role.value], 370) == [str(style.dxf_lineweight)]

    entities = {
        values(record, 8)[0]: record
        for record in records
        if record[0] == ("0", "LWPOLYLINE")
    }
    assert set(entities) == {role.value for role in expected_entity_roles}

    for role in expected_entity_roles:
        style = preset.style_for(role)
        assert values(entities[role.value], 6) == [style.dxf_linetype]
        assert values(entities[role.value], 370) == [str(style.dxf_lineweight)]


def assert_pdf_dispatch(layout: FirstAngleLayout, output_file: Path):
    preset = DEFAULT_TECHNICAL_STYLE_PRESET
    canvases = []

    def factory(*args, **kwargs):
        canvas = RecordingCanvas(*args, **kwargs)
        canvases.append(canvas)
        return canvas

    with patch("orthovideo.drawing.pdf_exporter.Canvas", side_effect=factory):
        export_layout_pdf(layout, output_file)

    assert len(canvases) == 1
    draws = canvases[0].draws
    assert len(draws) == len(LineRole)

    for role, draw in zip(preset.draw_order, draws):
        width, dash, cap, join, points = draw
        style = preset.style_for(role)
        assert isclose(width, style.width_mm * mm)
        assert len(dash) == len(style.dash_pattern_mm)
        assert all(
            isclose(actual, expected * mm)
            for actual, expected in zip(dash, style.dash_pattern_mm)
        )
        assert cap == {"butt": 0, "round": 1, "square": 2}[style.line_cap]
        assert join == {"miter": 0, "round": 1, "bevel": 2}[style.line_join]
        assert len(points) == 2


def assert_multipage_pdf_styles(layout: FirstAngleLayout, output_file: Path):
    canvases = []

    def factory(*args, **kwargs):
        canvas = RecordingCanvas(*args, **kwargs)
        canvases.append(canvas)
        return canvas

    presets = [ORTHOGRAPHIC_LIGHT_STYLE_PRESET, DEFAULT_TECHNICAL_STYLE_PRESET]

    with patch("orthovideo.drawing.pdf_exporter.Canvas", side_effect=factory):
        export_layouts_pdf(
            [layout, layout],
            output_file,
            style_presets=presets,
        )

    draws = canvases[0].draws
    role_count = len(LineRole)
    assert len(draws) == role_count * 2

    for page_index, preset in enumerate(presets):
        page_draws = draws[page_index * role_count : (page_index + 1) * role_count]
        for role, draw in zip(preset.draw_order, page_draws):
            assert isclose(draw[0], preset.style_for(role).width_mm * mm)


def main():
    assert_style_invariants()
    complete_layout = make_layout()
    legacy_roles = (LineRole.VISIBLE, LineRole.HIDDEN, LineRole.CENTER)
    legacy_layout = make_layout(legacy_roles)

    with TemporaryDirectory(prefix="orthovideo_styles_") as temporary:
        output = Path(temporary)
        complete_svg = export_layout_svg(complete_layout, output / "complete.svg")
        complete_dxf = export_layout_dxf(complete_layout, output / "complete.dxf")
        actual_pdf = export_layout_pdf(complete_layout, output / "complete.pdf")
        legacy_svg = export_layout_svg(legacy_layout, output / "legacy.svg")
        legacy_dxf = export_layout_dxf(legacy_layout, output / "legacy.dxf")
        compatibility_svg = export_first_angle_sheet(
            {
                "front": rectangle(40.0, 30.0),
                "rear": rectangle(40.0, 30.0),
                "top": rectangle(40.0, 20.0),
                "bottom": rectangle(40.0, 20.0),
                "right": rectangle(20.0, 30.0),
                "left": rectangle(20.0, 30.0),
            },
            output / "compatibility.svg",
        )

        assert_svg(complete_svg, expect_every_role_to_have_geometry=True)
        assert_dxf(complete_dxf, expected_entity_roles=set(LineRole))
        assert actual_pdf.read_bytes().startswith(b"%PDF-")
        assert_svg(legacy_svg, expect_every_role_to_have_geometry=False)
        assert_dxf(legacy_dxf, expected_entity_roles=set(legacy_roles))
        assert_svg(compatibility_svg, expect_every_role_to_have_geometry=False)
        assert_pdf_dispatch(complete_layout, output / "recorded.pdf")
        assert_multipage_pdf_styles(
            complete_layout,
            output / "recorded_multipage.pdf",
        )

    print("TECHNICAL_STYLES_OK")


if __name__ == "__main__":
    main()
