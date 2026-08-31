from dataclasses import dataclass, field


Point2D = tuple[float, float]
Polyline2D = list[Point2D]


@dataclass(frozen=True)
class Projection2D:
    """
    Rappresentazione indipendente dal formato sorgente
    di una vista ortogonale.

    Ogni linea è una polyline 2D in coordinate geometriche
    del modello.

    STEP e OBJ vengono entrambi convertiti in questo formato.
    """

    visible: list[Polyline2D]
    hidden: list[Polyline2D]
    # Optional smooth/tangent edges are kept separate so that a technical
    # drawing policy can omit them or render them as thin continuous lines.
    tangent: list[Polyline2D] = field(default_factory=list)
