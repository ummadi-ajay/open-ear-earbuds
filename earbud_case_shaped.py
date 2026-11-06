"""Round shaped storage case for the compact open-ear earbuds (clamshell: base + lid).

Pure numpy/scipy/scikit-image (no Blender): the case is built as voxel volumes from the real
earbud STL meshes, then meshed with marching cubes.
Usage: python3 case_vox.py <stl_dir> <out_dir>
Pockets follow the real pod + arm + cap, grown by CLEAR. A wire channel runs from each cap to a
cable spool (trench around a post) in the middle. Lid and base meet with a lip/groove.
"""
import math
import struct
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from skimage import measure

stl_dir, out_dir = Path(sys.argv[1]), Path(sys.argv[2])

# ---- Settings (mm) ----
H = 0.5                # voxel size of the case (0.35 is finer but the files get too big)
CLEAR = 1.0            # pocket clearance around the pod and cap (printed parts vary by about 0.2-0.3 mm)
CLEAR_ARM = 1.8        # extra room around the arm and end ball, so they drop in and lift out easily
MARGIN = 1.6           # wall between a pocket and the outside
FLOOR = 1.6            # floor / ceiling beyond the deepest part of the pockets
CORNER = 7.0           # plan corner radius
EDGE = 2.0             # outer edge rounding (soft, smooth edges)
LIP_ON = False         # True adds a lip-and-groove ring that locates the lid (leaves visible ring lines)
SCOOP_ON = False       # True adds a thumb scoop at the front edge
RW = 18.0              # round reel well radius in the middle of the case
WELL_W, WELL_L = 2 * RW, 2 * RW
REEL_CLEAR = 0.8       # gap between the reel flanges and the well wall
DRUM_R = 7.0           # drum the cable winds around
FLANGE_T = 1.6         # reel flange thickness
PIN_R, BORE_R = 2.5, 3.1                 # axle pin on the base and the bore in the reel (0.6 mm to spare)
STEM_R, STEM_H = 2.7, 3.0                # stem on the drum that the knob part presses onto
KNOB_R, HOLE_CLEAR = 15.0, 0.6           # turning disc radius that passes through the lid, gap in the lid hole
DISC_PROUD = -0.2                       # disc top stands this far above the lid
FH_D, FH_SPACING, FH_Y, FH_FLOOR = 13.0, 14.0, 0.0, 2.2
PEG_R, PEG_Y, PEG_H = 1.6, 4.8, 2.0          # two drive pegs on the drum that lock into the disc (the centre is free for the finger holes)   # two finger holes: diameter, centre distance, floor depth below the lid top
BAR_H, BAR_GAP = 0.0, 0.0
SLOT_W, SLOT_D = 2.2, 2.5                # two pinch slots on the drum for the cable ends
CABLE_D = 2.5          # cable diameter used to size the spool
CABLE_CM = 80          # length of each cable (cm); the spool is sized for one per earbud
LID_EXTRA = 1.0        # extra room above the pods on the lid side
LID_MIN = 6.0          # minimum lid depth (more room above the pods, and for the cable)
ARM_LID_DEPTH = 2.4     # matching recess in the lid above each arm channel, so the arms are held down when it is closed
LOGO_LINES = [("MAKERWORKSLAB", 88.0, None)]   # (text, width mm, centre y mm or None = in the logo strip of the pill case)
LIGHTEN = True         # hollow the underside of the base: leaves a thin wall around every pocket and a rib grid, open at the bottom
WALL_T = 1.2           # wall thickness left around the pockets and the outside
RIB_PITCH, RIB_W = 16.0, 1.6   # rib grid spacing and thickness
SKIN_B = 0.6           # flat skin kept on the bottom, so the underside is smooth
SKIN_T = 2.0           # flat skin kept on top of the lid
PILL = True            # slim oblong plan (rounded rectangle) instead of a round plan: about 40% less plastic
PILL_R = 14.0          # plan corner radius of the oblong case
STRIP_PAD = 1.8        # gap between the pockets and the logo strip, and below the logo   # (text, width mm, centre y mm): engraved on top of the lid, in the empty area in front of the pockets
LOGO_DEPTH = 0.8       # engraving depth into the lid top
PACK = 0.55            # how tightly a loose cable winding fills the trench
WIRE_D = 5.0           # wire channel diameter (cable plus the cap's strain-relief knot)
EXIT_D = 6.0           # slot where the single cable leaves the case
LIP_W, LIP_H, LIP_FIT = 1.2, 1.6, 0.25     # lid lip thickness, height, groove clearance
CAP_BACK = 10.9        # shell depth + cap plate: the back of the cap in shell coordinates
WALL_WELL = 1.5        # wall between the spool trench and a pocket


