from pathlib import Path

from orthovideo.io.obj_loader import (
    load_obj,
)

from orthovideo.projection.view_system import (
    build_six_views,
)

from orthovideo.projection.mesh_projection import (
    project_mesh_edges,
)

from orthovideo.drawing.mesh_svg import (
    export_mesh_view_svg,
)


ROOT = Path(__file__).resolve().parents[1]

MODEL = (
    ROOT
    / "models"
    / "test_mesh.obj"
)

OUTPUT = (
    ROOT
    / "output"
    / "obj_front.svg"
)


def main():

    mesh = load_obj(
        MODEL
    )

    views = build_six_views(
        main_normal=(
            0.0,
            -1.0,
            0.0,
        ),
        main_up=(
            0.0,
            0.0,
            1.0,
        ),
    )

    edges = project_mesh_edges(
        mesh,
        views["front"],

        feature_angle_deg=30.0,
    )

    export_mesh_view_svg(
        edges,
        OUTPUT,
        title="OBJ FRONT VIEW",
    )


if __name__ == "__main__":
    main()