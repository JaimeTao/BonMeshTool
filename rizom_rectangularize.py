# -*- coding: utf-8 -*-
"""
RizomUV-style "Rectangularize Polygons" for Maya  (Maya 2022+ / Python 3)

Reproduces

    RizomUV 2024.1  >  Straighten  >  Rectangularize Polygons              
    RizomUV 2024.1  >  Straighten  >  Rectangularize Polygons Horizontally 
    RizomUV 2024.1  >  Straighten  >  Rectangularize Polygons Vertically   

Reverse engineering summary (full trace in README.md next to this file)
----------------------------------------------------------------------
* All three entries are registered in the RizomUV UI command table
  (rizomuv.exe 2024.1.56.g5e9e9052, image base 0x140000000):
      ZOMID_RECTANGULARIZE_UI               id 0x2ED (749)  
      ZOMID_RECTANGULARIZE_VERTICALLY_UI    id 0x2F0 (752)  
      ZOMID_RECTANGULARIZE_HORIZONTALLY_UI  id 0x2F1 (753)  
  and end up in the same routine
      NZOM::NGeoTopo::Mesh::Rectangularize( CSubMesh&, vector<unsigned>&, string rule )
  (RVA 0x5D9B710, asserts "Polygons must be quad only in that method" and
  "Polygons are not connected").  The string argument is the only difference:
  "Horizontalize" / "Verticalize" / "" and it is only used to rotate the result
  by 90 degrees at the very end.
* The routine embeds the selected connected quad patch into an integer lattice,
  measures the mean edge length along both lattice directions and rebuilds the
  patch as a true rectangular grid; the centroid is preserved.

Why edge lengths and not averaged vertex projections
---------------------------------------------------
RizomUV compresses a strongly curved strip into its projected extent
(a 130 deg arc loses ~28% of its UV area, a 260 deg arc ~75%).  Averaging raw
projections reproduces that shrink but folds the strip onto itself for arcs
close to / above 180 degrees, which shows up as overlapping UVs on the two end
edges of the patch.  Building the grid from mean edge lengths keeps the strip
unfolded, keeps its UV area and matches RizomUV to ~1-2% on ordinary (mildly
distorted) grids.  This module uses the edge length construction and rescales
the result so that the total UV area of the patch is preserved.

Usage
-----
    import rizom_rectangularize as rz
    rz.rectangularize(rule="H")     # horizontal
    rz.rectangularize(rule="V")     # vertical
    rz.rectangularize(rule="N")     # rectangularize, keep fitted orientation

    rz.show_ui()                    # small window with the three buttons

Select UV faces (or whole objects) before calling.  Every patch must be made of
quads only and must be one connected quad grid in UV space.
"""

from __future__ import print_function

import math

import maya.cmds as cmds
import maya.api.OpenMaya as om

__version__ = "1.1"

RULES = ("H", "V", "N")


# --------------------------------------------------------------------------- #
#  selection
# --------------------------------------------------------------------------- #


def _mesh_shape(node):
    """Return the mesh shape below *node* (or *node* itself when it is a shape)."""
    try:
        if cmds.nodeType(node) == "mesh":
            return node
    except Exception:
        pass
    shapes = cmds.listRelatives(node, shapes=True, noIntermediate=True,
                                type="mesh", fullPath=True) or []
    return shapes[0] if shapes else None


def _parse_face_component(component):
    """'f[0:2,7]' -> [0, 1, 2, 7]"""
    body = component[component.index("[") + 1:component.rindex("]")]
    faces = []
    for part in body.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            a, b = part.split(":")
            faces.extend(range(int(a), int(b) + 1))
        else:
            faces.append(int(part))
    return faces


