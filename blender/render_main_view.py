import bpy
import json
import math
import sys

from pathlib import Path
from mathutils import Matrix, Vector


# ============================================================
# ARGUMENTI
# ============================================================

def get_job_file():

    if "--" not in sys.argv:
        raise RuntimeError(
            "Manca il separatore '--' negli argomenti Blender."
        )

    args = sys.argv[
        sys.argv.index("--") + 1:
    ]

    if len(args) != 1:
        raise RuntimeError(
            "È richiesto esattamente un file job JSON."
        )

    return Path(args[0]).resolve()


JOB_FILE = get_job_file()

job = json.loads(
    JOB_FILE.read_text(
        encoding="utf-8"
    )
)


# ============================================================
# RESET SCENA
# ============================================================

bpy.ops.object.select_all(
    action="SELECT"
)

bpy.ops.object.delete(
    use_global=False
)

for datablocks in (
    bpy.data.meshes,
    bpy.data.curves,
    bpy.data.materials,
    bpy.data.cameras,
    bpy.data.lights,
):
    # Non forziamo la rimozione:
    # alcuni datablock possono ancora essere referenziati.
    pass


# ============================================================
# IMPORT MODELLO
# ============================================================

model_file = Path(
    job["model_mesh"]
).resolve()

suffix = model_file.suffix.lower()

if suffix == ".stl":

    bpy.ops.wm.stl_import(
        filepath=str(model_file),

        # Coordinate sorgente già coerenti con Blender:
        # Z verticale, -Y convenzione forward.
        forward_axis="NEGATIVE_Y",
        up_axis="Z",

        use_scene_unit=False,
        use_mesh_validate=True,
    )

elif suffix == ".obj":

    bpy.ops.wm.obj_import(
        filepath=str(model_file),

        forward_axis="NEGATIVE_Y",
        up_axis="Z",

        global_scale=1.0,

        use_split_objects=True,
        use_split_groups=False,

        validate_meshes=True,
    )

else:

    raise RuntimeError(
        f"Formato Blender non supportato: {suffix}"
    )


mesh_objects = [
    obj
    for obj in bpy.context.scene.objects
    if obj.type == "MESH"
]

if not mesh_objects:
    raise RuntimeError(
        "Nessuna mesh importata."
    )


# ============================================================
# MATERIALI E SHADING
# ============================================================

neutral_material = bpy.data.materials.new(
    name="OrthoVideo Neutral"
)

neutral_material.use_nodes = True

bsdf = (
    neutral_material
    .node_tree
    .nodes
    .get("Principled BSDF")
)

if bsdf is not None:

    bsdf.inputs["Base Color"].default_value = (
        0.55,
        0.58,
        0.62,
        1.0,
    )

    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 0.55


for obj in mesh_objects:

    obj.data.materials.clear()
    obj.data.materials.append(
        neutral_material
    )

    bpy.context.view_layer.objects.active = obj

    obj.select_set(True)

    # Superfici dolci sulle zone quasi continue,
    # ma spigoli meccanici conservati.
    try:
        bpy.ops.object.shade_smooth_by_angle(
            angle=math.radians(30.0),
            keep_sharp_edges=True,
        )
    except Exception:
        bpy.ops.object.shade_smooth(
            keep_sharp_edges=True
        )

    obj.select_set(False)


# ============================================================
# BOUNDING BOX COMPLESSIVO
# ============================================================

world_points = []

for obj in mesh_objects:

    for corner in obj.bound_box:

        point = (
            obj.matrix_world
            @ Vector(corner)
        )

        world_points.append(
            point
        )


xmin = min(p.x for p in world_points)
xmax = max(p.x for p in world_points)

ymin = min(p.y for p in world_points)
ymax = max(p.y for p in world_points)

zmin = min(p.z for p in world_points)
zmax = max(p.z for p in world_points)


center = Vector(
    (
        (xmin + xmax) / 2.0,
        (ymin + ymax) / 2.0,
        (zmin + zmax) / 2.0,
    )
)


size = Vector(
    (
        xmax - xmin,
        ymax - ymin,
        zmax - zmin,
    )
)

diagonal = max(
    size.length,
    1.0,
)


# ============================================================
# SISTEMA DELLA VISTA PRINCIPALE
# ============================================================

normal = Vector(
    job["main_normal"]
).normalized()

up = Vector(
    job["main_up"]
)

# Garantiamo ortogonalità.
up = (
    up
    - normal
    * up.dot(normal)
)

if up.length < 1e-8:
    raise RuntimeError(
        "main_up parallelo a main_normal."
    )

up.normalize()

right = (
    up.cross(normal)
)

right.normalize()


