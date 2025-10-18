import os
import numpy as np
import matplotlib
matplotlib.use('webagg')
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Rectangle
from PIL import Image, ImageEnhance
import pygame
import time

# 初始化音频
pygame.mixer.init(frequency=44100)
# 为交叉淡入淡出预留更多通道
pygame.mixer.set_num_channels(16)

# 交叉淡入淡出与暂停淡出参数
SQUARE_FADE_MS = 250  # 正方形音频与下一个音频的交叉淡入淡出时长
PAUSE_FADE_MS = 300   # 暂停时的淡出时长
# 记录正方形轨当前使用的通道
square_current_channel = None
# 数量不平衡时的音量衰减比例（50%）
DUCK_FACTOR = 0.1

# 画布尺寸（像素坐标）
CANVAS_W, CANVAS_H = 1636, 1788

# 资源加载辅助
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RES = lambda name: os.path.join(BASE_DIR, 'resource', name)

# 音频加载与映射
def load_sound(rel_path):
    try:
        full_path = os.path.join(BASE_DIR, rel_path)
        return pygame.mixer.Sound(full_path)
    except Exception as e:
        print(f"无法加载音频文件: {rel_path}，错误: {e}，使用静音占位符")
        dummy_array = np.zeros((int(44100 * 0.2), 2), dtype=np.int16)
        return pygame.sndarray.make_sound(dummy_array)

# 预加载乐器音效
DRUM_SOUNDS = {i: load_sound(os.path.join('sounds', f'drum_{i}.mp3')) for i in range(1, 4)}
PIANO_SOUNDS = {i: load_sound(os.path.join('sounds', f'piano_{i}.mp3')) for i in range(1, 8)}
SYNTH_SOUNDS = {i: load_sound(os.path.join('sounds', f'synth_{i}.mp3')) for i in range(1, 8)}
REMOVE_SOUND = load_sound(os.path.join('sounds', 'remove.mp3'))
SCALE_SOUND = load_sound(os.path.join('sounds', 'scale.mp3'))

# 将y映射到音高区间（顶部为高音）
def get_pitch7(y_norm):
    return min(7, max(1, int(y_norm * 7) + 1))

def get_drum_pitch3(y_norm):
    return min(3, max(1, int(y_norm * 3) + 1))

# 计算音符中心y并播放对应声音
def play_note_sound(note):
    global square_current_channel
    cy = note.y + note.h * note.zoom / 2.0
    y_norm = 1.0 - float(np.clip(cy / CANVAS_H, 0.0, 1.0))  # 底部=低音、顶部=高音
    if note.kind == 'triangle':
        idx = get_drum_pitch3(y_norm)
        DRUM_SOUNDS[idx].play()
    elif note.kind == 'circle':
        idx = get_pitch7(y_norm)
        snd = PIANO_SOUNDS[idx]
        # 根据数量关系决定圆形音量（正方形多则降至DUCK_FACTOR）
        try:
            square_count = sum(1 for n in notes if n.kind == 'square')
            circle_count = sum(1 for n in notes if n.kind == 'circle')
            vol = DUCK_FACTOR if square_count > circle_count else 1.0
        except Exception:
            vol = 1.0
        ch = pygame.mixer.find_channel()
        if ch is None:
            ret_ch = snd.play()
            try:
                if ret_ch:
                    ret_ch.set_volume(vol)
            except Exception:
                pass
        else:
            try:
                ch.set_volume(vol)
            except Exception:
                pass
            ch.play(snd, fade_ms=50)
    elif note.kind == 'square':
        idx = get_pitch7(y_norm)
        snd = SYNTH_SOUNDS[idx]
        # 根据数量关系决定正方形音量（圆形多则降至50%）
        try:
            square_count = sum(1 for n in notes if n.kind == 'square')
            circle_count = sum(1 for n in notes if n.kind == 'circle')
            vol = DUCK_FACTOR if circle_count > square_count else 1.0
        except Exception:
            vol = 1.0
        try:
            # 若当前正方形音频尚未播放完，则与下一音频交叉淡入淡出
            if square_current_channel is not None and square_current_channel.get_busy():
                ch_new = pygame.mixer.find_channel()
                if ch_new is None:
                    # 无空闲通道：以淡出旧、淡入新为回退策略（同一通道无法重叠）
                    square_current_channel.fadeout(SQUARE_FADE_MS)
                    ret_ch = snd.play(fade_ms=SQUARE_FADE_MS)
                    try:
                        if ret_ch:
                            ret_ch.set_volume(vol)
                    except Exception:
                        pass
                else:
                    # 旧音频淡出，新音频淡入到新通道，实现平滑过渡
                    square_current_channel.fadeout(SQUARE_FADE_MS)
                    try:
                        ch_new.set_volume(vol)
                    except Exception:
                        pass
                    ch_new.play(snd, fade_ms=SQUARE_FADE_MS)
                    square_current_channel = ch_new
            else:
                # 正常播放：尽量使用固定通道，或寻找空闲通道，轻微淡入
                ch = square_current_channel if (square_current_channel and not square_current_channel.get_busy()) else pygame.mixer.find_channel()
                if ch is None:
                    ret_ch = snd.play()
                    try:
                        if ret_ch:
                            ret_ch.set_volume(vol)
                    except Exception:
                        pass
                else:
                    try:
                        ch.set_volume(vol)
                    except Exception:
                        pass
                    ch.play(snd, fade_ms=50)
                    square_current_channel = ch
        except Exception:
            ret_ch = snd.play()
            try:
                if ret_ch:
                    ret_ch.set_volume(vol)
            except Exception:
                pass

