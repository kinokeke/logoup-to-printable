# logoup-to-printable

把 **LogoUp 3D**（清软海芯 / Neobox）的 `.logoup` 建模代码，直接编译成可以上机打印的 **STL / 3MF**。
不用装官方 LogoUp 3D 软件（付费，798 元/年起，还只能手动导出）。

> 一个 Agent Skill：装进 WorkBuddy / Claude Code / Cursor 等 75+ 支持 Agent Skills 的客户端，
> 之后把 `.logoup` 丢给 AI 说一句「转成能打印的」，它就会自动按这套流程干活。

## 安装

```bash
npx skills add kinokeke/logoup-to-printable -g -y
```

- `-g` 全局安装（不写就只装进当前项目）；`-y` 跳过交互确认。需要 Node.js ≥ 22.20。
- 装完重启客户端，新会话生效。
- 只想先看看里面有什么，不安装：`npx skills add kinokeke/logoup-to-printable -l`

## 它解决什么问题

`.logoup` 是**程序代码**，不是网格文件。文件可能只有几百字节，常规切片软件一律打不开。
本技能内置一个 LogoUp 语言解释器，把代码解释成三维实体，并处理打印前的一切琐事：

| 步骤 | 说明 |
|---|---|
| 解释 | `NGON / FILL / BODY / UP / DONE / CLEAR / TURN / GO / WIDTH / COLOR` |
| 布尔 | 同位置重叠实体合并成一个零件，不同位置的自动分件 |
| 落板 | 每个零件 `z_min = 0`，不悬空 |
| 排板 | 自动排进 256×256 打印板（可改 180 / 256 / 350） |
| 导出 | STL（二进制、mm）+ 3MF（多零件独立对象、带颜色） |
| 预览 | ISO / TOP / FRONT 三视图 PNG |

## 最小示例

`examples/demo_box.logoup`（五边形小盒，底 4mm + 壁 20mm）：

```
WIDTH 2
NGON 5, 40
FILL
BODY
  COLOR cyan
  UP 4
DONE
CLEAR
WIDTH 2
NGON 5, 40
BODY
  COLOR white
  UP 20
DONE
CLEAR
```

跑一遍：

```bash
python scripts/selftest.py                      # 装好先自检
python scripts/logoup2stl.py examples/demo_box.logoup out.stl out.3mf preview.png
```

期望输出（回归基准）：

```
零件数: 1
  零件1: 尺寸 78.44 x 74.60 x 24.00 mm, 三角面 46, 水密=True, 体积=25.58 cm³
```

然后 `out.3mf` 用 Bambu Studio / OrcaSlicer / Cura 直接打开切片即可。

## 依赖

Python ≥ 3.9：

```bash
python -m pip install numpy shapely trimesh manifold3d pillow
```

没有 `pip` 命令就用 `python -m pip`。装完跑 `python scripts/selftest.py`，会打印 PASS 或缺失的包名。

## 支持的机型 / 板尺寸

在 `scripts/logoup2stl.py` 里改 `main(..., bed=(256, 256))`：

| 机型 | 板尺寸 |
|---|---|
| Bambu A1 mini | 180 |
| Bambu A1 / P1P / P1S / X1C | 256 |
| Bambu H2D | 350 |

## 能力边界（重要）

- 只实现基础绘图命令。`REPEAT / EXTRUDE / LINK / BALL / CUBE / SUBTRACT / JUMP / YAW` 等**没有实现**，遇到会明确报错并停下，不会瞎猜生成。
- 笔宽方向按「路径两侧各 1/2」处理（例如半径 50、笔宽 2 → 环形 49–51），误差 ≤ 1mm。
- 正多边形起始顶点朝向游标方向，只影响绕中心旋转角，不影响尺寸与装配。
- 这些推断项在 `SKILL.md` 里都标了 ⚠️，交付前会提醒你先看三视图。

## 常见失败原因

| 现象 | 原因 / 解法 |
|---|---|
| `npx skills add` 找不到技能 | 仓库根目录必须有 `SKILL.md`，且 frontmatter 的 `name` 只允许小写字母和连字符 |
| 命令能跑但装错目录 | 客户端不在 CLI 支持列表里（WorkBuddy 部分版本会装到 `~/.agents/skills/`），手动复制到 `~/.workbuddy/skills/logoup-to-printable` 即可 |
| `ModuleNotFoundError: shapely` | 依赖没装，见上面「依赖」 |
| 打开 3MF 是空的 | 用了会丢对象的导出器；本仓库自带最小 3MF 写入器，别替换 |
| 切片看到模型浮空 | 说明没走落板步骤，检查是否直接用了原始 STL |

## 仓库结构

```
logoup-to-printable/
├── SKILL.md                   技能定义（触发词 / 步骤 / 验收标准 / 踩坑表）
├── _meta.json                 WorkBuddy 界面元信息（显示名、图标、标签）
├── scripts/
│   ├── logoup2stl.py          解释器 + 建模 + 排板 + STL/3MF 导出
│   ├── softrender.py          z-buffer 三视图渲染（纯 numpy）
│   └── selftest.py            安装自检
└── examples/demo_box.logoup   最小示例
```

## License

MIT
