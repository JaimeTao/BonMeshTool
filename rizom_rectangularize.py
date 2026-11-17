# -*- coding: utf-8 -*-
"""
UV拉直工具 (UV Straighten Tool) for Maya 2018 and newer  (Python 2.7 / 3.x)

Rebuilds a connected patch of UV quads as a regular rectangular grid:

    Horizontal   水平拉直 - long side of the patch along U
    Vertical     垂直拉直 - long side of the patch along V
    Natural      自然拉直 - keep the fitted orientation of the patch

The grid is built from the mean edge length of every lattice line, so strongly
curved strips stay unfolded instead of folding onto themselves.  The UV area
and the centroid of each patch are preserved.

Every patch must be made of quads only and must be one connected quad grid in
UV space; other patches are skipped with a warning.

Usage
-----
Drag this single .py file into a Maya viewport to install it.  The installer
copies the file to Maya's user scripts directory and adds a button to the
currently active shelf.  Clicking that shelf button reloads this module and
opens the tool window.

Window buttons: click to run; Ctrl+Shift+click to add the action to the
active shelf; middle-mouse drag to copy the native shelf button to a shelf.

Keep editing the file you dropped: the shelf button copies it into Maya's
scripts directory again before importing it, so the installed copy never goes
stale and the tool never has to be re-installed.

    import maya_uv_straighten as uvr
    uvr.rectangularize(rule="H")     # 水平拉直
    uvr.rectangularize(rule="V")     # 垂直拉直
    uvr.rectangularize(rule="N")     # 自然拉直

    uvr.show_ui()                    # small window with the three buttons

Select UV faces (or whole objects) before calling.
"""

from __future__ import print_function

import math
import os
import shutil
import sys
import importlib

import maya.cmds as cmds
import maya.mel as mel
import maya.api.OpenMaya as om

__version__ = "1.9.1"

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
        # A polygon's first corner need not be the cell's lower-left corner.
        i0 = min(i for (i, j) in co)
        j0 = min(j for (i, j) in co)
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
        co = [coord_by_uv[uid] for uid in uvfaces[f].ids]
        # Orient each edge by the shared lattice, not local corner numbers.
        for a in range(4):
            b = (a + 1) % 4
            di = co[b][0] - co[a][0]
            dj = co[b][1] - co[a][1]
            dx = c[b][0] - c[a][0]
            dy = c[b][1] - c[a][1]
            if di:
                ex += dx * di
                ey += dy * di
            else:
                fx += dx * dj
                fy += dy * dj
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
        for a in range(4):
            b = (a + 1) % 4
            ia, ja = co[a]
            ib, jb = co[b]
            if ja == jb and ia != ib:
                u_len.setdefault(min(ia, ib), []).append(_dist(uv[a], uv[b]))
            elif ia == ib and ja != jb:
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

    width = abs(U[cols[-1]] - U[cols[0]])
    height = abs(V[rows[-1]] - V[rows[0]])

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


def _mesh_fn(shape):
    """MFnMesh for *shape* through the API 2.0 selection list.

    MSelectionList works on every Maya version that has API 2.0 (2016+), while
    MGlobal.getSelectionListByName is only available on newer ones.
    """
    selection = om.MSelectionList()
    selection.add(shape)
    return om.MFnMesh(selection.getDependNode(0))


def _process_shape(shape, faces, rule):
    """Returns (patches_done, patches_skipped)."""
    if not cmds.polyEvaluate(shape, face=True):
        return 0, 0
    uvset = cmds.polyUVSet(shape, query=True, currentUVSet=True)[0]
    fn = _mesh_fn(shape)

    if faces is None:
        faces = list(range(fn.numPolygons))
    faces = [f for f in faces if 0 <= f < fn.numPolygons]
    if not faces:
        return 0, 0

    uvfaces, bad = _read_uv_faces(fn, faces, uvset)
    if bad:
        cmds.warning(u"UV拉直: %d non-quad face(s) skipped on '%s' "
                     "(only quad patches can be rectangularized)."
                     % (len(bad), shape))
    if not uvfaces:
        return 0, 0

    adj = _build_adjacency(uvfaces)
    done = skipped = 0
    for comp in _components(uvfaces, adj):
        emb = _embed_lattice(comp, uvfaces, adj)
        if emb is None:
            cmds.warning(u"UV拉直: '%s' 的一个 UV 区域无法映射为无冲突的四边形网格，已跳过。"
                         u"请检查未切开的闭环、极点或重叠拓扑；这不一定表示面不相连。" % shape)
            skipped += 1
            continue
        new = _reshape(comp, uvfaces, emb[0], rule)
        for uid, (u, v) in new.items():
            fn.setUV(uid, u, v, uvset)
        fn.updateSurface()
        done += 1
    return done, skipped