def load_tris(p):
    b = Path(p).read_bytes()
    n = struct.unpack("<I", b[80:84])[0]
    d = np.frombuffer(b[84:84 + 50 * n], dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]))
    return d["v"].astype(np.float64)


def rot_y(deg):
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def subdivide(tri, max_edge):
    while True:
        e = np.stack([np.linalg.norm(tri[:, 1] - tri[:, 0], axis=1),
                      np.linalg.norm(tri[:, 2] - tri[:, 1], axis=1),
                      np.linalg.norm(tri[:, 0] - tri[:, 2], axis=1)]).max(0)
        big = e > max_edge
        if not big.any():
            return tri
        t = tri[big]
        a, b, c = t[:, 0], t[:, 1], t[:, 2]
        ab, bc, ca = (a + b) / 2, (b + c) / 2, (c + a) / 2
        new = np.concatenate([np.stack([a, ab, ca], 1), np.stack([ab, b, bc], 1),
                              np.stack([ca, bc, c], 1), np.stack([ab, bc, ca], 1)])
        tri = np.concatenate([tri[~big], new])


# ---- Orient each earbud to lie flat (minimum height) ----
ears = {}
for side in ("left", "right"):
    tri = load_tris(stl_dir / f"earbud_shell_compact_{side}.stl")
    v = tri.reshape(-1, 3)
    best = min(((((v @ rot_y(d).T)[:, 2].max() - (v @ rot_y(d).T)[:, 2].min()), d) for d in np.arange(-90, 90.5, 1.0)))
    R = rot_y(best[1])
    arm_pts = v[np.hypot(v[:, 0], v[:, 1]) > 9.4]            # shell-local points beyond the pod radius: arm and ball
    arm_zmax = (arm_pts @ R.T)[:, 2].max()
    pts = v @ R.T
    lo, hi = pts.min(0), pts.max(0)
    ears[side] = dict(tri=tri, R=R, deg=best[1], lo=lo, hi=hi, c=(lo + hi) / 2, size=hi - lo, arm_zmax=arm_zmax,
                      back=R @ np.array([0, 0, 1.0]), cap=R @ np.array([0, 0, CAP_BACK]))
    print(side, "lies flat at", best[1], "deg: size", np.round(hi - lo, 1), "back dir", np.round(R @ np.array([0, 0, 1.0]), 2))

# ---- Layout ----
half_w = max(e["size"][0] for e in ears.values()) / 2 + CLEAR_ARM
x_off = WELL_W / 2 + WALL_WELL + half_w
L_est = max(max(e["size"][1] for e in ears.values()) + 2 * CLEAR_ARM, WELL_L + 5)
R_est = math.hypot(x_off + half_w, L_est / 2) + 2.0
# Parting plane: just above the arm, so the whole arm lies in the base and the lid covers the pod tops.
for e in ears.values():
    e["dz"] = -(e["arm_zmax"] + CLEAR_ARM)
    e["zmin"], e["zmax"] = e["lo"][2] + e["dz"], e["hi"][2] + e["dz"]
