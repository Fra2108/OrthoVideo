from pathlib import Path

from orthovideo.io.step_loader import load_step

from orthovideo.projection.view_system import (
    build_six_views,
)

from orthovideo.projection.hlr import (
    project_shape,
)

from orthovideo.drawing.svg_exporter import (
    export_projection_svg,
)


ROOT = Path(__file__).resolve().parents[1]

MODEL = (
    ROOT
    / "models"
    / "test_part.step"
)

OUTPUT = (
    ROOT
    / "output"
    / "test_front.svg"
)


def main():

    print()
    print("ORTHOVIDEO")
    print("Generazione vista frontale")
    print("=" * 40)

    shape = load_step(
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

    projection = project_shape(
        shape,
        front,
    )

    export_projection_svg(
        projection.visible,
        projection.hidden,
        OUTPUT,
        title="FRONT VIEW",
    )

    print()
    print("Completato.")
    print(OUTPUT)


if __name__ == "__main__":
    main()