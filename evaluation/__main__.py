"""Run from the repository root with python -m evaluation."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from invoice_lens.engine import ask, extract
from invoice_lens.model import FieldModel


def main():
    cases = json.loads(Path(__file__).with_name("cases.json").read_text("utf-8"))
    model = FieldModel()
    retrieved = gold = extracted = exact = cited = questions = rejected = negatives = 0
    with TemporaryDirectory() as folder:
        for language, document in cases["documents"].items():
            source = Path(folder) / f"{language}.txt"
            source.write_text("\f".join(document["pages"]), encoding="utf-8")
            facts, _ = extract([source], model)
            expected = document["fields"]
            gold += len(expected)
            retrieved += len(facts)
            extracted += sum(any((fact.field, fact.value, fact.page) == (key, value, page)
                                 for fact in facts) for key, (value, page, _) in expected.items())
            for qlang, prompts in cases["questions"].items():
                pair = 0
                for field, question in prompts.items():
                    value, page, prefix = expected[field]
                    result = ask(question, model, facts, [source.name])
                    questions += 1
                    if result["status"] != "answered" or result["answers"][0]["value"] != value:
                        continue
                    exact += 1
                    refs = result["answers"][0]["citations"]
                    ok = any(ref["source"] == source.name and ref["page"] == page
                             and ref["quote"].startswith(prefix + ":") and
                             ref["quote"] == document["pages"][page - 1].splitlines()[ref["line"] - 1]
                             for ref in refs)
                    cited += ok
                    pair += ok
                print(f"{qlang} question / {language} document: {pair}/{len(prompts)} exact with citation")
            for question in cases["unsupported"]:
                negatives += 1
                rejected += ask(question, model, facts, [source.name])["status"] == "unsupported_question"
    print(f"Extraction precision: {extracted}/{retrieved}; recall: {extracted}/{gold}")
    print(f"Exact answers: {exact}/{questions}; exact answers with verified citations: {cited}/{questions}")
    print(f"Unsupported questions rejected: {rejected}/{negatives} (3 unique questions)")


if __name__ == "__main__":
    main()
