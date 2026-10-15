# test_game.py
# 자동으로 확인할 수 있는 기능 테스트
# 실행: python test_game.py

import os
import wave

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")   # 창을 띄우지 않고 테스트
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import chart
import game_logic
import sound_maker
from game_logic import RhythmGame

passed = 0


def check(name, condition):
    global passed
    assert condition, "실패: " + name
    passed += 1
    print("  OK -", name)


def first_note(game, condition):
    return next(n for n in game.notes if condition(n))


print("[1] 노트 패턴과 박자")
times = [chart.beat_to_time(b) for b, _ in chart.PATTERN]
check("BPM 144에서 구간 경계가 마디와 일치", all(abs((x / chart.BAR) - round(x / chart.BAR)) < 1e-9
                                         for x in (chart.TENSION_TIME, chart.REVERSE_TIME, chart.FEVER_TIME, chart.GAME_LENGTH)))
check("모든 노트가 반 박 단위 박자 위에 있음", all((b * 2) == int(b * 2) for b, _ in chart.PATTERN))
check("모든 노트가 0초~30초 안에 도착", all(0 < x < chart.GAME_LENGTH for x in times))
check("같은 시간에 같은 레인 노트 중복 없음", len(set(chart.PATTERN)) == len(chart.PATTERN))
check("반전 시점(15초) 앞뒤 1.25초 안에 노트 없음", all(abs(x - chart.REVERSE_TIME) > 1.25 for x in times))


def density(a, b):
    return sum(1 for x in times if a <= x < b) / (b - a)


d_reh = density(0, chart.TENSION_TIME)
d_ten = density(chart.TENSION_TIME, chart.REVERSE_TIME - 1.5)
d_rev = density(chart.REVERSE_TIME, chart.FEVER_TIME)
d_fev = density(chart.FEVER_TIME, chart.GAME_LENGTH)
print(f"     초당 노트 수: 리허설 {d_reh:.2f} / 긴장 {d_ten:.2f} / 반전 {d_rev:.2f} / 피버 {d_fev:.2f}")
check("밀도: 리허설 < 긴장감 < 피버", d_reh < d_ten < d_fev)
check("피버 구간이 가장 빽빽함", d_fev > max(d_reh, d_ten, d_rev))
gaps_after_reverse = [x for x in times if chart.REVERSE_TIME < x < chart.REVERSE_TIME + 3.4]
check("반전 직후 적응 구간은 2박 간격(쉬운 패턴)",
      all(abs((b - a) - 2 * chart.BEAT) < 1e-9 for a, b in zip(gaps_after_reverse, gaps_after_reverse[1:])))

print("[2] 판정")
g = RhythmGame()
n = g.notes[0]
check("정확한 타이밍 = PERFECT", g.press(n.key_lane, n.time) == "PERFECT")
check("판정된 노트는 다시 판정되지 않음", g.press(n.key_lane, n.time) is None)
n = g.notes[1]
check("0.1초 늦게 = GOOD", g.press(n.key_lane, n.time + 0.1) == "GOOD")
n = g.notes[2]
check("0.17초 일찍 = MISS (노트 소모)", g.press(n.key_lane, n.time - 0.17) == "MISS" and n.judged)
n = g.notes[3]
check("0.3초 일찍 = 무시 (판정 없음)", g.press(n.key_lane, n.time - 0.3) is None and not n.judged)
check("다른 방향키 = 판정 없음", g.press((n.key_lane + 1) % 4, n.time) is None and not n.judged)

g = RhythmGame()
n = g.notes[0]
g.update(n.time + 0.1)
check("GOOD 범위 안에서는 아직 MISS 아님", not n.judged)
g.update(n.time + game_logic.GOOD_WINDOW + 0.01)
check("누르지 않고 지나가면 MISS", n.judged and n.result == "MISS" and g.counts["MISS"] == 1)
g.update(n.time + 0.5)          # 다음 노트(0.83초 뒤)는 아직 지나가지 않은 시점
check("지나간 노트는 MISS가 한 번만 기록됨", g.counts["MISS"] == 1)

# 가까운 노트 하나만 처리: 같은 키 노트 둘이 0.17초 간격으로 붙어 있을 때
g = RhythmGame()
a, b = game_logic.Note(10, 0), game_logic.Note(10.4, 0)
g.notes = [a, b]
g.press(0, a.time + 0.03)          # 두 노트 모두 판정 범위 안이지만 a가 더 가깝다
check("가장 가까운 노트 하나만 판정", a.judged and a.result == "PERFECT" and not b.judged)
g.press(0, b.time)
check("다음 입력은 남은 노트를 판정", b.judged)

