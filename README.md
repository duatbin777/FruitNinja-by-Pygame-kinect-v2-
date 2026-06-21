# Kinect Fruit Ninja - Dual Hand Edition

> Python + PyKinect2 + Pygame 实现的 Kinect V2 体感水果忍者游戏

## Overview

A dual-hand Fruit Ninja game built with Kinect V2 and Pygame. Supports both Kinect body tracking and mouse control modes, featuring colorful skeleton visualization, combo system, and particle effects.

## Features

- **Dual-hand tracking**: Left and right hands control two knives with different colors (Ice Blue R / Magenta L)
- **Mouse mode**: Left button controls right knife, right button controls left knife
- **Colorful skeleton**: Rainbow gradient human skeleton rendering
- **Kinect camera background**: Real-time camera feed as game background
- **Combo system**: Consecutive fruit slicing grants bonus points
- **Particle effects**: Juice splashes, knife flashes, sparkle effects
- **Multiple fruits**: Apple, Banana, Peach, Watermelon, Strawberry + Bomb
- **Best score**: Auto-saved to `best.txt`
- **5 difficulty levels**: Gradually increasing difficulty over time

## Requirements

- Python 3.6+
- Pygame
- PyKinect2
- NumPy
- Kinect V2 sensor (optional, falls back to mouse mode)

```bash
pip install pygame numpy pykinect2
```

## Project Structure

```
FruitNinja/
├── main.py              # Entry point, Kinect manager, UI, main loop
├── game_config.py       # Constants, particle system, image loading
├── game_logic.py        # Core logic: fruits, chips, launcher, knives, controller
├── best.txt             # Best score record
├── images/              # Image assets (fruits, UI)
│   ├── apple.png / apple-1.png / apple-2.png
│   ├── banana.png / banana-1.png / banana-2.png
│   ├── peach.png / peach-1.png / peach-2.png
│   ├── watermelon.png / watermelon-1.png / watermelon-2.png
│   ├── strawberry.png / strawberry-1.png / strawberry-2.png
│   └── boom.png
└── sound/               # Sound assets
    ├── boom.mp3
    ├── menu.mp3
    ├── over.mp3
    ├── splatter.mp3
    ├── start.mp3
    └── throw.mp3
```

## Controls

| Key | Action |
|-----|--------|
| `SPACE` | Start / Restart game |
| `R` | Restart anytime |
| `S` | Toggle skeleton display |
| `C` | Toggle camera background |
| `M` | Toggle Mouse / Kinect mode |
| `ESC` | Quit game |

## Architecture

### Module Overview

| File | Responsibility |
|------|---------------|
| `main.py` | Kinect management, UI rendering, main loop, event handling |
| `game_config.py` | Constants, particle system, image loading, skeleton colors |
| `game_logic.py` | Fruits, chips, launcher, dual knives, game controller |

### Key Classes

| Class | Description |
|-------|-------------|
| `KinectManager` | Kinect V2 initialization, skeleton tracking, color frame capture |
| `GameUI` | Menu, score, HP, combo, GameOver UI rendering |
| `Fruit` | Fruit entity with image rendering, rotation, collision detection |
| `FruitChip` | Fruit slice fragments with rotation and alpha fade |
| `FruitLauncher` | Fruit spawner with 5 difficulty levels |
| `PlayerKnife` | Single knife with trail rendering, glow effects, color schemes |
| `GameController` | Game state management, scoring, combo, HP |
| `ParticleSystem` | Particle effects (juice, knife flash, sparkle) |

### Game Flow

1. Initialize Kinect (fallback to mouse if unavailable)
2. Display menu screen
3. Press `SPACE` to start
4. Fruits launch from bottom, player slices with both hands (or mouse)
5. Hitting a bomb costs 1 HP, missing a fruit costs 1 HP
6. HP reaches 0 -> Game Over, best score saved

## How to Run

```bash
python main.py
```

## Source Code

<details>
<summary><b>main.py</b> - Main Program (click to expand)</summary>

