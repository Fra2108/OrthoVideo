from pathlib import Path

from orthovideo.io.step_loader import load_step

from orthovideo.projection.view_system import (
    build_six_views,
)

from orthovideo.projection.hlr import (
    project_shape,
)

from orthovideo.drawing.technical_sheet import (
    export_first_angle_sheet,
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
    / "first_angle_A3.svg"
)


def main():

    print()
    print("ORTHOVIDEO")
    print("Tavola ortogonale - primo diedro")
    print("=" * 50)

    shape = load_step(
        MODEL
    )

    # Vista principale fornita dall'utente.
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

    projections = {}

    for name, view in views.items():

        print(
            f"Calcolo vista: {name}"
        )

        projections[name] = project_shape(
            shape,
            view,
        )

    export_first_angle_sheet(
        projections,
        OUTPUT,

        # A3 orizzontale
        page_width=420.0,
        page_height=297.0,

        margin=15.0,

        # distanza reale fra le viste
        gap=20.0,

        # inizialmente 1:1
        drawing_scale=1.0,

        # solo durante lo sviluppo
        show_labels=True,
    )

    print()
    print("Operazione completata.")


if __name__ == "__main__":
    main()