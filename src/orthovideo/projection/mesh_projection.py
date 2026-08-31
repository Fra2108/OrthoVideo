from dataclasses import dataclass
from math import acos, degrees

import numpy as np
import trimesh

from orthovideo.projection.view_system import (
    ViewDefinition,
    cross,
    dot,
    normalize,
)


Vector3 = tuple[float, float, float]
Point2D = tuple[float, float]


@dataclass(frozen=True)
class MeshProjectedEdge:
    start_3d: Vector3
    end_3d: Vector3

    start_2d: Point2D
    end_2d: Point2D

    kind: str

    adjacent_faces: tuple[int, ...]


def project_point_to_view(
    point: Vector3,
    view: ViewDefinition,
) -> Point2D:
    """
    Proiezione ortogonale nel sistema 2D della vista.

    X vista = cross(up, normal)
    Y vista = up
    """

    n = normalize(view.normal)
    up = normalize(view.up)

    screen_x = normalize(
        cross(up, n)
    )

    return (
        dot(point, screen_x),
        dot(point, up),
    )


def _edge_key(a: int, b: int) -> tuple[int, int]:

    if a < b:
        return a, b

    return b, a


def _build_edge_face_map(
    mesh: trimesh.Trimesh,
) -> dict[tuple[int, int], list[int]]:

    result: dict[
        tuple[int, int],
        list[int]
    ] = {}

    faces = np.asarray(
        mesh.faces,
        dtype=np.int64,
    )

    for face_index, face in enumerate(faces):

        a, b, c = (
            int(face[0]),
            int(face[1]),
            int(face[2]),
        )

        for v1, v2 in (
            (a, b),
            (b, c),
            (c, a),
        ):

            key = _edge_key(
                v1,
                v2,
            )

            result.setdefault(
                key,
                [],
            ).append(
                face_index
            )

    return result


def _dihedral_angle_deg(
    normal_1: np.ndarray,
    normal_2: np.ndarray,
) -> float:

    value = float(
        np.dot(
            normal_1,
            normal_2,
        )
    )

    value = np.clip(
        value,
        -1.0,
        1.0,
    )

    return degrees(
        acos(value)
    )


def project_mesh_edges(
    mesh: trimesh.Trimesh,
    view: ViewDefinition,
    *,
    feature_angle_deg: float = 30.0,
    facing_tolerance: float = 1e-9,
) -> list[MeshProjectedEdge]:
    """
    Genera i bordi candidati di una vista OBJ.

    Include:
      - silhouette;
      - boundary edge;
      - feature edge geometrici.

    NON effettua ancora il test di occlusione.
    """

    if feature_angle_deg < 0:
        raise ValueError(
            "feature_angle_deg deve essere >= 0."
        )

    vertices = np.asarray(
        mesh.vertices,
        dtype=float,
    )

    normals = np.asarray(
        mesh.face_normals,
        dtype=float,
    )

    view_normal = np.asarray(
        normalize(view.normal),
        dtype=float,
    )

    # Quanto ogni faccia è rivolta verso
    # l'osservatore.
    facing = (
        normals
        @ view_normal
    )

    edge_faces = (
        _build_edge_face_map(mesh)
    )

    projected: list[
        MeshProjectedEdge
    ] = []

    for edge, face_ids in edge_faces.items():

        vertex_1, vertex_2 = edge

        p1_np = vertices[vertex_1]
        p2_np = vertices[vertex_2]

        p1 = tuple(
            float(v)
            for v in p1_np
        )

        p2 = tuple(
            float(v)
            for v in p2_np
        )

        kind: str | None = None

        # -----------------------------------------
        # BOUNDARY
        # -----------------------------------------

        if len(face_ids) == 1:

            face = face_ids[0]

            # Manteniamo il boundary come candidato.
            kind = "boundary"

        # -----------------------------------------
        # EDGE CON DUE FACCE
        # -----------------------------------------

        elif len(face_ids) == 2:

            f1, f2 = face_ids

            facing_1 = float(
                facing[f1]
            )

            facing_2 = float(
                facing[f2]
            )

            # Una faccia sta da un lato della
            # direzione di vista e l'altra
            # dall'altro.
            #
            # Includiamo anche il caso tangente
            # (dot ≈ 0), necessario per box
            # osservati esattamente di fronte.
            opposite_or_tangent = (
                facing_1
                * facing_2
                <= facing_tolerance
            )

            significant_facing = (
                abs(facing_1)
                > facing_tolerance
                or
                abs(facing_2)
                > facing_tolerance
            )

            if (
                opposite_or_tangent
                and significant_facing
            ):

                kind = "silhouette"

            else:

                angle = (
                    _dihedral_angle_deg(
                        normals[f1],
                        normals[f2],
                    )
                )

                if (
                    angle
                    >= feature_angle_deg
                ):

                    kind = "feature"

        # -----------------------------------------
        # NON-MANIFOLD
        # -----------------------------------------

        else:

            kind = "non_manifold"

        if kind is None:
            continue

        start_2d = (
            project_point_to_view(
                p1,
                view,
            )
        )

        end_2d = (
            project_point_to_view(
                p2,
                view,
            )
        )

        # Segmento degenerato nella vista.
        dx = (
            end_2d[0]
            - start_2d[0]
        )

        dy = (
            end_2d[1]
            - start_2d[1]
        )

        if (
            dx * dx
            + dy * dy
            < 1e-16
        ):
            continue

        projected.append(
            MeshProjectedEdge(
                start_3d=p1,
                end_3d=p2,

                start_2d=start_2d,
                end_2d=end_2d,

                kind=kind,

                adjacent_faces=tuple(
                    face_ids
                ),
            )
        )

    return projected