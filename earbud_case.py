"""Storage case for the compact open-ear earbuds: base + friction-fit lid.

Run in Blender (Scripting > Open > Run Script). 1 Blender unit = 1 mm.
Writes stl/earbud_case_base.stl (print opening up) and stl/earbud_case_lid.stl
(print as exported: outer face down, rim up). No supports needed.

Each earbud lies on its side (25 mm direction up) in its own bay, with a divider
between them so the arms do not tangle. The cable coils on top, under the lid.
"""
from pathlib import Path

import bpy

# ---- Settings (mm) ----
EAR_X, EAR_Y, EAR_Z = 24.7, 39.3, 26.0   # one compact earbud bounding box (arm included)
FIT = 1.5               # extra room around each earbud
WALL = 2.0              # case wall and floor thickness
DIVIDER = 2.0           # wall between the two bays
DIV_H = 14.0            # divider height above the floor (leaves room for the cable over it)
BASE_H = 31.0           # base outer height
LID_PLATE = 3.0         # lid top thickness
RIM_H = 4.0             # lid rim length that slides into the base
RIM_T = 1.2             # lid rim wall thickness
RIM_CLEAR = 0.3         # gap between the lid rim and the base wall (friction fit)
CORNER = 3.0            # outer corner and edge rounding
NOTCH_W = 14.0          # thumb notch in the base rim, to prise the lid off

in_w = 2 * (EAR_Z + FIT) + DIVIDER      # interior width (two bays)
in_l = EAR_Y + FIT                      # interior length
in_h_ear = EAR_X + FIT                  # earbud lying on its side
out_w, out_l = in_w + 2 * WALL, in_l + 2 * WALL


def box(name, w, l, h, z0, bevel=0.0, seg=4):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, z0 + h / 2))
    o = bpy.context.object
    o.name = name
    o.scale = (w, l, h)
    bpy.ops.object.transform_apply(scale=True)
    if bevel > 0:
        m = o.modifiers.new("bev", "BEVEL")
        m.width = bevel
        m.segments = seg
        m.limit_method = "NONE"
        bpy.ops.object.modifier_apply(modifier=m.name)
    return o


def boolean(target, tool, op):
    m = target.modifiers.new("bool", "BOOLEAN")
    m.operation = op
    m.object = tool
    m.solver = "EXACT"
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(tool, do_unlink=True)


def export_stl(obj, path):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    try:
        bpy.ops.wm.stl_export(filepath=str(path), export_selected_objects=True)
    except AttributeError:
        bpy.ops.export_mesh.stl(filepath=str(path), use_selection=True)


bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()

# ---- Base ----
base = box("Base", out_w, out_l, BASE_H + 10, 0, bevel=CORNER)
boolean(base, box("TrimTop", out_w + 10, out_l + 10, 20, BASE_H), "DIFFERENCE")
boolean(base, box("Interior", in_w, in_l, BASE_H, WALL, bevel=1.0), "DIFFERENCE")
div = box("Divider", DIVIDER, in_l - 1.0, DIV_H, WALL - 0.2)
boolean(base, div, "UNION")
# thumb notch through the front rim
import math
bpy.ops.mesh.primitive_cylinder_add(
    vertices=64, radius=NOTCH_W / 2, depth=WALL + 2,
    location=(0, -out_l / 2 + WALL / 2, BASE_H + 2), rotation=(math.pi / 2, 0, 0))
notch = bpy.context.object
notch.scale = (1, 1, 1)
boolean(base, notch, "DIFFERENCE")

# ---- Lid (printed upside down: outer face on the bed) ----
LID_X = out_w + 12
lid = box("Lid", out_w, out_l, 10, 0, bevel=CORNER)
boolean(lid, box("TrimLid", out_w + 10, out_l + 10, 20, LID_PLATE), "DIFFERENCE")
rim_w, rim_l = in_w - RIM_CLEAR * 2, in_l - RIM_CLEAR * 2
rim = box("Rim", rim_w, rim_l, RIM_H, LID_PLATE - 0.2, bevel=1.0)
boolean(rim, box("RimIn", rim_w - 2 * RIM_T, rim_l - 2 * RIM_T, RIM_H + 2, LID_PLATE - 0.1, bevel=0.5), "DIFFERENCE")
boolean(lid, rim, "UNION")
lid.location.x = LID_X

out_dir = Path(__file__).resolve().parent / "stl" if "__file__" in globals() else Path.home()
export_stl(base, out_dir / "earbud_case_base.stl")
lid.location.x = 0
bpy.context.view_layer.update()
export_stl(lid, out_dir / "earbud_case_lid.stl")
print("Case interior: %.1f x %.1f, earbud height room %.1f; outer %.1f x %.1f x %.1f" % (in_w, in_l, in_h_ear, out_w, out_l, BASE_H))
