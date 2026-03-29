#!/usr/bin/env python3
"""
Discord 회의록 다운로더
────────────────────────
지정한 Discord 채널에서 .txt / .md 파일 첨부물을 자동으로 다운로드합니다.

사용법:
    python3 discord_download.py                     # 기본 채널, 기본 저장 경로
    python3 discord_download.py --limit 200         # 최근 200개 메시지 탐색
    python3 discord_download.py --out ~/Downloads   # 저장 경로 변경
    python3 discord_download.py --channel <ID>      # 다른 채널 지정
    python3 discord_download.py --all-types         # 모든 파일 형식 다운로드
"""

import os
import re
import sys
import time
import argparse
import requests
from pathlib import Path
from datetime import datetime

# ──────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────

# 봇 토큰 자동 로드: ~/.claude/channels/discord/.env
ENV_FILE = Path.home() / ".claude" / "channels" / "discord" / ".env"

# 기본 채널 ID (access.json의 groups 키)
DEFAULT_CHANNEL_ID = "1486590597929111704"

# 기본 저장 경로
DEFAULT_OUT_DIR = Path.home() / "Library" / "CloudStorage" / \
    "GoogleDrive-davidlikessangria@gmail.com" / "My Drive" / \
    "Python" / "081_Simulation" / "discord_downloads"

# 다운로드 대상 확장자
DEFAULT_EXTENSIONS = {".txt", ".md", ".csv", ".json"}

DISCORD_API = "https://discord.com/api/v10"


# ──────────────────────────────────────────────
# 토큰 로드
# ──────────────────────────────────────────────

def load_token() -> str:
    """~/.claude/channels/discord/.env 에서 DISCORD_BOT_TOKEN 읽기"""
    # 1) 환경변수 우선
    if token := os.environ.get("DISCORD_BOT_TOKEN"):
        return token

    # 2) .env 파일
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            m = re.match(r"^DISCORD_BOT_TOKEN=(.+)$", line.strip())
            if m:
                return m.group(1).strip()

    print("❌  DISCORD_BOT_TOKEN을 찾을 수 없습니다.")
    print(f"   {ENV_FILE} 에 DISCORD_BOT_TOKEN=<토큰> 을 추가하거나")
    print("   환경변수로 설정하세요.")
    sys.exit(1)


# ──────────────────────────────────────────────
# Discord API 헬퍼
# ──────────────────────────────────────────────

def get_headers(token: str) -> dict:
    return {"Authorization": f"Bot {token}"}


def fetch_messages(token: str, channel_id: str, limit: int = 100) -> list[dict]:
    """채널의 메시지를 페이지네이션으로 가져오기"""
    headers = get_headers(token)
    messages = []
    before = None
    batch_size = 100  # Discord API 최대값

    print(f"📥  채널 {channel_id} 에서 메시지 탐색 중... (최대 {limit}개)")

    while len(messages) < limit:
        params = {"limit": min(batch_size, limit - len(messages))}
        if before:
            params["before"] = before

        resp = requests.get(
            f"{DISCORD_API}/channels/{channel_id}/messages",
            headers=headers,
            params=params,
            timeout=15,
        )

        if resp.status_code == 429:  # Rate limit
            retry_after = resp.json().get("retry_after", 1)
            print(f"   ⏳ 레이트 리밋. {retry_after:.1f}초 대기...")
            time.sleep(retry_after)
            continue

        if resp.status_code != 200:
            print(f"❌  API 오류 {resp.status_code}: {resp.text[:200]}")
            break

        batch = resp.json()
        if not batch:
            break

        messages.extend(batch)
        before = batch[-1]["id"]
        print(f"   {len(messages)}개 로드됨...", end="\r")

        if len(batch) < batch_size:
            break  # 더 이상 메시지 없음

    print(f"\n✅  총 {len(messages)}개 메시지 탐색 완료")
    return messages


def extract_attachments(messages: list[dict], extensions: set[str]) -> list[dict]:
    """메시지에서 지정 확장자 첨부파일 추출"""
    found = []
    for msg in messages:
        for att in msg.get("attachments", []):
            filename = att.get("filename", "")
            ext = Path(filename).suffix.lower()
            if ext in extensions:
                found.append({
                    "filename":   filename,
                    "url":        att["url"],
                    "size":       att.get("size", 0),
                    "message_id": msg["id"],
                    "author":     msg.get("author", {}).get("username", "unknown"),
                    "timestamp":  msg.get("timestamp", ""),
                })
    return found


