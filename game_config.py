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