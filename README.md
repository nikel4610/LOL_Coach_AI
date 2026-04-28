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
  티어 평균과 비교
       ↓
  AI 코치 피드백 생성 (Claude API + 파인튜닝 모델)
       ↓
  시각화 리포트 제공 (Streamlit)
```

---

## Features

- **전적 분석**: KDA, CS/분, 시야점수, 킬관여율, 초반 10분 골드차·CS차, 포지션별 성과, 사망 패턴 히트맵
- **티어 평균 비교**: 같은 티어 플레이어 기준선 대비 개인 지표 비교 ("실버 평균 대비 CS가 1.2 낮음" 등)
- **AI 코치 피드백**: 약점 진단 + 구체적 개선 방법을 자연어로 제공
- **챔피언 추천**: 현재 메타 + 개인 숙련도 기반 챔피언/빌드 추천
- **시각화 대시보드**: plotly 기반 인터랙티브 차트

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
lol-coach-ai/
├── src/
│   ├── api/                  # Riot API 클라이언트
│   │   ├── client.py         # httpx AsyncClient 래퍼
│   │   ├── rate_limiter.py   # Token bucket rate limiter
│   │   └── endpoints.py      # API 엔드포인트 상수
│   ├── pipeline/             # 데이터 수집 파이프라인
│   │   ├── collector.py      # 소환사/매치 수집 메인 루프
│   │   └── storage.py        # JSON 저장 + DB upsert
│   ├── analysis/             # 개인 퍼포먼스 분석
│   │   ├── performance.py
│   │   └── timeline.py       # Match Timeline 파싱
│   ├── meta/                 # 메타/상성 분석
│   │   └── champion.py
│   ├── visualization/        # plotly 차트 생성
│   │   └── charts.py
│   ├── coach/                # AI 코치 연동
│   │   ├── claude_coach.py   # Claude API 호출
│   │   └── qwen_coach.py     # 파인튜닝 모델 추론
│   └── db/                   # DB 스키마 + 쿼리
│       ├── schema.sql
│       └── queries.py
├── training/                 # Qwen3-1.7B 파인튜닝
│   ├── prepare_dataset.py
│   ├── finetune.ipynb        # Google Colab 노트북
│   └── dataset/
├── data/
│   ├── raw/                  # 수집 원본 JSON
│   ├── processed/            # 가공 데이터
│   └── cache/                # API 응답 캐시
├── tests/
├── .env.example
├── requirements.txt
├── Dockerfile
└── app.py                    # Streamlit 엔트리포인트
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Riot Games API Key ([developer.riotgames.com](https://developer.riotgames.com/))
- Anthropic API Key ([console.anthropic.com](https://console.anthropic.com/))

### Installation

```bash
git clone https://github.com/nikel4610/LOL_Coach_AI.git
cd LOL_Coach_AI

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

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
# 데이터 수집 (티어별 플레이어 + 매치 히스토리)
python -m src.pipeline.collector

