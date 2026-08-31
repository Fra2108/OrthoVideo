from pathlib import Path

from orthovideo.io.step_loader import load_step
from orthovideo.projection.view_system import build_six_views
from orthovideo.projection.hlr import project_shape
from orthovideo.drawing.svg_exporter import export_projection_svg


ROOT = Path(__file__).resolve().parents[1]

MODEL = ROOT / "models" / "test_part.step"

OUTPUT_DIR = ROOT / "output" / "views"


def main():

    print()
    print("ORTHOVIDEO")
    print("Generazione delle 6 viste ortogonali")
    print("=" * 50)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    shape = load_step(MODEL)

    # Vista principale scelta dall'utente.
    #
    # Per il nostro test:
    # osservatore lungo -Y
    # Z verticale.
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

    for name, view in views.items():

        print()
        print(f"Generazione: {name.upper()}")

        projection = project_shape(
            shape,
            view,
        )

        output_file = (
            OUTPUT_DIR
            / f"{name}.svg"
        )

        export_projection_svg(
            projection.visible,
            projection.hidden,
            output_file,
            title=name.upper(),
        )

    print()
    print("=" * 50)
    print("Tutte le viste generate.")
    print()
    print(f"Cartella: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()