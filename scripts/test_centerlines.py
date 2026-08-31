from pathlib import Path

from orthovideo.io.step_loader import load_step

from orthovideo.features.cylinders import (
    extract_cylinders,
)

from orthovideo.projection.view_system import (
    build_six_views,
)

from orthovideo.projection.centerlines import (
    build_centerlines_for_view,
)


ROOT = Path(__file__).resolve().parents[1]

MODEL = (
    ROOT
    / "models"
    / "test_part.step"
)


def main():

    shape = load_step(
        MODEL
    )

    cylinders = extract_cylinders(
        shape
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
    print("ORTHOVIDEO - CENTERLINE TEST")
    print("=" * 60)

    print(
        f"Cilindri rilevati: {len(cylinders)}"
    )

    for name, view in views.items():

        lines = build_centerlines_for_view(
            cylinders,
            view,

            # Test in scala 1:1:
            # 3 mm oltre la geometria.
            extension=3.0,
        )

        print()
        print(
            f"{name.upper()}: "
            f"{len(lines)} centerline"
        )

        for i, line in enumerate(
            lines,
            start=1,
        ):

            print(
                f"  {i}: "
                f"{line.start} -> {line.end}"
            )

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()