import re
import pandas as pd
from opencc import OpenCC

cc = OpenCC('s2t')

def extract_only_hanzi(text):
    """띄어쓰기 및 특수문자 소거, 순수 한자만 추출"""
    return re.sub(r'[^\u4E00-\u9FFF]', '', text)

def extract_clean_text_blocks(content):
    """<text>...</text> 태그 소거 및 작품 단위 분리"""
    poems = []
    matches = re.findall(r'<text>(.*?)</text>', content, flags=re.DOTALL | re.IGNORECASE)
    for match in matches:
        clean_text = re.sub(r'<[^>]+>', '', match).strip()
        clean_text = re.sub(r'\s+', ' ', clean_text)
        if clean_text:
            poems.append(clean_text)
    return poems

def load_poems(file_path, is_simplified=False):
    """골드 데이터 파일 로드 및 작품 단위 리스트 반환"""
    poems = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
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
        print(f"[오류] 파일 로드 실패 ({file_path}): {e}")
    return poems

def calculate_tf_df(poems, keywords):
    """작품 리스트(poems)에 대한 키워드별 TF(총 빈도) 및 DF(출현 작품 수) 산출"""
    tf_dict = {kw: 0 for kw in keywords}
    df_dict = {kw: 0 for kw in keywords}
    
    for poem in poems:
        for kw in keywords:
            count = len(re.findall(re.escape(kw), poem))
            if count > 0:
                tf_dict[kw] += count
                df_dict[kw] += 1
                
    return tf_dict, df_dict

def analyze_gold_features(cn_pos_path, kr_pos_path, kr_feature_csv, cn_feature_csv, top_n=50):
    # 1. 골드 데이터 로드
    cn_poems = load_poems(cn_pos_path, is_simplified=True)
    kr_poems = load_poems(kr_pos_path, is_simplified=False)
    
    total_cn_poems = len(cn_poems)
    total_kr_poems = len(kr_poems)
    
    print(f"[데이터 현황] 중국 변새시 골드: 총 {total_cn_poems}수 | 조선 변새시 골드: 총 {total_kr_poems}수")
    
    # 2. 조선/중국 최상위 특성 로드
    df_kr_feat = pd.read_csv(kr_feature_csv).sort_values(by='Coefficient', ascending=False).head(top_n)
    df_cn_feat = pd.read_csv(cn_feature_csv).sort_values(by='Coefficient', ascending=True).head(top_n)
    
    # 3. 조선 고유 자질 검증
    kr_keywords = df_kr_feat['N-gram'].tolist()
    kr_coef_dict = dict(zip(df_kr_feat['N-gram'], df_kr_feat['Coefficient']))
    
    kr_tf_in_kr, kr_df_in_kr = calculate_tf_df(kr_poems, kr_keywords)
    kr_tf_in_cn, kr_df_in_cn = calculate_tf_df(cn_poems, kr_keywords)
    
    stats_kr = []
    for kw in kr_keywords:
        stats_kr.append({
            "Domain": "조선 고유 자질(Class 1)",
            "N-gram": kw,
            "LR_Coefficient": kr_coef_dict[kw],
            "조선_TF(총빈도)": kr_tf_in_kr,
            "조선_DF(작품수)": kr_df_in_kr[kw],
            "조선_DF비율(%)": round((kr_df_in_kr[kw] / total_kr_poems) * 100, 2),
            "중국_TF(총빈도)": kr_tf_in_cn[kw],
            "중국_DF(작품수)": kr_df_in_cn[kw],
            "중국_DF비율(%)": round((kr_df_in_cn[kw] / total_cn_poems) * 100, 2),
        })
        
    # 4. 중국 고유 자질 검증
    cn_keywords = df_cn_feat['N-gram'].tolist()
    cn_coef_dict = dict(zip(df_cn_feat['N-gram'], df_cn_feat['Coefficient']))
    
    cn_tf_in_kr, cn_df_in_kr = calculate_tf_df(kr_poems, cn_keywords)
    cn_tf_in_cn, cn_df_in_cn = calculate_tf_df(cn_poems, cn_keywords)
    
    stats_cn = []
    for kw in cn_keywords:
        stats_cn.append({
            "Domain": "중국 고유 자질(Class 0)",
            "N-gram": kw,
            "LR_Coefficient": cn_coef_dict[kw],
            "조선_TF(총빈도)": cn_tf_in_kr[kw],
            "조선_DF(작품수)": cn_df_in_kr[kw],
            "조선_DF비율(%)": round((cn_df_in_kr[kw] / total_kr_poems) * 100, 2),
            "중국_TF(총빈도)": cn_tf_in_cn[kw],
            "중국_DF(작품수)": cn_df_in_cn[kw],
            "중국_DF비율(%)": round((cn_df_in_cn[kw] / total_cn_poems) * 100, 2),
        })
        
    # 5. 결과 저장
    df_kr_res = pd.DataFrame(stats_kr)
    df_cn_res = pd.DataFrame(stats_cn)
    
    df_kr_res.to_csv("gold_korean_features_validation.csv", index=False, encoding="utf-8-sig")
    df_cn_res.to_csv("gold_chinese_features_validation.csv", index=False, encoding="utf-8-sig")
    
    print("\n[검증 완료] 저장 파일:")
    print("- gold_korean_features_validation.csv")
    print("- gold_chinese_features_validation.csv")

if __name__ == "__main__":
    CN_POS_FILE = "변새시_중국_작품소거.txt"
    KR_POS_FILE = "변새시_2차정리본.txt"
    KR_FEATURE_CSV = "korean_specific_features.csv"
    CN_FEATURE_CSV = "chinese_specific_features.csv"
    
    analyze_gold_features(CN_POS_FILE, KR_POS_FILE, KR_FEATURE_CSV, CN_FEATURE_CSV, top_n=50)
