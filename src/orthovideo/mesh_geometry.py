from dataclasses import dataclass

import numpy as np
import trimesh


@dataclass(frozen=True)
class MeshInfo:
    vertices: int
    triangles: int
    components: int

    watertight: bool
    winding_consistent: bool

    minimum: tuple[float, float, float]
    maximum: tuple[float, float, float]

    size: tuple[float, float, float]


def get_mesh_info(
    mesh: trimesh.Trimesh,
) -> MeshInfo:

    bounds = np.asarray(
        mesh.bounds,
        dtype=float,
    )

    minimum = bounds[0]
    maximum = bounds[1]

    size = maximum - minimum

    # Componenti connesse della mesh.
    components = mesh.split(
        only_watertight=False
    )

    return MeshInfo(
        vertices=len(mesh.vertices),
        triangles=len(mesh.faces),
        components=len(components),

        watertight=bool(
            mesh.is_watertight
        ),

        winding_consistent=bool(
            mesh.is_winding_consistent
        ),

        minimum=tuple(
            float(v)
            for v in minimum
        ),

        maximum=tuple(
            float(v)
            for v in maximum
        ),

        size=tuple(
            float(v)
            for v in size
        ),
    )