Hb = max(-e["zmin"] for e in ears.values()) + CLEAR + FLOOR     # base depth below the plane
Hl = max(max(e["zmax"] for e in ears.values()) + CLEAR + LID_EXTRA + FLOOR, LID_MIN)   # lid depth above the plane
Hh = max(Hb, Hl)
zfloor, zceil = -Hb + FLOOR * 0.8, Hl - FLOOR * 0.8          # bottom and top of the reel well
rz0, rz1 = zfloor + 0.6, zceil - 0.6                          # reel sits 0.6 mm clear of the floor and the ceiling
RF = RW - REEL_CLEAR                                          # flange radius
pin_top = rz1 - FLANGE_T - 2.0 - 0.6                          # pin stops 0.6 mm below the top of the bore
print("base depth %.1f mm, lid depth %.1f mm" % (Hb, Hl))

# ---- Grid (generous; the case radius is found from the contents below) ----
pad = 3 * H
nxy = int(math.ceil((R_est + pad) / H))
xs = np.arange(-nxy, nxy + 1) * H          # symmetric about 0, so the lid can be flipped exactly
ys = xs.copy()
nz = int(math.ceil((Hh + pad) / H))
zs = np.arange(-nz, nz + 1) * H
X, Y, Z = xs[:, None, None], ys[None, :, None], zs[None, None, :]
shape = (len(xs), len(ys), len(zs))
print("grid", shape)


def idx(p):
    return np.stack([np.floor((p[:, 0] - xs[0]) / H + 0.5), np.floor((p[:, 1] - ys[0]) / H + 0.5),
                     np.floor((p[:, 2] - zs[0]) / H + 0.5)], 1).astype(int)


def rr(x, y, hw, hl, r):
    qx, qy = np.abs(x) - (hw - r), np.abs(y) - (hl - r)
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r


# ---- Pockets (real earbud shapes: pod grown by CLEAR, arm and end ball by CLEAR_ARM) ----
pockets = np.zeros(shape, bool)
pockets_lid = np.zeros(shape, bool)          # lid side gets a bit more room above the pods
ear_solid = np.zeros(shape, bool)
arm_pocket = np.zeros(shape, bool)
wires = []
for side, e in ears.items():
    sx = -1 if e["back"][0] > 0 else 1            # earbud's back (cable end) faces the spool
    tr = np.array([sx * x_off - e["c"][0], -e["c"][1], e["dz"]])
    tri = subdivide(e["tri"] @ e["R"].T + tr, H * 0.5)
    S = np.zeros(shape, bool)
    ij = idx(tri.reshape(-1, 3))
    S[ij[:, 0], ij[:, 1], ij[:, 2]] = True
    S = ndi.binary_dilation(S)
    P = np.stack(np.broadcast_arrays(X - tr[0], Y - tr[1], Z - tr[2]), -1)
    loc = P @ e["R"]
    del P
    r2 = loc[..., 0] ** 2 + loc[..., 1] ** 2
    S |= (r2 <= 8.0 ** 2) & (loc[..., 2] >= 0.9) & (loc[..., 2] <= 9.6)
    S |= (r2 <= 8.5 ** 2) & (loc[..., 2] >= 9.4) & (loc[..., 2] <= CAP_BACK)
    solid = ndi.binary_erosion(ndi.binary_fill_holes(S))
    dist = ndi.distance_transform_edt(~solid, sampling=H)
    ear_solid |= solid
    arm_zone = r2 > 9.4 ** 2          # outside the pod's own radius: the arm and the end ball
    pockets |= (dist <= CLEAR) | ((dist <= CLEAR_ARM) & arm_zone)
    pockets_lid |= (dist <= CLEAR + LID_EXTRA) | ((dist <= CLEAR_ARM) & arm_zone)
    arm_pocket |= (dist <= CLEAR_ARM) & arm_zone
    wires.append(e["cap"] + tr)
    del loc, r2, S, dist
    print(side, "solid vol mm3", round(solid.sum() * H ** 3))

