"""
update_conferences.py
─────────────────────
GitHub Actions에서 매일 실행되어 index.html 안의 학회 정보를
Anthropic API + 웹 검색으로 검증·갱신합니다.
"""

import os, re, json, datetime
import anthropic

# ── 설정 ──────────────────────────────────────────────────────
HTML_FILE  = "index.html"
TODAY      = datetime.date.today().isoformat()
BATCH_SIZE = 7          # 배치 크기 줄임 → 응답 잘림 방지
MAX_TOKENS = 8192       # 충분한 토큰 확보
client     = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM = f"""You are an HCI conference database updater. Today is {TODAY}.
For each conference given, search the web and return ONLY a valid JSON array with no surrounding text, no explanation, no markdown code fences.
Start your response with [ and end with ].
Each element must have these exact keys:
  id, dateLabel, deadlineLabel, deadlineDate (YYYY-MM-DD or null), url, dateMonth (integer 1-12)
Rules:
- Keep original value for anything you could not verify with certainty.
- deadlineDate must be the paper submission deadline in YYYY-MM-DD, or null.
- dateMonth must be the integer month the conference is held.
- If a conference already took place, keep data but append ' ✓완료' to dateLabel if not already present.
- For rolling deadlines (IMWUT, PACMHCI), set deadlineDate to the next upcoming round.
- URLs must be the official conference website for the current or upcoming year.
- Output ONLY the JSON array. No text before or after."""

# ── JSON 추출 (텍스트에서 배열 부분만 파싱) ───────────────────
def extract_json_array(text: str) -> list:
    """응답 텍스트에서 JSON 배열만 추출합니다."""
    # 1) 코드 펜스 제거
    text = re.sub(r"```(?:json)?", "", text).strip()

    # 2) 첫 번째 [ 부터 마지막 ] 까지 추출
    start = text.find("[")
    end   = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("JSON 배열을 찾을 수 없음")

    raw = text[start:end + 1]

    # 3) 파싱 시도
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # 4) 잘린 JSON 복구 시도: 마지막 완성된 객체까지만 사용
        fixed = fix_truncated_json(raw)
        return json.loads(fixed)

def fix_truncated_json(raw: str) -> str:
    """잘린 JSON 배열을 마지막 완성된 객체까지만 복원합니다."""
    depth   = 0
    in_str  = False
    escape  = False
    last_complete = 0

    for i, ch in enumerate(raw):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_str:
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                last_complete = i + 1

    if last_complete == 0:
        raise ValueError("완성된 JSON 객체를 찾을 수 없음")

    trimmed = raw[:last_complete].rstrip().rstrip(",")
    return "[" + trimmed.lstrip("[") + "]"

# ── 파싱: index.html에서 conferences 배열 추출 ─────────────────
def extract_conferences(html: str) -> list[dict]:
    m = re.search(r"const conferences = \[(.*?)\];\n\n// ── State", html, re.DOTALL)
    if not m:
        raise ValueError("conferences 배열을 찾을 수 없습니다")

    confs = []
    for line in m.group(1).split("\n"):
        line = line.strip()
        if not line.startswith("{id:"):
            continue

        def get(field):
            sm = re.search(rf"{field}:'([^']*)'", line)
            if sm:
                return sm.group(1)
            if re.search(rf"{field}:null", line):
                return None
            im = re.search(rf"{field}:(\d+)", line)
            return int(im.group(1)) if im else None

        confs.append({
            "id":            get("id"),
            "abbr":          get("abbr"),
            "name":          get("name"),
            "dateLabel":     get("dateLabel"),
            "deadlineLabel": get("deadlineLabel"),
            "deadlineDate":  get("deadlineDate"),
            "dateMonth":     get("dateMonth"),
            "url":           get("url"),
        })
    return confs

