"""Step 9: verify the full-corpus shortlist (`08_score_full_corpus.py`) with
the LLM, in batches, with resume support -- same recipe as 06_llm_classifier.py
but reading from the pre-scored shortlist instead of gold/ambiguous samples.

Setup: same as 06_llm_classifier.py (GOOGLE_API_KEY env var, free tier).

Usage:
    python 09_llm_verify_shortlist.py --limit 1000
    python 09_llm_verify_shortlist.py --limit 1000 --batch-size 10 --pace 2.0
"""
import argparse
import json
import os
import re
import sys
import time

SHORTLIST_PATH = "../results/full_corpus_shortlist.json"
OUT_PATH = "../results/full_corpus_llm_verified.txt"

DEFINITION = """변새시(邊塞詩)의 정의: 변방의 생활을 반영하거나 변방 생활에 관련된 한시. 국경 지역의 실제
풍경이나 경험을 다루거나(實景), 변방에 가지 않고도 변새시 특유의 주제적 관습·비장한
정서·전고를 빌려 관념적으로 그려낸 경우(虛景)도 포함합니다.

주의: 시 안에 將軍·關防처럼 변방과 관련된 단어가 등장하더라도, 그것이 시 전체의
중심 주제가 아니라 스쳐 지나가는 언급(예: 무관에 대한 일반적인 만사·전별시 등)에
불과하다면 변새시가 아닙니다. 시 전체가 무엇을 다루고 있는지 보고 판단하세요."""

BATCH_PROMPT_TEMPLATE = """당신은 한국 한시 연구자입니다. 아래 여러 편의 한시 각각이 "변새시(邊塞詩)"인지 판단하세요.

{definition}

{poems_block}

반드시 아래 JSON 배열 형식으로만 답하세요. 각 시마다 하나의 객체를 넣고, 입력한 시의 개수와
정확히 같은 개수의 객체를 순서대로 반환하세요. 다른 말은 하지 마세요.
[{{"index": 1, "is_frontier": true 또는 false, "confidence": 0~1 사이 숫자, "reason": "한 문장 근거"}}, ...]
"""


def classify_batch(client, model_name, batch):
    poems_block = "\n\n".join(
        f"[{i+1}] 제목: {title}\n본문: {body}" for i, (title, body) in enumerate(batch)
    )
    prompt = BATCH_PROMPT_TEMPLATE.format(definition=DEFINITION, poems_block=poems_block)

    for attempt in range(3):
        try:
            resp = client.models.generate_content(model=model_name, contents=prompt)
            text = resp.text.strip()
            m = re.search(r"\[.*\]", text, re.S)
            if not m:
                return [None] * len(batch)
            parsed = json.loads(m.group(0))
            out = [None] * len(batch)
            for item in parsed:
                idx = item.get("index")
                if isinstance(idx, int) and 1 <= idx <= len(batch):
                    out[idx - 1] = item
            return out
        except Exception as e:
            msg = str(e)
            if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
                m = re.search(r"'retryDelay': '(\d+)s'", msg)
                wait = int(m.group(1)) + 2 if m else 20
                print(f"  [rate limited, waiting {wait}s]", file=sys.stderr)
                time.sleep(wait)
                continue
            if attempt == 2:
                print(f"  [error after 3 tries] {e}", file=sys.stderr)
                return [None] * len(batch)
            time.sleep(2 ** attempt)
    return [None] * len(batch)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=1000, help="how many top shortlist entries to verify")
    ap.add_argument("--model", default="gemini-3.5-flash")
    ap.add_argument("--batch-size", type=int, default=10)
    ap.add_argument("--pace", type=float, default=2.0)
    args = ap.parse_args()

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("GOOGLE_API_KEY not set.", file=sys.stderr)
        sys.exit(1)

    from google import genai
    client = genai.Client(api_key=api_key)

    shortlist = json.load(open(SHORTLIST_PATH, encoding="utf-8"))[:args.limit]

    # we don't have poem bodies in the shortlist JSON (only title, to keep it
    # small) -- re-load bodies from the source files on demand.
    from common import load_collection
    CORPUS_DIR = "../../2025_munzip_title_text_ver/"
    bodies_by_file = {}

    def get_body(fn, title):
        if fn not in bodies_by_file:
            bodies_by_file[fn] = dict(load_collection(CORPUS_DIR + fn))
        return bodies_by_file[fn].get(title, "")

    already_done = set()
    if os.path.exists(OUT_PATH):
        for line in open(OUT_PATH, encoding="utf-8"):
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 4 and parts[0] != "[FAILED]":
                already_done.add((parts[2], parts[3]))
    if already_done:
        print(f"resuming: {len(already_done)} already verified, skipping those")

    todo = [e for e in shortlist if (e["file"], e["title"]) not in already_done]
    print(f"{len(todo)} to verify in batches of {args.batch_size} "
          f"({(len(todo) + args.batch_size - 1)//args.batch_size} request(s))")

    done_this_run = 0
    with open(OUT_PATH, "a", encoding="utf-8") as f:
        for start in range(0, len(todo), args.batch_size):
            chunk = todo[start:start + args.batch_size]
            batch_input = [(e["title"], get_body(e["file"], e["title"])) for e in chunk]
            results = classify_batch(client, args.model, batch_input)

            for e, result in zip(chunk, results):
                if result is None:
                    f.write(f"[FAILED]\t\t{e['file']}\t{e['title']}\t\n")
                    continue
                pred = result.get("is_frontier")
                conf = result.get("confidence")
                reason = result.get("reason", "")
                f.write(f"{pred}\t{conf}\t{e['file']}\t{e['title']}\t{reason}\n")
                done_this_run += 1
                print(f"[{done_this_run}/{len(todo)}] {e['file']} / {e['title'][:20]} -> {pred} ({conf})")
            f.flush()

            if start + args.batch_size < len(todo):
                time.sleep(args.pace)

    print(f"saved {OUT_PATH} ({done_this_run} newly verified this run)")


if __name__ == "__main__":
    main()
