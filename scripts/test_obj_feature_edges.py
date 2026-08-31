from pathlib import Path
from collections import Counter

from orthovideo.io.obj_loader import (
    load_obj,
)

from orthovideo.projection.mesh_edges import (
    extract_feature_edges,
)


ROOT = Path(__file__).resolve().parents[1]

MODEL = (
    ROOT
    / "models"
    / "test_mesh.obj"
)


def vector_text(v):

    return (
        f"({v[0]:.3f}, "
        f"{v[1]:.3f}, "
        f"{v[2]:.3f})"
    )


def main():

    print()
    print("=" * 60)
    print("ORTHOVIDEO - OBJ FEATURE EDGE TEST")
    print("=" * 60)

    mesh = load_obj(
        MODEL
    )

    edges = extract_feature_edges(
        mesh,
        angle_threshold_deg=1.0,
    )

    print()
    print(
        f"Feature edge trovati: {len(edges)}"
    )

    kinds = Counter(
        edge.kind
        for edge in edges
    )

    print()

    for kind, count in sorted(
        kinds.items()
    ):
        print(
            f"{kind:15s}: {count}"
        )

    print()
    print("-" * 60)

    for i, edge in enumerate(
        edges,
        start=1,
    ):

        print()
        print(
            f"EDGE {i}"
        )

        print(
            "  start:",
            vector_text(
                edge.start
            ),
        )

        print(
            "  end:  ",
            vector_text(
                edge.end
            ),
        )

        print(
            f"  tipo:  {edge.kind}"
        )

        if edge.angle_deg is not None:

            print(
                f"  angolo: "
                f"{edge.angle_deg:.3f}°"
            )

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()