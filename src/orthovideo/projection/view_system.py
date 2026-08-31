from dataclasses import dataclass
from math import sqrt


Vector3 = tuple[float, float, float]


@dataclass(frozen=True)
class ViewDefinition:
    """
    Definizione geometrica di una vista ortogonale.

    normal:
        Direzione dal modello verso l'osservatore.

    up:
        Direzione che deve apparire verticale verso l'alto
        nel foglio.
    """

    name: str
    normal: Vector3
    up: Vector3


def dot(a: Vector3, b: Vector3) -> float:
    return (
        a[0] * b[0]
        + a[1] * b[1]
        + a[2] * b[2]
    )


def cross(a: Vector3, b: Vector3) -> Vector3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def norm(v: Vector3) -> float:
    return sqrt(dot(v, v))


def normalize(v: Vector3) -> Vector3:
    length = norm(v)

    if length < 1e-12:
        raise ValueError("Il vettore non può essere nullo.")

    return (
        v[0] / length,
        v[1] / length,
        v[2] / length,
    )


def negate(v: Vector3) -> Vector3:
    return (-v[0], -v[1], -v[2])


def subtract(a: Vector3, b: Vector3) -> Vector3:
    return (
        a[0] - b[0],
        a[1] - b[1],
        a[2] - b[2],
    )


def multiply(v: Vector3, value: float) -> Vector3:
    return (
        v[0] * value,
        v[1] * value,
        v[2] * value,
    )


def orthogonalize_up(
    normal: Vector3,
    up: Vector3,
) -> Vector3:
    """
    Rende il vettore up perfettamente ortogonale
    alla normale della vista.
    """

    n = normalize(normal)
    u = normalize(up)

    projection = multiply(
        n,
        dot(u, n),
    )

    u_orthogonal = subtract(
        u,
        projection,
    )

    if norm(u_orthogonal) < 1e-8:
        raise ValueError(
            "'up' non può essere parallelo alla normale della vista."
        )

    return normalize(u_orthogonal)


def build_six_views(
    main_normal: Vector3,
    main_up: Vector3,
) -> dict[str, ViewDefinition]:
    """
    Genera automaticamente le sei viste ortogonali
    a partire dalla vista principale scelta dall'utente.
    """

    n = normalize(main_normal)

    u = orthogonalize_up(
        n,
        main_up,
    )

    # Direzione orizzontale positiva della vista:
    # destra sul foglio.
    r = normalize(
        cross(u, n)
    )

    return {
        "front": ViewDefinition(
            name="front",
            normal=n,
            up=u,
        ),

        "rear": ViewDefinition(
            name="rear",
            normal=negate(n),
            up=u,
        ),

        "top": ViewDefinition(
            name="top",
            normal=u,
            up=negate(n),
        ),

        "bottom": ViewDefinition(
            name="bottom",
            normal=negate(u),
            up=n,
        ),

        "right": ViewDefinition(
            name="right",
            normal=r,
            up=u,
        ),

        "left": ViewDefinition(
            name="left",
            normal=negate(r),
            up=u,
        ),
    }