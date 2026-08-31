from pathlib import Path

from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILE = ROOT / "models" / "test_box.step"


def main():
    # Parallelepipedo:
    # X = 100 mm
    # Y = 60 mm
    # Z = 30 mm
    shape = BRepPrimAPI_MakeBox(100.0, 60.0, 30.0).Shape()

    if shape.IsNull():
        raise RuntimeError("Errore nella creazione del solido.")

    writer = STEPControl_Writer()

    transfer_status = writer.Transfer(shape, STEPControl_AsIs)

    write_status = writer.Write(str(OUTPUT_FILE))

    print(f"STEP creato: {OUTPUT_FILE}")
    print(f"Transfer status: {transfer_status}")
    print(f"Write status: {write_status}")


if __name__ == "__main__":
    main()