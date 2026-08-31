from pathlib import Path

import trimesh


ROOT = Path(__file__).resolve().parents[1]

OUTPUT_FILE = (
    ROOT
    / "models"
    / "hidden_test.obj"
)


def main():

    # =================================================
    # BLOCCO ANTERIORE
    #
    # X = 0 ... 100
    # Y = 0 ... 20
    # Z = 0 ... 60
    #
    # Il nostro osservatore FRONT si trova verso -Y,
    # quindi questo blocco è DAVANTI.
    # =================================================

    front = trimesh.creation.box(
        extents=(
            100.0,
            20.0,
            60.0,
        )
    )

    front.apply_translation(
        (
            50.0,
            10.0,
            30.0,
        )
    )

    # =================================================
    # BLOCCO POSTERIORE
    #
    # X = 20 ... 80
    # Y = 30 ... 50
    # Z = 15 ... 45
    #
    # In vista FRONT è completamente contenuto
    # dietro al blocco anteriore.
    # =================================================

    rear = trimesh.creation.box(
        extents=(
            60.0,
            20.0,
            30.0,
        )
    )

    rear.apply_translation(
        (
            50.0,
            40.0,
            30.0,
        )
    )

    # Un'unica mesh con due componenti connesse.
    mesh = trimesh.util.concatenate(
        [
            front,
            rear,
        ]
    )

    mesh.export(
        OUTPUT_FILE
    )

    print()
    print("=" * 60)
    print("ORTHOVIDEO - HIDDEN LINE TEST MODEL")
    print("=" * 60)

    print()
    print("OBJ creato:")
    print(OUTPUT_FILE)

    print()
    print(
        f"Vertici:   {len(mesh.vertices)}"
    )

    print(
        f"Triangoli: {len(mesh.faces)}"
    )

    print()

    components = mesh.split(
        only_watertight=False
    )

    print(
        f"Componenti: {len(components)}"
    )


if __name__ == "__main__":
    main()