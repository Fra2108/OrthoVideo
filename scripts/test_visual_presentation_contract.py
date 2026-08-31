from pathlib import Path

from orthovideo.drawing.technical_sheet import choose_iso_scale
from orthovideo.drawing.technical_styles import (
    DEFAULT_TECHNICAL_STYLE_PRESET,
    LineRole,
    ORTHOGRAPHIC_LIGHT_STYLE_PRESET,
)
from orthovideo.projection.result2d import Projection2D


ROOT = Path(__file__).resolve().parents[1]


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


def main():
    component_like = {
        name: rectangle(165.3, 98.25)
        for name in ("front", "rear", "right", "left")
    }
    component_like.update(
        {
            "top": rectangle(165.3, 165.24),
            "bottom": rectangle(165.3, 165.24),
        }
    )
    scale = choose_iso_scale(
        component_like,
        page_width=420.0,
        page_height=297.0,
        margin=15.0,
        gap=20.0,
    )
    assert scale == 0.4

    light = ORTHOGRAPHIC_LIGHT_STYLE_PRESET
    section = DEFAULT_TECHNICAL_STYLE_PRESET
    assert light.style_for(LineRole.VISIBLE).width_mm == 0.25
    assert light.style_for(LineRole.CENTER).width_mm == 0.13
    assert light.style_for(LineRole.VISIBLE).pdf_color_rgb == (0.14, 0.14, 0.13)
    assert light.pdf_background_rgb == (230.0 / 255.0, 230.0 / 255.0, 218.0 / 255.0)
    assert light.style_for(LineRole.VISIBLE).width_mm < section.style_for(
        LineRole.VISIBLE
    ).width_mm

    blender_script = (
        ROOT / "blender" / "render_projection_animation.py"
    ).read_text(encoding="utf-8")
    for contract in (
        "technical_contrast_v2",
        "ShaderNodeAmbientOcclusion",
        '"Rim Light"',
        'scene.view_settings.look = "AgX - Medium High Contrast"',
    ):
        assert contract in blender_script

    print("VISUAL_PRESENTATION_CONTRACT_OK")


if __name__ == "__main__":
    main()
