from pathlib import Path

import numpy as np
import trimesh


def load_obj(
    file_path: str | Path,
) -> trimesh.Trimesh:
    """
    Carica un modello OBJ come mesh triangolare.

    A differenza dello STEP, qui non esiste una
    rappresentazione B-Rep esatta: lavoriamo sui
    triangoli della mesh.
    """

    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"File non trovato: {file_path}"
        )

    if file_path.suffix.lower() != ".obj":
        raise ValueError(
            f"Il file non è un OBJ: {file_path}"
        )

    loaded = trimesh.load(
        file_path,
        force="mesh",
        process=True,
    )

    if not isinstance(
        loaded,
        trimesh.Trimesh,
    ):
        raise RuntimeError(
            "Impossibile convertire l'OBJ "
            "in una singola mesh."
        )

    mesh = loaded

    if len(mesh.vertices) == 0:
        raise RuntimeError(
            "La mesh OBJ non contiene vertici."
        )

    if len(mesh.faces) == 0:
        raise RuntimeError(
            "La mesh OBJ non contiene facce."
        )

    if mesh.faces.shape[1] != 3:
        raise RuntimeError(
            "La mesh risultante non è triangolare."
        )

    if not np.all(
        np.isfinite(mesh.vertices)
    ):
        raise RuntimeError(
            "La mesh contiene coordinate non finite."
        )

    return mesh