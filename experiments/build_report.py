import csv
from pathlib import Path

from src.poem_model import Poem
from src.xml_io import parse_collection

_OUTPUT_DIR = Path(__file__).resolve().parent / "2026-08-05-model-comparison"
# "원문"이 맨 앞에 온다: 설계 스펙의 리포트 레이아웃(원문 -> Claude -> Gemini -> GPT)을
# 따른다. run_comparison.py의 main()이 output_원문.xml을 무조건(모델 호출 성공 여부와
# 무관하게) 먼저 써 두므로, 아래 main()의 공용 "output_{label}.xml 있으면 읽고 없으면
# 빈 리스트" 로직이 원문에도 그대로 적용되어도 원문이 "결과 없음"으로 잘못 표시될
# 일이 없다. qa_{원문}.csv는 애초에 존재하지 않으므로(원문은 파이프라인을 거치지
# 않음) _load_qa_flags가 빈 dict를 반환해 QA 플래그도 오작동하지 않는다.
_MODEL_LABELS = ["원문", "claude-opus-4.7", "gemini-3-flash-preview", "gpt-5.5"]


def _poem_summary(poem: Poem, flags: list[dict] | None = None) -> str:
    flags = flags or []
    # "처리 실패" QA 행이 있으면, 정상 처리된 것과 시각적으로 구분되도록 실패
    # 사실을 맨 앞에 명시한다 -- 그렇지 않으면 "형식: /"와 "주제: (없음)"이
    # 정상적으로 주제가 없는 시와 똑같이 보여 크래시와 빈 결과를 구분할 수 없다.
    failure_flags = [f for f in flags if f.get("item") == "처리 실패"]
    other_flags = [f for f in flags if f.get("item") != "처리 실패"]

    if failure_flags:
        reasons = "; ".join(f["reason"] for f in failure_flags)
        return f"  [!! 처리 실패 -- 아래 내용은 실패 시점까지의 부분 결과일 수 있음] {reasons}"

    theme_labels = ", ".join(f"{t.label_ko}({t.category})" for t in poem.themes) or "(없음)"
    lines_text = "\n".join(f"    {ln.order}구: {ln.content_xml}" for ln in poem.lines)
    summary = (
        f"  형식: {poem.basetype}/{poem.detailtype}\n"
        f"  주제: {theme_labels}\n"
        f"  본문:\n{lines_text}"
    )
    if other_flags:
        qa_text = "; ".join(f"{f['item']}: {f['reason']}" for f in other_flags)
        summary += f"\n  QA 플래그: {qa_text}"
    return summary


def build_comparison_report(
    model_outputs: dict[str, list[Poem]],
    qa_flags: dict[str, dict[str, list[dict]]] | None = None,
) -> str:
    qa_flags = qa_flags or {}

    all_poem_ids: list[str] = []
    seen = set()
    for poems in model_outputs.values():
        for p in poems:
            if p.id not in seen:
                seen.add(p.id)
                all_poem_ids.append(p.id)

    sections = []
    for poem_id in all_poem_ids:
        sections.append(f"{'=' * 20} {poem_id} {'=' * 20}")
        for label in _MODEL_LABELS:
            poems_by_id = {p.id: p for p in model_outputs.get(label, [])}
            sections.append(f"--- {label} ---")
            if poem_id in poems_by_id:
                poem_flags = qa_flags.get(label, {}).get(poem_id, [])
                sections.append(_poem_summary(poems_by_id[poem_id], poem_flags))
            else:
                sections.append("  (결과 없음 -- 이 모델에서 누락됨)")
        sections.append("")

    return "\n".join(sections)


def _load_qa_flags(label: str) -> dict[str, list[dict]]:
    """qa_{label}.csv를 읽어 poem_id -> QA 행 리스트로 묶는다. 파일이 없으면
    (예: "원문"은 애초에 파이프라인을 거치지 않으므로 QA 파일이 없다) 빈 dict를
    반환한다."""
    path = _OUTPUT_DIR / f"qa_{label}.csv"
    if not path.exists():
        return {}
    flags_by_poem: dict[str, list[dict]] = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            flags_by_poem.setdefault(row["poem_id"], []).append(row)
    return flags_by_poem


def main() -> None:
    model_outputs: dict[str, list[Poem]] = {}
    qa_flags: dict[str, dict[str, list[dict]]] = {}
    for label in _MODEL_LABELS:
        output_path = _OUTPUT_DIR / f"output_{label}.xml"
        if output_path.exists():
            model_outputs[label] = parse_collection(output_path)
        else:
            model_outputs[label] = []
        qa_flags[label] = _load_qa_flags(label)

    report = build_comparison_report(model_outputs, qa_flags)
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (_OUTPUT_DIR / "comparison_report.txt").write_text(report, encoding="utf-8")
    print(f"리포트 저장: {_OUTPUT_DIR / 'comparison_report.txt'}")


if __name__ == "__main__":
    main()
