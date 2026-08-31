from pathlib import Path

import trimesh


ROOT = Path(__file__).resolve().parents[1]

OUTPUT_FILE = (
    ROOT
    / "models"
    / "test_mesh.obj"
)


def main():

    # Corpo principale 100 × 60 × 50
    box = trimesh.creation.box(
        extents=(
            100.0,
            60.0,
            50.0,
        )
    )

    # Trimesh crea il box centrato nell'origine.
    #
    # Lo spostiamo in modo da avere:
    #
    # X = 0 ... 100
    # Y = 0 ... 60
    # Z = 0 ... 50

    box.apply_translation(
        (
            50.0,
            30.0,
            25.0,
        )
    )

    box.export(
        OUTPUT_FILE
    )

    print()
    print("OBJ creato:")
    print(OUTPUT_FILE)

    print()
    print(
        f"Vertici: {len(box.vertices)}"
    )

    print(
        f"Triangoli: {len(box.faces)}"
    )


if __name__ == "__main__":
    main()