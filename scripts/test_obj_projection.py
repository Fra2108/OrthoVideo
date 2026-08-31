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


ROOT = Path(__file__).resolve().parents[1]

MODEL = (
    ROOT
    / "models"
    / "test_mesh.obj"
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

    print()
    print("=" * 60)
    print("ORTHOVIDEO - OBJ VIEW PROJECTION")
    print("=" * 60)

    for name, view in views.items():

        edges = project_mesh_edges(
            mesh,
            view,

            feature_angle_deg=30.0,
        )

        kinds = Counter(
            edge.kind
            for edge in edges
        )

        print()
        print(
            f"VIEW: {name.upper()}"
        )

        print(
            f"Projected edges: {len(edges)}"
        )

        for kind, count in sorted(
            kinds.items()
        ):

            print(
                f"  {kind:15s}: {count}"
            )

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()