# 状态
is_playing = False
notes = []  # frame范围中留下的图片（音符）
dragging = None  # 正在拖拽的类型：'circle'/'triangle'/'square' 或者具体note索引
press_pos = None
press_time = None
press_pos0 = None
clear_enabled = True
anim = None
hover_tip_artist = None
hover_tip_kind = None  # 'dragit' or 'scale_remove'

# 常量与参数
FLASH_TOTAL = 0.2  # 单次闪烁总时长（秒）：0.1提升亮度+放大，0.1还原
MEASURE_DURATION = 1.0  # 一个小节总时长（秒），为原先的1/4
GROUP_DISTANCE = 2.0  # 组合音符的水平间距阈值（像素）
SCALE_MIN, SCALE_MAX = 0.5, 3.0  # 缩放范围
BRIGHTEN_FACTOR = 0.15  # 闪烁时亮度提升幅度
LONG_PRESS_SEC = 0.6  # 长按判定阈值（秒）
LONG_PRESS_MOVE_TOL = 6.0  # 长按期间允许的最大移动距离（像素）
HOVER_PAD = 12  # 悬停提示与鼠标的间距（像素坐标）
TICKS_PER_MEASURE = 8  # 每小节分成八份
TICK_DURATION = MEASURE_DURATION / TICKS_PER_MEASURE  # 八分量化的每tick时长（秒）

# 颜色辅助

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def gradient_image(w, h, start_hex, end_hex):
    c1 = np.array(hex_to_rgb(start_hex)) / 255.0
    c2 = np.array(hex_to_rgb(end_hex)) / 255.0
    t = np.linspace(0, 1, h).reshape(h, 1, 1)
    grad = c1 * (1 - t) + c2 * t
    return grad

# 图像处理：随机色相与亮度

def pil_load(name):
    return Image.open(RES(name)).convert('RGBA')

# 新增：根据类型随机选择资源变体
def random_variant_for(kind):
    if kind == 'circle':
        options = [f'Ellipse {i}.png' for i in range(1, 7)]
    elif kind == 'triangle':
        options = [f'Polygon {i}.png' for i in range(1, 7)]
    elif kind == 'square':
        options = [f'Rectangle {i}.png' for i in range(1, 7)]
    else:
        options = []
    name = np.random.choice(options) if options else None
    return pil_load(name) if name else None