def rectangularize(rule="H", faces=None, objects=None):
    """UV拉直 - rebuild the selected (or given) UV quads into rectangles.

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
    cmds.undoInfo(openChunk=True, chunkName=u"UV拉直")
    try:
        for shape, face_list in targets:
            d, s = _process_shape(shape, face_list, rule)
            done += d
            skipped += s

        cmds.refresh(force=True)
        if done == 0:
            cmds.warning(u"UV拉直: nothing to do (need selected quads forming a quad grid).")
        return done
    finally:
        cmds.undoInfo(closeChunk=True)


def rectangularize_horizontal(*args):
    return rectangularize("H")


def rectangularize_vertical(*args):
    return rectangularize("V")


def rectangularize_natural(*args):
    return rectangularize("N")


# --------------------------------------------------------------------------- #
#  one-file installer / shelf deployment
# --------------------------------------------------------------------------- #

_MODULE_NAME = "maya_uv_straighten"
_SHELF_ANNOTATION = u"UV拉直工具"
_SHELF_LABEL = u"UV拉直"
# optionVar that remembers the dropped file, so the shelf command stays ASCII
_SOURCE_OPTION = "uvStraightenSourcePath"


def _text(value):
    """Return *value* as text (Maya returns str or unicode on Python 2)."""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value


def _remember_source(source_path):
    """Keep the file to sync from in an optionVar (no extra files on disk)."""
    try:
        if source_path:
            cmds.optionVar(stringValue=(_SOURCE_OPTION, source_path))
        else:
            cmds.optionVar(remove=_SOURCE_OPTION)
    except Exception:
        pass


def _source_option():
    """The file remembered by _remember_source(), or None."""
    try:
        if cmds.optionVar(exists=_SOURCE_OPTION):
            return _text(cmds.optionVar(query=_SOURCE_OPTION))
    except Exception:
        pass
    return None


def _maya_user_scripts_dir():
    """Return Maya's per-version user Python scripts directory."""
    path = cmds.internalVar(userScriptDir=True)
    if not path:
        raise RuntimeError("Maya user scripts directory is not available")
    if not os.path.isdir(path):
        os.makedirs(path)
    return os.path.normpath(path)


def _shelf_button_command():
    """Build a self-contained Python command stored in the Maya shelf.

    The command is pure ASCII: the folder of the dropped file is remembered in
    an optionVar instead of being embedded here, so the shelf file stays valid
    whatever encoding Maya uses for it and whatever Python version runs it.
    """
    return (
        "import sys; import maya.cmds as _c; "
        "p = _c.internalVar(userScriptDir=True); "
        "sys.path.insert(0, p) if p not in sys.path else None; "
        "import %s as _uvr; "
        "_uvr.open_tool()" % _MODULE_NAME
    )


def _current_shelf():
    """Return the shelf currently selected in Maya's shelf tab layout."""
    top_level = mel.eval("$tmp=$gShelfTopLevel")
    if not top_level or not cmds.control(top_level, exists=True):
        return None
    try:
        shelf = cmds.tabLayout(top_level, query=True, selectTab=True)
    except Exception:
        shelf = None
    return shelf if shelf and cmds.control(shelf, exists=True) else None


def _save_shelf(shelf):
    """Write the shelf to Maya's preferences folder so it survives a restart."""
    try:
        folder = os.path.join(cmds.internalVar(userPrefDir=True), "shelves")
        if not os.path.isdir(folder):
            os.makedirs(folder)
        cmds.saveShelf(shelf, os.path.join(folder, "shelf_" + shelf))
    except Exception:
        pass


def _clear_bytecode_cache(folder):
    """Remove this module's .pyc from *folder*/__pycache__.

    Python writes a bytecode cache next to a .py file the first time it is
    imported, which is how the __pycache__ folder shows up beside the script.
    Only this module's cache file is removed, and the folder itself only when
    it becomes empty, so the cache of other modules is left alone.
    """
    try:
        cache_dir = os.path.join(folder, "__pycache__")
        if not os.path.isdir(cache_dir):
            return
        removed = False
        for name in os.listdir(cache_dir):
            if name.startswith(_MODULE_NAME + ".") and name.endswith(".pyc"):
                try:
                    os.remove(os.path.join(cache_dir, name))
                    removed = True
                except Exception:
                    pass
        if removed and not os.listdir(cache_dir):
            os.rmdir(cache_dir)
    except Exception:
        pass