```python
# -*- coding: utf-8 -*-
"""
Kinect管理、UI渲染、主循环、事件处理
依赖：game_config.py, game_logic.py
"""
import math
import time
import ctypes
import pygame
import random
import numpy
from pykinect2 import PyKinectRuntime, PyKinectV2
from pykinect2.PyKinectV2 import *

from game_config import (
    WIDTH, HEIGHT, COLOR_W, COLOR_H, SCALE_X, SCALE_Y,
    COLORS, BONE_CONNECTIONS, JOINT_COLORS, ParticleSystem, Particle
)
from game_logic import (
    FruitLauncher, PlayerKnife, GameController, FruitChip
)

# ==================== Kinect====================
class KinectManager:
    def __init__(self):
        self.kinect = None
        self.initialized = False
        self.bodies = None
        self.tracked_body_index = None
        self.got_body_frame = False
        self.debug_counter = 0
        # 彩色帧相关
        self.color_surface = None
        self._color_array = None

    def initialize(self):
        print("[INFO] Initializing Kinect (this may take 2-5 seconds)...")
        try:
            self.kinect = PyKinectRuntime.PyKinectRuntime(
                PyKinectV2.FrameSourceTypes_Body
                | PyKinectV2.FrameSourceTypes_Depth
                | PyKinectV2.FrameSourceTypes_BodyIndex
                | PyKinectV2.FrameSourceTypes_Color
            )
            self.initialized = True
            print("[INFO] Kinect initialized. Warming up...")
            time.sleep(2.0)
            print("[INFO] Ready.")
            return True
        except Exception as e:
            print(f"[ERR] Failed to initialize Kinect: {e}")
            print("[INFO] Falling back to mouse control mode.")
            return False

    def joint_to_screen(self, joint):
        try:
            pt = self.kinect.body_joint_to_color_space(joint)
        except Exception:
            return None
        if pt.x is None or pt.y is None:
            return None
        if math.isinf(pt.x) or math.isinf(pt.y) or math.isnan(pt.x) or math.isnan(pt.y):
            return None
        x = int(pt.x * SCALE_X)
        y = int(pt.y * SCALE_Y)
        if x < -2000 or x > 5000 or y < -2000 or y > 5000:
            return None
        return (x, y)

    def get_color_frame(self):
        """获取最新的彩色帧作为背景"""
        if not self.initialized or self.kinect is None:
            return None
        try:
            if self.kinect.has_new_color_frame():
                frame = self.kinect.get_last_color_frame()
                if frame is not None:
                    # 将 BGR -> RGB 并缩放到窗口大小
                    self._color_array = frame.reshape((COLOR_H, COLOR_W, 4))
                    self._color_array = self._color_array[:, :, :3][:, :, ::-1]  # BGRA -> RGB
                    # 缩放
                    import pygame.transform as transform
                    surf = pygame.surfarray.make_surface(
                        numpy.swapaxes(self._color_array, 0, 1))
                    self.color_surface = transform.scale(surf, (WIDTH, HEIGHT))
            return self.color_surface
        except Exception as e:
            if self.debug_counter % 300 == 0:
                print(f"[WARN] Color frame error: {e}")
            return self.color_surface

    def get_both_hands(self):
        """
        获取双手位置
        返回: (right_hand_pos, left_hand_pos) 或 (None, None)
        """
        if not self.initialized or self.kinect is None:
            return None, None
        body_frame = None
        try:
            if self.kinect.has_new_body_frame():
                body_frame = self.kinect.get_last_body_frame()
        except Exception:
            pass
        if body_frame is None:
            try:
                body_frame = self.kinect.get_last_body_frame()
            except Exception:
                return None, None
        if body_frame is None:
            return None, None
        try:
            bodies = body_frame.bodies
            if not self.got_body_frame:
                self.got_body_frame = True
                print("[INFO] First body frame received!")
            tracked_idx = None
            for i in range(self.kinect.max_body_count):
                if bodies[i] is not None and bodies[i].is_tracked:
                    tracked_idx = i
                    break
            if tracked_idx is not None:
                self.tracked_body_index = tracked_idx
                body = bodies[tracked_idx]
                joints = body.joints
                right_pos = None
                left_pos = None
                # 右手 - 尝试 HandRight -> HandTipRight -> ThumbRight
                for jtype in [JointType_HandRight, JointType_HandTipRight, JointType_ThumbRight]:
                    j = joints[jtype]
                    if j.TrackingState != PyKinectV2.TrackingState_NotTracked:
                        pos = self.joint_to_screen(j)
                        if pos is not None:
                            right_pos = pos
                            break
                # 左手 - 尝试 HandLeft -> HandTipLeft -> ThumbLeft
                for jtype in [JointType_HandLeft, JointType_HandTipLeft, JointType_ThumbLeft]:
                    j = joints[jtype]
                    if j.TrackingState != PyKinectV2.TrackingState_NotTracked:
                        pos = self.joint_to_screen(j)
                        if pos is not None:
                            left_pos = pos
                            break
                return right_pos, left_pos
        except Exception as e:
            self.debug_counter += 1
            if self.debug_counter % 60 == 0:
                print(f"[ERR] Processing body frame: {e}")
        return None, None

    def get_body_for_drawing(self):
        if not self.initialized or self.kinect is None:
            return None, None
        try:
            body_frame = self.kinect.get_last_body_frame()
            if body_frame is None:
                return None, None
            bodies = body_frame.bodies
            if self.tracked_body_index is not None:
                idx = self.tracked_body_index
                if bodies[idx] is not None and bodies[idx].is_tracked:
                    return bodies[idx].joints, bodies[idx]
            for i in range(self.kinect.max_body_count):
                if bodies[i] is not None and bodies[i].is_tracked:
                    self.tracked_body_index = i
                    return bodies[i].joints, bodies[i]
        except Exception:
            pass
        return None, None

    def close(self):
        if self.kinect is not None:
            try:
                self.kinect.close()
            except Exception:
                pass

# ==================== 彩色骨架绘制 ====================
def draw_skeleton_colorful(screen, joints, body, kinect_mgr):
    """绘制彩虹渐变人体骨架"""
    if joints is None:
        return
    # ---- 画骨头连线（渐变色）----
    for joint_a, joint_b in BONE_CONNECTIONS:
        j1 = joints[joint_a]
        j2 = joints[joint_b]
        if j1.TrackingState == PyKinectV2.TrackingState_NotTracked:
            continue
        if j2.TrackingState == PyKinectV2.TrackingState_NotTracked:
            continue
        p1 = kinect_mgr.joint_to_screen(j1)
        p2 = kinect_mgr.joint_to_screen(j2)
        if p1 is None or p2 is None:
            continue
        # 取两端关节的颜色做渐变
        c1 = JOINT_COLORS.get(joint_a, (200, 200, 200))
        c2 = JOINT_COLORS.get(joint_b, (200, 200, 200))
        if (j1.TrackingState == PyKinectV2.TrackingState_Inferred or
                j2.TrackingState == PyKinectV2.TrackingState_Inferred):
            # 推断关节用暗淡版本
            c1 = tuple(int(c * 0.4) for c in c1)
            c2 = tuple(int(c * 0.4) for c in c2)
            width = 2
        else:
            width = 4
        try:
            # 绘制带发光效果的线
            # 外发光
            glow_color = tuple(int(c * 0.3) for c in c1)
            pygame.draw.line(screen, glow_color, p1, p2, width + 4)
            # 主体线
            pygame.draw.line(screen, c1, p1, p2, width)
        except Exception:
            pass
    # ---- 画关节点（彩色发光圆点）----
    for jid in range(PyKinectV2.JointType_Count):
        j = joints[jid]
        if j.TrackingState == PyKinectV2.TrackingState_NotTracked:
            continue
        p = kinect_mgr.joint_to_screen(j)
        if p is None:
            continue
        base_color = JOINT_COLORS.get(jid, (200, 200, 200))
        if j.TrackingState == PyKinectV2.TrackingState_Tracked:
            col = base_color
            r = 7
            # 发光效果
            glow_surf = pygame.Surface((30, 30), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (*col, 40), (15, 15), 14)
            pygame.draw.circle(glow_surf, (*col, 80), (15, 15), 10)
            screen.blit(glow_surf, (p[0] - 15, p[1] - 15))
        else:
            col = tuple(int(c * 0.7) for c in base_color)
            r = 5
        try:
            pygame.draw.circle(screen, col, p, r)
            # 关节点白色内核
            pygame.draw.circle(screen, (255, 255, 255), p, max(2, r // 2))
        except Exception:
            pass

# ==================== UI====================
class GameUI:
    def __init__(self):
        self.font_large = pygame.font.Font(None, 52)
        self.font_medium = pygame.font.Font(None, 38)
        self.font_small = pygame.font.Font(None, 24)
        self.font_tiny = pygame.font.Font(None, 20)

    def draw_life_bar(self, screen, hp, max_hp=3):
        bar_x = WIDTH - 135
        bar_y = 12
        for i in range(max_hp):
            x = bar_x + i * 40
            if i < hp:
                # 心形
                self._draw_heart(screen, x + 14, bar_y + 14, 13, (255, 55, 55))
            else:
                # 灰心
                self._draw_heart(screen, x + 14, bar_y + 14, 13, (70, 70, 70))

    def _draw_heart(self, screen, cx, cy, size, color):
        """画心形"""
        pygame.draw.circle(screen, color, (cx - size // 3, cy - size // 3), size // 2)
        pygame.draw.circle(screen, color, (cx + size // 3, cy - size // 3), size // 2)
        points = [
            (cx - size, cy - size // 4),
            (cx + size, cy - size // 4),
            (cx, cy + size),
        ]
        pygame.draw.polygon(screen, color, points)

    def draw_score(self, screen, score, best_score=0):
        # 分数带阴影
        shadow = self.font_medium.render(f"Score: {score}", True, (30, 30, 30))
        screen.blit(shadow, (17, 17))
        text = self.font_medium.render(f"Score: {score}", True, COLORS['white'])
        screen.blit(text, (15, 15))
        # 历史最高分
        if best_score > 0:
            best_shadow = self.font_small.render(f"BEST: {best_score}", True, (40, 25, 0))
            screen.blit(best_shadow, (17, 37))
            best_text = self.font_small.render(f"BEST: {best_score}", True, (255, 179, 78))
            screen.blit(best_text, (15, 35))

    def draw_combo(self, screen, combo, combo_timer):
        """显示连击数"""
        if combo > 1:
            alpha = min(1.0, combo_timer / 1.5)
            scale = 1.0 + min(combo * 0.05, 0.5)
            font_size = int(32 * scale)
            combo_font = pygame.font.Font(None, font_size)
            # 连击文字颜色随combo变化
            hue_shift = min(combo * 20, 200)
            combo_color = (
                min(255, 100 + hue_shift),
                max(50, 255 - hue_shift),
                200
            )
            text = combo_font.render(f"{combo}x COMBO!", True, combo_color)
            rect = text.get_rect(center=(WIDTH // 2, 90))
            # 发光背景
            glow_w, glow_h = rect.width + 20, rect.height + 10
            glow_surf = pygame.Surface((glow_w, glow_h), pygame.SRCALPHA)
            pygame.draw.rect(glow_surf, (*combo_color[:3], int(40 * alpha)),
                           glow_surf.get_rect(), border_radius=8)
            screen.blit(glow_surf, (rect.x - 10, rect.y - 5))
            screen.blit(text, rect)

    def draw_menu(self, screen, kinect_ok):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))
        # 标题 - 彩虹渐变效果
        t = time.time()
        title_colors = [
            (255, int(100 + 50 * math.sin(t * 2)), 50),
            (255, 200, int(50 + 50 * math.sin(t * 2 + 1))),
        ]
        title = self.font_large.render("KINECT FRUIT NINJA", True, (255, 210, 60))
        title_shadow = self.font_large.render("KINECT FRUIT NINJA", True, (80, 40, 0))
        title_rect = title.get_rect(center=(WIDTH // 2, HEIGHT // 3 - 10))
        screen.blit(title_shadow, (title_rect.x + 3, title_rect.y + 3))
        screen.blit(title, title_rect)
        sub = self.font_medium.render("Dual-Hand Edition", True, (180, 180, 220))
        sub_rect = sub.get_rect(center=(WIDTH // 2, HEIGHT // 3 + 40))
        screen.blit(sub, sub_rect)
        sub2 = self.font_small.render("Use BOTH hands to slice fruits!", True, (150, 220, 255))
        sub2_rect = sub2.get_rect(center=(WIDTH // 2, HEIGHT // 3 + 75))
        screen.blit(sub2, sub2_rect)
        if kinect_ok:
            status = "Kinect Connected - Dual-hand tracking active!"
            status_color = (100, 255, 150)
        else:
            status = "Kinect Not Found - Mouse Control Mode"
            status_color = (255, 180, 100)
        hint = self.font_small.render(status, True, status_color)
        hint_rect = hint.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 30))
        screen.blit(hint, hint_rect)
        # 手部示意
        self._draw_hand_icons(screen, kinect_ok)
        controls = self.font_small.render("SPACE Start | R Restart | S Skeleton | M Mouse | ESC Quit",
                                         True, (150, 150, 170))
        ctrl_rect = controls.get_rect(center=(WIDTH // 2, HEIGHT - 65))
        screen.blit(controls, ctrl_rect)
        self._draw_decorative_fruits(screen)

    def _draw_hand_icons(self, screen, kinect_ok):
        """绘制双手图标"""
        cx_l, cx_r = WIDTH // 2 - 80, WIDTH // 2 + 80
        cy = HEIGHT // 2 + 95
        # 左手图标 L
        pygame.draw.circle(screen, (255, 80, 200), (cx_l, cy), 22, 3)
        l_text = self.font_medium.render("L", True, (255, 80, 200))
        screen.blit(l_text, (cx_l - 8, cy - 14))
        lbl = self.font_tiny.render("Left Hand", True, (200, 150, 220))
        screen.blit(lbl, (cx_l - 26, cy + 28))
        # 右手图标 R
        pygame.draw.circle(screen, (80, 200, 255), (cx_r, cy), 22, 3)
        r_text = self.font_medium.render("R", True, (80, 200, 255))
        screen.blit(r_text, (cx_r - 8, cy - 14))
        rbl = self.font_tiny.render("Right Hand", True, (150, 200, 255))
        screen.blit(rbl, (cx_r - 28, cy + 28))
        # 中间连接线
        pygame.draw.line(screen, (100, 100, 120), (cx_l + 22, cy), (cx_r - 22, cy), 2)

    def draw_gameover(self, screen, score, elapsed, max_combo, best_score=0):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 210))
        screen.blit(overlay, (0, 0))
        go_text = self.font_large.render("GAME OVER", True, (255, 60, 60))
        go_shadow = self.font_large.render("GAME OVER", True, (80, 0, 0))
        go_rect = go_text.get_rect(center=(WIDTH // 2, HEIGHT // 3 - 10))
        screen.blit(go_shadow, (go_rect.x + 3, go_rect.y + 3))
        screen.blit(go_text, go_rect)
        score_text = self.font_medium.render(f"Final Score: {score}", True, (255, 255, 255))
        score_rect = score_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 10))
        screen.blit(score_text, score_rect)
        # 历史最高分
        if best_score > 0:
            is_new_best = (score >= best_score)
            best_color = (255, 215, 0) if is_new_best else (255, 179, 78)
            best_label = "NEW BEST!" if is_new_best else f"BEST: {best_score}"
            best_text = self.font_medium.render(best_label, True, best_color)
            best_rect = best_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 22))
            screen.blit(best_text, best_rect)
        time_text = self.font_small.render(f"Survived: {elapsed:.1f}s", True, (180, 180, 180))
        time_rect = time_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 55))
        screen.blit(time_text, time_rect)
        combo_text = self.font_small.render(f"Max Combo: {max_combo}x", True, (255, 200, 50))
        combo_rect = combo_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 80))
        screen.blit(combo_text, combo_rect)
        restart = self.font_small.render("Press R to Restart | ESC to Quit",
                                       True, (160, 160, 180))
        restart_rect = restart.get_rect(center=(WIDTH // 2, HEIGHT - 65))
        screen.blit(restart, restart_rect)

    def _draw_decorative_fruits(self, screen):
        t = time.time()
        fruits_deco = [
            (WIDTH * 0.15, HEIGHT * 0.68, 32, (220, 40, 40)),
            (WIDTH * 0.3, HEIGHT * 0.74, 26, (255, 230, 0)),
            (WIDTH * 0.5, HEIGHT * 0.72, 30, (255, 140, 0)),
            (WIDTH * 0.7, HEIGHT * 0.73, 28, (128, 0, 128)),
            (WIDTH * 0.85, HEIGHT * 0.67, 34, (255, 180, 180)),
        ]
        for i, (fx, fy, fr, fc) in enumerate(fruits_deco):
            offset_y = math.sin(t * 2.5 + i * 1.2) * 10
            offset_x = math.cos(t * 1.8 + i * 0.9) * 5
            # 阴影
            shadow_surf = pygame.Surface((fr * 2 + 8, 8), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow_surf, (0, 0, 0, 30), (0, 0, fr * 2 + 8, 8))
            screen.blit(shadow_surf, (int(fx + offset_x - fr - 4), int(fy + offset_y + fr + 3)))
            # 水果
            pygame.draw.circle(screen, fc, (int(fx + offset_x), int(fy + int(offset_y))), fr)
            hl = tuple(min(255, c + 55) for c in fc)
            pygame.draw.circle(screen, hl,
                             (int(fx + offset_x - fr * 0.25), int(fy + int(offset_y) - fr * 0.25)),
                             max(3, int(fr * 0.25)))

# ==================== 背景渲染 ====================
def draw_background(screen, kinect_mgr, show_camera):
    """绘制背景 - 可选Kinect彩色帧或默认动态背景"""
    if show_camera and kinect_mgr.initialized:
        color_surf = kinect_mgr.get_color_frame()
        if color_surf is not None:
            # 半透明叠加，让游戏元素更清晰
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 60))
            screen.blit(color_surf, (0, 0))
            screen.blit(overlay, (0, 0))
            return
    # 默认动态渐变背景
    t = time.time()
    # 深色渐变背景
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        r = int(20 + 15 * math.sin(t * 0.3 + ratio * 2))
        g = int(20 + 10 * math.sin(t * 0.25 + ratio * 3))
        b = int(35 + 20 * math.sin(t * 0.35 + ratio * 2.5))
        pygame.draw.line(screen, (r, g, b), (0, y), (WIDTH, y))
    # 网格装饰
    grid_alpha = int(25 + 10 * math.sin(t * 0.5))
    for gx in range(0, WIDTH, 60):
        pygame.draw.line(screen, (grid_alpha, grid_alpha, grid_alpha + 15), (gx, 0), (gx, HEIGHT), 1)
    for gy in range(0, HEIGHT, 60):
        pygame.draw.line(screen, (grid_alpha, grid_alpha, grid_alpha + 15), (0, gy), (WIDTH, gy), 1)

# ==================== 主程序入口 ====================
def main():
    pygame.init()
    pygame.mixer.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Kinect Fruit Ninja - Dual Hand Edition")
    clock = pygame.time.Clock()
    # ========== 初始化系统 ==========
    ui = GameUI()
    controller = GameController()
    launcher = FruitLauncher()
    particles = ParticleSystem()
    chips = []
    kinect = KinectManager()
    # ========== 双刀初始化 ==========
    knife_right = PlayerKnife(style='right')   # 右手刀 - 冰蓝
    knife_left = PlayerKnife(style='left')     # 左手刀 - 品红
    all_knives = [knife_right, knife_left]
    kinect_ok = kinect.initialize()
    # ========== 游戏变量 ==========
    start_time = time.time()
    mouse_control = not kinect_ok
    show_skeleton = True
    show_camera = True  # 显示Kinect彩色背景
    print("=" * 55)
    print("   KINECT FRUIT NINJA - Dual Hand Python Edition")
    print("=" * 55)
    print(f"   Kinect: {'Connected' if kinect_ok else 'Not Found (Mouse)'}")
    print("   Features:")
    print("     - Dual-hand knife control (R + L)")
    print("     - Color skeleton visualization")
    print("     - Kinect color camera background")
    print("     - Combo system")
    print("   Controls:")
    print("     SPACE - Start/Restart")
    print("     R     - Restart anytime")
    print("     S     - Toggle skeleton")
    print("     C     - Toggle camera background")
    print("     M     - Toggle Mouse/Kinect")
    print("     ESC   - Quit")
    print("=" * 55)
    # ========== 主循环 ==========
    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        dt = min(dt, 0.05)
        current_time = time.time()
        elapsed = current_time - start_time
        # ---------- 事件处理 ----------
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    if controller.game_state in ('menu', 'gameover'):
                        controller.start_game()
                        launcher.start()
                        particles.particles.clear()
                        chips.clear()
                        start_time = time.time()
                elif event.key == pygame.K_r:
                    controller.start_game()
                    launcher.start()
                    particles.particles.clear()
                    chips.clear()
                    start_time = time.time()
                elif event.key == pygame.K_s:
                    show_skeleton = not show_skeleton
                    print(f"Skeleton: {'ON' if show_skeleton else 'OFF'}")
                elif event.key == pygame.K_c:
                    show_camera = not show_camera
                    print(f"Camera BG: {'ON' if show_camera else 'OFF'}")
                elif event.key == pygame.K_m:
                    mouse_control = not mouse_control
                    print(f"Control: {'Mouse' if mouse_control else 'Kinect Dual-Hand'}")
        # ---------- 输入处理 ----------
        if mouse_control:
            # 鼠标模式：左键控制右手刀，右键控制左手刀
            mouse_buttons = pygame.mouse.get_pressed()
            mx, my = pygame.mouse.get_pos()
            if mouse_buttons[0]:  # 左键 -> 右手刀
                knife_right.set_position(mx, my)
            else:
                knife_right.set_inactive()
            if mouse_buttons[2]:  # 右键 -> 左手刀
                knife_left.set_position(mx, my)
            else:
                knife_left.set_inactive()
        else:
            # Kinect 双手模式
            right_pos, left_pos = kinect.get_both_hands()
            if right_pos is not None:
                knife_right.set_position(right_pos[0], right_pos[1])
            else:
                knife_right.set_inactive()
            if left_pos is not None:
                knife_left.set_position(left_pos[0], left_pos[1])
            else:
                knife_left.set_inactive()
        # 更新所有刀
        for knife in all_knives:
            knife.update(dt)
        # ---------- 游戏逻辑更新 ----------
        controller.update_combo(dt)
        if controller.game_state == 'playing':
            launcher.update(dt)
            # 碰撞检测：双刀都可以切水果
            for knife in all_knives:
                if not knife.valid:
                    continue
                for fruit in launcher.fruits[:]:
                    if not fruit.active or fruit.cut:
                        continue
                    if fruit.check_collision(knife.x, knife.y):
                        new_chips = fruit.do_cut(knife.vx, knife.vy)
                        if fruit.is_bomb:
                            controller.reduce_hp()
                            particles.emit_fruit_juice(fruit.x, fruit.y, (80, 80, 80), 40)
                            for _ in range(35):
                                angle = random.uniform(0, 2 * math.pi)
                                speed = random.uniform(150, 450)
                                p = Particle(fruit.x, fruit.y, (255, 150, 0),
                                          velocity=(math.cos(angle) * speed,
                                                   math.sin(angle) * speed),
                                          radius=random.randint(4, 11),
                                          lifetime=random.uniform(0.5, 1.3))
                                particles.particles.append(p)
                        else:
                            controller.add_score(fruit.score_value)
                            particles.emit_fruit_juice(fruit.x, fruit.y, fruit.juice_color)
                            particles.emit_knife_flash(fruit.x, fruit.y, knife.x, knife.y,
                                                      knife.color_flash)
                            particles.emit_slice_sparkle(fruit.x, fruit.y, knife.color_sparkle)
                            chips.extend(new_chips)
                        break  # 一个水果只切一次
            # 检测漏掉的水果
            for fruit in launcher.fruits[:]:
                if not fruit.active and not fruit.cut:
                    if not fruit.is_bomb:
                        controller.reduce_hp()
                        particles.emit_lose_mark(fruit.x, HEIGHT - 30)
                    if fruit in launcher.fruits:
                        launcher.fruits.remove(fruit)
            for chip in chips[:]:
                if not chip.update(dt):
                    chips.remove(chip)
            particles.update(dt)
        elif controller.game_state == 'gameover':
            particles.update(dt)
            for chip in chips[:]:
                if not chip.update(dt):
                    chips.remove(chip)
        # ========== 渲染 ==========
        # 背景（支持Kinect彩色帧）
        draw_background(screen, kinect, show_camera)
        if controller.game_state == 'menu':
            # ---- 菜单画面 ----
            ui.draw_menu(screen, kinect_ok)
            if kinect_ok and show_skeleton:
                joints, body = kinect.get_body_for_drawing()
                if joints is not None:
                    draw_skeleton_colorful(screen, joints, body, kinect)
        elif controller.game_state == 'playing':
            # ---- 游戏中画面 ----
            # 水果
            for fruit in launcher.fruits:
                fruit.draw(screen)
            # 碎片
            for chip in chips:
                chip.draw(screen)
            # 粒子
            particles.draw(screen)
            # 双刀
            for knife in all_knives:
                knife.draw(screen)
            # 彩色骨架
            if kinect_ok and show_skeleton:
                joints, body = kinect.get_body_for_drawing()
                if joints is not None:
                    draw_skeleton_colorful(screen, joints, body, kinect)
            # UI
            ui.draw_life_bar(screen, controller.hp)
            ui.draw_score(screen, controller.score, controller.best_score)
            ui.draw_combo(screen, controller.combo, controller.combo_timer)
            level_text = ui.font_small.render(
                f"Lv.{launcher.current_level + 1} | Time: {launcher.timer:.1f}s",
                True, (150, 150, 170))
            screen.blit(level_text, (15, 52))
            mode_str = "MOUSE" if mouse_control else "KINECT"
            mode_color = (255, 200, 100) if mouse_control else (100, 220, 255)
            mode_text = ui.font_small.render(f"Mode: {mode_str}", True, mode_color)
            screen.blit(mode_text, (WIDTH - 115, 52))
            # 双刀状态指示
            status_y = 76
            for knife in all_knives:
                if knife.active:
                    status_color = knife.color_main if knife.valid else (180, 180, 180)
                    status_text = f"{knife.label}:{'ACTIVE' if knife.valid else 'READY'}"
                else:
                    status_color = (80, 80, 80)
                    status_text = f"{knife.label}:--"
                st = ui.font_tiny.render(status_text, True, status_color)
                screen.blit(st, (15 if knife == knife_right else (WIDTH - 75 if knife == knife_left else 15), status_y))
                status_y += 18
        elif controller.game_state == 'gameover':
            for fruit in launcher.fruits:
                fruit.draw(screen)
            for chip in chips:
                chip.draw(screen)
            particles.draw(screen)
            ui.draw_gameover(screen, controller.score, launcher.timer, controller.max_combo, controller.best_score)
        # FPS
        fps_text = ui.font_tiny.render(f"FPS: {int(clock.get_fps())}", True, (80, 80, 90))
        screen.blit(fps_text, (15, HEIGHT - 22))
        pygame.display.flip()
    # ========== 清理 ==========
    print("\n[INFO] Cleaning up...")
    launcher.stop()
    kinect.close()
    pygame.quit()
    print("[INFO] Exited cleanly. Thanks for playing!")

if __name__ == '__main__':
    main()
```

