# Assignment02 — Interactive Canvas Music Toy

## English

### Overview
- Primary implementation: `ui.py` (Python + Matplotlib/Pygame). Richer feature set and recommended for full experience.
- Simplified implementation: `index.html` (Canvas in browser). Easier to run; use as fallback if the Python implementation cannot run on your machine.
- Playback logic differs slightly:
  - Python version: quantized ticks per measure, grouped scheduling by horizontal proximity, dynamic volume ducking, gentle crossfades, richer visual feedback.
  - HTML version: red playhead sweeping across the `frame`; triggers based on each shape’s horizontal position with a fixed loop length.
- First, watch the provided demo video to understand the intended behavior and effects.

### Quick Start (Recommended: Python)
- Create/activate venv (PowerShell): ` .\\.venv\\Scripts\\Activate.ps1`
- Install dependencies: `pip install -r requirements.txt`
- Run: `python ui.py`

### Controls (Python)
- Templates: `circle`, `triangle`, `square` are shown in the bottom bar.
- Place shapes: drag a template into the main `frame` area.
- Scale: press inside a placed shape and drag vertically to scale.
- Delete: long press inside a shape (~650ms); moving beyond ~6px cancels the delete.
- Play/Pause: click the Play/Pause button in the bottom bar.
- Clear: click the Clear button to remove all placed shapes.

### Effects & Playback (Python)
- Instruments: mapped by shape type and vertical position.
  - `circle` → piano timbres (`piano_1..7`)
  - `triangle` → drum regions (`drum_1..3`)
  - `square` → synth timbres (`synth_1..7`)
- Scheduling: shapes are grouped by horizontal proximity; playback uses quantized ticks within a measure for rhythmic consistency.
- Dynamics: when one instrument type dominates, the other is gently ducked to balance the mix.
- Transitions: squares use subtle crossfades when successive notes overlap.
- Visuals: background gradient, note flashes/brightening on trigger, size reflects energy.

### Troubleshooting (Python)
- No window or GUI issue: switch backend to `TkAgg` or `Qt5Agg`.
  - Add at the top of `ui.py`: `import matplotlib; matplotlib.use('TkAgg')`
  - Or install `PyQt5` and use `Qt5Agg`.
- Audio contention: avoid running multiple audio apps (e.g., another instance of `ui.py`) simultaneously.

### Fallback (Simplified: HTML)
- Start a local server: `python -m http.server 8000`
- Open: `http://localhost:8000/index.html`
- Single-file (offline): `python bundle.py` then open `index.bundle.html`

### Controls (HTML)
- Place shapes: drag from the template area into the `frame`.
- Scale: press inside a shape and drag vertically.
- Delete: long press inside a shape (~650ms), cancelled if moved too far.
- Toolbar: Play/Pause and Clear.

### Effects & Playback (HTML)
- Red playhead: a semi-transparent vertical line sweeps across the `frame`.
- Triggering: note events are scheduled based on each shape’s horizontal position within the loop.
- Loop: fixed-length loop (configurable), continuous repetition.
- Instruments: same type-to-timbre mapping as Python.

---

## 中文说明

### 概览
- 主要实现：`ui.py`（Python + Matplotlib/Pygame）。功能更完整，推荐优先运行。
- 简化实现：`index.html`（浏览器 Canvas）。更易运行，如你的电脑无法运行 Python 版可作为回退方案。
- 播放逻辑略有差异：
  - Python 版：按小节量化节拍、按横向临近分组调度、音量动态压制（ducking）、平滑交叉淡入淡出、更丰富的视觉反馈。
  - HTML 版：红色播放指针在 `frame` 横扫；按形状的横向位置触发，固定循环时长。
- 建议先观看项目的演示视频，以快速了解目标效果与交互方式。

### 快速开始（推荐：Python 版）
- 创建/激活虚拟环境（PowerShell）：` .\\.venv\\Scripts\\Activate.ps1`
- 安装依赖：`pip install -r requirements.txt`
- 运行：`python ui.py`

### 操作方式（Python 版）
- 模板：底栏提供 `circle`、`triangle`、`square`。
- 放置：从底栏拖拽到主画布 `frame` 内。
- 缩放：在形状内部按住上下拖动。
- 删除：长按约 650ms；移动超过约 6px 则取消删除。
- 播放/暂停：点击底栏的 Play/Pause 按钮。
- 清空：点击底栏的 Clear 按钮。

### 实现效果与播放（Python 版）
- 音色映射：按形状类型与纵向位置选择音色。
  - `circle` → 钢琴（`piano_1..7`）
  - `triangle` → 鼓区（`drum_1..3`）
  - `square` → 合成器（`synth_1..7`）
- 调度：按形状的横向临近分组，节拍采用小节量化（ticks），保证节奏稳定。
- 动态：当某一类音符数量过多时，另一类音色会轻微降音（ducking）以平衡整体声音。
- 过渡：正方形音色在连续触发时进行细微交叉淡入淡出，使过渡更平滑。
- 视觉：背景渐变、触发闪烁与亮度提升、大小体现能量。

### 故障排查（Python 版）
- 窗口未显示或图形后端异常：将后端切换为 `TkAgg` 或 `Qt5Agg`。
  - 在 `ui.py` 顶部添加：`import matplotlib; matplotlib.use('TkAgg')`
  - 或安装 `PyQt5` 并使用 `Qt5Agg`。
- 音频冲突：避免同时运行多个使用音频的程序（例如另一个 `ui.py`）。

### 回退方案（简化：HTML 版）
- 启动本地服务：`python -m http.server 8000`
- 打开页面：`http://localhost:8000/index.html`
- 单文件（离线可用）：执行 `python bundle.py` 后打开 `index.bundle.html`

### 操作方式（HTML 版）
- 放置：从模板区拖拽到 `frame`。
- 缩放：形状内上下拖动。
- 删除：长按约 650ms，移动过大则取消。
- 工具栏：播放/暂停与清空。

### 实现效果与播放（HTML 版）
- 播放指针：红色半透明竖线在 `frame` 内横向移动。
- 触发：按形状在 `frame` 的横向位置映射到循环时间触发。
- 循环：固定时长的循环（可配置），持续重复。
- 音色：与 Python 版一致的类型到音色映射。
