import bpy
import json
import math
import sys

from pathlib import Path
from mathutils import Matrix, Vector


VIEW_NAMES = ("front", "rear", "top", "bottom", "right", "left")
EXPECTED_PHYSICAL_FACES = {
    "front": "-Z",
    "rear": "+Z",
    "right": "-X",
    "left": "+X",
    "top": "-Y",
    "bottom": "+Y",
}
EXPECTED_PARENTS = {
    "front": None,
    "right": "front",
    "left": "front",
    "top": "front",
    "bottom": "front",
    "rear": "left",
}
EXPECTED_UNFOLD_DEGREES = {
    "right": -90.0,
    "left": 90.0,
    "top": 90.0,
    "bottom": -90.0,
    "rear": 90.0,
}


def get_job_file():
    if "--" not in sys.argv:
        raise RuntimeError("Manca il separatore '--'.")

    args = sys.argv[sys.argv.index("--") + 1 :]

    if len(args) != 1:
        raise RuntimeError("È richiesto un solo job JSON.")

    return Path(args[0]).resolve()


def create_principled_material(
    name,
    color,
    *,
    roughness=0.5,
    metallic=0.0,
    alpha=1.0,
    ambient_occlusion_distance=None,
):
    material = bpy.data.materials.new(name=name)
    material.use_nodes = True
    node_tree = material.node_tree

    if node_tree is None:
        raise RuntimeError(f"Impossibile creare node tree per {name}.")

    nodes = node_tree.nodes
    links = node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*color, alpha)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Alpha"].default_value = alpha

    # A subtle material-space AO pass makes holes, shoulders and raccords
    # readable even while the model is enclosed by translucent projection
    # planes.  Unsupported render backends simply keep the flat base color.
    if ambient_occlusion_distance is not None:
        try:
            ambient_occlusion = nodes.new("ShaderNodeAmbientOcclusion")
            ambient_occlusion.inputs["Color"].default_value = (*color, 1.0)
            ambient_occlusion.inputs["Distance"].default_value = float(
                ambient_occlusion_distance
            )
            links.new(
                ambient_occlusion.outputs["Color"],
                bsdf.inputs["Base Color"],
            )
        except Exception:
            pass

    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.38
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    material.diffuse_color = (*color, alpha)

    if alpha < 1.0:
        material.surface_render_method = "DITHERED"

    return material, bsdf


def import_model(model_file):
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
        raise RuntimeError(f"Formato mesh Blender non supportato: {suffix}")

    result = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]

    if not result:
        raise RuntimeError("Nessuna mesh importata.")

    return result


def view_basis(data):
    normal = Vector(data["normal"]).normalized()
    up = Vector(data["up"])
    up = up - normal * up.dot(normal)

    if up.length < 1e-8:
        raise RuntimeError("Vettori normal/up non validi nel job.")

    up.normalize()
    axis_x = up.cross(normal).normalized()
    return axis_x, up, normal


def basis_quaternion(axis_x, axis_y, axis_z):
    return Matrix((axis_x, axis_y, axis_z)).transposed().to_quaternion()


def create_empty(name, parent, location, rotation=None):
    obj = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = parent
    obj.location = Vector(location)

    if rotation is not None:
        obj.rotation_mode = "QUATERNION"
        obj.rotation_quaternion = rotation

    return obj


def create_plane_mesh(name, width, height, material, root):
    vertices = [
        (-width / 2.0, -height / 2.0, 0.0),
        (width / 2.0, -height / 2.0, 0.0),
        (width / 2.0, height / 2.0, 0.0),
        (-width / 2.0, height / 2.0, 0.0),
    ]
    mesh = bpy.data.meshes.new(name + " Mesh")
    mesh.from_pydata(vertices, [], [(0, 1, 2, 3)])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(material)
    obj.parent = root
    return obj


