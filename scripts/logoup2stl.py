# -*- coding: utf-8 -*-
"""logoup2stl.py —— 把 LogoUp 3D (.logoup) 程序解释成可打印网格 (STL/3MF)

支持命令: WIDTH / NGON / FILL / BODY / UP / DONE / CLEAR / TURN / GO / COLOR
语义（依据 LogoUp 官方教材 + 官方论文示例验证）:
  NGON n,r   以游标为中心、外接圆半径 r 的正 n 边形草图
  FILL       填充草图（未填充时为笔宽 w 的闭合薄壁）
  BODY..DONE 把当前草图沿 UP 距离拉伸成实体；结束后游标抬到实体顶面
  CLEAR      清除草图（游标位置不变）
  TURN a     a>0 顺时针
  GO d       沿朝向前进 d mm
"""
import math
import os
import sys
import numpy as np
import shapely
from shapely.geometry import Polygon
import trimesh

COLORS = {"cyan": (0, 188, 212), "white": (245, 245, 245), "red": (229, 57, 53),
          "lime": (139, 195, 74), "blue": (30, 93, 201), "gray": (128, 128, 128),
          "dark_gray": (66, 66, 66), "black": (30, 30, 30), "yellow": (253, 216, 53),
          "magenta": (194, 24, 91), "orange": (245, 124, 0)}


