import bpy
import json
import math
import sys

from pathlib import Path
from mathutils import Vector


# ============================================================
# ARGOMENTI
# ============================================================

def get_job_file():
    if "--" not in sys.argv:
        raise RuntimeError(
            "Manca il separatore '--'."
        )

    args = sys.argv[
        sys.argv.index("--") + 1:
    ]

    if len(args) != 1:
        raise RuntimeError(
            "È richiesto un solo job JSON."
        )

    return Path(args[0]).resolve()


JOB_FILE = get_job_file()

job = json.loads(
    JOB_FILE.read_text(
        encoding="utf-8"
    )
)


# ============================================================
# RESET
# ============================================================

bpy.ops.object.select_all(
    action="SELECT"
)

bpy.ops.object.delete(
    use_global=False
)


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
        validate_meshes=True,
    )

else:

    raise RuntimeError(
        f"Formato non supportato: {suffix}"
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
# MATERIAL HELPER
# ============================================================

def create_principled_material(
    name,
    base_color,
    *,
    roughness=0.5,
    metallic=0.0,
    alpha=1.0,
):
    """
    Crea esplicitamente un materiale Principled BSDF.

    Non dipende dai nodi predefiniti creati
    automaticamente da Blender.
    """

    material = bpy.data.materials.new(
        name=name
    )

    # In Blender 5.1 funziona ancora.
    # È marcato per futura deprecazione in Blender 6,
    # ma non è un errore.
    material.use_nodes = True

    node_tree = material.node_tree

    if node_tree is None:
        raise RuntimeError(
            f"Impossibile creare node tree per: {name}"
        )

    nodes = node_tree.nodes
    links = node_tree.links

    # Partiamo sempre da zero.
    nodes.clear()

    output = nodes.new(
        "ShaderNodeOutputMaterial"
    )

    output.location = (
        300,
        0,
    )

    bsdf = nodes.new(
        "ShaderNodeBsdfPrincipled"
    )

    bsdf.location = (
        0,
        0,
    )

    bsdf.inputs["Base Color"].default_value = (
        base_color[0],
        base_color[1],
        base_color[2],
        alpha,
    )

    bsdf.inputs["Metallic"].default_value = (
        metallic
    )

    bsdf.inputs["Roughness"].default_value = (
        roughness
    )

    bsdf.inputs["Alpha"].default_value = (
        alpha
    )

    links.new(
        bsdf.outputs["BSDF"],
        output.inputs["Surface"],
    )

    # Necessario per materiali trasparenti.
    if alpha < 1.0:
        material.surface_render_method = "DITHERED"

    return material


# ============================================================
# MATERIALE MODELLO
# ============================================================

model_material = create_principled_material(
    "OrthoVideo Model",

    (
        0.48,
        0.51,
        0.55,
    ),

    roughness=0.48,
    metallic=0.0,
    alpha=1.0,
)


for obj in mesh_objects:

    obj.data.materials.clear()
    obj.data.materials.append(
        model_material
    )

    bpy.context.view_layer.objects.active = obj

    obj.select_set(True)

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
# BOUNDING BOX MONDO
# ============================================================

world_points = []

for obj in mesh_objects:

    for corner in obj.bound_box:

        world_points.append(
            obj.matrix_world
            @ Vector(corner)
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


# ============================================================
# SISTEMA DELLA VISTA
# ============================================================

normal = Vector(
    job["main_normal"]
).normalized()

up = Vector(
    job["main_up"]
)

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
).normalized()


# ============================================================
# ESTENSIONI DEL MODELLO NEL SISTEMA DELLA VISTA
# ============================================================

coords_r = []
coords_u = []
coords_n = []

for point in world_points:

    delta = point - center

    coords_r.append(
        delta.dot(right)
    )

    coords_u.append(
        delta.dot(up)
    )

    coords_n.append(
        delta.dot(normal)
    )


half_r = max(
    abs(min(coords_r)),
    abs(max(coords_r)),
)

half_u = max(
    abs(min(coords_u)),
    abs(max(coords_u)),
)

half_n = max(
    abs(min(coords_n)),
    abs(max(coords_n)),
)


largest = max(
    half_r,
    half_u,
    half_n,
    1.0,
)


# Margine geometrico fra modello e piani.
gap = largest * 0.45

plane_r = half_r * 1.20
plane_u = half_u * 1.20
plane_n = half_n * 1.20


front_distance = (
    half_n + gap
)

side_distance = (
    half_r + gap
)

vertical_distance = (
    half_u + gap
)


# ============================================================
# MATERIALE PIANI
# ============================================================

plane_material = create_principled_material(
    "Projection Plane",

    (
        0.32,
        0.55,
        0.75,
    ),

    roughness=0.65,
    metallic=0.0,
    alpha=0.18,
)


# ============================================================
# CREAZIONE RETTANGOLO 3D
# ============================================================

def create_plane(
    name,
    plane_center,
    axis_a,
    axis_b,
    half_a,
    half_b,
):

    a = axis_a.normalized() * half_a
    b = axis_b.normalized() * half_b

    vertices = [
        plane_center - a - b,
        plane_center + a - b,
        plane_center + a + b,
        plane_center - a + b,
    ]

    mesh = bpy.data.meshes.new(
        name + " Mesh"
    )

    mesh.from_pydata(
        [
            tuple(v)
            for v in vertices
        ],
        [],
        [
            (0, 1, 2, 3)
        ],
    )

    mesh.update()

    obj = bpy.data.objects.new(
        name,
        mesh,
    )

    bpy.context.scene.collection.objects.link(
        obj
    )

    obj.data.materials.append(
        plane_material
    )

    return obj


# ============================================================
# SEI PIANI
# ============================================================

planes = {}


planes["front"] = create_plane(
    "Plane FRONT",

    center
    + normal * front_distance,

    right,
    up,

    plane_r,
    plane_u,
)


planes["rear"] = create_plane(
    "Plane REAR",

    center
    - normal * front_distance,

    right,
    up,

    plane_r,
    plane_u,
)


planes["top"] = create_plane(
    "Plane TOP",

    center
    + up * vertical_distance,

    right,
    normal,

    plane_r,
    plane_n,
)


planes["bottom"] = create_plane(
    "Plane BOTTOM",

    center
    - up * vertical_distance,

    right,
    normal,

    plane_r,
    plane_n,
)


planes["right"] = create_plane(
    "Plane RIGHT",

    center
    + right * side_distance,

    normal,
    up,

    plane_n,
    plane_u,
)


planes["left"] = create_plane(
    "Plane LEFT",

    center
    - right * side_distance,

    normal,
    up,

    plane_n,
    plane_u,
)


# ============================================================
# BORDI DEI PIANI
# ============================================================

edge_material = create_principled_material(
    "Projection Plane Border",

    (
        0.18,
        0.30,
        0.42,
    ),

    roughness=0.60,
    metallic=0.0,
    alpha=1.0,
)

def add_plane_border(
    plane_object,
    thickness,
):

    vertices = [
        plane_object.matrix_world
        @ Vector(v.co)
        for v in plane_object.data.vertices
    ]

    for i in range(4):

        p1 = vertices[i]
        p2 = vertices[
            (i + 1) % 4
        ]

        delta = p2 - p1

        length = delta.length

        midpoint = (
            p1 + p2
        ) / 2.0

        bpy.ops.mesh.primitive_cylinder_add(
            vertices=12,
            radius=thickness,
            depth=length,
            location=midpoint,
        )

        cylinder = (
            bpy.context.active_object
        )

        cylinder.name = (
            plane_object.name
            + " Border"
        )

        cylinder.data.materials.append(
            edge_material
        )

        cylinder.rotation_euler = (
            delta
            .to_track_quat(
                "Z",
                "Y",
            )
            .to_euler()
        )

border_thickness = (
    largest * 0.006
)

for plane in planes.values():

    add_plane_border(
        plane,
        border_thickness,
    )


# ============================================================
# CAMERA OVERVIEW
# ============================================================

camera_data = bpy.data.cameras.new(
    "OrthoVideo Overview Camera"
)

camera_data.type = "PERSP"
camera_data.lens = 60.0

camera = bpy.data.objects.new(
    "OrthoVideo Overview Camera",
    camera_data,
)

bpy.context.scene.collection.objects.link(
    camera
)

camera.location = (
    center

    + normal
    * largest
    * 4.2

    + right
    * largest
    * 3.0

    + up
    * largest
    * 2.6
)

direction = (
    center
    - camera.location
)

camera.rotation_euler = (
    direction
    .to_track_quat(
        "-Z",
        "Y",
    )
    .to_euler()
)

camera_data.clip_start = 0.1
camera_data.clip_end = largest * 30.0

bpy.context.scene.camera = camera


# ============================================================
# LIGHTING
# ============================================================

def create_area_light(
    name,
    position,
    energy,
    size,
):

    data = bpy.data.lights.new(
        name=name,
        type="AREA",
    )

    data.energy = energy
    data.shape = "DISK"
    data.size = size

    light = bpy.data.objects.new(
        name,
        data,
    )

    bpy.context.scene.collection.objects.link(
        light
    )

    light.location = position

    direction = (
        center - position
    )

    light.rotation_euler = (
        direction
        .to_track_quat(
            "-Z",
            "Y",
        )
        .to_euler()
    )

    return light

create_area_light(
    "Key Light",

    center
    + normal * largest * 4
    + right * largest * 3
    + up * largest * 5,

    energy=max(
        largest * largest * 4,
        1000,
    ),

    size=largest * 3,
)

create_area_light(
    "Fill Light",

    center
    - right * largest * 4
    + up * largest * 2,

    energy=max(
        largest * largest * 2,
        500,
    ),

    size=largest * 3,
)


# ============================================================
# WORLD
# ============================================================

world = bpy.data.worlds.new(
    "OrthoVideo World"
)

world.use_nodes = True

bpy.context.scene.world = world

world_nodes = (
    world.node_tree.nodes
)

world_links = (
    world.node_tree.links
)

world_nodes.clear()

background = world_nodes.new(
    "ShaderNodeBackground"
)

background.inputs["Color"].default_value = (
    0.95,
    0.95,
    0.95,
    1.0,
)

background.inputs["Strength"].default_value = (
    0.7
)

world_output = world_nodes.new(
    "ShaderNodeOutputWorld"
)

world_links.new(
    background.outputs["Background"],
    world_output.inputs["Surface"],
)

# ============================================================
# RENDER
# ============================================================

scene = bpy.context.scene

scene.render.engine = "BLENDER_EEVEE"

scene.render.resolution_x = int(
    job.get(
        "resolution_x",
        1400,
    )
)

scene.render.resolution_y = int(
    job.get(
        "resolution_y",
        1000,
    )
)

scene.render.resolution_percentage = 100

scene.render.image_settings.file_format = "PNG"

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
    "ORTHOVIDEO_PROJECTION_BOX_OUTPUT="
    + str(output_file)
)

bpy.ops.render.render(
    write_still=True
)

blend_file = job.get(
    "blend_file"
)

if blend_file:

    bpy.ops.wm.save_as_mainfile(
        filepath=str(
            Path(
                blend_file
            ).resolve()
        )
    )

print(
    "ORTHOVIDEO_PROJECTION_BOX_OK"
)