def _clear_caches(*paths):
    """Clear this module's bytecode cache next to each given file."""
    seen = set()
    for path in paths:
        if not path:
            continue
        folder = os.path.dirname(os.path.abspath(path))
        key = os.path.normcase(folder)
        if key in seen:
            continue
        seen.add(key)
        _clear_bytecode_cache(folder)


def _reload_module(module):
    """Reload *module* on Python 3 (importlib) and on Python 2 (built-in)."""
    reloader = getattr(importlib, "reload", None)
    if reloader is None:
        reloader = reload
    return reloader(module)


def _reload_without_cache(module):
    """_reload_module() that does not leave a .pyc behind."""
    previous = getattr(sys, "dont_write_bytecode", False)
    sys.dont_write_bytecode = True
    try:
        _reload_module(module)
    finally:
        sys.dont_write_bytecode = previous


def _deploy_shelf_button():
    """Create or replace this tool's button on the active Maya shelf."""
    shelf = _current_shelf()
    if not shelf:
        raise RuntimeError("No active Maya shelf was found")

    children = cmds.shelfLayout(shelf, query=True, childArray=True) or []
    for child in children:
        try:
            label = cmds.shelfButton(child, query=True, label=True)
        except Exception:
            label = None
        try:
            command = cmds.shelfButton(child, query=True, command=True) or ""
        except Exception:
            command = ""
        # also replaces the button of an older install of this module
        if (_text(label) == _SHELF_LABEL or
                (_MODULE_NAME in _text(command) and "_uvr.open_tool()" in _text(command))):
            try:
                cmds.deleteUI(child)
            except Exception:
                pass

    button = cmds.shelfButton(
        parent=shelf,
        label=_SHELF_LABEL,
        annotation=_SHELF_ANNOTATION,
        image1="tweakUVLarge.png",
        sourceType="python",
        command=_shelf_button_command(),
        style="iconAndTextHorizontal",
    )
    _save_shelf(shelf)
    return button


# Each action uses a persistent Python command, never a window-local callback.
_ACTION_LABELS = {"H": u"水平拉直", "V": u"垂直拉直", "N": u"自然拉直"}
_ACTION_ICONS = {"H": "doubleHorizArrow.png", "V": "doubleVertArrow.png",
                 "N": "cycleList.png"}


def _action_command(rule):
    if rule not in RULES:
        raise ValueError("Unknown straighten rule: %s" % rule)
    return (
        "import sys; import maya.cmds as _c; "
        "p = _c.internalVar(userScriptDir=True); "
        "sys.path.insert(0, p) if p not in sys.path else None; "
        "import %s as _uvr; _uvr._action_click(%r)" % (_MODULE_NAME, rule)
    )


def add_action_to_shelf(rule, *args):
    """Add/update just this action; do not run any UV operation."""
    if rule not in RULES:
        raise ValueError("Unknown straighten rule: %s" % rule)
    shelf = _current_shelf()
    if not shelf:
        cmds.warning(u"请先显示工具架并选中一个工具架标签。")
        return None
    command = _action_command(rule)
    tag = "UVStraighten/action/" + rule
    for child in cmds.shelfLayout(shelf, query=True, childArray=True) or []:
        try:
            matched = (cmds.shelfButton(child, query=True, docTag=True) == tag or
                       cmds.shelfButton(child, query=True, command=True) == command)
        except Exception:
            continue
        if matched:
            cmds.shelfButton(child, edit=True, command=command, sourceType="python",
                             image1=_ACTION_ICONS[rule],
                             style="iconAndTextHorizontal")
            _save_shelf(shelf)
            return child
    button = cmds.shelfButton(
        parent=shelf, label=_ACTION_LABELS[rule],
        annotation=u"UV拉直工具 - " + _ACTION_LABELS[rule],
        docTag=tag, image1=_ACTION_ICONS[rule], sourceType="python",
        command=command, style="iconAndTextHorizontal")
    _save_shelf(shelf)
    return button


def _action_click(rule):
    """Ctrl+Shift+click installs; a plain click executes the action."""
    if rule not in RULES:
        raise ValueError("Unknown straighten rule: %s" % rule)
    modifiers = cmds.getModifiers()
    if (modifiers & 5) == 5:  # Maya: Shift=1, Ctrl=4
        return add_action_to_shelf(rule)
    return rectangularize(rule)


