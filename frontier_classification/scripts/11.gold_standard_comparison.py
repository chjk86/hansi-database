import re
import random
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from opencc import OpenCC

# 간체 -> 번체 변환기 초기화
cc = OpenCC('s2t')

def extract_only_hanzi(text):
    return re.sub(r'[^\u4E00-\u9FFF]', '', text)

def extract_clean_text_blocks(content):
    poems = []
    matches = re.findall(r'<text>(.*?)</text>', content, flags=re.DOTALL | re.IGNORECASE)
    for match in matches:
        clean_text = re.sub(r'<[^>]+>', '', match).strip()
        clean_text = re.sub(r'\s+', ' ', clean_text)
        if clean_text:
            poems.append(clean_text)
    return poems

def load_and_preprocess_poems(txt_path, is_simplified=False):
    """골드 데이터를 로드하고 한자만 추출"""
    poems = []
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        raw_poems = extract_clean_text_blocks(content)
        if not raw_poems:
            raw_poems = [line.strip() for line in content.split('\n') if line.strip()]
            
        for p in raw_poems:
            trad_text = cc.convert(p) if is_simplified else p
            hanzi_only = extract_only_hanzi(trad_text)
            if hanzi_only:
                poems.append(hanzi_only)
    except Exception as e:
        print(f"[오류] 파일 로드 실패 ({txt_path}): {e}")
    return poems

def run_gold_standard_comparison(cn_pos_path, kr_pos_path, seed=42):
    print("[진행 상황] 양국 골드 데이터 로드 중...")
    cn_poems = load_and_preprocess_poems(cn_pos_path, is_simplified=True)
    kr_poems = load_and_preprocess_poems(kr_pos_path, is_simplified=False)
    
    # 1:1 데이터 동기화 (모수 통제)
    min_len = min(len(cn_poems), len(kr_poems))
    random.seed(seed)
    cn_poems_balanced = random.sample(cn_poems, min_len)
    kr_poems_balanced = random.sample(kr_poems, min_len)

    print(f"\n[데이터 분포: 1:1 무작위 샘플링]")
    print(f"- 중국 변새시(Class 0): {min_len}건")
    print(f"- 조선 변새시(Class 1): {min_len}건")

    # 통합 데이터 및 라벨링 (중국: 0, 조선: 1)
    X_all = cn_poems_balanced + kr_poems_balanced
    y_all = [0] * min_len + [1] * min_len

    X_train, X_test, y_train, y_test = train_test_split(
        X_all, y_all, test_size=0.2, random_state=seed, stratify=y_all
    )

    print("\n[진행 상황] TF-IDF 벡터화 및 로지스틱 회귀 학습 중...")
    vec = TfidfVectorizer(analyzer="char", ngram_range=(2, 3), min_df=2)
    X_train_vec = vec.fit_transform(X_train)
    
    clf = LogisticRegression(class_weight="balanced", max_iter=2000, random_state=seed)
    clf.fit(X_train_vec, y_train)

    print("\n■ 한·중 변새시 1:1 분류 결과 (Classification Report)")
    X_test_vec = vec.transform(X_test)
    print(classification_report(y_test, clf.predict(X_test_vec), target_names=["중국 변새시(0)", "조선 변새시(1)"]))
    
    # 가중치(Coefficient) 분석 및 CSV 추출
    feature_names = vec.get_feature_names_out()
    coefs = clf.coef_[0]
    
    df_features = pd.DataFrame({'N-gram': feature_names, 'Coefficient': coefs})
    
    kr_specific = df_features.sort_values(by='Coefficient', ascending=False)
    cn_specific = df_features.sort_values(by='Coefficient', ascending=True)
    
    kr_specific.to_csv('korean_specific_features.csv', index=False, encoding='utf-8-sig')
    cn_specific.to_csv('chinese_specific_features.csv', index=False, encoding='utf-8-sig')
    df_features.to_csv('all_domain_features.csv', index=False, encoding='utf-8-sig')
    
    print("\n[파일 저장 완료] korean_specific_features.csv, chinese_specific_features.csv 도출 완료.")

if __name__ == "__main__":
    # 실행 시 파일 경로를 실제 환경에 맞게 수정하십시오.
    CN_POS_FILE = "변새시_중국_작품소거.txt"
    KR_POS_FILE = "변새시_2차정리본.txt"
    run_gold_standard_comparison(CN_POS_FILE, KR_POS_FILE)