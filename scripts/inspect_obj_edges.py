from pathlib import Path
from math import degrees

from orthovideo.io.obj_loader import (
    load_obj,
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

    angles = mesh.face_adjacency_angles

    flat = 0
    sharp = 0

    print()
    print("ANGOLI FRA TRIANGOLI ADIACENTI")
    print("=" * 50)

    for angle in angles:

        value = degrees(
            float(angle)
        )

        print(
            f"{value:.6f}°"
        )

        if value < 1.0:
            flat += 1
        else:
            sharp += 1

    print()
    print(
        f"Edge triangolazione/complanari: {flat}"
    )

    print(
        f"Edge geometrici:                {sharp}"
    )


if __name__ == "__main__":
    main()