def install(source_path=None, *args):
    """Install this single file and add a launcher to the active shelf.

    This is the entry point used when the .py file is dragged into Maya.  It
    does not touch the current scene or modify unrelated shelf buttons.
    """
    source_path = source_path or globals().get("__file__")
    if not source_path:
        raise RuntimeError("Cannot determine the dropped script path")
    source_path = os.path.normpath(os.path.abspath(source_path))

    scripts_dir = _maya_user_scripts_dir()
    destination = os.path.join(scripts_dir, _MODULE_NAME + ".py")
    same_file = os.path.normcase(source_path) == os.path.normcase(destination)
    if not same_file:
        shutil.copy2(source_path, destination)
    _remember_source(None if same_file else source_path)

    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    button = _deploy_shelf_button()

    # Reload the installed copy when the dropped file came from elsewhere.
    if not same_file:
        module = sys.modules.get(_MODULE_NAME)
        if module is not None:
            try:
                _reload_without_cache(module)
            except Exception:
                pass

    cmds.inViewMessage(
        amg=u"<hl>UV拉直工具</hl> 已安装到 Maya scripts，并已添加到当前工具架。",
        pos="midCenter", fade=True)
    print("Installed: %s" % destination)
    if not same_file:
        print("Edits are synced from: %s" % source_path)
    print("Shelf button created: %s" % button)
    _clear_caches(destination, source_path)
    return destination


def onMayaDroppedPythonFile(file_path, *args):
    """Maya's standard callback for a Python file dropped into its UI."""
    try:
        return install(file_path)
    except Exception as exc:
        cmds.warning("UV Straighten Tool install failed: %s" % exc)
        raise


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
        fn = _mesh_fn(shape)
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
            print("  ! %d non-quad face(s) are ignored" % len(bad))
    if not report:
        print("diagnose_selection: nothing found (select UV faces or objects first).")
    return report


# --------------------------------------------------------------------------- #
#  keeping the installed copy in sync with the dropped file
# --------------------------------------------------------------------------- #


def _sync_from_source(source_path):
    """Copy *source_path* over this installed file when its content differs.

    Returns True when the module file was replaced and has to be reloaded.
    A file that does not compile is never installed, so a typo cannot break
    the working copy.
    """
    if not source_path:
        return False
    try:
        source_path = os.path.normpath(os.path.abspath(source_path))
        target = os.path.normpath(os.path.abspath(__file__))
        if os.path.normcase(source_path) == os.path.normcase(target):
            return False
        with open(source_path, "rb") as f:
            data = f.read()
        with open(target, "rb") as f:
            if f.read() == data:
                return False
        compile(data, source_path, "exec")
        with open(target, "wb") as f:
            f.write(data)
        try:
            shutil.copystat(source_path, target)
        except Exception:
            pass
        return True
    except Exception:
        return False


def open_tool(source_path=None):
    """Shelf button entry point: sync the installed copy, reload, open the UI."""
    if not source_path:
        source_path = _source_option()
    _sync_from_source(source_path)
    show = show_ui
    module = sys.modules.get(__name__)
    if module is not None:
        try:
            _reload_without_cache(module)
            show = sys.modules[__name__].show_ui
        except Exception:
            show = show_ui
    window = show()
    _clear_caches(__file__, source_path)
    return window


# --------------------------------------------------------------------------- #
#  UI
# --------------------------------------------------------------------------- #

_WIN = "uvStraightenWin"
_WIN_TITLE = u"UV拉直工具"


def _window_names_with_title(title):
    """Maya window names whose title bar text is *title*."""
    names = []
    for name in cmds.lsUI(windows=True) or []:
        try:
            if _text(cmds.window(name, query=True, title=True)) == _text(title):
                names.append(name)
        except Exception:
            pass
    return names