def shift_hue_pil(img_rgba, shift):
    rgb = img_rgba.convert('RGB')
    hsv = rgb.convert('HSV')
    h, s, v = hsv.split()
    np_h = (np.array(h, dtype=np.uint16) + shift) % 256
    h = Image.fromarray(np_h.astype('uint8'), 'L')
    hsv2 = Image.merge('HSV', (h, s, v))
    rgb2 = hsv2.convert('RGB')
    return rgb2.convert('RGBA')

def brighten_pil(img_rgba, factor):
    enhancer = ImageEnhance.Brightness(img_rgba)
    return enhancer.enhance(1.0 + factor)

def pil_to_np(img_rgba):
    return np.array(img_rgba) / 255.0

# 提供放置/闪烁所需的结构
class Note:
    def __init__(self, kind, x, y, img_rgba, base_zoom=1.0):
        self.kind = kind  # 'circle'/'triangle'/'square'
        self.x, self.y = x, y  # 顶端-左上角坐标
        self.base_img = img_rgba
        self.light_img = brighten_pil(img_rgba, BRIGHTEN_FACTOR)
        self.zoom = base_zoom
        # 原始尺寸
        self.h = self.base_img.height
        self.w = self.base_img.width
        # 当前显示句柄（AxesImage）
        self.artist = None

    def extent(self):
        # 顶左对齐，extent=(x, x+w*zoom, y, y+h*zoom)
        return (self.x, self.x + self.w * self.zoom, self.y, self.y + self.h * self.zoom)

    def area_weight(self):
        # 用可视面积近似权重（w*h*zoom^2）
        return float(self.w * self.h) * (self.zoom ** 2)

# 初始化画布与背景
fig = plt.figure(figsize=(8, 10))
ax = fig.add_subplot(111)
ax.set_xlim(0, CANVAS_W)
ax.set_ylim(CANVAS_H, 0)  # 顶端为y=0，向下递增
ax.axis('off')

bg = gradient_image(CANVAS_W, CANVAS_H, 'E0BCF3', '7EE7EE')
ax.imshow(bg, extent=(0, CANVAS_W, 0, CANVAS_H), zorder=0, origin='lower')

# 加载UI资源
frame_img = pil_load('frame.png')
circle_img = pil_load('circle.png')
triangle_img = pil_load('triangle.png')
square_img = pil_load('square.png')
play_img = pil_load('play.png')
pause_img = pil_load('pause.png')
clear_img = pil_load('clear.png')
dragit_img = pil_load('dragit.png')
scale_remove_img = pil_load('scale_remove.png')
# 放置frame与工具栏图标（按给定顶左坐标）
# 记录各图的AxesImage以便点击检测
ui_artists = {}

def add_ui_image(name, img_rgba, x, y, z=2, alpha=1.0):
    arr = pil_to_np(img_rgba)
    h, w = img_rgba.height, img_rgba.width
    art = ax.imshow(arr, extent=(x, x + w, y, y + h), zorder=z, alpha=alpha, origin='lower')
    ui_artists[name] = {'artist': art, 'x': x, 'y': y, 'w': w, 'h': h, 'img': img_rgba}
    return art

# 按需求位置放置
add_ui_image('frame', frame_img, 16, 14, z=1)
add_ui_image('circle_tpl', circle_img, 94, 1484, z=3)
add_ui_image('triangle_tpl', triangle_img, 356, 1484, z=3)
add_ui_image('square_tpl', square_img, 618, 1484, z=3)
add_ui_image('play_btn', play_img, 1140, 1562, z=3)
add_ui_image('clear_btn', clear_img, 1332, 1582, z=3)

# frame范围（用于判断拖拽释放是否在范围内）
frame_bounds = (
    ui_artists['frame']['x'],
    ui_artists['frame']['y'],
    ui_artists['frame']['x'] + ui_artists['frame']['w'],
    ui_artists['frame']['y'] + ui_artists['frame']['h']
)
# 使用frame作为裁剪路径（数据坐标），确保音符仅在frame范围内可见
frame_clip_rect = Rectangle((frame_bounds[0], frame_bounds[1]),
                            frame_bounds[2] - frame_bounds[0],
                            frame_bounds[3] - frame_bounds[1],
                            transform=ax.transData)

