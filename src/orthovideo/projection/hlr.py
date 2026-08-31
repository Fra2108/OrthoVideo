from dataclasses import dataclass

from OCP.BRepLib import BRepLib
from OCP.HLRAlgo import HLRAlgo_Projector
from OCP.HLRBRep import (
    HLRBRep_Algo,
    HLRBRep_HLRToShape,
)
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS_Shape
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

from orthovideo.projection.view_system import (
    ViewDefinition,
    cross,
    normalize,
)


@dataclass
class HLRResult:
    """
    Risultato di una proiezione ortogonale.
    """

    visible: list[TopoDS_Shape]
    hidden: list[TopoDS_Shape]
    tangent_visible: list[TopoDS_Shape]
    tangent_hidden: list[TopoDS_Shape]


def _make_projector(
    view: ViewDefinition,
) -> HLRAlgo_Projector:
    """
    Costruisce un proiettore ortogonale OpenCascade.
    """

    normal = normalize(view.normal)
    up = normalize(view.up)

    screen_x = normalize(
        cross(up, normal)
    )

    axis = gp_Ax2(
        gp_Pnt(0.0, 0.0, 0.0),

        gp_Dir(
            normal[0],
            normal[1],
            normal[2],
        ),

        gp_Dir(
            screen_x[0],
            screen_x[1],
            screen_x[2],
        ),
    )

    # Nessuna focale:
    # proiezione ORTOGONALE, non prospettica.
    return HLRAlgo_Projector(axis)


def project_shape(
    shape: TopoDS_Shape,
    view: ViewDefinition,
) -> HLRResult:
    """
    Esegue Hidden Line Removal sulla geometria
    secondo una vista ortogonale.
    """

    hlr = HLRBRep_Algo()

    hlr.Add(shape)

    projector = _make_projector(view)

    hlr.Projector(projector)

    hlr.Update()

    hlr.Hide()

    result = HLRBRep_HLRToShape(hlr)

    visible: list[TopoDS_Shape] = []
    hidden: list[TopoDS_Shape] = []

    # Spigoli netti visibili
    shape_visible = result.VCompound()

    if not shape_visible.IsNull():
        visible.append(shape_visible)

    # Silhouette / contorni apparenti
    outline_visible = result.OutLineVCompound()

    if not outline_visible.IsNull():
        visible.append(outline_visible)

    # Spigoli nascosti
    shape_hidden = result.HCompound()

    if not shape_hidden.IsNull():
        hidden.append(shape_hidden)

    # Contorni nascosti
    outline_hidden = result.OutLineHCompound()

    if not outline_hidden.IsNull():
        hidden.append(outline_hidden)

    tangent_visible: list[TopoDS_Shape] = []
    tangent_hidden: list[TopoDS_Shape] = []

    for tangent_shape in (
        result.Rg1LineVCompound(),
        result.RgNLineVCompound(),
    ):
        if not tangent_shape.IsNull():
            tangent_visible.append(tangent_shape)

    for tangent_shape in (
        result.Rg1LineHCompound(),
        result.RgNLineHCompound(),
    ):
        if not tangent_shape.IsNull():
            tangent_hidden.append(tangent_shape)

    # OpenCascade necessita delle curve 3D
    # associate agli edge HLR per elaborazioni successive.
    for compound in visible:
        BRepLib.BuildCurves3d_s(
            compound,
            1e-7,
        )

    for compound in hidden:
        BRepLib.BuildCurves3d_s(
            compound,
            1e-7,
        )

    for compound in tangent_visible + tangent_hidden:
        BRepLib.BuildCurves3d_s(compound, 1e-7)

    return HLRResult(
        visible=visible,
        hidden=hidden,
        tangent_visible=tangent_visible,
        tangent_hidden=tangent_hidden,
    )


def count_edges(
    shapes: list[TopoDS_Shape],
) -> int:
    """
    Conta gli edge presenti in una lista di shape/compound.
    """

    count = 0

    for shape in shapes:

        explorer = TopExp_Explorer(
            shape,
            TopAbs_EDGE,
        )

        while explorer.More():
            count += 1
            explorer.Next()

    return count
