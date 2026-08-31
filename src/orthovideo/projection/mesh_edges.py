from dataclasses import dataclass
from math import degrees, radians

import numpy as np
import trimesh


Vector3 = tuple[float, float, float]


@dataclass(frozen=True)
class MeshFeatureEdge:
    """
    Spigolo geometricamente significativo di una mesh.

    vertex_1 / vertex_2:
        Indici dei vertici nella mesh.

    start / end:
        Coordinate 3D.

    angle_deg:
        Angolo diedro fra le due facce adiacenti.
        None per boundary/non-manifold edge.

    kind:
        "sharp"
        "boundary"
        "non_manifold"
    """

    vertex_1: int
    vertex_2: int

    start: Vector3
    end: Vector3

    angle_deg: float | None

    kind: str


def _edge_key(
    edge,
) -> tuple[int, int]:

    a = int(edge[0])
    b = int(edge[1])

    return (
        min(a, b),
        max(a, b),
    )


def extract_feature_edges(
    mesh: trimesh.Trimesh,
    *,
    angle_threshold_deg: float = 1.0,
) -> list[MeshFeatureEdge]:
    """
    Estrae dalla mesh gli edge che hanno significato
    geometrico.

    Vengono mantenuti:

    1. boundary edge;
    2. edge non-manifold;
    3. edge fra facce con angolo maggiore della soglia.

    Vengono eliminati gli edge interni fra triangoli
    complanari, tipicamente le diagonali introdotte
    dalla triangolazione.
    """

    if angle_threshold_deg < 0:
        raise ValueError(
            "angle_threshold_deg non può essere negativo."
        )

    vertices = np.asarray(
        mesh.vertices,
        dtype=float,
    )

    faces = np.asarray(
        mesh.faces,
        dtype=np.int64,
    )

    # -------------------------------------------------
    # TUTTI GLI EDGE DEI TRIANGOLI
    # -------------------------------------------------

    all_edges = np.vstack(
        (
            faces[:, [0, 1]],
            faces[:, [1, 2]],
            faces[:, [2, 0]],
        )
    )

    # Rendiamo ogni edge indipendente dall'orientamento:
    #
    # (5, 2) == (2, 5)
    canonical_edges = np.sort(
        all_edges,
        axis=1,
    )

    unique_edges, counts = np.unique(
        canonical_edges,
        axis=0,
        return_counts=True,
    )

    edge_counts = {
        _edge_key(edge): int(count)
        for edge, count
        in zip(unique_edges, counts)
    }

    # -------------------------------------------------
    # ANGOLI FRA FACCE ADIACENTI
    # -------------------------------------------------

    adjacency_edges = np.asarray(
        mesh.face_adjacency_edges,
        dtype=np.int64,
    )

    adjacency_angles = np.asarray(
        mesh.face_adjacency_angles,
        dtype=float,
    )

    angle_by_edge: dict[
        tuple[int, int],
        float
    ] = {}

    for edge, angle in zip(
        adjacency_edges,
        adjacency_angles,
    ):

        key = _edge_key(
            edge
        )

        angle_by_edge[key] = float(
            angle
        )

    # -------------------------------------------------
    # CLASSIFICAZIONE
    # -------------------------------------------------

    threshold_rad = radians(
        angle_threshold_deg
    )

    result: list[MeshFeatureEdge] = []

    for edge in unique_edges:

        key = _edge_key(
            edge
        )

        count = edge_counts[key]

        v1, v2 = key

        start = tuple(
            float(v)
            for v in vertices[v1]
        )

        end = tuple(
            float(v)
            for v in vertices[v2]
        )

        # ---------------------------------------------
        # BORDO APERTO
        # ---------------------------------------------

        if count == 1:

            result.append(
                MeshFeatureEdge(
                    vertex_1=v1,
                    vertex_2=v2,

                    start=start,
                    end=end,

                    angle_deg=None,

                    kind="boundary",
                )
            )

            continue

        # ---------------------------------------------
        # NON-MANIFOLD
        # ---------------------------------------------

        if count > 2:

            result.append(
                MeshFeatureEdge(
                    vertex_1=v1,
                    vertex_2=v2,

                    start=start,
                    end=end,

                    angle_deg=None,

                    kind="non_manifold",
                )
            )

            continue

        # ---------------------------------------------
        # EDGE CON DUE FACCE ADIACENTI
        # ---------------------------------------------

        angle = angle_by_edge.get(
            key
        )

        if angle is None:
            continue

        # Se le facce sono quasi complanari,
        # l'edge appartiene solamente alla
        # triangolazione e viene ignorato.
        if angle <= threshold_rad:
            continue

        result.append(
            MeshFeatureEdge(
                vertex_1=v1,
                vertex_2=v2,

                start=start,
                end=end,

                angle_deg=degrees(
                    angle
                ),

                kind="sharp",
            )
        )

    return result