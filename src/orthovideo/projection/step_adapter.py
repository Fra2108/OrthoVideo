from orthovideo.drawing.svg_exporter import (
    shape_to_polylines,
)

from orthovideo.projection.hlr import (
    HLRResult,
)

from orthovideo.projection.result2d import (
    Projection2D,
)


def hlr_to_projection2d(
    result: HLRResult,
    *,
    deflection: float = 0.03,
) -> Projection2D:
    """
    Converte il risultato HLR esatto di OpenCascade
    nel formato 2D comune di OrthoVideo.
    """

    visible = shape_to_polylines(
        result.visible,
        deflection=deflection,
    )

    hidden = shape_to_polylines(
        result.hidden,
        deflection=deflection,
    )

    tangent = shape_to_polylines(
        result.tangent_visible,
        deflection=deflection,
    )

    return Projection2D(
        visible=visible,
        hidden=hidden,
        tangent=tangent,
    )
