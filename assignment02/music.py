import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Circle, Polygon, Rectangle
import pygame
import numpy as np
from datetime import datetime
import math
import os

# 初始化pygame for audio
pygame.mixer.init(frequency=44100)

# 加载音频文件函数
def load_sound(file_path):
    """尝试加载音频文件，如果失败则创建静音占位符"""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(base_dir, file_path)
        return pygame.mixer.Sound(full_path)
    except Exception as e:
        print(f"无法加载音频文件: {file_path}，错误: {e}，使用静音占位符")
        # 创建静音音效作为占位符（二维数组表示立体声）
        dummy_array = np.zeros((int(44100 * 0.2), 2), dtype=np.int16)
        return pygame.sndarray.make_sound(dummy_array)

# 创建占位音效（操作音效）
bremove_sound = load_sound('sounds/remove.mp3')  # 删除音效
up_sound = load_sound('sounds/scale.mp3')  # 放大音效
down_sound = load_sound('sounds/scale.mp3')  # 缩小音效（可以使用相同的音效）
play_sound = load_sound('sounds/play.mp3')  # 播放音效
pause_sound = load_sound('sounds/pause.mp3')  # 暂停音效

# 乐器音效
# 将鼓音效改为按竖直位置分区的三个文件
drum_sounds = {i: load_sound(f'sounds/drum_{i}.mp3') for i in range(1, 4)}

# 预加载不同音高的钢琴和合成器音效
piano_sounds = {i: load_sound(f'sounds/piano_{i}.mp3') for i in range(1, 8)}
synth_sounds = {i: load_sound(f'sounds/synth_{i}.mp3') for i in range(1, 8)}

# 马卡龙色系
colors = ['#AEC6CF', '#F7CAC9', '#B2D8B2', '#FFF2CC', '#FFCCE5', '#C1E1C1', '#FFD9DA']

# 创建图形界面，调整比例以避免纵向压缩
# 创建图形界面
fig = plt.figure(figsize=(8, 10))  # 调整为更适合纵向显示的比例
gs = plt.GridSpec(3, 1, height_ratios=[8, 2, 2])  # 增加底栏高度
ax_main = fig.add_subplot(gs[0])  # 主画布
ax_bottom = fig.add_subplot(gs[2])  # 底部工具栏放在最底部

# 设置坐标轴范围
ax_main.set_xlim(0, 1)
ax_main.set_ylim(0, 1)
ax_bottom.set_xlim(0, 1)
ax_bottom.set_ylim(0, 1)
ax_bottom.set_aspect('equal', adjustable='box')

# 设置背景色为马卡龙色
ax_main.set_facecolor('#FFE4E1')
ax_bottom.set_facecolor('#DDA0DD')

# 创建底栏模板和按钮
template_circle = Circle((0.15, 0.5), 0.25, color=np.random.choice(colors))
template_triangle = Polygon([[0.35, 0.25], [0.45, 0.75], [0.25, 0.75]], closed=True, color=np.random.choice(colors))
template_square = Rectangle((0.5, 0.25), 0.2, 0.5, color=np.random.choice(colors))
play_button = Rectangle((0.75, 0.15), 0.1, 0.7, color='green')
clear_button = Rectangle((0.9, 0.15), 0.1, 0.7, color='red')

# 添加到底栏
ax_bottom.add_patch(template_circle)
ax_bottom.add_patch(template_triangle)
ax_bottom.add_patch(template_square)
ax_bottom.add_patch(play_button)
ax_bottom.add_patch(clear_button)

# 添加按钮文字
ax_bottom.text(0.75, 0.5, 'Play/Pause', ha='center')
ax_bottom.text(0.9, 0.5, 'Clear', ha='center')

# 隐藏坐标轴刻度
ax_main.axis('off')
ax_bottom.axis('off')

# 状态变量
shapes = []  # 放置的图形列表
shapes_info = []  # 存储每个图形的信息（类型、位置、大小、颜色等）
dragging = None
press_time = None
press_pos = None
is_playing = False
anim = None

# 当前播放状态变量
current_group_index = 0
animation_frame = 0
groups = []  # 音符组合

