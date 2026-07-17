import json
import math
import os

import bpy
from mathutils import Vector


ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "deliverables_ex5531_final")
BLEND_PATH = os.path.join(OUT_DIR, "EX5531_TD8572A_ratio_specific_heats_final.blend")
GLB_PATH = os.path.join(OUT_DIR, "EX5531_TD8572A_ratio_specific_heats_final.glb")
REPORT_PATH = os.path.join(OUT_DIR, "verification_report.json")
PREVIEW_DIR = os.path.join(OUT_DIR, "previews")
os.makedirs(PREVIEW_DIR, exist_ok=True)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
        bpy.data.actions,
    ):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def collection(name):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    return col


def relink(obj, col):
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    col.objects.link(obj)
    return obj


def parent_to(obj, parent):
    if parent is not None:
        obj.parent = parent
    return obj


def empty(name, loc, col, parent=None, display="PLAIN_AXES", size=0.018):
    obj = bpy.data.objects.new(name, None)
    obj.location = loc
    obj.empty_display_type = display
    obj.empty_display_size = size
    col.objects.link(obj)
    return parent_to(obj, parent)


def material(name, rgba, roughness, metallic=0.0, transmission=0.0, ior=1.45):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = rgba
    node = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if node:
        values = {
            "Base Color": rgba,
            "Metallic": metallic,
            "Roughness": roughness,
            "Alpha": rgba[3],
            "Transmission Weight": transmission,
            "IOR": ior,
        }
        for key, value in values.items():
            if key in node.inputs:
                node.inputs[key].default_value = value
    if rgba[3] < 1.0 or transmission > 0.0:
        try:
            mat.surface_render_method = "DITHERED"
        except Exception:
            pass
        try:
            mat.use_transparency_overlap = False
        except Exception:
            pass
    return mat