# 工具函数

def point_in_extent(x, y, extent):
    x0, x1, y0, y1 = extent
    return (x0 <= x <= x1) and (y0 <= y <= y1)

def in_frame(x, y):
    x0, y0, x1, y1 = frame_bounds
    return (x0 <= x <= x1) and (y0 <= y <= y1)

def compute_hover_extent(img_rgba, x, y):
    # 默认放在鼠标右上角，必要时翻转以避免越界
    w, h = img_rgba.width, img_rgba.height
    x0 = x + HOVER_PAD
    y0 = y - h - HOVER_PAD
    if y0 < 0:
        y0 = y + HOVER_PAD
    if x0 + w > CANVAS_W:
        x0 = x - w - HOVER_PAD
    x0 = float(np.clip(x0, 0, CANVAS_W - w))
    y0 = float(np.clip(y0, 0, CANVAS_H - h))
    return (x0, x0 + w, y0, y0 + h)

def show_hover_tip(img_rgba, kind, x, y):
    global hover_tip_artist, hover_tip_kind
    arr = pil_to_np(img_rgba)
    extent = compute_hover_extent(img_rgba, x, y)
    if hover_tip_artist is None:
        hover_tip_artist = ax.imshow(arr, extent=extent, zorder=10, origin='lower')
        hover_tip_kind = kind
    else:
        if hover_tip_kind != kind:
            hover_tip_artist.set_data(arr)
            hover_tip_kind = kind
        hover_tip_artist.set_extent(extent)
        hover_tip_artist.set_alpha(1.0)
    fig.canvas.draw_idle()

def hide_hover_tip():
    global hover_tip_artist, hover_tip_kind
    if hover_tip_artist is not None:
        hover_tip_artist.set_alpha(0.0)
        fig.canvas.draw_idle()

# 交互：拖拽生成音符（随机色相）、上下缩放、清除、播放

def on_press(event):
    global dragging, press_pos, press_time, press_pos0
    if event.xdata is None or event.ydata is None:
        return
    x, y = event.xdata, event.ydata
    press_pos = (x, y)
    press_time = time.time()
    press_pos0 = (x, y)

    # 播放状态下禁用frame内调整
    # 仍允许点击pause
    # clear按钮在播放态不可操作

    # 点击检测：工具栏
    for key in ['circle_tpl', 'triangle_tpl', 'square_tpl']:
        info = ui_artists[key]
        ext = (info['x'], info['x'] + info['w'], info['y'], info['y'] + info['h'])
        if point_in_extent(x, y, ext):
            dragging = key  # 正在拖拽模板
            return

    # 播放/暂停
    info = ui_artists['play_btn']
    ext = (info['x'], info['x'] + info['w'], info['y'], info['y'] + info['h'])
    if point_in_extent(x, y, ext):
        toggle_play()
        return

    # 清除（仅普通态可用）
    info = ui_artists['clear_btn']
    ext = (info['x'], info['x'] + info['w'], info['y'], info['y'] + info['h'])
    if not is_playing and clear_enabled and point_in_extent(x, y, ext):
        clear_notes()
        return

    # 普通态下可以对frame里的note进行上下缩放
    if not is_playing:
        # 查找点击的note（从前到后检测）
        for i in reversed(range(len(notes))):
            n = notes[i]
            if point_in_extent(x, y, n.extent()):
                dragging = i  # 记录索引
                return