def _collect_targets():
    """[(shape, faces_or_None), ...] from the current selection.

    faces_or_None is None when the whole object has to be processed.
    """
    selection = cmds.ls(selection=True, long=True, flatten=True) or []
    if not selection:
        return [(s, None) for s in (cmds.ls(type="mesh", long=True, noIntermediate=True) or [])]

    order = []
    targets = {}
    for item in selection:
        node = item.split(".")[0]
        shape = _mesh_shape(node)
        if not shape:
            continue
        if shape not in targets:
            targets[shape] = None
            order.append(shape)
        if "." in item:
            comp = item.split(".", 1)[1]
            if comp.startswith("f["):
                faces = _parse_face_component(comp)
                if targets[shape] is None:
                    targets[shape] = set()
                targets[shape].update(faces)
    out = []
    for shape in order:
        faces = targets[shape]
        out.append((shape, None if faces is None else sorted(faces)))
    return out


# --------------------------------------------------------------------------- #
#  UV topology
# --------------------------------------------------------------------------- #


class _UVFace(object):
    __slots__ = ("ids", "uv")

    def __init__(self, ids, uv):
        self.ids = ids
        self.uv = uv


def _read_uv_faces(fn, faces, uvset):
    """{faceId: _UVFace} for quad faces; returns (dict, [non quad faces])."""
    out = {}
    bad = []
    for f in faces:
        if fn.polygonVertexCount(f) != 4:
            bad.append(f)
            continue
        ids = [fn.getPolygonUVid(f, k, uvset) for k in range(4)]
        uv = [fn.getPolygonUV(f, k, uvset) for k in range(4)]
        out[f] = _UVFace(ids, uv)
    return out, bad


def _edge_key(a, b):
    return (a, b) if a < b else (b, a)


def _build_adjacency(uvfaces):
    """{face: [(corner, neighbour_face, neighbour_corner), ...]}"""
    edges = {}
    for f, uvf in uvfaces.items():
        ids = uvf.ids
        for k in range(4):
            edges.setdefault(_edge_key(ids[k], ids[(k + 1) % 4]), []).append((f, k))

    adj = {}
    for f, uvf in uvfaces.items():
        ids = uvf.ids
        lst = []
        for k in range(4):
            a, b = ids[k], ids[(k + 1) % 4]
            for (g, m) in edges[_edge_key(a, b)]:
                if g == f:
                    continue
                gids = uvfaces[g].ids
                if gids[m] == b and gids[(m + 1) % 4] == a:
                    lst.append((k, g, m))
                    break
        adj[f] = lst
    return adj


def _components(uvfaces, adj):
    """Connected patches of faces (in UV space)."""
    seen = set()
    comps = []
    for f in uvfaces:
        if f in seen:
            continue
        stack = [f]
        seen.add(f)
        comp = []
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for (_k, g, _m) in adj[cur]:
                if g not in seen:
                    seen.add(g)
                    stack.append(g)
        comps.append(comp)
    return comps


# --------------------------------------------------------------------------- #
#  lattice embedding
# --------------------------------------------------------------------------- #


def _embed_lattice(comp, uvfaces, adj):
    """Assign integer (column, row) coordinates to every UV id of one patch.

    Returns (coord_by_uv, coord_by_face) or None when the patch is not a
    regular quad grid (i.e. the lattice assignment conflicts).
    """
    coord_by_uv = {}
    coord_by_face = {}

    seed = comp[0]
    base = [(0, 0), (1, 0), (1, 1), (0, 1)]
    coord_by_face[seed] = list(base)
    for k in range(4):
        coord_by_uv[uvfaces[seed].ids[k]] = base[k]

    stack = [seed]
    while stack:
        f = stack.pop()
        c = coord_by_face[f]
        for (k, g, m) in adj[f]:
            gc = [None, None, None, None]
            # the shared edge runs k -> k+1 on f and m -> m+1 (reversed) on g
            gc[m] = c[(k + 1) % 4]
            gc[(m + 1) % 4] = c[k]
            vx = c[(k + 3) % 4][0] - c[k][0]
            vy = c[(k + 3) % 4][1] - c[k][1]
            gc[(m + 2) % 4] = (gc[(m + 1) % 4][0] - vx, gc[(m + 1) % 4][1] - vy)
            gc[(m + 3) % 4] = (gc[m][0] - vx, gc[m][1] - vy)

            if g in coord_by_face:
                if coord_by_face[g] != gc:
                    return None
                continue
            coord_by_face[g] = gc
            gids = uvfaces[g].ids
            for kk in range(4):
                uid = gids[kk]
                old = coord_by_uv.get(uid)
                if old is not None and old != gc[kk]:
                    return None
                coord_by_uv[uid] = gc[kk]
            stack.append(g)

    # every face must own exactly one lattice cell
    occupied = set()
    for f in comp:
        co = [coord_by_uv[u] for u in uvfaces[f].ids]
        i0, j0 = co[0]
        rel = set((i - i0, j - j0) for (i, j) in co)
        if rel != {(0, 0), (1, 0), (1, 1), (0, 1)}:
            return None
        cell = (min(i for (i, j) in co), min(j for (i, j) in co))
        if cell in occupied:
            return None
        occupied.add(cell)
    return coord_by_uv, coord_by_face


