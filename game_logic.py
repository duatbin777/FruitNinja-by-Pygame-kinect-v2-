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