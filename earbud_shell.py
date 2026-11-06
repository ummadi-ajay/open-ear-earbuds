"""Open-ear earbud: egg-shaped pod, ear arm and back cap, built around a salvaged driver.

Run inside Blender (Scripting tab > Open > Run Script). 1 Blender unit = 1 mm.
Creates two printable parts, side by side, and exports them as STL files
into the stl/ folder next to this script (home folder if run without a file path):
  earbud_shell.stl  (egg pod with front grille, snap groove and printed ear arm)
  earbud_cap.stl    (back cap with snap ridge, clamp ring, cable slot and rear vent)
SIDE = 1 builds the left ear, SIDE = -1 the right. The cap fits either ear.
Rename the files after each run, because the next run overwrites them.
"""
import math
from pathlib import Path

import bpy

# ---- Settings (mm) ----
DRIVER_D = 14.4        # cavity inner diameter = DRIVER_D + 2*CLEAR = 15 mm
CLEAR = 0.3           # clearance per side (raise to 0.4 if your printer is rough)
WALL = 1.0             # shell wall thickness
RING_H = 0.6           # clamp ring length on the cap
LIP = 1.0              # front lip thickness
DRIVER_METAL_T = 6.6   # metal can thickness (measured)
FOAM_T = 0.8           # foam ring on the front face (estimate: measure and adjust)
DRIVER_T = DRIVER_METAL_T + FOAM_T
SQUEEZE = 0.3          # how far the ring compresses the foam
PLUG_H = 2.0
SHELL_H = LIP + DRIVER_T - SQUEEZE + RING_H + PLUG_H   # deep enough for the driver
RING_OD = 13.0         # clamp ring on the cap: presses the driver rim, not its centre
RING_ID = 10.0
PORT_D = 10.0          # area covered by the speaker grille
GRILLE_HOLE_D = 0.8    # each mesh hole (0.8-1.2 prints well on a 0.4 mm nozzle)
GRILLE_PITCH = 1.4     # centre-to-centre spacing (smaller = finer, more holes)
HOOK_WIRE_D = 2.0      # ear-hook wire diameter
CABLE_D = 2.5          # cable hole in cap
VENT_D = 0.8           # rear vent

# Ear hook: "printed" = open-ear arm printed with the pod, "wire" = socket for bent wire
HOOK_STYLE = "printed"
SIDE = 1               # 1 = one ear, -1 = the other ear (mirrors the arm)
ARM_THICK = 3.5       # arm diameter (print in TPU or PETG for some flex)
ARM_RISE = 14.0        # straight rise from the pod before the curve
ARM_R = 13.0           # half-circle radius; the ear sits in the 2*R gap
ARM_DROP = 16.0        # how far the arm drops behind the ear
ARM_TILT_DEG = 35.0    # swings the arm toward the back of the ear
END_BALL_D = 9.0       # end weight behind the ear

# Egg-shaped pod: rounded front, widest near the front, tapering to the cap's radius
EGG_FRONT_R = 6.8      # flat front face radius (covers the grille)
EGG_MAX_R = 9.2        # widest radius of the egg
EGG_MAX_Z = 3.0        # depth of the widest point (the front rounds off before it)
GRILLE_TILT_DEG = 15.0 # grille angled toward the ear canal (0 = square to the arm)

cav_r = DRIVER_D / 2 + CLEAR          # cavity radius
out_r = cav_r + WALL                  # shell outer radius
plug_r = cav_r - 0.1                  # cap plug radius (snug fit)
CAP_T = 1.5
boss_r = HOOK_WIRE_D / 2 + 1.5
hook_hole_r = HOOK_WIRE_D / 2 + 0.1


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def cyl(name, r, h, loc, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=96, radius=r, depth=h, location=loc, rotation=rot
    )
    obj = bpy.context.object
    obj.name = name
    return obj


def boolean(target, tool, op):
    mod = target.modifiers.new("bool", "BOOLEAN")
    mod.operation = op
    mod.object = tool
    mod.solver = "EXACT"
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(tool, do_unlink=True)


def export_stl(obj, path):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    try:
        bpy.ops.wm.stl_export(filepath=str(path), export_selected_objects=True)
    except AttributeError:  # Blender < 4.2
        bpy.ops.export_mesh.stl(filepath=str(path), use_selection=True)


clear_scene()