def _pin_on_top(window_name):
    """Keep the window above Maya's other windows and make it freely resizable.

    Maya sizes a command window to its contents, which on Windows ends up as
    minimum size == maximum size: the frame is drawn with a resize border but
    Qt snaps it straight back, so the window cannot be dragged.  The size
    constraints are released here after the window is shown, and the always on
    top flag is set with Qt.  Every step is optional: when the Qt bindings or
    the window pointer are missing the window simply keeps Maya's behaviour.
    """
    try:
        from maya import OpenMayaUI as omui
    except Exception:
        return False
    try:
        ptr = omui.MQtUtil.findWindow(window_name)
    except Exception:
        return False
    if not ptr:
        return False

    try:
        try:                              # Maya 2022 - 2024
            from shiboken2 import wrapInstance
            from PySide2 import QtCore, QtWidgets
        except ImportError:               # Maya 2025+
            from shiboken6 import wrapInstance
            from PySide6 import QtCore, QtWidgets

        flag = getattr(QtCore.Qt, "WindowStaysOnTopHint", None)
        if flag is None:                  # PySide6 without enum shortcuts
            flag = QtCore.Qt.WindowType.WindowStaysOnTopHint

        widget = wrapInstance(int(ptr), QtWidgets.QWidget)
        geometry = widget.geometry()      # re-applying the flags hides it
        widget.setWindowFlags(widget.windowFlags() | flag)
        widget.setGeometry(geometry)
        widget.show()
        widget.raise_()
        widget.activateWindow()

        # release the fixed size so the frame can really be dragged
        layout = widget.layout()
        if layout is not None:
            try:
                if layout.sizeConstraint() == QtWidgets.QLayout.SetFixedSize:
                    layout.setSizeConstraint(QtWidgets.QLayout.SetDefaultConstraint)
            except Exception:
                pass
        hint = widget.minimumSizeHint()
        widget.setMaximumSize(16777215, 16777215)          # QWIDGETSIZE_MAX
        widget.setMinimumSize(hint)                        # keep the buttons visible
    except Exception:
        return False
    return True


def _style_action_button(control):
    """Style the native button without replacing Maya's drag handling."""
    try:
        from maya import OpenMayaUI as omui
        try:
            from shiboken2 import wrapInstance
            from PySide2 import QtWidgets
        except ImportError:
            from shiboken6 import wrapInstance
            from PySide6 import QtWidgets
        ptr = omui.MQtUtil.findControl(control)
        if not ptr:
            return False
        widget = wrapInstance(int(ptr), QtWidgets.QWidget)
        widget.setProperty("uvStraightenAction", True)
        selector = '*[uvStraightenAction="true"]'
        widget.setStyleSheet(
            selector + ' { background-color: #5b5b5b; border: 1px solid #747474;'
            ' border-radius: 0px; padding: 3px 6px; color: #eeeeee; text-align: left; }'
            + selector + ':hover { background-color: #696969; border-color: #929292; }'
            + selector + ':pressed { background-color: #444444; border-color: #a0a0a0; }')
        return True
    except Exception as exc:
        cmds.warning("UV Straighten: button styling unavailable: %s" % exc)
        return False


def show_ui(*args):
    # The window is identified by its name: the control name plus the title
    # shown in the title bar, so re-running this always reuses one window.
    for name in [_WIN] + _window_names_with_title(_WIN_TITLE):
        if cmds.window(name, exists=True):
            cmds.deleteUI(name)

    cmds.window(_WIN, title=_WIN_TITLE, widthHeight=(230, 156),
                sizeable=True, resizeToFitChildren=False)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=6, columnAttach=("both", 8))

    for rule in RULES:
        # Native shelfButton supplies Maya's command drag-and-drop payload.
        # Do not replace dragCallback with an arbitrary custom message.
        button = cmds.shelfButton(
            label=_ACTION_LABELS[rule], height=32,
            style="iconAndTextHorizontal", sourceType="python", align="left",
            image1=_ACTION_ICONS[rule], docTag="UVStraighten/action/" + rule,
            backgroundColor=(0.36, 0.36, 0.36),
            command=_action_command(rule),
            annotation=u"单击执行；Ctrl+Shift+单击添加到当前工具架；中键拖到工具架。")
        _style_action_button(button)
        popup = cmds.popupMenu(parent=button, button=3)
        from functools import partial
        cmds.menuItem(parent=popup, label=u"添加到当前工具架",
                      command=partial(add_action_to_shelf, rule))

    cmds.text(label=u"中键拖拽按钮到工具架", align="left", height=22)

    cmds.showWindow(_WIN)
    # Maya can snap the window back to its content size while showing it, so
    # the auto-fit is switched off again before the size is released in Qt.
    try:
        cmds.window(_WIN, edit=True, resizeToFitChildren=False)
    except Exception:
        pass
    _pin_on_top(_WIN)
    _clear_caches(__file__)
    return _WIN


if __name__ == "__main__":
    # Running the file directly inside Maya is treated the same as dropping
    # it into the Maya UI: install it and deploy the shelf launcher.
    install(__file__)
