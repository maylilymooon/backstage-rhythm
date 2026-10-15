# game_logic.py
# 노트 판정, 점수, 콤보를 계산하는 파일 (화면/소리와 분리되어 있어 테스트하기 쉽다)

import chart

# 판정 범위(초): 노트 도착 시간과 키를 누른 시간의 차이
PERFECT_WINDOW = 0.070
GOOD_WINDOW = 0.140
MISS_WINDOW = 0.200   # 이보다 일찍 누르면 무시, GOOD 범위 밖~이 범위 안이면 MISS

SCORE = {"PERFECT": 100, "GOOD": 50, "MISS": 0}
ACCURACY_WEIGHT = {"PERFECT": 1.0, "GOOD": 0.5, "MISS": 0.0}


class Note:
    def __init__(self, beat, lane):
        self.time = chart.beat_to_time(beat)   # 판정선 도착 시간(초)
        self.lane = lane                        # 화면에 표시되는 레인
        # 반전 여부는 '노트의 도착 시간'으로 정한다.
        # 그래서 규칙이 바뀌는 순간에도 노트마다 정답이 하나로 정해진다.
        self.reversed = chart.is_reversed_at(self.time)
        self.judged = False                     # 이미 판정했는지 (중복 판정 방지)
        self.result = None

    @property
    def key_lane(self):
        """이 노트를 맞히려면 눌러야 하는 방향키"""
        if self.reversed:
            return chart.opposite_lane(self.lane)
        return self.lane


class RhythmGame:
    def __init__(self):
        self.reset()

    def reset(self):
        """재시작할 때 모든 상태를 처음으로 되돌린다."""
        self.notes = [Note(beat, lane) for beat, lane in chart.PATTERN]
        self.notes.sort(key=lambda n: n.time)
        self.score = 0
        self.combo = 0
        self.max_combo = 0
        self.counts = {"PERFECT": 0, "GOOD": 0, "MISS": 0}
        self.events = []   # 화면/소리에 알려 줄 판정 기록: (결과, 레인, 시간)

    def _judge(self, note, result, t):
        note.judged = True
        note.result = result
        self.counts[result] += 1

        if result == "MISS":
            self.combo = 0
        else:
            self.combo += 1
            self.max_combo = max(self.max_combo, self.combo)
            # 콤보 보너스: 10콤보마다 +5점, 최대 +25점
            bonus = min(self.combo // 10, 5) * 5
            self.score += SCORE[result] + bonus

        self.events.append((result, note.lane, t))

    def press(self, key_lane, t):
        """방향키를 눌렀을 때. 판정 결과를 돌려준다. (해당 노트가 없으면 None)"""
        candidates = [
            n for n in self.notes
            if not n.judged
            and n.key_lane == key_lane
            and abs(n.time - t) <= MISS_WINDOW
        ]
        if not candidates:
            return None

        # 가장 가까운 노트 하나만 판정한다
        note = min(candidates, key=lambda n: abs(n.time - t))
        diff = abs(note.time - t)
        if diff <= PERFECT_WINDOW:
            result = "PERFECT"
        elif diff <= GOOD_WINDOW:
            result = "GOOD"
        else:
            result = "MISS"
        self._judge(note, result, t)
        return result

    def update(self, t):
        """누르지 않고 지나간 노트를 MISS 처리한다."""
        for n in self.notes:
            if not n.judged and t > n.time + GOOD_WINDOW:
                self._judge(n, "MISS", t)

    def accuracy(self):
        """정확도(%) - PERFECT 100%, GOOD 50%, MISS 0%"""
        judged = sum(self.counts.values())
        if judged == 0:
            return 0.0
        total = sum(self.counts[r] * ACCURACY_WEIGHT[r] for r in self.counts)
        return total / judged * 100

    def rank(self):
        acc = self.accuracy()
        if acc >= 90:
            return "S", "완벽한 리허설! 관객들이 벌써 환호하고 있어요!"
        if acc >= 75:
            return "A", "훌륭해요! 반전 콘셉트도 문제없겠네요!"
        if acc >= 55:
            return "B", "좋아요! 무대에서는 더 잘할 수 있어요!"
        return "C", "조금 더 연습이 필요해요... 그래도 쇼는 계속됩니다!"
