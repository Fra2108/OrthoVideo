from pathlib import Path

from orthovideo.io.step_loader import load_step

from orthovideo.projection.view_system import (
    build_six_views,
)

from orthovideo.projection.hlr import (
    project_shape,
    count_edges,
)


ROOT = Path(__file__).resolve().parents[1]

MODEL = ROOT / "models" / "test_box.step"


def main():

    print()
    print("ORTHOVIDEO - TEST PROIEZIONI")
    print("=" * 40)

    shape = load_step(MODEL)

    views = build_six_views(
        main_normal=(0.0, -1.0, 0.0),
        main_up=(0.0, 0.0, 1.0),
    )

    for name, view in views.items():

        result = project_shape(
            shape,
            view,
        )

        visible_count = count_edges(
            result.visible
        )

        hidden_count = count_edges(
            result.hidden
        )

        print()
        print(f"Vista: {name.upper()}")

        print(
            "  normal = "
            f"{view.normal}"
        )

        print(
            "  up     = "
            f"{view.up}"
        )

        print(
            f"  edge visibili = {visible_count}"
        )

        print(
            f"  edge nascosti = {hidden_count}"
        )

    print()
    print("=" * 40)
    print("HLR completato.")


if __name__ == "__main__":
    main()