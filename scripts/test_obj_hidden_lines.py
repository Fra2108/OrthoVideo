from pathlib import Path
from collections import Counter

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
    / "hidden_test.obj"
)

OUTPUT = (
    ROOT
    / "output"
    / "obj_hidden_test_front.svg"
)


def main():

    print()
    print("=" * 60)
    print("ORTHOVIDEO - OBJ HIDDEN LINE TEST")
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

    # ---------------------------------------------
    # 1. Edge candidati
    # ---------------------------------------------

    candidates = project_mesh_edges(
        mesh,
        front,
        feature_angle_deg=30.0,
    )

    kinds = Counter(
        edge.kind
        for edge in candidates
    )

    print()
    print(
        f"Edge candidati: {len(candidates)}"
    )

    for kind, count in sorted(
        kinds.items()
    ):

        print(
            f"  {kind:15s}: {count}"
        )

    # ---------------------------------------------
    # 2. Visibilità
    # ---------------------------------------------

    result = resolve_mesh_visibility(
        mesh,
        candidates,
        front,

        samples_per_diagonal=200,
        max_segments_per_edge=128,
    )

    print()
    print(
        f"Segmenti visibili: {len(result.visible)}"
    )

    print(
        f"Segmenti nascosti: {len(result.hidden)}"
    )

    # ---------------------------------------------
    # 3. SVG
    # ---------------------------------------------

    export_mesh_visibility_svg(
        result,
        OUTPUT,
        title="OBJ HIDDEN LINE TEST",
    )

    print()
    print("Output:")
    print(OUTPUT)

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()