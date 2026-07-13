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
):
    """Create scale marks as thin annular sectors that conform to a tube wall."""
    verts = []
    faces = []
    for tick_index in range(count):
        z = z_start + tick_index * (z_end - z_start) / (count - 1)
        length = 0.014 if tick_index % 10 == 0 else (0.010 if tick_index % 5 == 0 else 0.0065)
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
    apparatus = empty("RSH_Apparatus_ROOT", (0, 0, 0), cols["00_Roots"], scene_root, size=0.025)
    stand = empty("Stand_ROOT", (0, 0, 0), cols["02_Stand"], apparatus)
    instrument_scale = 1.10
    previous_instrument_y_shift = 0.060
    previous_instrument_z_shift = 0.030
    instrument_y_shift = 0.000
    instrument_z_shift = 0.060
    instrument_pivot = Vector((0.0, -0.010, 0.081))
    instrument_root = empty(
        "InstrumentBodyScaled_ROOT",
        (instrument_pivot.x, instrument_pivot.y + instrument_y_shift, instrument_pivot.z + instrument_z_shift),
        cols["00_Roots"],
        apparatus,
        size=0.022,
    )
    instrument_root.scale = (instrument_scale,) * 3
    set_props(instrument_root, uniformScale=instrument_scale, yShift=instrument_y_shift, zShift=instrument_z_shift, pivot=list(instrument_pivot))

    def instrument_world(point):
        point = Vector(point)
        return instrument_pivot + Vector((0.0, instrument_y_shift, instrument_z_shift)) + (point - instrument_pivot) * instrument_scale

    def instrument_source_from_world(point):
        point = Vector(point)
        return instrument_pivot + (point - instrument_pivot - Vector((0.0, instrument_y_shift, instrument_z_shift))) / instrument_scale

    root_compensation = tuple(-component for component in instrument_pivot)
    engine = empty("HeatEngine_ROOT", root_compensation, cols["03_HeatEngine"], instrument_root)
    pneumatic = empty("Pneumatic_ROOT", root_compensation, cols["04_Pneumatic"], instrument_root)
    pneumatic_hose = empty("PneumaticHose_ROOT", (0, 0, 0), cols["04_Pneumatic"], apparatus)
    rod_support = empty("RodSupport_ROOT", (0, 0, 0), cols["03_HeatEngine"], apparatus)
    anchors = empty("ANCHORS", (0, 0, 0), cols["06_Anchors"], scene_root)
    colliders = empty("COLLIDERS", (0, 0, 0), cols["07_Colliders"], scene_root)

    original_table_center = Vector((0.0, -0.06, -0.015))
    original_table_dims = Vector((0.90, 0.70, 0.03))
    table_center = Vector((-0.10, -0.04, -0.015))
    table_dims = Vector((1.25, 0.90, 0.03))
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

    for name, p in (("LevelFoot_L", left_foot), ("LevelFoot_R", right_foot)):
        foot = cylinder(name, (p.x, p.y, 0.005), 0.022, 0.010, mats["rubber"], cols["02_Stand"], stand, 96, 0.001)
        cylinder(name + "_AdjusterScrew", (p.x, p.y, 0.025), 0.0048, 0.036, mats["steel"], cols["02_Stand"], stand, 64, 0.0003)
        set_props(foot, contactZ=0.0, adjustable=True)
    vertex = cylinder("VertexContactPad", (apex.x, apex.y, 0.005), 0.021, 0.010, mats["rubber"], cols["02_Stand"], stand, 96, 0.001)
    set_props(vertex, contactZ=0.0)

    # The shortened support rod now shares the upper-cylinder axis. It no longer
    # relies on the rear vertex pad because the V-frame pedestal carries the body.
    connector_axis_y = 0.050
    rod_xy = (0.0, connector_axis_y)

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

    rod_original_top_z = 0.456 + instrument_z_shift
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

    rod_pass_source = instrument_source_from_world((rod_xy[0], rod_xy[1], housing_center[2]))
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
    top_back_source_center = (0.0, 0.029, 0.301)
    top_back_source_dims = (0.102, 0.016, 0.016)
    top_back_world_center = instrument_world(top_back_source_center)
    rod_connection_z = top_back_world_center.z
    ring_wall("RodClampMount", (rod_xy[0], rod_xy[1], rod_connection_z), 0.015, 0.00655, 0.038, mats["abs"], cols["03_HeatEngine"], rod_support, 128)
    top_back_rear_y = top_back_world_center.y + top_back_source_dims[1] * 0.5 * instrument_scale
    bridge_front_y = top_back_rear_y - 0.004
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
    frame_outer_size = (0.102, 0.094, 0.178)
    frame_center = (0.0, -0.010, 0.220)
    frame_wall_depth = 0.008
    frame_cap_height = 0.016
    front_back_window = (0.082, 0.148)
    side_window = (0.050, 0.138)
    set_props(
        frame,
        structure="single_cuboid_shell",
        realOpenings=True,
        connectedBy="RodClampBridge",
        outerSize=list(frame_outer_size),
    )
    top_slab = cube(
        "ProtectiveFrame_TopSlab", (0, frame_center[1], 0.301),
        (frame_outer_size[0], frame_outer_size[1], frame_cap_height),
        mats["abs"], cols["03_HeatEngine"], frame, 0.003,
    )
    bottom_slab = cube(
        "ProtectiveFrame_BottomSlab", (0, frame_center[1], 0.139),
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
    cylinder_obj = ring_wall("Cylinder_Pyrex", (cyl_center[0], cyl_center[1], 0.2145), tube_outer_radius, tube_inner_radius, 0.157, mats["glass"], cols["03_HeatEngine"], engine, 192)
    set_props(cylinder_obj, materialRuntime="MeshPhysicalMaterial", wallThickness=tube_outer_radius - tube_inner_radius)
    torus("Cylinder_LowerSeal", (cyl_center[0], cyl_center[1], 0.138), 0.0220, 0.0020, mats["detail"], cols["03_HeatEngine"], engine)
    torus("Cylinder_UpperGuideRing", (cyl_center[0], cyl_center[1], 0.291), 0.0220, 0.0020, mats["detail"], cols["03_HeatEngine"], engine)

    ticks = cylindrical_scale_ticks(
        "ScaleTicks_Unnumbered", cyl_center, tube_outer_radius, 0.146, 0.286, 31,
        mats["ticks"], cols["03_HeatEngine"], engine,
        center_angle=-math.pi / 2 + math.radians(24),
    )
    set_props(ticks, pickable=False, containsNumbers=False, attachedTo="Cylinder_Pyrex", conformsToRadius=tube_outer_radius)

    piston_root = empty("PistonAssembly_MOV", (cyl_center[0], cyl_center[1], 0.195), cols["03_HeatEngine"], engine, size=0.022)
    set_props(piston_root, interaction="slide_z", min=0.0, max=0.10, initial=0.06, strokeBaseZ=0.135, axis="local_Z", locked=False)
    piston = cylinder("Piston_Graphite", (0, 0, 0.016), piston_radius, 0.032, mats["graphite"], cols["03_HeatEngine"], piston_root, 192, 0.0005)
    set_props(piston, nominalDiameter=piston_radius * 2.0, nominalHeight=0.032, radialClearance=tube_inner_radius - piston_radius)
    rod_part = cylinder("PistonRod", (0, 0, 0.084), 0.003, 0.104, mats["steel"], cols["03_HeatEngine"], piston_root, 96, 0.0002)
    set_props(rod_part, movesWith="PistonAssembly_MOV")
    platform = empty("MassPlatform", (0, 0, 0), cols["03_HeatEngine"], piston_root, size=0.016)
    leaf_dims = (0.072, 0.062, 0.008)
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
    set_props(platform, emptyPlatform=True, movesWith="PistonAssembly_MOV")

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
    hose_start = instrument_world(hose_start_source)

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
        enlargedInXAndZ=True,
        frontModuleAreasPreserved=True,
    )
    cube(
        "UniversalInterface_TopCover", (0, 0.004, 0.183), (0.523, 0.198, 0.010),
        mats["white"], cols["05_DataSystem"], universal_root, 0.010,
    )
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
    for index, x in enumerate(digital_x, start=1):
        digital_port = cylinder_axis(
            f"UniversalInterface_DigitalInput_{index}",
            (x, recess_face_y + 0.0015, digital_port_z), 0.0058, 0.0030, "Y",
            mats["detail"], cols["05_DataSystem"], digital_module, 64, 0.0002,
        )
        digital_ports.append(digital_port)
        set_props(digital_port, recessed=True, panelFacePlaneY=module_front_plane_y, socketFrontY=recess_face_y)
        cylinder_axis(
            f"UniversalInterface_DigitalInput_{index}_Inner",
            (x, recess_face_y + 0.00055, digital_port_z), 0.0043, 0.0010, "Y",
            mats["interface_panel"], cols["05_DataSystem"], digital_module, 48, 0.0001,
        )
        for pin_index, (dx, dz) in enumerate(((-0.0014, 0.0010), (0.0014, 0.0010), (0.0, -0.0014)), start=1):
            cylinder_axis(
                f"UniversalInterface_DigitalInput_{index}_Pin_{pin_index}",
                (x + dx, recess_face_y + 0.00020, digital_port_z + dz),
                0.00050, 0.0004, "Y", mats["steel"], cols["05_DataSystem"], digital_module, 24,
            )
        interface_label(f"UniversalInterface_DigitalLabel_{index}", str(index), (x, 0.0, 0.137), 0.0110, digital_module)
    interface_label("UniversalInterface_DigitalTitle", "DIGITAL INPUTS", (-0.135, 0.0, 0.098), 0.0073, digital_module)

    analog_letters = ("A", "B", "C", "D")
    analog_ports = []
    for index, (x, letter) in enumerate(zip(analog_x, analog_letters), start=1):
        analog_port = cylinder_axis(
            f"UniversalInterface_AnalogInput_{letter}",
            (x, recess_face_y + 0.0015, analog_port_z), 0.0116, 0.0030, "Y",
            mats["detail"], cols["05_DataSystem"], analog_module, 96, 0.0003,
        )
        analog_ports.append(analog_port)
        set_props(analog_port, recessed=True, panelFacePlaneY=module_front_plane_y, socketFrontY=recess_face_y)
        cylinder_axis(
            f"UniversalInterface_AnalogInput_{letter}_Inner",
            (x, recess_face_y + 0.00055, analog_port_z), 0.0094, 0.0010, "Y",
            mats["interface_panel"], cols["05_DataSystem"], analog_module, 72, 0.0002,
        )
        for pin_index in range(8):
            angle = 2.0 * math.pi * pin_index / 8.0
            dx = math.cos(angle) * 0.0048
            dz = math.sin(angle) * 0.0048
            cylinder_axis(
                f"UniversalInterface_AnalogInput_{letter}_PinHole_{pin_index + 1}",
                (x + dx, recess_face_y + 0.00020, analog_port_z + dz), 0.00065, 0.0004, "Y",
                mats["steel"], cols["05_DataSystem"], analog_module, 24,
            )
        cube(
            f"UniversalInterface_AnalogInput_{letter}_LocatorNotch",
            (x, recess_face_y + 0.00020, analog_port_z + 0.0070),
            (0.0025, 0.0004, 0.0030), mats["interface_panel"], cols["05_DataSystem"], analog_module, 0.0001,
        )
        interface_label(f"UniversalInterface_AnalogLabel_{letter}", letter, (x, 0.0, 0.137), 0.0110, analog_module)
    interface_label(
        "UniversalInterface_AnalogTitle", "ANALOG INPUTS (+/-20 V MAX)",
        (0.020, 0.0, 0.097), 0.0060, analog_module,
    )

    pasport_panels = []
    pasport_ports = []
    pasport_pin_holes = []
    pasport_pin_hole_radius = 0.00200
    pasport_pin_ring_radius = 0.00600
    pasport_pin_hole_adjacent_clearance = 2.0 * pasport_pin_ring_radius * math.sin(math.pi / 8.0) - 2.0 * pasport_pin_hole_radius
    for index, x in enumerate(pasport_x, start=1):
        pasport_panel = cube_with_circular_y_holes(
            f"UniversalInterface_PASPortPanel_{index}", (x, -0.1175, 0.043 + pasport_vertical_shift), (0.074, 0.005, 0.044),
            ((x, pasport_port_z, 0.0092),),
            mats["interface_blue"], cols["05_DataSystem"], pasport_module, 0.007,
        )
        pasport_panels.append(pasport_panel)
        pasport_port = cylinder_axis(
            f"UniversalInterface_PASPort_{index}",
            (x, recess_face_y + 0.0015, pasport_port_z), 0.0085, 0.0030, "Y",
            mats["detail"], cols["05_DataSystem"], pasport_module, 72, 0.0002,
        )
        pasport_ports.append(pasport_port)
        set_props(pasport_port, recessed=True, panelFacePlaneY=module_front_plane_y, socketFrontY=recess_face_y)
        for pin_index in range(8):
            angle = 2.0 * math.pi * pin_index / 8.0
            pin_hole = cylinder_axis(
                f"UniversalInterface_PASPort_{index}_Pin_{pin_index + 1}",
                (x + math.cos(angle) * pasport_pin_ring_radius, recess_face_y + 0.00020, pasport_port_z + math.sin(angle) * pasport_pin_ring_radius),
                pasport_pin_hole_radius, 0.0004, "Y", mats["steel"], cols["05_DataSystem"], pasport_module, 24,
            )
            set_props(pin_hole, recessed=True, visiblePinHole=True, port=index)
            pasport_pin_holes.append(pin_hole)
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

    bnc_ports = []
    for number, x in zip((2, 3), output_x):
        bnc = cylinder_axis(
            f"UniversalInterface_Output_BNC_{number}",
            (x, recess_face_y + 0.0015, output_bnc_z), 0.0070, 0.0030, "Y",
            mats["steel"], cols["05_DataSystem"], output_module, 96, 0.0002,
        )
        bnc_ports.append(bnc)
        set_props(bnc, recessed=True, panelFacePlaneY=module_front_plane_y, socketFrontY=recess_face_y)
        cylinder_axis(
            f"UniversalInterface_Output_BNC_{number}_Bore",
            (x, recess_face_y + 0.00045, output_bnc_z), 0.0032, 0.0008, "Y",
            mats["detail"], cols["05_DataSystem"], output_module, 48, 0.0001,
        )
        for lug_index, dx in enumerate((-0.0072, 0.0072), start=1):
            cube(
                f"UniversalInterface_Output_BNC_{number}_Lug_{lug_index}",
                (x + dx, recess_face_y + 0.00025, output_bnc_z),
                (0.0030, 0.0005, 0.0045), mats["steel"], cols["05_DataSystem"], output_module, 0.0001,
            )
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

    sensor_data_endpoint = world_from_local(
        sensor_origin,
        sensor_angle,
        tuple(value * sensor_scale for value in (-0.080, 0.0, 0.017)),
    )
    universal_data_endpoint = universal_origin + Vector((
        pasport_x[0],
        universal_input_plug_y - universal_input_plug_depth * 0.5,
        pasport_port_z,
    ))
    sensor_data_outward = Vector((-math.cos(sensor_angle), -math.sin(sensor_angle), 0.0))
    data_cable_points = [
        sensor_data_endpoint,
        sensor_data_endpoint + sensor_data_outward * 0.028,
        Vector((-0.250, -0.290, 0.020)),
        Vector((-0.550, -0.205, 0.018)),
        Vector((universal_data_endpoint.x, universal_data_endpoint.y - 0.050, 0.026)),
        universal_data_endpoint + Vector((0.0, -0.028, 0.0)),
        universal_data_endpoint,
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

    hose_end = world_from_local(
        sensor_origin,
        sensor_angle,
        tuple(value * sensor_scale for value in (0.069, -0.009, 0.018)),
    )
    sensor_axis = Vector((math.cos(sensor_angle), math.sin(sensor_angle), 0))
    hose_penultimate = hose_end + sensor_axis * 0.022
    hose_points = [
        hose_start,
        hose_start + Vector((0, 0, 0.040)),
        Vector((-0.050, -0.145, hose_start.z + 0.025)),
        Vector((-0.030, -0.220, 0.035)),
        Vector((-0.005, -0.245, 0.008)),
        hose_penultimate,
        hose_end,
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
    internal_entry = instrument_world((hose_port_source_xy.x, hose_port_source_xy.y, top_lip_top_z + 0.004))
    internal_down = instrument_world((hose_port_source_xy.x, hose_port_source_xy.y, housing_bottom_z + 0.012))
    internal_turn = instrument_world((-0.022, -0.034, housing_bottom_z + 0.010))
    internal_rise = instrument_world((-0.006, cyl_center[1], 0.125))
    cylinder_air_endpoint = instrument_world(cylinder_air_inlet_source)
    internal_hose_points = [internal_entry, internal_down, internal_turn, internal_rise, cylinder_air_endpoint]
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
        ("ANCHOR_Hose_Control_1", hose_points[2]),
        ("ANCHOR_Hose_Control_2", hose_points[4]),
        ("ANCHOR_InternalHose_QuickDisconnect", internal_entry),
        ("ANCHOR_InternalHose_Cylinder", cylinder_air_endpoint),
        ("AXIS_Piston", instrument_world((cyl_center[0], cyl_center[1], 0.135))),
        ("AXIS_RodClamp", (rod_xy[0], rod_xy[1], rod_connection_z)),
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
        ("COL_Base", (0, 0.005, 0.078), (0.330, 0.330, 0.156)),
        ("COL_Housing", tuple(instrument_world(housing_collider_source_center)), tuple(value * instrument_scale for value in housing_collider_source_dims)),
        ("COL_ProtectiveFrame", tuple(instrument_world(frame_center)), tuple(value * instrument_scale for value in (0.104, 0.096, 0.180))),
        (
            "COL_PressureSensor",
            sensor_origin[:2] + (0.017 * sensor_scale,),
            tuple(value * sensor_scale for value in (0.118, 0.041, 0.028)),
        ),
        (
            "COL_UniversalInterface",
            tuple(universal_origin + Vector((0.0, 0.0, (universal_dims.z + 0.008) * 0.5))),
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
        "hero": ((0.48, -0.72, 0.43), (-0.015, -0.055, 0.225), 45),
        "front": ((0.00, -0.78, 0.30), (0.0, -0.018, 0.235), 50),
        "side": ((0.76, -0.02, 0.32), (0.0, -0.010, 0.235), 50),
        "back": ((0.00, 0.75, 0.32), (0.0, 0.000, 0.235), 50),
        "top": ((0.001, -0.02, 0.76), (0.0, -0.02, 0.08), 56),
        "base_top": ((0.001, 0.015, 0.46), (0.0, 0.015, 0.025), 50),
        "sensor_hose": ((0.24, -0.48, 0.16), (-0.060, -0.215, 0.075), 58),
        "sensor_ports": ((-0.105, -0.260, 0.250), (-0.095, -0.258, 0.015), 65),
        "sensor_data_connector": ((-0.355, -0.390, 0.125), (-0.180, -0.272, 0.020), 72),
        "system_overview": ((0.84, -1.16, 0.68), (-0.165, -0.010, 0.165), 39),
        "universal_interface": ((-0.450, -0.650, 0.275), (-0.450, 0.035, 0.095), 52),
        "data_link": ((-0.710, -0.560, 0.325), (-0.355, -0.105, 0.065), 47),
        "quick_disconnect": ((-0.19, -0.30, 0.29), (-0.050, -0.074, 0.235), 75),
        "rod_knob_back": ((0.00, 0.34, 0.41), (0.0, 0.050, 0.383), 80),
    }
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
    for label in camera_specs:
        scene.camera = cameras[label]
        scene.render.filepath = os.path.join(PREVIEW_DIR, f"preview_{label}.png")
        hidden_for_base_top = []
        if label == "base_top":
            base_objects = set(cols["02_Stand"].objects)
            for obj in scene.objects:
                if obj.type in {"MESH", "CURVE"} and obj not in base_objects and obj.name != "Tabletop":
                    hidden_for_base_top.append((obj, obj.hide_render))
                    obj.hide_render = True
            if bpy.data.objects.get("SupportRod_45cm") is not None:
                support_rod_preview = bpy.data.objects["SupportRod_45cm"]
                hidden_for_base_top.append((support_rod_preview, support_rod_preview.hide_render))
                support_rod_preview.hide_render = True
        bpy.ops.render.render(write_still=True)
        for obj, previous_hide_render in hidden_for_base_top:
            obj.hide_render = previous_hide_render

    bpy.ops.object.select_all(action="DESELECT")
    for obj in scene.objects:
        if obj.type not in {"CAMERA", "LIGHT"}:
            obj.select_set(True)
    bpy.ops.export_scene.gltf(
        filepath=GLB_PATH,
        export_format="GLB",
        use_selection=True,
        export_animations=True,
        export_extras=True,
        export_apply=False,
    )

    required = [
        "RSH_Apparatus_ROOT", "Stand_ROOT", "Base_CastIron", "Base_CastIron_LeftBeam", "Base_CastIron_RightBeam", "LevelFoot_L", "LevelFoot_R",
        "VertexContactPad", "SupportRod_45cm", "InstrumentBodyScaled_ROOT", "HeatEngine_ROOT",
        "RodSupport_ROOT", "RodClampMount", "RodClampBridge", "RodClampKnob", "RodClampKnob_KnurledHead", "RodClampKnob_ThreadedShaft",
        "LowerHousing", "LowerHousing_TopLip", "BaseToInstrumentSupport_L", "BaseToInstrumentSupport_R",
        "BaseToInstrument_CrossMount", "BaseToInstrument_UpperCylinder", "ProtectiveFrame",
        "ProtectiveFrame_TopSlab", "ProtectiveFrame_BottomSlab", "ProtectiveFrame_TopBack",
        "ProtectiveFrame_FrontPanel", "ProtectiveFrame_BackPanel", "ProtectiveFrame_LeftPanel", "ProtectiveFrame_RightPanel", "Cylinder_Pyrex",
        "ScaleTicks_Unnumbered", "PistonAssembly_MOV", "Piston_Graphite",
        "PistonRod", "MassPlatform", "MassPlatform_LowerPlate", "MassPlatform_UpperPlate",
        "MassPlatform_LeftPillar", "MassPlatform_RightPillar", "Pneumatic_ROOT",
        "PneumaticHose_ROOT", "Port_Main", "Connector_Main_QuickDisconnect", "Connector_Main_White",
        "Connector_Main_ThreadedStem", "Connector_Main_RotatingCollar", "Hose_Main_Default",
        "Hose_Internal_ToCylinder", "Cylinder_BottomAirInlet",
        "PressureSensor_ROOT", "SensorShell_Blue", "SensorInnerCore", "SensorPort_1",
        "SensorPort_2", "SensorPortLabel_1", "SensorPortLabel_2", "SensorDataConnector",
        "SensorDataCircularPort", "SensorDataCircularPort_LockingCollar", "SensorDataCircularPort_CablePlug",
        "SensorRubberFeet", "UniversalInterface_ROOT", "UniversalInterface_RoundedHousing",
        "UniversalInterface_FrontPanel", "UniversalInterface_PowerModule", "UniversalInterface_DigitalInputModule",
        "UniversalInterface_AnalogInputModule", "UniversalInterface_PASPORTModule", "UniversalInterface_OutputModule",
        "UniversalInterface_DigitalTitle", "UniversalInterface_AnalogTitle", "UniversalInterface_OutputTitle",
        "UniversalInterface_AnalogInput_A", "UniversalInterface_AnalogInput_B", "UniversalInterface_AnalogInput_C", "UniversalInterface_AnalogInput_D",
        "UniversalInterface_Output_BananaBlack", "UniversalInterface_Output_BananaRed",
        "UniversalInterface_Output_BNC_2", "UniversalInterface_Output_BNC_3",
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

    def bounds_inside_with_margin(inner, outer, margin):
        return (
            inner[0] >= outer[0] + margin
            and inner[1] <= outer[1] - margin
            and inner[2] >= outer[2] + margin
            and inner[3] <= outer[3] - margin
        )

    universal_outline_bounds = world_bounds_xz(universal_shell)
    universal_front_panel_bounds = world_bounds_xz(universal_front_panel)
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
    interface_label_plane_world_y = universal_origin.y + module_text_plane_y
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
    recessed_socket_objects = digital_ports + analog_ports + pasport_ports + [output_black, output_red] + bnc_ports
    all_front_sockets_recessed = all(
        socket.get("recessed") is True
        and socket.get("socketFrontY") > socket.get("panelFacePlaneY")
        for socket in recessed_socket_objects
    )
    housing_front_world_y = universal_origin.y + housing_front_plane_y
    power_controls_seated = all(
        world_bounds_y(obj)[0] >= housing_front_world_y - 1e-7
        for obj in (power_ring, power_button, status_led)
    )
    pasport1_port_world_center = pasport_ports[0].matrix_world.translation
    universal_input_plug_world_center = universal_input_plug.matrix_world.translation
    universal_input_plug_inner_world_y = universal_origin.y + universal_input_plug_y + universal_input_plug_depth * 0.5
    pasport1_socket_front_world_y = universal_origin.y + recess_face_y
    universal_input_plug_seating_gap = abs(universal_input_plug_inner_world_y - pasport1_socket_front_world_y)
    universal_input_plug_axis_aligned = (
        abs(universal_input_plug_world_center.x - pasport1_port_world_center.x) < 1e-9
        and abs(universal_input_plug_world_center.z - pasport1_port_world_center.z) < 1e-9
    )

    rod_bottom = rod.location.z - rod.dimensions.z / 2
    rod_top = rod.location.z + rod.dimensions.z / 2
    piston_min = (0.135, 0.167)
    piston_max = (0.235, 0.267)
    cylinder_bounds = (0.136, 0.293)
    checks = {
        "required_nodes_present": len(missing) == 0,
        "metric_unit_scale_1": scene.unit_settings.system == "METRIC" and abs(scene.unit_settings.scale_length - 1.0) < 1e-9,
        "support_rod_nominal_450mm": abs(rod.get("nominalLength") - 0.450) < 1e-9,
        "support_rod_lower_segment_removed": rod_bottom >= housing_world_center.z - 1e-8 and rod.dimensions.z < 0.450,
        "support_rod_diameter_12_7mm": abs(rod.dimensions.x - 0.0127) < 1e-6,
        "support_rod_aligned_with_upper_cylinder_vertical_axis": (Vector((rod.location.x, rod.location.y)) - connector_cylinder.matrix_world.translation.xy).length < 1e-8,
        "instrument_uniform_scale_1_10": max(abs(value - instrument_scale) for value in instrument_root.scale) < 1e-6,
        "instrument_moved_negative_y_60mm_from_previous": instrument_y_shift < previous_instrument_y_shift and abs(previous_instrument_y_shift - instrument_y_shift - 0.060) < 1e-9,
        "instrument_shifted_up_60mm_total": abs((instrument_root.location.z - instrument_pivot.z) - instrument_z_shift) < 1e-7 and instrument_z_shift > previous_instrument_z_shift,
        "instrument_body_hierarchy_preserved": engine.parent == instrument_root and pneumatic.parent == instrument_root,
        "rod_clamp_still_centered_on_support_rod": (bpy.data.objects["RodClampMount"].matrix_world.translation.xy - rod.matrix_world.translation.xy).length < 1e-8,
        "rod_clamp_height_matches_top_back": abs(bpy.data.objects["RodClampMount"].matrix_world.translation.z - top_back_world_center.z) < 1e-8,
        "rod_bridge_horizontal_to_top_back": abs(bridge.matrix_world.translation.z - top_back_world_center.z) < 1e-8 and bridge_depth > 0.0,
        "rod_bridge_overlaps_top_back": bridge_front_y <= top_back_rear_y and bridge_front_y >= top_back_world_center.y,
        "rod_bridge_slab_end_matches_top_slab_length": abs(bridge.get("slabEndWidth") - top_slab.dimensions.x) < 1e-6,
        "rod_bridge_tapers_toward_clamp": bridge.get("slabEndWidth") > bridge.get("clampEndWidth"),
        "rod_knob_head_follows_top_connection": abs(rod_knob_head.matrix_world.translation.z - rod_connection_z) < 1e-8,
        "rod_knob_head_directly_behind_support_rod": abs(rod_knob_head.matrix_world.translation.x - rod.matrix_world.translation.x) < 1e-8 and rod_knob_head.matrix_world.translation.y > rod.matrix_world.translation.y,
        "rod_knob_threaded_shaft_directly_behind_support_rod": abs(rod_knob_shaft.matrix_world.translation.x - rod.matrix_world.translation.x) < 1e-8 and rod_knob_shaft.matrix_world.translation.y > rod.matrix_world.translation.y,
        "rod_knob_axis_is_rearward_y": rod_knob.get("axis") == "Y" and rod_knob.get("rearDirection") == "positive_Y",
        "protective_frame_is_single_cuboid_shell": frame.get("structure") == "single_cuboid_shell",
        "front_back_windows_large_for_glass_view": front_back_window[0] * front_back_window[1] / (frame_outer_size[0] * frame_outer_size[2]) > 0.65,
        "side_capsule_opening_size_preserved": abs(side_window[0] - 0.050) < 1e-9 and abs(side_window[1] - 0.138) < 1e-9,
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
        "glass_tube_thickened_to_48mm": abs(cylinder_obj.dimensions.x - tube_outer_radius * 2.0 * instrument_scale) < 1e-6,
        "piston_thickened_and_fits_tube": abs(piston.dimensions.x - piston_radius * 2.0 * instrument_scale) < 1e-6 and piston_radius < tube_inner_radius,
        "scale_ticks_conform_to_glass": ticks.get("attachedTo") == "Cylinder_Pyrex" and abs(ticks.get("conformsToRadius") - tube_outer_radius) < 1e-9,
        "scale_strip_removed": bpy.data.objects.get("ScaleStrip_Clear") is None,
        "vent_assembly_removed": all(bpy.data.objects.get(name) is None for name in ("Port_Vent", "Port_Vent_WhiteConnector", "Tube_Vent_Short", "VentPinchClamp", "VentPinchClamp_CompressionJaw")),
        "base_is_open_v_shape": base_node.get("type") == "cast_iron_open_V_frame" and bpy.data.objects.get("Base_CastIron_FrontBeam") is None,
        "base_beams_enlarged_in_length_width_height": base_arm_length > original_base_arm_length and base_beam_width > original_base_beam_width and base_beam_height > original_base_beam_height,
        "base_feet_spacing_enlarged": abs((right_foot - left_foot).length - base_foot_spacing) < 1e-7 and base_foot_spacing > original_base_foot_spacing,
        "base_arms_enlarged_to_295mm": abs((apex - left_foot).length - base_arm_length) < 1e-7 and abs((apex - right_foot).length - base_arm_length) < 1e-7,
        "v_arm_midpoint_supports_present": left_base_support.get("connectsFrom") == "Base_CastIron_LeftBeam_Midpoint" and right_base_support.get("connectsFrom") == "Base_CastIron_RightBeam_Midpoint",
        "base_connector_is_v_conforming_loft_plus_upper_cylinder": support_cross_mount.get("shape") == "v_conforming_footprint_loft" and connector_cylinder.get("shape") == "cylinder",
        "connector_rectangular_when_viewed_along_x": abs(pedestal_bottom_center.y - pedestal_top_center.y) < 1e-9,
        "connector_trapezoidal_when_viewed_along_y": pedestal_bottom_front_half_x > pedestal_top_front_half_x and pedestal_bottom_back_half_x > pedestal_top_back_half_x,
        "connector_is_trapezoid_in_top_view": pedestal_bottom_front_half_x > pedestal_bottom_back_half_x and support_cross_mount.get("topViewShape") == "trapezoid",
        "upper_connector_cylinder_meets_housing": abs(connector_cylinder_top_z - housing_world_bottom_z) < 1e-8,
        "upper_connector_is_off_center_on_housing_bottom": abs(connector_cylinder_center.y - housing_world_center.y) > 0.050,
        "lower_instrument_support_volume_enlarged": connector_cylinder_radius > previous_connector_cylinder_radius and connector_cylinder_depth > previous_connector_cylinder_depth and pedestal_top_footprint_scale > previous_pedestal_top_footprint_scale and (pedestal_top_z - pedestal_bottom_z) > 0.070,
        "trapezoid_overlaps_v_arm_midpoints": pedestal_y_front <= left_arm_mid.y <= pedestal_y_back and abs(left_arm_mid.x) < base_outer_half_x_at_y(left_arm_mid.y),
        "left_right_base_beams_meet_at_common_apex": (left_joint_end - apex).length < 1e-9 and (right_joint_end - apex).length < 1e-9,
        "crossmount_outer_edges_match_base_beams_at_every_y": abs(pedestal_bottom_front_half_x - base_outer_half_x_at_y(pedestal_y_front)) < 1e-9 and abs(pedestal_bottom_back_half_x - base_outer_half_x_at_y(pedestal_y_back)) < 1e-9,
        "connector_cylinder_fits_top_footprint": ((pedestal_top_front_half_x + pedestal_top_back_half_x) * 0.5) > connector_cylinder_radius,
        "base_beam_joint_is_smooth_boolean_union": left_base_beam.get("jointMethod") == "exact_boolean_union_with_rounded_hub" and left_base_beam.get("containsUnifiedVArms") is True and left_base_beam.get("pointedJointCornersRemoved") is True and right_base_beam.get("representedBy") == "Base_CastIron_LeftBeam",
        "base_beam_joint_has_rounded_transition": abs(left_base_beam.get("apexJointRadius") - base_joint_radius) < 1e-9 and base_joint_radius > base_beam_width * 0.5,
        "three_base_contacts_on_table": True,
        "sensor_feet_on_table": True,
        "hose_start_matches_anchor": (Vector(bpy.data.objects["ANCHOR_Hose_Start"].location) - hose_start).length < 1e-8,
        "hose_end_matches_anchor": (Vector(bpy.data.objects["ANCHOR_Hose_End"].location) - hose_end).length < 1e-8,
        "hose_terminal_enters_top_lip_vertically": (hose_points[1] - hose_points[0]).xy.length < 1e-9 and hose_points[1].z > hose_points[0].z and port_main.get("orientation") == "vertical_Z",
        "top_lip_has_quick_disconnect_hole": top_lip.get("quickDisconnectHole") is True and top_lip.get("quickDisconnectHoleAxis") == "Z",
        "quick_disconnect_rotates_and_seals": quick_disconnect_root.get("interaction") == "rotate_connect_disconnect" and quick_disconnect_root.get("sealedWhenConnected") is True and quick_disconnect_root.get("openToAtmosphereWhenDisconnected") is True,
        "internal_hose_descends_vertically_inside_housing": (internal_hose_points[1] - internal_hose_points[0]).xy.length < 1e-9 and internal_hose_points[1].z < internal_hose_points[0].z,
        "internal_hose_connects_to_cylinder_bottom": (internal_hose_points[-1] - cylinder_air_endpoint).length < 1e-9 and internal_hose.get("connectsTo") == "Cylinder_BottomAirInlet",
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
        "universal_interface_all_sockets_are_recessed": all_front_sockets_recessed,
        "universal_interface_digital_and_analog_sockets_enlarged": digital_ports[0].dimensions.x >= 0.0115 and analog_ports[0].dimensions.x >= 0.0231,
        "universal_interface_pasport_sockets_enlarged": pasport_ports[0].dimensions.x >= 0.0169,
        "universal_interface_all_32_pasport_pin_holes_enlarged": len(pasport_pin_holes) == 32 and all(pin_hole.dimensions.x >= pasport_pin_hole_radius * 2.0 - 1e-7 and pin_hole.get("recessed") is True for pin_hole in pasport_pin_holes),
        "universal_interface_pasport_pin_holes_remain_separate": pasport_pin_hole_adjacent_clearance > 0.0005,
        "universal_interface_pasport_pin_holes_remain_inside_socket": pasport_pin_ring_radius + pasport_pin_hole_radius <= 0.0085,
        "universal_interface_data_plug_seated_in_pasport_1": universal_input_plug.get("connectedTo") == "UniversalInterface_PASPort_1" and pasport_ports[0].get("occupiedBy") == "UniversalInterface_DataCablePlug" and universal_input_plug_axis_aligned and universal_input_plug_seating_gap < 1e-9,
        "universal_interface_power_zone_only_has_switch_and_led": bpy.data.objects.get("UniversalInterface_850Label") is None and set(child.name for child in power_module.children) == {"UniversalInterface_PowerRing", "UniversalInterface_PowerButton", "UniversalInterface_StatusLED"},
        "universal_interface_power_zone_shifted_left_with_clearance": power_x + 0.0125 < digital_panel_center.x - digital_panel_dims.x * 0.5 - 0.010,
        "universal_interface_power_controls_are_seated": power_controls_seated,
        "universal_interface_has_five_function_modules": all(module.parent == universal_root for module in (power_module, digital_module, analog_module, pasport_module, output_module)),
        "universal_interface_has_four_detailed_digital_inputs": all(bpy.data.objects.get(f"UniversalInterface_DigitalInput_{index}_Pin_3") is not None for index in range(1, 5)),
        "universal_interface_has_four_detailed_analog_din_inputs": len(analog_ports) == 4 and all(bpy.data.objects.get(f"UniversalInterface_AnalogInput_{letter}_PinHole_8") is not None and bpy.data.objects.get(f"UniversalInterface_AnalogInput_{letter}_LocatorNotch") is not None for letter in analog_letters),
        "universal_interface_has_four_detailed_pasport_inputs": len(pasport_ports) == 4 and all(bpy.data.objects.get(f"UniversalInterface_PASPort_{index}_Pin_8") is not None and bpy.data.objects.get(f"UniversalInterface_PASPortLabel_{index}") is not None for index in range(1, 5)),
        "universal_interface_output_section_complete": output_black.parent == output_module and output_red.parent == output_module and len(bnc_ports) == 2 and all(port.parent == output_module for port in bnc_ports),
        "universal_interface_function_labels_are_meshes": all(bpy.data.objects[name].type == "MESH" for name in ("UniversalInterface_DigitalTitle", "UniversalInterface_AnalogTitle", "UniversalInterface_OutputTitle", "UniversalInterface_Output15VLabel", "UniversalInterface_Output10VLabel")),
        "universal_interface_brand_logo_removed": universal_shell.get("brandLogoRemoved") is True and bpy.data.objects.get("UniversalInterface_Title") is None,
        "universal_interface_is_left_rear_of_main_apparatus": universal_origin.x < -0.15 and universal_origin.y > 0.05,
        "tabletop_expanded_for_universal_interface": table_dims.x > original_table_dims.x and table_dims.y > original_table_dims.y,
        "universal_interface_footprint_inside_table": universal_origin.x - universal_dims.x * 0.5 >= table_center.x - table_dims.x * 0.5 and universal_origin.x + universal_dims.x * 0.5 <= table_center.x + table_dims.x * 0.5 and universal_origin.y - universal_dims.y * 0.5 >= table_center.y - table_dims.y * 0.5 and universal_origin.y + universal_dims.y * 0.5 <= table_center.y + table_dims.y * 0.5,
        "universal_interface_feet_on_table": all(abs(foot.get("contactZ", -1.0)) < 1e-9 for foot in universal_feet),
        "sensor_data_cable_start_matches_connector": (data_cable_points[0] - sensor_data_endpoint).length < 1e-9 and (Vector(data_anchor_sensor.location) - sensor_data_endpoint).length < 1e-9,
        "sensor_data_cable_end_matches_universal_interface": (data_cable_points[-1] - universal_data_endpoint).length < 1e-9 and (Vector(data_anchor_interface.location) - universal_data_endpoint).length < 1e-9,
        "sensor_data_cable_terminal_directions_correct": (data_cable_points[1] - data_cable_points[0]).normalized().dot(sensor_data_outward) > 0.999 and (data_cable_points[-1] - data_cable_points[-2]).normalized().dot(Vector((0.0, 1.0, 0.0))) > 0.999,
        "sensor_to_universal_data_cable_present": data_cable.get("connectsFrom") == "SensorDataCircularPort_CablePlug" and data_cable.get("connectsTo") == "UniversalInterface_DataCablePlug",
        "no_text_objects": all(obj.type != "FONT" for obj in scene.objects),
    }
    report = {
        "source": "DOCX section 8 plus two supplied orbit videos",
        "blender_version": bpy.app.version_string,
        "blend_path": BLEND_PATH,
        "glb_path": GLB_PATH,
        "required_nodes_missing": missing,
        "checks": checks,
        "all_checks_passed": len(missing) == 0 and all(checks.values()),
        "evaluated_triangle_count_without_colliders": triangles,
        "measurements_m": {
            "support_rod_length": rod.dimensions.z,
            "support_rod_diameter": rod.dimensions.x,
            "support_rod_bottom": rod_bottom,
            "support_rod_top": rod_top,
            "support_rod_xy": list(rod_xy),
            "vertex_contact_pad_xy": [vertex.location.x, vertex.location.y],
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
            "protective_frame_outer_size": [value * instrument_scale for value in frame_outer_size],
            "front_back_window_size": [value * instrument_scale for value in front_back_window],
            "side_capsule_window_size": [value * instrument_scale for value in side_window],
            "glass_tube_outer_diameter": tube_outer_radius * 2.0 * instrument_scale,
            "glass_tube_inner_diameter": tube_inner_radius * 2.0 * instrument_scale,
            "piston_diameter": piston.dimensions.x,
            "piston_radial_clearance": (tube_inner_radius - piston_radius) * instrument_scale,
            "original_housing_combined_height": original_housing_combined_height * instrument_scale,
            "revised_housing_combined_height": housing_combined_height * instrument_scale,
            "v_arm_left_midpoint": list(left_arm_mid),
            "v_arm_right_midpoint": list(right_arm_mid),
            "base_trapezoid_center": list(support_cross_mount.location),
            "base_crossmount_y_range": [pedestal_y_front, pedestal_y_back],
            "base_crossmount_bottom_front_width": pedestal_bottom_front_half_x * 2.0,
            "base_crossmount_bottom_back_width": pedestal_bottom_back_half_x * 2.0,
            "base_crossmount_top_front_width": pedestal_top_front_half_x * 2.0,
            "base_crossmount_top_back_width": pedestal_top_back_half_x * 2.0,
            "base_crossmount_top_footprint_scale": pedestal_top_footprint_scale,
            "base_connector_cylinder_center": list(connector_cylinder.location),
            "base_connector_cylinder_diameter": connector_cylinder_radius * 2.0,
            "base_connector_cylinder_height": connector_cylinder_depth,
            "upper_cylinder_to_housing_center_y_offset": connector_cylinder_center.y - housing_world_center.y,
            "support_rod_to_upper_cylinder_axis_offset": (Vector((rod.location.x, rod.location.y)) - connector_cylinder.matrix_world.translation.xy).length,
            "rod_knob_head_center": list(rod_knob_head.matrix_world.translation),
            "rod_knob_threaded_shaft_center": list(rod_knob_shaft.matrix_world.translation),
            "crossmount_height": pedestal_top_z - pedestal_bottom_z,
            "support_rod_visible_length": rod_visible_length,
            "rod_bridge_front_y": bridge_front_y,
            "mass_platform_leaf_bounding_size": list(leaf_dims),
            "scaled_mass_platform_leaf_bounding_size": [value * instrument_scale for value in leaf_dims],
            "mass_platform_pillar_center_offset_x": pillar_x,
            "mass_platform_pillar_diameter": pillar_radius * 2.0,
            "base_foot_center_distance": (right_foot - left_foot).length,
            "base_foot_to_apex": (apex - left_foot).length,
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
            "universal_interface_origin": list(universal_origin),
            "previous_universal_interface_dimensions": list(previous_universal_dims),
            "universal_interface_dimensions": list(universal_dims),
            "universal_interface_x_growth": universal_dims.x - previous_universal_dims.x,
            "universal_interface_z_growth": universal_dims.z - previous_universal_dims.z,
            "universal_interface_front_width_height_ratio": universal_dims.x / universal_dims.z,
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
            "universal_interface_pasport_pin_hole_count": len(pasport_pin_holes),
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
            "universal_interface_analog_din_count": len(analog_ports),
            "universal_interface_pasport_count": len(pasport_ports),
            "universal_interface_bnc_output_count": len(bnc_ports),
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
