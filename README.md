# 🌐 HCI 학술대회 일정 대시보드

국내외 HCI(Human-Computer Interaction) 및 관련 분야 학술대회 일정을 한눈에 확인할 수 있는 정적 웹 대시보드입니다.  
GitHub Pages로 배포되며, GitHub Actions를 통해 **매일 자정 자동으로 최신 정보로 갱신**됩니다.

**→ [대시보드 바로가기](https://xml1324.github.io/HCI_Conference)**

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| 📋 **학회 목록** | 국외 22개 · 국내 6개, 총 28개 학회 정보 |
| 🗺️ **세계지도 시각화** | D3.js 기반 지도에 개최지 도트 표시, 호버 시 상세 정보 |
| 🏳️ **국기 & 파비콘** | 개최국 국기 이미지 및 학회 공식 사이트 파비콘 자동 로딩 |
| 🔍 **검색 & 필터** | 약자/이름 검색, 국내외·등급·결합저널별 필터, 마감순/개최순 정렬 |
| ⏱️ **D-Day 카운트다운** | 논문 마감일까지 남은 일수 실시간 표시 |
| 🤖 **매일 자동 업데이트** | GitHub Actions + Anthropic API 웹 검색으로 학회 정보 자동 갱신 |
| ✨ **AI 질문** | 특정 학회의 최신 정보를 자연어로 직접 질문 |
| 🐙 **피드백** | GitHub Issues로 버그 제보 및 개선 제안 |

---

## 수록 학회

### 국외 (22개)

| 약자 | 학회명 | 등급 | 결합 저널 |
|------|--------|------|-----------|
| CHI | ACM Conference on Human Factors in Computing Systems | 최우수 | — |
| UIST | ACM Symposium on User Interface Software and Technology | 최우수 | — |
| IEEE VIS | IEEE Visualization and Visual Analytics | 최우수 | TVCG |
| IEEE VR | IEEE VR and 3D User Interfaces | 최우수 | TVCG |
| IEEE ISMAR | IEEE International Symposium on Mixed and Augmented Reality | 최우수 | TVCG |
| SIGGRAPH | ACM SIGGRAPH | 최우수 | — |
| SIGGRAPH Asia | ACM SIGGRAPH Asia | 최우수 | — |
| UbiComp | ACM UbiComp / ISWC | 최우수 | IMWUT |
| CSCW | ACM Conference on Computer-Supported Cooperative Work | 우수 | PACMHCI |
| ACM MM | ACM International Conference on Multimedia | 우수 | — |
| IEEE PerCom | IEEE International Conference on Pervasive Computing | 우수 | — |
| IUI | ACM Conference on Intelligent User Interfaces | 우수 | — |
| VRST | ACM Symposium on Virtual Reality Software and Technology | 우수 | — |
| World Haptics | IEEE World Haptics Conference | 우수 | — |
| EuroVis | Eurographics Conference on Visualization | 우수 | CGF |
| EICS | ACM SIGCHI Symposium on Engineering Interactive Computing Systems | — | PACMHCI |
| CUI | ACM Conference on Conversational User Interfaces | — | PACMHCI |
| CHI PLAY | ACM Annual Symposium on Computer-Human Interaction in Play | — | PACMHCI |
| ISS | ACM Interactive Surfaces and Spaces | — | PACMHCI |
| ICMI | ACM International Conference on Multimodal Interaction | — | — |
| MobileHCI | ACM International Conference on Mobile HCI | — | — |
| SOUPS | USENIX Symposium On Usable Privacy and Security | — | — |

> **등급**: 한국정보과학회 등재 기준 · **IF**: BK21 우수학회 대체인정 Impact Factor

### 국내 (6개)

| 약자 | 학회명 |
|------|--------|
| ESK (춘) | 대한인간공학회 춘계학술대회 |
| ESK (추) | 대한인간공학회 추계학술대회 |
| KCC | 한국정보과학회 한국컴퓨터종합학술대회 |
| KSC | 한국정보과학회 동계학술발표논문집 |
| HCI Korea | 한국HCI학회 학술대회 |
| Haptics KR | 한국햅틱스학회 학술대회 |

---

## 설치 및 배포

### 1. 레포지토리 설정

```bash
git clone https://github.com/xml1324/HCI_Conference.git
cd HCI_Conference
```

### 2. GitHub Pages 활성화

**Settings → Pages → Source**: `main` 브랜치 / `/ (root)` 선택 후 Save

### 3. Anthropic API Key 등록 (자동 업데이트용)

**Settings → Secrets and variables → Actions → New repository secret**

| Name | Value |
|------|-------|
| `ANTHROPIC_API_KEY` | `sk-ant-...` |

> API 키 발급: [console.anthropic.com](https://console.anthropic.com/settings/keys)

### 4. (선택) AI 질문 기능 활성화

사이트 우측 상단 **⚙ 버튼** → API Key 입력 → 저장  
브라우저 `localStorage`에만 저장되며 외부로 전송되지 않습니다.

---

## 자동 업데이트 구조

```
매일 00:00 KST (UTC 15:00)
        │
        ▼
GitHub Actions (.github/workflows/daily-update.yml)
        │
        ▼
update_conferences.py
  ├── index.html에서 28개 학회 데이터 파싱
  ├── Anthropic API + 웹 검색으로 2배치 검증
  └── 변경된 필드만 index.html에 패치
        │
        ▼
변경사항 있음? ─── Yes ──→ git commit & push
        │                   "🤖 학회 정보 자동 업데이트 (YYYY-MM-DD)"
        └─── No ───→ 스킵
```

Actions 탭에서 **Run workflow** 버튼으로 수동 실행도 가능합니다.

---

## 파일 구조

```
HCI_Conference/
├── index.html                        # 메인 대시보드 (단일 파일 앱)
├── update_conferences.py             # 자동 업데이트 Python 스크립트
├── .github/
│   └── workflows/
│       └── daily-update.yml         # GitHub Actions 워크플로우
└── README.md
```

---

## 피드백 및 기여

학회 정보 오류, 추가 요청, 버그 제보는 우하단 **✉ 피드백 보내기** 버튼 또는 [Issues](https://github.com/xml1324/HCI_Conference/issues)를 이용해 주세요.

---

## 라이선스

MIT License

---

*데이터 출처: 각 학회 공식 웹사이트 · [hci-deadlines.github.io](https://hci-deadlines.github.io) · ACM Digital Library · IEEE Xplore*
