# build_web.py
# 웹 브라우저 버전을 만드는 스크립트 (pygbag 사용)
# 실행: python build_web.py
# 결과: build/web_src/backstage_rhythm/build/web 폴더 (index.html + 게임 파일)
#
# 필요한 도구 (처음 한 번만 설치):  python -m pip install pygbag soundfile

import os
import shutil
import subprocess
import sys

import soundfile

import sound_maker

HERE = os.path.dirname(os.path.abspath(__file__))
STAGE = os.path.join(HERE, "build", "web_src", "backstage_rhythm")
# sound_maker.py는 넣지 않는다: 웹 브라우저용 Python에는 wave 모듈이 없어서 미리 만든 OGG만 쓴다
GAME_FILES = ["main.py", "chart.py", "game_logic.py"]


def main():
    # 1) 소리 파일 준비 후 OGG로 변환 (브라우저용)
    sound_maker.ensure_sounds()
    for name in sound_maker.SOUND_FILES:
        data, rate = soundfile.read(sound_maker.sound_path(name))
        soundfile.write(os.path.join(sound_maker.ASSET_DIR, name + ".ogg"), data, rate,
                        format="OGG", subtype="VORBIS")
    print("OGG 변환 완료")

    # 2) 웹에 필요한 파일만 따로 모으기 (WAV, 테스트 파일 제외)
    if os.path.exists(STAGE):
        shutil.rmtree(STAGE)
    os.makedirs(os.path.join(STAGE, "assets"))
    for f in GAME_FILES:
        shutil.copy(os.path.join(HERE, f), STAGE)
    for name in sound_maker.SOUND_FILES:
        shutil.copy(os.path.join(sound_maker.ASSET_DIR, name + ".ogg"), os.path.join(STAGE, "assets"))
    shutil.copytree(os.path.join(sound_maker.ASSET_DIR, "fonts"), os.path.join(STAGE, "assets", "fonts"))

    # 3) pygbag로 웹 버전 빌드
    env = dict(os.environ, PYTHONUTF8="1")   # 한글 주석이 있는 파일을 UTF-8로 읽게 한다
    subprocess.run([sys.executable, "-m", "pygbag", "--build",
                    "--title", "박자 반전! 백스테이지", STAGE], check=True, env=env)

    # 4) 탭을 닫을 때 "정말 나가시겠습니까?" 확인창이 뜨지 않게 한다
    out_dir = os.path.join(STAGE, "build", "web")
    index = os.path.join(out_dir, "index.html")
    with open(index, encoding="utf-8") as f:
        html = f.read()
    with open(index, "w", encoding="utf-8") as f:
        f.write(html.replace("can_close : 0", "can_close : 1"))
    print("완료:", out_dir)


if __name__ == "__main__":
    main()