# 不同数量音符对应的4/4拍节奏型
rhythms = {
    1: [0],  # 全音符
    2: [0, 2],  # 二分音符
    3: [0, 1.33, 2.67],  # 附点二分音符
    4: [0, 1, 2, 3],  # 四分音符
    5: [0, 0.75, 1.5, 2.25, 3],  # 四分音符 + 八分音符
    6: [0, 0.67, 1.33, 2, 2.67, 3.33],  # 附点四分音符
    7: [0, 0.57, 1.14, 1.71, 2.29, 2.86, 3.43],  # 七连音
    8: [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],  # 八分音符
    9: [0, 0.44, 0.89, 1.33, 1.78, 2.22, 2.67, 3.11, 3.56],  # 九连音
    10: [0, 0.4, 0.8, 1.2, 1.6, 2, 2.4, 2.8, 3.2, 3.6],  # 十分音符
    12: [0, 0.33, 0.67, 1, 1.33, 1.67, 2, 2.33, 2.67, 3, 3.33, 3.67],  # 八分音符三连音
    16: [0, 0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2, 2.25, 2.5, 2.75, 3, 3.25, 3.5, 3.75]  # 十六分音符
}

def get_pitch(y):
    """将y坐标映射到1-7的音高"""
    # 将y坐标从0-1范围映射到1-7的整数
    return min(7, max(1, int(y * 7) + 1))

# 新增：三角形鼓音高映射到1-3区
def get_drum_pitch(y):
    """将y坐标映射到1-3的鼓音区"""
    return min(3, max(1, int(y * 3) + 1))

def get_duration(size):
    """根据图形大小计算音符持续时间"""
    return 0.1 + size * 0.9  # 0.1-1秒范围

def get_drum_type(size):
    """根据三角形大小决定鼓的类型"""
    if size > 0.07:
        return 'bass'  # 使用圆形鼓音效
    elif size > 0.04:
        return 'snare'  # 使用三角形鼓音效
    else:
        return 'cymbal'  # 使用正方形鼓音效

def rotate_polygon(points, angle, center):
    """旋转多边形点"""
    theta = math.radians(angle)
    rotated_points = []
    for point in points:
        x, y = point
        x_rot = center[0] + math.cos(theta) * (x - center[0]) - math.sin(theta) * (y - center[1])
        y_rot = center[1] + math.sin(theta) * (x - center[0]) + math.cos(theta) * (y - center[1])
        rotated_points.append([x_rot, y_rot])
    return rotated_points

# 事件处理函数
def on_press(event):
    global dragging, press_time, press_pos
    
    if event.xdata is None or event.ydata is None:
        return
        
    press_time = datetime.now()
    press_pos = (event.xdata, event.ydata)
    
    # 检查是否点击了底栏
    if event.inaxes == ax_bottom:
        # 检查是否点击了播放/暂停按钮
        if play_button.contains_point((event.x, event.y)):
            toggle_play()
        # 检查是否点击了清除按钮
        elif clear_button.contains_point((event.x, event.y)):
            clear_canvas()
        # 检查是否点击了圆形模板
        elif template_circle.contains_point((event.x, event.y)):
            dragging = 'circle'
        # 检查是否点击了三角形模板
        elif template_triangle.contains_point((event.x, event.y)):
            dragging = 'triangle'
        # 检查是否点击了正方形模板
        elif template_square.contains_point((event.x, event.y)):
            dragging = 'square'
    
    # 检查是否点击了主画布上的图形（仅在非播放状态）
    elif event.inaxes == ax_main and not is_playing:
        for i, shape in enumerate(shapes):
            if shape.contains_point((event.x, event.y)):
                dragging = shape
                break

def on_motion(event):
    global press_pos
    
    if event.xdata is None or event.ydata is None:
        return
        
    if dragging and not is_playing:
        if isinstance(dragging, str):  # 拖拽模板
            # 可以在这里添加阴影预览，暂时省略
            pass
        elif dragging:  # 拖拽已有图形
            dx, dy = event.xdata - press_pos[0], event.ydata - press_pos[1]
            if abs(dy) > 0.005:  # 降低阈值，提高灵敏度
                # 向上滑动放大，向下滑动缩小
                up = dy > 0
                scale_shape(dragging, up)
                # 立即更新press_pos以避免连续快速缩放
                press_pos = (event.xdata, event.ydata)