def bevel(obj, width, segments=4):
    if width <= 0:
        return obj
    mod = obj.modifiers.new("Realistic_Edge_Bevel", "BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE"
    return obj


def smooth(obj):
    if obj.type == "MESH":
        for polygon in obj.data.polygons:
            polygon.use_smooth = True
    return obj


def cube(name, loc, dims, mat, col, parent=None, edge=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if mat:
        obj.data.materials.append(mat)
    bevel(obj, edge)
    relink(obj, col)
    return parent_to(obj, parent)


def mesh_text_label(name, body, loc, size, mat, col, parent=None, flat=False, outline_offset=0.0):
    """Create a label and convert it to an export-safe mesh."""
    bpy.ops.object.text_add(location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.data.body = str(body)
    obj.data.align_x = "CENTER"
    obj.data.align_y = "CENTER"
    obj.data.size = size
    obj.data.offset = outline_offset
    obj.data.extrude = 0.0 if flat else 0.00045
    obj.data.bevel_depth = 0.0 if flat else 0.00012
    obj.data.bevel_resolution = 0 if flat else 3
    if mat:
        obj.data.materials.append(mat)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.convert(target="MESH")
    obj = bpy.context.object
    obj.name = name
    relink(obj, col)
    return parent_to(obj, parent)


def cube_with_circular_y_holes(name, loc, dims, holes_xz, mat, col, parent=None, edge=0.0):
    """Create a panel with real circular openings normal to Y."""
    obj = cube(name, loc, dims, mat, col, None, 0.0)
    for index, (x, z, radius) in enumerate(holes_xz, start=1):
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=128,
            radius=radius,
            depth=dims[1] + 0.020,
            location=(x, loc[1], z),
            rotation=(math.radians(90), 0.0, 0.0),
        )
        cutter = bpy.context.object
        cutter.name = f"{name}_Hole_{index}_CUTTER"
        relink(cutter, col)
        boolean = obj.modifiers.new(f"CircularOpening_{index}", "BOOLEAN")
        boolean.operation = "DIFFERENCE"
        boolean.solver = "EXACT"
        boolean.object = cutter
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        cutter.select_set(False)
        bpy.ops.object.modifier_apply(modifier=boolean.name)
        bpy.data.objects.remove(cutter, do_unlink=True)
    bevel(obj, edge, 5)
    set_props(obj, frontFacePlaneY=loc[1] - dims[1] * 0.5, circularOpeningCount=len(holes_xz))
    return parent_to(obj, parent)


def cube_with_vertical_hole(name, loc, dims, hole_xy, hole_radius, mat, col, parent=None, edge=0.0):
    """Create a beveled box with a real cylindrical Z through-hole."""
    obj = cube(name, loc, dims, mat, col, None, 0.0)
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=128,
        radius=hole_radius,
        depth=dims[2] + 0.020,
        location=(hole_xy[0], hole_xy[1], loc[2]),
    )
    cutter = bpy.context.object
    cutter.name = name + "_SupportRodHole_CUTTER"
    relink(cutter, col)
    boolean = obj.modifiers.new("SupportRod_ThroughHole", "BOOLEAN")
    boolean.operation = "DIFFERENCE"
    boolean.solver = "EXACT"
    boolean.object = cutter
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    cutter.select_set(False)
    bpy.ops.object.modifier_apply(modifier=boolean.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
    bevel(obj, edge, 5)
    set_props(obj, throughHoleFor="SupportRod_45cm", throughHoleRadius=hole_radius)
    return parent_to(obj, parent)


def leaf_plate(name, loc, dims, mat, col, parent=None, edge=0.0, segments=32):
    """Create an extruded, four-way-symmetric leaf with pointed X tips."""
    half_x, half_y, half_z = (dimension * 0.5 for dimension in dims)
    outline = []
    for i in range(segments + 1):
        x = -half_x + (2.0 * half_x * i / segments)
        y = half_y * (1.0 - (abs(x) / half_x) ** 2)
        outline.append((x, y))
    for i in range(segments - 1, 0, -1):
        x = -half_x + (2.0 * half_x * i / segments)
        y = -half_y * (1.0 - (abs(x) / half_x) ** 2)
        outline.append((x, y))

    count = len(outline)
    verts = [(x, y, -half_z) for x, y in outline] + [(x, y, half_z) for x, y in outline]
    faces = [tuple(reversed(range(count))), tuple(range(count, 2 * count))]
    for i in range(count):
        j = (i + 1) % count
        faces.append((i, j, count + j, count + i))

    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = loc
    if mat:
        obj.data.materials.append(mat)
    bevel(obj, edge, 6)
    col.objects.link(obj)
    return parent_to(obj, parent)


def cylinder(name, loc, radius, depth, mat, col, parent=None, vertices=96, edge=0.0):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc)
    obj = bpy.context.object
    obj.name = name
    if mat:
        obj.data.materials.append(mat)
    smooth(obj)
    bevel(obj, edge)
    relink(obj, col)
    return parent_to(obj, parent)


def half_cylinder(name, loc, radius, depth, rotation_z, mat, col, parent=None, segments=64, edge=0.0):
    """Create a vertical D-profile prism with its flat face on local +X."""
    outline = [(0.0, -radius), (0.0, radius)]
    for index in range(1, segments):
        angle = math.pi * 0.5 + math.pi * index / segments
        outline.append((radius * math.cos(angle), radius * math.sin(angle)))

    count = len(outline)
    half_depth = depth * 0.5
    verts = [(x, y, -half_depth) for x, y in outline] + [(x, y, half_depth) for x, y in outline]
    faces = [tuple(reversed(range(count))), tuple(range(count, count * 2))]
    for index in range(count):
        following = (index + 1) % count
        faces.append((index, following, count + following, count + index))

    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = loc
    obj.rotation_euler[2] = rotation_z
    if mat:
        obj.data.materials.append(mat)
    # Keep the two caps and the recessed flat mating face planar while
    # smoothing only the exposed semicircular wall.
    for polygon_index, polygon in enumerate(obj.data.polygons):
        polygon.use_smooth = polygon_index >= 3
    bevel(obj, edge, 6)
    col.objects.link(obj)
    return parent_to(obj, parent)


def cylinder_axis(name, loc, radius, depth, axis, mat, col, parent=None, vertices=96, edge=0.0):
    obj = cylinder(name, loc, radius, depth, mat, col, parent, vertices, edge)
    if axis == "X":
        obj.rotation_euler[1] = math.radians(90)
    elif axis == "Y":
        obj.rotation_euler[0] = math.radians(90)
    return obj


def torus(name, loc, major, minor, mat, col, parent=None, rotation=(0.0, 0.0, 0.0)):
    bpy.ops.mesh.primitive_torus_add(
        major_radius=major,
        minor_radius=minor,
        major_segments=128,
        minor_segments=24,
        location=loc,
        rotation=rotation,
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    smooth(obj)
    relink(obj, col)
    return parent_to(obj, parent)


def beam_between(name, a, b, width, height, z, mat, col, parent=None, edge=0.003):
    a = Vector(a)
    b = Vector(b)
    delta = b - a
    center = (a + b) * 0.5
    obj = cube(name, (center.x, center.y, z), (delta.length, width, height), mat, col, parent, edge)
    obj.rotation_euler[2] = math.atan2(delta.y, delta.x)
    return obj


def beam_between_3d(name, a, b, width, height, mat, col, parent=None, edge=0.003):
    """Create a rectangular support whose local X axis joins two 3D points."""
    a = Vector(a)
    b = Vector(b)
    delta = b - a
    center = (a + b) * 0.5
    obj = cube(name, center, (delta.length, width, height), mat, col, parent, edge)
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = delta.to_track_quat("X", "Z")
    return obj


def tapered_bridge(name, loc, depth, slab_width, clamp_width, height, mat, col, parent=None, edge=0.002):
    """Horizontal Y bridge that widens from the rod clamp to the slab edge."""
    half_depth = depth * 0.5
    half_height = height * 0.5
    half_slab = slab_width * 0.5
    half_clamp = clamp_width * 0.5
    verts = [
        (-half_slab, -half_depth, -half_height),
        (half_slab, -half_depth, -half_height),
        (-half_clamp, half_depth, -half_height),
        (half_clamp, half_depth, -half_height),
        (-half_slab, -half_depth, half_height),
        (half_slab, -half_depth, half_height),
        (-half_clamp, half_depth, half_height),
        (half_clamp, half_depth, half_height),
    ]
    faces = [
        (0, 2, 3, 1), (4, 5, 7, 6),
        (0, 1, 5, 4), (2, 6, 7, 3),
        (0, 4, 6, 2), (1, 3, 7, 5),
    ]
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = loc
    obj.data.materials.append(mat)
    col.objects.link(obj)
    bevel(obj, edge, 4)
    return parent_to(obj, parent)


def trapezoid_prism(name, bottom_center, top_center, bottom_dims, top_dims, mat, col, parent=None, edge=0.003):
    """Create a four-sided pedestal that tapers from a lower rectangle to an upper rectangle."""
    bottom_center = Vector(bottom_center)
    top_center = Vector(top_center)
    origin = (bottom_center + top_center) * 0.5
    bottom_half_x, bottom_half_y = bottom_dims[0] * 0.5, bottom_dims[1] * 0.5
    top_half_x, top_half_y = top_dims[0] * 0.5, top_dims[1] * 0.5
    verts = [
        (bottom_center.x - bottom_half_x - origin.x, bottom_center.y - bottom_half_y - origin.y, bottom_center.z - origin.z),
        (bottom_center.x + bottom_half_x - origin.x, bottom_center.y - bottom_half_y - origin.y, bottom_center.z - origin.z),
        (bottom_center.x + bottom_half_x - origin.x, bottom_center.y + bottom_half_y - origin.y, bottom_center.z - origin.z),
        (bottom_center.x - bottom_half_x - origin.x, bottom_center.y + bottom_half_y - origin.y, bottom_center.z - origin.z),
        (top_center.x - top_half_x - origin.x, top_center.y - top_half_y - origin.y, top_center.z - origin.z),
        (top_center.x + top_half_x - origin.x, top_center.y - top_half_y - origin.y, top_center.z - origin.z),
        (top_center.x + top_half_x - origin.x, top_center.y + top_half_y - origin.y, top_center.z - origin.z),
        (top_center.x - top_half_x - origin.x, top_center.y + top_half_y - origin.y, top_center.z - origin.z),
    ]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = origin
    obj.data.materials.append(mat)
    col.objects.link(obj)
    bevel(obj, edge, 5)
    return parent_to(obj, parent)


def v_footprint_loft(
    name, center_x, y_front, y_back, z_bottom, z_top,
    bottom_front_half_x, bottom_back_half_x,
    top_front_half_x, top_back_half_x,
    mat, col, parent=None, edge=0.003,
):
    """Loft two trapezoidal XY footprints whose outer edges follow a V-frame."""
    origin = Vector((center_x, (y_front + y_back) * 0.5, (z_bottom + z_top) * 0.5))
    verts_world = [
        (center_x - bottom_front_half_x, y_front, z_bottom),
        (center_x + bottom_front_half_x, y_front, z_bottom),
        (center_x + bottom_back_half_x, y_back, z_bottom),
        (center_x - bottom_back_half_x, y_back, z_bottom),
        (center_x - top_front_half_x, y_front, z_top),
        (center_x + top_front_half_x, y_front, z_top),
        (center_x + top_back_half_x, y_back, z_top),
        (center_x - top_back_half_x, y_back, z_top),
    ]
    verts = [(x - origin.x, y - origin.y, z - origin.z) for x, y, z in verts_world]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = origin
    obj.data.materials.append(mat)
    col.objects.link(obj)
    bevel(obj, edge, 6)
    return parent_to(obj, parent)


def ring_wall(name, loc, outer_r, inner_r, height, mat, col, parent=None, segments=160):
    verts = []
    faces = []
    for z in (-height / 2, height / 2):
        for radius in (outer_r, inner_r):
            for i in range(segments):
                angle = 2 * math.pi * i / segments
                verts.append((radius * math.cos(angle), radius * math.sin(angle), z))
    ob, ib, ot, it = 0, segments, 2 * segments, 3 * segments
    for i in range(segments):
        j = (i + 1) % segments
        faces.extend(
            [
                (ob + i, ob + j, ot + j, ot + i),
                (ib + j, ib + i, it + i, it + j),
                (ot + i, ot + j, it + j, it + i),
                (ob + j, ob + i, ib + i, ib + j),
            ]
        )
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = loc
    obj.data.materials.append(mat)
    col.objects.link(obj)
    smooth(obj)
    bevel(obj, 0.00035, 2)
    return parent_to(obj, parent)


def capsule_points(width, height, segments=28):
    radius = width / 2
    straight = height / 2 - radius
    points = []
    for i in range(segments + 1):
        angle = math.pi * i / segments
        points.append((radius * math.cos(angle), straight + radius * math.sin(angle)))
    for i in range(segments + 1):
        angle = math.pi + math.pi * i / segments
        points.append((radius * math.cos(angle), -straight + radius * math.sin(angle)))
    return points


def capsule_ring(name, loc, width, height, border, depth, orientation, mat, col, parent=None):
    outer = capsule_points(width, height)
    inner = capsule_points(width - 2 * border, height - 2 * border)
    count = len(outer)
    verts = []

    def map_point(p, d):
        if orientation == "XZ":
            return (p[0], d, p[1])
        return (d, p[0], p[1])

    for d in (-depth / 2, depth / 2):
        verts.extend(map_point(p, d) for p in outer)
        verts.extend(map_point(p, d) for p in inner)

    faces = []
    of, inf, ob, inb = 0, count, count * 2, count * 3
    for i in range(count):
        j = (i + 1) % count
        faces.extend(
            [
                (of + i, of + j, inf + j, inf + i),
                (ob + j, ob + i, inb + i, inb + j),
                (of + i, ob + i, ob + j, of + j),
                (inf + j, inb + j, inb + i, inf + i),
            ]
        )
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = loc
    obj.data.materials.append(mat)
    col.objects.link(obj)
    bevel(obj, 0.0012, 3)
    return parent_to(obj, parent)


def rounded_rect_points(width, height, radius, segments=12):
    half_w = width * 0.5
    half_h = height * 0.5
    radius = min(radius, half_w, half_h)
    centers = (
        (half_w - radius, half_h - radius, 0.0),
        (-half_w + radius, half_h - radius, math.pi * 0.5),
        (-half_w + radius, -half_h + radius, math.pi),
        (half_w - radius, -half_h + radius, math.pi * 1.5),
    )
    points = []
    for cx, cy, start in centers:
        for i in range(segments + 1):
            angle = start + math.pi * 0.5 * i / segments
            points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def rounded_window_panel(
    name, loc, outer_size, inner_size, depth, orientation, mat, col, parent=None,
    outer_corner=0.004, inner_corner=0.016, segments=12,
):
    """Solid rectangular wall panel with one real rounded-rectangle opening."""
    outer = rounded_rect_points(outer_size[0], outer_size[1], outer_corner, segments)
    inner = rounded_rect_points(inner_size[0], inner_size[1], inner_corner, segments)
    count = len(outer)
    verts = []

    def map_point(point, offset):
        if orientation == "XZ":
            return (point[0], offset, point[1])
        return (offset, point[0], point[1])

    for offset in (-depth * 0.5, depth * 0.5):
        verts.extend(map_point(point, offset) for point in outer)
        verts.extend(map_point(point, offset) for point in inner)

    faces = []
    outer_front, inner_front, outer_back, inner_back = 0, count, count * 2, count * 3
    for i in range(count):
        j = (i + 1) % count
        faces.extend(
            [
                (outer_front + i, outer_front + j, inner_front + j, inner_front + i),
                (outer_back + j, outer_back + i, inner_back + i, inner_back + j),
                (outer_front + i, outer_back + i, outer_back + j, outer_front + j),
                (inner_front + j, inner_back + j, inner_back + i, inner_front + i),
            ]
        )
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = loc
    obj.data.materials.append(mat)
    col.objects.link(obj)
    bevel(obj, 0.0012, 3)
    return parent_to(obj, parent)


def boxes_mesh(name, boxes, mat, col, parent=None):
    verts = []
    faces = []
    for center, dims in boxes:
        cx, cy, cz = center
        dx, dy, dz = (v / 2 for v in dims)
        start = len(verts)
        verts.extend(
            [
                (cx - dx, cy - dy, cz - dz),
                (cx + dx, cy - dy, cz - dz),
                (cx + dx, cy + dy, cz - dz),
                (cx - dx, cy + dy, cz - dz),
                (cx - dx, cy - dy, cz + dz),
                (cx + dx, cy - dy, cz + dz),
                (cx + dx, cy + dy, cz + dz),
                (cx - dx, cy + dy, cz + dz),
            ]
        )
        faces.extend(
            [
                tuple(start + i for i in (0, 1, 2, 3)),
                tuple(start + i for i in (4, 7, 6, 5)),
                tuple(start + i for i in (0, 4, 5, 1)),
                tuple(start + i for i in (1, 5, 6, 2)),
                tuple(start + i for i in (2, 6, 7, 3)),
                tuple(start + i for i in (4, 0, 3, 7)),
            ]
        )
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.data.materials.append(mat)
    col.objects.link(obj)
    return parent_to(obj, parent)


def cylindrical_scale_ticks(
    name, center_xy, radius, z_start, z_end, count, mat, col, parent=None,
    center_angle=-math.pi / 2, radial_depth=0.0005, tick_height=0.00065, arc_segments=10,
    major_every=10, medium_every=5, major_length=0.014, medium_length=0.010, minor_length=0.0065,
):
    """Create scale marks as thin annular sectors that conform to a tube wall."""
    verts = []
    faces = []
    for tick_index in range(count):
        z = z_start + tick_index * (z_end - z_start) / (count - 1)
        length = (
            major_length if tick_index % major_every == 0
            else (medium_length if medium_every and tick_index % medium_every == 0 else minor_length)
        )
        half_angle = math.asin(min(0.95, length / (2.0 * radius)))
        start = len(verts)
        for segment in range(arc_segments + 1):
            angle = center_angle - half_angle + 2.0 * half_angle * segment / arc_segments
            cosine = math.cos(angle)
            sine = math.sin(angle)
            for current_radius, current_z in (
                (radius + 0.0001, z - tick_height * 0.5),
                (radius + radial_depth, z - tick_height * 0.5),
                (radius + 0.0001, z + tick_height * 0.5),
                (radius + radial_depth, z + tick_height * 0.5),
            ):
                verts.append((
                    center_xy[0] + current_radius * cosine,
                    center_xy[1] + current_radius * sine,
                    current_z,
                ))
        for segment in range(arc_segments):
            current = start + segment * 4
            following = current + 4
            faces.extend(
                [
                    (current, following, following + 2, current + 2),
                    (current + 1, current + 3, following + 3, following + 1),
                    (current, current + 1, following + 1, following),
                    (current + 2, following + 2, following + 3, current + 3),
                ]
            )
        last = start + arc_segments * 4
        faces.extend(((start, start + 2, start + 3, start + 1), (last, last + 1, last + 3, last + 2)))

    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.data.materials.append(mat)
    col.objects.link(obj)
    return parent_to(obj, parent)


def curve_tube(name, points, radius, mat, col, parent=None):
    curve = bpy.data.curves.new(name + "_Curve", "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 20
    curve.bevel_depth = radius
    curve.bevel_resolution = 6
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for bp, co in zip(spline.bezier_points, points):
        bp.co = co
        bp.handle_left_type = "AUTO"
        bp.handle_right_type = "AUTO"
    first = spline.bezier_points[0]
    first.handle_right_type = "FREE"
    first.handle_right = Vector(points[0]) + (Vector(points[1]) - Vector(points[0])) / 3
    last = spline.bezier_points[-1]
    last.handle_left_type = "FREE"
    last.handle_left = Vector(points[-1]) - (Vector(points[-1]) - Vector(points[-2])) / 3
    obj = bpy.data.objects.new(name, curve)
    obj.data.materials.append(mat)
    col.objects.link(obj)
    return parent_to(obj, parent)


def world_from_local(origin, angle, local):
    x, y, z = local
    c, s = math.cos(angle), math.sin(angle)
    return Vector((origin[0] + c * x - s * y, origin[1] + s * x + c * y, origin[2] + z))


def set_props(obj, **props):
    for key, value in props.items():
        obj[key] = value
    return obj


def point_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()
    return obj


def add_knob(root_name, origin, radius, depth, axis, mat, detail_mat, col, parent, interaction):
    root = empty(root_name, origin, col, parent, size=0.012)
    set_props(root, interaction=interaction, interactive=True)
    shaft_loc = (depth * 0.30, 0, 0) if axis == "X" else (0, depth * 0.30, 0)
    head_loc = (depth * 1.05, 0, 0) if axis == "X" else (0, depth * 1.05, 0)
    cylinder_axis(root_name + "_ThreadedShaft", shaft_loc, radius * 0.30, depth * 1.2, axis, detail_mat, col, root, 64, 0.00025)
    head = cylinder_axis(root_name + "_KnurledHead", head_loc, radius, depth, axis, mat, col, root, 128, 0.0007)
    for i in range(32):
        angle = 2 * math.pi * i / 32
        if axis == "X":
            loc = (depth * 1.58, radius * 0.92 * math.cos(angle), radius * 0.92 * math.sin(angle))
            tooth = cube(root_name + f"_Grip_{i:02d}", loc, (0.0012, 0.0010, 0.0035), detail_mat, col, root, 0.0001)
            tooth.rotation_euler[0] = angle
        else:
            loc = (radius * 0.92 * math.cos(angle), depth * 1.58, radius * 0.92 * math.sin(angle))
            tooth = cube(root_name + f"_Grip_{i:02d}", loc, (0.0010, 0.0012, 0.0035), detail_mat, col, root, 0.0001)
            tooth.rotation_euler[1] = -angle
    return root, head


def create_scene():
    clear_scene()
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = "METERS"
    scene.frame_start = 1
    scene.frame_end = 72

    cols = {name: collection(name) for name in (
        "00_Roots", "01_Table", "02_Stand", "03_HeatEngine", "04_Pneumatic",
        "05_Sensor", "05_DataSystem", "06_Anchors", "07_Colliders", "08_Lighting"
    )}

    mats = {
        "cast": material("MAT_Base_CastIron", (0.006, 0.008, 0.009, 1.0), 0.60),
        "abs": material("MAT_Black_ABS", (0.008, 0.010, 0.012, 1.0), 0.41),
        "detail": material("MAT_Black_Detail", (0.0015, 0.0020, 0.0025, 1.0), 0.52),
        "steel": material("MAT_Stainless_Brushed", (0.47, 0.50, 0.52, 1.0), 0.22, 1.0),
        "bnc_metal": material("MAT_BNC_MachinedMetal", (0.62, 0.66, 0.68, 1.0), 0.14, 1.0),
        "din_metal": material("MAT_DIN_DarkNickel", (0.13, 0.15, 0.17, 1.0), 0.28, 0.88),
        "din_insulator": material("MAT_DIN_BlackInsulator", (0.003, 0.005, 0.007, 1.0), 0.46, 0.0),
        "pasport_insulator": material("MAT_PASPORT_DarkInsulator", (0.020, 0.026, 0.034, 1.0), 0.42, 0.0),
        "socket_void": material("MAT_SocketVoid_MatteBlack", (0.0002, 0.0003, 0.0004, 1.0), 0.98, 0.0),
        "glass": material("MAT_Glass_Pyrex", (0.76, 0.92, 1.0, 0.25), 0.045, 0.0, 1.0, 1.47),
        "graphite": material("MAT_Graphite", (0.055, 0.060, 0.064, 1.0), 0.64),
        "hose": material("MAT_Hose_ClearPU", (0.76, 0.91, 1.0, 0.44), 0.14, 0.0, 0.42, 1.46),
        "white": material("MAT_Connector_White", (0.90, 0.88, 0.82, 1.0), 0.34),
        "blue": material("MAT_Sensor_BluePC", (0.015, 0.045, 0.55, 0.68), 0.25, 0.0, 0.20, 1.49),
        "table": material("MAT_Table_White", (0.90, 0.91, 0.90, 1.0), 0.45),
        "rubber": material("MAT_Rubber_Feet", (0.010, 0.012, 0.013, 1.0), 0.76),
        "ticks": material("MAT_Scale_Ticks_Black", (0.012, 0.013, 0.014, 1.0), 0.50),
        "inner": material("MAT_Sensor_Inner_Core", (0.010, 0.018, 0.070, 1.0), 0.52),
        "interface_body": material("MAT_UniversalInterface_Body", (0.66, 0.69, 0.70, 1.0), 0.32, 0.18),
        "interface_panel": material("MAT_UniversalInterface_Panel", (0.018, 0.022, 0.030, 1.0), 0.48),
        "interface_blue": material("MAT_UniversalInterface_Blue", (0.015, 0.070, 0.30, 1.0), 0.40),
        "data_cable": material("MAT_DataCable", (0.035, 0.042, 0.050, 1.0), 0.52),
        "indicator_green": material("MAT_Indicator_Green", (0.01, 0.72, 0.08, 1.0), 0.22),
        "output_red": material("MAT_Output_Red", (0.65, 0.015, 0.020, 1.0), 0.38),
        "collider": material("MAT_Collider_Invisible", (0.0, 0.0, 0.0, 0.0), 1.0),
    }

    scene_root = empty("SCENE_ROOT", (0, 0, 0), cols["00_Roots"], size=0.03)
    original_table_center = Vector((0.0, -0.06, -0.015))
    original_table_dims = Vector((0.90, 0.70, 0.03))
    table_center = Vector((-0.10, -0.04, -0.015))
    table_dims = Vector((1.25, 0.90, 0.03))
    main_instrument_xy_shift = Vector((table_center.x, table_center.y, 0.0))
    # Shift the complete instrument ensemble (main rig, sensor, interface,
    # hoses and data cable) together so its combined footprint is centered on
    # the expanded tabletop.  Positive X and negative Y follow the requested
    # adjustment directions.
    all_instruments_xy_shift = Vector((0.22875, -0.024504092, 0.0))
    apparatus = empty("RSH_Apparatus_ROOT", all_instruments_xy_shift, cols["00_Roots"], scene_root, size=0.025)
    stand = empty("Stand_ROOT", main_instrument_xy_shift, cols["02_Stand"], apparatus)
    instrument_scale = 1.10
    previous_instrument_y_shift = 0.060
    previous_instrument_z_shift = 0.030
    instrument_y_shift = 0.000
    instrument_z_shift = 0.060
    instrument_pivot = Vector((0.0, -0.010, 0.081))
    instrument_root = empty(
        "InstrumentBodyScaled_ROOT",
        (
            instrument_pivot.x + main_instrument_xy_shift.x,
            instrument_pivot.y + instrument_y_shift + main_instrument_xy_shift.y,
            instrument_pivot.z + instrument_z_shift,
        ),
        cols["00_Roots"],
        apparatus,
        size=0.022,
    )
    instrument_root.scale = (instrument_scale,) * 3
    set_props(
        instrument_root,
        uniformScale=instrument_scale,
        yShift=instrument_y_shift,
        zShift=instrument_z_shift,
        pivot=list(instrument_pivot),
        ensembleShiftXY=list(all_instruments_xy_shift.xy),
    )
    set_props(stand, partOfCenteredEnsemble=True, ensembleShiftXY=list(all_instruments_xy_shift.xy))

    def instrument_apparatus_local(point):
        point = Vector(point)
        return main_instrument_xy_shift + instrument_pivot + Vector((0.0, instrument_y_shift, instrument_z_shift)) + (point - instrument_pivot) * instrument_scale

    def instrument_world(point):
        return all_instruments_xy_shift + instrument_apparatus_local(point)

    def instrument_source_from_world(point):
        point = Vector(point)
        return instrument_pivot + (point - all_instruments_xy_shift - main_instrument_xy_shift - instrument_pivot - Vector((0.0, instrument_y_shift, instrument_z_shift))) / instrument_scale

    root_compensation = tuple(-component for component in instrument_pivot)
    engine = empty("HeatEngine_ROOT", root_compensation, cols["03_HeatEngine"], instrument_root)
    pneumatic = empty("Pneumatic_ROOT", root_compensation, cols["04_Pneumatic"], instrument_root)
    pneumatic_hose = empty("PneumaticHose_ROOT", (0, 0, 0), cols["04_Pneumatic"], apparatus)
    rod_support = empty("RodSupport_ROOT", main_instrument_xy_shift, cols["03_HeatEngine"], apparatus)
    anchors = empty("ANCHORS", (0, 0, 0), cols["06_Anchors"], scene_root)
    colliders = empty("COLLIDERS", (0, 0, 0), cols["07_Colliders"], scene_root)

    tabletop = cube("Tabletop", table_center, table_dims, mats["table"], cols["01_Table"], scene_root, 0.002)
    set_props(tabletop, surface="tabletop", contactZ=0.0)

    # Enlarged open V base. Keep the rear apex under the support rod while
    # extending the free ends forward and increasing both beam cross-sections.
    original_base_foot_spacing = 0.250
    original_base_arm_length = 0.260
    original_base_beam_width = 0.043
    original_base_beam_height = 0.026
    base_foot_spacing = 0.280
    base_arm_length = 0.295
    base_beam_width = 0.052
    base_beam_height = 0.032
    base_beam_center_z = 0.023
    apex = Vector((0.0, 0.13298025727272034, 0.0))
    foot_y = apex.y - math.sqrt(base_arm_length ** 2 - (base_foot_spacing * 0.5) ** 2)
    left_foot = Vector((-base_foot_spacing * 0.5, foot_y, 0.0))
    right_foot = Vector((base_foot_spacing * 0.5, foot_y, 0.0))
    base_joint_overlap = 0.0
    base_joint_radius = base_beam_width * 0.62
    left_joint_end = apex.copy()
    right_joint_end = apex.copy()
    left_base_beam = beam_between("Base_CastIron_LeftBeam", left_foot, left_joint_end, base_beam_width, base_beam_height, base_beam_center_z, mats["cast"], cols["02_Stand"], stand, 0.0)
    right_beam_operand = beam_between("Base_CastIron_RightBeam", right_foot, right_joint_end, base_beam_width, base_beam_height, base_beam_center_z, mats["cast"], cols["02_Stand"], stand, 0.0)
    union_modifier = left_base_beam.modifiers.new("Smooth_V_Beam_Union", "BOOLEAN")
    union_modifier.operation = "UNION"
    union_modifier.solver = "EXACT"
    union_modifier.object = right_beam_operand
    bpy.context.view_layer.objects.active = left_base_beam
    left_base_beam.select_set(True)
    right_beam_operand.select_set(False)
    bpy.ops.object.modifier_apply(modifier=union_modifier.name)
    bpy.data.objects.remove(right_beam_operand, do_unlink=True)
    apex_joint_operand = cylinder(
        "Base_CastIron_ApexJoint_OPERAND", (apex.x, apex.y, base_beam_center_z),
        base_joint_radius, base_beam_height, mats["cast"], cols["02_Stand"], stand, 128, 0.0,
    )
    joint_union = left_base_beam.modifiers.new("Rounded_Apex_Joint_Union", "BOOLEAN")
    joint_union.operation = "UNION"
    joint_union.solver = "EXACT"
    joint_union.object = apex_joint_operand
    bpy.context.view_layer.objects.active = left_base_beam
    left_base_beam.select_set(True)
    apex_joint_operand.select_set(False)
    bpy.ops.object.modifier_apply(modifier=joint_union.name)
    bpy.data.objects.remove(apex_joint_operand, do_unlink=True)
    bevel(left_base_beam, 0.003, 8)
    right_base_beam = empty("Base_CastIron_RightBeam", right_arm_mid if 'right_arm_mid' in locals() else right_foot, cols["02_Stand"], stand, "CUBE", 0.010)
    set_props(
        left_base_beam,
        nominalArmLength=base_arm_length,
        apexJointOverlap=base_joint_overlap,
        apexJointRadius=base_joint_radius,
        containsUnifiedVArms=True,
        jointMethod="exact_boolean_union_with_rounded_hub",
        pointedJointCornersRemoved=True,
    )
    set_props(right_base_beam, logicalAlias=True, representedBy="Base_CastIron_LeftBeam", nominalArmLength=base_arm_length)
    base_node = empty("Base_CastIron", (0, 0, 0), cols["02_Stand"], stand)
    set_props(base_node, type="cast_iron_open_V_frame", footCenterDistance=base_foot_spacing, footToVertexDistance=base_arm_length)

    level_foot_radius = base_beam_width * 0.5
    level_foot_height = 0.012
    level_foot_beam_overlap = 0.003
    level_foot_edge_radius = 0.0012
    level_feet = {}
    for name, p, logical_side in (
        ("LevelFoot_L", left_foot, "left"),
        ("LevelFoot_R", right_foot, "right"),
    ):
        beam_direction = (apex - p).normalized()
        flat_face_center = p + beam_direction * level_foot_beam_overlap
        foot = half_cylinder(
            name,
            (flat_face_center.x, flat_face_center.y, level_foot_height * 0.5),
            level_foot_radius,
            level_foot_height,
            math.atan2(beam_direction.y, beam_direction.x),
            mats["rubber"], cols["02_Stand"], stand,
            segments=64, edge=level_foot_edge_radius,
        )
        level_feet[name] = foot
        set_props(
            foot,
            contactZ=0.0,
            adjustable=False,
            fixed=True,
            shape="vertical_half_cylinder",
            profile="D_profile_with_semicircular_exposed_edge",
            radius=level_foot_radius,
            height=level_foot_height,
            flatFaceWidth=level_foot_radius * 2.0,
            beamOverlap=level_foot_beam_overlap,
            edgeRadius=level_foot_edge_radius,
            logicalSide=logical_side,
            logicalBeam=f"Base_CastIron_{logical_side.capitalize()}Beam",
            representedGeometryBy="Base_CastIron_LeftBeam",
            adjusterScrewRemoved=True,
            protrudingCornersRemoved=True,
        )
    left_level_foot = level_feet["LevelFoot_L"]
    right_level_foot = level_feet["LevelFoot_R"]
    vertex = cylinder("VertexContactPad", (apex.x, apex.y, 0.005), 0.021, 0.010, mats["rubber"], cols["02_Stand"], stand, 96, 0.001)
    set_props(vertex, contactZ=0.0)

    # The shortened support rod now shares the upper-cylinder axis. It no longer
    # relies on the rear vertex pad because the V-frame pedestal carries the body.
    connector_axis_y = 0.050
    rod_xy = (0.0, connector_axis_y)
    rod_axis_world_xy = all_instruments_xy_shift.xy + main_instrument_xy_shift.xy + Vector(rod_xy)

    original_housing_dims = (0.120, 0.090, 0.058)
    original_top_lip_dims = (0.124, 0.094, 0.010)
    previous_housing_y = 0.122
    previous_top_lip_y = 0.128
    original_housing_combined_height = 0.062
    housing_dims = (0.138, 0.170, 0.044)
    housing_center = (0.0, -0.010, 0.117)
    top_lip_dims = (0.144, 0.176, 0.008)
    top_lip_center = (0.0, -0.010, 0.138)
    housing_bottom_z = housing_center[2] - housing_dims[2] * 0.5
    housing_top_z = housing_center[2] + housing_dims[2] * 0.5
    top_lip_bottom_z = top_lip_center[2] - top_lip_dims[2] * 0.5
    top_lip_top_z = top_lip_center[2] + top_lip_dims[2] * 0.5
    housing_combined_height = max(housing_top_z, top_lip_top_z) - min(housing_bottom_z, top_lip_bottom_z)
    # Stretch only the measurement assembly above LowerHousing.  The bottom
    # attachment plane remains fixed while all upper endpoints rise together.
    upper_z_stretch = 0.060

    housing_world_center = instrument_world(housing_center)
    housing_world_bottom_z = instrument_world((0.0, housing_center[1], housing_bottom_z)).z
    left_arm_mid = (left_foot + apex) * 0.5
    right_arm_mid = (right_foot + apex) * 0.5
    right_base_beam.location = (right_arm_mid.x, right_arm_mid.y, base_beam_center_z)
    left_base_support = empty("BaseToInstrumentSupport_L", (left_arm_mid.x, left_arm_mid.y, base_beam_center_z), cols["02_Stand"], stand, "CUBE", 0.010)
    right_base_support = empty("BaseToInstrumentSupport_R", (right_arm_mid.x, right_arm_mid.y, base_beam_center_z), cols["02_Stand"], stand, "CUBE", 0.010)

    previous_connector_cylinder_radius = 0.027
    previous_connector_cylinder_depth = 0.034
    connector_cylinder_radius = 0.032
    connector_cylinder_depth = 0.044
    connector_cylinder_top_z = housing_world_bottom_z
    connector_cylinder_bottom_z = connector_cylinder_top_z - connector_cylinder_depth
    connector_cylinder_center = Vector((0.0, connector_axis_y, (connector_cylinder_bottom_z + connector_cylinder_top_z) * 0.5))
    pedestal_bottom_z = base_beam_center_z + base_beam_height * 0.5 - 0.003
    pedestal_top_z = connector_cylinder_bottom_z + 0.002
    pedestal_center_y = connector_axis_y
    pedestal_bottom_center = Vector((0.0, pedestal_center_y, pedestal_bottom_z))
    pedestal_top_center = Vector((0.0, pedestal_center_y, pedestal_top_z))
    arm_direction = (apex - left_foot).normalized()
    pedestal_y_depth = 0.100
    pedestal_y_front = pedestal_center_y - pedestal_y_depth * 0.5
    pedestal_y_back = pedestal_center_y + pedestal_y_depth * 0.5

    def base_outer_half_x_at_y(y):
        progress = (y - left_foot.y) / (apex.y - left_foot.y)
        center_half_x = base_foot_spacing * 0.5 * (1.0 - progress)
        return center_half_x + abs(arm_direction.y) * base_beam_width * 0.5

    pedestal_bottom_front_half_x = base_outer_half_x_at_y(pedestal_y_front)
    pedestal_bottom_back_half_x = base_outer_half_x_at_y(pedestal_y_back)
    previous_pedestal_top_footprint_scale = 0.62
    pedestal_top_footprint_scale = 0.72
    pedestal_top_front_half_x = pedestal_bottom_front_half_x * pedestal_top_footprint_scale
    pedestal_top_back_half_x = pedestal_bottom_back_half_x * pedestal_top_footprint_scale
    support_cross_mount = v_footprint_loft(
        "BaseToInstrument_CrossMount", 0.0,
        pedestal_y_front, pedestal_y_back, pedestal_bottom_z, pedestal_top_z,
        pedestal_bottom_front_half_x, pedestal_bottom_back_half_x,
        pedestal_top_front_half_x, pedestal_top_back_half_x,
        mats["cast"], cols["02_Stand"], stand, 0.005,
    )
    connector_cylinder = cylinder(
        "BaseToInstrument_UpperCylinder", connector_cylinder_center,
        connector_cylinder_radius, connector_cylinder_depth,
        mats["cast"], cols["02_Stand"], stand, 128, 0.002,
    )
    set_props(left_base_support, connectsFrom="Base_CastIron_LeftBeam_Midpoint", connectsTo="BaseToInstrument_CrossMount")
    set_props(right_base_support, connectsFrom="Base_CastIron_RightBeam_Midpoint", connectsTo="BaseToInstrument_CrossMount")
    set_props(
        support_cross_mount,
        shape="v_conforming_footprint_loft",
        supportMode="V_arm_midpoint_pedestal",
        silhouetteAlongX="rectangle",
        silhouetteAlongY="trapezoid",
        topViewShape="trapezoid",
        footprintAlignedTo="Base_CastIron_LeftBeam+Base_CastIron_RightBeam_outer_edges_at_every_y",
        connectsTo="BaseToInstrument_UpperCylinder",
    )
    set_props(
        connector_cylinder,
        shape="cylinder",
        connectsFrom="BaseToInstrument_CrossMount",
        connectsTo="LowerHousing_off_center_rear_mount",
        verticalAxisY=connector_axis_y,
    )

    rod_original_top_z = 0.456 + instrument_z_shift + upper_z_stretch * instrument_scale
    rod_bottom_z = housing_world_center.z
    rod_visible_length = rod_original_top_z - rod_bottom_z
    rod = cylinder(
        "SupportRod_45cm", (rod_xy[0], rod_xy[1], (rod_bottom_z + rod_original_top_z) * 0.5),
        0.00635, rod_visible_length, mats["steel"], cols["02_Stand"], stand, 128, 0.00025,
    )
    set_props(
        rod, nominalLength=0.450, visibleLength=rod_visible_length,
        nominalDiameter=0.0127, lowerSegmentRemoved=True,
    )
    cylinder("MainRodSocket", (rod_xy[0], rod_xy[1], rod_bottom_z + 0.011), 0.014, 0.022, mats["cast"], cols["03_HeatEngine"], rod_support, 96, 0.001)
    clamp_main = cylinder_axis("BaseClampScrew_Main", (rod_xy[0] + 0.020, rod_xy[1], rod_bottom_z + 0.012), 0.0065, 0.028, "X", mats["cast"], cols["03_HeatEngine"], rod_support, 64, 0.0005)
    set_props(clamp_main, threaded=True)
    cylinder_axis("BaseClampScrew_Alt", (rod_xy[0] - 0.020, rod_xy[1], rod_bottom_z + 0.012), 0.0065, 0.028, "X", mats["cast"], cols["03_HeatEngine"], rod_support, 64, 0.0005)

    rod_pass_source = instrument_source_from_world((rod_axis_world_xy.x, rod_axis_world_xy.y, housing_world_center.z))
    rod_hole_radius = (0.00635 + 0.0015) / instrument_scale
    housing = cube_with_vertical_hole(
        "LowerHousing", housing_center, housing_dims, rod_pass_source.xy, rod_hole_radius,
        mats["abs"], cols["03_HeatEngine"], engine, 0.004,
    )
    set_props(housing, connectedBy="BaseToInstrument_UpperCylinder")
    top_lip = cube_with_vertical_hole(
        "LowerHousing_TopLip", top_lip_center, top_lip_dims, rod_pass_source.xy, rod_hole_radius,
        mats["abs"], cols["03_HeatEngine"], engine, 0.002,
    )
    # Freeze the first hole's edge bevel before cutting the independent hose port.
    # This keeps the quick-disconnect Boolean first in its own modifier stack.
    existing_top_lip_bevel = next((mod for mod in top_lip.modifiers if mod.type == "BEVEL"), None)
    if existing_top_lip_bevel is not None:
        bpy.ops.object.select_all(action="DESELECT")
        top_lip.select_set(True)
        bpy.context.view_layer.objects.active = top_lip
        bpy.ops.object.modifier_apply(modifier=existing_top_lip_bevel.name)
    hose_port_source_xy = Vector((-0.045, -0.068))
    hose_port_hole_radius = 0.0075
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=128,
        radius=hose_port_hole_radius,
        depth=top_lip_dims[2] + 0.020,
        location=(hose_port_source_xy.x, hose_port_source_xy.y, top_lip_center[2]),
    )
    hose_port_cutter = bpy.context.object
    hose_port_cutter.name = "LowerHousing_TopLip_HosePort_CUTTER"
    relink(hose_port_cutter, cols["03_HeatEngine"])
    parent_to(hose_port_cutter, engine)
    hose_port_boolean = top_lip.modifiers.new("QuickDisconnect_VerticalHole", "BOOLEAN")
    hose_port_boolean.operation = "DIFFERENCE"
    hose_port_boolean.solver = "EXACT"
    hose_port_boolean.object = hose_port_cutter
    bpy.context.view_layer.objects.active = top_lip
    top_lip.select_set(True)
    hose_port_cutter.select_set(False)
    bpy.ops.object.modifier_apply(modifier=hose_port_boolean.name)
    bpy.data.objects.remove(hose_port_cutter, do_unlink=True)
    set_props(
        top_lip,
        quickDisconnectHole=True,
        quickDisconnectHoleRadius=hose_port_hole_radius,
        quickDisconnectHoleAxis="Z",
    )
    top_back_source_center = (0.0, 0.029, 0.301 + upper_z_stretch)
    top_back_source_dims = (0.102, 0.016, 0.016)
    top_back_world_center = instrument_world(top_back_source_center)
    rod_connection_z = top_back_world_center.z
    ring_wall("RodClampMount", (rod_xy[0], rod_xy[1], rod_connection_z), 0.015, 0.00655, 0.038, mats["abs"], cols["03_HeatEngine"], rod_support, 128)
    top_back_rear_y = top_back_world_center.y + top_back_source_dims[1] * 0.5 * instrument_scale
    bridge_front_world_y = top_back_rear_y - 0.004
    bridge_front_y = bridge_front_world_y - all_instruments_xy_shift.y - main_instrument_xy_shift.y
    bridge_depth = rod_xy[1] - bridge_front_y
    bridge_slab_width = top_back_source_dims[0] * instrument_scale
    bridge_clamp_width = 0.040
    bridge = tapered_bridge(
        "RodClampBridge",
        (rod_xy[0], bridge_front_y + bridge_depth * 0.5, rod_connection_z),
        bridge_depth, bridge_slab_width, bridge_clamp_width, top_back_source_dims[2] * instrument_scale,
        mats["abs"], cols["03_HeatEngine"], rod_support, 0.002,
    )
    set_props(
        bridge,
        connectsFrom="SupportRod_45cm",
        connectsTo="ProtectiveFrame_TopSlab",
        horizontalAxis="Y",
        slabEndWidth=bridge_slab_width,
        clampEndWidth=bridge_clamp_width,
    )
    rod_knob, rod_knob_head = add_knob(
        "RodClampKnob", (rod_xy[0], rod_xy[1] + 0.010, rod_connection_z),
        0.012, 0.010, "Y", mats["abs"], mats["detail"],
        cols["03_HeatEngine"], rod_support, "rotate_feedback",
    )
    rod_knob_shaft = bpy.data.objects["RodClampKnob_ThreadedShaft"]
    set_props(
        rod_knob,
        removable=False,
        placement="directly_behind_SupportRod_45cm",
        rearDirection="positive_Y",
        axis="Y",
    )

    frame = empty("ProtectiveFrame", (0, 0, 0), cols["03_HeatEngine"], engine)
    frame_outer_size = (0.102, 0.094, 0.178 + upper_z_stretch)
    frame_bottom_z = 0.131
    frame_top_z = frame_bottom_z + frame_outer_size[2]
    frame_center = (0.0, -0.010, (frame_bottom_z + frame_top_z) * 0.5)
    frame_wall_depth = 0.008
    frame_cap_height = 0.016
    front_back_window = (0.082, 0.148 + upper_z_stretch)
    side_window = (0.050, 0.138 + upper_z_stretch)
    set_props(
        frame,
        structure="single_cuboid_shell",
        realOpenings=True,
        connectedBy="RodClampBridge",
        outerSize=list(frame_outer_size),
    )
    top_slab = cube(
        "ProtectiveFrame_TopSlab", (0, frame_center[1], frame_top_z - frame_cap_height * 0.5),
        (frame_outer_size[0], frame_outer_size[1], frame_cap_height),
        mats["abs"], cols["03_HeatEngine"], frame, 0.003,
    )
    bottom_slab = cube(
        "ProtectiveFrame_BottomSlab", (0, frame_center[1], frame_bottom_z + frame_cap_height * 0.5),
        (frame_outer_size[0], frame_outer_size[1], frame_cap_height),
        mats["abs"], cols["03_HeatEngine"], frame, 0.003,
    )
    front_panel = rounded_window_panel(
        "ProtectiveFrame_FrontPanel", (0, frame_center[1] - frame_outer_size[1] * 0.5 + frame_wall_depth * 0.5, frame_center[2]),
        (frame_outer_size[0], frame_outer_size[2]), front_back_window, frame_wall_depth, "XZ",
        mats["abs"], cols["03_HeatEngine"], frame, inner_corner=0.016,
    )
    back_panel = rounded_window_panel(
        "ProtectiveFrame_BackPanel", (0, frame_center[1] + frame_outer_size[1] * 0.5 - frame_wall_depth * 0.5, frame_center[2]),
        (frame_outer_size[0], frame_outer_size[2]), front_back_window, frame_wall_depth, "XZ",
        mats["abs"], cols["03_HeatEngine"], frame, inner_corner=0.016,
    )
    left_panel = rounded_window_panel(
        "ProtectiveFrame_LeftPanel", (-frame_outer_size[0] * 0.5 + frame_wall_depth * 0.5, frame_center[1], frame_center[2]),
        (frame_outer_size[1], frame_outer_size[2]), side_window, frame_wall_depth, "YZ",
        mats["abs"], cols["03_HeatEngine"], frame, inner_corner=side_window[0] * 0.5,
    )
    right_panel = rounded_window_panel(
        "ProtectiveFrame_RightPanel", (frame_outer_size[0] * 0.5 - frame_wall_depth * 0.5, frame_center[1], frame_center[2]),
        (frame_outer_size[1], frame_outer_size[2]), side_window, frame_wall_depth, "YZ",
        mats["abs"], cols["03_HeatEngine"], frame, inner_corner=side_window[0] * 0.5,
    )
    top_back_anchor = empty("ProtectiveFrame_TopBack", top_back_source_center, cols["03_HeatEngine"], frame, size=0.008)
    set_props(top_back_anchor, role="rod_bridge_anchor_on_top_slab")
    for panel, axis, shape, opening in (
        (front_panel, "Y", "large_rounded_rectangle", front_back_window),
        (back_panel, "Y", "large_rounded_rectangle", front_back_window),
        (left_panel, "X", "capsule_ring", side_window),
        (right_panel, "X", "capsule_ring", side_window),
    ):
        set_props(panel, faceNormalAxis=axis, cutoutShape=shape, cutoutSize=list(opening))

    cyl_center = (0, -0.010)
    tube_outer_radius = 0.0240
    tube_inner_radius = 0.0205
    piston_radius = 0.0202
    cylinder_bottom_z = 0.136
    cylinder_depth = 0.157 + upper_z_stretch
    cylinder_top_z = cylinder_bottom_z + cylinder_depth
    cylinder_obj = ring_wall(
        "Cylinder_Pyrex", (cyl_center[0], cyl_center[1], (cylinder_bottom_z + cylinder_top_z) * 0.5),
        tube_outer_radius, tube_inner_radius, cylinder_depth,
        mats["glass"], cols["03_HeatEngine"], engine, 192,
    )
    set_props(cylinder_obj, materialRuntime="MeshPhysicalMaterial", wallThickness=tube_outer_radius - tube_inner_radius)
    lower_seal_center_z = 0.138
    lower_seal_minor_radius = 0.0020
    torus(
        "Cylinder_LowerSeal", (cyl_center[0], cyl_center[1], lower_seal_center_z),
        0.0220, lower_seal_minor_radius, mats["detail"], cols["03_HeatEngine"], engine,
    )
    upper_seal_center_z = cylinder_top_z - 0.002
    upper_seal_minor_radius = 0.0020
    torus(
        "Cylinder_UpperGuideRing", (cyl_center[0], cyl_center[1], upper_seal_center_z),
        0.0220, upper_seal_minor_radius, mats["detail"], cols["03_HeatEngine"], engine,
    )

    # Keep the zero graduation visually tight to the lower glass seal, extend
    # the scale upward to 90, and preserve a small safe gap below the upper
    # glass seal for both the highest tick and its number.
    scale_tick_height = 0.00065
    scale_zero_tick_edge_clearance = 0.000675
    scale_z_start = lower_seal_center_z + lower_seal_minor_radius + scale_tick_height * 0.5 + scale_zero_tick_edge_clearance
    scale_top_tick_center_clearance_to_glass_top = 0.0085
    scale_z_end = cylinder_top_z - scale_top_tick_center_clearance_to_glass_top
    scale_span = scale_z_end - scale_z_start
    scale_max_value = 90
    scale_major_value_step = 10
    scale_major_every = 4
    scale_major_tick_count = scale_max_value // scale_major_value_step + 1
    scale_labeled_major_tick_count = scale_major_tick_count - 1
    scale_tick_count = (scale_major_tick_count - 1) * scale_major_every + 1
    scale_tick_arc_segments = 10
    scale_tick_center_angle = -math.pi / 2 - math.radians(9)
    ticks = cylindrical_scale_ticks(
        "ScaleTicks_Unnumbered", cyl_center, tube_outer_radius, scale_z_start, scale_z_end, scale_tick_count,
        mats["ticks"], cols["03_HeatEngine"], engine,
        # Keep the graduation group centered in the front view: the tick arcs
        # sit just left of the tube centreline and the numbers sit immediately
        # to their right.
        center_angle=scale_tick_center_angle,
        tick_height=scale_tick_height,
        arc_segments=scale_tick_arc_segments,
        major_every=scale_major_every, medium_every=2,
        major_length=0.016, medium_length=0.0105, minor_length=0.0065,
    )
    set_props(
        ticks,
        pickable=False,
        containsNumbers=False,
        numberedBy="ScaleLabels_90_to_10",
        attachedTo="Cylinder_Pyrex",
        conformsToRadius=tube_outer_radius,
        totalTickCount=scale_tick_count,
        majorTickEvery=scale_major_every,
        majorTickCount=scale_major_tick_count,
        labeledMajorTickCount=scale_labeled_major_tick_count,
        highestMajorValue=scale_max_value,
        lowestMajorValue=0,
        lowestMajorLabeled=False,
        zStart=scale_z_start,
        zEnd=scale_z_end,
        tickHeight=scale_tick_height,
    )
    scale_labels = []
    scale_label_surface_offset = 0.00015
    scale_label_initial_radius = tube_outer_radius + 0.0010
    scale_label_x_offset = 0.0095
    scale_label_size = 0.0090
    scale_label_outline = 0.0
    scale_major_z_values = [
        scale_z_end - major_index * (scale_z_end - scale_z_start) / (scale_major_tick_count - 1)
        for major_index in range(scale_major_tick_count)
    ]
    for label_order, displayed_value in enumerate(range(scale_max_value, 0, -scale_major_value_step)):
        label_z = scale_major_z_values[label_order]
        scale_label = mesh_text_label(
            f"ScaleLabel_{displayed_value}", str(displayed_value),
            (cyl_center[0] + scale_label_x_offset, cyl_center[1] - scale_label_initial_radius, label_z),
            scale_label_size, mats["ticks"], cols["03_HeatEngine"], engine,
            flat=True, outline_offset=scale_label_outline,
        )
        scale_label.rotation_euler = (math.radians(90), 0.0, 0.0)
        # Apply the front-facing orientation, then map every text-mesh vertex
        # analytically onto the Pyrex outer cylinder.  This preserves clean,
        # readable glyphs while removing the tangent-plane gap.
        bpy.context.view_layer.objects.active = scale_label
        scale_label.select_set(True)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
        label_target_radius = tube_outer_radius + scale_label_surface_offset
        for label_vertex in scale_label.data.vertices:
            source_x = scale_label.location.x + label_vertex.co.x
            radial_x = source_x - cyl_center[0]
            front_y = cyl_center[1] - math.sqrt(max(0.0, label_target_radius ** 2 - radial_x ** 2))
            label_vertex.co.y = front_y - scale_label.location.y
        scale_label.data.update()
        scale_label.select_set(False)
        scale_labels.append(scale_label)
        set_props(
            scale_label,
            displayedValue=displayed_value,
            attachedTo="Cylinder_Pyrex",
            alignedWith="major_scale_tick",
            scaleOrder="top_to_bottom_90_to_10",
            surfaceConforming=True,
            surfaceOffset=scale_label_surface_offset,
            labelSize=scale_label_size,
            outlineOffset=scale_label_outline,
            frontViewPlacement="center_ticks_left_numbers_right",
        )

    piston_root = empty("PistonAssembly_MOV", (cyl_center[0], cyl_center[1], 0.195), cols["03_HeatEngine"], engine, size=0.022)
    set_props(piston_root, interaction="slide_z", min=0.0, max=0.10, initial=0.06, strokeBaseZ=0.135, axis="local_Z", locked=False)
    original_piston_height = 0.032
    piston_height = 0.024
    piston = cylinder("Piston_Graphite", (0, 0, 0.016), piston_radius, piston_height, mats["graphite"], cols["03_HeatEngine"], piston_root, 192, 0.0005)
    set_props(piston, nominalDiameter=piston_radius * 2.0, nominalHeight=piston_height, radialClearance=tube_inner_radius - piston_radius)
    previous_piston_rod_extra_length = 0.018
    piston_rod_extra_length = 0.012
    piston_rod_depth = 0.180 + upper_z_stretch + piston_rod_extra_length
    piston_rod_center_z = 0.016 + piston_rod_depth * 0.5
    rod_part = cylinder(
        "PistonRod", (0, 0, piston_rod_center_z), 0.003, piston_rod_depth,
        mats["steel"], cols["03_HeatEngine"], piston_root, 96, 0.0002,
    )
    set_props(
        rod_part,
        movesWith="PistonAssembly_MOV",
        nominalLength=piston_rod_depth,
        longerThan="Cylinder_Pyrex",
    )
    leaf_dims = (0.072, 0.062, 0.008)
    piston_rod_source_top = piston_rod_center_z + piston_rod_depth * 0.5
    upper_plate_source_top = 0.171 + leaf_dims[2] * 0.5
    mass_platform_vertical_shift = piston_rod_source_top - upper_plate_source_top
    platform = empty(
        "MassPlatform", (0, 0, mass_platform_vertical_shift),
        cols["03_HeatEngine"], piston_root, size=0.016,
    )
    lower_plate = leaf_plate("MassPlatform_LowerPlate", (0, 0, 0.137), leaf_dims, mats["abs"], cols["03_HeatEngine"], platform, 0.0022)
    upper_plate = leaf_plate("MassPlatform_UpperPlate", (0, 0, 0.171), leaf_dims, mats["abs"], cols["03_HeatEngine"], platform, 0.0022)
    pillar_radius = 0.0025
    pillar_x = leaf_dims[0] * 0.5 - pillar_radius
    pillar_depth = 0.026
    cylinder("MassPlatform_LeftPillar", (-pillar_x, 0, 0.154), pillar_radius, pillar_depth, mats["abs"], cols["03_HeatEngine"], platform, 64, 0.0005)
    cylinder("MassPlatform_RightPillar", (pillar_x, 0, 0.154), pillar_radius, pillar_depth, mats["abs"], cols["03_HeatEngine"], platform, 64, 0.0005)
    set_props(lower_plate, shape="four_way_symmetric_leaf", boundingSize=list(leaf_dims))
    set_props(upper_plate, shape="four_way_symmetric_leaf", boundingSize=list(leaf_dims))
    cylinder("MassPlatform_CentralHub", (0, 0, 0.137), 0.008, 0.015, mats["abs"], cols["03_HeatEngine"], platform, 96, 0.001)
    torus("MassPlatform_TopRecess", (0, 0, 0.1752), 0.005, 0.0012, mats["detail"], cols["03_HeatEngine"], platform)
    set_props(
        platform,
        emptyPlatform=True,
        movesWith="PistonAssembly_MOV",
        verticalShift=mass_platform_vertical_shift,
        upperPlateTopAlignedTo="PistonRod.top",
    )

    for frame_no, offset in ((1, 0.0), (12, 0.003), (24, -0.0024), (36, 0.0018), (48, -0.0010), (60, 0.0005), (72, 0.0)):
        piston_root.location.z = 0.195 + offset
        piston_root.keyframe_insert(data_path="location", frame=frame_no)
    if piston_root.animation_data and piston_root.animation_data.action:
        piston_root.animation_data.action.name = "Piston_Damped_Oscillation_3mm"
    scene.frame_set(1)

    quick_disconnect_root = empty("Connector_Main_QuickDisconnect", (0, 0, 0), cols["04_Pneumatic"], pneumatic, size=0.012)
    port_source_z = top_lip_top_z + 0.006
    port_main = cylinder_axis(
        "Port_Main", (hose_port_source_xy.x, hose_port_source_xy.y, port_source_z),
        0.0068, 0.018, "Z", mats["detail"], cols["04_Pneumatic"], quick_disconnect_root, 96, 0.0006,
    )
    set_props(port_main, line="main_pressure", orientation="vertical_Z", penetrates="LowerHousing_TopLip")
    torus(
        "Port_Main_O_Ring", (hose_port_source_xy.x, hose_port_source_xy.y, top_lip_top_z + 0.010),
        0.0063, 0.0012, mats["detail"], cols["04_Pneumatic"], quick_disconnect_root,
    )
    threaded_stem = cylinder_axis(
        "Connector_Main_ThreadedStem", (hose_port_source_xy.x, hose_port_source_xy.y, top_lip_top_z + 0.017),
        0.0062, 0.022, "Z", mats["detail"], cols["04_Pneumatic"], quick_disconnect_root, 96, 0.0005,
    )
    connector_main = cylinder_axis(
        "Connector_Main_White", (hose_port_source_xy.x, hose_port_source_xy.y, top_lip_top_z + 0.027),
        0.0078, 0.022, "Z", mats["white"], cols["04_Pneumatic"], quick_disconnect_root, 96, 0.0008,
    )
    rotating_collar = cylinder_axis(
        "Connector_Main_RotatingCollar", (hose_port_source_xy.x, hose_port_source_xy.y, top_lip_top_z + 0.020),
        0.0100, 0.012, "Z", mats["white"], cols["04_Pneumatic"], quick_disconnect_root, 128, 0.0010,
    )
    for i in range(6):
        torus(
            "Connector_Main_Grip_%02d" % i,
            (hose_port_source_xy.x, hose_port_source_xy.y, top_lip_top_z + 0.0165 + i * 0.0015),
            0.0085, 0.00055, mats["detail"], cols["04_Pneumatic"], quick_disconnect_root,
        )
    set_props(
        quick_disconnect_root,
        interaction="rotate_connect_disconnect",
        connectionStates=["connected_sealed", "disconnected_open_to_atmosphere"],
        defaultState="connected_sealed",
        sealedWhenConnected=True,
        openToAtmosphereWhenDisconnected=True,
        pistonAdjustableWhen="disconnected_open_to_atmosphere",
    )
    set_props(
        connector_main,
        connection="Hose_Main_Default",
        inserted=True,
        lockingMethod="rotate_threaded_collar",
        airtightWhenLocked=True,
    )
    set_props(rotating_collar, interaction="rotate", controls="Connector_Main_QuickDisconnect.state")
    set_props(threaded_stem, threaded=True, matesWith="Connector_Main_RotatingCollar")

    # Seat the transparent hose slightly inside the white connector cap so the
    # detachable air path reads as physically connected rather than hovering.
    hose_start_source = Vector((hose_port_source_xy.x, hose_port_source_xy.y, top_lip_top_z + 0.035))
    hose_start_local = instrument_apparatus_local(hose_start_source)
    hose_start = hose_start_local + all_instruments_xy_shift

    sensor_origin = (-0.105, -0.260, 0.0)
    sensor_angle = math.radians(10)
    sensor_scale = 1.08
    sensor_root = empty("PressureSensor_ROOT", sensor_origin, cols["05_Sensor"], apparatus, size=0.024)
    sensor_root.rotation_euler[2] = sensor_angle
    sensor_root.scale = (sensor_scale, sensor_scale, sensor_scale)
    set_props(
        sensor_root,
        interaction="drag_table", plane="XY", lockZ=True, lockRotation=True,
        interactive=True, uniformScale=sensor_scale,
    )
    shell = cube("SensorShell_Blue", (0, 0, 0.017), (0.115, 0.038, 0.024), mats["blue"], cols["05_Sensor"], sensor_root, 0.006)
    set_props(shell, deviceType="dual_channel_pressure_sensor", isPump=False)
    cube("SensorInnerCore", (-0.004, 0, 0.017), (0.085, 0.026, 0.014), mats["inner"], cols["05_Sensor"], sensor_root, 0.003)
    port1 = cylinder_axis("SensorPort_1", (0.061, -0.009, 0.018), 0.0052, 0.014, "X", mats["white"], cols["05_Sensor"], sensor_root, 96, 0.0006)
    set_props(port1, channel=1, connected=True)
    port2 = cylinder_axis("SensorPort_2", (0.061, 0.009, 0.018), 0.0052, 0.014, "X", mats["white"], cols["05_Sensor"], sensor_root, 96, 0.0006)
    set_props(port2, channel=2, connected=False)
    cylinder_axis("SensorPort_1_Bore", (0.0681, -0.009, 0.018), 0.0022, 0.0008, "X", mats["detail"], cols["05_Sensor"], sensor_root, 48)
    cylinder_axis("SensorPort_2_Bore", (0.0681, 0.009, 0.018), 0.0022, 0.0008, "X", mats["detail"], cols["05_Sensor"], sensor_root, 48)
    port_label_1 = mesh_text_label(
        "SensorPortLabel_1", "1", (0.046, -0.009, 0.0305), 0.009,
        mats["white"], cols["05_Sensor"], sensor_root,
    )
    port_label_2 = mesh_text_label(
        "SensorPortLabel_2", "2", (0.046, 0.009, 0.0305), 0.009,
        mats["white"], cols["05_Sensor"], sensor_root,
    )
    set_props(port_label_1, displayedNumber="1", adjacentTo="SensorPort_1", channel=1)
    set_props(port_label_2, displayedNumber="2", adjacentTo="SensorPort_2", channel=2)
    sensor_data_connector = empty(
        "SensorDataConnector", (-0.061, 0, 0.017), cols["05_Sensor"], sensor_root, size=0.008,
    )
    set_props(sensor_data_connector, connectorShape="circular_coaxial", replaces="rectangular_data_connector")
    sensor_data_port = cylinder_axis(
        "SensorDataCircularPort", (0, 0, 0), 0.0065, 0.010, "X",
        mats["steel"], cols["05_Sensor"], sensor_data_connector, 128, 0.0005,
    )
    cylinder_axis(
        "SensorDataCircularPort_Insulator", (-0.0053, 0, 0), 0.0047, 0.0015, "X",
        mats["detail"], cols["05_Sensor"], sensor_data_connector, 96, 0.0002,
    )
    sensor_data_collar = cylinder_axis(
        "SensorDataCircularPort_LockingCollar", (-0.0080, 0, 0), 0.0072, 0.006, "X",
        mats["steel"], cols["05_Sensor"], sensor_data_connector, 128, 0.0004,
    )
    sensor_data_plug = cylinder_axis(
        "SensorDataCircularPort_CablePlug", (-0.0140, 0, 0), 0.0058, 0.010, "X",
        mats["hose"], cols["05_Sensor"], sensor_data_connector, 96, 0.0005,
    )
    set_props(sensor_data_port, circular=True, axis="X", connected=True)
    set_props(sensor_data_collar, rotatesToLock=True, matesWith="SensorDataCircularPort_CablePlug")
    set_props(sensor_data_plug, connectedTo="DataCable_SensorToUniversal")
    rubber_root = empty("SensorRubberFeet", (0, 0, 0), cols["05_Sensor"], sensor_root, size=0.006)
    for i, (x, y) in enumerate(((-0.043, -0.012), (-0.043, 0.012), (0.043, -0.012), (0.043, 0.012))):
        foot = cylinder(f"SensorRubberFoot_{i+1}", (x, y, 0.0015), 0.004, 0.003, mats["rubber"], cols["05_Sensor"], rubber_root, 48, 0.0004)
        set_props(foot, contactZ=0.0)

    # Detailed 850-style universal interface, positioned left and behind the main apparatus.
    previous_universal_dims = Vector((0.500, 0.220, 0.165))
    universal_origin = Vector((-0.450, 0.150, 0.0))
    universal_dims = Vector((0.545, 0.220, 0.180))
    universal_root = empty(
        "UniversalInterface_ROOT", universal_origin, cols["05_DataSystem"], apparatus, size=0.030,
    )
    set_props(
        universal_root,
        deviceType="large_universal_data_interface",
        placement="left_rear_of_main_apparatus",
        interactive=True,
    )
    universal_shell = cube(
        "UniversalInterface_RoundedHousing", (0, 0, 0.095), universal_dims,
        mats["interface_body"], cols["05_DataSystem"], universal_root, 0.018,
    )
    set_props(
        universal_shell,
        shape="rounded_cuboid",
        referenceStyle="850_universal_interface",
        optimizedFrontPanel=True,
        brandLogoRemoved=True,
        topBrandBadgeModeled=True,
        topBadgeMarkingsRemoved=True,
        enlargedInXAndZ=True,
        frontModuleAreasPreserved=True,
    )
    universal_top_cover = cube(
        "UniversalInterface_TopCover", (0, 0.004, 0.183), (0.523, 0.198, 0.010),
        mats["white"], cols["05_DataSystem"], universal_root, 0.0,
    )
    top_cover_surface_z = 0.188
    top_badge_center = Vector((0.0, 0.004, 0.0))
    top_badge_recess_dims = Vector((0.150, 0.052, 0.0018))
    top_badge_inlay_dims = Vector((0.140, 0.042, 0.0008))
    top_badge_recess_depth = 0.0018
    top_badge_corner_radius = 0.007
    top_badge_root = empty(
        "UniversalInterface_TopBadge", (0, 0, 0), cols["05_DataSystem"], universal_root, size=0.012,
    )
    badge_recess_cutter = cube(
        "UniversalInterface_TopBadge_Recess_CUTTER",
        (top_badge_center.x, top_badge_center.y, top_cover_surface_z - 0.0007),
        (top_badge_recess_dims.x, top_badge_recess_dims.y, 0.0026),
        None, cols["05_DataSystem"], universal_root, top_badge_corner_radius,
    )
    badge_boolean = universal_top_cover.modifiers.new("TopBadge_RoundedRecess", "BOOLEAN")
    badge_boolean.operation = "DIFFERENCE"
    badge_boolean.solver = "EXACT"
    badge_boolean.object = badge_recess_cutter
    bpy.context.view_layer.objects.active = universal_top_cover
    universal_top_cover.select_set(True)
    badge_recess_cutter.select_set(False)
    bpy.ops.object.modifier_apply(modifier=badge_boolean.name)
    bpy.data.objects.remove(badge_recess_cutter, do_unlink=True)
    bevel(universal_top_cover, 0.010)

    top_badge_recess = cube(
        "UniversalInterface_TopBadge_Recess",
        (top_badge_center.x, top_badge_center.y, top_cover_surface_z - top_badge_recess_depth + 0.00030),
        (top_badge_recess_dims.x - 0.002, top_badge_recess_dims.y - 0.002, 0.00060),
        mats["interface_panel"], cols["05_DataSystem"], top_badge_root, top_badge_corner_radius,
    )
    top_badge_inlay = cube(
        "UniversalInterface_TopBadge_Inlay",
        (top_badge_center.x, top_badge_center.y, top_cover_surface_z - 0.00105),
        tuple(top_badge_inlay_dims), mats["interface_body"], cols["05_DataSystem"], top_badge_root, 0.0055,
    )
    set_props(
        top_badge_root,
        structure="rounded_rectangular_recess_with_inset_brand_plate",
        referenceDevice="PASCO_850_Universal_Interface_UI-5000",
        centeredOnTopCover=True,
        recessed=True,
        markingsRemoved=True,
    )
    set_props(top_badge_recess, recessFloor=True, recessDepth=top_badge_recess_depth)
    set_props(top_badge_inlay, insetBrandPlate=True, seatedBelowTopSurface=True)
    housing_front_plane_y = -0.116
    module_front_plane_y = -0.120
    module_text_plane_y = module_front_plane_y - 0.00005
    recess_face_y = module_front_plane_y + 0.0012
    power_x = -0.220
    power_z = 0.130
    status_z = 0.103

    universal_front_panel = cube_with_circular_y_holes(
        "UniversalInterface_FrontPanel", (0, -0.112, 0.095), (0.478, 0.008, 0.151),
        ((power_x, power_z, 0.0125), (power_x, status_z, 0.0037)),
        mats["interface_body"], cols["05_DataSystem"], universal_root, 0.014,
    )
    power_module = empty("UniversalInterface_PowerModule", (0, 0, 0), cols["05_DataSystem"], universal_root, size=0.010)
    digital_module = empty("UniversalInterface_DigitalInputModule", (0, 0, 0), cols["05_DataSystem"], universal_root, size=0.010)
    analog_module = empty("UniversalInterface_AnalogInputModule", (0, 0, 0), cols["05_DataSystem"], universal_root, size=0.010)
    pasport_module = empty("UniversalInterface_PASPORTModule", (0, 0, 0), cols["05_DataSystem"], universal_root, size=0.010)
    output_module = empty("UniversalInterface_OutputModule", (0, 0, 0), cols["05_DataSystem"], universal_root, size=0.010)

    interface_labels = []
    interface_text_bold_offset = 0.00030

    def interface_label(name, text_body, loc, size, parent, label_mat=None):
        flat_loc = (loc[0], module_text_plane_y, loc[2])
        label = mesh_text_label(
            name, text_body, flat_loc, size, label_mat or mats["white"],
            cols["05_DataSystem"], parent, flat=True, outline_offset=interface_text_bold_offset,
        )
        label.rotation_euler[0] = math.radians(90)
        set_props(
            label,
            functionalLabel=True,
            exportAsMesh=True,
            sourceTextSize=size,
            strokeOffset=interface_text_bold_offset,
        )
        interface_labels.append(label)
        return label

    digital_x = (-0.174, -0.148, -0.122, -0.096)
    analog_x = (-0.046, -0.002, 0.042, 0.086)
    pasport_x = (-0.159, -0.077, 0.005, 0.087)
    pasport_vertical_shift = 0.012
    output_x = (0.177, 0.211)
    digital_port_z = 0.114
    analog_port_z = 0.114
    pasport_port_z = 0.041 + pasport_vertical_shift
    output_banana_z = 0.128
    output_bnc_z = 0.060

    digital_panel_center = Vector((-0.135, -0.1175, 0.118))
    digital_panel_dims = Vector((0.112, 0.005, 0.054))
    analog_panel_center = Vector((0.020, -0.1175, 0.118))
    analog_panel_dims = Vector((0.174, 0.005, 0.054))
    output_panel_center = Vector((0.194, -0.1175, 0.088))
    output_panel_dims = Vector((0.073, 0.005, 0.106))
    pasport_panel_center = Vector((-0.020, -0.1175, 0.043 + pasport_vertical_shift))
    pasport_panel_dims = Vector((0.350, 0.006, 0.052))

    digital_panel = cube_with_circular_y_holes(
        "UniversalInterface_DigitalPanel", digital_panel_center, digital_panel_dims,
        tuple((x, digital_port_z, 0.0065) for x in digital_x),
        mats["interface_panel"], cols["05_DataSystem"], digital_module, 0.010,
    )
    analog_panel = cube_with_circular_y_holes(
        "UniversalInterface_AnalogPanel", analog_panel_center, analog_panel_dims,
        tuple((x, analog_port_z, 0.0125) for x in analog_x),
        mats["interface_panel"], cols["05_DataSystem"], analog_module, 0.010,
    )
    output_panel = cube_with_circular_y_holes(
        "UniversalInterface_OutputPanel", output_panel_center, output_panel_dims,
        (
            (output_x[0], output_banana_z, 0.0082),
            (output_x[1], output_banana_z, 0.0082),
            (output_x[0], output_bnc_z, 0.0078),
            (output_x[1], output_bnc_z, 0.0078),
        ),
        mats["interface_panel"], cols["05_DataSystem"], output_module, 0.010,
    )
    lower_blue_panel = empty(
        "UniversalInterface_LowerBluePanel", pasport_panel_center,
        cols["05_DataSystem"], pasport_module, size=0.008,
    )
    set_props(lower_blue_panel, representedBy="UniversalInterface_PASPortPanel_1_to_4")
    set_props(pasport_module, verticalShift=pasport_vertical_shift, shiftDirection="positive_Z")

    power_ring = torus(
        "UniversalInterface_PowerRing",
        (power_x, housing_front_plane_y + 0.0018, power_z),
        0.0102, 0.0015, mats["detail"], cols["05_DataSystem"], power_module,
        rotation=(math.radians(90), 0.0, 0.0),
    )
    power_button = cylinder_axis(
        "UniversalInterface_PowerButton",
        (power_x, housing_front_plane_y + 0.0016, power_z),
        0.0093, 0.0020, "Y", mats["interface_blue"],
        cols["05_DataSystem"], power_module, 96, 0.0002,
    )
    status_led = cylinder_axis(
        "UniversalInterface_StatusLED",
        (power_x, housing_front_plane_y + 0.00125, status_z),
        0.0030, 0.0015, "Y", mats["indicator_green"],
        cols["05_DataSystem"], power_module, 64, 0.0001,
    )
    set_props(power_ring, seatedIn="UniversalInterface_FrontPanel", recessed=True)
    set_props(power_button, seatedIn="UniversalInterface_FrontPanel", recessed=True)
    set_props(status_led, seatedIn="UniversalInterface_FrontPanel", recessed=True)

    digital_ports = []
    digital_trim_rings = []
    digital_bezel_rings = []
    digital_throat_rings = []
    digital_bores = []
    digital_contact_springs = []
    digital_outer_radius = 0.0065
    digital_jack_bore_radius = 0.00330
    digital_inner_face_y = recess_face_y + 0.00105
    for index, x in enumerate(digital_x, start=1):
        prefix = f"UniversalInterface_DigitalInput_{index}"
        digital_port = empty(
            prefix, (x, 0.0, digital_port_z),
            cols["05_DataSystem"], digital_module, size=0.006,
        )
        digital_ports.append(digital_port)
        set_props(
            digital_port,
            connectorType="6.35mm_TRS_stereo_phone_jack",
            digitalChannel=index,
            recessed=True,
            precisionModeled=True,
            panelFacePlaneY=module_front_plane_y,
            socketFrontY=recess_face_y,
            outerDiameter=digital_outer_radius * 2.0,
            nominalPlugDiameter=0.00635,
        )

        trim_ring = torus(
            prefix + "_MetalTrimRing", (0.0, module_front_plane_y - 0.00018, 0.0),
            0.00585, 0.00065, mats["din_metal"], cols["05_DataSystem"], digital_port,
            rotation=(math.radians(90), 0.0, 0.0),
        )
        digital_trim_rings.append(trim_ring)
        set_props(trim_ring, function="jack_panel_retainer", flushMounted=True)

        bezel_ring = ring_wall(
            prefix + "_SteppedBezel", (0.0, module_front_plane_y + 0.00075, 0.0),
            0.00575, 0.00425, 0.0030,
            mats["detail"], cols["05_DataSystem"], digital_port, 128,
        )
        bezel_ring.rotation_euler[0] = math.radians(90)
        digital_bezel_rings.append(bezel_ring)
        set_props(bezel_ring, function="recessed_jack_bezel", steppedProfile=True)

        throat_ring = ring_wall(
            prefix + "_JackThroat", (0.0, recess_face_y + 0.00035, 0.0),
            0.00425, digital_jack_bore_radius, 0.0024,
            mats["din_metal"], cols["05_DataSystem"], digital_port, 128,
        )
        throat_ring.rotation_euler[0] = math.radians(90)
        digital_throat_rings.append(throat_ring)
        set_props(throat_ring, function="TRS_ground_sleeve_contact", recessed=True)

        bore = cylinder_axis(
            prefix + "_CentralBore", (0.0, digital_inner_face_y, 0.0),
            digital_jack_bore_radius, 0.0016, "Y",
            mats["socket_void"], cols["05_DataSystem"], digital_port, 96, 0.00018,
        )
        for polygon in bore.data.polygons:
            polygon.use_smooth = False
        digital_bores.append(bore)
        set_props(bore, deepSocketOpening=True, acceptsPlugDiameter=0.00635)

        # Keep the two visible TRS contact springs as an exact mirror pair about
        # the socket's vertical centreline.  All four channels reuse this layout.
        for contact_name, dx, dz, rotation_z in (
            ("Tip", -0.00165, 0.0, -18.0),
            ("Ring", 0.00165, 0.0, 18.0),
        ):
            spring = cube(
                f"{prefix}_ContactSpring_{contact_name}",
                (dx, digital_inner_face_y - 0.00088, dz),
                (0.00055, 0.00035, 0.00210), mats["din_metal"], cols["05_DataSystem"], digital_port, 0.00018,
            )
            spring.rotation_euler[1] = math.radians(rotation_z)
            digital_contact_springs.append(spring)
            set_props(
                spring,
                internalTRSContact=contact_name,
                recessed=True,
                symmetricContactPair=True,
                symmetryAxis="local_vertical_centerline",
            )

        interface_label(f"UniversalInterface_DigitalLabel_{index}", str(index), (x, 0.0, 0.137), 0.0110, digital_module)
    interface_label("UniversalInterface_DigitalTitle", "DIGITAL INPUTS", (-0.135, 0.0, 0.098), 0.0073, digital_module)

    analog_letters = ("A", "B", "C", "D")
    analog_ports = []
    analog_trim_rings = []
    analog_bezel_rings = []
    analog_shield_rings = []
    analog_insulators = []
    analog_pin_collars = []
    analog_pin_holes = []
    analog_locator_notches = []
    analog_locator_rails = []
    analog_outer_radius = 0.0125
    analog_bezel_outer_radius = 0.0117
    analog_bezel_inner_radius = 0.0097
    analog_shield_outer_radius = 0.01025
    analog_shield_inner_radius = 0.00905
    analog_insulator_radius = 0.00885
    analog_pin_arc_degrees = 270.0
    analog_pin_ring_radius = 0.00525
    analog_pin_collar_outer_radius = 0.00100
    analog_pin_hole_radius = 0.00065
    analog_inner_face_y = recess_face_y + 0.00115
    analog_pin_angles = [math.radians(135.0 + index * analog_pin_arc_degrees / 7.0) for index in range(8)]

    for index, (x, letter) in enumerate(zip(analog_x, analog_letters), start=1):
        prefix = f"UniversalInterface_AnalogInput_{letter}"
        analog_port = empty(
            prefix, (x, 0.0, analog_port_z),
            cols["05_DataSystem"], analog_module, size=0.009,
        )
        analog_ports.append(analog_port)
        set_props(
            analog_port,
            connectorType="full_size_8_pin_DIN_female",
            channel=letter,
            recessed=True,
            precisionModeled=True,
            panelFacePlaneY=module_front_plane_y,
            socketFrontY=recess_face_y,
            pinCount=8,
            pinArcDegrees=analog_pin_arc_degrees,
            pinArrangement="270_degree_horseshoe",
            orientationKey="upper_center",
            outerDiameter=analog_outer_radius * 2.0,
        )

        trim_ring = torus(
            prefix + "_MetalTrimRing", (0.0, module_front_plane_y - 0.00025, 0.0),
            0.01135, 0.00115, mats["din_metal"], cols["05_DataSystem"], analog_port,
            rotation=(math.radians(90), 0.0, 0.0),
        )
        analog_trim_rings.append(trim_ring)
        set_props(trim_ring, function="panel_retaining_trim", flushMounted=True, machinedMetal=True)

        bezel_ring = ring_wall(
            prefix + "_SteppedBezel", (0.0, module_front_plane_y + 0.00085, 0.0),
            analog_bezel_outer_radius, analog_bezel_inner_radius, 0.0034,
            mats["detail"], cols["05_DataSystem"], analog_port, 192,
        )
        bezel_ring.rotation_euler[0] = math.radians(90)
        analog_bezel_rings.append(bezel_ring)
        set_props(bezel_ring, function="recessed_black_socket_bezel", steppedProfile=True)

        shield_ring = ring_wall(
            prefix + "_InnerShieldRing", (0.0, recess_face_y + 0.00025, 0.0),
            analog_shield_outer_radius, analog_shield_inner_radius, 0.0026,
            mats["din_metal"], cols["05_DataSystem"], analog_port, 192,
        )
        shield_ring.rotation_euler[0] = math.radians(90)
        analog_shield_rings.append(shield_ring)
        set_props(shield_ring, function="DIN_shell_shield", recessed=True, machinedMetal=True)

        insulator = cylinder_axis(
            prefix + "_InnerInsulator", (0.0, analog_inner_face_y, 0.0),
            analog_insulator_radius, 0.0014, "Y",
            mats["din_insulator"], cols["05_DataSystem"], analog_port, 160, 0.00020,
        )
        analog_insulators.append(insulator)
        set_props(insulator, dielectric=True, recessedDepth=analog_inner_face_y - module_front_plane_y)

        for pin_index, angle in enumerate(analog_pin_angles, start=1):
            dx = math.cos(angle) * analog_pin_ring_radius
            dz = math.sin(angle) * analog_pin_ring_radius
            pin_collar = ring_wall(
                f"{prefix}_PinCollar_{pin_index}",
                (dx, analog_inner_face_y - 0.00078, dz),
                analog_pin_collar_outer_radius, analog_pin_hole_radius, 0.00055,
                mats["din_metal"], cols["05_DataSystem"], analog_port, 72,
            )
            pin_collar.rotation_euler[0] = math.radians(90)
            analog_pin_collars.append(pin_collar)
            set_props(pin_collar, femaleContactRim=True, pinIndex=pin_index)
            pin_hole = cylinder_axis(
                f"{prefix}_PinHole_{pin_index}",
                (dx, analog_inner_face_y - 0.00110, dz), analog_pin_hole_radius, 0.00035, "Y",
                mats["detail"], cols["05_DataSystem"], analog_port, 48,
            )
            analog_pin_holes.append(pin_hole)
            set_props(
                pin_hole,
                recessed=True,
                femaleContactHole=True,
                pinIndex=pin_index,
                arrangementAngleDegrees=math.degrees(angle),
            )

        locator_notch = cube(
            prefix + "_LocatorNotch",
            (0.0, analog_inner_face_y - 0.00088, 0.00665),
            (0.00265, 0.00055, 0.00355), mats["detail"], cols["05_DataSystem"], analog_port, 0.00025,
        )
        analog_locator_notches.append(locator_notch)
        set_props(locator_notch, DINOrientationKey=True, keyPosition="upper_center", recessed=True)
        for side_name, side_sign in (("L", -1.0), ("R", 1.0)):
            rail = cube(
                f"{prefix}_LocatorRail_{side_name}",
                (side_sign * 0.00172, analog_inner_face_y - 0.00095, 0.00655),
                (0.00055, 0.00055, 0.00390), mats["din_metal"], cols["05_DataSystem"], analog_port, 0.00016,
            )
            analog_locator_rails.append(rail)
            set_props(rail, orientationKeyGuide=True, side=side_name)

        interface_label(f"UniversalInterface_AnalogLabel_{letter}", letter, (x, 0.0, 0.137), 0.0110, analog_module)
    interface_label(
        "UniversalInterface_AnalogTitle", "ANALOG INPUTS (+/-20 V MAX)",
        (0.020, 0.0, 0.097), 0.0060, analog_module,
    )

    pasport_panels = []
    pasport_ports = []
    pasport_trim_rings = []
    pasport_bezel_rings = []
    pasport_insulators = []
    pasport_pin_collars = []
    pasport_pin_holes = []
    pasport_locator_notches = []
    pasport_pin_hole_radius = 0.00200
    pasport_pin_ring_radius = 0.00600
    pasport_outer_radius = 0.00920
    pasport_bezel_outer_radius = 0.00870
    pasport_bezel_inner_radius = 0.00825
    pasport_insulator_radius = 0.00820
    pasport_pin_collar_outer_radius = 0.00215
    pasport_inner_face_y = recess_face_y + 0.00100
    pasport_pin_hole_adjacent_clearance = 2.0 * pasport_pin_ring_radius * math.sin(math.pi / 8.0) - 2.0 * pasport_pin_hole_radius
    for index, x in enumerate(pasport_x, start=1):
        pasport_panel = cube_with_circular_y_holes(
            f"UniversalInterface_PASPortPanel_{index}", (x, -0.1175, 0.043 + pasport_vertical_shift), (0.074, 0.005, 0.044),
            ((x, pasport_port_z, 0.0092),),
            mats["interface_blue"], cols["05_DataSystem"], pasport_module, 0.007,
        )
        pasport_panels.append(pasport_panel)
        prefix = f"UniversalInterface_PASPort_{index}"
        pasport_port = empty(
            prefix, (x, 0.0, pasport_port_z),
            cols["05_DataSystem"], pasport_module, size=0.008,
        )
        pasport_ports.append(pasport_port)
        set_props(
            pasport_port,
            connectorType="PASPORT_8_contact_female",
            channel=index,
            recessed=True,
            precisionModeled=True,
            panelFacePlaneY=module_front_plane_y,
            socketFrontY=recess_face_y,
            outerDiameter=pasport_outer_radius * 2.0,
            contactCount=8,
            contactHoleDiameter=pasport_pin_hole_radius * 2.0,
            pinAngularOffsetDegrees=22.5,
            orientationKey="upper_center",
        )

        trim_ring = torus(
            prefix + "_MetalTrimRing", (0.0, module_front_plane_y - 0.00018, 0.0),
            0.00835, 0.00085, mats["din_metal"], cols["05_DataSystem"], pasport_port,
            rotation=(math.radians(90), 0.0, 0.0),
        )
        pasport_trim_rings.append(trim_ring)
        set_props(trim_ring, function="PASPORT_panel_retainer", flushMounted=True)

        bezel_ring = ring_wall(
            prefix + "_SteppedBezel", (0.0, module_front_plane_y + 0.00078, 0.0),
            pasport_bezel_outer_radius, pasport_bezel_inner_radius, 0.0030,
            mats["detail"], cols["05_DataSystem"], pasport_port, 144,
        )
        bezel_ring.rotation_euler[0] = math.radians(90)
        pasport_bezel_rings.append(bezel_ring)
        set_props(bezel_ring, function="recessed_PASPORT_bezel", steppedProfile=True)

        insulator = cylinder_axis(
            prefix + "_InnerInsulator", (0.0, pasport_inner_face_y, 0.0),
            pasport_insulator_radius, 0.0014, "Y",
            mats["pasport_insulator"], cols["05_DataSystem"], pasport_port, 144, 0.00018,
        )
        pasport_insulators.append(insulator)
        set_props(insulator, dielectric=True, recessedDepth=pasport_inner_face_y - module_front_plane_y)

        for pin_index in range(8):
            angle = 2.0 * math.pi * (pin_index + 0.5) / 8.0
            dx = math.cos(angle) * pasport_pin_ring_radius
            dz = math.sin(angle) * pasport_pin_ring_radius
            pin_collar = ring_wall(
                f"{prefix}_PinCollar_{pin_index + 1}",
                (dx, pasport_inner_face_y - 0.00072, dz),
                pasport_pin_collar_outer_radius, pasport_pin_hole_radius, 0.00048,
                mats["din_metal"], cols["05_DataSystem"], pasport_port, 72,
            )
            pin_collar.rotation_euler[0] = math.radians(90)
            pasport_pin_collars.append(pin_collar)
            set_props(pin_collar, femaleContactRim=True, pinIndex=pin_index + 1)
            pin_hole = cylinder_axis(
                f"{prefix}_Pin_{pin_index + 1}",
                (dx, pasport_inner_face_y - 0.00055, dz),
                pasport_pin_hole_radius, 0.00032, "Y",
                mats["socket_void"], cols["05_DataSystem"], pasport_port, 64,
            )
            for polygon in pin_hole.data.polygons:
                polygon.use_smooth = False
            set_props(
                pin_hole,
                recessed=True,
                visiblePinHole=True,
                femaleContactHole=True,
                port=index,
                pinIndex=pin_index + 1,
                holeDiameter=pasport_pin_hole_radius * 2.0,
            )
            pasport_pin_holes.append(pin_hole)

        locator_notch = cube(
            prefix + "_LocatorNotch",
            (0.0, pasport_inner_face_y - 0.00084, 0.00775),
            (0.00235, 0.00052, 0.00125), mats["detail"], cols["05_DataSystem"], pasport_port, 0.00022,
        )
        pasport_locator_notches.append(locator_notch)
        set_props(locator_notch, orientationKey=True, keyPosition="upper_center", recessed=True)

        interface_label(
            f"UniversalInterface_PASPortLabel_{index}", f"PASPORT {index}",
            (x, 0.0, 0.057 + pasport_vertical_shift), 0.0078, pasport_module,
        )

    output_black = cylinder_axis(
        "UniversalInterface_Output_BananaBlack",
        (output_x[0], recess_face_y + 0.0015, output_banana_z), 0.0074, 0.0030, "Y",
        mats["detail"], cols["05_DataSystem"], output_module, 72, 0.0002,
    )
    output_red = cylinder_axis(
        "UniversalInterface_Output_BananaRed",
        (output_x[1], recess_face_y + 0.0015, output_banana_z), 0.0074, 0.0030, "Y",
        mats["output_red"], cols["05_DataSystem"], output_module, 72, 0.0002,
    )
    set_props(output_black, recessed=True, panelFacePlaneY=module_front_plane_y, socketFrontY=recess_face_y)
    set_props(output_red, recessed=True, panelFacePlaneY=module_front_plane_y, socketFrontY=recess_face_y)
    cylinder_axis("UniversalInterface_Output_BananaBlack_Bore", (output_x[0], recess_face_y + 0.00045, output_banana_z), 0.003, 0.0008, "Y", mats["interface_panel"], cols["05_DataSystem"], output_module, 48)
    cylinder_axis("UniversalInterface_Output_BananaRed_Bore", (output_x[1], recess_face_y + 0.00045, output_banana_z), 0.003, 0.0008, "Y", mats["interface_panel"], cols["05_DataSystem"], output_module, 48)
    interface_label("UniversalInterface_Output15VLabel", "+/-15 V @ 1 A", (0.194, 0.0, 0.111), 0.0051, output_module)
    interface_label("UniversalInterface_OutputTitle", "OUTPUTS", (0.194, 0.0, 0.094), 0.0071, output_module)

    # Precision BNC-style outputs 2/3.  Unlike the recessed input sockets,
    # these are hollow machined-metal sleeves that project from the front face.
    bnc_ports = []
    bnc_sleeves = []
    bnc_insulators = []
    bnc_center_contacts = []
    bnc_bayonet_lugs = []
    bnc_contact_slots = []
    bnc_body_length = 0.0180
    bnc_panel_insertion = 0.0015
    bnc_outer_radius = 0.0072
    bnc_inner_radius = 0.0054
    bnc_body_back_y = module_front_plane_y + bnc_panel_insertion
    bnc_body_front_y = bnc_body_back_y - bnc_body_length
    bnc_body_center_y = (bnc_body_front_y + bnc_body_back_y) * 0.5
    bnc_nominal_protrusion = module_front_plane_y - bnc_body_front_y

    for number, x in zip((2, 3), output_x):
        prefix = f"UniversalInterface_Output_BNC_{number}"
        bnc = empty(prefix, (x, 0.0, output_bnc_z), cols["05_DataSystem"], output_module, size=0.008)
        bnc_ports.append(bnc)
        set_props(
            bnc,
            connectorType="precision_BNC_female",
            outputChannel=number,
            projecting=True,
            metalRingSleeve=True,
            panelFacePlaneY=module_front_plane_y,
            bodyFrontY=bnc_body_front_y,
            bodyBackY=bnc_body_back_y,
            nominalProtrusion=bnc_nominal_protrusion,
        )

        gasket = torus(
            prefix + "_PanelGasket", (0.0, module_front_plane_y - 0.0002, 0.0),
            0.0083, 0.00115, mats["detail"], cols["05_DataSystem"], bnc,
            rotation=(math.radians(90), 0.0, 0.0),
        )
        set_props(gasket, function="panel_seal_and_backing_ring")

        flange = ring_wall(
            prefix + "_MountingFlange", (0.0, module_front_plane_y - 0.0006, 0.0),
            0.0094, bnc_outer_radius, 0.0032,
            mats["bnc_metal"], cols["05_DataSystem"], bnc, 192,
        )
        flange.rotation_euler[0] = math.radians(90)
        set_props(flange, function="panel_mounting_flange", machinedMetal=True)

        sleeve = ring_wall(
            prefix + "_OuterSleeve", (0.0, bnc_body_center_y, 0.0),
            bnc_outer_radius, bnc_inner_radius, bnc_body_length,
            mats["bnc_metal"], cols["05_DataSystem"], bnc, 192,
        )
        sleeve.rotation_euler[0] = math.radians(90)
        bnc_sleeves.append(sleeve)
        set_props(
            sleeve,
            hollow=True,
            machinedMetal=True,
            outerDiameter=bnc_outer_radius * 2.0,
            innerDiameter=bnc_inner_radius * 2.0,
            axialLength=bnc_body_length,
        )

        front_lip = torus(
            prefix + "_RolledFrontLip", (0.0, bnc_body_front_y - 0.0001, 0.0),
            0.00625, 0.00095, mats["bnc_metal"], cols["05_DataSystem"], bnc,
            rotation=(math.radians(90), 0.0, 0.0),
        )
        set_props(front_lip, function="reinforced_connector_mouth", machinedMetal=True)

        insulator = cylinder_axis(
            prefix + "_InnerInsulator",
            (0.0, bnc_body_front_y + 0.00085, 0.0), 0.00475, 0.0015, "Y",
            mats["detail"], cols["05_DataSystem"], bnc, 128, 0.00015,
        )
        bnc_insulators.append(insulator)
        set_props(insulator, dielectric=True, recessedInsideSleeve=True)

        center_contact = ring_wall(
            prefix + "_CenterContact", (0.0, bnc_body_front_y - 0.00005, 0.0),
            0.00205, 0.00072, 0.0012,
            mats["bnc_metal"], cols["05_DataSystem"], bnc, 128,
        )
        center_contact.rotation_euler[0] = math.radians(90)
        bnc_center_contacts.append(center_contact)
        set_props(center_contact, femaleContact=True, hollowCenter=True, machinedMetal=True)

        bore = cylinder_axis(
            prefix + "_CenterBore", (0.0, bnc_body_front_y - 0.00072, 0.0),
            0.00070, 0.00035, "Y", mats["detail"], cols["05_DataSystem"], bnc, 48,
        )
        set_props(bore, contactOpening=True)

        for slot_index in range(3):
            angle = math.radians(90.0 + slot_index * 120.0)
            slot = cylinder_axis(
                f"{prefix}_ContactSlot_{slot_index + 1}",
                (math.cos(angle) * 0.00135, bnc_body_front_y - 0.00070, math.sin(angle) * 0.00135),
                0.00034, 0.00040, "Y", mats["detail"], cols["05_DataSystem"], bnc, 32,
            )
            bnc_contact_slots.append(slot)
            set_props(slot, precisionContactRelief=True, radialIndex=slot_index + 1)

        for side_name, side_sign in (("L", -1.0), ("R", 1.0)):
            lug = cube(
                f"{prefix}_BayonetLug_{side_name}",
                (side_sign * (bnc_outer_radius + 0.00075), bnc_body_front_y + 0.0062, 0.0),
                (0.0023, 0.0042, 0.0028), mats["bnc_metal"], cols["05_DataSystem"], bnc, 0.00055,
            )
            bnc_bayonet_lugs.append(lug)
            set_props(lug, bayonetLockingStud=True, side=side_name)

        interface_label(f"UniversalInterface_Output_BNCLabel_{number}", str(number), (x, 0.0, 0.078), 0.0075, output_module)
    interface_label("UniversalInterface_Output10VLabel", "+/-10 V @ 50 mA", (0.194, 0.0, 0.041), 0.0048, output_module)

    universal_input_plug_depth = 0.020
    universal_input_plug_y = recess_face_y - universal_input_plug_depth * 0.5
    universal_input_plug = cylinder_axis(
        "UniversalInterface_DataCablePlug", (pasport_x[0], universal_input_plug_y, pasport_port_z), 0.0064, universal_input_plug_depth, "Y",
        mats["steel"], cols["05_DataSystem"], pasport_module, 96, 0.0005,
    )
    set_props(
        universal_input_plug,
        connectedTo="UniversalInterface_PASPort_1",
        cable="DataCable_SensorToUniversal",
        channel=1,
        seated=True,
        insertionEndY=recess_face_y,
    )
    set_props(pasport_ports[0], occupiedBy="UniversalInterface_DataCablePlug", connected=True)
    universal_feet = []
    for index, (x, y) in enumerate(((-0.210, -0.085), (-0.210, 0.085), (0.210, -0.085), (0.210, 0.085)), start=1):
        foot = cylinder(
            f"UniversalInterface_Foot_{index}", (x, y, 0.004), 0.011, 0.008,
            mats["rubber"], cols["05_DataSystem"], universal_root, 64, 0.0008,
        )
        set_props(foot, contactZ=0.0)
        universal_feet.append(foot)

    def panel_rect_xz(center, dims):
        return (
            center.x - dims.x * 0.5,
            center.x + dims.x * 0.5,
            center.z - dims.z * 0.5,
            center.z + dims.z * 0.5,
        )

    front_module_rects = [
        panel_rect_xz(digital_panel_center, digital_panel_dims),
        panel_rect_xz(analog_panel_center, analog_panel_dims),
        panel_rect_xz(pasport_panel_center, pasport_panel_dims),
        panel_rect_xz(output_panel_center, output_panel_dims),
    ]

    def panel_rects_overlap(first, second):
        return min(first[1], second[1]) > max(first[0], second[0]) and min(first[3], second[3]) > max(first[2], second[2])

    front_modules_nonoverlapping = all(
        not panel_rects_overlap(front_module_rects[i], front_module_rects[j])
        for i in range(len(front_module_rects))
        for j in range(i + 1, len(front_module_rects))
    )
    front_modules_inside_outline = all(
        rect[0] >= -universal_dims.x * 0.5
        and rect[1] <= universal_dims.x * 0.5
        and rect[2] >= 0.0
        and rect[3] <= universal_dims.z + 0.005
        for rect in front_module_rects
    )
    pasport_to_upper_clearance = min(
        front_module_rects[0][2], front_module_rects[1][2],
    ) - front_module_rects[2][3]

    sensor_data_endpoint_local = world_from_local(
        sensor_origin,
        sensor_angle,
        tuple(value * sensor_scale for value in (-0.080, 0.0, 0.017)),
    )
    sensor_data_endpoint = sensor_data_endpoint_local + all_instruments_xy_shift
    universal_data_endpoint_local = universal_origin + Vector((
        pasport_x[0],
        universal_input_plug_y - universal_input_plug_depth * 0.5,
        pasport_port_z,
    ))
    universal_data_endpoint = universal_data_endpoint_local + all_instruments_xy_shift
    sensor_data_outward = Vector((-math.cos(sensor_angle), -math.sin(sensor_angle), 0.0))
    data_cable_points = [
        sensor_data_endpoint_local,
        sensor_data_endpoint_local + sensor_data_outward * 0.028,
        Vector((-0.250, -0.290, 0.020)),
        Vector((-0.550, -0.205, 0.018)),
        Vector((universal_data_endpoint_local.x, universal_data_endpoint_local.y - 0.050, 0.026)),
        universal_data_endpoint_local + Vector((0.0, -0.028, 0.0)),
        universal_data_endpoint_local,
    ]
    data_cable = curve_tube(
        "DataCable_SensorToUniversal", data_cable_points, 0.0032,
        mats["data_cable"], cols["05_DataSystem"], apparatus,
    )
    set_props(
        data_cable,
        cableType="sensor_data",
        connectsFrom="SensorDataCircularPort_CablePlug",
        connectsTo="UniversalInterface_DataCablePlug",
        sensorTerminalAxis="negative_local_X",
        interfaceTerminalAxis="positive_Y",
    )
    data_anchor_sensor = empty(
        "ANCHOR_DataCable_Sensor", sensor_data_endpoint, cols["06_Anchors"], anchors, "ARROWS", 0.008,
    )
    data_anchor_interface = empty(
        "ANCHOR_DataCable_Interface", universal_data_endpoint, cols["06_Anchors"], anchors, "ARROWS", 0.008,
    )
    set_props(data_anchor_sensor, helper=True)
    set_props(data_anchor_interface, helper=True)

    hose_end_local = world_from_local(
        sensor_origin,
        sensor_angle,
        tuple(value * sensor_scale for value in (0.069, -0.009, 0.018)),
    )
    hose_end = hose_end_local + all_instruments_xy_shift
    sensor_axis = Vector((math.cos(sensor_angle), math.sin(sensor_angle), 0))
    hose_penultimate_local = hose_end_local + sensor_axis * 0.022
    hose_points = [
        hose_start_local,
        hose_start_local + Vector((0, 0, 0.040)),
        Vector((-0.050, -0.145, hose_start_local.z + 0.025)),
        Vector((-0.030, -0.220, 0.035)),
        Vector((-0.005, -0.245, 0.008)),
        hose_penultimate_local,
        hose_end_local,
    ]
    hose = curve_tube("Hose_Main_Default", hose_points, 0.0025, mats["hose"], cols["04_Pneumatic"], pneumatic_hose)
    set_props(
        hose,
        pneumatic=True,
        outerDiameter=0.005,
        innerDiameter=0.0032,
        dynamicInThreeJS=True,
        detachableAt="Connector_Main_QuickDisconnect",
        terminalInsertionAxis="vertical_Z",
        airtightWhenConnected=True,
    )

    cylinder_air_inlet_source = Vector((cyl_center[0], cyl_center[1], 0.133))
    cylinder_air_inlet = cylinder(
        "Cylinder_BottomAirInlet", cylinder_air_inlet_source,
        0.0052, 0.012, mats["detail"], cols["04_Pneumatic"], pneumatic, 96, 0.0005,
    )
    set_props(cylinder_air_inlet, connectsTo="Cylinder_Pyrex", line="sealed_working_air")
    internal_entry_local = instrument_apparatus_local((hose_port_source_xy.x, hose_port_source_xy.y, top_lip_top_z + 0.004))
    internal_down_local = instrument_apparatus_local((hose_port_source_xy.x, hose_port_source_xy.y, housing_bottom_z + 0.012))
    internal_turn_local = instrument_apparatus_local((-0.022, -0.034, housing_bottom_z + 0.010))
    internal_rise_local = instrument_apparatus_local((-0.006, cyl_center[1], 0.125))
    cylinder_air_endpoint_local = instrument_apparatus_local(cylinder_air_inlet_source)
    internal_entry = internal_entry_local + all_instruments_xy_shift
    cylinder_air_endpoint = cylinder_air_endpoint_local + all_instruments_xy_shift
    internal_hose_points = [
        internal_entry_local, internal_down_local, internal_turn_local,
        internal_rise_local, cylinder_air_endpoint_local,
    ]
    internal_hose = curve_tube(
        "Hose_Internal_ToCylinder", internal_hose_points, 0.0022,
        mats["hose"], cols["04_Pneumatic"], pneumatic_hose,
    )
    set_props(
        internal_hose,
        pneumatic=True,
        hiddenInsideHousing=True,
        connectsFrom="Connector_Main_QuickDisconnect",
        connectsTo="Cylinder_BottomAirInlet",
        continuousWith="Hose_Main_Default_when_connected",
        sealedWorkingVolume=True,
    )
    set_props(
        piston_root,
        lockedByPneumaticSealWhen="Connector_Main_QuickDisconnect.connected_sealed",
        freeVolumeAdjustmentWhen="Connector_Main_QuickDisconnect.disconnected_open_to_atmosphere",
    )

    for name, point in (
        ("ANCHOR_Hose_Start", hose_start),
        ("ANCHOR_Hose_End", hose_end),
        ("ANCHOR_Hose_Control_1", hose_points[2] + all_instruments_xy_shift),
        ("ANCHOR_Hose_Control_2", hose_points[4] + all_instruments_xy_shift),
        ("ANCHOR_InternalHose_QuickDisconnect", internal_entry),
        ("ANCHOR_InternalHose_Cylinder", cylinder_air_endpoint),
        ("AXIS_Piston", instrument_world((cyl_center[0], cyl_center[1], 0.135))),
        ("AXIS_RodClamp", (rod_axis_world_xy.x, rod_axis_world_xy.y, rod_connection_z)),
    ):
        anchor = empty(name, point, cols["06_Anchors"], anchors, "ARROWS", 0.010)
        set_props(anchor, helper=True)

    housing_collider_source_center = (
        0.0,
        -0.010,
        (min(housing_bottom_z, top_lip_bottom_z) + max(housing_top_z, top_lip_top_z)) * 0.5,
    )
    housing_collider_source_dims = (
        max(housing_dims[0], top_lip_dims[0]) + 0.002,
        max(housing_dims[1], top_lip_dims[1]) + 0.002,
        housing_combined_height + 0.002,
    )
    collider_specs = (
        ("COL_Base", tuple(all_instruments_xy_shift + main_instrument_xy_shift + Vector((0, 0.005, 0.078))), (0.330, 0.330, 0.156)),
        ("COL_Housing", tuple(instrument_world(housing_collider_source_center)), tuple(value * instrument_scale for value in housing_collider_source_dims)),
        (
            "COL_ProtectiveFrame", tuple(instrument_world(frame_center)),
            tuple(value * instrument_scale for value in (frame_outer_size[0] + 0.002, frame_outer_size[1] + 0.002, frame_outer_size[2] + 0.002)),
        ),
        (
            "COL_PressureSensor",
            tuple(Vector(sensor_origin) + all_instruments_xy_shift + Vector((0.0, 0.0, 0.017 * sensor_scale))),
            tuple(value * sensor_scale for value in (0.118, 0.041, 0.028)),
        ),
        (
            "COL_UniversalInterface",
            tuple(all_instruments_xy_shift + universal_origin + Vector((0.0, 0.0, (universal_dims.z + 0.008) * 0.5))),
            tuple(universal_dims + Vector((0.006, 0.006, 0.008))),
        ),
        ("COL_Tabletop", tuple(table_center), tuple(table_dims)),
    )
    for name, loc, dims in collider_specs:
        col_obj = cube(name, loc, dims, mats["collider"], cols["07_Colliders"], colliders)
        col_obj.display_type = "WIRE"
        col_obj.hide_render = True
        set_props(col_obj, collider=True, visibleDefault=False)

    # Neutral studio lighting on a white tabletop; no laboratory background.
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg = next((n for n in world.node_tree.nodes if n.type == "BACKGROUND"), None)
    if bg:
        bg.inputs["Color"].default_value = (0.92, 0.93, 0.94, 1.0)
        bg.inputs["Strength"].default_value = 0.08

    for name, loc, energy, size, target in (
        ("Key_Softbox", (-0.32, -0.38, 0.62), 18.0, 0.35, (0, -0.03, 0.20)),
        ("Fill_Softbox", (0.38, -0.12, 0.44), 9.0, 0.28, (0, -0.03, 0.19)),
        ("Rim_Softbox", (0.10, 0.34, 0.50), 13.0, 0.24, (0, 0.0, 0.22)),
    ):
        bpy.ops.object.light_add(type="AREA", location=loc)
        light = bpy.context.object
        light.name = name
        light.data.energy = energy
        light.data.shape = "DISK"
        light.data.size = size
        point_at(light, target)
        relink(light, cols["08_Lighting"])

    cameras = {}
    camera_specs = {
        "hero": ((0.38, -0.76, 0.43), (-0.115, -0.095, 0.225), 45),
        "front": ((-0.10, -0.82, 0.30), (-0.10, -0.058, 0.235), 50),
        "scale_detail": ((-0.10, -0.70, 0.360), (-0.10, -0.055, 0.323), 45),
        "upper_assembly": ((-0.10, -0.86, 0.465), (-0.10, -0.055, 0.350), 45),
        "side": ((0.66, -0.06, 0.32), (-0.10, -0.050, 0.235), 50),
        "back": ((-0.10, 0.71, 0.32), (-0.10, -0.040, 0.235), 50),
        "top": ((-0.10, -0.04, 1.70), (-0.10, -0.04, 0.050), 45),
        "base_top": ((-0.099, -0.025, 0.46), (-0.10, -0.025, 0.025), 50),
        "base_foot_detail": ((-0.095, -0.350, 0.095), (-0.010, -0.189, 0.010), 65),
        "sensor_hose": ((0.24, -0.48, 0.16), (-0.060, -0.215, 0.075), 58),
        "sensor_ports": ((-0.105, -0.260, 0.250), (-0.095, -0.258, 0.015), 65),
        "sensor_data_connector": ((-0.355, -0.390, 0.125), (-0.180, -0.272, 0.020), 72),
        "system_overview": ((0.84, -1.16, 0.68), (-0.165, -0.010, 0.165), 39),
        "universal_interface": ((-0.450, -0.650, 0.275), (-0.450, 0.035, 0.095), 52),
        "universal_top_badge": ((-0.450, -0.245, 0.355), (-0.450, 0.150, 0.184), 76),
        "universal_digital_inputs": ((-0.585, -0.350, 0.118), (-0.585, 0.030, 0.118), 92),
        "universal_analog_inputs": ((-0.430, -0.350, 0.118), (-0.430, 0.030, 0.118), 70),
        "universal_pasport_inputs": ((-0.470, -0.560, 0.055), (-0.470, 0.030, 0.055), 62),
        "universal_bnc_outputs": ((-0.256, -0.240, 0.105), (-0.256, 0.030, 0.061), 85),
        "data_link": ((-0.710, -0.560, 0.325), (-0.355, -0.105, 0.065), 47),
        "quick_disconnect": ((-0.29, -0.34, 0.29), (-0.150, -0.114, 0.235), 75),
        "rod_knob_back": ((-0.10, 0.30, 0.41), (-0.10, 0.010, 0.383), 80),
        "piston_rod": ((-0.10, -0.55, 0.43), (-0.10, -0.05, 0.350), 72),
    }
    # Follow the translated ensemble for all detail/hero views.  Keep the top
    # camera fixed on the tabletop so centering remains directly inspectable.
    for label, (loc, target, lens) in list(camera_specs.items()):
        if label != "top":
            camera_specs[label] = (
                tuple(Vector(loc) + all_instruments_xy_shift),
                tuple(Vector(target) + all_instruments_xy_shift),
                lens,
            )
    for label, (loc, target, lens) in camera_specs.items():
        bpy.ops.object.camera_add(location=loc)
        cam = bpy.context.object
        cam.name = "Camera_" + label.capitalize()
        cam.data.lens = lens
        cam.data.sensor_width = 36
        point_at(cam, target)
        if label == "sensor_ports":
            # A true top view is singular for track-quaternion roll; lock world
            # X/Y to the image axes so the horizontal sensor and both ports fit.
            cam.rotation_euler = (0.0, 0.0, 0.0)
        relink(cam, cols["08_Lighting"])
        cameras[label] = cam

    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1100
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.look = "AgX - Medium High Contrast"

    # Save, render all QA directions, and export the selected runtime scene.
    scene.camera = cameras["hero"]
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    for label in (camera_specs if os.environ.get("EX5531_SKIP_PREVIEWS") != "1" else []):
        scene.camera = cameras[label]
        scene.render.filepath = os.path.join(PREVIEW_DIR, f"preview_{label}.png")
        hidden_for_base_top = []
        if label in {"base_top", "base_foot_detail"}:
            base_objects = set(cols["02_Stand"].objects)
            for obj in scene.objects:
                if obj.type in {"MESH", "CURVE"} and obj not in base_objects and obj.name != "Tabletop":
                    hidden_for_base_top.append((obj, obj.hide_render))
                    obj.hide_render = True
            if bpy.data.objects.get("SupportRod_45cm") is not None:
                support_rod_preview = bpy.data.objects["SupportRod_45cm"]
                hidden_for_base_top.append((support_rod_preview, support_rod_preview.hide_render))
                support_rod_preview.hide_render = True
        try:
            bpy.ops.render.render(write_still=True)
        except RuntimeError as error:
            # A foreground Blender image editor can briefly hold an existing
            # PNG on Windows.  Keep the last successfully rendered QA image
            # and continue so model export and verification are not lost.
            print(f"WARNING: preview write skipped for {label}: {error}")
        finally:
            for obj, previous_hide_render in hidden_for_base_top:
                obj.hide_render = previous_hide_render

    bpy.ops.object.select_all(action="DESELECT")
    for obj in scene.objects:
        if obj.type not in {"CAMERA", "LIGHT"}:
            obj.select_set(True)
    staging_glb_path = os.path.join(OUT_DIR, "EX5531_TD8572A_ratio_specific_heats_final_updated.glb")
    bpy.ops.export_scene.gltf(
        filepath=staging_glb_path,
        export_format="GLB",
        use_selection=True,
        export_animations=True,
        export_extras=True,
        export_apply=False,
    )
    exported_glb_path = GLB_PATH
    try:
        os.replace(staging_glb_path, GLB_PATH)
    except PermissionError as error:
        # Keep the newly exported alternate file when a foreground Blender
        # session currently owns the canonical GLB on Windows.
        exported_glb_path = staging_glb_path
        print(f"WARNING: canonical GLB is in use; retained updated export at {exported_glb_path}: {error}")

    required = [
        "RSH_Apparatus_ROOT", "Stand_ROOT", "Base_CastIron", "Base_CastIron_LeftBeam", "Base_CastIron_RightBeam", "LevelFoot_L", "LevelFoot_R",
        "VertexContactPad", "SupportRod_45cm", "InstrumentBodyScaled_ROOT", "HeatEngine_ROOT",
        "RodSupport_ROOT", "RodClampMount", "RodClampBridge", "RodClampKnob", "RodClampKnob_KnurledHead", "RodClampKnob_ThreadedShaft",
        "LowerHousing", "LowerHousing_TopLip", "BaseToInstrumentSupport_L", "BaseToInstrumentSupport_R",
        "BaseToInstrument_CrossMount", "BaseToInstrument_UpperCylinder", "ProtectiveFrame",
        "ProtectiveFrame_TopSlab", "ProtectiveFrame_BottomSlab", "ProtectiveFrame_TopBack",
        "ProtectiveFrame_FrontPanel", "ProtectiveFrame_BackPanel", "ProtectiveFrame_LeftPanel", "ProtectiveFrame_RightPanel", "Cylinder_Pyrex",
        "ScaleTicks_Unnumbered", "PistonAssembly_MOV", "Piston_Graphite",
        "ScaleLabel_90", "ScaleLabel_80", "ScaleLabel_70", "ScaleLabel_60", "ScaleLabel_50", "ScaleLabel_40",
        "ScaleLabel_30", "ScaleLabel_20", "ScaleLabel_10",
        "PistonRod", "MassPlatform", "MassPlatform_LowerPlate", "MassPlatform_UpperPlate",
        "MassPlatform_LeftPillar", "MassPlatform_RightPillar", "Pneumatic_ROOT",
        "PneumaticHose_ROOT", "Port_Main", "Connector_Main_QuickDisconnect", "Connector_Main_White",
        "Connector_Main_ThreadedStem", "Connector_Main_RotatingCollar", "Hose_Main_Default",
        "Hose_Internal_ToCylinder", "Cylinder_BottomAirInlet",
        "PressureSensor_ROOT", "SensorShell_Blue", "SensorInnerCore", "SensorPort_1",
        "SensorPort_2", "SensorPortLabel_1", "SensorPortLabel_2", "SensorDataConnector",
        "SensorDataCircularPort", "SensorDataCircularPort_LockingCollar", "SensorDataCircularPort_CablePlug",
        "SensorRubberFeet", "UniversalInterface_ROOT", "UniversalInterface_RoundedHousing",
        "UniversalInterface_TopCover", "UniversalInterface_TopBadge", "UniversalInterface_TopBadge_Recess",
        "UniversalInterface_TopBadge_Inlay",
        "UniversalInterface_FrontPanel", "UniversalInterface_PowerModule", "UniversalInterface_DigitalInputModule",
        "UniversalInterface_AnalogInputModule", "UniversalInterface_PASPORTModule", "UniversalInterface_OutputModule",
        "UniversalInterface_DigitalTitle", "UniversalInterface_AnalogTitle", "UniversalInterface_OutputTitle",
        "UniversalInterface_AnalogInput_A", "UniversalInterface_AnalogInput_B", "UniversalInterface_AnalogInput_C", "UniversalInterface_AnalogInput_D",
        "UniversalInterface_Output_BananaBlack", "UniversalInterface_Output_BananaRed",
        "UniversalInterface_Output_BNC_2", "UniversalInterface_Output_BNC_3",
        "UniversalInterface_Output_BNC_2_OuterSleeve", "UniversalInterface_Output_BNC_3_OuterSleeve",
        "UniversalInterface_Output_BNC_2_InnerInsulator", "UniversalInterface_Output_BNC_3_InnerInsulator",
        "UniversalInterface_Output_BNC_2_CenterContact", "UniversalInterface_Output_BNC_3_CenterContact",
        "UniversalInterface_Output_BNC_2_BayonetLug_L", "UniversalInterface_Output_BNC_2_BayonetLug_R",
        "UniversalInterface_Output_BNC_3_BayonetLug_L", "UniversalInterface_Output_BNC_3_BayonetLug_R",
        "UniversalInterface_DataCablePlug", "DataCable_SensorToUniversal",
        "ANCHOR_DataCable_Sensor", "ANCHOR_DataCable_Interface", "ANCHOR_Hose_Start",
        "ANCHOR_Hose_End", "ANCHOR_InternalHose_QuickDisconnect", "ANCHOR_InternalHose_Cylinder",
        "AXIS_Piston", "AXIS_RodClamp", "COL_Base",
        "COL_Housing", "COL_ProtectiveFrame", "COL_PressureSensor", "COL_UniversalInterface", "COL_Tabletop", "Tabletop",
    ]
    missing = [name for name in required if bpy.data.objects.get(name) is None]
    depsgraph = bpy.context.evaluated_depsgraph_get()
    triangles = 0
    for obj in scene.objects:
        if obj.type != "MESH" or obj.name.startswith("COL_"):
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        mesh.calc_loop_triangles()
        triangles += len(mesh.loop_triangles)
        evaluated.to_mesh_clear()

    bpy.context.view_layer.update()

    def world_bounds_xz(obj):
        corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        return (
            min(corner.x for corner in corners),
            max(corner.x for corner in corners),
            min(corner.z for corner in corners),
            max(corner.z for corner in corners),
        )

    def world_bounds_y(obj):
        corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        return (min(corner.y for corner in corners), max(corner.y for corner in corners))

    def world_bounds_xy(obj):
        corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        return (
            min(corner.x for corner in corners),
            max(corner.x for corner in corners),
            min(corner.y for corner in corners),
            max(corner.y for corner in corners),
        )

    def world_bounds_z(obj):
        corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        return (min(corner.z for corner in corners), max(corner.z for corner in corners))

    def bounds_inside_with_margin(inner, outer, margin):
        return (
            inner[0] >= outer[0] + margin
            and inner[1] <= outer[1] - margin
            and inner[2] >= outer[2] + margin
            and inner[3] <= outer[3] - margin
        )

    universal_outline_bounds = world_bounds_xz(universal_shell)
    universal_front_panel_bounds = world_bounds_xz(universal_front_panel)
    top_cover_world_bounds_z = world_bounds_z(universal_top_cover)
    top_badge_inlay_world_bounds_z = world_bounds_z(top_badge_inlay)
    top_badge_xy_center_error = max(
        abs(top_badge_inlay.location.x - universal_top_cover.location.x),
        abs(top_badge_inlay.location.y - universal_top_cover.location.y),
        abs(top_badge_recess.location.x - universal_top_cover.location.x),
        abs(top_badge_recess.location.y - universal_top_cover.location.y),
    )
    universal_front_panel_inside_housing = bounds_inside_with_margin(
        universal_front_panel_bounds, universal_outline_bounds, 0.010,
    )
    universal_front_panel_margin_x = min(
        universal_front_panel_bounds[0] - universal_outline_bounds[0],
        universal_outline_bounds[1] - universal_front_panel_bounds[1],
    )
    universal_front_panel_margin_z = min(
        universal_front_panel_bounds[2] - universal_outline_bounds[2],
        universal_outline_bounds[3] - universal_front_panel_bounds[3],
    )
    interface_labels_inside_outline = all(
        (lambda bounds: bounds[0] >= universal_outline_bounds[0] - 0.001
         and bounds[1] <= universal_outline_bounds[1] + 0.001
         and bounds[2] >= universal_outline_bounds[2] - 0.001
         and bounds[3] <= universal_outline_bounds[3] + 0.006)(world_bounds_xz(label))
        for label in interface_labels
    )
    interface_label_y_thickness_max = max((world_bounds_y(label)[1] - world_bounds_y(label)[0]) for label in interface_labels)
    universal_world_origin = universal_origin + all_instruments_xy_shift
    sensor_world_origin = Vector(sensor_origin) + all_instruments_xy_shift
    interface_label_plane_world_y = universal_world_origin.y + module_text_plane_y
    interface_labels_coplanar = all(
        abs((world_bounds_y(label)[0] + world_bounds_y(label)[1]) * 0.5 - interface_label_plane_world_y) < 1e-7
        for label in interface_labels
    )
    module_panel_objects = [digital_panel, analog_panel, output_panel] + pasport_panels
    module_panels_coplanar = all(
        abs(panel.get("frontFacePlaneY") - module_front_plane_y) < 1e-9
        for panel in module_panel_objects
    )
    digital_text_inside_panel = all(
        bounds_inside_with_margin(
            world_bounds_xz(bpy.data.objects[name]), world_bounds_xz(digital_panel), 0.0015,
        )
        for name in ["UniversalInterface_DigitalTitle"] + [f"UniversalInterface_DigitalLabel_{index}" for index in range(1, 5)]
    )
    analog_text_inside_panel = all(
        bounds_inside_with_margin(
            world_bounds_xz(bpy.data.objects[name]), world_bounds_xz(analog_panel), 0.0015,
        )
        for name in ["UniversalInterface_AnalogTitle"] + [f"UniversalInterface_AnalogLabel_{letter}" for letter in analog_letters]
    )
    pasport_text_inside_panels = all(
        bounds_inside_with_margin(
            world_bounds_xz(bpy.data.objects[f"UniversalInterface_PASPortLabel_{index}"]),
            world_bounds_xz(pasport_panels[index - 1]),
            0.0015,
        )
        for index in range(1, 5)
    )
    recessed_socket_objects = digital_ports + analog_ports + pasport_ports + [output_black, output_red]
    all_front_sockets_recessed = all(
        socket.get("recessed") is True
        and socket.get("socketFrontY") > socket.get("panelFacePlaneY")
        for socket in recessed_socket_objects
    )
    housing_front_world_y = universal_world_origin.y + housing_front_plane_y
    power_controls_seated = all(
        world_bounds_y(obj)[0] >= housing_front_world_y - 1e-7
        for obj in (power_ring, power_button, status_led)
    )
    pasport1_port_world_center = pasport_ports[0].matrix_world.translation
    universal_input_plug_world_center = universal_input_plug.matrix_world.translation
    universal_input_plug_inner_world_y = universal_world_origin.y + universal_input_plug_y + universal_input_plug_depth * 0.5
    pasport1_socket_front_world_y = universal_world_origin.y + recess_face_y
    universal_input_plug_seating_gap = abs(universal_input_plug_inner_world_y - pasport1_socket_front_world_y)
    universal_input_plug_axis_aligned = (
        abs(universal_input_plug_world_center.x - pasport1_port_world_center.x) < 1e-9
        and abs(universal_input_plug_world_center.z - pasport1_port_world_center.z) < 1e-9
    )
    digital_contact_symmetry_errors = []
    for index in range(1, 5):
        tip_contact = bpy.data.objects[f"UniversalInterface_DigitalInput_{index}_ContactSpring_Tip"]
        ring_contact = bpy.data.objects[f"UniversalInterface_DigitalInput_{index}_ContactSpring_Ring"]
        digital_contact_symmetry_errors.append(max(
            abs(tip_contact.location.x + ring_contact.location.x),
            abs(tip_contact.location.z - ring_contact.location.z),
            abs(tip_contact.rotation_euler.y + ring_contact.rotation_euler.y),
            abs(tip_contact.dimensions.x - ring_contact.dimensions.x),
            abs(tip_contact.dimensions.y - ring_contact.dimensions.y),
            abs(tip_contact.dimensions.z - ring_contact.dimensions.z),
        ))
    digital_contact_symmetry_error_max = max(digital_contact_symmetry_errors)

    rod_world_center = rod.matrix_world.translation
    connector_cylinder_world_center = connector_cylinder.matrix_world.translation
    support_cross_mount_world_center = support_cross_mount.matrix_world.translation
    rod_bottom = rod.location.z - rod.dimensions.z / 2
    rod_top = rod.location.z + rod.dimensions.z / 2
    piston_min = (0.135, 0.167)
    piston_max = (0.235, 0.267)
    cylinder_bounds = (cylinder_bottom_z, cylinder_top_z)
    scale_tick_vertices_per_mark = (scale_tick_arc_segments + 1) * 4
    scale_tick_center_z_values_actual = []
    for tick_index in range(scale_tick_count):
        vertex_start = tick_index * scale_tick_vertices_per_mark
        tick_vertex_z_values = [
            ticks.data.vertices[vertex_index].co.z
            for vertex_index in range(vertex_start, vertex_start + scale_tick_vertices_per_mark)
        ]
        scale_tick_center_z_values_actual.append((min(tick_vertex_z_values) + max(tick_vertex_z_values)) * 0.5)
    scale_major_z_values_actual_top_down = list(reversed([
        scale_tick_center_z_values_actual[index]
        for index in range(0, scale_tick_count, scale_major_every)
    ]))
    expected_scale_tick_spacing = scale_span / (scale_tick_count - 1)
    scale_tick_spacing_error_max = max(
        abs(
            scale_tick_center_z_values_actual[index + 1]
            - scale_tick_center_z_values_actual[index]
            - expected_scale_tick_spacing
        )
        for index in range(scale_tick_count - 1)
    )
    scale_label_values = [label.get("displayedValue") for label in scale_labels]
    scale_label_z_values = [label.location.z for label in scale_labels]
    scale_label_alignment_error_max = max(
        abs(scale_label_z_values[index] - scale_major_z_values_actual_top_down[index]) for index in range(len(scale_labels))
    )
    scale_label_spacing = min(
        scale_label_z_values[index] - scale_label_z_values[index + 1] for index in range(len(scale_labels) - 1)
    )
    scale_zero_tick_center_z = scale_tick_center_z_values_actual[0]
    scale_zero_tick_lower_edge_z = min(vertex.co.z for vertex in ticks.data.vertices)
    scale_top_tick_upper_edge_z = max(vertex.co.z for vertex in ticks.data.vertices)
    lower_seal_top_z = lower_seal_center_z + lower_seal_minor_radius
    upper_seal_bottom_z = upper_seal_center_z - upper_seal_minor_radius
    scale_zero_tick_edge_clearance_actual = scale_zero_tick_lower_edge_z - lower_seal_top_z
    scale_zero_tick_center_to_glass_bottom = scale_zero_tick_center_z - cylinder_bottom_z
    scale_top_tick_to_glass_top_clearance_actual = cylinder_top_z - scale_top_tick_upper_edge_z
    scale_top_tick_to_upper_seal_clearance_actual = upper_seal_bottom_z - scale_top_tick_upper_edge_z
    scale_top_label_upper_z = max(
        scale_labels[0].location.z + vertex.co.z for vertex in scale_labels[0].data.vertices
    )
    scale_top_label_clearance_below_upper_seal = upper_seal_bottom_z - scale_top_label_upper_z
    previous_scale_tick_spacing = 0.163 / 32.0
    previous_scale_major_spacing = 0.163 / 8.0
    expected_scale_major_spacing = scale_span / (scale_major_tick_count - 1)
    cylinder_world_center = cylinder_obj.matrix_world.translation
    scale_label_target_world_radius = (tube_outer_radius + scale_label_surface_offset) * instrument_scale
    scale_label_world_vertices = [
        [label.matrix_world @ vertex.co for vertex in label.data.vertices]
        for label in scale_labels
    ]
    scale_label_surface_error_max = max(
        abs(
            math.hypot(vertex.x - cylinder_world_center.x, vertex.y - cylinder_world_center.y)
            - scale_label_target_world_radius
        )
        for vertices in scale_label_world_vertices
        for vertex in vertices
    )
    scale_labels_all_on_front_half = all(
        vertex.y < cylinder_world_center.y
        for vertices in scale_label_world_vertices
        for vertex in vertices
    )
    tick_world_vertices = [ticks.matrix_world @ vertex.co for vertex in ticks.data.vertices]
    scale_group_world_x_values = [vertex.x for vertex in tick_world_vertices] + [
        vertex.x for vertices in scale_label_world_vertices for vertex in vertices
    ]
    scale_group_world_center_x = (min(scale_group_world_x_values) + max(scale_group_world_x_values)) * 0.5
    scale_group_center_x_error = abs(scale_group_world_center_x - cylinder_world_center.x)
    major_half_angle = math.asin(min(0.95, 0.016 / (2.0 * tube_outer_radius)))
    major_tick_right_x_source = cyl_center[0] + tube_outer_radius * max(
        math.cos(scale_tick_center_angle - major_half_angle),
        math.cos(scale_tick_center_angle + major_half_angle),
    )
    major_tick_right_x_world = instrument_world((major_tick_right_x_source, cyl_center[1], scale_z_start)).x
    scale_label_left_x_world = min(vertex.x for vertices in scale_label_world_vertices for vertex in vertices)
    scale_label_to_major_tick_gap = scale_label_left_x_world - major_tick_right_x_world
    piston_rod_world_top = world_bounds_z(rod_part)[1]
    upper_plate_world_top = world_bounds_z(upper_plate)[1]
    mass_platform_rod_top_gap = abs(piston_rod_world_top - upper_plate_world_top)

    main_envelope_center = all_instruments_xy_shift.xy + main_instrument_xy_shift.xy + Vector((0.0, 0.005))
    main_envelope_bounds = (
        main_envelope_center.x - 0.165, main_envelope_center.x + 0.165,
        main_envelope_center.y - 0.165, main_envelope_center.y + 0.165,
    )
    sensor_envelope_bounds = world_bounds_xy(shell)
    universal_envelope_bounds = world_bounds_xy(universal_shell)
    ensemble_bounds = (
        min(main_envelope_bounds[0], sensor_envelope_bounds[0], universal_envelope_bounds[0]),
        max(main_envelope_bounds[1], sensor_envelope_bounds[1], universal_envelope_bounds[1]),
        min(main_envelope_bounds[2], sensor_envelope_bounds[2], universal_envelope_bounds[2]),
        max(main_envelope_bounds[3], sensor_envelope_bounds[3], universal_envelope_bounds[3]),
    )
    ensemble_center = Vector(((ensemble_bounds[0] + ensemble_bounds[1]) * 0.5, (ensemble_bounds[2] + ensemble_bounds[3]) * 0.5))
    ensemble_center_offset = (ensemble_center - table_center.xy).length
    table_bounds_xy = (
        table_center.x - table_dims.x * 0.5, table_center.x + table_dims.x * 0.5,
        table_center.y - table_dims.y * 0.5, table_center.y + table_dims.y * 0.5,
    )
    left_foot_direction = (apex - left_foot).normalized()
    right_foot_direction = (apex - right_foot).normalized()
    left_foot_expected_center = left_foot + left_foot_direction * level_foot_beam_overlap
    right_foot_expected_center = right_foot + right_foot_direction * level_foot_beam_overlap
    base_beam_bottom_z = base_beam_center_z - base_beam_height * 0.5
    level_foot_vertical_overlap = level_foot_height - base_beam_bottom_z
    level_foot_local_bounds = []
    for foot in (left_level_foot, right_level_foot):
        x_values = [vertex.co.x for vertex in foot.data.vertices]
        y_values = [vertex.co.y for vertex in foot.data.vertices]
        z_values = [vertex.co.z for vertex in foot.data.vertices]
        level_foot_local_bounds.append((min(x_values), max(x_values), min(y_values), max(y_values), min(z_values), max(z_values)))
    level_foot_bevels = [
        next((modifier for modifier in foot.modifiers if modifier.type == "BEVEL"), None)
        for foot in (left_level_foot, right_level_foot)
    ]
    checks = {
        "required_nodes_present": len(missing) == 0,
        "metric_unit_scale_1": scene.unit_settings.system == "METRIC" and abs(scene.unit_settings.scale_length - 1.0) < 1e-9,
        "support_rod_nominal_450mm": abs(rod.get("nominalLength") - 0.450) < 1e-9,
        "support_rod_lower_segment_removed": rod_bottom >= housing_world_center.z - 1e-8 and rod.dimensions.z < 0.450,
        "support_rod_diameter_12_7mm": abs(rod.dimensions.x - 0.0127) < 1e-6,
        "support_rod_aligned_with_upper_cylinder_vertical_axis": (rod_world_center.xy - connector_cylinder_world_center.xy).length < 1e-8,
        "instrument_uniform_scale_1_10": max(abs(value - instrument_scale) for value in instrument_root.scale) < 1e-6,
        "instrument_moved_negative_y_60mm_from_previous": instrument_y_shift < previous_instrument_y_shift and abs(previous_instrument_y_shift - instrument_y_shift - 0.060) < 1e-9,
        "instrument_shifted_up_60mm_total": abs((instrument_root.location.z - instrument_pivot.z) - instrument_z_shift) < 1e-7 and instrument_z_shift > previous_instrument_z_shift,
        "instrument_body_hierarchy_preserved": engine.parent == instrument_root and pneumatic.parent == instrument_root,
        "all_instruments_shifted_positive_x_negative_y": all_instruments_xy_shift.x > 0.0 and all_instruments_xy_shift.y < 0.0,
        "all_instruments_ensemble_centered_on_table": ensemble_center_offset < 0.0001,
        "all_instruments_ensemble_inside_tabletop": ensemble_bounds[0] >= table_bounds_xy[0] and ensemble_bounds[1] <= table_bounds_xy[1] and ensemble_bounds[2] >= table_bounds_xy[2] and ensemble_bounds[3] <= table_bounds_xy[3],
        "rod_clamp_still_centered_on_support_rod": (bpy.data.objects["RodClampMount"].matrix_world.translation.xy - rod.matrix_world.translation.xy).length < 1e-8,
        "rod_clamp_height_matches_top_back": abs(bpy.data.objects["RodClampMount"].matrix_world.translation.z - top_back_world_center.z) < 1e-8,
        "rod_bridge_horizontal_to_top_back": abs(bridge.matrix_world.translation.z - top_back_world_center.z) < 1e-8 and bridge_depth > 0.0,
        "rod_bridge_overlaps_top_back": bridge_front_world_y <= top_back_rear_y and bridge_front_world_y >= top_back_world_center.y,
        "rod_bridge_slab_end_matches_top_slab_length": abs(bridge.get("slabEndWidth") - top_slab.dimensions.x) < 1e-6,
        "rod_bridge_tapers_toward_clamp": bridge.get("slabEndWidth") > bridge.get("clampEndWidth"),
        "rod_knob_head_follows_top_connection": abs(rod_knob_head.matrix_world.translation.z - rod_connection_z) < 1e-8,
        "rod_knob_head_directly_behind_support_rod": abs(rod_knob_head.matrix_world.translation.x - rod.matrix_world.translation.x) < 1e-8 and rod_knob_head.matrix_world.translation.y > rod.matrix_world.translation.y,
        "rod_knob_threaded_shaft_directly_behind_support_rod": abs(rod_knob_shaft.matrix_world.translation.x - rod.matrix_world.translation.x) < 1e-8 and rod_knob_shaft.matrix_world.translation.y > rod.matrix_world.translation.y,
        "rod_knob_axis_is_rearward_y": rod_knob.get("axis") == "Y" and rod_knob.get("rearDirection") == "positive_Y",
        "protective_frame_is_single_cuboid_shell": frame.get("structure") == "single_cuboid_shell",
        "upper_measurement_assembly_stretched_60mm_in_z": abs(upper_z_stretch - 0.060) < 1e-9 and abs(frame_outer_size[2] - (0.178 + upper_z_stretch)) < 1e-9 and abs(cylinder_depth - (0.157 + upper_z_stretch)) < 1e-9,
        "upper_measurement_assembly_bottom_plane_preserved": abs(frame_bottom_z - 0.131) < 1e-7 and abs(cylinder_bottom_z - 0.136) < 1e-7 and abs(bottom_slab.location.z - 0.139) < 1e-7,
        "upper_frame_clamp_and_platform_endpoints_raised_together": abs(top_slab.location.z - (0.301 + upper_z_stretch)) < 1e-7 and abs(top_back_source_center[2] - top_slab.location.z) < 1e-7 and abs(piston_rod_depth - (0.180 + upper_z_stretch + piston_rod_extra_length)) < 1e-7,
        "front_back_windows_large_for_glass_view": front_back_window[0] * front_back_window[1] / (frame_outer_size[0] * frame_outer_size[2]) > 0.65,
        "side_capsule_opening_width_preserved_and_height_stretched": abs(side_window[0] - 0.050) < 1e-9 and abs(side_window[1] - (0.138 + upper_z_stretch)) < 1e-9,
        "protective_frame_panels_share_parent": all(panel.parent == frame for panel in (front_panel, back_panel, left_panel, right_panel, top_slab, bottom_slab)),
        "legacy_four_ring_frames_removed": all(bpy.data.objects.get(name) is None for name in ("ProtectiveFrame_Front", "ProtectiveFrame_Back", "ProtectiveFrame_Left", "ProtectiveFrame_Right")),
        "lower_housing_xy_expanded": housing_dims[0] > original_housing_dims[0] and housing_dims[1] > original_housing_dims[1],
        "top_lip_xy_expanded": top_lip_dims[0] > original_top_lip_dims[0] and top_lip_dims[1] > original_top_lip_dims[1],
        "housing_y_extended_again": housing_dims[1] > previous_housing_y and top_lip_dims[1] > previous_top_lip_y,
        "support_rod_axis_inside_housing_xy": abs(rod_pass_source.x - housing_center[0]) + rod_hole_radius < housing_dims[0] * 0.5 and abs(rod_pass_source.y - housing_center[1]) + rod_hole_radius < housing_dims[1] * 0.5,
        "support_rod_axis_inside_top_lip_xy": abs(rod_pass_source.x - top_lip_center[0]) + rod_hole_radius < top_lip_dims[0] * 0.5 and abs(rod_pass_source.y - top_lip_center[1]) + rod_hole_radius < top_lip_dims[1] * 0.5,
        "housing_and_lip_have_support_rod_holes": housing.get("throughHoleFor") == "SupportRod_45cm" and top_lip.get("throughHoleFor") == "SupportRod_45cm",
        "piston_lock_assembly_removed": all(not obj.name.startswith("PistonLock") for obj in scene.objects),
        "housing_combined_height_reduced": housing_combined_height < original_housing_combined_height,
        "housing_and_top_lip_connected": top_lip_bottom_z < housing_top_z,
        "underside_cylindrical_post_removed": bpy.data.objects.get("Underside_CylindricalPost") is None,
        "mass_platform_leafs_centered": abs(lower_plate.location.x) < 1e-9 and abs(upper_plate.location.x) < 1e-9,
        "mass_platform_pillars_mirrored": abs(bpy.data.objects["MassPlatform_LeftPillar"].location.x + bpy.data.objects["MassPlatform_RightPillar"].location.x) < 1e-9,
        "mass_platform_moved_upward": mass_platform_vertical_shift > 0.0 and abs(platform.location.z - mass_platform_vertical_shift) < 1e-7,
        "mass_platform_upper_plate_flush_with_piston_rod_top": mass_platform_rod_top_gap < 1e-6,
        "glass_tube_thickened_to_48mm": abs(cylinder_obj.dimensions.x - tube_outer_radius * 2.0 * instrument_scale) < 1e-6,
        "piston_thickened_and_fits_tube": abs(piston.dimensions.x - piston_radius * 2.0 * instrument_scale) < 1e-6 and piston_radius < tube_inner_radius,
        "piston_z_length_shortened_to_24mm": abs(piston_height - 0.024) < 1e-9 and piston_height < original_piston_height and abs(piston.dimensions.z - piston_height * instrument_scale) < 1e-6,
        "piston_rod_longer_than_pyrex_cylinder": rod_part.dimensions.z > cylinder_obj.dimensions.z and abs(rod_part.get("nominalLength") - piston_rod_depth) < 1e-9,
        "piston_rod_shortened_again_by_6mm": abs(previous_piston_rod_extra_length - piston_rod_extra_length - 0.006) < 1e-9 and abs(rod_part.dimensions.z - piston_rod_depth * instrument_scale) < 1e-6,
        "scale_ticks_conform_to_glass": ticks.get("attachedTo") == "Cylinder_Pyrex" and abs(ticks.get("conformsToRadius") - tube_outer_radius) < 1e-9,
        "scale_has_37_ticks_and_10_long_major_ticks": ticks.get("totalTickCount") == 37 and ticks.get("majorTickEvery") == 4 and ticks.get("majorTickCount") == 10 and len(scale_tick_center_z_values_actual) == 37 and len(scale_major_z_values_actual_top_down) == 10,
        "scale_major_ticks_run_90_to_0_with_zero_unlabeled": ticks.get("majorTickCount") == scale_major_tick_count and len(scale_labels) == scale_labeled_major_tick_count and scale_label_values == list(range(scale_max_value, 0, -scale_major_value_step)) and bpy.data.objects.get("ScaleLabel_0") is None and all(scale_label_z_values[index] > scale_label_z_values[index + 1] for index in range(len(scale_labels) - 1)),
        "scale_labels_align_one_to_one_with_labeled_major_ticks": scale_label_alignment_error_max < 1e-7 and len(set(round(value, 7) for value in scale_label_z_values)) == scale_labeled_major_tick_count,
        "scale_labels_are_evenly_spaced_and_clear": scale_label_spacing > previous_scale_major_spacing and all(label.type == "MESH" and label.get("attachedTo") == "Cylinder_Pyrex" for label in scale_labels),
        "scale_labels_conform_to_front_glass_surface": scale_label_surface_error_max < 5e-5 and scale_labels_all_on_front_half and all(label.get("surfaceConforming") is True for label in scale_labels),
        "scale_group_centered_in_front_view": scale_group_center_x_error < 0.0030,
        "scale_labels_close_beside_major_ticks": -0.0005 <= scale_label_to_major_tick_gap <= 0.0030,
        "scale_labels_regular_weight_and_readable_size": all(label.get("labelSize") >= 0.0090 and abs(label.get("outlineOffset")) < 1e-9 for label in scale_labels),
        "scale_keeps_zero_at_bottom_and_extends_to_90": abs(scale_z_start - 0.141) < 1e-9 and abs(scale_z_end - 0.3445) < 1e-9 and abs(scale_span - 0.2035) < 1e-9,
        "scale_actual_tick_mesh_spans_requested_range": abs(scale_tick_center_z_values_actual[0] - scale_z_start) < 1e-7 and abs(scale_tick_center_z_values_actual[-1] - scale_z_end) < 1e-7,
        "scale_tick_and_major_spacing_increased": scale_tick_spacing_error_max < 1e-7 and expected_scale_tick_spacing > previous_scale_tick_spacing and expected_scale_major_spacing > previous_scale_major_spacing,
        "scale_90_tick_keeps_small_gap_below_glass_top": 0.0 < scale_top_tick_to_glass_top_clearance_actual < 0.010 and scale_top_tick_to_upper_seal_clearance_actual > 0.0,
        "scale_90_label_clears_upper_seal": scale_top_label_clearance_below_upper_seal > 0.0005,
        "scale_zero_tick_close_to_glass_bottom": abs(scale_zero_tick_center_z - scale_z_start) < 1e-7 and 0.0 < scale_zero_tick_center_to_glass_bottom <= 0.00501,
        "scale_zero_tick_clears_lower_seal": scale_zero_tick_edge_clearance_actual > 0.0 and abs(scale_zero_tick_edge_clearance_actual - scale_zero_tick_edge_clearance) < 1e-7,
        "scale_zero_numeric_label_removed": bpy.data.objects.get("ScaleLabel_0") is None and 0 not in scale_label_values,
        "scale_strip_removed": bpy.data.objects.get("ScaleStrip_Clear") is None,
        "vent_assembly_removed": all(bpy.data.objects.get(name) is None for name in ("Port_Vent", "Port_Vent_WhiteConnector", "Tube_Vent_Short", "VentPinchClamp", "VentPinchClamp_CompressionJaw")),
        "base_is_open_v_shape": base_node.get("type") == "cast_iron_open_V_frame" and bpy.data.objects.get("Base_CastIron_FrontBeam") is None,
        "base_beams_enlarged_in_length_width_height": base_arm_length > original_base_arm_length and base_beam_width > original_base_beam_width and base_beam_height > original_base_beam_height,
        "base_feet_spacing_enlarged": abs((right_foot - left_foot).length - base_foot_spacing) < 1e-7 and base_foot_spacing > original_base_foot_spacing,
        "level_foot_adjuster_screws_removed": bpy.data.objects.get("LevelFoot_L_AdjusterScrew") is None and bpy.data.objects.get("LevelFoot_R_AdjusterScrew") is None,
        "level_feet_are_matching_fixed_half_cylinders": all(foot.type == "MESH" and foot.get("shape") == "vertical_half_cylinder" and foot.get("adjustable") is False and foot.get("fixed") is True for foot in (left_level_foot, right_level_foot)) and all(abs(bounds[0] + level_foot_radius) < 1e-7 and abs(bounds[1]) < 1e-7 and abs(bounds[2] + level_foot_radius) < 1e-7 and abs(bounds[3] - level_foot_radius) < 1e-7 for bounds in level_foot_local_bounds),
        "level_foot_flat_faces_match_beam_width": all(abs(foot.get("flatFaceWidth") - base_beam_width) < 1e-9 for foot in (left_level_foot, right_level_foot)),
        "level_feet_overlap_unified_v_beam_without_gap": (left_level_foot.location.xy - left_foot_expected_center.xy).length < 1e-8 and (right_level_foot.location.xy - right_foot_expected_center.xy).length < 1e-8 and level_foot_beam_overlap > 0.0 and level_foot_vertical_overlap > 0.0 and left_level_foot.get("logicalBeam") == "Base_CastIron_LeftBeam" and right_level_foot.get("logicalBeam") == "Base_CastIron_RightBeam" and all(foot.get("representedGeometryBy") == "Base_CastIron_LeftBeam" for foot in (left_level_foot, right_level_foot)),
        "level_feet_have_rounded_corner_free_edges": all(modifier is not None and abs(modifier.width - level_foot_edge_radius) < 1e-9 and modifier.segments >= 6 for modifier in level_foot_bevels) and all(foot.get("protrudingCornersRemoved") is True for foot in (left_level_foot, right_level_foot)),
        "level_feet_are_left_right_symmetric": abs(left_level_foot.location.x + right_level_foot.location.x) < 1e-8 and abs(left_level_foot.location.y - right_level_foot.location.y) < 1e-8,
        "base_arms_enlarged_to_295mm": abs((apex - left_foot).length - base_arm_length) < 1e-7 and abs((apex - right_foot).length - base_arm_length) < 1e-7,
        "v_arm_midpoint_supports_present": left_base_support.get("connectsFrom") == "Base_CastIron_LeftBeam_Midpoint" and right_base_support.get("connectsFrom") == "Base_CastIron_RightBeam_Midpoint",
        "base_connector_is_v_conforming_loft_plus_upper_cylinder": support_cross_mount.get("shape") == "v_conforming_footprint_loft" and connector_cylinder.get("shape") == "cylinder",
        "connector_rectangular_when_viewed_along_x": abs(pedestal_bottom_center.y - pedestal_top_center.y) < 1e-9,
        "connector_trapezoidal_when_viewed_along_y": pedestal_bottom_front_half_x > pedestal_top_front_half_x and pedestal_bottom_back_half_x > pedestal_top_back_half_x,
        "connector_is_trapezoid_in_top_view": pedestal_bottom_front_half_x > pedestal_bottom_back_half_x and support_cross_mount.get("topViewShape") == "trapezoid",
        "upper_connector_cylinder_meets_housing": abs(connector_cylinder_top_z - housing_world_bottom_z) < 1e-8,
        "upper_connector_is_off_center_on_housing_bottom": abs(connector_cylinder_world_center.y - housing_world_center.y) > 0.050,
        "lower_instrument_support_volume_enlarged": connector_cylinder_radius > previous_connector_cylinder_radius and connector_cylinder_depth > previous_connector_cylinder_depth and pedestal_top_footprint_scale > previous_pedestal_top_footprint_scale and (pedestal_top_z - pedestal_bottom_z) > 0.070,
        "trapezoid_overlaps_v_arm_midpoints": pedestal_y_front <= left_arm_mid.y <= pedestal_y_back and abs(left_arm_mid.x) < base_outer_half_x_at_y(left_arm_mid.y),
        "left_right_base_beams_meet_at_common_apex": (left_joint_end - apex).length < 1e-9 and (right_joint_end - apex).length < 1e-9,
        "crossmount_outer_edges_match_base_beams_at_every_y": abs(pedestal_bottom_front_half_x - base_outer_half_x_at_y(pedestal_y_front)) < 1e-9 and abs(pedestal_bottom_back_half_x - base_outer_half_x_at_y(pedestal_y_back)) < 1e-9,
        "connector_cylinder_fits_top_footprint": ((pedestal_top_front_half_x + pedestal_top_back_half_x) * 0.5) > connector_cylinder_radius,
        "base_beam_joint_is_smooth_boolean_union": left_base_beam.get("jointMethod") == "exact_boolean_union_with_rounded_hub" and left_base_beam.get("containsUnifiedVArms") is True and left_base_beam.get("pointedJointCornersRemoved") is True and right_base_beam.get("representedBy") == "Base_CastIron_LeftBeam",
        "base_beam_joint_has_rounded_transition": abs(left_base_beam.get("apexJointRadius") - base_joint_radius) < 1e-9 and base_joint_radius > base_beam_width * 0.5,
        "three_base_contacts_on_table": all(abs(obj.get("contactZ")) < 1e-9 and abs(world_bounds_z(obj)[0]) < 1e-7 for obj in (left_level_foot, right_level_foot, vertex)),
        "sensor_feet_on_table": True,
        "hose_start_matches_anchor": (Vector(bpy.data.objects["ANCHOR_Hose_Start"].location) - hose_start).length < 1e-8,
        "hose_end_matches_anchor": (Vector(bpy.data.objects["ANCHOR_Hose_End"].location) - hose_end).length < 1e-8,
        "hose_terminal_enters_top_lip_vertically": (hose_points[1] - hose_points[0]).xy.length < 1e-9 and hose_points[1].z > hose_points[0].z and port_main.get("orientation") == "vertical_Z",
        "top_lip_has_quick_disconnect_hole": top_lip.get("quickDisconnectHole") is True and top_lip.get("quickDisconnectHoleAxis") == "Z",
        "quick_disconnect_rotates_and_seals": quick_disconnect_root.get("interaction") == "rotate_connect_disconnect" and quick_disconnect_root.get("sealedWhenConnected") is True and quick_disconnect_root.get("openToAtmosphereWhenDisconnected") is True,
        "internal_hose_descends_vertically_inside_housing": (internal_hose_points[1] - internal_hose_points[0]).xy.length < 1e-9 and internal_hose_points[1].z < internal_hose_points[0].z,
        "internal_hose_connects_to_cylinder_bottom": (internal_hose_points[-1] - cylinder_air_endpoint_local).length < 1e-9 and internal_hose.get("connectsTo") == "Cylinder_BottomAirInlet",
        "sealed_air_path_controls_piston_adjustment": piston_root.get("lockedByPneumaticSealWhen") == "Connector_Main_QuickDisconnect.connected_sealed" and piston_root.get("freeVolumeAdjustmentWhen") == "Connector_Main_QuickDisconnect.disconnected_open_to_atmosphere",
        "piston_full_stroke_inside_cylinder": piston_min[0] >= cylinder_bounds[0] - 0.002 and piston_max[1] <= cylinder_bounds[1],
        "sensor_channel_1_connected": bool(port1["connected"]),
        "sensor_channel_2_empty": not bool(port2["connected"]),
        "pressure_sensor_slightly_enlarged": abs(sensor_root.scale.x - sensor_scale) < 1e-6 and sensor_scale > 1.0,
        "sensor_upper_port_labeled_2": port_label_2.get("displayedNumber") == "2" and port_label_2.location.y > port_label_1.location.y,
        "sensor_lower_port_labeled_1": port_label_1.get("displayedNumber") == "1" and port_label_1.location.y < port_label_2.location.y,
        "sensor_port_labels_export_as_meshes": port_label_1.type == "MESH" and port_label_2.type == "MESH",
        "sensor_left_interface_is_circular": sensor_data_connector.get("connectorShape") == "circular_coaxial" and sensor_data_port.get("circular") is True and sensor_data_connector.type == "EMPTY",
        "sensor_circular_connector_has_locking_collar": sensor_data_collar.get("rotatesToLock") is True and sensor_data_collar.parent == sensor_data_connector,
        "large_universal_interface_is_rounded_cuboid": universal_shell.get("shape") == "rounded_cuboid" and all(universal_dims[i] > sensor_root.scale[i] * shell.dimensions[i] for i in range(3)),
        "universal_interface_enlarged_in_x_and_z": universal_dims.x > previous_universal_dims.x and universal_dims.z > previous_universal_dims.z and abs(universal_dims.y - previous_universal_dims.y) < 1e-9,
        "universal_interface_front_remains_wide_format": universal_dims.x / universal_dims.z > 3.0,
        "universal_interface_front_panel_inside_housing_with_10mm_margin": universal_front_panel_inside_housing,
        "universal_interface_front_module_areas_preserved": abs(digital_panel_dims.x * digital_panel_dims.z - 0.112 * 0.054) < 1e-9 and abs(analog_panel_dims.x * analog_panel_dims.z - 0.174 * 0.054) < 1e-9 and abs(pasport_panel_dims.x * pasport_panel_dims.z - 0.350 * 0.052) < 1e-9 and abs(output_panel_dims.x * output_panel_dims.z - 0.073 * 0.106) < 1e-9,
        "universal_interface_front_modules_do_not_overlap": front_modules_nonoverlapping,
        "universal_interface_front_modules_inside_outline": front_modules_inside_outline,
        "universal_interface_function_labels_enlarged": bpy.data.objects["UniversalInterface_DigitalTitle"].get("sourceTextSize") >= 0.0073 and bpy.data.objects["UniversalInterface_AnalogTitle"].get("sourceTextSize") >= 0.0060 and bpy.data.objects["UniversalInterface_PASPortLabel_1"].get("sourceTextSize") >= 0.0078 and bpy.data.objects["UniversalInterface_OutputTitle"].get("sourceTextSize") >= 0.0071 and bpy.data.objects["UniversalInterface_Output10VLabel"].get("sourceTextSize") >= 0.0048,
        "universal_interface_function_labels_boldened": all(label.get("strokeOffset") >= 0.00030 for label in interface_labels),
        "universal_interface_function_labels_inside_outline": interface_labels_inside_outline,
        "universal_interface_module_panels_share_one_face_plane": module_panels_coplanar,
        "universal_interface_text_has_zero_y_thickness": interface_label_y_thickness_max < 1e-8,
        "universal_interface_text_is_coplanar_and_surface_seated": interface_labels_coplanar and abs(module_text_plane_y - module_front_plane_y) <= 0.00005 + 1e-9,
        "universal_interface_digital_text_inside_panel_with_margin": digital_text_inside_panel,
        "universal_interface_analog_text_inside_panel_with_margin": analog_text_inside_panel,
        "universal_interface_pasport_text_inside_each_panel_with_margin": pasport_text_inside_panels,
        "universal_interface_pasport_group_shifted_up_12mm": abs(pasport_module.get("verticalShift") - 0.012) < 1e-9 and all(abs(panel.location.z - (0.043 + pasport_vertical_shift)) < 1e-9 for panel in pasport_panels) and all(abs(port.location.z - pasport_port_z) < 1e-9 for port in pasport_ports) and abs(universal_input_plug.location.z - pasport_port_z) < 1e-9,
        "universal_interface_pasport_group_keeps_10mm_upper_clearance": pasport_to_upper_clearance >= 0.010 - 1e-9,
        "universal_interface_all_recessed_input_sockets_are_recessed": all_front_sockets_recessed,
        "universal_interface_digital_and_analog_sockets_enlarged": digital_ports[0].get("outerDiameter") >= 0.0130 and analog_ports[0].get("outerDiameter") >= 0.0250,
        "universal_interface_pasport_sockets_enlarged": pasport_ports[0].get("outerDiameter") >= 0.0184,
        "universal_interface_all_32_pasport_pin_holes_enlarged": len(pasport_pin_holes) == 32 and all(pin_hole.dimensions.x >= pasport_pin_hole_radius * 2.0 - 1e-7 and pin_hole.get("recessed") is True for pin_hole in pasport_pin_holes),
        "universal_interface_pasport_pin_holes_remain_separate": pasport_pin_hole_adjacent_clearance > 0.0005,
        "universal_interface_pasport_pin_holes_remain_inside_socket": pasport_pin_ring_radius + pasport_pin_hole_radius <= 0.0085,
        "universal_interface_data_plug_seated_in_pasport_1": universal_input_plug.get("connectedTo") == "UniversalInterface_PASPort_1" and pasport_ports[0].get("occupiedBy") == "UniversalInterface_DataCablePlug" and universal_input_plug_axis_aligned and universal_input_plug_seating_gap < 1e-9,
        "universal_interface_power_zone_only_has_switch_and_led": bpy.data.objects.get("UniversalInterface_850Label") is None and set(child.name for child in power_module.children) == {"UniversalInterface_PowerRing", "UniversalInterface_PowerButton", "UniversalInterface_StatusLED"},
        "universal_interface_power_zone_shifted_left_with_clearance": power_x + 0.0125 < digital_panel_center.x - digital_panel_dims.x * 0.5 - 0.010,
        "universal_interface_power_controls_are_seated": power_controls_seated,
        "universal_interface_has_five_function_modules": all(module.parent == universal_root for module in (power_module, digital_module, analog_module, pasport_module, output_module)),
        "universal_interface_has_four_detailed_digital_inputs": len(digital_ports) == 4 and all(bpy.data.objects.get(f"UniversalInterface_DigitalInput_{index}_CentralBore") is not None and bpy.data.objects.get(f"UniversalInterface_DigitalInput_{index}_ContactSpring_Tip") is not None and bpy.data.objects.get(f"UniversalInterface_DigitalInput_{index}_ContactSpring_Ring") is not None for index in range(1, 5)),
        "universal_interface_digital_inputs_are_precision_6_35mm_trs_jacks": all(port.get("connectorType") == "6.35mm_TRS_stereo_phone_jack" and abs(port.get("nominalPlugDiameter") - 0.00635) < 1e-9 for port in digital_ports),
        "universal_interface_digital_inputs_have_complete_recessed_ring_stack": len(digital_trim_rings) == 4 and len(digital_bezel_rings) == 4 and len(digital_throat_rings) == 4 and len(digital_bores) == 4 and all(bore.get("deepSocketOpening") is True for bore in digital_bores),
        "universal_interface_digital_inputs_have_internal_tip_and_ring_contacts": len(digital_contact_springs) == 8 and all(spring.get("recessed") is True for spring in digital_contact_springs),
        "universal_interface_digital_input_contacts_are_mirror_symmetric": digital_contact_symmetry_error_max < 1e-9 and all(spring.get("symmetricContactPair") is True for spring in digital_contact_springs),
        "universal_interface_has_four_detailed_analog_din_inputs": len(analog_ports) == 4 and all(bpy.data.objects.get(f"UniversalInterface_AnalogInput_{letter}_PinHole_8") is not None and bpy.data.objects.get(f"UniversalInterface_AnalogInput_{letter}_LocatorNotch") is not None for letter in analog_letters),
        "universal_interface_analog_inputs_are_full_size_8_pin_din_female": all(port.get("connectorType") == "full_size_8_pin_DIN_female" and port.get("pinCount") == 8 for port in analog_ports),
        "universal_interface_analog_inputs_use_270_degree_horseshoe_layout": all(port.get("pinArrangement") == "270_degree_horseshoe" and abs(port.get("pinArcDegrees") - 270.0) < 1e-9 for port in analog_ports) and abs(math.degrees(analog_pin_angles[-1] - analog_pin_angles[0]) - 270.0) < 1e-8,
        "universal_interface_analog_inputs_have_complete_ring_stack": len(analog_trim_rings) == 4 and len(analog_bezel_rings) == 4 and len(analog_shield_rings) == 4 and len(analog_insulators) == 4 and all(ring.get("machinedMetal") is True for ring in analog_trim_rings + analog_shield_rings),
        "universal_interface_analog_inputs_have_32_recessed_female_holes": len(analog_pin_collars) == 32 and len(analog_pin_holes) == 32 and all(hole.get("femaleContactHole") is True and hole.get("recessed") is True for hole in analog_pin_holes),
        "universal_interface_analog_inputs_have_upper_orientation_keys": len(analog_locator_notches) == 4 and len(analog_locator_rails) == 8 and all(notch.get("DINOrientationKey") is True and notch.get("keyPosition") == "upper_center" for notch in analog_locator_notches),
        "universal_interface_has_four_detailed_pasport_inputs": len(pasport_ports) == 4 and all(bpy.data.objects.get(f"UniversalInterface_PASPort_{index}_Pin_8") is not None and bpy.data.objects.get(f"UniversalInterface_PASPortLabel_{index}") is not None for index in range(1, 5)),
        "universal_interface_pasport_inputs_are_precision_8_contact_female_sockets": all(port.get("connectorType") == "PASPORT_8_contact_female" and port.get("contactCount") == 8 for port in pasport_ports),
        "universal_interface_pasport_inputs_have_complete_recessed_ring_stack": len(pasport_trim_rings) == 4 and len(pasport_bezel_rings) == 4 and len(pasport_insulators) == 4,
        "universal_interface_pasport_pin_holes_are_recessed_not_protruding": len(pasport_pin_collars) == 32 and all(hole.get("femaleContactHole") is True and hole.get("recessed") is True for hole in pasport_pin_holes),
        "universal_interface_pasport_inputs_have_upper_locator_notches": len(pasport_locator_notches) == 4 and all(notch.get("orientationKey") is True and notch.get("keyPosition") == "upper_center" for notch in pasport_locator_notches) and all(abs(port.get("pinAngularOffsetDegrees") - 22.5) < 1e-9 for port in pasport_ports),
        "universal_interface_output_section_complete": output_black.parent == output_module and output_red.parent == output_module and len(bnc_ports) == 2 and all(port.parent == output_module for port in bnc_ports),
        "universal_interface_bnc_2_and_3_are_projecting_metal_ring_sleeves": all(port.get("projecting") is True and port.get("metalRingSleeve") is True and port.get("nominalProtrusion") >= 0.016 for port in bnc_ports) and all(sleeve.get("hollow") is True and sleeve.get("machinedMetal") is True for sleeve in bnc_sleeves),
        "universal_interface_bnc_internal_details_complete": len(bnc_insulators) == 2 and len(bnc_center_contacts) == 2 and len(bnc_contact_slots) == 6 and all(contact.get("femaleContact") is True for contact in bnc_center_contacts),
        "universal_interface_bnc_has_two_bayonet_lugs_each": len(bnc_bayonet_lugs) == 4 and all(lug.get("bayonetLockingStud") is True for lug in bnc_bayonet_lugs),
        "universal_interface_function_labels_are_meshes": all(bpy.data.objects[name].type == "MESH" for name in ("UniversalInterface_DigitalTitle", "UniversalInterface_AnalogTitle", "UniversalInterface_OutputTitle", "UniversalInterface_Output15VLabel", "UniversalInterface_Output10VLabel")),
        "universal_interface_top_badge_matches_reference_structure": universal_shell.get("topBrandBadgeModeled") is True and top_badge_root.get("structure") == "rounded_rectangular_recess_with_inset_brand_plate" and top_badge_recess.get("recessFloor") is True and top_badge_inlay.get("insetBrandPlate") is True,
        "universal_interface_top_badge_centered_and_inside_cover": top_badge_xy_center_error < 1e-9 and top_badge_recess_dims.x < 0.523 - 0.020 and top_badge_recess_dims.y < 0.198 - 0.020,
        "universal_interface_top_badge_is_recessed_below_top_surface": top_badge_inlay_world_bounds_z[1] < top_cover_world_bounds_z[1] - 0.0002,
        "universal_interface_top_badge_markings_removed": universal_shell.get("brandLogoRemoved") is True and universal_shell.get("topBadgeMarkingsRemoved") is True and top_badge_root.get("markingsRemoved") is True and bpy.data.objects.get("UniversalInterface_TopBadge_PASCO") is None and bpy.data.objects.get("UniversalInterface_TopBadge_Scientific") is None,
        "universal_interface_front_brand_title_remains_absent": bpy.data.objects.get("UniversalInterface_Title") is None,
        "universal_interface_is_left_rear_of_main_apparatus": universal_world_origin.x < stand.matrix_world.translation.x - 0.15 and universal_world_origin.y > stand.matrix_world.translation.y + 0.05,
        "tabletop_expanded_for_universal_interface": table_dims.x > original_table_dims.x and table_dims.y > original_table_dims.y,
        "universal_interface_footprint_inside_table": universal_world_origin.x - universal_dims.x * 0.5 >= table_center.x - table_dims.x * 0.5 and universal_world_origin.x + universal_dims.x * 0.5 <= table_center.x + table_dims.x * 0.5 and universal_world_origin.y - universal_dims.y * 0.5 >= table_center.y - table_dims.y * 0.5 and universal_world_origin.y + universal_dims.y * 0.5 <= table_center.y + table_dims.y * 0.5,
        "universal_interface_feet_on_table": all(abs(foot.get("contactZ", -1.0)) < 1e-9 for foot in universal_feet),
        "sensor_data_cable_start_matches_connector": (data_cable_points[0] - sensor_data_endpoint_local).length < 1e-9 and (Vector(data_anchor_sensor.location) - sensor_data_endpoint).length < 1e-9,
        "sensor_data_cable_end_matches_universal_interface": (data_cable_points[-1] - universal_data_endpoint_local).length < 1e-9 and (Vector(data_anchor_interface.location) - universal_data_endpoint).length < 1e-9,
        "sensor_data_cable_terminal_directions_correct": (data_cable_points[1] - data_cable_points[0]).normalized().dot(sensor_data_outward) > 0.999 and (data_cable_points[-1] - data_cable_points[-2]).normalized().dot(Vector((0.0, 1.0, 0.0))) > 0.999,
        "sensor_to_universal_data_cable_present": data_cable.get("connectsFrom") == "SensorDataCircularPort_CablePlug" and data_cable.get("connectsTo") == "UniversalInterface_DataCablePlug",
        "no_text_objects": all(obj.type != "FONT" for obj in scene.objects),
    }
    report = {
        "source": "DOCX section 8, supplied reference photos, and official PASCO UI-5000 product materials",
        "blender_version": bpy.app.version_string,
        "blend_path": BLEND_PATH,
        "glb_path": exported_glb_path,
        "required_nodes_missing": missing,
        "checks": checks,
        "all_checks_passed": len(missing) == 0 and all(checks.values()),
        "evaluated_triangle_count_without_colliders": triangles,
        "measurements_m": {
            "support_rod_length": rod.dimensions.z,
            "support_rod_diameter": rod.dimensions.x,
            "support_rod_bottom": rod_bottom,
            "support_rod_top": rod_top,
            "support_rod_xy": list(rod_world_center.xy),
            "vertex_contact_pad_xy": list(vertex.matrix_world.translation.xy),
            "table_center_xy": list(table_center.xy),
            "main_instrument_xy_shift": list(main_instrument_xy_shift.xy),
            "all_instruments_xy_shift": list(all_instruments_xy_shift.xy),
            "all_instruments_ensemble_bounds_xy": list(ensemble_bounds),
            "all_instruments_ensemble_center_xy": list(ensemble_center),
            "all_instruments_ensemble_center_offset": ensemble_center_offset,
            "instrument_uniform_scale": instrument_scale,
            "instrument_y_shift": instrument_y_shift,
            "instrument_y_movement_from_previous": instrument_y_shift - previous_instrument_y_shift,
            "instrument_z_shift": instrument_z_shift,
            "instrument_z_movement_from_previous": instrument_z_shift - previous_instrument_z_shift,
            "instrument_pivot": list(instrument_pivot),
            "scaled_housing_center": list(housing_world_center),
            "scaled_lower_housing_dimensions": list(housing.dimensions),
            "scaled_top_lip_dimensions": list(top_lip.dimensions),
            "support_rod_hole_center_world": list(instrument_world((rod_pass_source.x, rod_pass_source.y, housing_center[2]))),
            "support_rod_hole_diameter": rod_hole_radius * 2.0 * instrument_scale,
            "rod_top_connection_z": rod_connection_z,
            "protective_frame_top_back_center": list(top_back_world_center),
            "rod_bridge_depth": bridge_depth,
            "rod_bridge_slab_end_width": bridge_slab_width,
            "rod_bridge_clamp_end_width": bridge_clamp_width,
            "upper_measurement_assembly_source_z_stretch": upper_z_stretch,
            "upper_measurement_assembly_scaled_z_growth": upper_z_stretch * instrument_scale,
            "protective_frame_bottom_z_preserved": frame_bottom_z * instrument_scale,
            "protective_frame_top_z_after_stretch": frame_top_z * instrument_scale,
            "protective_frame_outer_size": [value * instrument_scale for value in frame_outer_size],
            "front_back_window_size": [value * instrument_scale for value in front_back_window],
            "side_capsule_window_size": [value * instrument_scale for value in side_window],
            "glass_tube_outer_diameter": tube_outer_radius * 2.0 * instrument_scale,
            "glass_tube_inner_diameter": tube_inner_radius * 2.0 * instrument_scale,
            "glass_tube_length_after_stretch": cylinder_depth * instrument_scale,
            "scale_tick_count": scale_tick_count,
            "scale_major_tick_count": ticks.get("majorTickCount"),
            "scale_labeled_major_tick_count": len(scale_labels),
            "scale_major_values_top_to_bottom": list(range(scale_max_value, -1, -scale_major_value_step)),
            "scale_label_values_top_to_bottom": scale_label_values,
            "scale_unlabeled_major_values": [0],
            "scale_z_start": scale_z_start * instrument_scale,
            "scale_z_end": scale_z_end * instrument_scale,
            "scale_downward_translation": 0.028 * instrument_scale,
            "scale_upper_extension_from_previous": (scale_z_end - 0.304) * instrument_scale,
            "scale_tick_spacing": expected_scale_tick_spacing * instrument_scale,
            "scale_tick_spacing_error_max": scale_tick_spacing_error_max * instrument_scale,
            "scale_tick_spacing_increase": (expected_scale_tick_spacing - previous_scale_tick_spacing) * instrument_scale,
            "scale_tick_spacing_increase_ratio": expected_scale_tick_spacing / previous_scale_tick_spacing - 1.0,
            "scale_major_spacing_increase": (expected_scale_major_spacing - previous_scale_major_spacing) * instrument_scale,
            "scale_top_tick_clearance_to_glass_top": scale_top_tick_to_glass_top_clearance_actual * instrument_scale,
            "scale_top_tick_clearance_to_upper_seal": scale_top_tick_to_upper_seal_clearance_actual * instrument_scale,
            "scale_top_label_clearance_below_upper_seal": scale_top_label_clearance_below_upper_seal * instrument_scale,
            "scale_zero_tick_center_to_glass_bottom": scale_zero_tick_center_to_glass_bottom * instrument_scale,
            "scale_zero_tick_edge_clearance_above_lower_seal": scale_zero_tick_edge_clearance_actual * instrument_scale,
            "scale_major_spacing": scale_label_spacing * instrument_scale,
            "scale_label_alignment_error_max": scale_label_alignment_error_max,
            "scale_label_surface_error_max": scale_label_surface_error_max,
            "scale_label_surface_offset": scale_label_surface_offset * instrument_scale,
            "scale_group_center_x_error": scale_group_center_x_error,
            "scale_label_to_major_tick_gap": scale_label_to_major_tick_gap,
            "scale_label_size": scale_label_size * instrument_scale,
            "scale_label_outline": scale_label_outline * instrument_scale,
            "piston_diameter": piston.dimensions.x,
            "original_piston_height": original_piston_height * instrument_scale,
            "piston_height_after_shortening": piston.dimensions.z,
            "piston_height_reduction": (original_piston_height - piston_height) * instrument_scale,
            "piston_radial_clearance": (tube_inner_radius - piston_radius) * instrument_scale,
            "piston_rod_length": rod_part.dimensions.z,
            "piston_rod_previous_additional_source_length": previous_piston_rod_extra_length,
            "piston_rod_additional_source_length": piston_rod_extra_length,
            "piston_rod_additional_scaled_length": piston_rod_extra_length * instrument_scale,
            "piston_rod_change_this_revision": (piston_rod_extra_length - previous_piston_rod_extra_length) * instrument_scale,
            "pyrex_cylinder_length": cylinder_obj.dimensions.z,
            "piston_rod_length_excess_over_cylinder": rod_part.dimensions.z - cylinder_obj.dimensions.z,
            "mass_platform_vertical_shift": mass_platform_vertical_shift * instrument_scale,
            "piston_rod_top_z": piston_rod_world_top,
            "mass_platform_upper_plate_top_z": upper_plate_world_top,
            "mass_platform_upper_plate_to_piston_rod_top_gap": mass_platform_rod_top_gap,
            "original_housing_combined_height": original_housing_combined_height * instrument_scale,
            "revised_housing_combined_height": housing_combined_height * instrument_scale,
            "v_arm_left_midpoint": list(left_arm_mid),
            "v_arm_right_midpoint": list(right_arm_mid),
            "base_trapezoid_center": list(support_cross_mount_world_center),
            "base_crossmount_y_range": [pedestal_y_front, pedestal_y_back],
            "base_crossmount_bottom_front_width": pedestal_bottom_front_half_x * 2.0,
            "base_crossmount_bottom_back_width": pedestal_bottom_back_half_x * 2.0,
            "base_crossmount_top_front_width": pedestal_top_front_half_x * 2.0,
            "base_crossmount_top_back_width": pedestal_top_back_half_x * 2.0,
            "base_crossmount_top_footprint_scale": pedestal_top_footprint_scale,
            "base_connector_cylinder_center": list(connector_cylinder_world_center),
            "base_connector_cylinder_diameter": connector_cylinder_radius * 2.0,
            "base_connector_cylinder_height": connector_cylinder_depth,
            "upper_cylinder_to_housing_center_y_offset": connector_cylinder_world_center.y - housing_world_center.y,
            "support_rod_to_upper_cylinder_axis_offset": (rod_world_center.xy - connector_cylinder_world_center.xy).length,
            "rod_knob_head_center": list(rod_knob_head.matrix_world.translation),
            "rod_knob_threaded_shaft_center": list(rod_knob_shaft.matrix_world.translation),
            "crossmount_height": pedestal_top_z - pedestal_bottom_z,
            "support_rod_visible_length": rod_visible_length,
            "rod_bridge_front_y": bridge_front_world_y,
            "mass_platform_leaf_bounding_size": list(leaf_dims),
            "scaled_mass_platform_leaf_bounding_size": [value * instrument_scale for value in leaf_dims],
            "mass_platform_pillar_center_offset_x": pillar_x,
            "mass_platform_pillar_diameter": pillar_radius * 2.0,
            "base_foot_center_distance": (right_foot - left_foot).length,
            "base_foot_to_apex": (apex - left_foot).length,
            "level_foot_shape": "vertical_half_cylinder",
            "level_foot_radius": level_foot_radius,
            "level_foot_diameter": level_foot_radius * 2.0,
            "level_foot_height": level_foot_height,
            "level_foot_flat_face_width": level_foot_radius * 2.0,
            "level_foot_beam_overlap": level_foot_beam_overlap,
            "level_foot_visible_outward_projection": level_foot_radius - level_foot_beam_overlap,
            "level_foot_vertical_overlap": level_foot_vertical_overlap,
            "level_foot_lateral_margin_to_beam": base_beam_width * 0.5 - level_foot_radius,
            "level_foot_edge_radius": level_foot_edge_radius,
            "level_foot_left_center": list(left_level_foot.matrix_world.translation),
            "level_foot_right_center": list(right_level_foot.matrix_world.translation),
            "level_foot_left_rotation_z": left_level_foot.rotation_euler.z,
            "level_foot_right_rotation_z": right_level_foot.rotation_euler.z,
            "level_foot_adjuster_screw_count": sum(1 for name in ("LevelFoot_L_AdjusterScrew", "LevelFoot_R_AdjusterScrew") if bpy.data.objects.get(name) is not None),
            "base_beam_width": base_beam_width,
            "base_beam_height": base_beam_height,
            "base_beam_apex_joint_overlap": base_joint_overlap,
            "base_beam_apex_joint_radius": base_joint_radius,
            "base_beam_joint_method": left_base_beam.get("jointMethod"),
            "piston_max_stroke": 0.10 * instrument_scale,
            "hose_outer_diameter": 0.005,
            "hose_inner_diameter": 0.0032,
            "pressure_sensor_uniform_scale": sensor_scale,
            "pressure_sensor_scaled_dimensions": [value * sensor_scale for value in (0.115, 0.038, 0.024)],
            "expanded_table_center": list(table_center),
            "expanded_table_dimensions": list(table_dims),
            "universal_interface_local_origin": list(universal_origin),
            "universal_interface_origin": list(universal_world_origin),
            "pressure_sensor_origin": list(sensor_world_origin),
            "previous_universal_interface_dimensions": list(previous_universal_dims),
            "universal_interface_dimensions": list(universal_dims),
            "universal_interface_x_growth": universal_dims.x - previous_universal_dims.x,
            "universal_interface_z_growth": universal_dims.z - previous_universal_dims.z,
            "universal_interface_front_width_height_ratio": universal_dims.x / universal_dims.z,
            "universal_interface_top_badge_recess_dimensions": list(top_badge_recess_dims),
            "universal_interface_top_badge_inlay_dimensions": list(top_badge_inlay_dims),
            "universal_interface_top_badge_recess_depth": top_badge_recess_depth,
            "universal_interface_top_badge_corner_radius": top_badge_corner_radius,
            "universal_interface_top_badge_center_error": top_badge_xy_center_error,
            "universal_interface_top_badge_inlay_below_cover_top": top_cover_world_bounds_z[1] - top_badge_inlay_world_bounds_z[1],
            "universal_interface_front_panel_dimensions": [0.478, 0.008, 0.151],
            "universal_interface_front_panel_minimum_x_margin": universal_front_panel_margin_x,
            "universal_interface_front_panel_minimum_z_margin": universal_front_panel_margin_z,
            "universal_interface_front_module_areas": {
                "digital": digital_panel_dims.x * digital_panel_dims.z,
                "analog": analog_panel_dims.x * analog_panel_dims.z,
                "pasport": pasport_panel_dims.x * pasport_panel_dims.z,
                "outputs": output_panel_dims.x * output_panel_dims.z,
            },
            "universal_interface_pasport_vertical_shift": pasport_vertical_shift,
            "universal_interface_pasport_panel_center_z": pasport_panel_center.z,
            "universal_interface_pasport_port_center_z": pasport_port_z,
            "universal_interface_pasport_to_upper_panel_clearance": pasport_to_upper_clearance,
            "universal_interface_pasport_pin_hole_diameter": pasport_pin_hole_radius * 2.0,
            "universal_interface_pasport_pin_ring_radius": pasport_pin_ring_radius,
            "universal_interface_pasport_pin_angular_offset_degrees": 22.5,
            "universal_interface_pasport_pin_hole_count": len(pasport_pin_holes),
            "universal_interface_pasport_outer_diameter": pasport_outer_radius * 2.0,
            "universal_interface_pasport_pin_collar_count": len(pasport_pin_collars),
            "universal_interface_pasport_locator_notch_count": len(pasport_locator_notches),
            "universal_interface_pasport_pin_hole_adjacent_clearance": pasport_pin_hole_adjacent_clearance,
            "universal_interface_data_plug_seating_gap": universal_input_plug_seating_gap,
            "universal_interface_housing_front_plane_y": housing_front_plane_y,
            "universal_interface_module_front_plane_y": module_front_plane_y,
            "universal_interface_text_plane_y": module_text_plane_y,
            "universal_interface_text_surface_gap": module_front_plane_y - module_text_plane_y,
            "universal_interface_max_text_y_thickness": interface_label_y_thickness_max,
            "universal_interface_text_bold_offset": interface_text_bold_offset,
            "universal_interface_socket_recess_depth": recess_face_y - module_front_plane_y,
            "universal_interface_digital_input_count": 4,
            "universal_interface_digital_trs_outer_diameter": digital_outer_radius * 2.0,
            "universal_interface_digital_trs_bore_diameter": digital_jack_bore_radius * 2.0,
            "universal_interface_digital_trs_contact_spring_count": len(digital_contact_springs),
            "universal_interface_digital_trs_contact_symmetry_error_max": digital_contact_symmetry_error_max,
            "universal_interface_analog_din_count": len(analog_ports),
            "universal_interface_analog_din_outer_diameter": analog_outer_radius * 2.0,
            "universal_interface_analog_din_pin_arc_degrees": analog_pin_arc_degrees,
            "universal_interface_analog_din_pin_ring_diameter": analog_pin_ring_radius * 2.0,
            "universal_interface_analog_din_pin_hole_diameter": analog_pin_hole_radius * 2.0,
            "universal_interface_analog_din_pin_hole_count": len(analog_pin_holes),
            "universal_interface_analog_din_locator_notch_count": len(analog_locator_notches),
            "universal_interface_analog_din_ring_stack_count": len(analog_trim_rings) + len(analog_bezel_rings) + len(analog_shield_rings),
            "universal_interface_pasport_count": len(pasport_ports),
            "universal_interface_bnc_output_count": len(bnc_ports),
            "universal_interface_bnc_outer_diameter": bnc_outer_radius * 2.0,
            "universal_interface_bnc_inner_diameter": bnc_inner_radius * 2.0,
            "universal_interface_bnc_sleeve_length": bnc_body_length,
            "universal_interface_bnc_nominal_protrusion": bnc_nominal_protrusion,
            "universal_interface_bnc_internal_contact_slot_count": len(bnc_contact_slots),
            "universal_interface_bnc_bayonet_lug_count": len(bnc_bayonet_lugs),
            "sensor_circular_data_port_diameter": 0.013 * sensor_scale,
            "sensor_to_universal_data_cable_diameter": 0.0064,
        },
        "hose_endpoints_m": {
            "external_quick_disconnect": list(hose_start),
            "external_sensor": list(hose_end),
            "internal_quick_disconnect": list(internal_entry),
            "internal_cylinder_bottom": list(cylinder_air_endpoint),
            "data_cable_sensor_circular_connector": list(sensor_data_endpoint),
            "data_cable_universal_interface": list(universal_data_endpoint),
        },
        "previews": [os.path.join(PREVIEW_DIR, f"preview_{label}.png") for label in camera_specs],
    }
    with open(REPORT_PATH, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


create_scene()
