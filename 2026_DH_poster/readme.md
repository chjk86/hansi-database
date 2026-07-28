# 조선 시대 한시 주제 자동 분류를 위한 기계학습 방법론 대조 및 인문학적 주석의 효용성 검증
**2026 한국디지털인문학협회(KADH) 연차학술대회 포스터 발표 자료 및 실험 코드**

본 저장소는 조선 시대 방대한 문집 코퍼스 내에서 특정 주제의 한시(본 연구에서는 '변새시(邊塞詩)')를 자동으로 추출하고 분류하기 위해, 사전학습 언어모델(GuwenBERT)과 범용 대형언어모델(LLM, Gemini)의 분류 성능을 대조한 실험 파이프라인을 제공합니다. 

특히 단순 텍스트 추론을 넘어, 인간 연구자의 정밀한 인문학적 마크업(핵심 시어, 전고, 판별 근거)이 기계학습 모델의 오탐 방어력(Precision)에 미치는 효용성을 교차 검증합니다.

## 📂 Repository Structure (저장소 구조)

```text
2026_DH_poster/
│
├── data/                                 # 데이터셋 폴더
│   ├── 변새시_2차정리본.txt              # 전공자의 정밀 마크업(XML 태그)이 포함된 정답지(Gold Standard)
│   └── 00_final_integrated_evaluation_인간평가통합본.csv # 전문가 사후 평가 및 교차 검증 스냅샷 자료
│
├── scripts/                              # 실험 파이프라인 코드 (Google Colab 호환)
│   ├── 01_main_evaluation.ipynb          # 1:1 통제 환경을 구축하여 BERT 파인튜닝(지도)과 LLM(제로샷/퓨샷)의 개념 인지 능력 평가
│   ├── 02_imbalanced_evaluation.ipynb    # 고문헌 장르의 실제 희소성을 반영한 1:20 불균형 환경에서의 실전 탐지력(Recall) 및 오탐 방어력(Precision) 검증
│   └── 03_data_efficiency_evaluation.ipynb # 훈련 데이터 투입 비율(10~100%) 증강에 따른 데이터 효율성(Data Efficiency) 및 학습 궤적 분석
│
└── outputs/                              # 결과물 (자동 생성)
    ├── confusion_matrix_*.png            # 방법론별 교차 검증 혼동 행렬 이미지
    └── final_integrated_evaluation.csv   # 모델별 최종 예측 및 산출 근거 통합 시트

```

## 💻 Code & Experiments (실험 및 방법론)

모든 실험은 재현성(Reproducibility)을 위해 `RANDOM_SEED = 42`로 고정된 독립적 파이프라인에서 실행되었습니다.

1. **BERT Fine-tuning (Supervised):** 텍스트 원문과 인간의 마크업 메타데이터를 쌍(Pair)으로 입력하여 은유와 전고를 인식하도록 훈련.
2. **BERT Clustering (Unsupervised):** `[CLS]` 토큰 임베딩 기반 K-Means 군집화 수행.
3. **LLM Zero-shot / Few-shot:** 생성형 AI의 연쇄적 추론(Chain-of-Thought)을 통한 자동 판별.

## ⚠️ 데이터 누수(Data Leakage) 및 인간 평가 자료에 대한 안내

* 본 저장소의 `data/` 폴더에 포함된 `인간평가통합본.csv` 등의 인간 평가 자료는 특정 무작위 샘플링 시점에서 추출된 1회성 스냅샷(Snapshot)입니다. 이는 기계와 인간의 정성적 판별 차이를 사후 분석(Error Analysis)하기 위한 목적으로 제한적으로 제공됩니다.
* **모델의 최종 성능 지표(포스터에 기재된 F1-score, Precision, Recall 등)는 이 스냅샷과 무관하게, 시드가 고정된 별도의 무작위 분할(Random Split) 파이프라인을 통해 완전히 독립적으로 도출되었습니다.**
* 이는 기계학습 과정에서 평가용 데이터(Test Set)가 훈련 데이터(Train Set)에 혼입되는 데이터 누수 현상을 원천적으로 차단하고, 방법론 간 대조의 학술적 타당성과 객관성을 보장하기 위함입니다.

## 🤖 Acknowledgments / AI Assistance
본 연구의 실험 파이프라인 구축(Python 스크립트 작성 및 디버깅) 및 영문 번역 과정에서 생성형 AI(Gemini)의 보조를 받았습니다. (The experimental pipeline code and English translations in this project were developed with the assistance of generative AI.)

## 📚 References (주요 참고문헌)

* 胡靭奮·諸雨辰 (2015), 「唐詩題材自動分類研究」, 『中文信息學報』.
* Hou, J. & Zhang, S. (2024), "Exploring Thematic Diversity in Classical Chinese Poetry: A Novel Dataset and a BERT-Enhanced Ensemble Learning Approach", *Digital Scholarship in the Humanities*.
* Wang, E. et al. (2021), "GuwenBERT: A Pre-Trained Language Model for Classical Chinese", *arXiv preprint*.

```

```