# ---- Cable spool, wire channels, cable exit ----
well = (np.hypot(X, Y) <= RW) & (Z >= zfloor) & (Z <= zceil)
wire = np.zeros(shape, bool)
for wx, wy, wz in wires:
    xe = -math.copysign(RW - 1.0, wx)              # ends inside the reel well, between the flanges
    x0, x1 = sorted((wx, xe))
    open_up = (np.abs(Y - wy) <= WIRE_D / 2) & (Z >= min(0.0, wz)) & (Z <= max(0.0, wz))
    wire |= (((Y - wy) ** 2 + (Z - wz) ** 2 <= (WIRE_D / 2) ** 2) | open_up) & (X >= x0) & (X <= x1)

# the round case: radius from the contents plus the wall
content = pockets_lid | pockets | well | wire
rad = np.hypot(X, Y) + 0 * Z
Rc = float(rad[content].max()) + MARGIN
cyy = (Y + 0 * X + 0 * Z)[content]
cxx = np.abs(X + 0 * Y + 0 * Z)[content]
c_ymin, c_ymax, c_xmax = float(cyy.min()), float(cyy.max()), float(cxx.max())
LOGO_H = 7.0                                    # engraved line height (set again from the real text below)
logo_cy = c_ymin - STRIP_PAD - LOGO_H / 2
if PILL:
    p_xmax = c_xmax + MARGIN
    p_ymax = c_ymax + MARGIN
    p_ymin = logo_cy - LOGO_H / 2 - STRIP_PAD - 0.8
    p_yc, p_hl = (p_ymax + p_ymin) / 2, (p_ymax - p_ymin) / 2
    Rc = p_ymax - 0.0
    print("slim oblong case %.1f x %.1f mm, height %.1f mm (base %.1f + lid %.1f)" % (2 * p_xmax, 2 * p_hl, Hb + Hl, Hb, Hl))
else:
    print("case diameter %.1f mm, height %.1f mm (base %.1f + lid %.1f)" % (2 * Rc, Hb + Hl, Hb, Hl))
exit_slot = ((X ** 2 + Z ** 2) <= (EXIT_D / 2) ** 2) & (Y >= WELL_L / 2 - 4) & (Y <= Rc + 2)
chan_h = (rz1 - FLANGE_T) - (rz0 + FLANGE_T)
chan_vol = math.pi * (RF ** 2 - DRUM_R ** 2) * chan_h
cap_mm = chan_vol * 0.7 / (math.pi / 4 * CABLE_D ** 2)          # a neatly wound reel packs about 70%
need_mm = 2 * CABLE_CM * 10
print("reel winds about %.0f cm of %.1f mm cable (needs %.0f cm for 2 x %d cm)" % (cap_mm / 10, CABLE_D, need_mm / 10, CABLE_CM))
for (wx, wy, wz), side in zip(wires, ears):
    print(side, "cable enters at z=%.1f; reel winding space is z=%.1f to %.1f: %s" % (wz, rz0 + FLANGE_T, rz1 - FLANGE_T, "OK" if rz0 + FLANGE_T < wz < rz1 - FLANGE_T else "OUTSIDE"))

# ---- Case volumes (round, edges rounded) ----
a = (rr(X, Y - p_yc, p_xmax, p_hl, PILL_R) if PILL else np.hypot(X, Y) - Rc) + EDGE
b = np.abs(Z - (Hl - Hb) / 2) - (Hl + Hb) / 2 + EDGE
block = (np.hypot(np.maximum(a, 0), np.maximum(b, 0)) + np.minimum(np.maximum(a, b), 0) - EDGE) <= 0

ring = lambda grow: (np.hypot(X, Y) <= Rc - 1.6 + grow) & (np.hypot(X, Y) > Rc - 1.6 - LIP_W - grow)
lip = ring(0) & (Z > 0) & (Z <= LIP_H) & LIP_ON
groove = ring(LIP_FIT) & (Z >= 0) & (Z <= LIP_H + 0.3) & LIP_ON
scoop = ((X ** 2 + (Y + Rc - 0.5) ** 2 + Z ** 2) <= 6.0 ** 2) & SCOOP_ON


