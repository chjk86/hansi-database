# 문집총간 한시 데이터 고도화 (hansi_enrichment)

`../frontier_classification/` 자매 프로젝트. 16세기 문집 20종 한시 XML을
골드(임백호집 3차완본)에 준하는 수준으로 고도화하는 3단계 파이프라인.

> git 반입 시 `gitignore_rename_to_dotfile.txt` → `.gitignore` 로 이름 변경.

## 단계

| 단계 | 스크립트 | 입력 → 출력 | 검증 (임백호집 골드) |
|---|---|---|---|
| 1 코퍼스 재통합 | `scripts_1_merge/run.py` | Drive "4-1. 생성 데이터" 작업자 결과 → `00_corpus/` 19문집 18,235수 | 임백호집 == 3차완본, 정합성 OK |
| 2 기계적 고도화 | `scripts_2_enrich/run.py` | `00_corpus/` → `01_enriched/` (자수·형식·운자·대장·Themes스키마) | Basetype 98.9% / rhyme recall 0.998 |
| 3 Themes + term/d | `scripts_3_themes/{30_suggest,40_termd}.py` | `01_enriched/` → `02_suggested/` | 아래 |

### 3단계 상세

- **Themes 26분류** (`30_suggest.py` + `lib/hansi/{themonto,themconf}.py`): 골드 evidence 시소러스 →
  거의 전 시에 주분류 제안 + 확신도(0~100). 확신도는 임백호집 5-fold 캘리브
  (≥70 정밀도 82~94%, 50~69 38~52%, <50 14~27%). conf ≥ 40이면 `<Themes>` 채움.
  **분류율 89%** (제안채움 13,821 + 작업자기입 1,708 / 17,512).
  작업자용: `reports/3_conf_<문집>.tsv` (제안·확신도·구간정밀도) 를 확신도 내림차순 검토.
- **term/d 재태깅** (`40_termd.py` + `lib/hansi/termdtag.py` + `assets/d_lexicon.txt`):
  대상데이터 4문집(기재집·동명집·동악집·현주집)은 사전 bigram 무차별 자동태깅 상태 →
  사전 bigram→`<term>`, d-어휘(수작업 문집 시어 중 사전 미등재)→`<d>`, 부정어구 정리.
  임백호집 골드 대비 토큰 **F1 0.83**, term/d 규칙 100% 준수. **Drive 15문집(수작업)은 미적용.**
- **전고(Allusion)**: 유명 전고만 탐지 가능, 자동 확정 불가 → 검수 영역 (`docs/…3단계… §8`).

## 실행

- Python 3.11 표준 라이브러리 + `striprtf`(1단계 rtf), `gdown`(1단계 다운로드).
- 입력(저장소 미포함, 별도 확보): `한어대사전.txt` `평수운_수정.txt`
  `임백호집_3차완본_20260730.txt` `대상데이터_데이터클리닝/` Drive zip.
- `assets/hdc_headwords.txt` 는 `scripts_2_enrich/10_assets.py` 로 생성.
- 각 `scripts_*/run.py` 는 이 폴더(프로젝트 루트)에서 실행. `01_enriched/` 는 재생성 대상.

## 문서 · 리포트

- `docs/2026-08-28-한시데이터-{1,2,3}단계-*.md` — 설계·검증·결과 (3단계는 §8~12).
- `reports/` — 병합·XML lint·검증·term 감사·Themes 확신도(TSV)·term/d 재태깅.