def on_motion(event):
    global press_pos
    if event.xdata is None or event.ydata is None:
        hide_hover_tip()
        return
    x, y = event.xdata, event.ydata

    # 悬停提示：circle模板显示拖拽图，frame中的图形显示缩放/删除图
    needs_tip = False
    # 检测是否悬停在模板（circle/triangle/square）
    for key in ['circle_tpl', 'triangle_tpl', 'square_tpl']:
        info = ui_artists.get(key)
        if info is None:
            continue
        ext_tpl = (info['x'], info['x'] + info['w'], info['y'], info['y'] + info['h'])
        if point_in_extent(x, y, ext_tpl):
            show_hover_tip(dragit_img, 'dragit', x, y)
            needs_tip = True
            break
    # 检测是否悬停在frame内现有图形
    if not needs_tip:
        for i in reversed(range(len(notes))):
            n = notes[i]
            if point_in_extent(x, y, n.extent()):
                show_hover_tip(scale_remove_img, 'scale_remove', x, y)
                needs_tip = True
                break
    if not needs_tip:
        hide_hover_tip()

    # 拖拽模板时不做预览，松开后再生成
    # 普通态下拖拽已存在note做上下缩放
    if dragging is not None and isinstance(dragging, int) and not is_playing:
        i = dragging
        n = notes[i]
        dx = x - press_pos[0]
        dy = y - press_pos[1]
        if abs(dy) > 2:  # 垂直方向灵敏度
            up = dy < 0  # 顶端为0，向下增大，所以dy<0为上划
            scale = 1.05 if up else 0.95
            new_zoom = np.clip(n.zoom * scale, SCALE_MIN, SCALE_MAX)
            n.zoom = float(new_zoom)
            # 更新显示
            if n.artist:
                n.artist.set_extent(n.extent())
            # 缩放时播放音效
            try:
                SCALE_SOUND.play()
            except Exception:
                pass
            press_pos = (x, y)
            fig.canvas.draw_idle()

KIND_LIMITS = {
    'circle': 8,
    'square': 4,
    'triangle': None,  # 不限制
}

def get_kind_limit(kind):
    return KIND_LIMITS.get(kind, None)

def count_kind(kind):
    return sum(1 for n in notes if n.kind == kind)

def remove_note_index(idx):
    """移除指定索引的 Note，并重置播放调度以避免索引错位。"""
    global notes, flash_active, track_schedule
    if 0 <= idx < len(notes):
        n = notes[idx]
        if n.artist:
            n.artist.remove()
        # 真正从列表中移除
        notes.pop(idx)
        # 索引发生变化，清理闪烁状态并重建音轨调度
        flash_active = {}
        track_schedule = None
        fig.canvas.draw_idle()

def remove_first_of_kind(kind):
    for i, n in enumerate(notes):
        if n.kind == kind:
            remove_note_index(i)
            return True
    return False

