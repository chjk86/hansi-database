"""Step 6: LLM-based (Gemini) frontier-poem classifier, for comparison against
the rule-based and TF-IDF baselines.

Unlike the rule-based/TF-IDF methods, this asks the model to read the whole
poem and judge whether it genuinely reflects/relates to frontier (변새) life,
per the definition in the research proposal -- not just whether it contains
frontier vocabulary. That distinction is exactly where the rule-based method
hit its ceiling (see README), so this is the step that should be able to
resolve cases like "명장을 애도하는 만사에 將軍이 나오지만 변방 경험을 다룬
시는 아님" that pure keyword matching cannot.

Setup:
    1. Get a free API key at https://aistudio.google.com/apikey
       (Google account, no credit card needed for the free tier).
    2. Set it as an environment variable, do NOT paste it into code/chat:
         PowerShell:  $env:GOOGLE_API_KEY = "your-key-here"
         bash:        export GOOGLE_API_KEY="your-key-here"
    3. python 06_llm_classifier.py --sample 40

Usage:
    python 06_llm_classifier.py --mode gold_recall --sample 40
    python 06_llm_classifier.py --mode ambiguous --sample 40
"""
import argparse
import json
import os
import random
import re
import sys
import time

from common import (
    parse_gold_poems, full_plain, title_plain, author_of, is_frontier,
    load_collection, AUTHOR_FILE,
)

GOLD_PATH = "../data/변새시_1차정리본.txt"
CORPUS_BASE = "../../2025_munzip_title_text_ver/"
TIERS_PATH = "../thesaurus/thesaurus_tiers.json"

PROMPT_TEMPLATE = """당신은 한국 한시 연구자입니다. 아래 한시가 "변새시(邊塞詩)"인지 판단하세요.

변새시의 정의: 변방의 생활을 반영하거나 변방 생활에 관련된 한시. 국경 지역의 실제
풍경이나 경험을 다루거나(實景), 변방에 가지 않고도 변새시 특유의 주제적 관습·비장한
정서·전고를 빌려 관념적으로 그려낸 경우(虛景)도 포함합니다.

주의: 시 안에 將軍·關防처럼 변방과 관련된 단어가 등장하더라도, 그것이 시 전체의
중심 주제가 아니라 스쳐 지나가는 언급(예: 무관에 대한 일반적인 만사·전별시 등)에
불과하다면 변새시가 아닙니다. 시 전체가 무엇을 다루고 있는지 보고 판단하세요.

시 제목: {title}
시 본문: {body}

반드시 아래 JSON 형식으로만 답하세요. 다른 말은 하지 마세요.
{{"is_frontier": true 또는 false, "confidence": 0~1 사이 숫자, "reason": "한 문장 근거"}}
"""


def classify_with_gemini(client, model_name, title, body):
    prompt = PROMPT_TEMPLATE.format(title=title, body=body)
    for attempt in range(3):
        try:
            resp = client.models.generate_content(model=model_name, contents=prompt)
            text = resp.text.strip()
            m = re.search(r"\{.*\}", text, re.S)
            if not m:
                return None
            return json.loads(m.group(0))
        except Exception as e:
            msg = str(e)
            if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
                # free-tier rate limit hit: honor the server's requested retryDelay
                m = re.search(r"'retryDelay': '(\d+)s'", msg)
                wait = int(m.group(1)) + 2 if m else 20
                print(f"  [rate limited, waiting {wait}s]", file=sys.stderr)
                time.sleep(wait)
                continue
            if attempt == 2:
                print(f"  [error after 3 tries] {e}", file=sys.stderr)
                return None
            time.sleep(2 ** attempt)
    return None


def build_gold_recall_sample(n):
    poems = [p for p in parse_gold_poems(GOLD_PATH) if is_frontier(p)]
    random.seed(42)
    sample = random.sample(poems, min(n, len(poems)))
    return [(author_of(p), title_plain(p), full_plain(p), True) for p in sample]


def build_ambiguous_sample(n):
    tiers = json.load(open(TIERS_PATH, encoding="utf-8"))
    specific = set(tiers["specific"])

    poems = parse_gold_poems(GOLD_PATH)
    gold_titles = {a: set() for a in AUTHOR_FILE}
    for p in poems:
        a = author_of(p)
        if a in gold_titles:
            gold_titles[a].add(title_plain(p))

    ambiguous = []
    for author, fn in AUTHOR_FILE.items():
        for title, body in load_collection(CORPUS_BASE + fn):
            if title in gold_titles[author]:
                continue
            full = title + body
            if any(t in full for t in specific):
                ambiguous.append((author, title, full, None))  # label unknown

    random.seed(42)
    return random.sample(ambiguous, min(n, len(ambiguous)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["gold_recall", "ambiguous"], default="gold_recall")
    ap.add_argument("--sample", type=int, default=40)
    ap.add_argument("--model", default="gemini-3.5-flash")
    ap.add_argument("--pace", type=float, default=4.5,
                     help="seconds to sleep between requests, to stay under the free-tier RPM limit")
    args = ap.parse_args()

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("GOOGLE_API_KEY not set. See the module docstring for setup steps.", file=sys.stderr)
        sys.exit(1)

    from google import genai
    client = genai.Client(api_key=api_key)

    rows = (build_gold_recall_sample(args.sample) if args.mode == "gold_recall"
            else build_ambiguous_sample(args.sample))

    # Resume support: free-tier daily quotas are small, so re-running the same
    # command later should pick up where it left off instead of re-spending
    # quota on poems already classified.
    out_path = f"../results/llm_{args.mode}_sample.txt"
    already_done = set()
    if os.path.exists(out_path):
        for line in open(out_path, encoding="utf-8"):
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 4 and parts[0] != "[FAILED]":
                already_done.add((parts[2], parts[3]))  # (author, title)
            elif len(parts) >= 3 and parts[0] == "[FAILED]":
                pass  # allow retrying failed ones
    if already_done:
        print(f"resuming: {len(already_done)} poems already classified in {out_path}, skipping those")

    correct = 0
    scored = 0
    done_this_run = 0
    with open(out_path, "a", encoding="utf-8") as f:
        for author, title, body, true_label in rows:
            if (author, title) in already_done:
                continue
            result = classify_with_gemini(client, args.model, title, body)
            if result is None:
                f.write(f"[FAILED]\t\t{author}\t{title}\t\n")
                f.flush()
                continue
            pred = result.get("is_frontier")
            conf = result.get("confidence")
            reason = result.get("reason", "")
            f.write(f"{pred}\t{conf}\t{author}\t{title}\t{reason}\n")
            f.flush()
            done_this_run += 1
            if true_label is not None:
                scored += 1
                if pred == true_label:
                    correct += 1
            print(f"[{done_this_run}/{len(rows)-len(already_done)}] {author} / {title[:20]} -> {pred} ({conf})")
            time.sleep(args.pace)

    if scored:
        print(f"\naccuracy on labeled sample (this run): {correct}/{scored} ({correct/scored*100:.1f}%)")
    print(f"saved {out_path} ({done_this_run} newly classified this run)")


if __name__ == "__main__":
    main()