def text_mask(text, width, cy):
    """Bold text as a 2D mask over the (x, y) grid, centred at x=0, y=cy, reading left to right with +y up."""
    from PIL import Image, ImageDraw, ImageFont
    font = None
    for f in ("Poppins-Bold.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf", "LiberationSans-Bold.ttf"):
        try:
            font = ImageFont.truetype(f, 200)
            break
        except OSError:
            continue
    if font is None:
        for p in ("/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
            if Path(p).exists():
                font = ImageFont.truetype(p, 200)
                break
    if font is None:
        print("no bold font found: skipping the engraving")
        return np.zeros((len(xs), len(ys)), bool)
    l, t, r, b = font.getbbox(text)
    img = Image.new("L", (r - l + 8, b - t + 8), 0)
    ImageDraw.Draw(img).text((4 - l, 4 - t), text, fill=255, font=font)
    a = np.asarray(img) > 128
    ppm = a.shape[1] / width                         # pixels per mm
    hmm = a.shape[0] / ppm
    px = ((xs + width / 2) * ppm).astype(int)
    py = ((cy + hmm / 2 - ys) * ppm).astype(int)
    ok_x, ok_y = (px >= 0) & (px < a.shape[1]), (py >= 0) & (py < a.shape[0])
    m = np.zeros((len(xs), len(ys)), bool)
    m[np.ix_(ok_x, ok_y)] = a[py[ok_y][None, :], px[ok_x][:, None]]
    print("logo text %s: %.0f x %.1f mm" % (text, width, hmm))
    return m


logo_2d = np.zeros((len(xs), len(ys)), bool)
for _t, _w, _y in LOGO_LINES:
    logo_2d |= text_mask(_t, _w, logo_cy if _y is None else _y)
logo = logo_2d[:, :, None] & (Z >= Hl - LOGO_DEPTH)

# Make every pocket drop-in: in each half, cut straight up to the parting plane above the deepest point of
# the pocket in that column. Without this the opening at the plane can be narrower than the arm
# (the arm tube lies below the plane), and the earbud could not be lowered in.
zi = np.arange(shape[2])[None, None, :]
pb = pockets & (Z <= 0)
first = np.argmax(pb, axis=2)
pocket_base = pb.any(2)[:, :, None] & (zi >= first[:, :, None]) & (Z <= 0)
pl = pockets_lid & (Z >= 0)
last = shape[2] - 1 - np.argmax(pl[:, :, ::-1], axis=2)
pocket_lid = pl.any(2)[:, :, None] & (zi <= last[:, :, None]) & (Z >= 0)
# matching recess in the lid straight above each arm channel and the end ball
pocket_lid |= arm_pocket.any(2)[:, :, None] & (Z >= 0) & (Z <= ARM_LID_DEPTH)
other = well | wire | exit_slot
base = ((block & (Z <= 0)) | lip) & ~(pocket_base | other) & ~scoop
lid = (block & (Z >= 0)) & ~groove & ~(pocket_lid | other)
lid &= ~((np.hypot(X, Y) <= KNOB_R + HOLE_CLEAR) & (Z >= zceil - 0.1))          # hole the reel knob comes up through
base |= (np.hypot(X, Y) <= PIN_R) & (Z >= zfloor - 0.5) & (Z <= pin_top)          # axle pin the reel turns on
cols = logo.any(2)
under = (np.abs(Z - (Hl - LOGO_DEPTH - 1.0)) <= H / 2) & cols[:, :, None]       # 1 mm below the engraving floor
print("logo: %d voxels engraved; lettering touches a pocket or channel: %d; solid lid material 1 mm below the letters: %.0f%%" % (
    int(logo.sum()), int((logo & (pocket_lid | other)).sum()), 100 * (lid & under).sum() / max(under.sum(), 1)))
lid = lid & ~logo
base_cav = lid_cav = None
if LIGHTEN:
    first_b = np.argmax(base, axis=2)
    below = (np.arange(shape[2])[None, None, :] < first_b[:, :, None]) & base.any(2)[:, :, None]
    ed = ndi.distance_transform_edt(base | below, sampling=H)          # the bottom face does not count as a wall
    ribs = (np.abs(((X + RIB_PITCH / 2) % RIB_PITCH) - RIB_PITCH / 2) <= RIB_W / 2) | (np.abs(((Y + RIB_PITCH / 2) % RIB_PITCH) - RIB_PITCH / 2) <= RIB_W / 2)
    zbot = (np.where(base.any(2), first_b, 0) * H)[:, :, None] + zs[0] + SKIN_B     # skin top, per column
    cavity = base & (ed >= WALL_T) & ~ribs & (Z >= zbot)
    v0 = int(base.sum())
    base = base & ~cavity
    base_cav = cavity
    print("lightening: removed %.0f cm3 from the base (%.0f%% of it)" % (cavity.sum() * H ** 3 / 1000, 100 * cavity.sum() / v0))
    edl = ndi.distance_transform_edt(lid, sampling=H)
    cav_l = lid & (edl >= WALL_T) & ~ribs
    v1 = int(lid.sum())
    lid = lid & ~cav_l
    lid_cav = cav_l
    print("lightening: removed %.0f cm3 from the lid (%.0f%% of it)" % (cav_l.sum() * H ** 3 / 1000, 100 * cav_l.sum() / v1))

# Insertion check: lowering the real earbud straight down into the base (and the lid straight onto it)
# must not hit any material.
eb = ear_solid & (Z <= 0)
first_e = np.argmax(eb, axis=2)
sweep_down = eb.any(2)[:, :, None] & (zi >= first_e[:, :, None])            # from its lowest point up and out
el = ear_solid & (Z >= 0)
last_e = shape[2] - 1 - np.argmax(el[:, :, ::-1], axis=2)
sweep_up = el.any(2)[:, :, None] & (zi <= last_e[:, :, None])                # from its highest point down to the plane
print("insertion check: base voxels in the way of the earbuds:", int((sweep_down & (Z <= 0) & base).sum()),
      "| lid voxels in the way:", int((sweep_up & (Z >= 0) & lid).sum()))

closed = base | lid
lab, _ = ndi.label(~closed)
outside = lab[0, 0, 0]
for (wx, wy, wz), side in zip(wires, ears):
    i, j, k = idx(np.array([[wx, wy, wz]]))[0]
    print(side, "cap cable exit connects to the outside:", bool(lab[i, j, k] == outside))


def reel_masks(Xg, Yg, Zg):
    r = np.hypot(Xg, Yg)
    # part A: bottom flange, drum, stem, bore, two pinch slots
    A = (r <= RF) & (Zg >= rz0) & (Zg <= rz0 + FLANGE_T)
    A |= (r <= DRUM_R) & (Zg >= rz0) & (Zg <= rz1 - FLANGE_T)
    for sgn in (1, -1):
        A |= (np.hypot(Xg, Yg - sgn * PEG_Y) <= PEG_R) & (Zg > rz1 - FLANGE_T) & (Zg <= rz1 - FLANGE_T + PEG_H)
    A &= ~((r <= BORE_R) & (Zg <= rz1 - FLANGE_T - 2.0))
    for sgn in (1, -1):
        A &= ~((np.abs(Yg) <= SLOT_W / 2) & (sgn * Xg >= DRUM_R - SLOT_D) & (sgn * Xg <= DRUM_R + 0.2)
               & (Zg > rz0 + FLANGE_T) & (Zg < rz1 - FLANGE_T))
    # part B: a flat disc with two finger holes (put two fingers in the holes and turn); flange underneath keeps it in the lid
    ztop = Hl + DISC_PROUD
    B = (r <= RF) & (Zg >= rz1 - FLANGE_T) & (Zg <= rz1)
    B |= (r <= KNOB_R) & (Zg > rz1) & (Zg <= ztop)
    e = 1.0                                            # soft rounded top edge
    cut = (r > KNOB_R - e) & (Zg > ztop - e) & ((r - (KNOB_R - e)) ** 2 + (Zg - (ztop - e)) ** 2 > e ** 2)
    B &= ~cut
    for sgn in (1, -1):                                # finger holes: round, blind, soft rim
        hr = np.hypot(Xg - sgn * FH_SPACING / 2, Yg - FH_Y)
        B &= ~((hr <= FH_D / 2) & (Zg >= Hl - FH_FLOOR))
    for sgn in (1, -1):
        B &= ~((np.hypot(Xg, Yg - sgn * PEG_Y) <= PEG_R + 0.15) & (Zg <= rz1 - FLANGE_T + PEG_H + 0.3))
    return A, B


reel_A, reel_B = reel_masks(X, Y, Z)
print("assembly check (reel against case): overlap voxels reel A: %d, reel B: %d" % (
    int((reel_A & (base | lid)).sum()), int((reel_B & (base | lid)).sum())))
lid_cav = lid_cav[::-1, :, ::-1] if lid_cav is not None else None
lid = lid[::-1, :, ::-1]         # turn the lid over about the Y axis (a true rotation, not a mirror): open side up for printing


def write_stl(path, verts, faces):
    tri = verts[faces]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    rec = np.zeros(len(tri), dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]))
    rec["n"], rec["v"] = n, tri
    with open(path, "wb") as f:
        f.write(b"case".ljust(80, b"\0"))
        f.write(struct.pack("<I", len(tri)))
        f.write(rec.tobytes())


