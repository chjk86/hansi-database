from pathlib import Path

from src.poem_model import Poem
from src.xml_io import parse_collection

_OUTPUT_DIR = Path(__file__).resolve().parent / "2026-08-05-model-comparison"
_MODEL_LABELS = ["claude-opus-4.7", "gemini-3-flash-preview", "gpt-5.5"]


def _poem_summary(poem: Poem) -> str:
    theme_labels = ", ".join(f"{t.label_ko}({t.category})" for t in poem.themes) or "(없음)"
    lines_text = "\n".join(f"    {ln.order}구: {ln.content_xml}" for ln in poem.lines)
    return (
        f"  형식: {poem.basetype}/{poem.detailtype}\n"
        f"  주제: {theme_labels}\n"
        f"  본문:\n{lines_text}"
    )


def build_comparison_report(model_outputs: dict[str, list[Poem]]) -> str:
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
                sections.append(_poem_summary(poems_by_id[poem_id]))
            else:
                sections.append("  (결과 없음 -- 이 모델에서 누락됨)")
        sections.append("")

    return "\n".join(sections)


def main() -> None:
    model_outputs: dict[str, list[Poem]] = {}
    for label in _MODEL_LABELS:
        output_path = _OUTPUT_DIR / f"output_{label}.xml"
        if output_path.exists():
            model_outputs[label] = parse_collection(output_path)
        else:
            model_outputs[label] = []

    report = build_comparison_report(model_outputs)
    (_OUTPUT_DIR / "comparison_report.txt").write_text(report, encoding="utf-8")
    print(f"리포트 저장: {_OUTPUT_DIR / 'comparison_report.txt'}")


if __name__ == "__main__":
    main()