# ============================================================
# CAMERA ORTOGRAFICA
# ============================================================

camera_data = bpy.data.cameras.new(
    "OrthoVideo Camera"
)

camera_data.type = "ORTHO"

camera = bpy.data.objects.new(
    "OrthoVideo Camera",
    camera_data,
)

bpy.context.scene.collection.objects.link(
    camera
)

camera_distance = (
    diagonal * 2.5
)

camera.location = (
    center
    + normal * camera_distance
)


# La camera Blender guarda lungo il proprio asse locale -Z.
#
# Vogliamo:
#
# local X = right della vista
# local Y = up della vista
# local Z = verso osservatore = normal
#
basis = Matrix(
    (
        right,
        up,
        normal,
    )
).transposed()

camera.rotation_euler = (
    basis.to_euler()
)


# ============================================================
# FIT DEL MODELLO NELLA CAMERA
# ============================================================

projected_x = []
projected_y = []

for point in world_points:

    delta = (
        point - center
    )

    projected_x.append(
        delta.dot(right)
    )

    projected_y.append(
        delta.dot(up)
    )


view_width = (
    max(projected_x)
    - min(projected_x)
)

view_height = (
    max(projected_y)
    - min(projected_y)
)


resolution_x = int(
    job.get(
        "resolution_x",
        1200,
    )
)

resolution_y = int(
    job.get(
        "resolution_y",
        900,
    )
)

aspect = (
    resolution_x
    / resolution_y
)


required_vertical = max(
    view_height,
    view_width / aspect,
)

camera_data.ortho_scale = (
    required_vertical
    * 1.20
)

camera_data.clip_start = max(
    diagonal * 0.001,
    0.001,
)

camera_data.clip_end = (
    camera_distance
    + diagonal * 5.0
)

bpy.context.scene.camera = camera


# ============================================================
# ILLUMINAZIONE
# ============================================================

def create_area_light(
    name,
    position,
    energy,
    size,
):

    light_data = bpy.data.lights.new(
        name=name,
        type="AREA",
    )

    light_data.energy = energy
    light_data.shape = "DISK"
    light_data.size = size

    light = bpy.data.objects.new(
        name,
        light_data,
    )

    bpy.context.scene.collection.objects.link(
        light
    )

    light.location = position

    direction = (
        center - position
    )

    light.rotation_euler = (
        direction.to_track_quat(
            "-Z",
            "Y",
        ).to_euler()
    )

    return light

create_area_light(
    "Key Light",

    center
    + normal * diagonal
    + right * diagonal
    + up * diagonal,

    energy=max(
        diagonal * diagonal * 3.0,
        500.0,
    ),

    size=diagonal,
)

create_area_light(
    "Fill Light",

    center
    + normal * diagonal * 0.5
    - right * diagonal
    + up * diagonal * 0.4,

    energy=max(
        diagonal * diagonal * 1.5,
        250.0,
    ),

    size=diagonal * 1.2,
)

# ============================================================
# WORLD
# ============================================================

world = bpy.data.worlds.new(
    "OrthoVideo World"
)

bpy.context.scene.world = world

world.use_nodes = True

background = (
    world.node_tree
    .nodes
    .get("Background")
)

if background is not None:

    background.inputs["Color"].default_value = (
        0.94,
        0.94,
        0.94,
        1.0,
    )

    background.inputs["Strength"].default_value = 0.7

# ============================================================
# RENDER
# ============================================================

scene = bpy.context.scene

scene.render.resolution_x = resolution_x
scene.render.resolution_y = resolution_y
scene.render.resolution_percentage = 100

scene.render.image_settings.file_format = "PNG"

scene.render.film_transparent = False

# Metricamente consideriamo le coordinate come millimetri.
scene.unit_settings.system = "METRIC"
scene.unit_settings.length_unit = "MILLIMETERS"
scene.unit_settings.scale_length = 0.001

output_file = Path(
    job["output_file"]
).resolve()

output_file.parent.mkdir(
    parents=True,
    exist_ok=True,
)

scene.render.filepath = str(
    output_file
)

print(
    "ORTHOVIDEO_RENDER_MODEL="
    + str(model_file)
)

print(
    "ORTHOVIDEO_RENDER_OUTPUT="
    + str(output_file)
)

print(
    "ORTHOVIDEO_CAMERA_NORMAL="
    + str(tuple(normal))
)

bpy.ops.render.render(
    write_still=True
)

# Salviamo anche il .blend di debug.
blend_file = job.get(
    "blend_file"
)

if blend_file:

    bpy.ops.wm.save_as_mainfile(
        filepath=str(
            Path(blend_file).resolve()
        )
    )

print("ORTHOVIDEO_RENDER_OK")