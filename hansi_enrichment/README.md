# 문집총간 한시 데이터 고도화 (hansi_enrichment)

`../frontier_classification/` 자매 프로젝트. 16세기 문집 20종 한시 XML 데이터를
골드(임백호집 3차완본) 수준으로 고도화하는 3단계 파이프라인.

## 단계별 산출

| 단계 | 스크립트 | 입력 → 출력 | 검증 |
|---|---|---|---|
| 1 코퍼스 재통합 | `scripts_1_merge/run.py` | Drive "4-1. 생성 데이터" → `00_corpus/*.xml` (19문집 18,235수) | 임백호집 == 3차완본 골드 |
| 2 기계적 고도화 | `scripts_2_enrich/run.py` | `00_corpus/` → `01_enriched/*.xml` (자수·형식·운자·대장·스키마) | Basetype 98.9% · rhyme recall 0.998 |
| 3 Themes 분류 | `scripts_3_themes/{10_thesaurus,20_apply}.py` | `01_enriched/` → `02_pilot/*.xml` (auto 4,575수 자동채움) | 임백호집 5-fold 정밀도 0.923 |

term/d 재분절·전고(Allusion)는 자동화 불가로 확인 → 검수 영역 (`docs/…3단계…` §8·9).

## 설계 문서

`docs/2026-08-28-한시데이터-{1,2,3}단계-*.md`

## 실행 환경

- Python 3.11 표준 라이브러리 + `striprtf`(1단계 rtf), `gdown`(1단계 다운로드 — 레이트리밋 시 수동 zip).
- 입력(저장소 미포함, 별도 확보): `한어대사전.txt`, `평수운_수정.txt`, `임백호집_3차완본_20260730.txt`,
  `대상데이터_데이터클리닝/`, Drive zip.
- `assets/rhyme_map.tsv`·`tongun.tsv`는 산출물 동봉. `hdc_headwords.txt`는 `scripts_2_enrich/10_assets.py`로 생성.
- 각 `scripts_*/run.py`는 프로젝트 루트(이 폴더)에서 실행.

## 리포트

`reports/` — 병합 내역(`00_merge.md`)·XML lint·검증·term 감사·Themes 문집별 내역.