def _is_num(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


class Turtle:
    def __init__(self):
        self.x = self.y = self.z = 0.0
        self.heading = 90.0          # 度，数学角：0=+X，90=+Y（正北）
        self.width = 1.0
        self.color = "gray"
        self.sketch = []             # [(Polygon, filled)]
        self.fill = False
        self.body = None             # dict(z0, h, color, shapes)
        self.solids = []             # [(mesh, color, name)]

    # ---------- 绘图 ----------
    def ngon(self, n, r):
        n = int(round(n))
        verts = []
        for k in range(n):
            a = math.radians(self.heading - k * 360.0 / n)
            verts.append((self.x + r * math.cos(a), self.y + r * math.sin(a)))
        poly = Polygon(verts)
        if not poly.is_valid:
            poly = poly.buffer(0)
        self.sketch.append((poly, self.fill, self.width))
        self.fill = False            # 下一段草图默认不填充

    def go(self, d):
        a = math.radians(self.heading)
        self.x += d * math.cos(a)
        self.y += d * math.sin(a)

    def turn(self, deg):
        self.heading -= deg          # 正数顺时针

    # ---------- 实体 ----------
    def build_body(self):
        b = self.body
        regions = []
        for poly, filled, w in b["shapes"]:
            outer = poly.buffer(w / 2.0, join_style=2, resolution=8)
            if filled:
                regions.append(outer)
            else:
                inner = poly.buffer(-w / 2.0, join_style=2, resolution=8)
                ring = outer.difference(inner) if not inner.is_empty else outer
                if not ring.is_empty:
                    regions.append(ring)
        if not regions:
            raise RuntimeError("BODY 内没有草图")
        region = shapely.unary_union(regions)
        h = b["h"]
        if abs(h) < 1e-9:
            raise RuntimeError("BODY 高度为 0")
        mesh = trimesh.creation.extrude_polygon(region, abs(h))
        z0 = b["z0"] if h > 0 else b["z0"] + h
        mesh.apply_translation((0, 0, z0))
        self.solids.append((mesh, b["color"]))
        self.z = (b["z0"] + h)       # 游标抬到顶面（负拉伸则到下方）


def run(path):
    t = Turtle()
    body_n = 0
    for raw in open(path, encoding="utf-8-sig"):
        line = raw.strip()
        if not line or line[0] in "#;":
            continue
        parts = line.replace(",", " ").split()
        cmd = parts[0].upper()
        args = [float(a) for a in parts[1:] if _is_num(a)]
        if cmd == "WIDTH":
            t.width = args[0]
        elif cmd == "NGON":
            t.ngon(args[0], args[1])
        elif cmd == "FILL":
            t.fill = True
            if t.sketch:                       # FILL 作用于已画好的闭合环
                t.sketch = [(poly, True, w) for poly, _, w in t.sketch]
        elif cmd == "BODY":
            t.body = {"z0": t.z, "h": 0.0, "color": t.color,
                      "shapes": list(t.sketch)}
        elif cmd == "UP":
            if t.body is not None:
                t.body["h"] += args[0]
            t.z += args[0]
        elif cmd == "DONE":
            if t.body is not None:
                t.build_body()
                body_n += 1
                print(f"  BODY#{body_n}: z0={t.body['z0']:.2f} h={t.body['h']:.2f} "
                      f"色={t.body['color']} 三角形={len(t.solids[-1][0].faces)}")
                t.body = None
        elif cmd == "CLEAR":
            t.sketch = []
            t.fill = False
        elif cmd == "TURN":
            t.turn(args[0])
        elif cmd == "GO":
            t.go(args[0])
        elif cmd == "COLOR":
            t.color = parts[1].lower()
            if t.body is not None:
                t.body["color"] = t.color
        else:
            print(f"  ! 暂不支持的指令: {line}")
    return t


def group_objects(solids):
    """按 XY 包围盒重叠分组成独立零件，并做布尔并集"""
    n = len(solids)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    boxes = [m.bounds for m, _ in solids]   # 每项 shape=(2,3): [min_xyz, max_xyz]
    for i in range(n):
        for j in range(i + 1, n):
            a, b = boxes[i], boxes[j]
            if not (a[1][0] < b[0][0] or b[1][0] < a[0][0]
                    or a[1][1] < b[0][1] or b[1][1] < a[0][1]):
                parent[find(i)] = find(j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    objs = []
    for idxs in groups.values():
        meshes = [solids[i][0] for i in idxs]
        merged = trimesh.boolean.union(meshes, engine="manifold") if len(meshes) > 1 else meshes[0]
        merged.remove_unreferenced_vertices()
        merged.apply_translation((0, 0, -merged.bounds[0][2]))   # 落到打印平台
        col = COLORS.get(solids[idxs[0]][1], (200, 200, 200))
        objs.append((merged, col))
    return objs


def write_stl(objs, path, name="logoup2stl"):
    """自写二进制 STL，单位 mm"""
    import struct
    tris, norms = [], []
    for m, _ in objs:
        v = np.asarray(m.vertices)
        f = np.asarray(m.faces)
        t = v[f]
        n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        ln = np.linalg.norm(n, axis=1, keepdims=True)
        ln[ln == 0] = 1
        tris.append(t)
        norms.append(n / ln)
    t = np.vstack(tris)
    n = np.vstack(norms)
    with open(path, "wb") as fh:
        fh.write(name.encode()[:80].ljust(80, b" "))
        fh.write(struct.pack("<I", len(t)))
        for i in range(len(t)):
            fh.write(struct.pack("<12fH", *n[i], *t[i][0], *t[i][1], *t[i][2], 0))
    print(f"  三角面 {len(t)} -> {path}")


def concat(objs):
    """不用 scipy 的合并：直接拼接顶点/面"""
    vs, fs, off = [], [], 0
    for m, _ in objs:
        vs.append(np.asarray(m.vertices))
        fs.append(np.asarray(m.faces) + off)
        off += len(m.vertices)
    return trimesh.Trimesh(vertices=np.vstack(vs), faces=np.vstack(fs), process=False)


def arrange(objs, bed=(256, 256), gap=8):
    """把零件按 2 列网格排到打印板上（拓竹 256x256 常见机型）"""
    usable_w, usable_h = bed[0] - 12, bed[1] - 12
    sizes = [((m.bounds[1][0] - m.bounds[0][0]), (m.bounds[1][1] - m.bounds[0][1])) for m, _ in objs]
    order = sorted(range(len(objs)), key=lambda i: -sizes[i][0])
    cols = 2 if len(objs) > 1 else 1
    out, x, y, row_h, k = {}, 0.0, 0.0, 0.0, 0
    for i in order:
        w, h = sizes[i]
        if k % cols == 0 and k:
            x, y, row_h = 0.0, y + row_h + gap, 0.0
        if x + w > usable_w and k % cols:
            x, y, row_h = 0.0, y + row_h + gap, 0.0
        out[i] = (x - (m_b := objs[i][0].bounds[0][0]) + 6, y - objs[i][0].bounds[0][1] + 6)
        x += w + gap
        row_h = max(row_h, h)
        k += 1
    moved = []
    for i, (m, c) in enumerate(objs):
        mm = m.copy()
        mm.apply_translation((out[i][0], out[i][1], -mm.bounds[0][2]))
        moved.append((mm, c))
    total_w = max(mm.bounds[1][0] for mm, _ in moved)
    total_h = max(mm.bounds[1][1] for mm, _ in moved)
    print(f"  排版后占用 {total_w:.1f} x {total_h:.1f} mm")
    return moved


def main(src, out_stl, out_3mf=None, png=None, bed=(256, 256)):
    print(f"解释 {src}")
    t = run(src)
    objs = group_objects(t.solids)
    print(f"零件数: {len(objs)}")
    for k, (m, _) in enumerate(objs, 1):
        b = m.bounds
        print(f"  零件{k}: 尺寸 {b[1][0]-b[0][0]:.2f} x {b[1][1]-b[0][1]:.2f} x {b[1][2]-b[0][2]:.2f} mm, "
              f"三角面 {len(m.faces)}, 水密={m.is_watertight}, 体积={m.volume/1000:.2f} cm³")
    tag = os.path.splitext(os.path.basename(src))[0]
    write_stl(objs, out_stl, tag)
    print("STL ->", out_stl)
    print(f"排版到 {bed[0]}x{bed[1]} 打印板:")
    placed = arrange(objs, bed=bed)
    write_stl(placed, out_stl.replace(".stl", "_plate.stl"), f"{tag} layout {bed[0]}")
    print("STL(排版) ->", out_stl.replace(".stl", "_plate.stl"))
    objs_plate = placed
    if out_3mf:
        try:
            write_3mf(objs_plate, out_3mf)
            print("3MF ->", out_3mf)
        except Exception as e:
            print("3MF 导出失败(可忽略):", e)
    if png:
        render(objs, png)
    return objs


def write_3mf(objs, path):
    """最小可用 3MF（分包、带颜色），Bambu Studio / PrusaSlicer 均可导入"""
    import zipfile
    from xml.sax.saxutils import escape
    mats = []
    objs_xml = []
    for k, (m, col) in enumerate(objs, 1):
        hexcol = "#FF%02X%02X%02X" % tuple(int(c) for c in col)
        mats.append(f'<base name="part{k}" displaycolor="{hexcol}"/>')
        vs = "".join(f'<vertex x="{v[0]:.4f}" y="{v[1]:.4f}" z="{v[2]:.4f}"/>' for v in m.vertices)
        ts = "".join(f'<triangle v1="{f[0]}" v2="{f[1]}" v3="{f[2]}" p1="0" p2="0" p3="0"/>'
                     for f in m.faces)
        objs_xml.append(
            f'<object id="{k}" type="model" name="part{k}" pid="1" pindex="{k-1}">'
            f'<mesh><vertices>{vs}</vertices><triangles>{ts}</triangles></mesh></object>')
    model = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<model unit="millimeter" xml:lang="en-US" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
        '<metadata name="Title">box_small</metadata>'
        '<metadata name="Application">logoup2stl</metadata>'
        '<resources><basematerials id="1">' + "".join(mats) + '</basematerials>'
        + "".join(objs_xml) + '</resources><build>'
        + "".join(f'<item objectid="{k}"/>' for k in range(1, len(objs) + 1))
        + '</build></model>')
    ct = ('<?xml version="1.0" encoding="UTF-8"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
          '</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
            'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
            '</Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", model)


def render(objs, png):
    from softrender import render as sr
    from PIL import Image
    tiles = [sr(objs, "_iso.png", elev=26, azim=-128, size=(1100, 780),
                label="ISO view (mm)"),
             sr(objs, "_top.png", elev=0, azim=180, size=(1100, 780),
                label="TOP view"),
             sr(objs, "_front.png", elev=90, azim=180, size=(1100, 780),
                label="FRONT view")]
    ims = [Image.open(t) for t in tiles]
    w = sum(i.width for i in ims)
    h = max(i.height for i in ims)
    sheet = Image.new("RGB", (w, h), "white")
    x = 0
    for im in ims:
        sheet.paste(im, (x, 0))
        x += im.width
    sheet.save(png)
    print("预览 ->", png)


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], a[2] if len(a) > 2 else None, a[3] if len(a) > 3 else None)