def surface(mask, h, step=1):
    m = np.pad(mask, 2)
    f = ndi.distance_transform_edt(m, sampling=h) - ndi.distance_transform_edt(~m, sampling=h)
    f = ndi.gaussian_filter(f, 0.6)
    v, fc, _, _ = measure.marching_cubes(f, 0.0, spacing=(h, h, h), step_size=step)
    v -= 2 * h
    t = v[fc]
    vol = np.einsum("ij,ij->i", t[:, 0], np.cross(t[:, 1], t[:, 2])).sum() / 6
    if vol < 0:
        fc = fc[:, ::-1]
        vol = -vol
    return v, fc, vol


def mesh(mask, name, h=None, origin=None, voids=None):
    """Outer surface at full detail. Hidden internal cells (voids) are meshed coarser, as separate inward-facing shells."""
    h = h or H
    full = mask | voids if voids is not None else mask
    v, fc, vol = surface(full, h)
    if voids is not None and voids.any():
        vv, fv, volv = surface(ndi.binary_erosion(voids), h, step=2)     # one voxel smaller, so the walls never get thinner
        fc = np.concatenate([fc, fv[:, ::-1] + len(v)])
        v = np.concatenate([v, vv])
        vol -= volv
    lo = np.array(origin) if origin is not None else np.array([xs[0], ys[0], zs[0]])
    z_low = lo[2] + np.argwhere(full)[:, 2].min() * h
    v = v + lo
    v[:, 2] -= z_low
    write_stl(out_dir / name, v, fc)
    print(name, len(fc), "tris, volume %.0f mm3, size" % vol, np.round(v.max(0) - v.min(0), 1))


if len(sys.argv) > 3:
    np.save(sys.argv[3] + "_base.npy", base)
    np.save(sys.argv[3] + "_lid.npy", lid)
    np.save(sys.argv[3] + "_reelA.npy", reel_A)
    np.save(sys.argv[3] + "_reelB.npy", reel_B)
mesh(base, "earbud_case_shaped_base.stl", voids=base_cav)
mesh(lid, "earbud_case_shaped_lid.stl", voids=lid_cav)

# Reel parts on a finer grid (the fit between pin, bore and stem matters more than on the case)
h2 = 0.25
gx = np.arange(-RF - 1, RF + 1 + h2 / 2, h2)
gz = np.arange(rz0 - 1, Hl + DISC_PROUD + 1 + h2 / 2, h2)
GX, GY, GZ = gx[:, None, None], gx[None, :, None], gz[None, None, :]
A2, B2 = reel_masks(GX, GY, GZ)
org = (gx[0], gx[0], gz[0])
mesh(A2, "earbud_reel_drum.stl", h2, org)
mesh(B2, "earbud_reel_knob.stl", h2, org)
