---
name: logoup-to-printable
description: 把 LogoUp 3D（清软海芯 / Neobox）的 .logoup 程序文件转换为可直接切片打印的 STL / 3MF（拓竹 Bambu、Creality、Prusa 均适用）。当用户提到 .logoup、LogoUp、logoup 转 STL/3MF、3D打印文件转换、拓竹可打印文件、或「这个模型文件打不开」时触发。也用于判断一个3D文件到底是网格还是程序代码。
display_name: LogoUp(.logoup) 转可打印文件
display_name_en: LogoUp (.logoup) to printable STL/3MF
description_zh: 把 .logoup 建模代码解释成 STL/3MF（水密、分件、带颜色、自动排板），无需安装付费的官方 LogoUp 3D 软件。
description_en: Interpret LogoUp 3D .logoup modeling code into watertight STL/3MF for slicing, without the paid official software.
version: 1.0.0
author: 小布
category: 3d-printing
---

# LogoUp (.logoup) → 可打印 STL / 3MF

## 一句话结论

`.logoup` 是**建模程序代码**（类 LOGO 海龟绘图语言），不是网格文件。官方 Neobox LogoUp 3D 是付费软件（798 元/年起）且只能 GUI 手动导出，**不要去下载安装**；直接用本 skill 的解释器把代码编译成网格，等价且免费。

## 何时用 / 何时不用

| 用 | 不用 |
|---|---|
| 文件后缀 `.logoup` | `.stl/.3mf/.obj/.step/.z1/.scad` — 走常规切片或别的转换器 |
| 用户说「LogoUp / 清软海芯 / 3D打印课堂模型」 | 文件是二进制网格（步骤 0 会先判定） |
| 需要给拓竹/创想三维输出可打印文件 | 需要保留参数化可编辑性（那必须回官方软件） |

## 步骤 0：先判类型（30 秒，必做）

```bash
ls -la "FILE" && head -c 200 "FILE" | od -c | head -12
```
- 出现可读文本（WIDTH / NGON / BODY / GO / COLOR）→ `.logoup` 程序，走本流程。
- 开头 `solid` 或 80 字节头 + 大量二进制 → STL。
- 开头 `PK` → 3MF（zip）。
- 文件只有几百字节却号称「模型」→ 一定是程序，绝不是网格。

## LogoUp 语义速查

✅ = 官方教材/论文示例验证过；⚠️ = 本次推断，交付前需向用户明示

| 命令 | 语义 | 状态 |
|---|---|---|
| `NGON n, r` | 以**游标为中心**的正 n 边形，r = 外接圆半径（单位 mm） | ✅ |
| `WIDTH w` | 笔画宽度；闭合环未填充时 → 薄壁厚度 | ✅ |
| `FILL` | 填充**上一段已画好的闭合环**（写在 NGON **之后**，要回溯生效） | ✅ |
| `BODY … DONE` | 把当前草图拉伸成实体 | ✅ |
| `UP h`（在 BODY 内） | 拉伸高度，可负；**结束后游标抬到实体顶面** | ✅ |
| `UP h`（BODY 外） | 游标沿 z 移动 | ✅ |
| `CLEAR` | **只清草图，不动游标位置/朝向** | ✅ |
| `TURN a` / `GO d` | a>0 顺时针；GO 沿朝向移动（默认朝北 +Y） | ✅ |
| `COLOR c` | 写在 BODY 块内时，赋给该实体 | ✅ |
| 未 FILL 的闭合环 + BODY | 生成薄壁（管/环），这是 LogoUp 的「薄壳」特性 | ⚠️ 强推断 |
| 笔宽在路径两侧各 1/2 | 环 r、宽 w → 半径区间 [r-w/2, r+w/2] | ⚠️ 推断，误差 ≤1mm |
| 正多边形起始顶点朝向游标 | 仅影响绕中心旋转角，不影响尺寸/装配 | ⚠️ 推断 |

扩展命令（本脚本未实现，遇到先报错并人工判断）：`DRAW/GO/DONE`（笔画）、`EXTRUDE`、`REPEAT/VAR/FUNC`、`JUMP/LINK/YAW/PITCH/ROLL`、`SCALE/ERASE/SUBTRACT`、`BALL/CUBE/CONE`。

## 执行 SOP

```bash
# 1) 依赖（本机 Python 3.13，必须用 -m pip）
python -m pip install --quiet pypdf numpy shapely trimesh manifold3d networkx pillow

# 2) 转换：脚本在 skill 目录 scripts/ 下
python "scripts/logoup2stl.py" "输入.logoup" "输出.stl" "输出.3mf" "预览.png"

# 3) 校验
python - <<'EOF'
import zipfile, xml.etree.ElementTree as ET, struct
z = zipfile.ZipFile("输出.3mf"); assert z.testzip() is None
root = ET.fromstring(z.read("3D/3dmodel.model"))
ns = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
for ob in root.findall(".//m:object", ns):
    v = ob.findall(".//m:vertex", ns); t = ob.findall(".//m:triangle", ns)
    xs=[float(a.get("x")) for a in v]; ys=[float(a.get("y")) for a in v]; zs=[float(a.get("z")) for a in v]
    print(ob.get("name"), len(v),"顶点", len(t),"面",
          f"x[{min(xs):.1f},{max(xs):.1f}] y[{min(ys):.1f},{max(ys):.1f}] z[{min(zs):.1f},{max(zs):.1f}]")
b = open("输出.stl","rb").read(); n = struct.unpack("<I", b[80:84])[0]
print("STL 面数", n, "字节一致:", len(b) == 84 + n*50)
EOF
```

