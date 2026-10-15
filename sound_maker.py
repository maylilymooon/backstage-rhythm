# sound_maker.py
# 8비트 EDM 스타일 음악과 효과음을 Python 표준 라이브러리만으로 만들어 WAV 파일로 저장한다.
# 외부 음원을 사용하지 않으므로 저작권 걱정이 없다.
# 직접 실행하면 assets 폴더에 소리 파일을 다시 만든다:  python sound_maker.py

import array
import math
import os
import random
import wave

import chart

SR = 22050                         # 샘플레이트(1초에 22050개 숫자) - 8비트 느낌에 충분하다
SONG_LENGTH = chart.GAME_LENGTH + 2.0   # 마지막 심벌 여운을 위해 2초 더
SOUND_VERSION = "3"                # 소리 설계를 바꾸면 이 값을 올려서 다시 생성되게 한다

ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
SOUND_FILES = ["song", "perfect", "good", "miss", "alert", "select"]

rng = random.Random(144)   # 항상 같은 소리가 나오도록 고정된 난수


# ---------------- 기본 소리 재료 ----------------
def new_buffer(seconds):
    return [0.0] * int(seconds * SR)


def midi_to_freq(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def tone(buf, start, dur, freq, vol, shape="square", duty=0.5,
         decay=0.0, attack=0.004, release=0.03, slide_to=None):
    """음 하나를 buf에 더한다. shape: square / triangle / sine"""
    i0 = int(start * SR)
    n = int(dur * SR)
    phase = 0.0
    two_pi = 2 * math.pi
    for i in range(n):
        idx = i0 + i
        if idx >= len(buf):
            break
        t = i / SR
        f = freq if slide_to is None else freq + (slide_to - freq) * (i / n)
        phase += f / SR
        p = phase % 1.0
        if shape == "square":
            s = 1.0 if p < duty else -1.0
        elif shape == "triangle":
            s = 4.0 * abs(p - 0.5) - 1.0
        else:
            s = math.sin(two_pi * p)
        env = 1.0
        if t < attack:
            env = t / attack
        if decay:
            env *= math.exp(-t * decay)
        remain = dur - t
        if remain < release:
            env *= remain / release
        buf[idx] += s * vol * env


def noise(buf, start, dur, vol, decay=20.0, highpass=True, rise=False):
    """잡음(드럼, 심벌, 효과음용). rise=True면 점점 커진다."""
    i0 = int(start * SR)
    n = int(dur * SR)
    prev = 0.0
    for i in range(n):
        idx = i0 + i
        if idx >= len(buf):
            break
        t = i / SR
        x = rng.uniform(-1, 1)
        s = x - prev if highpass else x     # 앞 값과의 차이 = 고음만 남기는 간단한 필터
        prev = x
        if rise:
            env = (i / n) ** 2
        else:
            env = math.exp(-t * decay)
        buf[idx] += s * vol * env


# ---------------- 드럼 ----------------
def kick(buf, start, vol=0.9):
    n = int(0.22 * SR)
    i0 = int(start * SR)
    phase = 0.0
    for i in range(n):
        idx = i0 + i
        if idx >= len(buf):
            break
        t = i / SR
        f = 45 + 120 * math.exp(-t * 35)     # 높은 음에서 낮은 음으로 '쿵'
        phase += f / SR
        buf[idx] += math.sin(2 * math.pi * phase) * vol * math.exp(-t * 14)


def snare(buf, start, vol=0.45):
    noise(buf, start, 0.16, vol * 0.8, decay=22, highpass=False)
    tone(buf, start, 0.10, 185, vol * 0.5, shape="sine", decay=30)


def hat(buf, start, vol=0.12):
    noise(buf, start, 0.045, vol, decay=90)


def clap(buf, start, vol=0.3):
    for k in range(3):
        noise(buf, start + k * 0.011, 0.012, vol, decay=200, highpass=False)
    noise(buf, start + 0.033, 0.14, vol, decay=28, highpass=False)


def crash(buf, start, vol=0.3):
    noise(buf, start, 1.4, vol, decay=3.0)


# ---------------- 화음 ----------------
CHORDS = {
    "Am": [57, 60, 64],
    "F": [53, 57, 60],
    "C": [55, 60, 64],
    "G": [55, 59, 62],
}
NORMAL_PROGRESSION = ["Am", "F", "C", "G"]
REVERSE_PROGRESSION = ["G", "C", "F", "Am"]   # 반전 구간은 화음 진행도 거꾸로!


def chord_for_bar(bar):
    if bar <= 8:
        return NORMAL_PROGRESSION[bar % 4]
    if bar == 9:
        return "Am"
    if bar <= 14:
        return REVERSE_PROGRESSION[(bar - 10) % 4]
    if bar <= 17:
        return NORMAL_PROGRESSION[(bar - 15) % 4]
    return "Am"


def lead_pitch(chord, lane):
    """레인별 멜로디 음: ← 가장 낮은 음 ~ → 가장 높은 음"""
    c = CHORDS[chord]
    return [c[0] + 12, c[1] + 12, c[2] + 12, c[0] + 24][lane]


# ---------------- 곡 만들기 ----------------
def make_song():
    buf = new_buffer(SONG_LENGTH)
    B = chart.BEAT

    for bar in range(18):
        bar_start = bar * 4                 # 박 번호
        chord = CHORDS[chord_for_bar(bar)]
        tension = 6 <= bar <= 8
        reverse = 10 <= bar <= 14
        fever = bar >= 15
        full = tension or reverse or fever  # 베이스와 스네어가 들어가는 구간

        if bar == 9:
            # 돌발 상황 마디: 쾅! 하고 멈춘 뒤 긴장감 있는 화음만
            kick(buf, bar_start * B, 1.0)
            crash(buf, bar_start * B, 0.35)
            for m in chord:
                tone(buf, bar_start * B, 4 * B, midi_to_freq(m), 0.05,
                     shape="triangle", attack=0.3, release=0.3)
            noise(buf, (bar_start + 2) * B, 2 * B, 0.15, rise=True)   # 다시 시작 전 상승음
            continue

        for beat in range(4):
            b = bar_start + beat
            kick(buf, b * B)
            # 하이햇: 기본은 반 박, 피버는 1/4박
            if fever:
                for k in range(4):
                    hat(buf, (b + k * 0.25) * B, 0.10 if k % 2 == 0 else 0.07)
            else:
                hat(buf, (b + 0.5) * B, 0.12)
                if full:
                    hat(buf, b * B, 0.06)
            # 스네어 / 박수: 2, 4번째 박
            if full and beat in (1, 3):
                snare(buf, b * B)
                if fever:
                    clap(buf, b * B)

            # 베이스 (10초 이후): 반 박마다 '둠-둥' 옥타브 왕복
            if full:
                root = chord[0] - 24
                for k in range(2):
                    m = root + (12 if (k == 1 and (reverse or fever)) else 0)
                    tone(buf, (b + k * 0.5) * B, B * 0.45, midi_to_freq(m),
                         0.11, shape="square", duty=0.5, release=0.04)

            # 배경 아르페지오 (첫 마디 제외)
            if bar >= 1:
                steps = 4 if fever else 2
                order = chord if not reverse else list(reversed(chord))
                for k in range(steps):
                    m = order[(beat * steps + k) % 3] + (12 if fever else 0)
                    tone(buf, (b + k / steps) * B, B / steps * 0.8,
                         midi_to_freq(m), 0.035, shape="triangle")

        # 긴장감 구간 마지막 마디: 스네어 연타 + 상승음
        if bar == 8:
            for k in range(8):
                snare(buf, (bar_start + 2 + k * 0.25) * B, 0.15 + k * 0.04)
            noise(buf, bar_start * B, 4 * B, 0.18, rise=True)
            tone(buf, bar_start * B, 4 * B, 200, 0.04, slide_to=1200)
        if bar == 15:
            crash(buf, bar_start * B, 0.3)   # 피버 시작 심벌

    # 멜로디: 노트 하나하나가 멜로디 음이 된다 (노트 = 음악)
    pattern = sorted(chart.PATTERN)
    for i, (beat, lane) in enumerate(pattern):
        bar = int(beat // 4)
        m = lead_pitch(chord_for_bar(bar), lane)
        next_beat = pattern[i + 1][0] if i + 1 < len(pattern) else beat + 2
        length = min(next_beat - beat, 1.0) * B * 0.9
        start = beat * B
        duty = 0.125 if chart.is_reversed_at(start) else 0.25   # 반전 후 음색 변화
        tone(buf, start, length, midi_to_freq(m), 0.10, shape="square",
             duty=duty, decay=3.0)
        if start >= chart.FEVER_TIME:
            tone(buf, start, length, midi_to_freq(m + 12), 0.05, shape="sine")

    # 마지막 '쾅!' (30초) - 공연 시작
    end = chart.GAME_LENGTH
    kick(buf, end, 1.0)
    crash(buf, end, 0.4)
    for m in CHORDS["Am"]:
        tone(buf, end, 1.8, midi_to_freq(m + 12), 0.06, shape="square",
             duty=0.25, decay=1.5)
    return buf


# ---------------- 효과음 ----------------
def make_perfect():
    buf = new_buffer(0.2)
    tone(buf, 0.0, 0.07, 1568, 0.35, shape="sine", decay=25)
    tone(buf, 0.03, 0.15, 2093, 0.35, shape="sine", decay=20)
    return buf


def make_good():
    buf = new_buffer(0.12)
    tone(buf, 0.0, 0.1, 1319, 0.3, shape="sine", decay=30)
    return buf


def make_miss():
    buf = new_buffer(0.2)
    tone(buf, 0.0, 0.18, 150, 0.18, shape="square", slide_to=70)
    noise(buf, 0.0, 0.08, 0.15, decay=40)
    return buf


def make_alert():
    """반전 이벤트 전용: 경보음 + 레코드 긁는 소리"""
    buf = new_buffer(1.1)
    noise(buf, 0.0, 0.25, 0.3, decay=10)
    tone(buf, 0.0, 0.25, 900, 0.15, shape="square", slide_to=150)
    for k in range(4):
        f = 880 if k % 2 == 0 else 1175
        tone(buf, 0.25 + k * 0.16, 0.15, f, 0.18, shape="square", duty=0.3)
    return buf


def make_select():
    buf = new_buffer(0.15)
    tone(buf, 0.0, 0.05, 660, 0.2, shape="square", duty=0.25)
    tone(buf, 0.05, 0.08, 990, 0.2, shape="square", duty=0.25)
    return buf


# ---------------- 저장 ----------------
def save_wav(path, buf):
    peak = max(1e-9, max(abs(x) for x in buf))
    gain = 0.9 / math.tanh(min(peak, 3.0)) if peak > 1 else 0.9
    data = array.array("h")
    for x in buf:
        y = math.tanh(x) * gain                  # 부드럽게 눌러서 찢어지는 소리 방지
        data.append(int(max(-1.0, min(1.0, y)) * 32767))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def sound_path(name):
    return os.path.join(ASSET_DIR, name + ".wav")


def sounds_ready():
    stamp = os.path.join(ASSET_DIR, "version.txt")
    if not os.path.exists(stamp):
        return False
    with open(stamp, encoding="utf-8") as f:
        if f.read().strip() != SOUND_VERSION:
            return False
    return all(os.path.exists(sound_path(n)) for n in SOUND_FILES)


def generate_all():
    os.makedirs(ASSET_DIR, exist_ok=True)
    makers = {
        "song": make_song, "perfect": make_perfect, "good": make_good,
        "miss": make_miss, "alert": make_alert, "select": make_select,
    }
    for name, maker in makers.items():
        save_wav(sound_path(name), maker())
    with open(os.path.join(ASSET_DIR, "version.txt"), "w", encoding="utf-8") as f:
        f.write(SOUND_VERSION)


def ensure_sounds():
    """소리 파일이 없으면 만든다. (처음 한 번만 몇 초 걸림)"""
    if not sounds_ready():
        generate_all()


if __name__ == "__main__":
    import time
    t0 = time.time()
    generate_all()
    print(f"assets 폴더에 소리 파일 생성 완료 ({time.time() - t0:.1f}초)")