# ---- Shell: front face on z=0, open at the back (z=SHELL_H) ----
def egg_body(name):
    """Solid of revolution about Z: flat front face, rounded shoulder, taper to out_r."""
    prof = []
    for i in range(25):
        z = EGG_MAX_Z * i / 24
        k = math.sqrt(max(0.0, 1 - ((EGG_MAX_Z - z) / EGG_MAX_Z) ** 2))
        prof.append((EGG_FRONT_R + (EGG_MAX_R - EGG_FRONT_R) * k, z))
    for i in range(1, 25):
        t = i / 24
        prof.append((out_r + (EGG_MAX_R - out_r) * (0.5 + 0.5 * math.cos(math.pi * t)),
                     EGG_MAX_Z + (SHELL_H - EGG_MAX_Z) * t))
    n = 96
    verts = [(0, 0, 0)]
    for r, z in prof:
        for j in range(n):
            a = 2 * math.pi * j / n
            verts.append((r * math.cos(a), r * math.sin(a), z))
    verts.append((0, 0, SHELL_H))
    last = len(verts) - 1
    faces = []
    for j in range(n):
        faces.append((0, 1 + (j + 1) % n, 1 + j))
    for i in range(len(prof) - 1):
        for j in range(n):
            a, b = 1 + i * n + j, 1 + i * n + (j + 1) % n
            faces.append((a, b, b + n, a + n))
    base = 1 + (len(prof) - 1) * n
    for j in range(n):
        faces.append((last, base + j, base + (j + 1) % n))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.validate()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    return obj


shell = egg_body("Shell")

# Boss on the top (+Y) side for the ear-hook wire
boss_len = 6.4
boss_y0 = out_r - 0.3
if HOOK_STYLE == "wire":
    boss = cyl(
        "Boss", boss_r, boss_len,
        (0, boss_y0 + boss_len / 2, SHELL_H / 2),
        rot=(math.pi / 2, 0, 0),
    )
    boolean(shell, boss, "UNION")
else:
    # Printed open-ear arm: up from the pod, a half-circle over the top of the
    # ear toward the head, then down behind the ear to an end weight.
    pts = []
    zc = SHELL_H / 2
    y_a = out_r + ARM_RISE
    tilt = math.radians(ARM_TILT_DEG)

    def add(y, dz):
        # dz is the offset from the shell centre along the driver axis (negative
        # = toward the head). The tilt swings the arm toward the back of the ear.
        pts.append((-SIDE * dz * math.sin(tilt), y, zc + dz * math.cos(tilt)))

    for i in range(0, 9):                       # rise out of the pod
        add(out_r - 0.5 + (y_a - out_r + 0.5) * i / 8, 0)
    for i in range(1, 25):                      # half-circle over the ear
        t = math.pi * i / 24
        add(y_a + ARM_R * math.sin(t), -ARM_R + ARM_R * math.cos(t))
    for i in range(1, 9):                       # down behind the ear
        add(y_a - ARM_DROP * i / 8, -2 * ARM_R)

    crv = bpy.data.curves.new("Arm", "CURVE")
    crv.dimensions = "3D"
    crv.bevel_depth = ARM_THICK / 2
    crv.bevel_resolution = 5
    crv.use_fill_caps = True
    spl = crv.splines.new("POLY")
    spl.points.add(len(pts) - 1)
    # Tilt the arm about the pod centre so the grille angles toward the ear canal
    ca, sa = math.cos(math.radians(GRILLE_TILT_DEG)), math.sin(math.radians(GRILLE_TILT_DEG))
    pts = [(x, y * ca - (z - zc) * sa, zc + y * sa + (z - zc) * ca) for x, y, z in pts]
    for p, co in zip(spl.points, pts):
        p.co = (*co, 1.0)
    arm = bpy.data.objects.new("Arm", crv)
    bpy.context.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.convert(target="MESH")
    arm = bpy.context.object

    # End weight behind the ear (balances the pod, like the reference design)
    ex, ey, ez = pts[-1]
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=48, ring_count=24, radius=END_BALL_D / 2, location=(ex, ey, ez)
    )
    ball = bpy.context.object
    boolean(arm, ball, "UNION")
    boolean(shell, arm, "UNION")

# Cavity for the driver (leaves the front lip)
cav_h = SHELL_H - LIP + 0.5
cavity = cyl("Cavity", cav_r, cav_h, (0, 0, LIP + cav_h / 2))
boolean(shell, cavity, "DIFFERENCE")

# Snap groove near the back of the cavity: the cap's ridge clicks into it
RIDGE_H = 0.8
GROOVE_Z = SHELL_H - PLUG_H + 0.4 + RIDGE_H / 2
groove = cyl("Groove", cav_r + 0.2, RIDGE_H, (0, 0, GROOVE_Z))
boolean(shell, groove, "DIFFERENCE")