def on_release(event):
    global dragging
    if event.xdata is None or event.ydata is None:
        dragging = None
        return
    x, y = event.xdata, event.ydata

    # 松开模板，若在frame范围中，则留下一个随机资源变体
    if dragging in ['circle_tpl', 'triangle_tpl', 'square_tpl']:
        if in_frame(x, y):
            kind = dragging.split('_')[0]  # circle/triangle/square
            # 在添加之前检查并执行业务上限：达到上限则移除最早的同类
            limit = get_kind_limit(kind)
            if limit is not None and count_kind(kind) >= limit:
                remove_first_of_kind(kind)
            img_var = random_variant_for(kind)
            if img_var is None:
                # 回退使用原模板图
                img_var = ui_artists[dragging]['img']
            # 随机方向：可能镜像+任意角度旋转
            if np.random.rand() < 0.5:
                img_var = img_var.transpose(Image.FLIP_LEFT_RIGHT)
            if np.random.rand() < 0.5:
                img_var = img_var.transpose(Image.FLIP_TOP_BOTTOM)
            angle = float(np.random.uniform(0, 360))
            img_var = img_var.rotate(angle, expand=True, resample=Image.BICUBIC)
            # 随机大小：设置初始缩放到 [SCALE_MIN, SCALE_MAX]
            base_zoom = float(np.random.uniform(SCALE_MIN, SCALE_MAX))
            # 以鼠标松开点作为图形中心，换算左上角坐标
            w, h = img_var.width, img_var.height
            x0 = float(x - (w * base_zoom) / 2.0)
            y0 = float(y - (h * base_zoom) / 2.0)
            note = Note(kind, x0, y0, img_var, base_zoom=base_zoom)
            arr = pil_to_np(note.base_img)
            artist = ax.imshow(arr, extent=note.extent(), zorder=2, origin='lower')
            try:
                artist.set_clip_path(frame_clip_rect)
                artist.set_clip_on(True)
            except Exception:
                pass
            note.artist = artist
            notes.append(note)
            # 放置时播放对应音符声音（按中心y映射）
            try:
                play_note_sound(note)
            except Exception:
                pass
            # 新增/删除后需要重建音轨调度
            track_schedule = None
            fig.canvas.draw_idle()
        dragging = None
    elif isinstance(dragging, int):
        idx = dragging
        # 长按删除：时间超过阈值且移动距离不超过容差
        held = (time.time() - press_time) if press_time else 0.0
        dx = x - press_pos0[0] if press_pos0 else 0.0
        dy = y - press_pos0[1] if press_pos0 else 0.0
        dist = (dx * dx + dy * dy) ** 0.5
        if held >= LONG_PRESS_SEC and dist <= LONG_PRESS_MOVE_TOL:
            remove_note_index(idx)
            try:
                REMOVE_SOUND.play()
            except Exception:
                pass
        dragging = None

# 清除frame中的图片

def clear_notes():
    global notes
    # 清空时播放删除音效
    try:
        REMOVE_SOUND.play()
    except Exception:
        pass
    for n in notes:
        if n.artist:
            n.artist.remove()
    notes = []
    fig.canvas.draw_idle()

# 播放/暂停

def toggle_play():
    global is_playing, anim, clear_enabled
    is_playing = not is_playing

    # 切换play按钮图像
    pb = ui_artists['play_btn']
    if is_playing:
        # 切到pause
        arr = pil_to_np(pause_img)
        pb['artist'].set_data(arr)
        clear_enabled = False
        ui_artists['clear_btn']['artist'].set_alpha(0.8)
        start_animation()
    else:
        # 切回play
        arr = pil_to_np(play_img)
        pb['artist'].set_data(arr)
        clear_enabled = True
        ui_artists['clear_btn']['artist'].set_alpha(1.0)
        stop_animation()
    fig.canvas.draw_idle()

# 分组与时长权重调度

def build_groups():
    # 根据水平“中心点到组最右边缘”的距离聚合为组合音符：
    # 若当前元素的中心点与组内“最右边缘”之间的间距 <= GROUP_DISTANCE，则归为同组。
    # 限制每组最多包含3个元素；从左到右第4个符合条件的元素开始新组。
    pts = []  # 每项: (索引, 左, 右, 中心, y)
    for i, n in enumerate(notes):
        left = n.x
        right = n.x + n.w * n.zoom
        center = (left + right) / 2.0
        pts.append((i, left, right, center, n.y))
    # 按中心从左到右排序
    pts.sort(key=lambda t: t[3])

    groups = []
    current = []
    current_right = None
    for i, left, right, center, y in pts:
        if not current:
            current = [i]
            current_right = right
        else:
            gap = center - current_right  # 当前元素中心与当前组最右边缘的间距
            if gap <= GROUP_DISTANCE:
                # 符合间距条件，尝试加入当前组；若已达3个，则开启新组
                if len(current) < 3:
                    current.append(i)
                    current_right = max(current_right, right)
                else:
                    groups.append(current)
                    current = [i]
                    current_right = right
            else:
                # 不符合间距，结束当前组，开启新组
                groups.append(current)
                current = [i]
                current_right = right
    if current:
        groups.append(current)

    # 计算权重（组合取最大note的面积权重）
    weights = []
    for g in groups:
        w = max(notes[i].area_weight() for i in g)
        weights.append(w)
    # 计算每组的开始时间（按权重分配MEASURE_DURATION）
    total_w = max(sum(weights), 1e-6)
    durations = [MEASURE_DURATION * (w / total_w) for w in weights]
    starts = [0.0]
    for d in durations[:-1]:
        starts.append(starts[-1] + d)
    return groups, starts, durations