# ── API 호출 ──────────────────────────────────────────────────
def fetch_updates(batch: list[dict]) -> list[dict]:
    conf_list = "\n".join(
        f'id:{c["id"]} abbr:"{c["abbr"]}" name:"{c["name"]}" '
        f'currentDate:"{c["dateLabel"]}" currentDeadline:"{c["deadlineLabel"]}" '
        f'currentDeadlineDate:"{c["deadlineDate"] or ""}" url:"{c["url"]}"'
        for c in batch
    )

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=MAX_TOKENS,
        system=SYSTEM,
        messages=[{"role": "user", "content": f"Verify and update these {len(batch)} conferences:\n{conf_list}"}],
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
    )

    # 텍스트 블록만 합치기
    text = "".join(
        b.text for b in message.content
        if hasattr(b, "text") and b.type == "text"
    ).strip()

    print(f"    응답 길이: {len(text)}자, stop_reason: {message.stop_reason}")

    if not text:
        print("    ⚠ 텍스트 응답 없음")
        return []

    try:
        result = extract_json_array(text)
        return result
    except (ValueError, json.JSONDecodeError) as e:
        print(f"    ⚠ JSON 파싱 실패: {e}")
        print(f"    응답 앞부분:\n{text[:400]}")
        return []

# ── index.html 패치 ────────────────────────────────────────────
def patch_html(html: str, updates: list[dict]) -> tuple[str, list[str]]:
    changed = []
    for u in updates:
        cid = u.get("id")
        if not cid:
            continue

        m = re.search(rf"(\{{id:'{re.escape(cid)}'[^\n]*\}})", html)
        if not m:
            continue
        old_line = m.group(1)
        new_line = old_line

        def swap_str(line, field, val):
            if val is None:
                return re.sub(rf"{field}:'[^']*'", f"{field}:null", line)
            # 값 안의 작은따옴표 이스케이프
            safe = str(val).replace("'", "\\'")
            return re.sub(rf"{field}:'[^']*'", f"{field}:'{safe}'", line)

        def swap_int(line, field, val):
            return re.sub(rf"{field}:\d+", f"{field}:{int(val)}", line) if val else line

        fields_changed = []
        for field in ("dateLabel", "deadlineLabel", "deadlineDate", "url"):
            new_val = u.get(field)
            old_m = re.search(rf"{field}:'([^']*)'", old_line)
            old_val = old_m.group(1) if old_m else None
            if new_val and new_val != old_val:
                new_line = swap_str(new_line, field, new_val)
                fields_changed.append(field)

        if u.get("dateMonth"):
            old_dm = re.search(r"dateMonth:(\d+)", old_line)
            if old_dm and int(u["dateMonth"]) != int(old_dm.group(1)):
                new_line = swap_int(new_line, "dateMonth", u["dateMonth"])
                fields_changed.append("dateMonth")

        if new_line != old_line:
            html = html.replace(old_line, new_line, 1)
            changed.append(f"{cid} ({', '.join(fields_changed)})")

    # TODAY 상수 업데이트
    html = re.sub(
        r"const TODAY = new Date\('[^']*'\);",
        f"const TODAY = new Date('{TODAY}');",
        html,
    )
    # 헤더 업데이트 태그
    html = re.sub(
        r'id="lastUpdated">[^<]*<',
        f'id="lastUpdated">{TODAY} 자동 업데이트<',
        html,
    )
    return html, changed

# ── 메인 ──────────────────────────────────────────────────────
def main():
    print(f"[{TODAY}] HCI 학회 정보 업데이트 시작")

    with open(HTML_FILE, encoding="utf-8") as f:
        html = f.read()

    confs = extract_conferences(html)
    print(f"  파싱된 학회 수: {len(confs)}개 (배치 크기: {BATCH_SIZE})")

    all_updates = []
    batches = [confs[i:i + BATCH_SIZE] for i in range(0, len(confs), BATCH_SIZE)]
    for idx, batch in enumerate(batches, 1):
        print(f"  배치 {idx}/{len(batches)}: {len(batch)}개 학회 검색 중...")
        updates = fetch_updates(batch)
        all_updates.extend(updates)
        print(f"    → {len(updates)}개 응답 파싱 완료")

    html_new, changed = patch_html(html, all_updates)

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html_new)

    if changed:
        print(f"  ✅ 변경된 학회 ({len(changed)}개): {', '.join(changed)}")
    else:
        print("  ✓ 변경사항 없음")
    print("완료.")

if __name__ == "__main__":
    main()
