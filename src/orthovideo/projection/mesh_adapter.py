from orthovideo.projection.mesh_visibility import (
    MeshVisibilityResult,
)

from orthovideo.projection.result2d import (
    Projection2D,
)


def mesh_visibility_to_projection2d(
    result: MeshVisibilityResult,
) -> Projection2D:
    """
    Converte il risultato del motore di visibilità OBJ
    nel formato 2D comune di OrthoVideo.
    """

    visible = [
        [
            segment.start,
            segment.end,
        ]
        for segment in result.visible
    ]

    hidden = [
        [
            segment.start,
            segment.end,
        ]
        for segment in result.hidden
    ]

    return Projection2D(
        visible=visible,
        hidden=hidden,
    )