def on_release(event):
    global dragging
    
    if event.xdata is None or event.ydata is None:
        dragging = None
        return
        
    # 检查是否有移动（拖拽）
    is_dragging = False
    if dragging and not isinstance(dragging, str) and press_pos:
        # 计算移动距离
        move_distance = math.sqrt((event.xdata - press_pos[0])**2 + (event.ydata - press_pos[1])**2)
        is_dragging = move_distance > 0.01  # 移动超过这个距离视为拖拽
    
    # 如果是从底栏拖拽到主画布
    if dragging and isinstance(dragging, str) and event.inaxes == ax_main:
        place_shape(dragging, event.xdata, event.ydata)
    # 如果是长按已有图形且没有拖拽（只是点击）
    elif dragging and not isinstance(dragging, str) and not is_dragging and (datetime.now() - press_time).total_seconds() > 0.5:
        remove_shape(dragging)
    
    dragging = None
    fig.canvas.draw_idle()

def place_shape(shape_type, x, y):
    """在画布上放置图形"""
    color = np.random.choice(colors)
    rotation = np.random.uniform(0, 360)
    size = 0.05  # 默认大小
    new_shape = None
    
    # 根据类型创建不同的图形
    if shape_type == 'circle':
        new_shape = Circle((x, y), size, color=color)
    elif shape_type == 'triangle':
        # 创建三角形的基本点
        points = [[x, y + size], [x - size, y - size], [x + size, y - size]]
        # 旋转三角形
        points = rotate_polygon(points, rotation, (x, y))
        new_shape = Polygon(points, color=color)
    elif shape_type == 'square':
        # 创建正方形的基本点
        points = [[x - size, y - size], [x + size, y - size], [x + size, y + size], [x - size, y + size]]
        # 旋转正方形
        points = rotate_polygon(points, rotation, (x, y))
        new_shape = Polygon(points, color=color)
    
    if new_shape:
        # 添加到画布
        ax_main.add_patch(new_shape)
        shapes.append(new_shape)
        
        # 存储图形信息
        shapes_info.append({
            'type': shape_type,
            'center': (x, y),
            'size': size,
            'color': color,
            'rotation': rotation
        })
        
        # 限制图形数量为16个
        if len(shapes) > 16:
            old_shape = shapes.pop(0)
            shapes_info.pop(0)
            old_shape.remove()
        
        # 播放图形对应的声音
        play_shape_sound(shapes_info[-1])
        fig.canvas.draw()

def scale_shape(shape, up):
    """缩放图形并播放相应的音效"""
    # 找到图形在shapes列表中的索引
    index = shapes.index(shape)
    
    # 获取当前图形信息
    info = shapes_info[index]
    current_size = info['size']
    
    # 计算新的大小（限制在合理范围内）
    scale_factor = 1.1 if up else 0.9
    new_size = current_size * scale_factor
    
    # 确保大小在合理范围内
    if new_size < 0.02 or new_size > 0.15:
        return
    
    # 删除旧图形
    shape.remove()
    
    # 创建新大小的图形
    x, y = info['center']
    color = info['color']
    rotation = info['rotation']
    new_shape = None
    
    if info['type'] == 'circle':
        new_shape = Circle((x, y), new_size, color=color)
    elif info['type'] == 'triangle':
        points = [[x, y + new_size], [x - new_size, y - new_size], [x + new_size, y - new_size]]
        points = rotate_polygon(points, rotation, (x, y))
        new_shape = Polygon(points, color=color)
    elif info['type'] == 'square':
        points = [[x - new_size, y - new_size], [x + new_size, y - new_size], 
                  [x + new_size, y + new_size], [x - new_size, y + new_size]]
        points = rotate_polygon(points, rotation, (x, y))
        new_shape = Polygon(points, color=color)
    
    if new_shape:
        # 更新图形和信息
        ax_main.add_patch(new_shape)
        shapes[index] = new_shape
        shapes_info[index]['size'] = new_size
        
        # 播放相应的音效
        if up:
            up_sound.play()
        else:
            down_sound.play()
            
        fig.canvas.draw()

def remove_shape(shape):
    """移除图形并播放音效"""
    if shape in shapes:
        index = shapes.index(shape)
        shapes.remove(shape)
        shapes_info.pop(index)
        shape.remove()
        bremove_sound.play()
        fig.canvas.draw()

def clear_canvas():
    """清除画布上的所有内容"""
    global shapes, shapes_info
    
    # 移除所有图形
    for s in shapes[:]:
        s.remove()
    
    # 清空列表
    shapes = []
    shapes_info = []
    
    fig.canvas.draw()