# Streamlit 앱 실행
streamlit run app.py
```

---

## Development Roadmap

- [x] 프로젝트 설계 및 아키텍처 확정
- [ ] **1단계** — 데이터 수집 인프라
  - Riot API 클라이언트 (httpx + asyncio)
  - Token bucket rate limiter
  - SQLite 스키마 설계 및 수집 파이프라인
- [ ] **2단계** — 개인 퍼포먼스 분석 + SQL 집계
  - KDA/CS/시야/킬관여율 분석
  - 티어 평균 비교 쿼리
  - Match Timeline 파싱 (10분 골드차/CS차)
- [ ] **3단계** — AI 코치 + 시각화 + Streamlit MVP
  - Claude API 연동 및 프롬프트 엔지니어링
  - plotly 인터랙티브 차트
  - Streamlit 대시보드 UI
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
-- 소환사 정보
CREATE TABLE summoners (
    puuid          TEXT PRIMARY KEY,
    summoner_id    TEXT UNIQUE NOT NULL,
    game_name      TEXT NOT NULL,
    tag_line       TEXT NOT NULL,
    tier           TEXT,
    rank           TEXT,
    lp             INTEGER,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 매치 기본 정보
CREATE TABLE matches (
    match_id       TEXT PRIMARY KEY,
    game_duration  INTEGER,
    game_version   TEXT,
    queue_id       INTEGER,
    game_start_ts  BIGINT
);

-- 매치 참가자 성과
CREATE TABLE match_participants (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id       TEXT REFERENCES matches(match_id),
    puuid          TEXT REFERENCES summoners(puuid),
    champion_id    INTEGER,
    position       TEXT,
    win            BOOLEAN,
    kills          INTEGER,
    deaths         INTEGER,
    assists        INTEGER,
    cs_total       INTEGER,
    cs_per_min     REAL,
    gold_earned    INTEGER,
    vision_score   INTEGER,
    kp_percent     REAL,
    dmg_dealt      INTEGER,
    dmg_taken      INTEGER
);

-- 분당 타임라인 스냅샷
CREATE TABLE timeline_snapshots (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id       TEXT REFERENCES matches(match_id),
    puuid          TEXT,
    minute         INTEGER,
    gold           INTEGER,
    cs             INTEGER,
    xp             INTEGER,
    gold_diff      INTEGER,
    cs_diff        INTEGER
);

-- 티어 평균 집계 캐시
CREATE TABLE tier_averages (
    tier           TEXT,
    position       TEXT,
    metric         TEXT,
    avg_value      REAL,
    sample_count   INTEGER,
    patch_version  TEXT,
    updated_at     TIMESTAMP,
    PRIMARY KEY (tier, position, metric, patch_version)
);
```

---

## Architecture

```
[Riot Games API]  [Data Dragon]
       ↓                ↓
   httpx AsyncClient + Token Bucket Rate Limiter
       ↓
   SQLite (로컬) / AWS RDS PostgreSQL (배포)
   AWS S3 (원본 JSON)
       ↓
   pandas 전처리 + SQL 집계
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

롤 특화 코치 피드백 생성을 위해 Qwen3-1.7B 모델을 QLoRA로 파인튜닝합니다.

- **베이스 모델**: [Qwen/Qwen3-1.7B](https://huggingface.co/Qwen/Qwen3-1.7B) (Apache 2.0)
- **방법**: QLoRA (4-bit quantization + LoRA)
- **학습 환경**: Google Colab T4 GPU (무료)
- **라이브러리**: Unsloth + peft + bitsandbytes + trl
- **데이터셋**: 수집 매치 데이터 + Claude API self-instruct 레이블링

학습 노트북: [`training/finetune.ipynb`](training/finetune.ipynb)

---

## API Reference

주요 Riot API 엔드포인트:

| API | 용도 |
|-----|------|
| `GET /lol/summoner/v4/summoners/by-name/{name}` | 소환사 정보 조회 |
| `GET /lol/match/v5/matches/by-puuid/{puuid}/ids` | 매치 ID 목록 |
| `GET /lol/match/v5/matches/{matchId}` | 매치 상세 |
| `GET /lol/match/v5/matches/{matchId}/timeline` | 분당 타임라인 |
| `GET /lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}` | 챔피언 숙련도 |
| `GET /lol/league/v4/entries/RANKED_SOLO_5x5/{tier}/{division}` | 티어별 플레이어 목록 |

Rate Limit (Development Key): 20 req/1s, 100 req/2min

---

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

## Acknowledgements

- [Riot Games API](https://developer.riotgames.com/) — 게임 데이터 제공
- [Qwen3](https://huggingface.co/Qwen/Qwen3-1.7B) — 파인튜닝 베이스 모델
- [Unsloth](https://github.com/unslothai/unsloth) — 효율적인 LLM 파인튜닝
- [Anthropic Claude](https://www.anthropic.com/) — AI 코치 메인 엔진