改板尺寸：脚本内 `main(..., bed=(256,256))`；拓竹 A1/P1P/X1C=256，A1 mini=180，H2D=350。

## 判断标准（交付前逐条过）

| # | 检查项 | 合格标准 |
|---|---|---|
| 1 | 每个零件水密 | `is_watertight == True`；不是就别交付 |
| 2 | 每个零件贴板 | z 最小值 = 0 |
| 3 | 全部在板内 | max(x,y) ≤ bed-12 |
| 4 | 体积对账 | 手算体积 vs 脚本输出，误差 <5%（见下） |
| 5 | 壁厚对账 | 壁体积 ≈ (A外-A内)×高，不是实心体积 |
| 6 | 分件正确 | XY 重叠的实体合并成一件，分开的各自独立 |
| 7 | 三视图目视 | 开口容器能看到内腔与均匀壁厚；无破面/悬空 |
| 8 | 支撑判断 | 全直壁 → 无需支撑；有悬垂再提醒开支撑 |

对账公式（正 n 边形面积 `A = n/2·r²·sin(2π/n)`，五边形 ≈ `2.3776·r²`）：
- 实心盘：`A × 高`
- 环/薄壁：`(A(r+w/2) − A(r−w/2)) × 高`
- 容器类总体积应**远小于**同尺寸实心块（例：本次盒 49.6 cm³ vs 实心 216 cm³）→ 说明确实是空心壳。

## 踩过的坑（按出现顺序）

| 现象 | 原因 | 解法 |
|---|---|---|
| 以为要装转换软件 | 官方软件付费且仅 GUI | 自写解释器，不下载 |
| `pip: command not found` | 本机无 pip 可执行 | 一律 `python -m pip` |
| 官方教材 PDF 抽不出文字 | 扫描/图形版 PDF | `pypdfium2` 渲染成 PNG 再看；或查官方论文里的代码示例反推语义 |
| `ValueError: could not convert 'cyan'` | 把颜色当数字参数解析 | 参数只取能 `float()` 的 token |
| 实体全变成灰色 | `COLOR` 写在 `BODY` 之后 | COLOR 在 BODY 块内要写回 `body["color"]` |
| 底板变空心环 | `FILL` 在 `NGON` **之后**出现 | FILL 需回溯修改已有草图的填充标记 |
| `IndexError: index 3 is out of bounds` | trimesh 5.x `bounds` 是 `(2,3)`，不是 `(6,)` | 用 `b[1][0]` / `b[0][1]` 这种二维下标 |
| `No module named 'scipy'`（合并/剖切/导出时） | trimesh 的 `concatenate`、`faces_sparse` 依赖 scipy 且本机装不上 | 自己拼顶点/面；自写二进制 STL；剖切校验改用体积对账 |
| 3MF：`name 'etree' is not defined` | trimesh 5.2 的 `export_3MF` 有 bug | 自写最小 3MF（zip + Content_Types + rels + 3dmodel.model） |
| 零件悬空 | 拉伸后游标停在顶面，后续草图跟着抬高 | 每个零件导出前平移到 `z_min = 0` |
| 排版超板 | 原程序里零件间距 100mm，总跨 400mm | `arrange()` 重新排 2 列网格 |
| 三视图贴错标签 | 自写渲染器 `elev=0` 是俯视、`elev=90` 是正视 | TOP 用 `elev=0`，FRONT 用 `elev=90` |
| matplotlib 中文乱码 | 缺 CJK 字体 | 预览标签全用英文；或改用 `scripts/softrender.py`（纯 numpy z-buffer） |
| `FileNotFoundError: /f/下载/...` | Python 不认 Git Bash 的 `/f/` 路径 | 用 `F:/下载/...` |

## 不确定时的规矩

1. 语义存疑（尤其「未 FILL 环 = 薄壁」）→ **先出三视图预览 + 尺寸/壁厚数字，让用户对着看一眼**，再放行；别闷头交付。
2. 遇到未实现的命令（REPEAT / LINK / BALL 等）→ 直接说不支持，给出人工方案（装官方软件导出，或按语义补解释器），不要猜着生成。
3. 交付时必须写清：哪些是✅验证、哪些是⚠️推断、推断的误差量级（如笔宽方向 ±1mm、多边形起始角不影响装配）。

## 交付清单

- `xxx_原始位置.stl` — 严格按程序坐标，1:1 复刻
- `xxx_排版.stl` — 已排进目标板尺寸
- `xxx.3mf` — **推荐**：多零件独立对象 + 颜色，切片软件可直接分件
- `预览_三视图.png` — ISO / TOP / FRONT
- 结论表：零件数、尺寸、壁厚、体积、是否水密、是否需支撑、耗材与耗时粗估

## 本次实测值（五边形小盒，可作回归基准）

4 件，全部水密；盒 97.46×92.69×35（底 5 + 壁 25 厚 2 + 内唇 5 厚 1）、盖圈 φ94×15、盖板 94×5、装饰片 87×2.5；总体积 95.5 cm³；138 三角面；排版后占 205.8×196.4 mm。