def toggle_play():
    global is_playing, anim, groups, current_group_index, animation_frame
    
    is_playing = not is_playing
    
    if is_playing:
        # 按x坐标排序图形
        sorted_shapes = sorted(enumerate(shapes_info), key=lambda x: x[1]['center'][0])
        
        # 将水平距离相近的图形分组
        groups = []
        current_group = []
        prev_x = None
        
        for idx, info in sorted_shapes:
            x = info['center'][0]
            if prev_x is None or x - prev_x < 0.05:  # 距离小于0.05视为一组
                current_group.append(idx)
            else:
                groups.append(current_group)
                current_group = [idx]
            prev_x = x
        
        # 添加最后一组
        if current_group:
            groups.append(current_group)
        
        # 初始化播放状态
        current_group_index = 0
        animation_frame = 0
        
        # 开始动画
        anim = FuncAnimation(fig, animate_play, interval=50, blit=False, cache_frame_data=False)
    else:
        # 停止动画
        if anim:
            anim.event_source.stop()
            anim = None

def animate_play(frame):
    """播放状态下的动画函数"""
    global current_group_index, animation_frame
    
    # 一个完整循环持续1小节，每小节4拍
    beats_per_measure = 4
    measures = 1
    total_beats = beats_per_measure * measures
    
    # 获取当前的节奏型
    num_groups = len(groups)
    if num_groups > 0:
        # 选择合适的节奏型
        rhythm_key = min(num_groups, max(rhythms.keys()))
        rhythm = rhythms.get(rhythm_key, rhythms[4])  # 默认使用4拍节奏
        
        # 计算当前应该播放哪个组
        frame_time = frame * 0.05  # 每帧50毫秒
        beat_progress = frame_time % total_beats
        
        # 找到当前应该播放的组
        active_groups = []
        for i, beat_time in enumerate(rhythm):
            if abs(beat_progress - beat_time) < 0.1:  # 允许100ms的误差
                group_idx = i % num_groups
                active_groups.append(groups[group_idx])
        
        # 为每个活跃组播放声音并跳动
        for group in active_groups:
            # 同时播放组内所有图形的声音
            for idx in group:
                info = shapes_info[idx]
                play_shape_sound(info)
            
            # 让组内的图形跳动
            jump_shapes(group)
    
    animation_frame += 1
    return []

def play_shape_sound(shape_info):
    """根据图形信息播放声音"""
    shape_type = shape_info['type']
    y = shape_info['center'][1]
    if shape_type == 'triangle':
        drum_index = get_drum_pitch(y)
        drum_sounds[drum_index].play()
    elif shape_type == 'circle':
        pitch = get_pitch(y)
        piano_sounds[pitch].play()
    elif shape_type == 'square':
        pitch = get_pitch(y)
        synth_sounds[pitch].play()

# 添加跳动动画状态跟踪
jumping_shapes = {}

# 颜色变浅的辅助函数
def lighten_color(hex_color, factor=0.7):
    # 将十六进制颜色转换为RGB
    hex_color = hex_color.lstrip('#')
    rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    # 计算变浅的RGB值
    r, g, b = rgb
    r = min(255, int(r + (255 - r) * factor))
    g = min(255, int(g + (255 - g) * factor))
    b = min(255, int(b + (255 - b) * factor))
    # 转换回十六进制
    return f'#{r:02x}{g:02x}{b:02x}'

def jump_shapes(shape_indices):
    """让指定索引的图形跳动：微弱放大，颜色变浅，0.2秒内完成"""
    for idx in shape_indices:
        if idx < len(shapes) and idx < len(shapes_info):
            # 标记此图形开始跳动动画
            jumping_shapes[idx] = {'frame': 0, 'original_info': shapes_info[idx].copy()}