def create_curve_object(
    name,
    polylines,
    material,
    bevel_depth,
    root,
    z_offset,
    *,
    cyclic=False,
):
    usable = [line for line in polylines if len(line) >= 2]

    if not usable:
        return None

    curve = bpy.data.curves.new(name=name, type="CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 1
    curve.bevel_depth = bevel_depth
    curve.bevel_resolution = 2

    for points in usable:
        spline = curve.splines.new("POLY")
        spline.points.add(len(points) - 1)

        for target, point in zip(spline.points, points):
            target.co = (point[0], point[1], z_offset, 1.0)

        spline.use_cyclic_u = cyclic

    obj = bpy.data.objects.new(name, curve)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(material)
    obj.parent = root
    return obj


def patterned_polyline(points, pattern):
    """Create strokes with one continuous pattern phase along the polyline."""
    if len(points) < 2:
        return []

    if not pattern or any(length <= 0.0 for length, _ in pattern):
        raise RuntimeError("Pattern linea Blender non valido.")

    pieces = []
    active_piece = None
    pattern_index = 0
    pattern_remaining = float(pattern[0][0])
    epsilon = 1e-9

    for p1, p2 in zip(points, points[1:]):
        a = Vector((p1[0], p1[1]))
        b = Vector((p2[0], p2[1]))
        delta = b - a
        length = delta.length

        if length < epsilon:
            continue

        direction = delta / length
        cursor = 0.0

        while cursor < length - epsilon:
            step = min(pattern_remaining, length - cursor)
            is_drawn = bool(pattern[pattern_index][1])

            if is_drawn and step > epsilon:
                start = a + direction * cursor
                end = a + direction * (cursor + step)
                start_tuple = (start.x, start.y)
                end_tuple = (end.x, end.y)

                if active_piece is None:
                    active_piece = [start_tuple, end_tuple]
                    pieces.append(active_piece)
                elif (Vector(active_piece[-1]) - start).length <= epsilon * 10.0:
                    active_piece.append(end_tuple)
                else:
                    active_piece = [start_tuple, end_tuple]
                    pieces.append(active_piece)

            cursor += step
            pattern_remaining -= step

            if pattern_remaining <= epsilon:
                pattern_index = (pattern_index + 1) % len(pattern)
                pattern_remaining = float(pattern[pattern_index][0])
                active_piece = None

    return pieces


def create_curve_batches(
    name_prefix,
    source_lines,
    point_offset,
    material,
    bevel_depth,
    root,
    z_offset,
    *,
    pattern=None,
    max_splines=512,
):
    """Batch thousands of source lines without one Blender object per dash."""
    result = []
    batch = []
    batch_index = 0

    def flush():
        nonlocal batch, batch_index

        if not batch:
            return

        obj = create_curve_object(
            f"{name_prefix} Batch {batch_index:04d}",
            batch,
            material,
            bevel_depth,
            root,
            z_offset,
        )

        if obj is not None:
            result.append(obj)

        batch = []
        batch_index += 1

    for source_line in source_lines:
        local_line = [
            (point[0] - point_offset[0], point[1] - point_offset[1])
            for point in source_line
        ]
        pieces = [local_line] if pattern is None else patterned_polyline(
            local_line,
            pattern,
        )

        for piece in pieces:
            if len(piece) < 2:
                continue

            if len(batch) >= max_splines:
                flush()

            batch.append(piece)

    flush()
    return result


def create_hinge(name, parent, location, parent_view, end_degrees):
    hinge = create_empty(name, parent, location)
    hinge.rotation_mode = "XYZ"
    hinge.rotation_euler = (0.0, 0.0, 0.0)
    hinge["orthovideo_parent_view"] = parent_view
    hinge["orthovideo_end_degrees"] = float(end_degrees)
    return hinge


def animate_hinge(
    hinge,
    axis_index,
    end_degrees,
    frame_start,
    unfold_start,
    unfold_end,
    frame_end,
):
    end_angle = math.radians(float(end_degrees))

    for frame, value in (
        (frame_start, 0.0),
        (unfold_start, 0.0),
        (unfold_end, end_angle),
        (frame_end, end_angle),
    ):
        hinge.rotation_euler[axis_index] = value
        hinge.keyframe_insert(
            data_path="rotation_euler",
            index=axis_index,
            frame=frame,
        )

    # Blender 5.1 uses layered/slotted Actions and no longer exposes Action.fcurves
    # directly. Older versions do, so keep the linear interpolation optimization
    # where available without depending on the legacy API.
    action = hinge.animation_data.action if hinge.animation_data else None

    if action is not None:
        for fcurve in getattr(action, "fcurves", ()):
            for keyframe in fcurve.keyframe_points:
                keyframe.interpolation = "LINEAR"


def validated_rig(job):
    rig = job.get(
        "rig",
        {
            "type": "contiguous_first_angle_box",
            "physical_faces": EXPECTED_PHYSICAL_FACES,
            "parents": EXPECTED_PARENTS,
            "unfold_degrees": EXPECTED_UNFOLD_DEGREES,
            "box_clearance_ratio": 0.12,
        },
    )

    if rig.get("type") != "contiguous_first_angle_box":
        raise RuntimeError("Rig animazione non supportato.")

    if rig.get("physical_faces") != EXPECTED_PHYSICAL_FACES:
        raise RuntimeError("Disposizione fisica first-angle non valida.")

    if rig.get("parents") != EXPECTED_PARENTS:
        raise RuntimeError("Gerarchia first-angle non valida.")

    degrees = {
        name: float(value)
        for name, value in rig.get("unfold_degrees", {}).items()
    }

    if degrees != EXPECTED_UNFOLD_DEGREES:
        raise RuntimeError("Angoli unfolding first-angle non validi.")

    clearance_ratio = float(rig.get("box_clearance_ratio", 0.12))

    if not 0.01 <= clearance_ratio <= 0.5:
        raise RuntimeError("box_clearance_ratio non valido.")

    return rig, degrees, clearance_ratio


def track_quaternion(location, target):
    return (target - location).to_track_quat("-Z", "Y")


def create_area_light(
    name,
    location,
    target,
    energy,
    size,
    *,
    color=(1.0, 1.0, 1.0),
):
    data = bpy.data.lights.new(name=name, type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = color
    data.use_shadow = True
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = track_quaternion(location, target).to_euler()
    return obj


def world_edge(root, first, second):
    return root.matrix_world @ Vector(first), root.matrix_world @ Vector(second)


def assert_same_edge(label, first_edge, second_edge, tolerance):
    a1, a2 = first_edge
    b1, b2 = second_edge
    direct = (a1 - b1).length <= tolerance and (a2 - b2).length <= tolerance
    reverse = (a1 - b2).length <= tolerance and (a2 - b1).length <= tolerance

    if not (direct or reverse):
        raise RuntimeError(f"Pannelli non contigui sul bordo {label}.")


def validate_scene_rig(
    scene,
    box_root,
    view_roots,
    half_x,
    half_y,
    half_z,
    unfold_start,
    unfold_end,
    largest,
):
    tolerance = max(largest * 1e-5, 1e-5)
    scene.frame_set(unfold_start)
    bpy.context.view_layer.update()

    closed_edges = (
        (
            "FRONT-RIGHT",
            world_edge(view_roots["front"], (-half_x, -half_y, 0), (-half_x, half_y, 0)),
            world_edge(view_roots["right"], (half_z, -half_y, 0), (half_z, half_y, 0)),
        ),
        (
            "FRONT-LEFT",
            world_edge(view_roots["front"], (half_x, -half_y, 0), (half_x, half_y, 0)),
            world_edge(view_roots["left"], (-half_z, -half_y, 0), (-half_z, half_y, 0)),
        ),
        (
            "FRONT-TOP",
            world_edge(view_roots["front"], (-half_x, -half_y, 0), (half_x, -half_y, 0)),
            world_edge(view_roots["top"], (-half_x, half_z, 0), (half_x, half_z, 0)),
        ),
        (
            "FRONT-BOTTOM",
            world_edge(view_roots["front"], (-half_x, half_y, 0), (half_x, half_y, 0)),
            world_edge(view_roots["bottom"], (-half_x, -half_z, 0), (half_x, -half_z, 0)),
        ),
        (
            "LEFT-REAR",
            world_edge(view_roots["left"], (half_z, -half_y, 0), (half_z, half_y, 0)),
            world_edge(view_roots["rear"], (-half_x, -half_y, 0), (-half_x, half_y, 0)),
        ),
    )

    for label, first_edge, second_edge in closed_edges:
        assert_same_edge(label, first_edge, second_edge, tolerance)

    scene.frame_set(unfold_end)
    bpy.context.view_layer.update()
    front_normal = (
        view_roots["front"].matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))
    ).normalized()

    for name, root in view_roots.items():
        normal = (root.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()

        if normal.dot(front_normal) < 1.0 - 1e-6:
            raise RuntimeError(f"Vista {name} non coplanare dopo l'unfolding.")

    expected_centers = {
        "front": Vector((0.0, 0.0, -half_z)),
        "right": Vector((-half_x - half_z, 0.0, -half_z)),
        "left": Vector((half_x + half_z, 0.0, -half_z)),
        "rear": Vector((2.0 * half_x + 2.0 * half_z, 0.0, -half_z)),
        "top": Vector((0.0, -half_y - half_z, -half_z)),
        "bottom": Vector((0.0, half_y + half_z, -half_z)),
    }
    inverse_box = box_root.matrix_world.inverted()

    for name, expected in expected_centers.items():
        actual = inverse_box @ view_roots[name].matrix_world.translation

        if (actual - expected).length > tolerance:
            raise RuntimeError(
                f"Centro finale first-angle errato per {name}: {tuple(actual)}"
            )

    print("ORTHOVIDEO_FIRST_ANGLE_RIG_OK")


JOB_FILE = get_job_file()
job = json.loads(JOB_FILE.read_text(encoding="utf-8"))

if job.get("schema_version") != 1:
    raise RuntimeError("Versione job Blender non supportata.")

rig, unfold_degrees, clearance_ratio = validated_rig(job)

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

try:
    bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
except Exception:
    pass

model_objects = import_model(Path(job["model_mesh"]).resolve())
world_points = [
    obj.matrix_world @ Vector(corner)
    for obj in model_objects
    for corner in obj.bound_box
]

main_data = {"normal": job["main_normal"], "up": job["main_up"]}
main_x, main_y, main_z = view_basis(main_data)
main_rotation = basis_quaternion(main_x, main_y, main_z)
coordinates = [
    Vector((point.dot(main_x), point.dot(main_y), point.dot(main_z)))
    for point in world_points
]
raw_min = Vector(
    (
        min(point.x for point in coordinates),
        min(point.y for point in coordinates),
        min(point.z for point in coordinates),
    )
)
raw_max = Vector(
    (
        max(point.x for point in coordinates),
        max(point.y for point in coordinates),
        max(point.z for point in coordinates),
    )
)
raw_size = raw_max - raw_min
largest = max(raw_size.x, raw_size.y, raw_size.z, 1.0)
clearance = largest * clearance_ratio
box_min = raw_min - Vector((clearance, clearance, clearance))
box_max = raw_max + Vector((clearance, clearance, clearance))
box_center_coordinates = (box_min + box_max) / 2.0
box_center = (
    main_x * box_center_coordinates.x
    + main_y * box_center_coordinates.y
    + main_z * box_center_coordinates.z
)
half_x, half_y, half_z = (box_max - box_min) / 2.0

model_material, _ = create_principled_material(
    "OrthoVideo Model",
    (0.34, 0.41, 0.50),
    roughness=0.30,
    metallic=0.03,
    alpha=1.0,
    ambient_occlusion_distance=largest * 0.10,
)
model_material["orthovideo_visual_profile"] = "technical_contrast_v2"

for obj in model_objects:
    obj.data.materials.clear()
    obj.data.materials.append(model_material)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    try:
        bpy.ops.object.shade_smooth_by_angle(
            angle=math.radians(24.0),
            keep_sharp_edges=True,
        )
    except Exception:
        bpy.ops.object.shade_smooth(keep_sharp_edges=True)

    obj.select_set(False)

plane_material, _ = create_principled_material(
    "Projection Plane",
    (0.70, 0.82, 0.92),
    roughness=0.70,
    alpha=0.20,
)
border_material, _ = create_principled_material(
    "Projection Plane Border",
    (0.18, 0.32, 0.45),
    roughness=0.55,
)
visible_material, _ = create_principled_material(
    "Visible Projection",
    (0.025, 0.045, 0.065),
    roughness=0.45,
)
hidden_material, _ = create_principled_material(
    "Hidden Projection",
    (0.24, 0.30, 0.36),
    roughness=0.55,
)
center_material, _ = create_principled_material(
    "Center Projection",
    (0.05, 0.30, 0.50),
    roughness=0.48,
)
tangent_material, _ = create_principled_material(
    "Tangent Projection",
    (0.30, 0.36, 0.42),
    roughness=0.55,
)
hatch_material, _ = create_principled_material(
    "Section Hatching",
    (0.18, 0.22, 0.26),
    roughness=0.55,
)
section_cut_material, _ = create_principled_material(
    "Section Cut",
    (0.05, 0.10, 0.14),
    roughness=0.48,
)
label_material, _ = create_principled_material(
    "View Labels",
    (0.12, 0.18, 0.24),
    roughness=0.55,
)

timing = job["timing"]
frame_start = int(timing["frame_start"])
draw_start = int(timing["draw_start"])
draw_end = int(timing["draw_end"])
unfold_start = int(timing["unfold_start"])
unfold_end = int(timing["unfold_end"])
frame_end = int(timing["frame_end"])

render_data = job["render"]
expected_view_normals = {
    "front": Vector((0.0, 0.0, 1.0)),
    "rear": Vector((0.0, 0.0, -1.0)),
    "right": Vector((1.0, 0.0, 0.0)),
    "left": Vector((-1.0, 0.0, 0.0)),
    "top": Vector((0.0, 1.0, 0.0)),
    "bottom": Vector((0.0, -1.0, 0.0)),
}
view_axes = {}

for name in VIEW_NAMES:
    axis_x, axis_y, axis_normal = view_basis(job["views"][name])
    local_axes = tuple(
        Vector((axis.dot(main_x), axis.dot(main_y), axis.dot(main_z)))
        for axis in (axis_x, axis_y, axis_normal)
    )

    if (local_axes[2] - expected_view_normals[name]).length > 1e-6:
        raise RuntimeError(f"Base della vista {name} incompatibile con first-angle.")

    view_axes[name] = (axis_x, axis_y, axis_normal, *local_axes)

box_root = create_empty("Projection Box Basis", None, box_center, main_rotation)
box_root["orthovideo_basis"] = "X=right,Y=up,Z=normal"
box_root["orthovideo_clearance"] = clearance

right_hinge = create_hinge(
    "Hinge FRONT-RIGHT",
    box_root,
    (-half_x, 0.0, -half_z),
    "front",
    unfold_degrees["right"],
)
left_hinge = create_hinge(
    "Hinge FRONT-LEFT",
    box_root,
    (half_x, 0.0, -half_z),
    "front",
    unfold_degrees["left"],
)
top_hinge = create_hinge(
    "Hinge FRONT-TOP",
    box_root,
    (0.0, -half_y, -half_z),
    "front",
    unfold_degrees["top"],
)
bottom_hinge = create_hinge(
    "Hinge FRONT-BOTTOM",
    box_root,
    (0.0, half_y, -half_z),
    "front",
    unfold_degrees["bottom"],
)
rear_hinge = create_hinge(
    "Hinge LEFT-REAR",
    left_hinge,
    (0.0, 0.0, 2.0 * half_z),
    "left",
    unfold_degrees["rear"],
)

for hinge, axis_index, view_name in (
    (right_hinge, 1, "right"),
    (left_hinge, 1, "left"),
    (top_hinge, 0, "top"),
    (bottom_hinge, 0, "bottom"),
    (rear_hinge, 1, "rear"),
):
    animate_hinge(
        hinge,
        axis_index,
        unfold_degrees[view_name],
        frame_start,
        unfold_start,
        unfold_end,
        frame_end,
    )

view_parent_and_location = {
    "front": (box_root, (0.0, 0.0, -half_z)),
    "right": (right_hinge, (0.0, 0.0, half_z)),
    "left": (left_hinge, (0.0, 0.0, half_z)),
    "top": (top_hinge, (0.0, 0.0, half_z)),
    "bottom": (bottom_hinge, (0.0, 0.0, half_z)),
    "rear": (rear_hinge, (-half_x, 0.0, 0.0)),
}
view_sizes = {
    "front": (2.0 * half_x, 2.0 * half_y),
    "rear": (2.0 * half_x, 2.0 * half_y),
    "right": (2.0 * half_z, 2.0 * half_y),
    "left": (2.0 * half_z, 2.0 * half_y),
    "top": (2.0 * half_x, 2.0 * half_z),
    "bottom": (2.0 * half_x, 2.0 * half_z),
}
view_roots = {}

for name in VIEW_NAMES:
    parent, location = view_parent_and_location[name]
    _, _, _, local_x, local_y, local_normal = view_axes[name]
    root = create_empty(
        "View " + name.upper(),
        parent,
        location,
        basis_quaternion(local_x, local_y, local_normal),
    )
    root["orthovideo_view"] = name
    root["orthovideo_physical_face"] = EXPECTED_PHYSICAL_FACES[name]
    view_roots[name] = root

line_styles = job.get("line_styles", {})
visible_style = line_styles.get("visible", {})
hidden_style = line_styles.get("hidden", {})
center_style = line_styles.get("center", {})
tangent_style = line_styles.get("tangent", {})
hatch_style = line_styles.get("hatch", {})
section_cut_style = line_styles.get("section_cut", {})
visible_radius = largest * float(visible_style.get("width_ratio", 0.0042))
hidden_radius = largest * float(hidden_style.get("width_ratio", 0.0026))
center_radius = largest * float(center_style.get("width_ratio", 0.0022))
tangent_radius = largest * float(tangent_style.get("width_ratio", 0.0018))
hatch_radius = largest * float(hatch_style.get("width_ratio", 0.0014))
section_cut_radius = largest * float(section_cut_style.get("width_ratio", 0.0038))
hidden_ratios = hidden_style.get("pattern_ratios", [0.065, 0.032])
center_ratios = center_style.get(
    "pattern_ratios",
    [0.10, 0.025, 0.010, 0.025],
)

if len(hidden_ratios) != 2 or len(center_ratios) != 4:
    raise RuntimeError("Pattern linee del job non valido.")

hidden_pattern = [
    (largest * float(hidden_ratios[0]), True),
    (largest * float(hidden_ratios[1]), False),
]
center_pattern = [
    (largest * float(center_ratios[0]), True),
    (largest * float(center_ratios[1]), False),
    (largest * float(center_ratios[2]), True),
    (largest * float(center_ratios[3]), False),
]
border_radius = largest * 0.0032
z_offset = largest * 0.0022
curve_objects = []
labels = {}

for name in VIEW_NAMES:
    data = job["views"][name]
    root = view_roots[name]
    width, height = view_sizes[name]
    axis_x, axis_y, _, _, _, _ = view_axes[name]
    point_offset = (box_center.dot(axis_x), box_center.dot(axis_y))

    create_plane_mesh("Plane " + name.upper(), width, height, plane_material, root)
    border = [
        (-width / 2.0, -height / 2.0),
        (width / 2.0, -height / 2.0),
        (width / 2.0, height / 2.0),
        (-width / 2.0, height / 2.0),
    ]
    create_curve_object(
        "Border " + name.upper(),
        [border],
        border_material,
        border_radius,
        root,
        z_offset * 0.5,
        cyclic=True,
    )
    curve_objects.extend(
        create_curve_batches(
            "Visible " + name.upper(),
            data.get("visible", []),
            point_offset,
            visible_material,
            visible_radius,
            root,
            z_offset,
        )
    )
    curve_objects.extend(
        create_curve_batches(
            "Tangent " + name.upper(),
            data.get("tangent", []),
            point_offset,
            tangent_material,
            tangent_radius,
            root,
            z_offset,
        )
    )
    curve_objects.extend(
        create_curve_batches(
            "Hidden " + name.upper(),
            data.get("hidden", []),
            point_offset,
            hidden_material,
            hidden_radius,
            root,
            z_offset,
            pattern=hidden_pattern,
        )
    )
    curve_objects.extend(
        create_curve_batches(
            "Center " + name.upper(),
            data.get("center", []),
            point_offset,
            center_material,
            center_radius,
            root,
            z_offset,
            pattern=center_pattern,
        )
    )

    annotations_by_role = {}

    for annotation in data.get("annotations", []):
        role = str(annotation.get("role", "")).upper()
        points = annotation.get("points", [])

        if len(points) >= 2:
            annotations_by_role.setdefault(role, []).append(points)

    for role, source_lines in annotations_by_role.items():
        if role == "HATCH":
            material = hatch_material
            radius = hatch_radius
            pattern = None
        elif role == "SECTION_CUT":
            material = section_cut_material
            radius = section_cut_radius
            pattern = None
        elif role in {"SYMMETRY", "PITCH", "CENTER"}:
            material = center_material
            radius = center_radius
            pattern = center_pattern
        else:
            material = tangent_material
            radius = tangent_radius
            pattern = None

        curve_objects.extend(
            create_curve_batches(
                f"Annotation {role} {name.upper()}",
                source_lines,
                point_offset,
                material,
                radius,
                root,
                z_offset * 1.05,
                pattern=pattern,
            )
        )

    if bool(render_data.get("show_labels", False)):
        text_data = bpy.data.curves.new("Label " + name.upper(), type="FONT")
        text_data.body = name.upper()
        text_data.align_x = "CENTER"
        text_data.align_y = "CENTER"
        text_data.size = largest * 0.075
        text_data.extrude = largest * 0.0008
        text_obj = bpy.data.objects.new("Label " + name.upper(), text_data)
        bpy.context.scene.collection.objects.link(text_obj)
        text_obj.data.materials.append(label_material)
        text_obj.parent = root
        text_obj.location = (0.0, -height / 2.0 - largest * 0.10, z_offset)
        labels[name] = text_obj

fps = int(render_data["fps"])
reveal_duration = max(3, round(fps * 0.22))
reveal_span = max(draw_end - draw_start - reveal_duration, 0)

for index, curve_obj in enumerate(curve_objects):
    fraction = index / max(len(curve_objects) - 1, 1)
    reveal_frame = draw_start + round(reveal_span * fraction)
    curve_obj.data.bevel_factor_end = 0.0
    curve_obj.data.keyframe_insert(
        data_path="bevel_factor_end",
        frame=max(frame_start, reveal_frame - 1),
    )
    curve_obj.data.bevel_factor_end = 1.0
    curve_obj.data.keyframe_insert(
        data_path="bevel_factor_end",
        frame=min(draw_end, reveal_frame + reveal_duration),
    )

scene = bpy.context.scene
validate_scene_rig(
    scene,
    box_root,
    view_roots,
    half_x,
    half_y,
    half_z,
    unfold_start,
    unfold_end,
    largest,
)

# Final first-angle net: RIGHT-FRONT-LEFT-REAR, BOTTOM above, TOP below.
net_min_x = -half_x - 2.0 * half_z
net_max_x = 3.0 * half_x + 2.0 * half_z
net_min_y = -half_y - 2.0 * half_z
net_max_y = half_y + 2.0 * half_z
net_center_x = (net_min_x + net_max_x) / 2.0
net_center_y = (net_min_y + net_max_y) / 2.0
camera_target = (
    box_center
    + main_x * net_center_x
    + main_y * net_center_y
    - main_z * half_z
)
camera_direction = (main_z * 4.0 + main_x * 3.0 + main_y * 2.5).normalized()
camera_location = camera_target + camera_direction * largest * 14.0

camera_data = bpy.data.cameras.new("OrthoVideo Camera")
camera_data.type = "ORTHO"
camera_data.clip_start = 0.1
camera_data.clip_end = largest * 120.0
camera = bpy.data.objects.new("OrthoVideo Camera", camera_data)
bpy.context.scene.collection.objects.link(camera)
camera.location = camera_location
camera.rotation_mode = "QUATERNION"
camera.rotation_quaternion = track_quaternion(camera_location, camera_target)
bpy.context.scene.camera = camera

camera_right = camera.rotation_quaternion @ Vector((1.0, 0.0, 0.0))
camera_up = camera.rotation_quaternion @ Vector((0.0, 1.0, 0.0))
framing_points_local = [
    Vector((x, y, z))
    for x in (net_min_x, net_max_x)
    for y in (net_min_y - largest * 0.14, net_max_y + largest * 0.14)
    for z in (-half_z, half_z)
]
framing_points_world = [
    box_center + main_x * point.x + main_y * point.y + main_z * point.z
    for point in framing_points_local
]
camera_x = [(point - camera_target).dot(camera_right) for point in framing_points_world]
camera_y = [(point - camera_target).dot(camera_up) for point in framing_points_world]
projected_width = max(camera_x) - min(camera_x)
projected_height = max(camera_y) - min(camera_y)
aspect = float(render_data["resolution_x"]) / float(render_data["resolution_y"])
# In Blender ortho_scale is the vertical span; derive the minimum vertical
# span that also contains the requested horizontal extent.
camera_data.ortho_scale = max(
    projected_height * 1.18,
    (projected_width / aspect) * 1.18,
)

create_area_light(
    "Key Light",
    box_center + main_z * largest * 5.0 + main_x * largest * 3.0 + main_y * largest * 4.0,
    box_center,
    max(largest * largest * 5.0, 1500.0),
    largest * 3.0,
    color=(1.0, 0.96, 0.90),
)
create_area_light(
    "Fill Light",
    box_center + main_z * largest * 2.0 - main_x * largest * 4.0 + main_y * largest,
    box_center,
    max(largest * largest * 0.85, 400.0),
    largest * 4.0,
    color=(0.78, 0.88, 1.0),
)
create_area_light(
    "Rim Light",
    box_center - main_z * largest * 4.0 + main_x * largest * 2.0 + main_y * largest * 3.0,
    box_center,
    max(largest * largest * 2.5, 900.0),
    largest * 2.5,
    color=(0.72, 0.84, 1.0),
)

world = bpy.data.worlds.new("OrthoVideo World")
world.use_nodes = True
bpy.context.scene.world = world
world.node_tree.nodes.clear()
background = world.node_tree.nodes.new("ShaderNodeBackground")
background.inputs["Color"].default_value = (0.92, 0.94, 0.96, 1.0)
background.inputs["Strength"].default_value = 0.28
world_output = world.node_tree.nodes.new("ShaderNodeOutputWorld")
world.node_tree.links.new(background.outputs["Background"], world_output.inputs["Surface"])

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene["orthovideo_model_shading"] = "technical_contrast_v2"
scene.render.resolution_x = int(render_data["resolution_x"])
scene.render.resolution_y = int(render_data["resolution_y"])
scene.render.resolution_percentage = int(render_data.get("render_percentage", 100))
scene.render.fps = int(render_data["fps"])
scene.render.film_transparent = False
scene.render.image_settings.file_format = "PNG"
scene.unit_settings.system = "METRIC"
scene.unit_settings.length_unit = "MILLIMETERS"
scene.unit_settings.scale_length = 0.001
scene.frame_start = frame_start
scene.frame_end = frame_end

try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    pass

preview_file = Path(render_data["preview_file"]).resolve()
preview_file.parent.mkdir(parents=True, exist_ok=True)
scene.frame_set(frame_end)
scene.render.filepath = str(preview_file)
bpy.ops.render.render(write_still=True)

blend_file = Path(render_data["blend_file"]).resolve()
bpy.ops.wm.save_as_mainfile(filepath=str(blend_file))

if render_data.get("render_video", False):
    video_file = Path(render_data["video_file"]).resolve()
    frames_dir = video_file.parent / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(frames_dir / "frame_")
    scene.frame_set(frame_start)
    bpy.ops.render.render(animation=True)
    print("ORTHOVIDEO_ANIMATION_FRAMES=" + str(frames_dir))

print("ORTHOVIDEO_ANIMATION_PREVIEW=" + str(preview_file))
print("ORTHOVIDEO_ANIMATION_BLEND=" + str(blend_file))
print("ORTHOVIDEO_ANIMATION_OK")
