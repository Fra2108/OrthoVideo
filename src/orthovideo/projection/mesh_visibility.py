from dataclasses import dataclass
from math import ceil

import numpy as np
import trimesh

from orthovideo.projection.mesh_projection import (
    MeshProjectedEdge,
    project_point_to_view,
)

from orthovideo.projection.view_system import (
    ViewDefinition,
    normalize,
)


Point2D = tuple[float, float]


@dataclass(frozen=True)
class MeshLineSegment2D:
    start: Point2D
    end: Point2D

    source_kind: str


@dataclass(frozen=True)
class MeshVisibilityResult:
    visible: list[MeshLineSegment2D]
    hidden: list[MeshLineSegment2D]


def _lerp(
    a: np.ndarray,
    b: np.ndarray,
    t: float,
) -> np.ndarray:

    return (
        a
        + (b - a) * t
    )


def _segment_key(
    segment: MeshLineSegment2D,
    tolerance: float,
):

    def q(point):

        return (
            round(point[0] / tolerance),
            round(point[1] / tolerance),
        )

    a = q(segment.start)
    b = q(segment.end)

    if a <= b:
        return a, b

    return b, a


def _classify_sample_points(
    mesh: trimesh.Trimesh,
    points: np.ndarray,
    view: ViewDefinition,
    *,
    camera_distance: float,
    hit_tolerance: float,
) -> np.ndarray:
    """
    Stabilisce quali punti della geometria siano
    direttamente visibili dall'osservatore.

    Per ogni punto viene creato un raggio che parte
    molto davanti al modello e procede verso di esso.

    Se il primo impatto coincide con il punto:
        VISIBLE

    Se incontra prima un'altra superficie:
        HIDDEN
    """

    if len(points) == 0:
        return np.zeros(
            0,
            dtype=bool,
        )

    normal = np.asarray(
        normalize(view.normal),
        dtype=float,
    )

    # view.normal:
    # modello -> osservatore
    #
    # Posizioniamo quindi l'origine del raggio
    # davanti al modello.
    origins = (
        points
        + normal[None, :]
        * camera_distance
    )

    directions = np.repeat(
        (-normal)[None, :],
        len(points),
        axis=0,
    )

    try:

        locations, ray_ids, triangle_ids = (
            mesh.ray.intersects_location(
                ray_origins=origins,
                ray_directions=directions,
                multiple_hits=True,
            )
        )

    except ImportError as exc:

        raise RuntimeError(
            "Il ray casting Trimesh richiede "
            "la dipendenza 'rtree'. "
            "Esegui: python -m pip install rtree"
        ) from exc

    # Distanza del primo impatto per ciascun raggio.
    nearest_distance = np.full(
        len(points),
        np.inf,
        dtype=float,
    )

    nearest_location = np.full(
        (
            len(points),
            3,
        ),
        np.nan,
        dtype=float,
    )

    for location, ray_id in zip(
        locations,
        ray_ids,
    ):

        ray_id = int(
            ray_id
        )

        distance = float(
            np.linalg.norm(
                location
                - origins[ray_id]
            )
        )

        if (
            distance
            < nearest_distance[ray_id]
        ):

            nearest_distance[ray_id] = (
                distance
            )

            nearest_location[ray_id] = (
                location
            )

    visible = np.zeros(
        len(points),
        dtype=bool,
    )

    for i, point in enumerate(points):

        # Su una silhouette numericamente perfetta
        # il raggio può sfiorare la mesh senza che
        # l'intersezione venga registrata.
        #
        # In questo caso trattiamo il punto come
        # visibile.
        if not np.isfinite(
            nearest_distance[i]
        ):

            visible[i] = True
            continue

        distance_to_target = float(
            np.linalg.norm(
                nearest_location[i]
                - point
            )
        )

        visible[i] = (
            distance_to_target
            <= hit_tolerance
        )

    return visible


