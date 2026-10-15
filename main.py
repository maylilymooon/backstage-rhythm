# main.py
# 박자 반전! 백스테이지 - pygame 리듬 게임
# 실행: python main.py

import math
import os
import random
import sys
import time

import pygame

import chart
import sound_maker
from game_logic import RhythmGame

# ---------------- 기본 설정 ----------------
WIDTH, HEIGHT = 960, 640
FPS = 60
# 소리가 스피커에서 실제로 들리기까지 걸리는 시간(초).
# 노트를 박자에 맞게 눌렀는데 판정이 늦거나 빠르게 느껴지면 이 값을 0.0~0.12 사이에서 조절한다.
AUDIO_LATENCY = 0.03

LANE_W = 84
LANE_LEFT = (WIDTH - LANE_W * 4) // 2      # 레인 4개를 화면 가운데에
HUD_H = 56
HIT_Y = 548                                # 판정선 높이
NOTE_TRAVEL = 1.5                          # 노트가 화면 위에서 판정선까지 오는 시간(초)
SPEED = (HIT_Y - 40) / NOTE_TRAVEL         # 노트 속도(px/초)
FLOOR_Y = 578

KEY_TO_LANE = {pygame.K_LEFT: 0, pygame.K_DOWN: 1, pygame.K_UP: 2, pygame.K_RIGHT: 3}
LANE_ANGLE = [270, 180, 0, 90]             # 화살표 회전 각도: ← ↓ ↑ →
LANE_COLORS = [(255, 80, 170), (70, 200, 255), (100, 240, 140), (255, 175, 60)]

WHITE = (255, 255, 255)
GOLD = (255, 215, 90)
REVERSE_COLOR = (190, 100, 255)
MODE_INFO = {
    "rehearsal": ("리허설", (120, 200, 255)),
    "tension": ("긴장 고조!", (255, 160, 60)),
    "reverse": ("반전 모드 · 반대로 누르세요!", REVERSE_COLOR),
    "fever": ("FEVER TIME! · 반전 유지", (255, 80, 170)),
}
JUDGE_COLORS = {"PERFECT": GOLD, "GOOD": (90, 220, 255), "MISS": (255, 90, 100)}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def lane_x(lane):
    return LANE_LEFT + LANE_W * lane + LANE_W // 2


def arrow_points(cx, cy, size, lane):
    """방향 화살표 다각형의 꼭짓점"""
    base = [(0, -1), (0.9, -0.05), (0.35, -0.05), (0.35, 0.9),
            (-0.35, 0.9), (-0.35, -0.05), (-0.9, -0.05)]
    a = math.radians(LANE_ANGLE[lane])
    pts = []
    for x, y in base:
        rx = x * math.cos(a) - y * math.sin(a)
        ry = x * math.sin(a) + y * math.cos(a)
        pts.append((cx + rx * size, cy + ry * size))
    return pts


def mix(c1, c2, k):
    return tuple(int(a + (b - a) * k) for a, b in zip(c1, c2))


def load_font(size, bold=False):
    """한글이 깨지지 않도록 Windows의 맑은 고딕을 우선 사용한다."""
    names = ["malgunbd.ttf", "malgun.ttf"] if bold else ["malgun.ttf"]
    for name in names:
        path = os.path.join("C:/Windows/Fonts", name)
        if os.path.exists(path):
            return pygame.font.Font(path, size)
    return pygame.font.SysFont("malgungothic,applegothic,nanumgothic", size, bold=bold)


class Button:
    def __init__(self, center, size, label):
        self.rect = pygame.Rect(0, 0, *size)
        self.rect.center = center
        self.label = label


