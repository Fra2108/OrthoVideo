from pathlib import Path

from orthovideo.io.step_loader import load_step
from orthovideo.geometry import get_bounding_box


ROOT = Path(__file__).resolve().parents[1]

MODEL = ROOT / "models" / "test_box.step"


def main():
    print("Caricamento modello...")
    print()

    shape = load_step(MODEL)

    print("STEP caricato correttamente.")
    print(f"Shape nulla: {shape.IsNull()}")

    dimensions = get_bounding_box(shape)

    print()
    print("Dimensioni rilevate:")
    print(f"X = {dimensions['width_x']:.3f} mm")
    print(f"Y = {dimensions['width_y']:.3f} mm")
    print(f"Z = {dimensions['height_z']:.3f} mm")


if __name__ == "__main__":
    main()