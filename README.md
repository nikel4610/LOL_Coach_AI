# LoL Coach AI

> 리그오브레전드 플레이어 전적을 분석하고, AI 과외 선생님처럼 맞춤형 피드백을 제공하는 서비스

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![AWS](https://img.shields.io/badge/AWS-232F3E?style=flat&logo=amazon-aws&logoColor=white)](https://aws.amazon.com/)
[![HuggingFace](https://img.shields.io/badge/HuggingFace-FFD21E?style=flat&logo=huggingface&logoColor=black)](https://huggingface.co/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat)](LICENSE)

---

## Overview

소환사 닉네임을 입력하면 최근 전적을 자동 분석하고, 같은 티어 평균 데이터와 비교해 **구체적인 약점과 개선 방법**을 AI가 피드백해줍니다.

단순 전적 조회를 넘어, 실제로 실력 향상에 도움이 되는 인사이트를 제공하는 것이 목표입니다.

```
소환사 닉네임 입력
       ↓
  전적 데이터 수집 (Riot API)
       ↓
  개인 지표 분석 (KDA / CS / 시야 / 초반 라인전 등)
       ↓
  티어 평균과 비교 (패치 버전 기준 고정)
       ↓
  AI 코치 피드백 생성 (Claude API + 파인튜닝 모델)
       ↓
  시각화 리포트 제공 (Streamlit)
```

---

## Features

- **전적 분석**: KDA, CS/분, 시야점수, 킬관여율, 초반 10분 골드차·CS차, 포지션별 성과
- **티어 평균 비교**: 최신 패치 기준 티어 평균 대비 개인 지표 비교 ("실버 평균 대비 CS가 1.2 낮음" 등)
- **포지션별 맞춤 분석**: 포지션·챔피언 역할군·빌드 유형 기반 핵심 지표 차등 평가
- **AI 코치 피드백**: 약점 진단 + 구체적 개선 방법을 자연어로 제공
- **시각화 대시보드**: plotly 기반 인터랙티브 차트 (3단계)

---

## Tech Stack

| 영역 | 기술 |
|---|---|
| 언어 | Python 3.11+ |
| 데이터 수집 | Riot Games API, `httpx` (비동기), token bucket rate limiter |
| 데이터 처리 | `pandas`, `numpy` |
| 데이터베이스 | SQLite (로컬) → AWS RDS PostgreSQL (배포) |
| 원본 저장 | 로컬 파일시스템 → AWS S3 (배포) |
| 시각화 | `plotly` |
| AI 코치 (메인) | Anthropic Claude API |
| AI 코치 (파인튜닝) | Qwen3-1.7B + QLoRA (Hugging Face, Apache 2.0) |
| 파인튜닝 | Unsloth + `peft` + `bitsandbytes` + `trl` (Google Colab T4) |
| 서빙 UI | Streamlit |
| 클라우드 | AWS (S3, RDS, Lambda) |
| 컨테이너 | Docker |
| CI/CD | GitHub Actions |
| 정적 데이터 | Riot Data Dragon (챔피언/아이템 메타) |

---

## Project Structure

```
LOL_Coach_AI/
├── src/
│   ├── api/                        # Riot API 클라이언트
│   │   ├── client.py               # httpx AsyncClient 래퍼
│   │   ├── rate_limiter.py         # Token bucket rate limiter
│   │   └── endpoints.py            # API 엔드포인트 상수
│   ├── pipeline/                   # 데이터 수집 파이프라인
│   │   ├── collector.py            # 소환사/매치 수집 메인 루프
│   │   └── storage.py              # JSON 저장 + DB upsert
│   ├── analysis/                   # 개인 퍼포먼스 분석
│   │   ├── queries.py              # 개인 지표 집계 쿼리
│   │   ├── tier_stats.py           # 티어 평균 계산 + DB 저장
│   │   ├── compare.py              # 개인 vs 티어 평균 비교 + Claude payload
│   │   ├── validator.py            # 입력 검증 + 커스텀 예외
│   │   └── event_parser.py         # 타임라인 이벤트 파싱 (초반/중반/후반)
│   ├── meta/                       # 챔피언 메타 데이터
│   │   ├── champions.py            # Data Dragon 챔피언 수집 + DB 저장
│   │   ├── champion_roles.py       # 3레이어 역할군 구성 + DB 저장
│   │   └── role_lookup.py          # 역할군 조회 + 평가 컨텍스트 결정
│   ├── visualization/              # plotly 차트 생성 (3단계)
│   └── coach/                      # AI 코치 연동 (3단계)
├── training/                       # Qwen3-1.7B 파인튜닝 (4단계)
├── data/
│   ├── raw/                        # 수집 원본 JSON (gitignore)
│   ├── champion_overrides.json     # 수동 역할군 오버라이드
│   └── lol_coach.db                # SQLite DB (gitignore)
├── test_compare.py                 # compare.py 동작 확인 스크립트
├── test_analysis.py                # 분석 쿼리 테스트
├── test_client.py                  # Riot API 연결 테스트
├── test_roles.py                   # 역할군 조회 테스트
├── test_validator.py               # 입력 검증 테스트
├── check_db.py                     # DB 수집 현황 확인
├── check_events.py                 # 타임라인 이벤트 파싱 확인
├── average_per_tier.py             # 티어별 리포트 CSV 생성
├── update_names.py                 # 소환사 닉네임 업데이트
├── .env.example
├── requirements.txt
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Riot Games API Key ([developer.riotgames.com](https://developer.riotgames.com/))
- Anthropic API Key ([console.anthropic.com](https://console.anthropic.com/))
- conda 권장 (pandas/numpy pip 빌드 오류 방지)

### Installation

```bash
git clone https://github.com/nikel4610/LOL_Coach_AI.git
cd LOL_Coach_AI

# conda 환경 (권장)
conda create -n lol python=3.11
conda activate lol
conda install pandas numpy

pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
```

`.env` 파일에 아래 값을 입력합니다:

```env
RIOT_API_KEY=your_riot_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
DB_PATH=data/lol_coach.db
TARGET_REGION=kr
TARGET_SERVER=asia
```

### Run

```bash
# DB 초기화
python -m src.db.init_db

# 데이터 수집 (티어별 플레이어 + 매치 히스토리)
python -m src.pipeline.collector --players 15 --matches 10

# 티어 평균 집계
python -m src.analysis.tier_stats

# 챔피언 메타 데이터 수집
python -m src.meta.champions
python -m src.meta.champion_roles

# 분석 테스트
python test_compare.py
python test_compare.py --name "닉네임"

# DB 현황 확인
python check_db.py
```

---

## Development Roadmap

- [x] 프로젝트 설계 및 아키텍처 확정
- [x] **1단계** — 데이터 수집 인프라
  - Riot API 클라이언트 (httpx + asyncio)
  - Token bucket rate limiter
  - SQLite 스키마 설계 및 수집 파이프라인
  - 아이언~챌린저 전 티어 수집 (163명 / 1,656게임)
- [x] **2단계** — 개인 퍼포먼스 분석 + SQL 집계
  - KDA/CS/시야/킬관여율 분석 (`queries.py`)
  - 티어 평균 비교 쿼리 (`tier_stats.py`, `compare.py`)
  - Match Timeline 파싱 — 10분 골드차/CS차 (`event_parser.py`)
  - 챔피언 역할군 3레이어 시스템 (`champion_roles.py`, `role_lookup.py`)
  - 포지션별 핵심 지표 프로필 + Claude payload 구조화
- [ ] **3단계** — AI 코치 + 시각화 + Streamlit MVP
  - Claude API 연동 및 포지션/역할군별 프롬프트 설계
  - plotly 인터랙티브 차트
  - Streamlit 대시보드 UI (닉네임 검색 → 리포트)
- [ ] **4단계** — ML 모델 (Qwen3-1.7B QLoRA 파인튜닝)
  - 코치 피드백 데이터셋 구성 (self-instruct)
  - Google Colab + Unsloth QLoRA 학습
  - Hugging Face Hub 업로드
- [ ] **5단계** — 클라우드 배포 + CI/CD
  - AWS S3 / RDS PostgreSQL / Lambda
  - Docker + GitHub Actions
  - Streamlit Community Cloud 배포

---

## Database Schema

```sql
CREATE TABLE summoners (
    puuid           TEXT PRIMARY KEY,
    game_name       TEXT NOT NULL,
    tag_line        TEXT NOT NULL,
    summoner_level  INTEGER,
    profile_icon_id INTEGER,
    tier            TEXT,
    rank            TEXT,
    lp              INTEGER,
    wins            INTEGER,
    losses          INTEGER,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE matches (
    match_id        TEXT PRIMARY KEY,
    game_duration   INTEGER,
    game_version    TEXT,
    queue_id        INTEGER,
    game_start_ts   INTEGER,
    collected_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE match_participants (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id        TEXT REFERENCES matches(match_id),
    puuid           TEXT REFERENCES summoners(puuid),
    champion_id     INTEGER,
    champion_name   TEXT,
    position        TEXT,
    win             INTEGER,
    kills           INTEGER,
    deaths          INTEGER,
    assists         INTEGER,
    cs_total        INTEGER,
    cs_per_min      REAL,
    gold_earned     INTEGER,
    vision_score    INTEGER,
    wards_placed    INTEGER,
    wards_killed    INTEGER,
    kp_percent      REAL,
    dmg_dealt       INTEGER,
    dmg_taken       INTEGER,
    UNIQUE(match_id, puuid)
);

CREATE TABLE timeline_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id        TEXT REFERENCES matches(match_id),
    puuid           TEXT NOT NULL,
    minute          INTEGER NOT NULL,
    gold            INTEGER,
    cs              INTEGER,
    xp              INTEGER,
    gold_diff       INTEGER,
    cs_diff         INTEGER,
    UNIQUE(match_id, puuid, minute)
);

CREATE TABLE tier_averages (
    tier            TEXT NOT NULL,
    position        TEXT NOT NULL,
    metric          TEXT NOT NULL,
    avg_value       REAL,
    sample_count    INTEGER,
    patch_version   TEXT NOT NULL,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tier, position, metric, patch_version)
);

CREATE TABLE champion_info (
    champion_id     TEXT PRIMARY KEY,
    champion_name   TEXT NOT NULL,
    primary_tag     TEXT,
    secondary_tag   TEXT,
    patch_version   TEXT NOT NULL,
    ...
);

CREATE TABLE champion_roles (
    champion_id     TEXT PRIMARY KEY,
    final_role      TEXT,       -- override > riot_primary 우선순위
    main_position   TEXT,
    role_override   TEXT,
    patch_version   TEXT
);

CREATE TABLE champion_position_stats (
    champion_id     TEXT NOT NULL,
    position        TEXT NOT NULL,
    games           INTEGER,
    win_rate        REAL,
    pick_rate       REAL,
    patch_version   TEXT NOT NULL,
    PRIMARY KEY (champion_id, position, patch_version)
);
```

---

## Key Design Decisions

**패치 버전 고정**: `tier_averages` 비교 시 항상 최신 패치(`tier_averages.updated_at` 기준) 사용. 유저 매치의 `game_version`과 무관하게 고정.

**포지션별 핵심 지표 차등**: JUNGLE은 `cs_diff_10`/`gold_diff_10` 제외, UTILITY는 CS/딜량 제외 등 포지션별로 의미있는 지표만 약점/강점 판정에 사용.

**부호 혼재 지표 처리**: `gold_diff_10`, `cs_diff_10`은 평균이 0에 가깝거나 부호가 달라 `diff_pct`가 수백%로 과장될 수 있어 절댓값 diff로 대체 표시.

**챔피언 역할군 3레이어**: Riot 공식 태그 → 실제 데이터 포지션 집계 → 수동 오버라이드 순으로 최종 역할군 결정.

---

## Architecture

```
[Riot Games API]  [Data Dragon]
       ↓                ↓
   httpx AsyncClient + Token Bucket Rate Limiter
       ↓
   SQLite (로컬) / AWS RDS PostgreSQL (배포)
       ↓
   queries.py + tier_stats.py + compare.py
       ↓
   ┌─────────────────────────────┐
   │  Claude API (메인 코치)      │
   │  Qwen3-1.7B QLoRA (보조)    │
   └─────────────────────────────┘
       ↓
   plotly 시각화 + Streamlit UI
```

---

## Fine-tuning (Qwen3-1.7B)

- **베이스 모델**: [Qwen/Qwen3-1.7B](https://huggingface.co/Qwen/Qwen3-1.7B) (Apache 2.0)
- **방법**: QLoRA (4-bit quantization + LoRA)
- **학습 환경**: Google Colab T4 GPU (무료)
- **라이브러리**: Unsloth + peft + bitsandbytes + trl
- **데이터셋**: 수집 매치 데이터 + Claude API self-instruct 레이블링

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

## Acknowledgements

- [Riot Games API](https://developer.riotgames.com/) — 게임 데이터 제공
- [Qwen3](https://huggingface.co/Qwen/Qwen3-1.7B) — 파인튜닝 베이스 모델
- [Unsloth](https://github.com/unslothai/unsloth) — 효율적인 LLM 파인튜닝
- [Anthropic Claude](https://www.anthropic.com/) — AI 코치 메인 엔진