</details>

<details>
<summary><b>game_config.py</b> - Game Configuration (click to expand)</summary>

```python
# -*- coding: utf-8 -*-
"""
游戏基础配置与通用组件
常量定义、配置类、粒子系统、图片加载、基础数据结构
"""
import math
import random
import pygame
import numpy
from pykinect2 import PyKinectRuntime, PyKinectV2
from pykinect2.PyKinectV2 import *

# ================== numpy 补丁（必须在 pykinect2 前导入） ==================
if not hasattr(numpy, 'object'):
    numpy.object = object
if not hasattr(numpy, 'int'):
    numpy.int = int
if not hasattr(numpy, 'float'):
    numpy.float = float
if not hasattr(numpy, 'bool'):
    numpy.bool = bool

# ==================== 游戏配置 ====================
class GameConfig:
    CHIP_SPEED_FAC = 3.0
    KNIFE_SPEED_FAC = 10000.0
    KNIFE_SPEED_MIN = 20.0
    KNIFE_SPEED_2_FRUIT_FAC = 0.1
    GRAVITY = 980.0

config = GameConfig()

# ==================== 屏幕设置 ====================
WIDTH, HEIGHT = 960, 540
COLOR_W, COLOR_H = 1920, 1080
SCALE_X = WIDTH / COLOR_W
SCALE_Y = HEIGHT / COLOR_H

# ==================== 颜色定义 ====================
COLORS = {
    'bg': (20, 20, 30),
    'white': (255, 255, 255),
}

# ==================== 图片资源路径 ====================
IMAGE_DIR = "./images/"
IMAGE_CACHE = {}  # 图片缓存

def load_image(name):
    """加载并缓存图片"""
    if name not in IMAGE_CACHE:
        try:
            IMAGE_CACHE[name] = pygame.image.load(IMAGE_DIR + name)
        except Exception as e:
            print(f"[WARN] Failed to load image {name}: {e}")
            IMAGE_CACHE[name] = None
    return IMAGE_CACHE[name]

# ==================== 水果类型定义 ====================
FRUIT_TYPES = [
    {'name': 'apple',       'radius': 40, 'color': (220, 40, 40),   'juice_color': (200, 30, 30),  'score': 10, 'image': 'apple.png',       'half_left': 'apple-1.png',       'half_right': 'apple-2.png'},
    {'name': 'banana',      'radius': 38, 'color': (255, 220, 0),   'juice_color': (240, 200, 0),  'score': 10, 'image': 'banana.png',      'half_left': 'banana-1.png',      'half_right': 'banana-2.png'},
    {'name': 'peach',       'radius': 38, 'color': (255, 180, 180), 'juice_color': (255, 150, 150),'score': 10, 'image': 'peach.png',       'half_left': 'peach-1.png',       'half_right': 'peach-2.png'},
    {'name': 'watermelon',  'radius': 50, 'color': (50, 180, 50),   'juice_color': (200, 30, 30),  'score': 10, 'image': 'watermelon.png',  'half_left': 'watermelon-1.png',  'half_right': 'watermelon-2.png'},
    {'name': 'strawberry',  'radius': 32, 'color': (220, 40, 80),    'juice_color': (200, 30, 60),  'score': 10, 'image': 'strawberry.png',  'half_left': 'strawberry-1.png',  'half_right': 'strawberry-2.png'},
    {'name': 'bomb',        'radius': 40, 'color': (30, 30, 30),    'juice_color': (80, 80, 80),   'score': -50,'image': 'boom.png',        'half_left': 'boom.png',           'half_right': 'boom.png'},
]

# ==================== 骨架连线定义 ====================
BONE_CONNECTIONS = [
    (JointType_Head, JointType_Neck),
    (JointType_Neck, JointType_SpineShoulder),
    (JointType_SpineShoulder, JointType_SpineMid),
    (JointType_SpineMid, JointType_SpineBase),
    (JointType_SpineShoulder, JointType_ShoulderRight),
    (JointType_SpineShoulder, JointType_ShoulderLeft),
    (JointType_ShoulderRight, JointType_ElbowRight),
    (JointType_ElbowRight, JointType_WristRight),
    (JointType_WristRight, JointType_HandRight),
    (JointType_HandRight, JointType_HandTipRight),
    (JointType_HandRight, JointType_ThumbRight),
    (JointType_ShoulderLeft, JointType_ElbowLeft),
    (JointType_ElbowLeft, JointType_WristLeft),
    (JointType_WristLeft, JointType_HandLeft),
    (JointType_HandLeft, JointType_HandTipLeft),
    (JointType_HandLeft, JointType_ThumbLeft),
    (JointType_SpineBase, JointType_HipRight),
    (JointType_SpineBase, JointType_HipLeft),
    (JointType_HipRight, JointType_KneeRight),
    (JointType_KneeRight, JointType_AnkleRight),
    (JointType_AnkleRight, JointType_FootRight),
    (JointType_HipLeft, JointType_KneeLeft),
    (JointType_KneeLeft, JointType_AnkleLeft),
    (JointType_AnkleLeft, JointType_FootLeft),
]

# 彩色骨架
# 彩色骨架配色方案 - 渐变彩虹色
JOINT_COLORS = {
    JointType_Head:          (255, 80, 80),
    JointType_Neck:          (255, 120, 80),
    JointType_SpineShoulder: (255, 160, 60),
    JointType_SpineMid:      (255, 200, 40),
    JointType_SpineBase:     (220, 220, 40),
    JointType_ShoulderRight: (180, 220, 40),
    JointType_ElbowRight:    (140, 220, 60),
    JointType_WristRight:    (100, 220, 100),
    JointType_HandRight:     (60, 210, 150),
    JointType_HandTipRight:  (40, 190, 200),
    JointType_ThumbRight:    (60, 160, 230),
    JointType_ShoulderLeft:  (100, 130, 255),
    JointType_ElbowLeft:     (140, 100, 255),
    JointType_WristLeft:     (180, 70, 240),
    JointType_HandLeft:      (220, 50, 200),
    JointType_HandTipLeft:   (250, 50, 160),
    JointType_ThumbLeft:     (255, 80, 120),
    JointType_HipRight:      (200, 200, 60),
    JointType_HipLeft:       (200, 180, 80),
    JointType_KneeRight:     (180, 200, 80),
    JointType_KneeLeft:      (160, 210, 100),
    JointType_AnkleRight:    (140, 220, 140),
    JointType_AnkleLeft:     (120, 220, 180),
    JointType_FootRight:     (100, 210, 210),
    JointType_FootLeft:      (80, 190, 230),
}

# ==================== 粒子系统 ====================
class Particle:
    def __init__(self, x, y, color, velocity=None, radius=None, lifetime=None):
        self.x = x
        self.y = y
        self.color = color
        self.vx = velocity[0] if velocity else random.uniform(-200, 200)
        self.vy = velocity[1] if velocity else random.uniform(-300, -50)
        self.radius = radius or random.randint(2, 6)
        self.lifetime = lifetime or random.uniform(0.3, 0.8)
        self.max_lifetime = self.lifetime
        self.gravity = random.uniform(400, 800)

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += self.gravity * dt
        self.lifetime -= dt
        return self.lifetime > 0

    def draw(self, screen):
        alpha = max(0, self.lifetime / self.max_lifetime)
        r = int(self.radius * alpha)
        if r > 0:
            color = tuple(int(c * alpha) for c in self.color[:3])
            pygame.draw.circle(screen, color, (int(self.x), int(self.y)), r)

class ParticleSystem:
    def __init__(self):
        self.particles = []

    def emit_fruit_juice(self, x, y, color, count=25):
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(80, 250)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed - 100
            p = Particle(x, y, color, velocity=(vx, vy),
                        radius=random.randint(3, 8),
                        lifetime=random.uniform(0.4, 1.0))
            self.particles.append(p)

    def emit_knife_flash(self, x1, y1, x2, y2, knife_color=(255, 255, 255)):
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2
        for _ in range(12):
            angle = math.atan2(y2 - y1, x2 - x1) + random.uniform(-0.6, 0.6)
            speed = random.uniform(150, 400)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            p = Particle(mid_x, mid_y, knife_color, velocity=(vx, vy),
                        radius=random.randint(2, 6),
                        lifetime=random.uniform(0.1, 0.25))
            self.particles.append(p)

    def emit_slice_sparkle(self, x, y, knife_color):
        """切中时的火花特效"""
        for _ in range(15):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(100, 350)
            p = Particle(x, y, knife_color,
                        velocity=(math.cos(angle) * speed, math.sin(angle) * speed - 80),
                        radius=random.randint(2, 5),
                        lifetime=random.uniform(0.15, 0.4))
            self.particles.append(p)

    def emit_lose_mark(self, x, y):
        for offset in [(-8, -8), (-4, -4), (0, 0), (4, 4), (8, 8),
                       (-8, 8), (-4, 4), (4, -4), (8, -8)]:
            p = Particle(x + offset[0], y + offset[1], (255, 80, 80),
                        velocity=(offset[0] * 10, offset[1] * 10 - 50),
                        radius=3, lifetime=1.5)
            self.particles.append(p)

    def update(self, dt):
        self.particles = [p for p in self.particles if p.update(dt)]

    def draw(self, screen):
        for p in self.particles:
            p.draw(screen)
```