# 动画：按分配的时长顺序让各组闪烁
play_time = 0.0
play_time_prev = 0.0
last_tick_idx = -1
flash_active = {}
track_schedule = None

def start_animation():
    global anim, play_time, play_time_prev, last_tick_idx, flash_active, track_schedule
    play_time = 0.0
    play_time_prev = 0.0
    last_tick_idx = -1
    flash_active = {}
    track_schedule = build_track_schedule()
    anim = FuncAnimation(fig, animate, interval=50, blit=False)


def stop_animation():
    global anim, flash_active, square_current_channel
    if anim:
        anim.event_source.stop()
        anim = None
    # 暂停时淡出所有正在播放的音频
    try:
        n = pygame.mixer.get_num_channels()
        for i in range(n):
            pygame.mixer.Channel(i).fadeout(PAUSE_FADE_MS)
    except Exception:
        pass
    square_current_channel = None
    # 恢复所有正在闪烁的图片到基态
    if flash_active:
        for idx in list(flash_active.keys()):
            note = notes[idx]
            arr = pil_to_np(note.base_img)
            if note.artist:
                note.artist.set_data(arr)
                note.artist.set_extent(note.extent())
        flash_active.clear()
    fig.canvas.draw_idle()

# 闪烁效果应用/恢复

def apply_flash(note, phase):
    # phase in [0, FLASH_TOTAL]
    # 前0.1s：提升亮度并放大到1.1倍；后0.1s：回归
    if phase < FLASH_TOTAL / 2:
        # 提升亮度
        arr = pil_to_np(note.light_img)
        note.artist.set_data(arr)
        # 放大到1.1倍
        z = note.zoom * 1.1
        note.artist.set_extent((note.x, note.x + note.w * z, note.y, note.y + note.h * z))
    else:
        # 回归原图与原尺寸
        arr = pil_to_np(note.base_img)
        note.artist.set_data(arr)
        note.artist.set_extent(note.extent())


def build_track_schedule():
    """为三条音轨构建每小节触发表（每tick最多一个同轨音符；如超出tick数量将发生末尾饱和）。"""
    kinds = ['triangle', 'square', 'circle']
    n_ticks = max(1, int(MEASURE_DURATION / TICK_DURATION + 1e-9))
    schedule = {k: [[] for _ in range(n_ticks)] for k in kinds}
    for k in kinds:
        items = []
        for i, n in enumerate(notes):
            if n.kind == k:
                left = n.x
                right = n.x + n.w * n.zoom
                center = (left + right) / 2.0
                items.append((i, center))
        if not items:
            continue
        items.sort(key=lambda t: t[1])
        indices = [i for (i, _) in items]
        weights = np.array([notes[i].area_weight() for i in indices], dtype=float)
        total_w = float(weights.sum())
        if total_w <= 1e-12:
            weights = np.ones_like(weights)
            total_w = float(weights.sum())
        durations = (MEASURE_DURATION * (weights / total_w)).astype(float)
        starts = [0.0]
        for d in durations[:-1]:
            starts.append(starts[-1] + float(d))
        tick_indices = []
        prev_tick = -1
        for st in starts:
            # 先 floor 量化，避免 round 导致 4 -> 截断到 3 的碰撞
            t = int(np.floor(st / TICK_DURATION + 1e-9))
            # 保证严格递增（先递增再截断）
            if t <= prev_tick:
                t = prev_tick + 1
            # 截断到合法范围
            if t >= n_ticks:
                t = n_ticks - 1
            tick_indices.append(t)
            prev_tick = t
        for idx, ti in zip(indices, tick_indices):
            if ti >= 0 and ti < n_ticks:
                # 寻找从该tick开始的第一个空tick，避免同轨同tick同时闪烁
                t_cur = ti
                assigned = False
                while t_cur < n_ticks:
                    if not schedule[k][t_cur]:
                        schedule[k][t_cur].append(idx)
                        assigned = True
                        break
                    t_cur += 1
                if not assigned:
                    # 回退到更早的空tick（保持本小节唯一触发），如仍无空位则本小节跳过
                    t_cur = 0
                    while t_cur < ti:
                        if not schedule[k][t_cur]:
                            schedule[k][t_cur].append(idx)
                            assigned = True
                            break
                        t_cur += 1
                    if not assigned:
                        pass
            else:
                pass
    return schedule