def resolve_mesh_visibility(
    mesh: trimesh.Trimesh,
    edges: list[MeshProjectedEdge],
    view: ViewDefinition,
    *,
    samples_per_diagonal: int = 150,
    max_segments_per_edge: int = 128,
) -> MeshVisibilityResult:
    """
    Suddivide gli edge candidati e stabilisce quali
    parti siano visibili e quali nascoste.

    La suddivisione consente anche di gestire edge
    parzialmente occultati.
    """

    bounds = np.asarray(
        mesh.bounds,
        dtype=float,
    )

    diagonal = float(
        np.linalg.norm(
            bounds[1]
            - bounds[0]
        )
    )

    if diagonal <= 0:
        raise RuntimeError(
            "Bounding box mesh degenerato."
        )

    target_segment_length = (
        diagonal
        / max(
            samples_per_diagonal,
            1,
        )
    )

    camera_distance = (
        diagonal * 2.0
        + 1.0
    )

    hit_tolerance = max(
        diagonal * 1e-6,
        1e-7,
    )

    # ---------------------------------------------
    # CREAZIONE DI TUTTI I CAMPIONI
    # ---------------------------------------------

    samples = []

    metadata = []

    edge_segment_counts = []

    for edge_index, edge in enumerate(edges):

        p1 = np.asarray(
            edge.start_3d,
            dtype=float,
        )

        p2 = np.asarray(
            edge.end_3d,
            dtype=float,
        )

        length = float(
            np.linalg.norm(
                p2 - p1
            )
        )

        if length <= 1e-12:

            edge_segment_counts.append(0)
            continue

        segment_count = int(
            ceil(
                length
                / target_segment_length
            )
        )

        segment_count = max(
            1,
            min(
                segment_count,
                max_segments_per_edge,
            ),
        )

        edge_segment_counts.append(
            segment_count
        )

        for segment_index in range(
            segment_count
        ):

            t0 = (
                segment_index
                / segment_count
            )

            t1 = (
                (segment_index + 1)
                / segment_count
            )

            tm = (
                t0 + t1
            ) / 2.0

            midpoint = _lerp(
                p1,
                p2,
                tm,
            )

            samples.append(
                midpoint
            )

            metadata.append(
                (
                    edge_index,
                    segment_index,
                    t0,
                    t1,
                )
            )

    if not samples:

        return MeshVisibilityResult(
            visible=[],
            hidden=[],
        )

    samples_array = np.asarray(
        samples,
        dtype=float,
    )

    visibility = (
        _classify_sample_points(
            mesh,
            samples_array,
            view,
            camera_distance=camera_distance,
            hit_tolerance=hit_tolerance,
        )
    )

    # ---------------------------------------------
    # RIPORTIAMO I RISULTATI AI SINGOLI EDGE
    # ---------------------------------------------

    edge_visibility = [
        []
        for _ in edges
    ]

    for (
        data,
        is_visible,
    ) in zip(
        metadata,
        visibility,
    ):

        edge_index, segment_index, t0, t1 = (
            data
        )

        edge_visibility[
            edge_index
        ].append(
            (
                t0,
                t1,
                bool(is_visible),
            )
        )

    visible_segments = []
    hidden_segments = []

    # ---------------------------------------------
    # MERGE DEI SEGMENTI CONSECUTIVI
    # ---------------------------------------------

    for edge, classifications in zip(
        edges,
        edge_visibility,
    ):

        if not classifications:
            continue

        p1 = np.asarray(
            edge.start_3d,
            dtype=float,
        )

        p2 = np.asarray(
            edge.end_3d,
            dtype=float,
        )

        run_start = (
            classifications[0][0]
        )

        run_end = (
            classifications[0][1]
        )

        run_visible = (
            classifications[0][2]
        )

        def emit(
            t_start,
            t_end,
            is_visible,
        ):

            start_3d = _lerp(
                p1,
                p2,
                t_start,
            )

            end_3d = _lerp(
                p1,
                p2,
                t_end,
            )

            start_2d = (
                project_point_to_view(
                    tuple(
                        float(v)
                        for v in start_3d
                    ),
                    view,
                )
            )

            end_2d = (
                project_point_to_view(
                    tuple(
                        float(v)
                        for v in end_3d
                    ),
                    view,
                )
            )

            segment = MeshLineSegment2D(
                start=start_2d,
                end=end_2d,
                source_kind=edge.kind,
            )

            if is_visible:

                visible_segments.append(
                    segment
                )

            else:

                hidden_segments.append(
                    segment
                )

        for (
            t0,
            t1,
            is_visible,
        ) in classifications[1:]:

            if (
                is_visible
                == run_visible
                and abs(
                    t0 - run_end
                ) < 1e-12
            ):

                run_end = t1

            else:

                emit(
                    run_start,
                    run_end,
                    run_visible,
                )

                run_start = t0
                run_end = t1
                run_visible = is_visible

        emit(
            run_start,
            run_end,
            run_visible,
        )

    # ---------------------------------------------
    # DEDUPLICAZIONE 2D
    #
    # SOLO ORA che conosciamo la profondità.
    # Le linee visibili hanno precedenza.
    # ---------------------------------------------

    key_tolerance = max(
        diagonal * 1e-7,
        1e-8,
    )

    unique_visible = {}

    for segment in visible_segments:

        key = _segment_key(
            segment,
            key_tolerance,
        )

        unique_visible[key] = segment

    unique_hidden = {}

    for segment in hidden_segments:

        key = _segment_key(
            segment,
            key_tolerance,
        )

        # Se nello stesso punto esiste già
        # geometria visibile, non mostriamo
        # la linea nascosta sottostante.
        if key in unique_visible:
            continue

        unique_hidden[key] = segment

    return MeshVisibilityResult(
        visible=list(
            unique_visible.values()
        ),

        hidden=list(
            unique_hidden.values()
        ),
    )