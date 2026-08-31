from pathlib import Path

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepPrimAPI import (
    BRepPrimAPI_MakeBox,
    BRepPrimAPI_MakeCylinder,
)
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILE = ROOT / "models" / "test_part.step"


def main():
    # Corpo principale:
    #
    # X = 100 mm
    # Y = 60 mm
    # Z = 50 mm
    box = BRepPrimAPI_MakeBox(
        100.0,
        60.0,
        50.0,
    ).Shape()

    # Foro passante:
    # diametro = 20 mm
    #
    # Asse parallelo a Y.
    #
    # Il centro è volutamente NON centrato:
    # X = 30 mm
    # Z = 28 mm
    #
    # Questo ci permetterà di capire immediatamente
    # se una vista viene specchiata.
    hole_axis = gp_Ax2(
        gp_Pnt(
            30.0,
            -5.0,
            28.0,
        ),
        gp_Dir(
            0.0,
            1.0,
            0.0,
        ),
    )

    cylinder = BRepPrimAPI_MakeCylinder(
        hole_axis,
        10.0,   # raggio
        70.0,   # lunghezza > 60 per attraversare tutto
    ).Shape()

    cutter = BRepAlgoAPI_Cut(
        box,
        cylinder,
    )

    cutter.Build()

    if not cutter.IsDone():
        raise RuntimeError(
            "Operazione booleana CUT fallita."
        )

    part = cutter.Shape()

    if part.IsNull():
        raise RuntimeError(
            "La geometria finale è nulla."
        )

    writer = STEPControl_Writer()

    writer.Transfer(
        part,
        STEPControl_AsIs,
    )

    writer.Write(
        str(OUTPUT_FILE)
    )

    print()
    print("Pezzo di prova creato correttamente:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()