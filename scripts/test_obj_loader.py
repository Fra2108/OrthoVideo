from pathlib import Path

from orthovideo.io.obj_loader import (
    load_obj,
)

from orthovideo.mesh_geometry import (
    get_mesh_info,
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
    print("ORTHOVIDEO - OBJ TEST")
    print("=" * 60)

    mesh = load_obj(
        MODEL
    )

    info = get_mesh_info(
        mesh
    )

    print()
    print(
        f"Vertici:        {info.vertices}"
    )

    print(
        f"Triangoli:      {info.triangles}"
    )

    print(
        f"Componenti:     {info.components}"
    )

    print(
        f"Watertight:     {info.watertight}"
    )

    print(
        "Winding OK:     "
        f"{info.winding_consistent}"
    )

    print()

    print(
        "Min: ",
        vector_text(
            info.minimum
        )
    )

    print(
        "Max: ",
        vector_text(
            info.maximum
        )
    )

    print(
        "Size:",
        vector_text(
            info.size
        )
    )

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()