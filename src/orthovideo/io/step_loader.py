from pathlib import Path

from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.TopoDS import TopoDS_Shape


def load_step(file_path: str | Path) -> TopoDS_Shape:
    """
    Carica un file STEP/STP e restituisce la geometria OpenCascade.

    Parameters
    ----------
    file_path:
        Percorso del file .step o .stp.

    Returns
    -------
    TopoDS_Shape
        Geometria B-Rep caricata tramite OpenCascade.

    Raises
    ------
    FileNotFoundError
        Se il file non esiste.

    ValueError
        Se l'estensione non è STEP/STP.

    RuntimeError
        Se OpenCascade non riesce a leggere o trasferire il modello.
    """

    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"File non trovato: {file_path}"
        )

    if file_path.suffix.lower() not in {".step", ".stp"}:
        raise ValueError(
            f"Formato non supportato: {file_path.suffix}"
        )

    reader = STEPControl_Reader()

    status = reader.ReadFile(str(file_path))

    if status != IFSelect_RetDone:
        raise RuntimeError(
            f"Impossibile leggere il file STEP: {file_path}"
        )

    transferred = reader.TransferRoots()

    if transferred == 0:
        raise RuntimeError(
            "Il file STEP è stato letto, "
            "ma nessuna geometria è stata trasferita."
        )

    shape = reader.OneShape()

    if shape.IsNull():
        raise RuntimeError(
            "OpenCascade ha restituito una geometria nulla."
        )

    return shape