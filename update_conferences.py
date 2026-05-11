"""
update_conferences.py  ─  비용 $0 버전
────────────────────────────────────────
hci-deadlines/conf-database GitHub 레포에서
직접 YAML을 가져와 파싱합니다. Anthropic API 완전 미사용.

데이터 출처: https://github.com/hci-deadlines/conf-database
"""

import re, json, datetime, urllib.request, urllib.error
try:
    import yaml
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyyaml", "-q"])
    import yaml

# ── 설정 ──────────────────────────────────────────────────────
HTML_FILE = "index.html"
TODAY     = datetime.date.today()
TODAY_STR = TODAY.isoformat()
BASE_URL  = "https://raw.githubusercontent.com/hci-deadlines/conf-database/main/conferences"

# 우리 id → hci-deadlines 파일명 매핑
CONF_MAP = {
    "chi":          "chi",
    "uist":         "uist",
    "cscw":         "cscw",
    "ubicomp":      "ubicomp",
    "vis":          "ieeevis",
    "ismar":        "ismar",
    "mm":           "acmmm",
    "siggraph":     "siggraph",
    "siggraph_asia":"siggraphasia",
    "eics":         "eics",
    "cui":          "cui",
    "chiplay":      "chiplay",
    "iss":          "iss",
    "icmi":         "icmi",
    "mobilehci":    "mobilehci",
    "whc":          "worldhaptics",
    "eurovis":      "eurovis",
    "ieeeVR":       "ieeevr",
    "iui":          "iui",
    "percom":       "percom",
    "soups":        "soups",
    "vrst":         "vrst",
}
# 국내 학회·SIGGRAPH Asia 등 데이터 없는 건 스킵

# ── YAML 페치 ─────────────────────────────────────────────────
def fetch_yaml(conf_slug: str) -> list | None:
    url = f"{BASE_URL}/{conf_slug}.yml"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HCI-Dashboard/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return yaml.safe_load_all(r.read().decode()) if False else yaml.safe_load(r.read().decode())
    except Exception as e:
        print(f"    fetch 실패 ({conf_slug}): {e}")
        return None

# ── 최신/다음 항목 선택 ───────────────────────────────────────
def pick_best(entries: list | dict) -> dict | None:
    """여러 연도 항목 중 가장 가까운 미래 혹은 최근 항목을 선택."""
    if isinstance(entries, dict):
        entries = [entries]
    if not entries:
        return None

    future, past = [], []
    for e in entries:
        dl = e.get("deadline") or e.get("abstract_deadline")
        if not dl:
            past.append((datetime.date.min, e))
            continue
        try:
            dl_date = datetime.date.fromisoformat(str(dl)[:10])
            if dl_date >= TODAY:
                future.append((dl_date, e))
            else:
                past.append((dl_date, e))
        except Exception:
            past.append((datetime.date.min, e))

    if future:
        return sorted(future)[0][1]   # 가장 가까운 미래 마감
    if past:
        return sorted(past, reverse=True)[0][1]  # 가장 최근 지난 항목
    return None

# ── YAML 항목 → 우리 형식 변환 ────────────────────────────────
def to_our_format(entry: dict, our_id: str) -> dict | None:
    if not entry:
        return None

    dl_raw = entry.get("deadline") or entry.get("abstract_deadline")
    dl_date = None
    dl_label = "미확정"
    if dl_raw:
        try:
            dl_date = datetime.date.fromisoformat(str(dl_raw)[:10])
            passed  = dl_date < TODAY
            dl_label = f"{dl_date.year}년 {dl_date.month}월 {dl_date.day}일" + (" (완료)" if passed else "")
            if entry.get("abstract_deadline") and entry.get("deadline"):
                abs_raw = str(entry["abstract_deadline"])[:10]
                dl_label += f" · 초록 {abs_raw}"
        except Exception:
            pass

    place = entry.get("place", "")
    date_str = entry.get("date", "")
    year  = entry.get("year", TODAY.year)

    # dateLabel 조합: "2026년 4월 13-17일 · 바르셀로나" 형태
    date_label = f"{year}년 {date_str}" if date_str else f"{year}년"
    if place:
        date_label += f" · {place}"

    # 이미 지난 conference → ✓완료 표시
    start_raw = entry.get("start")
    if start_raw:
        try:
            if datetime.date.fromisoformat(str(start_raw)[:10]) < TODAY:
                if "✓완료" not in date_label:
                    date_label += " ✓완료"
        except Exception:
            pass

    # dateMonth 추출
    start_month = None
    if start_raw:
        try:
            start_month = datetime.date.fromisoformat(str(start_raw)[:10]).month
        except Exception:
            pass
    if not start_month and date_str:
        month_names = ["january","february","march","april","may","june",
                       "july","august","september","october","november","december"]
        for i, mn in enumerate(month_names, 1):
            if mn in date_str.lower():
                start_month = i
                break

    return {
        "id":            our_id,
        "dateLabel":     date_label,
        "deadlineLabel": dl_label,
        "deadlineDate":  str(dl_date) if dl_date else None,
        "url":           entry.get("link", ""),
        "dateMonth":     start_month,
    }

