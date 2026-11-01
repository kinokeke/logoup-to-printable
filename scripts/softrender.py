# -*- coding: utf-8 -*-
"""简易 z-buffer 软渲染：正交投影 + 平行光平直着色，输出 PNG 预览"""
import numpy as np
from PIL import Image, ImageDraw


def rot(elev_deg, azim_deg):
    e, a = np.radians(elev_deg), np.radians(azim_deg)
    rz = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
    rx = np.array([[1, 0, 0], [0, np.cos(e), -np.sin(e)], [0, np.sin(e), np.cos(e)]])
    return rx @ rz


def render(meshes_colors, out_png, elev=22, azim=-118, size=(1500, 900),
           bg=(255, 255, 255), margin=0.07, label=None):
    W, H = size
    R = rot(elev, azim)
    p = np.vstack([m.vertices for m, _ in meshes_colors]) @ R.T
    faces, cols = [], []
    off = 0
    for m, c in meshes_colors:
        faces.append(m.faces + off)
        cols.append(np.tile(np.array(c) / 255.0, (len(m.faces), 1)))
        off += len(m.vertices)
    faces = np.vstack(faces)
    cols = np.vstack(cols)

    lo, hi = p.min(0), p.max(0)
    ctr = (lo + hi) / 2
    span = (hi - lo)[:2].max()
    s = min(W, H) * (1 - 2 * margin) / span

    light = np.array([0.45, -0.55, 0.72])
    light /= np.linalg.norm(light)
    v = p[faces]
    n = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
    nn = np.linalg.norm(n, axis=1, keepdims=True)
    nn[nn == 0] = 1
    n = n / nn
    lam = 0.34 + 0.66 * np.clip(np.abs(n @ light), 0, 1)
    shade = (np.clip(cols * lam[:, None], 0, 1) * 255).astype(np.uint8)

    sx = (p[:, 0] - ctr[0]) * s + W / 2
    sy = H / 2 - (p[:, 1] - ctr[1]) * s
    sz = p[:, 2]

    buf = np.empty((H, W, 3), np.uint8)
    buf[:] = bg
    zbuf = np.full((H, W), -1e18)

    for fi in np.argsort(v[:, :, 2].mean(1)):
        f = faces[fi]
        X, Y, Z = sx[f], sy[f], sz[f]
        x0, x1 = int(max(0, np.floor(X.min()))), int(min(W - 1, np.ceil(X.max())))
        y0, y1 = int(max(0, np.floor(Y.min()))), int(min(H - 1, np.ceil(Y.max())))
        if x1 < x0 or y1 < y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + .5, np.arange(y0, y1 + 1) + .5)
        d = (Y[1] - Y[2]) * (X[0] - X[2]) + (X[2] - X[1]) * (Y[0] - Y[2])
        if abs(d) < 1e-9:
            continue
        w0 = ((Y[1] - Y[2]) * (xs - X[2]) + (X[2] - X[1]) * (ys - Y[2])) / d
        w1 = ((Y[2] - Y[0]) * (xs - X[2]) + (X[0] - X[2]) * (ys - Y[2])) / d
        w2 = 1 - w0 - w1
        inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not inside.any():
            continue
        zz = w0 * Z[0] + w1 * Z[1] + w2 * Z[2]
        sub = zbuf[y0:y1 + 1, x0:x1 + 1]
        upd = inside & (zz > sub)
        if not upd.any():
            continue
        sub[upd] = zz[upd]
        subimg = buf[y0:y1 + 1, x0:x1 + 1]
        subimg[upd] = shade[fi]

    img = Image.fromarray(buf)
    if label:
        ImageDraw.Draw(img).text((26, 22), label, fill=(60, 60, 60))
    img.save(out_png)
    return out_png
