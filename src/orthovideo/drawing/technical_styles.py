from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping


class LineRole(StrEnum):
    """Semantic roles used by every technical drawing exporter."""

    VISIBLE = "VISIBLE"
    HIDDEN = "HIDDEN"
    CENTER = "CENTER"
    SYMMETRY = "SYMMETRY"
    PITCH = "PITCH"
    SECTION_CUT = "SECTION_CUT"
    HATCH = "HATCH"
    TANGENT = "TANGENT"


@dataclass(frozen=True)
class TechnicalLineStyle:
    """Physical line style shared by SVG, PDF and DXF.

    Widths and dash lengths are expressed in paper millimetres.  Positive DXF
    pattern elements are drawn, while the exporter changes gaps to negative
    elements as required by the DXF LTYPE format.
    """

    width_mm: float
    dash_pattern_mm: tuple[float, ...]
    dxf_linetype: str
    dxf_color: int
    line_cap: str = "butt"
    line_join: str = "round"
    pdf_color_rgb: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        if self.width_mm <= 0:
            raise ValueError("Technical line width must be positive.")

        if any(element <= 0 for element in self.dash_pattern_mm):
            raise ValueError("Dash-pattern elements must be positive.")

        if len(self.dash_pattern_mm) % 2:
            raise ValueError("Dash patterns must alternate draw and gap lengths.")

        if not self.dxf_linetype:
            raise ValueError("DXF linetype name cannot be empty.")

        if not 1 <= self.dxf_color <= 255:
            raise ValueError("DXF ACI color must be in the 1..255 range.")

        if self.line_cap not in {"butt", "round", "square"}:
            raise ValueError(f"Unsupported line cap: {self.line_cap}")

        if self.line_join not in {"miter", "round", "bevel"}:
            raise ValueError(f"Unsupported line join: {self.line_join}")

        if len(self.pdf_color_rgb) != 3 or any(
            not 0.0 <= channel <= 1.0 for channel in self.pdf_color_rgb
        ):
            raise ValueError("PDF RGB channels must be in the 0..1 range.")

    @property
    def dxf_lineweight(self) -> int:
        """DXF group-code 370 value in hundredths of a millimetre."""

        return round(self.width_mm * 100.0)


@dataclass(frozen=True)
class TechnicalStylePreset:
    """Complete, validated set of semantic technical line styles."""

    name: str
    styles: Mapping[LineRole, TechnicalLineStyle]
    draw_order: tuple[LineRole, ...]
    pdf_background_rgb: tuple[float, float, float] = (1.0, 1.0, 1.0)

    def __post_init__(self) -> None:
        normalized = {
            coerce_line_role(role): style
            for role, style in self.styles.items()
        }
        expected = set(LineRole)

        if set(normalized) != expected:
            missing = sorted(role.value for role in expected - set(normalized))
            extra = sorted(str(role) for role in set(normalized) - expected)
            raise ValueError(
                "Technical style preset must define every line role; "
                f"missing={missing}, extra={extra}."
            )

        normalized_order = tuple(coerce_line_role(role) for role in self.draw_order)

        if len(normalized_order) != len(expected) or set(normalized_order) != expected:
            raise ValueError("draw_order must contain every line role exactly once.")

        linetypes: dict[str, tuple[float, ...]] = {}

        for style in normalized.values():
            previous = linetypes.setdefault(style.dxf_linetype, style.dash_pattern_mm)

            if previous != style.dash_pattern_mm:
                raise ValueError(
                    f"DXF linetype {style.dxf_linetype!r} has conflicting patterns."
                )

        object.__setattr__(self, "styles", MappingProxyType(normalized))
        object.__setattr__(self, "draw_order", normalized_order)
        if len(self.pdf_background_rgb) != 3 or any(
            not 0.0 <= channel <= 1.0 for channel in self.pdf_background_rgb
        ):
            raise ValueError("PDF background RGB channels must be in the 0..1 range.")

    def style_for(self, role: LineRole | str) -> TechnicalLineStyle:
        return self.styles[coerce_line_role(role)]


def coerce_line_role(value: LineRole | str) -> LineRole:
    """Normalize legacy string layer names to a known semantic role."""

    if isinstance(value, LineRole):
        return value

    try:
        return LineRole(str(value).strip().upper())
    except ValueError as exc:
        supported = ", ".join(role.value for role in LineRole)
        raise ValueError(
            f"Unknown technical line role {value!r}; supported roles: {supported}."
        ) from exc