# Fine mesh grille in the front wall: a hexagonal grid of small holes inside
# PORT_D, so they line up with the driver's sound holes.
holes = []
row_h = GRILLE_PITCH * math.sqrt(3) / 2
max_r = PORT_D / 2 - GRILLE_HOLE_D / 2 - 0.3
for row in range(-8, 9):
    y = row * row_h
    for col in range(-8, 9):
        x = col * GRILLE_PITCH + (GRILLE_PITCH / 4 if row % 2 else -GRILLE_PITCH / 4)
        if math.hypot(x, y) <= max_r:
            holes.append((x, y))
objs = [cyl(f"Hole{i}", GRILLE_HOLE_D / 2, LIP + 2, (x, y, LIP / 2))
        for i, (x, y) in enumerate(holes)]
bpy.ops.object.select_all(action="DESELECT")
for o in objs:
    o.select_set(True)
bpy.context.view_layer.objects.active = objs[0]
bpy.ops.object.join()
boolean(shell, bpy.context.object, "DIFFERENCE")

# Blind hole for the hook wire (stops before the cavity wall)
if HOOK_STYLE == "wire":
    hole_y0 = out_r + 0.7
    hole_len = boss_y0 + boss_len - hole_y0 + 0.5
    hook_hole = cyl(
        "HookHole", hook_hole_r, hole_len,
        (0, hole_y0 + hole_len / 2, SHELL_H / 2),
        rot=(math.pi / 2, 0, 0),
    )
    boolean(shell, hook_hole, "DIFFERENCE")

# ---- Cap: printed flat, plug pointing up, placed beside the shell ----
CAP_X = out_r * 2 + 30  # clear of the printed arm
cap = cyl("Cap", out_r, CAP_T, (CAP_X, 0, CAP_T / 2))
plug = cyl("Plug", plug_r, PLUG_H, (CAP_X, 0, CAP_T + PLUG_H / 2))
boolean(cap, plug, "UNION")

# Tapered snap ridge near the plug tip (flat shoulder on the cap side holds it in)
ridge_z = CAP_T + PLUG_H - 0.4 - RIDGE_H / 2
bpy.ops.mesh.primitive_cone_add(
    vertices=96, radius1=cav_r + 0.15, radius2=plug_r, depth=RIDGE_H,
    location=(CAP_X, 0, ridge_z),
)
ridge = bpy.context.object
ridge.name = "Ridge"
boolean(cap, ridge, "UNION")

# Clamp ring: pushes the driver's foam rim against the front lip, so the
# front and back of the driver are sealed with no glue. Centre stays open for
# the solder joints and wires.
RING_L = SHELL_H - PLUG_H - (LIP + DRIVER_T - SQUEEZE)
if RING_L > 0.2:
    ring_z = CAP_T + PLUG_H + RING_L / 2
    ring = cyl("Ring", RING_OD / 2, RING_L + 0.2, (CAP_X, 0, ring_z - 0.1))
    ring_in = cyl("RingIn", RING_ID / 2, RING_L + 1, (CAP_X, 0, ring_z))
    boolean(ring, ring_in, "DIFFERENCE")
    boolean(cap, ring, "UNION")
else:
    RING_L = 0

total = CAP_T + PLUG_H + RING_L
cable = cyl("Cable", CABLE_D / 2, total + 2, (CAP_X - 3.5, 0, total / 2))
boolean(cap, cable, "DIFFERENCE")

# Open slot from the cable hole to the cap edge, so the cable (with the driver
# wires already attached) can be dropped in from the side, not threaded through.
slot_x0 = CAP_X - 3.5
slot_x1 = CAP_X - out_r - 1.0
slot_len = slot_x0 - slot_x1
bpy.ops.mesh.primitive_cube_add(
    location=((slot_x0 + slot_x1) / 2, 0, total / 2)
)
slot = bpy.context.object
slot.name = "Slot"
slot.scale = (slot_len / 2, CABLE_D / 2, (total + 2) / 2)
boolean(cap, slot, "DIFFERENCE")

vent = cyl("Vent", VENT_D / 2, total + 2, (CAP_X + 3.5, 0, total / 2))
boolean(cap, vent, "DIFFERENCE")

# ---- Export ----
out_dir = Path(__file__).resolve().parent / "stl" if "__file__" in globals() else Path.home()
out_dir.mkdir(exist_ok=True)
export_stl(shell, out_dir / "earbud_shell.stl")
export_stl(cap, out_dir / "earbud_cap.stl")
print(f"Exported STL files to {out_dir}")