# 在animate_play函数中处理跳动动画
def animate_play(frame):
    """播放状态下的动画函数"""
    global current_group_index, animation_frame
    
    # 一个完整循环持续1小节，每小节4拍
    beats_per_measure = 4
    measures = 1
    total_beats = beats_per_measure * measures
    
    # 获取当前的节奏型
    num_groups = len(groups)
    if num_groups > 0:
        # 选择合适的节奏型
        rhythm_key = min(num_groups, max(rhythms.keys()))
        rhythm = rhythms.get(rhythm_key, rhythms[4])  # 默认使用4拍节奏
        
        # 计算当前应该播放哪个组
        frame_time = frame * 0.05  # 每帧50毫秒
        beat_progress = frame_time % total_beats
        
        # 找到当前应该播放的组
        active_groups = []
        for i, beat_time in enumerate(rhythm):
            if abs(beat_progress - beat_time) < 0.1:  # 允许100ms的误差
                group_idx = i % num_groups
                active_groups.append(groups[group_idx])
        
        # 为每个活跃组播放声音并跳动
        for group in active_groups:
            # 同时播放组内所有图形的声音
            for idx in group:
                info = shapes_info[idx]
                play_shape_sound(info)
            
            # 让组内的图形开始跳动动画
            jump_shapes(group)
    
    # 处理正在跳动的图形动画
    jump_frames_total = 4  # 0.2秒，每帧50ms，共4帧
    shapes_to_remove = []
    
    for idx, jump_info in jumping_shapes.items():
        if idx < len(shapes) and idx < len(shapes_info):
            frame_num = jump_info['frame']
            if frame_num < jump_frames_total:
                # 计算当前帧的动画进度
                progress = frame_num / jump_frames_total
                original_info = jump_info['original_info']
                current_info = shapes_info[idx]
                shape = shapes[idx]
                
                # 移除旧图形
                shape.remove()
                
                # 计算当前帧的大小和颜色
                # 微弱放大：最大1.1倍
                scale_factor = 1.0 + 0.1 * math.sin(progress * math.pi)
                current_size = original_info['size'] * scale_factor
                
                # 颜色变浅：根据进度变化
                original_color = original_info['color']
                lightened_color = lighten_color(original_color, 0.7 * math.sin(progress * math.pi))
                
                # 创建新的图形
                x, y = current_info['center']
                rotation = original_info['rotation']
                new_shape = None
                
                if original_info['type'] == 'circle':
                    new_shape = Circle((x, y), current_size, color=lightened_color)
                elif original_info['type'] == 'triangle':
                    points = [[x, y + current_size], [x - current_size, y - current_size], [x + current_size, y - current_size]]
                    points = rotate_polygon(points, rotation, (x, y))
                    new_shape = Polygon(points, color=lightened_color)
                elif original_info['type'] == 'square':
                    points = [[x - current_size, y - current_size], [x + current_size, y - current_size], 
                              [x + current_size, y + current_size], [x - current_size, y + current_size]]
                    points = rotate_polygon(points, rotation, (x, y))
                    new_shape = Polygon(points, color=lightened_color)
                
                # 更新图形
                if new_shape:
                    ax_main.add_patch(new_shape)
                    shapes[idx] = new_shape
                    
                    # 更新动画帧计数
                    jumping_shapes[idx]['frame'] += 1
            else:
                # 动画结束，恢复原始状态
                shape = shapes[idx]
                shape.remove()
                
                # 恢复原始大小和颜色
                original_info = jump_info['original_info']
                x, y = original_info['center']
                size = original_info['size']
                color = original_info['color']
                rotation = original_info['rotation']
                
                new_shape = None
                if original_info['type'] == 'circle':
                    new_shape = Circle((x, y), size, color=color)
                elif original_info['type'] == 'triangle':
                    points = [[x, y + size], [x - size, y - size], [x + size, y - size]]
                    points = rotate_polygon(points, rotation, (x, y))
                    new_shape = Polygon(points, color=color)
                elif original_info['type'] == 'square':
                    points = [[x - size, y - size], [x + size, y - size], 
                              [x + size, y + size], [x - size, y + size]]
                    points = rotate_polygon(points, rotation, (x, y))
                    new_shape = Polygon(points, color=color)
                
                if new_shape:
                    ax_main.add_patch(new_shape)
                    shapes[idx] = new_shape
                    
                # 标记为移除
                shapes_to_remove.append(idx)
    
    # 移除已完成动画的图形
    for idx in shapes_to_remove:
        if idx in jumping_shapes:
            del jumping_shapes[idx]
    
    animation_frame += 1
    return []

# Connect events
fig.canvas.mpl_connect('button_press_event', on_press)
fig.canvas.mpl_connect('motion_notify_event', on_motion)
fig.canvas.mpl_connect('button_release_event', on_release)

plt.show()