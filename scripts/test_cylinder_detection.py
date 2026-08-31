from pathlib import Path

from orthovideo.io.step_loader import load_step

from orthovideo.features.cylinders import (
    extract_cylinders,
)


ROOT = Path(__file__).resolve().parents[1]

MODEL = (
    ROOT
    / "models"
    / "test_part.step"
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
    print("ORTHOVIDEO - CYLINDER DETECTION")
    print("=" * 60)

    shape = load_step(
        MODEL
    )

    cylinders = extract_cylinders(
        shape
    )

    print()
    print(
        f"Superfici cilindriche trovate: "
        f"{len(cylinders)}"
    )

    for i, cylinder in enumerate(
        cylinders,
        start=1,
    ):

        print()
        print(f"CILINDRO {i}")

        print(
            f"  raggio: "
            f"{cylinder.radius:.3f} mm"
        )

        print(
            "  asse origine:   ",
            vector_text(
                cylinder.axis_origin
            ),
        )

        print(
            "  asse direzione: ",
            vector_text(
                cylinder.axis_direction
            ),
        )

        print(
            "  inizio:         ",
            vector_text(
                cylinder.start
            ),
        )

        print(
            "  fine:           ",
            vector_text(
                cylinder.end
            ),
        )

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()