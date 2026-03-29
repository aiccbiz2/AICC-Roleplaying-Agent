"""퀴즈 풀 사전 생성 스크립트 — CLI에서 실행: python3 generate_quiz_pool.py"""
from __future__ import annotations

import json
import time

from quiz import QUIZ_CATEGORIES, generate_quiz
from config import PROJECT_DIR

POOL_PATH = PROJECT_DIR / "quiz_pool.json"
PER_COMBO = 5  # 카테고리×난이도 조합당 문제 수
DIFFICULTIES = ["초급", "중급", "고급"]


def main():
    # 기존 풀이 있으면 로드 (이어서 생성 가능)
    if POOL_PATH.exists():
        pool = json.loads(POOL_PATH.read_text(encoding="utf-8"))
        print(f"기존 풀 로드: {len(pool)}문제")
    else:
        pool = []

    # 이미 생성된 조합 카운트
    existing = {}
    for q in pool:
        key = (q.get("category", ""), q.get("difficulty", ""))
        existing[key] = existing.get(key, 0) + 1

    total_new = 0
    for cat in QUIZ_CATEGORIES:
        for diff in DIFFICULTIES:
            key = (cat, diff)
            already = existing.get(key, 0)
            needed = PER_COMBO - already
            if needed <= 0:
                print(f"  [SKIP] {cat} / {diff} — 이미 {already}문제")
                continue

            print(f"  [GEN] {cat} / {diff} — {needed}문제 생성 중...")
            for i in range(needed):
                try:
                    quiz = generate_quiz(category=cat, difficulty=diff)
                    pool.append(quiz)
                    total_new += 1
                    print(f"    #{already + i + 1} 완료")
                    # 저장 (중간 저장 — 중단 시 복구 가능)
                    POOL_PATH.write_text(
                        json.dumps(pool, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    time.sleep(1)  # CLI 호출 간격
                except Exception as e:
                    print(f"    #{already + i + 1} 실패: {e}")

    print(f"\n완료! 총 {len(pool)}문제 (신규 {total_new}문제)")
    print(f"저장 위치: {POOL_PATH}")


if __name__ == "__main__":
    main()