# ── index.html 파싱 ───────────────────────────────────────────
def extract_conferences(html: str) -> list:
    m = re.search(r"const conferences = \[(.*?)\];\n\n// ── State", html, re.DOTALL)
    if not m:
        raise ValueError("conferences 배열을 찾을 수 없습니다")
    confs = []
    for line in m.group(1).split("\n"):
        line = line.strip()
        if not line.startswith("{id:"):
            continue
        def get(f, line=line):
            sm = re.search(rf"{f}:'([^']*)'", line)
            if sm:   return sm.group(1)
            if re.search(rf"{f}:null", line): return None
            im = re.search(rf"{f}:(\d+)", line)
            return int(im.group(1)) if im else None
        confs.append({k: get(k) for k in
                      ("id","abbr","dateLabel","deadlineLabel","deadlineDate","dateMonth","url")})
    return confs

# ── HTML 패치 ─────────────────────────────────────────────────
def patch_html(html: str, updates: list) -> tuple:
    changed = []
    for u in updates:
        cid = u.get("id")
        if not cid:
            continue
        m = re.search(rf"(\{{id:'{re.escape(cid)}'[^\n]*\}})", html)
        if not m:
            continue
        old = m.group(1)
        new = old

        def sw(line, f, v):
            if v is None:
                return re.sub(rf"{f}:'[^']*'", f"{f}:null", line)
            safe = str(v).replace("'", "\\'")
            return re.sub(rf"{f}:'[^']*'", f"{f}:'{safe}'", line)

        dirty = []
        for f in ("dateLabel", "deadlineLabel", "deadlineDate", "url"):
            nv = u.get(f)
            ov = (re.search(rf"{f}:'([^']*)'", old) or [None, None])[1] if True else None
            ov_m = re.search(rf"{f}:'([^']*)'", old)
            ov = ov_m.group(1) if ov_m else None
            if nv and nv != ov:
                new = sw(new, f, nv)
                dirty.append(f)
        if u.get("dateMonth"):
            odm = re.search(r"dateMonth:(\d+)", old)
            if odm and int(u["dateMonth"]) != int(odm.group(1)):
                new = re.sub(r"dateMonth:\d+", f"dateMonth:{int(u['dateMonth'])}", new)
                dirty.append("dateMonth")

        if new != old:
            html = html.replace(old, new, 1)
            changed.append(f"{cid}({','.join(dirty)})")

    html = re.sub(r"const TODAY = new Date\('[^']*'\);",
                  f"const TODAY = new Date('{TODAY_STR}');", html)
    html = re.sub(r'id="lastUpdated">[^<]*<',
                  f'id="lastUpdated">{TODAY_STR} 자동 업데이트<', html)
    return html, changed

# ── 메인 ──────────────────────────────────────────────────────
def main():
    print(f"[{TODAY_STR}] HCI 업데이트 시작 (API 비용 $0 — hci-deadlines 직접 파싱)")

    with open(HTML_FILE, encoding="utf-8") as f:
        html = f.read()

    confs   = extract_conferences(html)
    updates = []
    skipped = 0

    for conf in confs:
        cid  = conf["id"]
        slug = CONF_MAP.get(cid)
        if not slug:
            skipped += 1
            continue

        print(f"  {conf['abbr']:15} → {slug}.yml", end=" ... ", flush=True)
        raw = fetch_yaml(slug)
        if not raw:
            print("skip")
            continue

        entries = raw if isinstance(raw, list) else [raw]
        best    = pick_best(entries)
        result  = to_our_format(best, cid)
        if result:
            updates.append(result)
            print("ok")
        else:
            print("no data")

    print(f"\n  {len(updates)}개 업데이트, {skipped}개 스킵 (국내 학회 등)")

    html_new, changed = patch_html(html, updates)

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html_new)

    if changed:
        print(f"  ✅ 변경 ({len(changed)}개): {', '.join(changed)}")
    else:
        print("  ✓ 변경사항 없음")
    print("완료. API 비용: $0.00")

if __name__ == "__main__":
    main()