def download_file(url: str, dest: Path, token: str) -> bool:
    """파일 다운로드. 성공하면 True."""
    try:
        resp = requests.get(
            url,
            headers=get_headers(token),
            timeout=30,
            stream=True,
        )
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return True
    except Exception as e:
        print(f"   ⚠️  다운로드 실패 ({dest.name}): {e}")
        return False


# ──────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Discord 채널에서 회의록 파일 다운로드")
    parser.add_argument("--channel", default=DEFAULT_CHANNEL_ID, help="채널 ID")
    parser.add_argument("--limit",   type=int, default=500,      help="탐색할 메시지 수 (기본: 500)")
    parser.add_argument("--out",     type=Path, default=DEFAULT_OUT_DIR, help="저장 경로")
    parser.add_argument("--all-types", action="store_true",      help="모든 파일 형식 다운로드")
    parser.add_argument("--no-dedup", action="store_true",       help="중복 파일도 재다운로드")
    args = parser.parse_args()

    token = load_token()
    extensions = None if args.all_types else DEFAULT_EXTENSIONS
    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    # 메시지 가져오기
    messages = fetch_messages(token, args.channel, limit=args.limit)

    # 첨부파일 추출
    ext_set = extensions or {Path(a["filename"]).suffix.lower()
                             for m in messages for a in m.get("attachments", [])}
    attachments = extract_attachments(messages, ext_set or DEFAULT_EXTENSIONS)

    if not attachments:
        print("📭  다운로드할 첨부파일이 없습니다.")
        return

    print(f"\n📎  첨부파일 {len(attachments)}개 발견:")
    for att in attachments:
        ts = att["timestamp"][:10] if att["timestamp"] else "unknown"
        size_kb = att["size"] / 1024
        print(f"   [{ts}] {att['filename']}  ({size_kb:.1f} KB)  — @{att['author']}")

    # 다운로드
    print(f"\n⬇️   저장 경로: {out_dir}\n")
    success, skip, fail = 0, 0, 0

    for att in attachments:
        ts = att["timestamp"][:10].replace("-", "") if att["timestamp"] else "00000000"
        # 파일명에 날짜 prefix: 20260327_filename.txt
        safe_name = re.sub(r'[\\/:*?"<>|]', "_", att["filename"])
        dest = out_dir / f"{ts}_{safe_name}"

        # 중복 체크
        if dest.exists() and not args.no_dedup:
            print(f"   ⏭️  건너뜀 (이미 존재): {dest.name}")
            skip += 1
            continue

        print(f"   ⬇️  {dest.name}...", end=" ")
        if download_file(att["url"], dest, token):
            size_kb = dest.stat().st_size / 1024
            print(f"✅  ({size_kb:.1f} KB)")
            success += 1
        else:
            fail += 1

    # 요약
    print(f"\n{'─'*50}")
    print(f"✅  다운로드 완료: {success}개")
    if skip:  print(f"⏭️  건너뜀 (중복): {skip}개")
    if fail:  print(f"❌  실패:         {fail}개")
    print(f"📁  저장 위치: {out_dir}")

    # 인덱스 파일 생성
    write_index(out_dir, attachments)


def write_index(out_dir: Path, attachments: list[dict]):
    """다운로드 목록을 README.md로 기록"""
    lines = [
        "# Discord 회의록 다운로드 목록\n",
        f"_마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n\n",
        "| 날짜 | 파일명 | 작성자 | 크기 |\n",
        "|------|--------|--------|------|\n",
    ]
    for att in sorted(attachments, key=lambda x: x["timestamp"], reverse=True):
        ts = att["timestamp"][:10] if att["timestamp"] else "-"
        size_kb = att["size"] / 1024
        lines.append(f"| {ts} | {att['filename']} | @{att['author']} | {size_kb:.1f} KB |\n")

    index_path = out_dir / "README.md"
    index_path.write_text("".join(lines), encoding="utf-8")
    print(f"📋  인덱스 저장: {index_path}")


if __name__ == "__main__":
    main()
