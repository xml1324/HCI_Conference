"""
update_conferences.py
─────────────────────
GitHub Actions에서 매일 실행되어 index.html 안의 학회 정보를
Anthropic API + 웹 검색으로 검증·갱신합니다.
"""

import os, re, json, datetime
import anthropic

# ── 설정 ──────────────────────────────────────────────────────
HTML_FILE   = "index.html"
TODAY       = datetime.date.today().isoformat()
client      = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM = f"""You are an HCI conference database updater. Today is {TODAY}.
For each conference given, search the web and return ONLY a valid JSON array — no markdown, no explanation.
Each element must have these exact keys:
  id, dateLabel, deadlineLabel, deadlineDate (YYYY-MM-DD or null), url, dateMonth (integer 1-12)
Rules:
- Keep original value for anything you could not verify with certainty.
- deadlineDate must be the paper submission deadline in YYYY-MM-DD format, or null.
- dateMonth must be the integer month the conference is held.
- If a conference already took place, keep its data but add ' ✓완료' at the end of dateLabel if not already present.
- For rolling deadlines (IMWUT, PACMHCI), set deadlineDate to the next upcoming round.
- URLs must be the official conference website, updated to the current year where applicable.
"""

# ── 파싱: index.html에서 conferences 배열 추출 ─────────────────
def extract_conferences(html: str) -> list[dict]:
    """JS conferences 배열에서 각 항목을 파싱합니다."""
    # 배열 전체 추출
    m = re.search(r'const conferences = \[(.*?)\];\n\n// ── State', html, re.DOTALL)
    if not m:
        raise ValueError("conferences 배열을 찾을 수 없습니다")

    block = m.group(1)
    confs = []
    # 각 {…} 블록 추출 (한 줄 형식)
    for line in block.split('\n'):
        line = line.strip()
        if not line.startswith('{id:'):
            continue
        # 필드 추출
        def get(field, default=None):
            # 문자열 값
            sm = re.search(rf"{field}:'([^']*)'", line)
            if sm:
                return sm.group(1)
            # null
            nm = re.search(rf"{field}:null", line)
            if nm:
                return None
            # 숫자
            im = re.search(rf"{field}:(\d+)", line)
            if im:
                return int(im.group(1))
            return default

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

# ── API 호출: 배치로 나눠 처리 ────────────────────────────────
def fetch_updates(batch: list[dict]) -> list[dict]:
    conf_list = "\n".join(
        f'id:{c["id"]} abbr:"{c["abbr"]}" name:"{c["name"]}" '
        f'currentDate:"{c["dateLabel"]}" currentDeadline:"{c["deadlineLabel"]}" '
        f'currentDeadlineDate:"{c["deadlineDate"] or ""}" url:"{c["url"]}"'
        for c in batch
    )
    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4096,
        system=SYSTEM,
        messages=[{"role": "user", "content": f"Verify and update:\n{conf_list}"}],
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
    )
    # 텍스트 블록만 추출
    text = "".join(b.text for b in message.content if hasattr(b, "text"))
    text = text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print(f"  ⚠ JSON 파싱 실패 (배치 {len(batch)}개):\n{text[:300]}")
        return []

# ── index.html 패치 ────────────────────────────────────────────
def patch_html(html: str, updates: list[dict]) -> tuple[str, list[str]]:
    changed = []
    for u in updates:
        cid = u.get("id")
        if not cid:
            continue

        # id로 해당 줄 찾기
        pattern = rf"(\{{id:'{re.escape(cid)}'.*?\}})"
        m = re.search(pattern, html)
        if not m:
            continue
        old_line = m.group(1)

        def replace_field(line, field, new_val):
            if new_val is None:
                return re.sub(rf"{field}:'[^']*'", f"{field}:null", line)
            return re.sub(rf"{field}:'[^']*'", f"{field}:'{new_val}'", line)

        def replace_int_field(line, field, new_val):
            if new_val is None:
                return line
            return re.sub(rf"{field}:\d+", f"{field}:{int(new_val)}", line)

        new_line = old_line
        fields_changed = []

        for field in ("dateLabel", "deadlineLabel", "deadlineDate", "url"):
            new_val = u.get(field)
            old_val_m = re.search(rf"{field}:'([^']*)'", old_line)
            old_val = old_val_m.group(1) if old_val_m else None
            if new_val and new_val != old_val:
                new_line = replace_field(new_line, field, new_val)
                fields_changed.append(field)

        if "dateMonth" in u and u["dateMonth"]:
            old_dm_m = re.search(r"dateMonth:(\d+)", old_line)
            old_dm = int(old_dm_m.group(1)) if old_dm_m else None
            if int(u["dateMonth"]) != old_dm:
                new_line = replace_int_field(new_line, "dateMonth", u["dateMonth"])
                fields_changed.append("dateMonth")

        if new_line != old_line:
            html = html.replace(old_line, new_line)
            changed.append(f"{cid} ({', '.join(fields_changed)})")

    # TODAY 상수 및 lastUpdated 태그 업데이트
    html = re.sub(
        r"const TODAY = new Date\('[^']*'\);",
        f"const TODAY = new Date('{TODAY}');",
        html
    )
    html = re.sub(
        r'id="lastUpdated">[^<]*<',
        f'id="lastUpdated">{TODAY} 자동 업데이트<',
        html
    )
    return html, changed

# ── 메인 ──────────────────────────────────────────────────────
def main():
    print(f"[{TODAY}] HCI 학회 정보 업데이트 시작")

    with open(HTML_FILE, encoding="utf-8") as f:
        html = f.read()

    confs = extract_conferences(html)
    print(f"  파싱된 학회 수: {len(confs)}개")

    # 2개 배치로 나눠 API 호출
    batch_size = len(confs) // 2 + 1
    all_updates = []
    for i in range(0, len(confs), batch_size):
        batch = confs[i:i+batch_size]
        print(f"  배치 {i//batch_size + 1}: {len(batch)}개 학회 검색 중...")
        updates = fetch_updates(batch)
        all_updates.extend(updates)
        print(f"    → {len(updates)}개 응답 수신")

    html_new, changed = patch_html(html, all_updates)

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html_new)

    if changed:
        print(f"  ✅ 변경된 학회: {', '.join(changed)}")
    else:
        print("  ✓ 변경사항 없음")
    print("완료.")

if __name__ == "__main__":
    main()