</details>

<details>
<summary><b>game_logic.py</b> - Core Game Logic (click to expand)</summary>

```python
# -*- coding: utf-8 -*-
"""
游戏核心逻辑
水果、碎片、发射器、玩家刀、游戏控制器
依赖：game_config.py
"""
import math
import random
import time
import pygame
from game_config import (
    config, WIDTH, HEIGHT, FRUIT_TYPES, load_image, ParticleSystem
)


# ==================== 水果碎片 ====================
class FruitChip:
    def __init__(self, x, y, color, juice_color, vx, vy, radius, is_left_half=True, fruit_name=None):
        self.x = x
        self.y = y
        self.color = color
        self.juice_color = juice_color
        self.vx = vx
        self.vy = vy
        self.radius = radius * 0.7
        self.is_left_half = is_left_half
        self.rotation = random.uniform(0, 360)
        self.rot_speed = random.uniform(-360, 360)
        self.lifetime = 3.0
        self.offset_x = radius * 0.3 if is_left_half else -radius * 0.3
        self.fruit_name = fruit_name

        # 加载切片图片
        self.chip_image = None
        if fruit_name:
            for ft in FRUIT_TYPES:
                if ft['name'] == fruit_name:
                    if is_left_half:
                        img_name = ft.get('half_left', ft['image'])
                    else:
                        img_name = ft.get('half_right', ft['image'])
                    self.chip_image = load_image(img_name)
                    break

        # 碎片内部果汁滴
        self.juice_drops = []
        for _ in range(random.randint(3, 7)):
            self.juice_drops.append({
                'ox': random.uniform(-radius * 0.5, radius * 0.5),
                'oy': random.uniform(-radius * 0.5, radius * 0.5),
                'r': random.randint(2, 5),
            })

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += config.GRAVITY * dt
        self.rotation += self.rot_speed * dt
        self.lifetime -= dt
        return self.lifetime > 0 and self.y < HEIGHT + 100

    def draw(self, screen):
        alpha = min(1.0, self.lifetime)
        pos = (int(self.x + self.offset_x), int(self.y))
        # 如果有切片图片，使用图片绘制
        if self.chip_image:
            # 旋转图片
            rotated = pygame.transform.rotate(self.chip_image, self.rotation)
            rect = rotated.get_rect(center=(int(self.x), int(self.y)))

            # 应用透明度
            if alpha < 1.0:
                rotated.set_alpha(int(alpha * 255))

            screen.blit(rotated, rect)
        else:
            # 回退：绘制半圆碎片
            color = tuple(int(c * alpha) for c in self.color)
            rect = pygame.Rect(pos[0] - int(self.radius), pos[1] - int(self.radius),
                               int(self.radius * 2), int(self.radius * 2))
            pygame.draw.ellipse(screen, color, rect)
        # 果汁滴
        jc = tuple(int(c * alpha * 0.8) for c in self.juice_color)
        for drop in self.juice_drops:
            dx = int(pos[0] + drop['ox'])
            dy = int(pos[1] + drop['oy'])
            dr = max(1, int(drop['r'] * alpha))
            pygame.draw.circle(screen, jc, (dx, dy), dr)


# ==================== 水果类 ====================
class Fruit:
    _id_counter = 0

    def __init__(self, fruit_type=None):
        Fruit._id_counter += 1
        self.id = Fruit._id_counter
        if fruit_type is None:
            # 先从非炸弹水果中随机选一个
            fruit_type = random.choice([f for f in FRUIT_TYPES if f['name'] != 'bomb'])
            # 炸弹概率: 10%
            BOMB_CHANCE = 0.1
            if random.random() < BOMB_CHANCE:
                fruit_type = FRUIT_TYPES[-1]  # bomb
        self.name = fruit_type['name']
        self.radius = fruit_type['radius']
        self.color = fruit_type['color']
        self.juice_color = fruit_type['juice_color']
        self.score_value = fruit_type['score']
        self.is_bomb = (self.name == 'bomb')

        # 加载水果图片
        self.fruit_image = None
        self.half_left_image = None
        self.half_right_image = None
        if 'image' in fruit_type:
            self.fruit_image = load_image(fruit_type['image'])
        if 'half_left' in fruit_type:
            self.half_left_image = load_image(fruit_type['half_left'])
        if 'half_right' in fruit_type:
            self.half_right_image = load_image(fruit_type['half_right'])
        self.x = 0
        self.y = 0
        self.vx = 0
        self.vy = 0
        self.active = True
        self.cut = False
        self.rotation = 0
        self.rot_speed = random.uniform(-180, 180)

    def launch(self, x, vx, vy):
        self.x = x
        self.y = HEIGHT + self.radius + 20
        self.vx = vx
        self.vy = vy
        self.active = True
        self.cut = False
        self.rot_speed = random.uniform(-200, 200)

    def update(self, dt):
        if not self.active or self.cut:
            return False
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += config.GRAVITY * dt
        self.rotation += self.rot_speed * dt
        if self.y > HEIGHT + 100 or self.x < -200 or self.x > WIDTH + 200:
            self.active = False
            return False
        return True

    def do_cut(self, knife_vx, knife_vy):
        self.cut = True
        self.active = False
        chips = []
        for i, is_left in enumerate([True, False]):
            chip_vx = (random.uniform(-1, 1) * 100) - knife_vx * config.KNIFE_SPEED_2_FRUIT_FAC
            chip_vy = (random.uniform(-1, 1) * 80) - knife_vy * config.KNIFE_SPEED_2_FRUIT_FAC - 50
            chip = FruitChip(self.x, self.y, self.color, self.juice_color,
                             chip_vx, chip_vy, self.radius, is_left_half=is_left, fruit_name=self.name)
            chips.append(chip)
        return chips

    def draw(self, screen):
        if not self.active or self.cut:
            return

        # 如果有水果图片，使用图片绘制
        if self.fruit_image:
            # 旋转图片
            rotated = pygame.transform.rotate(self.fruit_image, self.rotation)
            rect = rotated.get_rect(center=(int(self.x), int(self.y)))
            screen.blit(rotated, rect)
        else:
            # 回退：绘制圆形水果
            # 绘制水果阴影
            shadow_surf = pygame.Surface((self.radius * 2 + 10, 10), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow_surf, (0, 0, 0, 40), (0, 0, self.radius * 2 + 10, 10))
            screen.blit(shadow_surf, (int(self.x - self.radius - 5), int(self.y + self.radius + 2)))
            # 绘制水果主体
            pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)
            # 高光效果
            highlight_pos = (int(self.x - self.radius * 0.3), int(self.y - self.radius * 0.3))
            highlight_radius = max(3, int(self.radius * 0.3))
            highlight_color = tuple(min(255, c + 70) for c in self.color)
            pygame.draw.circle(screen, highlight_color, highlight_pos, highlight_radius)
            # 第二层高光
            hl2_pos = (int(self.x - self.radius * 0.15), int(self.y - self.radius * 0.45))
            hl2_r = max(2, int(self.radius * 0.15))
            hl2_color = tuple(min(255, c + 100) for c in self.color)
            pygame.draw.circle(screen, hl2_color, hl2_pos, hl2_r)
            # 炸弹特殊绘制
            if self.is_bomb:
                fuse_start = (int(self.x), int(self.y - self.radius))
                fuse_end = (int(self.x + 8), int(self.y - self.radius - 12))
                pygame.draw.line(screen, (139, 90, 43), fuse_start, fuse_end, 3)
                spark_color = (255, random.randint(100, 200), 0)
                pygame.draw.circle(screen, spark_color,
                                   (int(self.x + 8), int(self.y - self.radius - 14)), 4)
                font_small = pygame.font.Font(None, 22)
                text = font_small.render("X", True, (255, 50, 50))
                screen.blit(text, (int(self.x - 6), int(self.y - 8)))
                # 炸弹金属环
                ring_color = (100, 100, 110)
                pygame.draw.circle(screen, ring_color, (int(self.x), int(self.y)), self.radius, 3)

    def check_collision(self, kx, ky, knife_radius=15):
        if not self.active or self.cut:
            return False
        dist = math.sqrt((self.x - kx) ** 2 + (self.y - ky) ** 2)
        return dist < (self.radius + knife_radius)


# ==================== 水果发射器 ====================
class FruitLauncher:
    LEVEL_CONFIGS = [
        {'interval': (1.2, 2.0), 'count': (1, 2), 'pos_x': (100, WIDTH - 100), 'vel_x': (-80, 80),
         'vel_y': (-750, -600)},
        {'interval': (1.0, 1.8), 'count': (1, 3), 'pos_x': (80, WIDTH - 80), 'vel_x': (-120, 120),
         'vel_y': (-800, -650)},
        {'interval': (0.8, 1.5), 'count': (2, 3), 'pos_x': (60, WIDTH - 60), 'vel_x': (-150, 150),
         'vel_y': (-850, -700)},
        {'interval': (0.6, 1.3), 'count': (2, 4), 'pos_x': (40, WIDTH - 40), 'vel_x': (-180, 180),
         'vel_y': (-900, -750)},
        {'interval': (0.5, 1.1), 'count': (3, 5), 'pos_x': (20, WIDTH - 20), 'vel_x': (-200, 200),
         'vel_y': (-950, -800)},
    ]

    def __init__(self):
        self.fruits = []
        self.timer = 0
        self.running = False
        self.current_level = 0
        self.launch_timer = 0
        self.next_interval = 1.0

    def start(self):
        self.running = True
        self.timer = 0
        self.fruits.clear()

    def stop(self):
        self.running = False

    def get_current_level(self):
        if self.timer < 20:
            return 0
        elif self.timer < 40:
            return 1
        elif self.timer < 60:
            return 2
        elif self.timer < 100:
            return 3
        else:
            return 4

    def update(self, dt):
        if not self.running:
            return
        self.timer += dt
        self.current_level = self.get_current_level()
        cfg = self.LEVEL_CONFIGS[self.current_level]
        self.launch_timer -= dt
        if self.launch_timer <= 0:
            count = random.randint(cfg['count'][0], cfg['count'][1])
            for _ in range(count):
                self._launch_one(cfg)
            self.next_interval = random.uniform(cfg['interval'][0], cfg['interval'][1])
            self.launch_timer = self.next_interval
        for fruit in self.fruits[:]:
            if not fruit.update(dt):
                if fruit in self.fruits:
                    self.fruits.remove(fruit)

    def _launch_one(self, cfg):
        fruit = Fruit()
        x = random.uniform(cfg['pos_x'][0], cfg['pos_x'][1])
        vx = random.uniform(cfg['vel_x'][0], cfg['vel_x'][1])
        vy = random.uniform(cfg['vel_y'][0], cfg['vel_y'][1])
        fruit.launch(x, vx, vy)
        self.fruits.append(fruit)


# ==================== 玩家刀 - 支持双刀 ====================
class PlayerKnife:
    """
    单把刀 - 支持自定义颜色和标签
    右手刀(R): 青蓝色系
    左手刀(L): 品红色系
    """
    # 预定义的刀颜色方案
    KNIFE_STYLES = {
        'right': {
            'main': (80, 200, 255),  # 刀尖主色 - 冰蓝
            'trail': (60, 170, 255),  # 轨迹颜色
            'glow': (80, 200, 255, 60),  # 发光颜色
            'flash': (150, 230, 255),  # 刀光闪烁
            'sparkle': (100, 220, 255),  # 火花
            'label': 'R',
        },
        'left': {
            'main': (255, 80, 200),  # 刀尖主色 - 品红
            'trail': (255, 60, 170),  # 轨迹颜色
            'glow': (255, 80, 200, 60),  # 发光颜色
            'flash': (255, 150, 230),  # 刀光闪烁
            'sparkle': (255, 120, 220),  # 火花
            'label': 'L',
        },
        'mouse': {
            'main': (200, 220, 255),
            'trail': (150, 180, 255),
            'glow': (200, 220, 255, 50),
            'flash': (255, 255, 255),
            'sparkle': (255, 255, 255),
            'label': 'M',
        },
    }

    def __init__(self, style='right'):
        style_data = self.KNIFE_STYLES.get(style, self.KNIFE_STYLES['right'])
        self.style = style
        self.color_main = style_data['main']
        self.color_trail = style_data['trail']
        self.color_glow = style_data['glow']
        self.color_flash = style_data['flash']
        self.color_sparkle = style_data['sparkle']
        self.label = style_data['label']
        self.x = WIDTH / 2
        self.y = HEIGHT / 2
        self.last_x = self.x
        self.last_y = self.y
        self.vx = 0
        self.vy = 0
        self.valid = False
        self.trail = []
        self.max_trail_length = 15
        self.active = True  # 是否激活（手是否被追踪到）

    def set_position(self, x, y):
        self.last_x = self.x
        self.last_y = self.y
        self.x = x
        self.y = y
        self.active = True

    def set_inactive(self):
        """标记为未追踪状态"""
        self.active = False
        self.valid = False

    def update(self, dt):
        if not self.active:
            self.trail.clear()
            return
        dx = self.x - self.last_x
        dy = self.y - self.last_y
        if abs(dx) > 0.1 or abs(dy) > 0.1:
            self.vx = dx / dt * config.KNIFE_SPEED_FAC * 0.0001
            self.vy = dy / dt * config.KNIFE_SPEED_FAC * 0.0001
        else:
            self.vx *= 0.8
            self.vy *= 0.8
        # 轨迹
        self.trail.append((self.x, self.y, time.time()))
        current_time = time.time()
        self.trail = [(tx, ty, t) for tx, ty, t in self.trail
                      if current_time - t < 0.18]
        if len(self.trail) > self.max_trail_length:
            self.trail = self.trail[-self.max_trail_length:]
        speed_sq = self.vx ** 2 + self.vy ** 2
        self.valid = speed_sq > config.KNIFE_SPEED_MIN

    def draw(self, screen):
        if not self.active:
            return
        # ---- 绘制轨迹（渐变刀光）----
        if len(self.trail) > 1:
            trail_len = len(self.trail)
            for i in range(1, trail_len):
                alpha = i / trail_len
                width = int(2 + alpha * 7)
                # 颜色从透明渐变到主色
                r = int(self.color_trail[0] * alpha * 0.85)
                g = int(self.color_trail[1] * alpha * 0.85)
                b = int(self.color_trail[2] * alpha * 0.85)
                p1 = (int(self.trail[i - 1][0]), int(self.trail[i - 1][1]))
                p2 = (int(self.trail[i][0]), int(self.trail[i][1]))
                try:
                    pygame.draw.line(screen, (r, g, b), p1, p2, width)
                except Exception:
                    pass
        # ---- 绘制刀尖 ----
        if self.valid:
            knife_color = self.color_main
            knife_radius = 11
            # 外发光
            glow_size = 44
            glow_surf = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)
            for gr in range(20, 2, -3):
                ga = int(25 * (1 - gr / 20))
                gc = (*self.color_main[:3], ga)
                pygame.draw.circle(glow_surf, gc, (glow_size // 2, glow_size // 2), gr)
            screen.blit(glow_surf, (int(self.x - glow_size // 2), int(self.y - glow_size // 2)))
        else:
            knife_color = tuple(max(80, c - 80) for c in self.color_main)
            knife_radius = 7
        pygame.draw.circle(screen, knife_color, (int(self.x), int(self.y)), knife_radius)
        # 刀尖高亮核心
        core_color = tuple(min(255, c + 80) for c in knife_color)
        pygame.draw.circle(screen, core_color, (int(self.x), int(self.y)), max(2, knife_radius // 2))
        # 标签文字 (R/L)
        if self.label:
            label_font = pygame.font.Font(None, 16)
            label_text = label_font.render(self.label, True, (255, 255, 255))
            label_rect = label_text.get_rect(center=(int(self.x), int(self.y) - knife_radius - 10))
            # 标签背景
            bg_rect = label_rect.inflate(6, 2)
            bg_surf = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
            pygame.draw.rect(bg_surf, (*self.color_main[:3], 150), bg_surf.get_rect(), border_radius=3)
            screen.blit(bg_surf, bg_rect.topleft)
            screen.blit(label_text, label_rect)


# ==================== 主游戏控制器 ====================
class GameController:
    def __init__(self):
        self.hp = 3
        self.score = 0
        self.game_state = 'menu'
        self.gameover_timer = 0
        self.combo = 0  # 连击计数
        self.combo_timer = 0  # 连击计时器
        self.max_combo = 0  # 最大连击
        self.best_score = self._load_best_score()  # 历史最高分

    def _load_best_score(self):
        """从 best.txt 加载历史最高分"""
        try:
            with open('best.txt', 'r') as f:
                for line in f:
                    if 'kinect_mode' in line:
                        return int(line.split(':')[-1].strip())
        except Exception:
            pass
        return 0

    def _save_best_score(self):
        """保存历史最高分到 best.txt"""
        if self.score > self.best_score:
            self.best_score = self.score
        try:
            # 读取现有内容
            content = ''
            has_kinect_line = False
            try:
                with open('best.txt', 'r') as f:
                    content = f.read()
            except Exception:
                pass
            if 'kinect_mode' in content:
                # 替换已有的 kinect_mode 行
                lines = content.strip().split('\n')
                new_lines = []
                for line in lines:
                    if 'kinect_mode' in line:
                        new_lines.append(f"kinect_mode:{self.best_score}")
                        has_kinect_line = True
                    else:
                        new_lines.append(line)
                content = '\n'.join(new_lines)
            else:
                # 追加 kinect_mode 行
                has_kinect_line = True
                if content and not content.endswith('\n'):
                    content += '\n'
                content += f"kinect_mode:{self.best_score}"
            with open('best.txt', 'w') as f:
                f.write(content)
        except Exception as e:
            print(f"[WARN] Failed to save best score: {e}")

    def start_game(self):
        self.hp = 3
        self.score = 0
        self.game_state = 'playing'
        self.combo = 0
        self.combo_timer = 0
        self.max_combo = 0

    def add_score(self, points):
        self.combo += 1
        self.combo_timer = 1.5  # 1.5秒内连续切算连击
        if self.combo > self.max_combo:
            self.max_combo = self.combo
        # 连击加成
        combo_bonus = min(self.combo - 1, 5) * 2  # 每次连击额外+2分，最多+10
        self.score += max(0, points) + combo_bonus

    def reduce_hp(self):
        self.hp -= 1
        self.combo = 0  # 扣血重置连击
        if self.hp <= 0:
            self.gameover()

    def gameover(self):
        self.game_state = 'gameover'
        self.gameover_timer = time.time()
        self._save_best_score()

    def update_combo(self, dt):
        if self.combo > 0:
            self.combo_timer -= dt
            if self.combo_timer <= 0:
                self.combo = 0
```

</details>

<details>
<summary><b>best.txt</b> - Best Score Record (click to expand)</summary>

```
zen_mode:36
classic_mode:56
kinect_mode:1202
```

</details>

