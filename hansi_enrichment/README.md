# 문집총간 한시 데이터 고도화 (hansi_enrichment)

`../frontier_classification/` 자매 프로젝트. 16세기 문집 20종 한시 XML을
골드(임백호집 3차완본) 수준으로 고도화하는 3단계 파이프라인.
(git 반입 시 `gitignore_rename_to_dotfile.txt` → `.gitignore` 로 이름 변경)

## 단계

| 단계 | 스크립트 | 입력 → 출력 | 검증 (임백호집 골드) |
|---|---|---|---|
| 1 코퍼스 재통합 | `scripts_1_merge/run.py` | Drive "4-1. 생성 데이터" → `00_corpus/` 19문집 18,235수 | 임백호집 == 3차완본, 정합성 OK |
| 2 기계적 고도화 | `scripts_2_enrich/run.py` | `00_corpus/` → `01_enriched/` (자수·형식·운자·대장·스키마) | Basetype 98.9% / rhyme recall 0.998 |
| 3 Themes 26분류 | `scripts_3_themes/30_suggest.py` | `01_enriched/` → `02_suggested/` + 확신도 TSV | 확신도 캘리브(5-fold), ≥70구간 정밀도 82~94% |

- **3단계 결과**: `02_suggested/*.xml` 18문집. 확신도 ≥ 40이면 `<Themes>`에 주분류 1개 제안(13,821수).
  작업자는 `reports/3_conf_<문집>.tsv`(제안·확신도·구간정밀도)를 확신도 내림차순으로 검토.
- **term/d 재분절·전고(Allusion)**: 규칙·시소러스 자동화 불가로 확인 → 검수 영역 (`docs/…3단계… §8·9`).

## 실행

- Python 3.11 표준 라이브러리 + `striprtf`(1단계), `gdown`(1단계 다운로드).
- 입력(저장소 미포함): `한어대사전.txt` `평수운_수정.txt` `임백호집_3차완본_20260730.txt` `대상데이터_데이터클리닝/` Drive zip.
- `assets/hdc_headwords.txt`는 `scripts_2_enrich/10_assets.py`로 생성.
- 각 `scripts_*/run.py`는 이 폴더(프로젝트 루트)에서 실행. `01_enriched/`는 재생성 대상.

## 문서

`docs/2026-08-28-한시데이터-{1,2,3}단계-*.md` — 설계·검증·결과. 3단계는 §8~11.