# =====================================================================
class App:
    def __init__(self):
        pygame.mixer.pre_init(44100, -16, 2, 512)   # 작은 버퍼 = 소리 지연 감소
        pygame.init()
        pygame.display.set_caption("박자 반전! 백스테이지")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.fonts = {}
        self.text_cache = {}

        self.game = RhythmGame()
        self.state = "title"
        self.sound_on = True
        self.fake_time = None        # 테스트용: 값이 있으면 이 시간을 게임 시간으로 사용
        self.app_time = 0.0

        self.draw_loading()
        self.load_sounds()

        self.background = self.make_background()
        self.light_layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.fx_layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.lane_panel = pygame.Surface((LANE_W * 4 + 16, HEIGHT - HUD_H), pygame.SRCALPHA)
        self.lane_panel.fill((8, 6, 16, 210))
        self.beams = [self.make_beam(c) for c in LANE_COLORS]

        self.start_button = Button((620, 545), (260, 58), "▶  공연 리허설 시작")
        self.sound_button = Button((620, 600), (200, 36), "")
        self.retry_button = Button((520, 560), (230, 56), "다시 시작하기 (R)")
        self.quit_button = Button((770, 560), (200, 56), "종료하기 (Esc)")
        self.reset_effects()

    # ---------------- 준비 ----------------
    def font(self, size, bold=True):
        key = (size, bold)
        if key not in self.fonts:
            self.fonts[key] = load_font(size, bold)
        return self.fonts[key]

    def text(self, s, size, color, bold=True):
        key = (s, size, color, bold)
        if key not in self.text_cache:
            if len(self.text_cache) > 400:
                self.text_cache.clear()
            self.text_cache[key] = self.font(size, bold).render(s, True, color)
        return self.text_cache[key]

    def blit_center(self, surf, center, alpha=None):
        if alpha is not None:
            surf = surf.copy()
            surf.set_alpha(int(max(0, min(255, alpha))))
        self.screen.blit(surf, surf.get_rect(center=center))

    def draw_loading(self):
        self.screen.fill((10, 8, 16))
        self.blit_center(self.text("무대 뒤 음향 장비 준비 중...", 28, GOLD), (WIDTH // 2, HEIGHT // 2))
        pygame.display.flip()

    def load_sounds(self):
        self.sounds = {}
        self.song_channel = None
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            sound_maker.ensure_sounds()
            for name in sound_maker.SOUND_FILES:
                self.sounds[name] = pygame.mixer.Sound(sound_maker.sound_path(name))
            pygame.mixer.set_num_channels(16)
            pygame.mixer.set_reserved(1)                # 0번 채널은 음악 전용
            self.song_channel = pygame.mixer.Channel(0)
            self.sounds["perfect"].set_volume(0.45)
            self.sounds["good"].set_volume(0.4)
            self.sounds["miss"].set_volume(0.5)
            self.sounds["alert"].set_volume(0.8)
            self.audio_ok = True
        except pygame.error as e:
            print("소리 장치를 사용할 수 없어 소리 없이 실행합니다:", e)
            self.audio_ok = False

    def play_sfx(self, name):
        if self.audio_ok and self.sound_on:
            self.sounds[name].play()

    def toggle_sound(self):
        self.sound_on = not self.sound_on
        if self.audio_ok:
            # 음악은 멈추지 않고 볼륨만 0으로 → 게임 시간 기준이 흔들리지 않는다
            self.song_channel.set_volume(0.9 if self.sound_on else 0.0)
        self.play_sfx("select")

    def reset_effects(self):
        self.particles = []      # [x, y, vx, vy, 남은수명, 전체수명, 색, 크기]
        self.rings = []          # [x, y, 나이, 색, 최대반지름]
        self.floaters = []       # 기타에서 튀어나오는 음표: [x, y, 나이, 글자]
        self.lane_glow = [0.0] * 4
        self.judge_show = None   # (결과, 표시 시작 시각)
        self.strum = 0.0
        self.strum_dir = 1
        self.miss_time = -10.0
        self.flash = None        # (색, 시작 시각, 길이)
        self.alert_done = False
        self.fever_done = False
        self.paused = False

    # ---------------- 시간 ----------------
    def game_time(self):
        """음악과 노트 판정이 함께 쓰는 단 하나의 기준 시간"""
        if self.fake_time is not None:
            return self.fake_time
        if self.paused:
            return self.paused_at - self.song_start - AUDIO_LATENCY
        return time.perf_counter() - self.song_start - AUDIO_LATENCY

    # ---------------- 게임 흐름 ----------------
    def start_play(self):
        """시작 / 재시작: 점수, 콤보, 노트, 타이머, 음악을 모두 처음으로"""
        self.game.reset()
        self.reset_effects()
        self.state = "play"
        if self.audio_ok:
            pygame.mixer.stop()
            self.song_channel.set_volume(0.9 if self.sound_on else 0.0)
            self.song_channel.play(self.sounds["song"])
        self.song_start = time.perf_counter()   # 음악 재생 직후의 시각 = 게임 시간 0

    def pause(self):
        if self.state == "play" and not self.paused:
            self.paused = True
            self.paused_at = time.perf_counter()
            if self.audio_ok:
                pygame.mixer.pause()

    def resume(self):
        if self.paused:
            self.song_start += time.perf_counter() - self.paused_at   # 멈춘 시간만큼 기준 시각을 미룬다
            self.paused = False
            if self.audio_ok:
                pygame.mixer.unpause()

    def go_title(self):
        self.paused = False
        if self.audio_ok:
            pygame.mixer.stop()
        self.state = "title"

    # ---------------- 입력 ----------------
    def handle_event(self, e):
        if e.type == pygame.QUIT:
            return False
        if e.type == pygame.WINDOWFOCUSLOST:
            self.pause()          # 다른 창을 누르면 자동 일시정지
            return True
        if e.type == pygame.KEYDOWN and e.key == pygame.K_m:
            self.toggle_sound()
            return True

        if self.state == "title":
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.play_sfx("select")
                    self.start_play()
                elif e.key == pygame.K_ESCAPE:
                    return False
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if self.start_button.rect.collidepoint(e.pos):
                    self.play_sfx("select")
                    self.start_play()
                elif self.sound_button.rect.collidepoint(e.pos):
                    self.toggle_sound()

        elif self.state == "play":
            if self.paused:
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    self.go_title()
                elif (e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE) or \
                        (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1):
                    self.resume()
            elif e.type == pygame.KEYDOWN:
                if e.key in KEY_TO_LANE:
                    self.press_key(KEY_TO_LANE[e.key])
                elif e.key in (pygame.K_ESCAPE, pygame.K_p):
                    self.pause()

        elif self.state == "result":
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_r, pygame.K_RETURN, pygame.K_SPACE):
                    self.play_sfx("select")
                    self.start_play()
                elif e.key in (pygame.K_ESCAPE, pygame.K_q):
                    return False
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if self.retry_button.rect.collidepoint(e.pos):
                    self.play_sfx("select")
                    self.start_play()
                elif self.quit_button.rect.collidepoint(e.pos):
                    return False
        return True

    def press_key(self, key_lane):
        t = self.game_time()
        # 반전 모드에서는 → 키가 ← 레인을 친다. 빛나는 레인도 그에 맞춘다.
        shown_lane = chart.opposite_lane(key_lane) if chart.is_reversed_at(t) else key_lane
        self.lane_glow[shown_lane] = 1.0
        self.strum = 1.0
        self.strum_dir *= -1
        self.game.press(key_lane, t)

    # ---------------- 업데이트 ----------------
    def update(self, dt):
        self.app_time += dt
        self.strum = max(0.0, self.strum - dt * 6)

        if self.state != "play" or self.paused:
            if self.state != "play":
                self.update_effects(dt)
            return

        t = self.game_time()
        self.game.update(t)

        # 판정 결과에 맞춰 소리와 이펙트
        for result, lane, _ in self.game.events:
            self.on_judge(result, lane, t)
        self.game.events.clear()

        # 15초: 돌발 상황!
        if t >= chart.REVERSE_TIME and not self.alert_done:
            self.alert_done = True
            self.play_sfx("alert")
            self.flash = ((255, 40, 80), t, 0.6)
        # 25초: 피버 타임
        if t >= chart.FEVER_TIME and not self.fever_done:
            self.fever_done = True
            self.flash = ((255, 255, 255), t, 0.35)
            for _ in range(60):
                self.particles.append([random.uniform(LANE_LEFT, LANE_LEFT + LANE_W * 4), 60,
                                       random.uniform(-60, 60), random.uniform(80, 260),
                                       1.4, 1.4, random.choice(LANE_COLORS), random.randint(3, 5)])

        self.update_effects(dt)

        if t >= chart.GAME_LENGTH + 1.6:
            self.state = "result"

    def on_judge(self, result, lane, t):
        x, y = lane_x(lane), HIT_Y
        color = LANE_COLORS[lane]
        self.judge_show = (result, t)
        if result == "PERFECT":
            self.play_sfx("perfect")
            self.rings.append([x, y, 0.0, GOLD, 70])
            for _ in range(16):
                a = random.uniform(0, math.tau)
                v = random.uniform(120, 320)
                self.particles.append([x, y, math.cos(a) * v, math.sin(a) * v - 80,
                                       0.5, 0.5, random.choice([GOLD, color, WHITE]), random.randint(2, 4)])
            self.floaters.append([200, FLOOR_Y - 150, 0.0, random.choice("♪♫")])
        elif result == "GOOD":
            self.play_sfx("good")
            self.rings.append([x, y, 0.0, color, 50])
            for _ in range(6):
                a = random.uniform(0, math.tau)
                v = random.uniform(80, 200)
                self.particles.append([x, y, math.cos(a) * v, math.sin(a) * v - 40,
                                       0.35, 0.35, color, 2])
        else:
            self.play_sfx("miss")
            self.miss_time = t

    def update_effects(self, dt):
        for p in self.particles:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += 400 * dt
            p[4] -= dt
        self.particles = [p for p in self.particles if p[4] > 0][-300:]   # 최대 300개
        for r in self.rings:
            r[2] += dt
        self.rings = [r for r in self.rings if r[2] < 0.35]
        for f in self.floaters:
            f[1] -= 60 * dt
            f[2] += dt
        self.floaters = [f for f in self.floaters if f[2] < 1.2]
        for i in range(4):
            self.lane_glow[i] = max(0.0, self.lane_glow[i] - dt * 5)

    # ---------------- 배경 (한 번만 그려 두고 재사용) ----------------
    def make_background(self):
        bg = pygame.Surface((WIDTH, HEIGHT))
        # 벽 그라데이션 + 벽돌
        for y in range(HEIGHT):
            bg.fill(mix((26, 20, 40), (10, 8, 16), y / HEIGHT), (0, y, WIDTH, 1))
        for row, y in enumerate(range(HUD_H, FLOOR_Y, 26)):
            pygame.draw.line(bg, (32, 26, 46), (0, y), (WIDTH, y))
            off = 0 if row % 2 == 0 else 36
            for x in range(off, WIDTH, 72):
                pygame.draw.line(bg, (32, 26, 46), (x, y), (x, y + 26))
        # 바닥 (나무판)
        pygame.draw.rect(bg, (38, 26, 22), (0, FLOOR_Y, WIDTH, HEIGHT - FLOOR_Y))
        pygame.draw.line(bg, (90, 60, 40), (0, FLOOR_Y), (WIDTH, FLOOR_Y), 3)
        for y in range(FLOOR_Y + 18, HEIGHT, 18):
            pygame.draw.line(bg, (30, 20, 18), (0, y), (WIDTH, y))
        # 조명 트러스
        pygame.draw.line(bg, (80, 80, 92), (0, 66), (WIDTH, 66), 3)
        pygame.draw.line(bg, (80, 80, 92), (0, 80), (WIDTH, 80), 3)
        for x in range(0, WIDTH, 24):
            pygame.draw.line(bg, (60, 60, 70), (x, 66), (x + 12, 80), 2)
        for x in (160, 330, 630, 800):
            pygame.draw.rect(bg, (20, 20, 24), (x - 14, 80, 28, 22), border_radius=4)
            pygame.draw.circle(bg, (70, 70, 80), (x, 98), 9)
        # 분장실 거울 + 전구
        pygame.draw.rect(bg, (70, 52, 38), (52, 112, 176, 126), border_radius=6)
        pygame.draw.rect(bg, (44, 54, 74), (64, 124, 152, 102))
        pygame.draw.line(bg, (80, 96, 124), (90, 226), (150, 124), 6)
        for i in range(6):
            pygame.draw.circle(bg, (255, 226, 150), (68 + i * 29, 112), 6)
            pygame.draw.circle(bg, (255, 226, 150), (68 + i * 29, 238), 6)
        # 앰프 (왼쪽)
        for i, (y, h) in enumerate([(426, 74), (500, 78)]):
            pygame.draw.rect(bg, (24, 24, 28), (40, y, 100, h), border_radius=4)
            pygame.draw.rect(bg, (44, 44, 52), (48, y + 8, 84, h - 16))
            for cx in (70, 110):
                pygame.draw.circle(bg, (18, 18, 22), (cx, y + h // 2), 16)
                pygame.draw.circle(bg, (60, 60, 70), (cx, y + h // 2), 6)
        pygame.draw.rect(bg, (30, 30, 34), (44, 398, 92, 28), border_radius=4)
        for k in range(5):
            pygame.draw.circle(bg, (200, 190, 160), (58 + k * 16, 412), 4)
        # 스피커 (오른쪽)
        pygame.draw.rect(bg, (22, 22, 26), (834, 330, 90, 248), border_radius=6)
        for cy, r in ((380, 24), (460, 34), (530, 30)):
            pygame.draw.circle(bg, (40, 40, 48), (879, cy), r)
            pygame.draw.circle(bg, (14, 14, 18), (879, cy), r - 8)
        # 장비 케이스
        pygame.draw.rect(bg, (46, 46, 58), (690, 506, 120, 72), border_radius=4)
        for cx, cy in ((690, 506), (802, 506), (690, 570), (802, 570)):
            pygame.draw.rect(bg, (150, 150, 160), (cx, cy, 8, 8))
        bg.blit(load_font(15, True).render("FRAGILE", True, (230, 140, 60)), (712, 520))
        bg.blit(load_font(12, False).render("WORLD TOUR", True, (170, 170, 180)), (714, 545))
        # 세트리스트 종이
        pygame.draw.rect(bg, (220, 214, 196), (700, 196, 70, 90))
        bg.blit(load_font(11, True).render("SETLIST", True, (60, 50, 50)), (711, 202))
        for k in range(5):
            pygame.draw.line(bg, (120, 110, 110), (708, 226 + k * 11), (760 - (k % 2) * 14, 226 + k * 11))
        # 바닥 케이블
        pygame.draw.arc(bg, (12, 12, 14), (120, 560, 220, 40), math.pi, math.tau, 4)
        pygame.draw.arc(bg, (12, 12, 14), (640, 566, 260, 50), 0.2, math.pi, 4)
        # 커튼 (양옆 + 위)
        for side_x in (0, WIDTH - 38):
            pygame.draw.rect(bg, (110, 14, 34), (side_x, HUD_H, 38, FLOOR_Y - HUD_H))
            for k in range(4):
                pygame.draw.line(bg, (70, 8, 22), (side_x + 5 + k * 10, HUD_H), (side_x + 5 + k * 10, FLOOR_Y), 3)
        return bg

    def make_beam(self, color):
        """키를 누를 때 레인에서 올라오는 빛 (그라데이션)"""
        h = 260
        s = pygame.Surface((LANE_W - 6, h), pygame.SRCALPHA)
        for y in range(h):
            a = int(140 * (y / h) ** 2)
            s.fill((*color, a), (0, y, LANE_W - 6, 1))
        return s

    # ---------------- 그리기: 조명 ----------------
    def draw_lights(self, t, section, pulse):
        layer = self.light_layer
        layer.fill((0, 0, 0, 0))
        combo = min(self.game.combo, 40) if self.state == "play" else 10
        strength = 18 + combo * 1.0
        if section == "rehearsal":
            beams = [(160, (255, 225, 170)), (800, (255, 225, 170))]
            sway, speed = 30, 0.6
        elif section == "tension":
            beams = [(160, (255, 140, 60)), (330, (255, 90, 60)), (630, (255, 90, 60)), (800, (255, 140, 60))]
            sway, speed = 70, 1.6
            strength += pulse * 18
        elif section == "reverse":
            beams = [(160, (180, 90, 255)), (330, (255, 70, 200)), (630, (255, 70, 200)), (800, (180, 90, 255))]
            sway, speed = 90, 1.2
            strength += pulse * 14
        else:  # fever: 무지개 조명
            beams = []
            for i, x in enumerate((160, 330, 630, 800, 245, 715)):
                c = pygame.Color(0)
                c.hsva = ((t * 120 + i * 60) % 360, 80, 100, 100)
                beams.append((x, (c.r, c.g, c.b)))
            sway, speed = 140, 2.6
            strength += 14 + pulse * 26
        for i, (x, color) in enumerate(beams):
            bx = x + math.sin(t * speed + i * 1.9) * sway
            w = 60 + combo * 1.5
            a = int(min(110, strength))
            pygame.draw.polygon(layer, (*color, a), [(x - 8, 100), (x + 8, 100), (bx + w, FLOOR_Y), (bx - w, FLOOR_Y)])
            pygame.draw.ellipse(layer, (*color, min(150, a + 30)), (bx - w, FLOOR_Y - 10, w * 2, 26))
        # 콤보가 높을수록 음악가를 비추는 스포트라이트가 강해진다
        if self.state != "play" or self.game.combo >= 5:
            w = 50 + combo * 2
            a = int(30 + combo * 2.2)
            pygame.draw.polygon(layer, (255, 240, 200, a), [(150, 100), (170, 100), (165 + w, FLOOR_Y), (165 - w, FLOOR_Y)])
        self.screen.blit(layer, (0, 0))

    # ---------------- 그리기: 캐릭터 ----------------
    def draw_musician(self, t, pulse, fever=False):
        x = 175
        bob = pulse * 4
        if fever:
            bob += abs(math.sin(t * math.pi * chart.BPM / 60)) * 10   # 피버: 박자에 맞춰 점프
        top = FLOOR_Y - bob
        s = self.screen
        # 다리, 신발
        pygame.draw.rect(s, (40, 46, 80), (x - 20, top - 92, 16, 86))
        pygame.draw.rect(s, (40, 46, 80), (x + 4, top - 92, 16, 86))
        pygame.draw.rect(s, WHITE, (x - 24, top - 10, 22, 10), border_radius=4)
        pygame.draw.rect(s, WHITE, (x + 2, top - 10, 22, 10), border_radius=4)
        # 몸통 (재킷)
        pygame.draw.rect(s, (100, 50, 170), (x - 30, top - 172, 60, 86), border_radius=12)
        pygame.draw.line(s, (255, 90, 200), (x - 2, top - 170), (x - 2, top - 90), 3)
        # 머리
        hy = top - 196
        pygame.draw.circle(s, (245, 205, 175), (x, hy), 24)
        pygame.draw.polygon(s, (40, 30, 60), [(x - 26, hy - 4), (x - 22, hy - 30), (x - 8, hy - 22),
                                               (x + 2, hy - 38), (x + 12, hy - 22), (x + 26, hy - 30), (x + 24, hy - 4)])
        pygame.draw.polygon(s, (255, 90, 200), [(x + 2, hy - 38), (x + 12, hy - 22), (x + 6, hy - 20)])
        pygame.draw.rect(s, (20, 20, 30), (x - 18, hy - 6, 36, 10), border_radius=4)   # 선글라스
        pygame.draw.line(s, (120, 200, 255), (x - 14, hy - 4), (x - 8, hy - 4), 2)
        recent_miss = 0 <= t - self.miss_time < 0.5
        if recent_miss:
            pygame.draw.circle(s, (120, 60, 60), (x, hy + 12), 4)                     # 당황한 입
            pygame.draw.circle(s, (120, 200, 255), (x + 26, hy - 10), 4)              # 땀방울
        else:
            pygame.draw.arc(s, (120, 60, 60), (x - 8, hy + 4, 16, 12), math.pi, math.tau, 2)
        # 기타
        neck_a = (x - 78, top - 168)
        neck_b = (x + 4, top - 118)
        pygame.draw.line(s, (120, 80, 40), neck_a, neck_b, 8)
        pygame.draw.rect(s, (60, 40, 20), (neck_a[0] - 8, neck_a[1] - 8, 16, 14), border_radius=3)
        body = pygame.Rect(0, 0, 64, 46)
        body.center = (x + 14, top - 110)
        pygame.draw.ellipse(s, (225, 50, 75), body)
        pygame.draw.ellipse(s, (255, 120, 140), body, 2)
        pygame.draw.circle(s, (30, 20, 20), (x + 8, top - 112), 7)
        for k in (-2, 2):
            pygame.draw.line(s, (230, 230, 230), (neck_a[0], neck_a[1] + k), (x + 26, top - 108 + k), 1)
        # 왼팔 (코드 잡는 손)
        pygame.draw.line(s, (100, 50, 170), (x - 22, top - 160), (x - 52, top - 150), 10)
        pygame.draw.circle(s, (245, 205, 175), (x - 54, top - 150), 7)
        # 오른팔 (줄을 치는 손) - 키를 누르면 위아래로 움직인다
        hand_y = top - 112 + self.strum * 18 * self.strum_dir
        pygame.draw.line(s, (100, 50, 170), (x + 22, top - 160), (x + 30, hand_y), 10)
        pygame.draw.circle(s, (245, 205, 175), (int(x + 30), int(hand_y)), 7)
        if self.strum > 0.5:
            for k in range(3):
                pygame.draw.line(s, GOLD, (x + 48, top - 120 + k * 8), (x + 60, top - 124 + k * 8), 2)
        # 기타에서 튀어나오는 음표 (글꼴에 없는 기호일 수 있어서 도형으로 그린다)
        for f in self.floaters:
            fx = int(f[0] + math.sin(f[2] * 6) * 8)
            fy = int(f[1])
            c = mix(GOLD, (20, 16, 30), f[2] / 1.2)
            pygame.draw.ellipse(s, c, (fx - 7, fy + 6, 12, 9))
            pygame.draw.line(s, c, (fx + 4, fy + 10), (fx + 4, fy - 10), 2)
            pygame.draw.line(s, c, (fx + 4, fy - 10), (fx + 11, fy - 4), 3)

    def draw_manager(self, t):
        """15초에 등장하는 매니저"""
        age = t - chart.REVERSE_TIME
        if age < 0 or age > 4.2:
            return
        if age < 0.3:
            k = age / 0.3
        elif age > 3.8:
            k = 1 - (age - 3.8) / 0.4
        else:
            k = 1.0
        x = int(WIDTH + 70 - 230 * k)
        top = FLOOR_Y
        s = self.screen
        shake = math.sin(age * 40) * 3 if age < 1.5 else 0
        pygame.draw.rect(s, (30, 30, 36), (x - 18, top - 90, 15, 86))
        pygame.draw.rect(s, (30, 30, 36), (x + 3, top - 90, 15, 86))
        pygame.draw.rect(s, (60, 64, 80), (x - 28, top - 170, 56, 84), border_radius=10)
        pygame.draw.polygon(s, WHITE, [(x - 10, top - 170), (x + 10, top - 170), (x, top - 150)])
        pygame.draw.polygon(s, (220, 40, 60), [(x - 4, top - 160), (x + 4, top - 160), (x + 2, top - 120), (x - 2, top - 120)])
        hy = top - 194 + shake
        pygame.draw.circle(s, (235, 195, 160), (x, int(hy)), 23)
        pygame.draw.arc(s, (40, 40, 40), (x - 26, hy - 28, 52, 46), 0, math.pi, 4)       # 헤드셋
        pygame.draw.circle(s, (40, 40, 40), (x - 24, int(hy)), 6)
        pygame.draw.line(s, (40, 40, 40), (x - 24, hy), (x - 10, hy + 14), 3)
        pygame.draw.circle(s, (30, 30, 30), (x - 8, int(hy - 4)), 3)
        pygame.draw.circle(s, (30, 30, 30), (x + 8, int(hy - 4)), 3)
        mouth = 4 + int(abs(math.sin(age * 18)) * 6)                                         # 외치는 입
        pygame.draw.ellipse(s, (120, 30, 40), (x - 6, hy + 6, 12, mouth))
        # 팔을 흔들며 클립보드
        wave = math.sin(age * 14) * 12
        pygame.draw.line(s, (60, 64, 80), (x - 24, top - 160), (x - 50, top - 200 + wave), 9)
        pygame.draw.rect(s, (200, 170, 120), (x - 66, top - 226 + wave, 28, 36))
        pygame.draw.line(s, (60, 64, 80), (x + 24, top - 160), (x + 40, top - 120), 9)
        # 말풍선 (큰 경고 배너가 사라진 뒤에 나와서 서로 겹치지 않게)
        if 1.6 < age < 3.9:
            bubble = pygame.Rect(660, 238, 292, 82)
            pygame.draw.rect(s, WHITE, bubble, border_radius=14)
            pygame.draw.polygon(s, WHITE, [(x - 20, bubble.bottom - 2), (x + 4, bubble.bottom - 2), (x - 4, hy - 30)])
            s.blit(self.text("긴급! 공연 콘셉트 변경!", 20, (220, 30, 60)), (bubble.x + 18, bubble.y + 10))
            s.blit(self.text("이제 반대로 연주하세요!", 20, (40, 30, 60)), (bubble.x + 18, bubble.y + 42))

    # ---------------- 그리기: 레인과 노트 ----------------
    def draw_lanes(self, t, section, pulse):
        s = self.screen
        mode_color = MODE_INFO[section][1]
        s.blit(self.lane_panel, (LANE_LEFT - 8, HUD_H))
        for i in range(5):
            x = LANE_LEFT + i * LANE_W
            pygame.draw.line(s, (40, 36, 60), (x, HUD_H), (x, HEIGHT))
        border = mix(mode_color, WHITE, pulse * 0.4)
        pygame.draw.line(s, border, (LANE_LEFT - 8, HUD_H), (LANE_LEFT - 8, HEIGHT), 3)
        pygame.draw.line(s, border, (LANE_LEFT + LANE_W * 4 + 8, HUD_H), (LANE_LEFT + LANE_W * 4 + 8, HEIGHT), 3)
        # 키를 누른 레인에서 올라오는 빛
        for i in range(4):
            if self.lane_glow[i] > 0:
                beam = self.beams[i]
                beam.set_alpha(int(255 * self.lane_glow[i]))
                s.blit(beam, (LANE_LEFT + i * LANE_W + 3, HIT_Y - beam.get_height() + 20))
        # 판정선
        pygame.draw.line(s, mix(mode_color, WHITE, 0.3 + pulse * 0.5),
                         (LANE_LEFT - 8, HIT_Y), (LANE_LEFT + LANE_W * 4 + 8, HIT_Y), 3)

    def draw_receptors(self, t):
        s = self.screen
        reversed_now = chart.is_reversed_at(t)
        for i in range(4):
            x = lane_x(i)
            color = LANE_COLORS[i]
            g = self.lane_glow[i]
            size = 22 + g * 5
            if g > 0:
                pygame.draw.polygon(s, mix(color, WHITE, 0.4), arrow_points(x, HIT_Y, size, i))
            pygame.draw.polygon(s, color, arrow_points(x, HIT_Y, size, i), 3)
            # 반전 직후 6초 동안: 이 레인은 어떤 키로 치는지 알려 준다
            if reversed_now and t < chart.REVERSE_TIME + 6:
                # 처음 3초는 깜빡이고, 마지막 1.5초 동안 서서히 사라진다
                fade = min(1.0, (chart.REVERSE_TIME + 6 - t) / 1.5)
                if int(t * 4) % 2 == 0 or t > chart.REVERSE_TIME + 3:
                    hint = mix((8, 6, 16), REVERSE_COLOR, fade)
                    key = chart.opposite_lane(i)
                    pygame.draw.polygon(s, hint, arrow_points(x - 10, HIT_Y + 52, 10, key))
                    s.blit(self.text("키", 15, hint), (x + 4, HIT_Y + 41))

    def draw_notes(self, t):
        s = self.screen
        s.set_clip(pygame.Rect(LANE_LEFT - 8, HUD_H, LANE_W * 4 + 16, HEIGHT - HUD_H))
        for n in self.game.notes:
            if n.judged:
                continue
            y = HIT_Y - (n.time - t) * SPEED
            if y < HUD_H - 30 or y > HEIGHT + 30:
                continue
            x = lane_x(n.lane)
            color = LANE_COLORS[n.lane]
            rect = pygame.Rect(0, 0, LANE_W - 14, 36)
            rect.center = (x, int(y))
            if n.reversed:
                pygame.draw.rect(s, REVERSE_COLOR, rect.inflate(8, 8), 3, border_radius=13)
            pygame.draw.rect(s, mix(color, (10, 10, 20), 0.55), rect, border_radius=10)
            pygame.draw.rect(s, color, rect, 3, border_radius=10)
            pygame.draw.polygon(s, WHITE, arrow_points(x, y, 13, n.lane))
        s.set_clip(None)

    def draw_effects(self, t):
        s = self.screen
        layer = self.fx_layer
        layer.fill((0, 0, 0, 0))
        for x, y, age, color, rmax in self.rings:
            k = age / 0.35
            pygame.draw.circle(layer, (*color, int(220 * (1 - k))), (x, y), int(20 + rmax * k), 4)
        for p in self.particles:
            a = int(255 * p[4] / p[5])
            pygame.draw.circle(layer, (*p[6], a), (int(p[0]), int(p[1])), p[7])
        s.blit(layer, (0, 0))

    def draw_center_texts(self, t):
        """콤보, 판정, 카운트다운, 이벤트 배너 - 모두 노트 '뒤'에 그려서 노트를 가리지 않는다"""
        cx = WIDTH // 2
        # 이벤트 배너 (15초)
        age = t - chart.REVERSE_TIME
        if 0 <= age < 1.7:
            band = pygame.Surface((WIDTH, 120), pygame.SRCALPHA)
            blink = (int(age * 8) % 2 == 0)
            band.fill((150, 0, 40, 170) if blink else (60, 0, 90, 170))
            self.screen.blit(band, (0, 230))
            k = min(1.0, age / 0.15)
            self.blit_center(self.text("긴급! 공연 콘셉트 변경!", 40, WHITE), (cx, 268), 255 * k)
            self.blit_center(self.text("이제 반대로 연주하세요!", 30, GOLD), (cx, 316), 255 * k)
        # 콤보
        combo = self.game.combo
        if combo >= 3 and not (0 <= age < 1.7):
            self.blit_center(self.text(str(combo), 64, WHITE), (cx, 200), 110 + min(combo, 30) * 3)
            self.blit_center(self.text("COMBO", 18, GOLD), (cx, 244), 180)
        # 판정
        if self.judge_show:
            result, jt = self.judge_show
            jage = t - jt
            if 0 <= jage < 0.5:
                surf = self.text(result, 38, JUDGE_COLORS[result])
                scale = 1 + 0.35 * max(0.0, 1 - jage / 0.1)
                if scale != 1:
                    surf = pygame.transform.smoothscale(surf, (int(surf.get_width() * scale), int(surf.get_height() * scale)))
                self.blit_center(surf, (cx, 420), 255 * (1 - max(0, jage - 0.3) / 0.2))
        # 카운트다운 (첫 마디, 드럼 소리에 맞춰)
        if t < chart.BAR:
            beat = max(0, int(t / chart.BEAT))
            word = ["3", "2", "1", "GO!"][min(beat, 3)]
            phase = (t / chart.BEAT) % 1 if t >= 0 else 0
            self.blit_center(self.text(word, 80, GOLD), (cx, 330), 255 * (1 - phase * 0.7))
        # 30초: 공연 시작!
        if t >= chart.GAME_LENGTH:
            self.blit_center(self.text("공연 시작!!", 64, GOLD), (cx, 320))

    def draw_hud(self, t, section):
        s = self.screen
        bar = pygame.Surface((WIDTH, HUD_H), pygame.SRCALPHA)
        bar.fill((6, 4, 12, 225))
        s.blit(bar, (0, 0))
        mode_name, mode_color = MODE_INFO[section]
        pygame.draw.line(s, mode_color, (0, HUD_H - 1), (WIDTH, HUD_H - 1), 2)
        # 남은 시간 + 구간 진행 막대
        remain = max(0.0, chart.GAME_LENGTH - max(0.0, t))
        s.blit(self.text("남은 시간", 13, (180, 170, 200), False), (20, 4))
        s.blit(self.text(f"{remain:4.1f}초", 22, WHITE), (88, 0))
        bar_x, bar_w = 20, 250
        segs = [(0, chart.TENSION_TIME, (120, 200, 255)), (chart.TENSION_TIME, chart.REVERSE_TIME, (255, 160, 60)),
                (chart.REVERSE_TIME, chart.FEVER_TIME, REVERSE_COLOR), (chart.FEVER_TIME, chart.GAME_LENGTH, (255, 80, 170))]
        for a, b, c in segs:
            x0 = bar_x + bar_w * a / chart.GAME_LENGTH
            x1 = bar_x + bar_w * b / chart.GAME_LENGTH
            pygame.draw.rect(s, mix(c, (0, 0, 0), 0.5), (x0, 36, x1 - x0 - 2, 10))
            done = min(max(t, 0), b)
            if done > a:
                pygame.draw.rect(s, c, (x0, 36, bar_w * (done - a) / chart.GAME_LENGTH - 2, 10))
        mx = bar_x + bar_w * min(max(t, 0), chart.GAME_LENGTH) / chart.GAME_LENGTH
        pygame.draw.polygon(s, WHITE, [(mx, 34), (mx - 5, 28), (mx + 5, 28)])
        # 가운데: 현재 상태
        label = self.text(mode_name, 20, (10, 8, 16))
        pill = label.get_rect(center=(WIDTH // 2, HUD_H // 2)).inflate(30, 10)
        pygame.draw.rect(s, mode_color, pill, border_radius=16)
        self.blit_center(label, pill.center)
        # 오른쪽: 점수, 사운드
        s.blit(self.text("SCORE", 13, (180, 170, 200), False), (760, 4))
        score_s = self.text(f"{self.game.score:06d}", 26, GOLD)
        s.blit(score_s, (WIDTH - 20 - score_s.get_width(), 2))
        snd = "소리 ON [M]" if self.sound_on else "소리 OFF [M]"
        s.blit(self.text(snd, 12, (150, 140, 170), False), (760, 32))

    def draw_flash(self, t):
        if self.flash:
            color, ft, dur = self.flash
            age = t - ft
            if 0 <= age < dur:
                f = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                f.fill((*color, int(140 * (1 - age / dur))))
                self.screen.blit(f, (0, 0))
        # 반전 이벤트 동안 화면 가장자리 경고등
        age = t - chart.REVERSE_TIME
        if 0 <= age < 1.7:
            c = (255, 30, 60) if int(age * 8) % 2 == 0 else (60, 120, 255)
            pygame.draw.rect(self.screen, c, (0, HUD_H, WIDTH, HEIGHT - HUD_H), 8)

    # ---------------- 화면별 그리기 ----------------
    def draw_play(self):
        t = self.game_time()
        section = chart.section_at(max(t, 0))
        pulse = (1 - (t / chart.BEAT) % 1) ** 4 if t >= 0 else 0.0   # 박자마다 1→0으로 줄어드는 값

        self.screen.blit(self.background, (0, 0))
        self.draw_lights(t, section, pulse)
        self.draw_musician(t, pulse, fever=(section == "fever"))
        self.draw_manager(t)
        self.draw_lanes(t, section, pulse)
        self.draw_flash(t)
        self.draw_center_texts(t)
        self.draw_effects(t)
        self.draw_receptors(t)
        self.draw_notes(t)
        self.draw_hud(t, section)

        if self.paused:
            dark = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            dark.fill((0, 0, 0, 170))
            self.screen.blit(dark, (0, 0))
            self.blit_center(self.text("일시정지", 48, GOLD), (WIDTH // 2, 270))
            self.blit_center(self.text("Space 또는 클릭: 계속하기    Esc: 처음 화면으로", 20, WHITE, False), (WIDTH // 2, 340))

    def draw_button(self, button, color, label=None):
        hover = button.rect.collidepoint(pygame.mouse.get_pos())
        c = mix(color, WHITE, 0.25) if hover else color
        pygame.draw.rect(self.screen, c, button.rect, border_radius=14)
        pygame.draw.rect(self.screen, WHITE, button.rect, 2, border_radius=14)
        size = 22 if button.rect.height > 40 else 15
        self.blit_center(self.text(label or button.label, size, (10, 8, 16)), button.rect.center)

    def draw_panel(self, rect):
        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        panel.fill((10, 6, 20, 242))
        self.screen.blit(panel, rect.topleft)
        pygame.draw.rect(self.screen, (255, 80, 170), rect, 2, border_radius=8)

    def draw_title(self):
        t = self.app_time
        pulse = (1 - (t / chart.BEAT) % 1) ** 4
        self.screen.blit(self.background, (0, 0))
        self.draw_lights(t, "rehearsal", pulse)
        self.draw_musician(t, pulse)
        if int(t / chart.BEAT) % 4 == 0 and (t / chart.BEAT) % 1 < 0.05:
            self.strum = 1.0
        self.draw_panel(pygame.Rect(320, 70, 600, 556))
        cx = 620
        glow = mix((255, 80, 170), WHITE, pulse * 0.5)
        self.blit_center(self.text("박자 반전!", 64, (120, 30, 90)), (cx + 3, 128))
        self.blit_center(self.text("박자 반전!", 64, glow), (cx, 125))
        self.blit_center(self.text("B A C K S T A G E  ·  백스테이지", 20, (90, 220, 255)), (cx, 180))
        story = ["공연 시작 30초 전, 무대 뒤 대기실.",
                 "음악가인 당신은 마지막 리듬 연습 중이다.",
                 "그런데 매니저가 뭔가 급한 얼굴로 달려오는데...?"]
        for i, line in enumerate(story):
            self.blit_center(self.text(line, 17, (230, 225, 240), False), (cx, 222 + i * 26))
        # 조작 방법
        self.blit_center(self.text("노트가 판정선에 닿는 순간 같은 방향키를 누르세요", 17, GOLD), (cx, 316))
        for i in range(4):
            x = cx - 135 + i * 90
            r = pygame.Rect(0, 0, 56, 50)
            r.center = (x, 368)
            pygame.draw.rect(self.screen, (30, 26, 44), r, border_radius=8)
            pygame.draw.rect(self.screen, LANE_COLORS[i], r, 2, border_radius=8)
            pygame.draw.polygon(self.screen, LANE_COLORS[i], arrow_points(x, 368, 15, i))
        self.blit_center(self.text("PERFECT +100   GOOD +50   MISS 0   ·   콤보 보너스!", 15, (190, 180, 210), False), (cx, 412))
        # 반전 규칙 안내
        warn = pygame.Rect(0, 0, 520, 64)
        warn.center = (cx, 466)
        pygame.draw.rect(self.screen, (60, 20, 80), warn, border_radius=10)
        pygame.draw.rect(self.screen, REVERSE_COLOR, warn, 2, border_radius=10)
        self.blit_center(self.text("※ 주의! 15초부터 규칙이 바뀝니다", 18, (255, 120, 140)), (cx, 452))
        self.blit_center(self.text("그때부터는 화살표의 반대 방향키를 눌러야 해요 (← ↔ →, ↑ ↔ ↓)", 14, WHITE, False), (cx, 480))
        self.draw_button(self.start_button, GOLD)
        self.draw_button(self.sound_button, (150, 140, 180), "소리: ON  [M]" if self.sound_on else "소리: OFF  [M]")
        self.blit_center(self.text("Enter / Space로도 시작", 12, (150, 140, 170), False), (870, 545))

    def draw_result(self):
        t = self.app_time
        pulse = (1 - (t / chart.BEAT) % 1) ** 4
        if (t / chart.BEAT) % 1 < 0.05:
            self.strum = 1.0
            self.strum_dir *= -1
        self.screen.blit(self.background, (0, 0))
        self.draw_lights(t, "fever", pulse)
        self.draw_musician(t, pulse, fever=True)
        self.draw_effects(t)
        rect = pygame.Rect(320, 70, 600, 556)
        self.draw_panel(rect)
        cx = 620
        g = self.game
        grade, message = g.rank()
        self.blit_center(self.text("리허설 종료!", 36, GOLD), (cx, 112))
        pygame.draw.circle(self.screen, (255, 80, 170), (cx - 170, 220), 56, 4)
        self.blit_center(self.text(grade, 72, WHITE), (cx - 170, 214))
        self.blit_center(self.text("최종 점수", 16, (180, 170, 200), False), (cx + 70, 172))
        self.blit_center(self.text(f"{g.score:,}", 48, GOLD), (cx + 70, 212))
        self.blit_center(self.text(f"정확도 {g.accuracy():.1f}%", 22, WHITE), (cx + 70, 262))
        rows = [("PERFECT", g.counts["PERFECT"], GOLD), ("GOOD", g.counts["GOOD"], (90, 220, 255)),
                ("MISS", g.counts["MISS"], (255, 90, 100)), ("최고 콤보", g.max_combo, (255, 80, 170))]
        for i, (name, value, color) in enumerate(rows):
            y = 320 + i * 38
            self.screen.blit(self.text(name, 22, color), (cx - 150, y))
            v = self.text(str(value), 22, WHITE)
            self.screen.blit(v, (cx + 150 - v.get_width(), y))
            pygame.draw.line(self.screen, (50, 44, 70), (cx - 150, y + 33), (cx + 150, y + 33))
        self.blit_center(self.text(message, 18, (230, 225, 240), False), (cx, 488))
        self.draw_button(self.retry_button, GOLD)
        self.draw_button(self.quit_button, (150, 140, 180))

    def draw(self):
        if self.state == "title":
            self.draw_title()
        elif self.state == "play":
            self.draw_play()
        else:
            self.draw_result()

    # ---------------- 메인 루프 ----------------
    def run(self):
        running = True
        while running:
            dt = min(self.clock.tick(FPS) / 1000, 0.05)
            for e in pygame.event.get():
                if not self.handle_event(e):
                    running = False
            self.update(dt)
            self.draw()
            pygame.display.flip()
        pygame.quit()


if __name__ == "__main__":
    App().run()
    sys.exit()