DEFAULT_TECHNICAL_STYLE_PRESET = TechnicalStylePreset(
    name="ISO_MONOCHROME",
    styles={
        LineRole.VISIBLE: TechnicalLineStyle(
            width_mm=0.35,
            dash_pattern_mm=(),
            dxf_linetype="CONTINUOUS",
            dxf_color=7,
            line_cap="round",
        ),
        LineRole.HIDDEN: TechnicalLineStyle(
            width_mm=0.18,
            dash_pattern_mm=(3.5, 2.0),
            dxf_linetype="DASHED",
            dxf_color=8,
        ),
        LineRole.CENTER: TechnicalLineStyle(
            width_mm=0.18,
            dash_pattern_mm=(8.0, 2.0, 1.5, 2.0),
            dxf_linetype="CENTER",
            dxf_color=4,
        ),
        LineRole.SYMMETRY: TechnicalLineStyle(
            width_mm=0.18,
            dash_pattern_mm=(8.0, 2.0, 1.5, 2.0),
            dxf_linetype="CENTER",
            dxf_color=4,
        ),
        LineRole.PITCH: TechnicalLineStyle(
            width_mm=0.18,
            dash_pattern_mm=(8.0, 2.0, 1.5, 2.0),
            dxf_linetype="CENTER",
            dxf_color=4,
        ),
        LineRole.SECTION_CUT: TechnicalLineStyle(
            width_mm=0.70,
            dash_pattern_mm=(),
            dxf_linetype="CONTINUOUS",
            dxf_color=1,
            line_cap="round",
        ),
        LineRole.HATCH: TechnicalLineStyle(
            width_mm=0.18,
            dash_pattern_mm=(),
            dxf_linetype="CONTINUOUS",
            dxf_color=8,
        ),
        LineRole.TANGENT: TechnicalLineStyle(
            width_mm=0.18,
            dash_pattern_mm=(),
            dxf_linetype="CONTINUOUS",
            dxf_color=8,
        ),
    },
    draw_order=(
        LineRole.HATCH,
        LineRole.TANGENT,
        LineRole.CENTER,
        LineRole.SYMMETRY,
        LineRole.PITCH,
        LineRole.HIDDEN,
        LineRole.VISIBLE,
        LineRole.SECTION_CUT,
    ),
)


# Page-one preset: the six-view sheet contains many overlapping details and is
# normally printed at a reduction scale.  These ISO lineweights keep it light
# and readable, while the separate section page retains the stronger default
# hierarchy above.
ORTHOGRAPHIC_LIGHT_STYLE_PRESET = TechnicalStylePreset(
    name="ISO_ORTHOGRAPHIC_LIGHT",
    styles={
        LineRole.VISIBLE: TechnicalLineStyle(
            width_mm=0.25,
            dash_pattern_mm=(),
            dxf_linetype="CONTINUOUS",
            dxf_color=7,
            line_cap="round",
            pdf_color_rgb=(0.14, 0.14, 0.13),
        ),
        LineRole.HIDDEN: TechnicalLineStyle(
            width_mm=0.13,
            dash_pattern_mm=(3.5, 2.0),
            dxf_linetype="DASHED",
            dxf_color=8,
            pdf_color_rgb=(0.35, 0.35, 0.32),
        ),
        LineRole.CENTER: TechnicalLineStyle(
            width_mm=0.13,
            dash_pattern_mm=(8.0, 2.0, 1.5, 2.0),
            dxf_linetype="CENTER",
            dxf_color=4,
            pdf_color_rgb=(0.30, 0.30, 0.28),
        ),
        LineRole.SYMMETRY: TechnicalLineStyle(
            width_mm=0.13,
            dash_pattern_mm=(8.0, 2.0, 1.5, 2.0),
            dxf_linetype="CENTER",
            dxf_color=4,
            pdf_color_rgb=(0.30, 0.30, 0.28),
        ),
        LineRole.PITCH: TechnicalLineStyle(
            width_mm=0.13,
            dash_pattern_mm=(8.0, 2.0, 1.5, 2.0),
            dxf_linetype="CENTER",
            dxf_color=4,
            pdf_color_rgb=(0.30, 0.30, 0.28),
        ),
        LineRole.SECTION_CUT: TechnicalLineStyle(
            width_mm=0.40,
            dash_pattern_mm=(),
            dxf_linetype="CONTINUOUS",
            dxf_color=1,
            line_cap="round",
            pdf_color_rgb=(0.20, 0.20, 0.18),
        ),
        LineRole.HATCH: TechnicalLineStyle(
            width_mm=0.13,
            dash_pattern_mm=(),
            dxf_linetype="CONTINUOUS",
            dxf_color=8,
            pdf_color_rgb=(0.30, 0.30, 0.28),
        ),
        LineRole.TANGENT: TechnicalLineStyle(
            width_mm=0.13,
            dash_pattern_mm=(),
            dxf_linetype="CONTINUOUS",
            dxf_color=8,
            pdf_color_rgb=(0.35, 0.35, 0.32),
        ),
    },
    draw_order=DEFAULT_TECHNICAL_STYLE_PRESET.draw_order,
    pdf_background_rgb=(230.0 / 255.0, 230.0 / 255.0, 218.0 / 255.0),
)


# Short alias for callers that do not need to name the preset explicitly.
DEFAULT_TECHNICAL_STYLES = DEFAULT_TECHNICAL_STYLE_PRESET