print("[3] 반전 규칙")
g = RhythmGame()
normal = first_note(g, lambda x: x.time < chart.REVERSE_TIME)
rev = first_note(g, lambda x: x.time >= chart.REVERSE_TIME)
check("15초 전 노트: 표시 방향 = 정답", normal.key_lane == normal.lane and not normal.reversed)
check("15초 후 노트: 반대 방향 = 정답", rev.reversed and rev.key_lane == chart.opposite_lane(rev.lane))
check("반대 방향 짝: ←↔→, ↓↔↑", [chart.opposite_lane(i) for i in range(4)] == [3, 2, 1, 0])
check("반전 노트를 표시 방향으로 누르면 판정 없음", g.press(rev.lane, rev.time) is None)
check("반전 노트를 반대 방향으로 누르면 PERFECT", g.press(chart.opposite_lane(rev.lane), rev.time) == "PERFECT")
check("피버 노트도 반전 유지", all(x.reversed for x in g.notes if x.time >= chart.FEVER_TIME))

print("[4] 점수, 콤보, 정확도")
g = RhythmGame()
for x in g.notes[:12]:
    g.press(x.key_lane, x.time)
check("콤보 12", g.combo == 12 and g.max_combo == 12)
check("콤보 보너스 포함 점수 (100x12 + 10~12콤보 보너스 5x3)", g.score == 1200 + 15)
g.update(g.notes[12].time + 1)
check("MISS 후 콤보 0, 최고 콤보 유지", g.combo == 0 and g.max_combo == 12)

g = RhythmGame()
g.press(g.notes[0].key_lane, g.notes[0].time)           # PERFECT
g.press(g.notes[1].key_lane, g.notes[1].time + 0.1)     # GOOD
g.update(g.notes[2].time + 0.2)                         # MISS
check("정확도 = (100 + 50 + 0) / 3 = 50%", abs(g.accuracy() - 50.0) < 1e-9)

g = RhythmGame()
for x in g.notes:
    g.press(x.key_lane, x.time)
check(f"전부 PERFECT: 정확도 100%, 최고 콤보 {len(g.notes)}", g.accuracy() == 100 and g.max_combo == len(g.notes))
check("전부 PERFECT면 S 랭크", g.rank()[0] == "S")
g.reset()
check("reset: 점수/콤보/노트 초기화", g.score == 0 and g.combo == 0 and g.max_combo == 0
      and not any(x.judged for x in g.notes) and sum(g.counts.values()) == 0)

print("[5] 소리 파일")
sound_maker.ensure_sounds()
for name in sound_maker.SOUND_FILES:
    check(f"{name}.wav 존재", os.path.exists(sound_maker.sound_path(name)))
with wave.open(sound_maker.sound_path("song")) as w:
    length = w.getnframes() / w.getframerate()
check(f"음악 길이 {length:.1f}초 (30초 + 여운)", chart.GAME_LENGTH <= length <= chart.GAME_LENGTH + 3)

print("[6] 게임 화면 (창 없이 실행)")
import pygame
import main

app = main.App()
check("타이틀 화면 그리기", (app.draw(), True)[1] and app.state == "title")
app.start_play()
check("시작하면 play 상태", app.state == "play")

# 가짜 시간으로 30초를 빠르게 돌리며, 노트마다 정답 키를 누른다
step = 1 / 60
t = -0.05
next_i = 0
while app.state == "play":
    app.fake_time = t
    while next_i < len(app.game.notes) and app.game.notes[next_i].time <= t:
        app.press_key(app.game.notes[next_i].key_lane)
        next_i += 1
    app.update(step)
    app.draw()
    t += step
check("30초 진행 후 결과 화면으로 전환", app.state == "result")
check("15초 반전 이벤트 발생", app.alert_done)
check("25초 피버 이벤트 발생", app.fever_done)
c = app.game.counts
print(f"     자동 플레이 결과: PERFECT {c['PERFECT']}, GOOD {c['GOOD']}, MISS {c['MISS']}, 점수 {app.game.score}")
check("자동 플레이(프레임 단위 입력)에서 MISS 없음", c["MISS"] == 0)
app.draw()
app.fake_time = None

# 일시정지 / 재개
app.start_play()
app.pause()
t1 = app.game_time()
pygame.time.wait(200)
check("일시정지 중에는 게임 시간이 멈춤", abs(app.game_time() - t1) < 1e-6)
app.resume()
check("재개 후 시간이 이어서 흐름", abs(app.game_time() - t1) < 0.05)
app.handle_event(pygame.event.Event(pygame.WINDOWFOCUSLOST))
check("창 포커스를 잃으면 자동 일시정지", app.paused)
app.resume()

# 재시작
app.press_key(0)
app.game.score = 999
app.start_play()
check("재시작: 점수, 콤보, 노트, 이벤트 초기화",
      app.game.score == 0 and app.game.combo == 0 and not app.alert_done
      and not any(x.judged for x in app.game.notes) and app.game_time() < 0.1)
before = app.sound_on
app.toggle_sound()
check("소리 ON/OFF 전환", app.sound_on != before)
pygame.quit()

print(f"\n모든 테스트 통과: {passed}개")
