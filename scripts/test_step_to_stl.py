from pathlib import Path

from orthovideo.io.step_loader import load_step
from orthovideo.animation.mesh_prepare import (
    export_step_render_mesh,
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
    / "animation"
    / "test_part_render.stl"
)


def main():

    print()
    print("=" * 60)
    print("ORTHOVIDEO - STEP TO RENDER MESH")
    print("=" * 60)

    shape = load_step(
        MODEL
    )

    result = export_step_render_mesh(
        shape,
        OUTPUT,
        linear_deflection=0.10,
    )

    print()
    print("STL creato correttamente:")
    print(result)

    print()
    print(
        f"Dimensione file: "
        f"{result.stat().st_size} bytes"
    )

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()