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