# --------------------------------------------------------------------------- #
#  reshaping
# --------------------------------------------------------------------------- #


def _dist(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _quad_area(uv):
    """Absolute area of a (possibly non planar) UV quad, as two triangles."""
    (ax, ay), (bx, by), (cx, cy), (dx, dy) = uv
    return 0.5 * (abs((bx - ax) * (cy - ay) - (by - ay) * (cx - ax)) +
                  abs((cx - ax) * (dy - ay) - (cy - ay) * (dx - ax)))


def _reshape(comp, uvfaces, coord_by_uv, rule):
    """New UV coordinates for one patch.  Returns {uvid: (u, v)}."""
    # --- fitted frame : mean of every U edge of the patch ------------------ #
    ex = ey = 0.0
    fx = fy = 0.0
    for f in comp:
        c = uvfaces[f].uv
        ex += (c[1][0] - c[0][0]) + (c[2][0] - c[3][0])
        ey += (c[1][1] - c[0][1]) + (c[2][1] - c[3][1])
        fx += (c[2][0] - c[1][0]) + (c[3][0] - c[0][0])
        fy += (c[2][1] - c[1][1]) + (c[3][1] - c[0][1])
    ln = math.hypot(ex, ey)
    if ln < 1e-12:
        ex, ey = 1.0, 0.0
    else:
        ex, ey = ex / ln, ey / ln
    px, py = -ey, ex

    # Handedness of the (column, row) lattice in UV space.  The BFS seed can
    # produce a left handed lattice; building on it would mirror the patch.
    # Flip the row axis in that case so the result is never mirrored.
    handed = (ex * fy - ey * fx) >= 0.0

    # --- mean edge length of every lattice line ---------------------------- #
    u_len = {}
    v_len = {}
    for f in comp:
        uv = uvfaces[f].uv
        co = [coord_by_uv[x] for x in uvfaces[f].ids]
        for a, b in ((0, 1), (2, 3)):          # U edges
            ia, ja = co[a]
            ib, jb = co[b]
            if ia == ib:
                continue
            u_len.setdefault(min(ia, ib), []).append(_dist(uv[a], uv[b]))
        for a, b in ((1, 2), (3, 0)):          # V edges
            ia, ja = co[a]
            ib, jb = co[b]
            if ja == jb:
                continue
            v_len.setdefault(min(ja, jb), []).append(_dist(uv[a], uv[b]))

    if not u_len or not v_len:
        return {uid: uvfaces[comp[0]].uv[k] for k, uid in enumerate(uvfaces[comp[0]].ids)}

    flat_u = [x for lst in u_len.values() for x in lst]
    flat_v = [x for lst in v_len.values() for x in lst]
    mean_u = sum(flat_u) / len(flat_u)
    mean_v = sum(flat_v) / len(flat_v)

    cols = sorted(set(i for (i, j) in coord_by_uv.values()))
    rows = sorted(set(j for (i, j) in coord_by_uv.values()))

    def line_positions(indices, table, fallback):
        pos = {indices[0]: 0.0}
        for k in range(len(indices) - 1):
            vals = table.get(indices[k])
            step = (sum(vals) / len(vals)) if vals else fallback
            pos[indices[k + 1]] = pos[indices[k]] + step
        return pos

    U = line_positions(cols, u_len, mean_u)
    V = line_positions(rows, v_len, mean_v)
    if not handed:
        V = {j: -v for j, v in V.items()}

    width = U[cols[-1]] - U[cols[0]]
    height = V[rows[-1]] - V[rows[0]]

    uc = 0.5 * (U[cols[0]] + U[cols[-1]])
    vc = 0.5 * (V[rows[0]] + V[rows[-1]])
    grid = {uid: (U[i] - uc, V[j] - vc) for uid, (i, j) in coord_by_uv.items()}

    # --- orientation -------------------------------------------------------- #
    if rule == "N":
        out = {uid: (u * ex + v * px, u * ey + v * py) for uid, (u, v) in grid.items()}
    elif rule == "H":
        if width >= height:
            out = dict(grid)
        else:
            out = {uid: (v, -u) for uid, (u, v) in grid.items()}
    else:  # "V"
        if height >= width:
            out = dict(grid)
        else:
            out = {uid: (-v, u) for uid, (u, v) in grid.items()}

    # --- keep the UV area (texel density) of the patch --------------------- #
    a_in = sum(_quad_area(uvfaces[f].uv) for f in comp)
    a_out = abs(width * height)
    if a_in > 1e-12 and a_out > 1e-12:
        s = math.sqrt(a_in / a_out)
        s = min(max(s, 0.2), 5.0)
        if abs(s - 1.0) > 1e-4:
            out = {uid: (p[0] * s, p[1] * s) for uid, p in out.items()}

    # --- put the patch back on its original centroid ----------------------- #
    orig = {}
    for f in comp:
        ids = uvfaces[f].ids
        uvs = uvfaces[f].uv
        for k in range(4):
            if ids[k] not in orig:
                orig[ids[k]] = uvs[k]
    ox = sum(p[0] for p in orig.values()) / len(orig)
    oy = sum(p[1] for p in orig.values()) / len(orig)
    cx = sum(p[0] for p in out.values()) / len(out)
    cy = sum(p[1] for p in out.values()) / len(out)
    return {uid: (p[0] - cx + ox, p[1] - cy + oy) for uid, p in out.items()}


# --------------------------------------------------------------------------- #
#  per object processing
# --------------------------------------------------------------------------- #


def _process_shape(shape, faces, rule):
    """Returns (patches_done, patches_skipped)."""
    if not cmds.polyEvaluate(shape, face=True):
        return 0, 0
    uvset = cmds.polyUVSet(shape, query=True, currentUVSet=True)[0]
    fn = om.MFnMesh(om.MGlobal.getSelectionListByName(shape).getDependNode(0))

    if faces is None:
        faces = list(range(fn.numPolygons))
    faces = [f for f in faces if 0 <= f < fn.numPolygons]
    if not faces:
        return 0, 0

    uvfaces, bad = _read_uv_faces(fn, faces, uvset)
    if bad:
        cmds.warning("Rectangularize: %d non-quad face(s) skipped on '%s' "
                     "(RizomUV: 'Polygons must be quad only in that method')."
                     % (len(bad), shape))
    if not uvfaces:
        return 0, 0

    adj = _build_adjacency(uvfaces)
    done = skipped = 0
    for comp in _components(uvfaces, adj):
        emb = _embed_lattice(comp, uvfaces, adj)
        if emb is None:
            cmds.warning("Rectangularize: a patch on '%s' is not a connected quad grid "
                         "(RizomUV: 'Polygons are not connected') - skipped." % shape)
            skipped += 1
            continue
        new = _reshape(comp, uvfaces, emb[0], rule)
        for uid, (u, v) in new.items():
            fn.setUV(uid, u, v, uvset)
        fn.updateSurface()
        done += 1
    return done, skipped


def rectangularize(rule="H", faces=None, objects=None):
    """Rectangularize selected (or given) UV quads.

    rule    : "H" horizontal, "V" vertical, "N" keep the fitted orientation
    faces   : optional {object_or_shape: [face ids] or None} mapping that
              overrides the selection
    objects : optional list of objects to process instead of the selection
    """
    rule = rule.upper()
    if rule not in RULES:
        raise ValueError("rule must be one of %s" % (RULES,))

    if faces is None and objects is None:
        targets = _collect_targets()
    else:
        if objects is None:
            objects = list(faces.keys())
        targets = []
        for obj in objects:
            shape = _mesh_shape(obj)
            if shape:
                targets.append((shape, None if faces is None else faces.get(obj)))

    done = skipped = 0
    cmds.undoInfo(openChunk=True, chunkName="UV矩形化")
    try:
        for shape, face_list in targets:
            d, s = _process_shape(shape, face_list, rule)
            done += d
            skipped += s

        cmds.refresh(force=True)
        if done == 0:
            cmds.warning("Rectangularize: nothing to do (need selected quads forming a quad grid).")
        return done
    finally:
        cmds.undoInfo(closeChunk=True)


def rectangularize_horizontal(*args):
    return rectangularize("H")


def rectangularize_vertical(*args):
    return rectangularize("V")


def rectangularize_natural(*args):
    return rectangularize("N")


def diagnose_selection():
    """Print a report about the selected UVs (why a patch is skipped, areas...).

    Returns a list of dicts with the collected facts.  Run it before
    rectangularize() when the result is not what you expect.
    """
    report = []
    for shape, faces in _collect_targets():
        if not cmds.polyEvaluate(shape, face=True):
            continue
        uvset = cmds.polyUVSet(shape, query=True, currentUVSet=True)[0]
        fn = om.MFnMesh(om.MGlobal.getSelectionListByName(shape).getDependNode(0))
        all_faces = list(range(fn.numPolygons)) if faces is None else faces
        uvfaces, bad = _read_uv_faces(fn, all_faces, uvset)
        adj = _build_adjacency(uvfaces)
        comps = _components(uvfaces, adj) if uvfaces else []
        print("mesh %s  uv set '%s'" % (shape, uvset))
        print("  faces selected/used : %d  (quads %d, non quad %d)"
              % (len(all_faces), len(uvfaces), len(bad)))
        for idx, comp in enumerate(comps):
            emb = _embed_lattice(comp, uvfaces, adj)
            area = sum(_quad_area(uvfaces[f].uv) for f in comp)
            print("  patch %d: %d quad(s), UV area %.6f, %s"
                  % (idx, len(comp), area,
                     "quad grid OK" if emb else "NOT a regular quad grid -> skipped"))
            report.append({'shape': shape, 'patch': idx, 'quads': len(comp),
                           'area': area, 'grid': emb is not None})
        if bad:
            print("  ! %d non-quad face(s) are ignored (RizomUV also refuses them)" % len(bad))
    if not report:
        print("diagnose_selection: nothing found (select UV faces or objects first).")
    return report


# --------------------------------------------------------------------------- #
#  UI
# --------------------------------------------------------------------------- #

_WIN = "rizomRectangularizeWin"


def show_ui(*args):
    if cmds.window(_WIN, exists=True):
        cmds.deleteUI(_WIN)

    cmds.window(_WIN, title="UV矩形化", widthHeight=(320, 168),
                sizeable=False)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=6, columnAttach=("both", 8))

    cmds.text(label="UV矩形化",
              font="smallObliqueLabelFont", align="left")
    cmds.separator(height=6, style="in")

    cmds.button(label="水平矩形化",
                height=32, command=rectangularize_horizontal)
    cmds.button(label="垂直矩形化",
                height=32, command=rectangularize_vertical)
    cmds.button(label="自然矩形化",
                height=26, command=rectangularize_natural)

    cmds.separator(height=4, style="none")
    cmds.text(label="选择 UV 面或整个物体（仅支持四边面组成的连续网格）。",
              font="smallObliqueLabelFont", align="left")

    cmds.showWindow(_WIN)
    return _WIN


if __name__ == "__main__":
    show_ui()
