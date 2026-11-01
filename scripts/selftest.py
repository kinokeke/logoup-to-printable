# -*- coding: utf-8 -*-
"""安装自检：依赖是否齐全 + 用示例件跑一遍转换

用法： python selftest.py
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

DEPS = [("numpy", "numpy"), ("shapely", "shapely"), ("trimesh", "trimesh"),
        ("manifold3d", "manifold3d"), ("PIL", "pillow")]


def main():
    print("=" * 46)
    print(" logoup-to-printable  安装自检")
    print("=" * 46)
    print(f"Python {sys.version.split()[0]}  ({sys.executable})")

    missing = []
    for mod, pkg in DEPS:
        try:
            __import__(mod)
            print(f"  [OK]   {pkg}")
        except ImportError:
            print(f"  [缺失] {pkg}")
            missing.append(pkg)

    if missing:
        print("\n先装依赖，再跑本自检：")
        print(f"  {sys.executable} -m pip install " + " ".join(missing))
        return 1

    demo = os.path.join(ROOT, "examples", "demo_box.logoup")
    if not os.path.exists(demo):
        print(f"\n[FAIL] 缺示例文件 {demo}")
        return 1

    sys.path.insert(0, HERE)
    import logoup2stl as L

    out = tempfile.mkdtemp(prefix="logoup_selftest_")
    stl = os.path.join(out, "demo.stl")
    threemf = os.path.join(out, "demo.3mf")
    print(f"\n示例件：{demo}")
    objs = L.main(demo, stl, threemf, None)
    print(f"\n输出目录：{out}")

    ok = bool(objs) and all(m.is_watertight for m, _ in objs)
    print("\n" + ("通过：解释器可用，输出水密。" if ok else "失败：存在非水密零件，请把上面的输出发回给作者。"))
    print("=" * 46)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
