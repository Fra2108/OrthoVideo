from dataclasses import dataclass
from math import cos, pi, sin


Point2D = tuple[float, float]
Polyline2D = list[Point2D]


@dataclass(frozen=True)
class TechnicalAnnotation2D:
    """A technical line carrying an explicit semantic drawing role."""

    role: str
    points: Polyline2D


@dataclass(frozen=True)
class TechnicalLabel2D:
    """Text anchored in the model-space coordinates of one view."""

    text: str
    position: Point2D


def circle_annotation(
    *,
    role: str,
    center: Point2D,
    radius: float,
    segments: int = 96,
) -> TechnicalAnnotation2D:
    """Create a closed polyline for explicit pitch/primitive circles."""
    if radius <= 0:
        raise ValueError("Il raggio della circonferenza deve essere positivo.")

    if segments < 12:
        raise ValueError("Una circonferenza richiede almeno 12 segmenti.")

    points = [
        (
            center[0] + radius * cos(2.0 * pi * index / segments),
            center[1] + radius * sin(2.0 * pi * index / segments),
        )
        for index in range(segments)
    ]
    points.append(points[0])
    return TechnicalAnnotation2D(role=role.upper(), points=points)
