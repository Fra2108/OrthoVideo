from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.TopoDS import TopoDS_Shape


def get_bounding_box(shape: TopoDS_Shape):
    """
    Restituisce il bounding box geometrico del modello.
    """

    bbox = Bnd_Box()

    BRepBndLib.AddOptimal_s(
        shape,
        bbox,
    )

    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()

    return {
        "xmin": xmin,
        "ymin": ymin,
        "zmin": zmin,
        "xmax": xmax,
        "ymax": ymax,
        "zmax": zmax,
        "width_x": xmax - xmin,
        "width_y": ymax - ymin,
        "height_z": zmax - zmin,
    }