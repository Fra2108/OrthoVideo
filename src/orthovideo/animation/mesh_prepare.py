from pathlib import Path

from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.StlAPI import StlAPI_Writer
from OCP.TopoDS import TopoDS_Shape
import trimesh


def export_step_render_mesh(
    shape: TopoDS_Shape,
    output_file: str | Path,
    *,
    linear_deflection: float = 0.10,
) -> Path:
    """
    Crea una mesh STL destinata esclusivamente
    alla visualizzazione/animazione Blender.

    Le proiezioni tecniche NON vengono ricavate
    da questa mesh.
    """

    output_file = Path(output_file)

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if shape.IsNull():
        raise ValueError(
            "Impossibile meshing di una shape nulla."
        )

    mesher = BRepMesh_IncrementalMesh(
        shape,
        linear_deflection,
    )

    mesher.Perform()

    if not mesher.IsDone():
        raise RuntimeError(
            "Tessellazione OpenCascade fallita."
        )

    writer = StlAPI_Writer()

    success = writer.Write(
        shape,
        str(output_file),
    )

    if not success:
        raise RuntimeError(
            f"Esportazione STL fallita: {output_file}"
        )

    if not output_file.exists():
        raise RuntimeError(
            f"STL non creato: {output_file}"
        )

    # Some CAD assemblies contain zero-area triangles along coincident seams.
    # They are irrelevant to the authoritative B-Rep projections but create
    # micro-islands and shading artefacts in Blender, so clean only the render
    # mesh after OCCT has written it.
    render_mesh = trimesh.load_mesh(output_file, process=False)

    if isinstance(render_mesh, trimesh.Scene):
        render_mesh = render_mesh.to_geometry()

    if not isinstance(render_mesh, trimesh.Trimesh):
        raise RuntimeError("STL Blender non interpretabile come mesh triangolare.")

    render_mesh.update_faces(render_mesh.nondegenerate_faces(height=1e-9))
    render_mesh.remove_unreferenced_vertices()
    render_mesh.export(output_file, file_type="stl")

    return output_file
