from pathlib import Path

from orthovideo.drawing.dxf_exporter import export_layout_dxf
from orthovideo.drawing.pdf_exporter import export_layout_pdf
from orthovideo.drawing.sheet_layout import build_first_angle_layout
from orthovideo.drawing.technical_sheet import choose_iso_scale
from orthovideo.projection.result2d import Projection2D


ROOT = Path(__file__).resolve().parents[1]


def rectangle(width, height):
    return Projection2D(
        visible=[
            [(0.0, 0.0), (width, 0.0)],
            [(width, 0.0), (width, height)],
            [(width, height), (0.0, height)],
            [(0.0, height), (0.0, 0.0)],
        ],
        hidden=[],
    )


def main():
    projections = {
        "front": rectangle(40.0, 30.0),
        "rear": rectangle(40.0, 30.0),
        "top": rectangle(40.0, 20.0),
        "bottom": rectangle(40.0, 20.0),
        "right": rectangle(20.0, 30.0),
        "left": rectangle(20.0, 30.0),
    }
    layout = build_first_angle_layout(
        projections,
        page_width=420.0,
        page_height=297.0,
        margin=15.0,
        gap=20.0,
    )
    positions = {name: item.origin for name, item in layout.placements.items()}
    assert positions["right"][0] < positions["front"][0]
    assert positions["front"][0] < positions["left"][0] < positions["rear"][0]
    assert positions["bottom"][1] < positions["front"][1] < positions["top"][1]

    component_like = {
        "front": rectangle(165.3, 98.25),
        "rear": rectangle(165.3, 98.25),
        "top": rectangle(165.3, 165.24),
        "bottom": rectangle(165.3, 165.24),
        "right": rectangle(165.3, 98.25),
        "left": rectangle(165.3, 98.25),
    }
    assert choose_iso_scale(
        component_like,
        page_width=420.0,
        page_height=297.0,
        margin=15.0,
        gap=20.0,
    ) == 0.4

    output = ROOT / "output" / "tests" / "sheet_exports"
    pdf = export_layout_pdf(layout, output / "sheet.pdf")
    dxf = export_layout_dxf(layout, output / "sheet.dxf")
    assert pdf.read_bytes().startswith(b"%PDF-")
    dxf_text = dxf.read_text(encoding="ascii")
    assert "VISIBLE" in dxf_text and "HIDDEN" in dxf_text and "CENTER" in dxf_text
    print("SHEET_EXPORTS_OK")


if __name__ == "__main__":
    main()
