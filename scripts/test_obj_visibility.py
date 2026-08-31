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

from orthovideo.projection.mesh_visibility import (
    resolve_mesh_visibility,
)

from orthovideo.drawing.mesh_svg import (
    export_mesh_visibility_svg,
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
    / "obj_front_visibility.svg"
)


def main():

    print()
    print("=" * 60)
    print("ORTHOVIDEO - OBJ VISIBILITY TEST")
    print("=" * 60)

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

    front = views["front"]

    candidate_edges = (
        project_mesh_edges(
            mesh,
            front,
            feature_angle_deg=30.0,
        )
    )

    print()
    print(
        "Edge candidati:",
        len(candidate_edges),
    )

    result = (
        resolve_mesh_visibility(
            mesh,
            candidate_edges,
            front,

            samples_per_diagonal=150,
            max_segments_per_edge=128,
        )
    )

    print(
        "Segmenti visibili:",
        len(result.visible),
    )

    print(
        "Segmenti nascosti:",
        len(result.hidden),
    )

    export_mesh_visibility_svg(
        result,
        OUTPUT,
        title="OBJ FRONT - VISIBILITY",
    )

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()