def animate(frame):
    global play_time, play_time_prev, last_tick_idx, flash_active, track_schedule
    if not is_playing:
        return []

    # 确保有音轨调度
    if track_schedule is None:
        track_schedule = build_track_schedule()

    dt = 0.05
    old_time = play_time
    new_time = play_time + dt
    wrap = new_time >= MEASURE_DURATION

    if wrap:
        # 小节结束，复位并开始新一轮
        new_time = new_time - MEASURE_DURATION
        play_time_prev = 0.0
        # 清空闪烁状态，保证每小节独立
        if flash_active:
            for idx in list(flash_active.keys()):
                note = notes[idx]
                arr = pil_to_np(note.base_img)
                if note.artist:
                    note.artist.set_data(arr)
                    note.artist.set_extent(note.extent())
            flash_active.clear()
        # 新小节重新量化音轨调度，并重置tick索引
        track_schedule = build_track_schedule()
        last_tick_idx = -1
    else:
        play_time_prev = old_time

    play_time = new_time
    # 在每小节开始（或启动播放）时触发tick 0，避免第一个音符缺失
    if last_tick_idx < 0 and track_schedule is not None:
        tick_idx = 0
        for kind in ['triangle', 'square', 'circle']:
            sched = track_schedule.get(kind, [])
            if not sched:
                continue
            tick_notes = sched[tick_idx] if tick_idx < len(sched) else []
            for idx in tick_notes:
                if 0 <= idx < len(notes) and notes[idx].kind == kind:
                    flash_active[idx] = 0.0
                    play_note_sound(notes[idx])
        last_tick_idx = tick_idx

    # 量化tick触发：当跨过新的1/8小节tick时，按音轨播放并闪烁
    n_ticks = max(1, int(MEASURE_DURATION / TICK_DURATION + 1e-9))
    old_tick = int(np.floor((old_time if not wrap else 0.0) / TICK_DURATION))
    new_tick = int(np.floor(new_time / TICK_DURATION))
    if new_tick != old_tick:
        tick_idx = int(np.clip(new_tick, 0, n_ticks - 1))
        for kind in ['triangle', 'square', 'circle']:
            sched = track_schedule.get(kind, [])
            if not sched:
                continue
            tick_notes = sched[tick_idx] if tick_idx < len(sched) else []
            for idx in tick_notes:
                if 0 <= idx < len(notes) and notes[idx].kind == kind:
                    flash_active[idx] = 0.0
                    play_note_sound(notes[idx])
        last_tick_idx = tick_idx

    # 更新已触发的闪烁进度，并在完成后复位
    new_flash_active = {}
    for idx, phase in flash_active.items():
        new_phase = phase + dt
        if new_phase < FLASH_TOTAL:
            apply_flash(notes[idx], new_phase)
            new_flash_active[idx] = new_phase
        else:
            # 闪烁结束，恢复基态
            note = notes[idx]
            arr = pil_to_np(note.base_img)
            if note.artist:
                note.artist.set_data(arr)
                note.artist.set_extent(note.extent())
    flash_active = new_flash_active

    fig.canvas.draw_idle()
    return []

# 事件绑定
fig.canvas.mpl_connect('button_press_event', on_press)
fig.canvas.mpl_connect('motion_notify_event', on_motion)
fig.canvas.mpl_connect('button_release_event', on_release)

plt.show()