from pathlib import Path

from orthovideo.drawing.sheet_layout import FirstAngleLayout
from orthovideo.drawing.technical_styles import (
    DEFAULT_TECHNICAL_STYLE_PRESET,
    LineRole,
    TechnicalStylePreset,
)


def _pair(code: int, value) -> str:
    return f"{code}\n{value}\n"


def _linetype_record(
    name: str,
    description: str,
    dash_pattern_mm: tuple[float, ...],
) -> list[str]:
    """Create a complete R2000 LTYPE symbol-table record."""

    content = [
        _pair(0, "LTYPE"),
        _pair(100, "AcDbSymbolTableRecord"),
        _pair(100, "AcDbLinetypeTableRecord"),
        _pair(2, name),
        _pair(70, 0),
        _pair(3, description),
        _pair(72, 65),
        _pair(73, len(dash_pattern_mm)),
        _pair(40, f"{sum(dash_pattern_mm):.6f}"),
    ]

    for index, length in enumerate(dash_pattern_mm):
        # DXF uses positive values for drawn elements and negative values for
        # gaps. TechnicalStylePreset stores the portable positive-only form.
        signed_length = length if index % 2 == 0 else -length
        content.extend(
            [
                _pair(49, f"{signed_length:.6f}"),
                _pair(74, 0),
            ]
        )

    return content


def _linetype_definitions(
    style_preset: TechnicalStylePreset,
) -> list[tuple[str, str, tuple[float, ...]]]:
    definitions = [
        ("BYBLOCK", "ByBlock", ()),
        ("BYLAYER", "ByLayer", ()),
        ("CONTINUOUS", "Solid line", ()),
    ]
    known = {name for name, _, _ in definitions}

    for role in style_preset.draw_order:
        style = style_preset.style_for(role)

        if style.dxf_linetype in known:
            continue

        definitions.append(
            (
                style.dxf_linetype,
                f"OrthoVideo {style.dxf_linetype}",
                style.dash_pattern_mm,
            )
        )
        known.add(style.dxf_linetype)

    return definitions


def export_layout_dxf(
    layout: FirstAngleLayout,
    output_file: str | Path,
    *,
    style_preset: TechnicalStylePreset = DEFAULT_TECHNICAL_STYLE_PRESET,
) -> Path:
    """Write an ASCII R2000 DXF with real linetypes and lineweights."""

    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    linetypes = _linetype_definitions(style_preset)
    layer_count = len(LineRole) + 1  # technical roles plus LABEL

    content = [
        _pair(0, "SECTION"),
        _pair(2, "HEADER"),
        _pair(9, "$ACADVER"),
        _pair(1, "AC1015"),
        _pair(9, "$INSUNITS"),
        _pair(70, 4),
        _pair(9, "$LTSCALE"),
        _pair(40, "1.000000"),
        _pair(9, "$CELTSCALE"),
        _pair(40, "1.000000"),
        _pair(0, "ENDSEC"),
        _pair(0, "SECTION"),
        _pair(2, "TABLES"),
        _pair(0, "TABLE"),
        _pair(100, "AcDbSymbolTable"),
        _pair(2, "LTYPE"),
        _pair(70, len(linetypes)),
    ]

    for name, description, pattern in linetypes:
        content.extend(_linetype_record(name, description, pattern))

    content.extend(
        [
            _pair(0, "ENDTAB"),
            _pair(0, "TABLE"),
            _pair(100, "AcDbSymbolTable"),
            _pair(2, "LAYER"),
            _pair(70, layer_count),
        ]
    )

    for role in LineRole:
        style = style_preset.style_for(role)
        content.extend(
            [
                _pair(0, "LAYER"),
                _pair(100, "AcDbSymbolTableRecord"),
                _pair(100, "AcDbLayerTableRecord"),
                _pair(2, role.value),
                _pair(70, 0),
                _pair(62, style.dxf_color),
                _pair(6, style.dxf_linetype),
                _pair(370, style.dxf_lineweight),
            ]
        )

    content.extend(
        [
            _pair(0, "LAYER"),
            _pair(100, "AcDbSymbolTableRecord"),
            _pair(100, "AcDbLayerTableRecord"),
            _pair(2, "LABEL"),
            _pair(70, 0),
            _pair(62, 8),
            _pair(6, "CONTINUOUS"),
            _pair(370, 18),
            _pair(0, "ENDTAB"),
            _pair(0, "ENDSEC"),
            _pair(0, "SECTION"),
            _pair(2, "ENTITIES"),
        ]
    )

    for polyline in layout.polylines:
        if len(polyline.points) < 2:
            continue

        role = polyline.role
        style = style_preset.style_for(role)
        content.extend(
            [
                _pair(0, "LWPOLYLINE"),
                _pair(100, "AcDbEntity"),
                _pair(8, role.value),
                _pair(6, style.dxf_linetype),
                _pair(370, style.dxf_lineweight),
                _pair(100, "AcDbPolyline"),
                _pair(90, len(polyline.points)),
                _pair(70, 0),
            ]
        )

        for x, y_top_down in polyline.points:
            content.extend(
                [
                    _pair(10, f"{x:.6f}"),
                    _pair(20, f"{layout.page_height - y_top_down:.6f}"),
                ]
            )

    for label in layout.labels:
        x, y_top_down = label.position
        content.extend(
            [
                _pair(0, "TEXT"),
                _pair(100, "AcDbEntity"),
                _pair(8, "LABEL"),
                _pair(6, "CONTINUOUS"),
                _pair(370, 18),
                _pair(100, "AcDbText"),
                _pair(10, f"{x:.6f}"),
                _pair(20, f"{layout.page_height - y_top_down:.6f}"),
                _pair(40, "4.000000"),
                _pair(1, label.text),
                _pair(72, 1),
                _pair(11, f"{x:.6f}"),
                _pair(21, f"{layout.page_height - y_top_down:.6f}"),
            ]
        )

    content.extend([_pair(0, "ENDSEC"), _pair(0, "EOF")])
    output_file.write_text("".join(content), encoding="ascii")
    return output_file
