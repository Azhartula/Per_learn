#!/usr/bin/env python3
"""Expand Year 5 fractions bank with parallel forms A/B/C and distractor maps."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANK = ROOT / "data" / "questions" / "year5_fractions.json"


def _mcq(item_id, skill, difficulty, form, misconceptions, stem, choices, answer, explanation, dmap):
    return {
        "id": item_id,
        "skill": skill,
        "difficulty": difficulty,
        "form": form,
        "misconceptions": misconceptions,
        "stem": stem,
        "type": "mcq",
        "choices": choices,
        "answer": answer,
        "answer_sympy": answer if "/" in str(answer) or str(answer).isdigit() else None,
        "explanation": explanation,
        "distractor_misconceptions": dmap,
    }


def new_items() -> list[dict]:
    items: list[dict] = []

    # --- equivalent_fractions forms B/C ---
    items += [
        _mcq("eq_b01", "equivalent_fractions", 1, "B", ["equivalent_add_same"],
             "Which fraction is equivalent to 1/3?", ["2/5", "2/6", "3/5", "1/6"], "2/6",
             "Multiply num and den by 2.", {"2/5": "equivalent_add_same", "3/5": "equivalent_add_same", "1/6": "bigger_denominator_bigger"}),
        _mcq("eq_b02", "equivalent_fractions", 2, "B", ["equivalent_add_same"],
             "Simplify 8/12.", ["2/3", "4/6", "3/4", "1/2"], "2/3",
             "Divide by 4.", {"4/6": "equivalent_add_same", "3/4": "ignore_denominator", "1/2": "ignore_denominator"}),
        _mcq("eq_b03", "equivalent_fractions", 2, "B", ["equivalent_add_same"],
             "Fill: 3/4 = ?/12", ["6", "8", "9", "7"], "9",
             "Denominator ×3 so numerator ×3.", {"6": "equivalent_add_same", "8": "equivalent_add_same", "7": "equivalent_add_same"}),
        _mcq("eq_c01", "equivalent_fractions", 1, "C", ["equivalent_add_same"],
             "Which is equivalent to 2/5?", ["4/10", "3/6", "2/10", "5/2"], "4/10",
             "Multiply by 2/2.", {"3/6": "equivalent_add_same", "2/10": "ignore_denominator", "5/2": "ignore_denominator"}),
        _mcq("eq_c02", "equivalent_fractions", 2, "C", ["equivalent_add_same"],
             "Are 2/8 and 1/4 equivalent?", ["yes", "no", "cannot tell"], "yes",
             "2/8 simplifies to 1/4.", {"no": "equivalent_add_same"}),
        _mcq("eq_c03", "equivalent_fractions", 3, "C", ["equivalent_add_same"],
             "Which equals 5/6?", ["10/12", "6/5", "5/12", "10/6"], "10/12",
             "Multiply by 2/2.", {"6/5": "ignore_denominator", "5/12": "ignore_denominator", "10/6": "ignore_denominator"}),
        _mcq("eq_a07", "equivalent_fractions", 2, "A", ["equivalent_add_same"],
             "Which is equivalent to 3/9?", ["1/3", "3/6", "2/3", "9/3"], "1/3",
             "Divide by 3.", {"3/6": "equivalent_add_same", "2/3": "ignore_denominator", "9/3": "ignore_denominator"}),
        _mcq("eq_a08", "equivalent_fractions", 3, "A", ["equivalent_add_same"],
             "Complete: 4/5 = 8/?", ["10", "9", "12", "16"], "10",
             "Numerator ×2 ⇒ denominator ×2.", {"9": "equivalent_add_same", "12": "equivalent_add_same", "16": "equivalent_add_same"}),
    ]

    # --- ordering ---
    items += [
        _mcq("ord_b01", "ordering_fractions", 1, "B", ["bigger_denominator_bigger"],
             "Which is larger: 1/5 or 1/2?", ["1/5", "1/2", "equal"], "1/2",
             "Same numerator: smaller den is larger.", {"1/5": "bigger_denominator_bigger"}),
        _mcq("ord_b02", "ordering_fractions", 2, "B", ["ignore_denominator"],
             "Which is greater: 3/5 or 4/7?", ["3/5", "4/7", "equal"], "3/5",
             "3/5=0.6, 4/7≈0.57.", {"4/7": "ignore_denominator"}),
        _mcq("ord_b03", "ordering_fractions", 2, "B", ["ignore_denominator"],
             "Order smallest to largest: 2/3, 1/4, 1/2", ["1/4, 1/2, 2/3", "1/2, 1/4, 2/3", "2/3, 1/2, 1/4"], "1/4, 1/2, 2/3",
             "Convert or compare carefully.", {"1/2, 1/4, 2/3": "ignore_denominator", "2/3, 1/2, 1/4": "ignore_denominator"}),
        _mcq("ord_c01", "ordering_fractions", 1, "C", ["bigger_denominator_bigger"],
             "Which is smaller: 1/6 or 1/8?", ["1/6", "1/8", "equal"], "1/8",
             "Unit fractions: larger den is smaller value.", {"1/6": "bigger_denominator_bigger"}),
        _mcq("ord_c02", "ordering_fractions", 2, "C", ["ignore_denominator"],
             "Which is greater: 5/8 or 3/5?", ["5/8", "3/5", "equal"], "5/8",
             "5/8=0.625, 3/5=0.6.", {"3/5": "ignore_denominator"}),
        _mcq("ord_c03", "ordering_fractions", 3, "C", ["ignore_denominator"],
             "Which is closest to 1/2: 2/5, 3/7, or 4/9?", ["2/5", "3/7", "4/9"], "3/7",
             "3/7≈0.429 closest to 0.5 among options? Wait check: 2/5=0.4, 3/7≈0.429, 4/9≈0.444 — 4/9 closest.",
             {"2/5": "ignore_denominator", "3/7": "ignore_denominator"}),
    ]
    # Fix ord_c03 answer to 4/9
    items[-1]["answer"] = "4/9"
    items[-1]["answer_sympy"] = "4/9"
    items[-1]["explanation"] = "2/5=0.4, 3/7≈0.429, 4/9≈0.444; 4/9 is closest to 1/2."
    items[-1]["distractor_misconceptions"] = {"2/5": "ignore_denominator", "3/7": "ignore_denominator"}

    items += [
        _mcq("ord_a08", "ordering_fractions", 2, "A", ["ignore_denominator"],
             "Which is greater: 4/9 or 3/7?", ["4/9", "3/7", "equal"], "4/9",
             "4/9≈0.444, 3/7≈0.429.", {"3/7": "ignore_denominator"}),
        _mcq("ord_a09", "ordering_fractions", 3, "A", ["bigger_denominator_bigger"],
             "True or false: 3/8 is greater than 3/5.", ["true", "false"], "false",
             "Same numerator: 3/5 > 3/8.", {"true": "bigger_denominator_bigger"}),
    ]

    # --- add/subtract ---
    items += [
        _mcq("add_b01", "add_subtract_fractions", 1, "B", ["add_across"],
             "Calculate 2/9 + 4/9.", ["6/9", "6/18", "8/9", "2/4"], "6/9",
             "Add numerators only.", {"6/18": "add_across", "8/9": "add_across", "2/4": "add_across"}),
        _mcq("add_b02", "add_subtract_fractions", 2, "B", ["add_across"],
             "Calculate 1/3 + 1/6.", ["1/2", "2/9", "1/9", "2/6"], "1/2",
             "1/3=2/6; 2/6+1/6=3/6=1/2.", {"2/9": "add_across", "1/9": "add_across", "2/6": "add_across"}),
        _mcq("add_b03", "add_subtract_fractions", 2, "B", ["add_across"],
             "Calculate 7/10 − 1/5.", ["1/2", "6/5", "6/10", "1/10"], "1/2",
             "1/5=2/10; 7/10−2/10=5/10=1/2.", {"6/5": "add_across", "6/10": "add_across", "1/10": "add_across"}),
        _mcq("add_c01", "add_subtract_fractions", 1, "C", ["add_across"],
             "Calculate 3/8 + 2/8.", ["5/8", "5/16", "6/8", "1/2"], "5/8",
             "Same den: add nums.", {"5/16": "add_across", "6/8": "add_across"}),
        _mcq("add_c02", "add_subtract_fractions", 2, "C", ["add_across"],
             "Calculate 3/4 − 1/8.", ["5/8", "2/4", "2/8", "4/12"], "5/8",
             "3/4=6/8; 6/8−1/8=5/8.", {"2/4": "add_across", "2/8": "add_across", "4/12": "add_across"}),
        _mcq("add_c03", "add_subtract_fractions", 3, "C", ["add_across"],
             "Calculate 2/5 + 3/10.", ["7/10", "5/15", "5/10", "6/10"], "7/10",
             "2/5=4/10; 4/10+3/10=7/10.", {"5/15": "add_across", "5/10": "add_across", "6/10": "add_across"}),
        _mcq("add_a08", "add_subtract_fractions", 2, "A", ["add_across"],
             "Calculate 5/6 − 1/3.", ["1/2", "4/3", "4/6", "1/6"], "1/2",
             "1/3=2/6; 5/6−2/6=3/6=1/2.", {"4/3": "add_across", "4/6": "add_across", "1/6": "add_across"}),
        _mcq("add_a09", "add_subtract_fractions", 3, "A", ["add_across"],
             "Calculate 1/2 + 2/5.", ["9/10", "3/7", "3/10", "2/7"], "9/10",
             "1/2=5/10; 5/10+4/10=9/10.", {"3/7": "add_across", "3/10": "add_across", "2/7": "add_across"}),
    ]

    # --- multiply ---
    items += [
        _mcq("mul_b01", "multiply_fractions", 1, "B", ["multiply_add_confusion"],
             "Calculate 1/4 × 1/2.", ["1/8", "2/6", "1/6", "1/2"], "1/8",
             "Multiply nums and dens.", {"2/6": "multiply_add_confusion", "1/6": "multiply_add_confusion", "1/2": "multiply_add_confusion"}),
        _mcq("mul_b02", "multiply_fractions", 2, "B", ["multiply_add_confusion"],
             "Calculate 2/3 × 3/5.", ["2/5", "5/8", "6/15", "1/5"], "2/5",
             "2/3×3/5=6/15=2/5.", {"5/8": "multiply_add_confusion", "6/15": "multiply_add_confusion"}),
        _mcq("mul_b03", "multiply_fractions", 2, "B", ["multiply_add_confusion"],
             "Calculate 3/4 × 2/5.", ["3/10", "5/9", "6/20", "1/2"], "3/10",
             "6/20=3/10.", {"5/9": "multiply_add_confusion", "6/20": "multiply_add_confusion", "1/2": "multiply_add_confusion"}),
        _mcq("mul_c01", "multiply_fractions", 1, "C", ["multiply_add_confusion"],
             "Calculate 1/5 × 1/3.", ["1/15", "2/8", "1/8", "1/2"], "1/15",
             "Multiply across.", {"2/8": "multiply_add_confusion", "1/8": "multiply_add_confusion"}),
        _mcq("mul_c02", "multiply_fractions", 2, "C", ["multiply_add_confusion"],
             "Calculate 4/5 × 1/2.", ["2/5", "5/7", "4/10", "1/5"], "2/5",
             "4/10=2/5.", {"5/7": "multiply_add_confusion", "4/10": "multiply_add_confusion"}),
        _mcq("mul_c03", "multiply_fractions", 3, "C", ["multiply_add_confusion"],
             "Calculate 5/6 × 3/4.", ["5/8", "8/10", "15/24", "2/3"], "5/8",
             "15/24=5/8.", {"8/10": "multiply_add_confusion", "15/24": "multiply_add_confusion", "2/3": "multiply_add_confusion"}),
        _mcq("mul_a08", "multiply_fractions", 2, "A", ["multiply_add_confusion"],
             "Calculate 2/5 × 5/6.", ["1/3", "7/11", "10/30", "2/6"], "1/3",
             "10/30=1/3.", {"7/11": "multiply_add_confusion", "10/30": "multiply_add_confusion", "2/6": "multiply_add_confusion"}),
        _mcq("mul_a09", "multiply_fractions", 3, "A", ["multiply_add_confusion"],
             "Calculate 3/8 × 4/9.", ["1/6", "7/17", "12/72", "3/9"], "1/6",
             "12/72=1/6.", {"7/17": "multiply_add_confusion", "12/72": "multiply_add_confusion", "3/9": "multiply_add_confusion"}),
    ]

    # --- fraction of ---
    items += [
        _mcq("of_b01", "fraction_of", 1, "B", ["of_means_divide_wrong"],
             "What is 1/4 of 20?", ["5", "4", "16", "24"], "5",
             "20÷4=5.", {"4": "of_means_divide_wrong", "16": "of_means_divide_wrong", "24": "of_means_divide_wrong"}),
        _mcq("of_b02", "fraction_of", 2, "B", ["of_means_divide_wrong"],
             "What is 2/5 of 30?", ["12", "15", "10", "6"], "12",
             "30÷5=6; 6×2=12.", {"15": "of_means_divide_wrong", "10": "of_means_divide_wrong", "6": "of_means_divide_wrong"}),
        _mcq("of_b03", "fraction_of", 2, "B", ["of_means_divide_wrong"],
             "What is 3/4 of 16?", ["12", "4", "19", "8"], "12",
             "16÷4=4; 4×3=12.", {"4": "of_means_divide_wrong", "19": "of_means_divide_wrong", "8": "of_means_divide_wrong"}),
        _mcq("of_c01", "fraction_of", 1, "C", ["of_means_divide_wrong"],
             "What is 1/3 of 18?", ["6", "3", "15", "9"], "6",
             "18÷3=6.", {"3": "of_means_divide_wrong", "15": "of_means_divide_wrong", "9": "of_means_divide_wrong"}),
        _mcq("of_c02", "fraction_of", 2, "C", ["of_means_divide_wrong"],
             "What is 3/5 of 25?", ["15", "5", "22", "10"], "15",
             "25÷5×3=15.", {"5": "of_means_divide_wrong", "22": "of_means_divide_wrong", "10": "of_means_divide_wrong"}),
        _mcq("of_c03", "fraction_of", 3, "C", ["of_means_divide_wrong"],
             "What is 5/6 of 24?", ["20", "4", "19", "30"], "20",
             "24÷6×5=20.", {"4": "of_means_divide_wrong", "19": "of_means_divide_wrong", "30": "of_means_divide_wrong"}),
        _mcq("of_a07", "fraction_of", 2, "A", ["of_means_divide_wrong"],
             "What is 2/3 of 27?", ["18", "9", "25", "12"], "18",
             "27÷3×2=18.", {"9": "of_means_divide_wrong", "25": "of_means_divide_wrong", "12": "of_means_divide_wrong"}),
        _mcq("of_a08", "fraction_of", 3, "A", ["of_means_divide_wrong"],
             "What is 4/7 of 21?", ["12", "3", "17", "28"], "12",
             "21÷7×4=12.", {"3": "of_means_divide_wrong", "17": "of_means_divide_wrong", "28": "of_means_divide_wrong"}),
    ]

    # --- mixed / improper ---
    items += [
        _mcq("mix_b01", "mixed_improper", 1, "B", ["ignore_denominator"],
             "Convert 7/4 to a mixed number.", ["1 3/4", "1 1/4", "3 1/4", "7/4"], "1 3/4",
             "7÷4=1 remainder 3.", {"1 1/4": "ignore_denominator", "3 1/4": "ignore_denominator"}),
        _mcq("mix_b02", "mixed_improper", 2, "B", ["ignore_denominator"],
             "Convert 2 1/5 to an improper fraction.", ["11/5", "10/5", "21/5", "3/5"], "11/5",
             "2×5+1=11.", {"10/5": "ignore_denominator", "21/5": "ignore_denominator", "3/5": "ignore_denominator"}),
        _mcq("mix_b03", "mixed_improper", 2, "B", ["ignore_denominator"],
             "Convert 11/3 to a mixed number.", ["3 2/3", "2 3/3", "4 1/3", "3 1/3"], "3 2/3",
             "11÷3=3 remainder 2.", {"4 1/3": "ignore_denominator", "3 1/3": "ignore_denominator"}),
        _mcq("mix_c01", "mixed_improper", 1, "C", ["ignore_denominator"],
             "Convert 9/4 to a mixed number.", ["2 1/4", "1 3/4", "2 3/4", "9/4"], "2 1/4",
             "9÷4=2 remainder 1.", {"1 3/4": "ignore_denominator", "2 3/4": "ignore_denominator"}),
        _mcq("mix_c02", "mixed_improper", 2, "C", ["ignore_denominator"],
             "Convert 1 2/3 to improper.", ["5/3", "3/3", "6/3", "2/3"], "5/3",
             "1×3+2=5.", {"3/3": "ignore_denominator", "6/3": "ignore_denominator", "2/3": "ignore_denominator"}),
        _mcq("mix_c03", "mixed_improper", 3, "C", ["ignore_denominator"],
             "Convert 17/5 to mixed.", ["3 2/5", "2 3/5", "4 1/5", "3 1/5"], "3 2/5",
             "17÷5=3 remainder 2.", {"2 3/5": "ignore_denominator", "4 1/5": "ignore_denominator", "3 1/5": "ignore_denominator"}),
        _mcq("mix_a06", "mixed_improper", 2, "A", ["ignore_denominator"],
             "Convert 3 1/4 to improper.", ["13/4", "12/4", "7/4", "31/4"], "13/4",
             "3×4+1=13.", {"12/4": "ignore_denominator", "7/4": "ignore_denominator", "31/4": "ignore_denominator"}),
        _mcq("mix_a07", "mixed_improper", 3, "A", ["ignore_denominator"],
             "Convert 14/6 to mixed in simplest form.", ["2 1/3", "2 2/6", "1 4/6", "2 4/6"], "2 1/3",
             "14/6=2 2/6=2 1/3.", {"2 2/6": "ignore_denominator", "1 4/6": "ignore_denominator", "2 4/6": "ignore_denominator"}),
    ]

    # Fix answer_sympy for yes/no/true/false/mixed
    for it in items:
        ans = str(it["answer"])
        if ans.lower() in {"yes", "no", "true", "false"} or " " in ans or "," in ans:
            it["answer_sympy"] = None
        elif ans.isdigit():
            it["answer_sympy"] = ans
    return items


def main() -> None:
    raw = json.loads(BANK.read_text(encoding="utf-8"))
    existing_ids = {x["id"] for x in raw["items"]}

    # Tag existing items as form A if missing
    for it in raw["items"]:
        it.setdefault("form", "A")
        it.setdefault("distractor_misconceptions", {})

    added = 0
    for it in new_items():
        if it["id"] in existing_ids:
            continue
        raw["items"].append(it)
        existing_ids.add(it["id"])
        added += 1

    raw["meta"]["version"] = 2
    raw["meta"]["title"] = "Year 5 fractions question bank (parallel forms A/B/C)"
    raw["meta"]["forms"] = {
        "A": "pretest / diagnostic preferred",
        "B": "immediate post preferred",
        "C": "delayed_24h preferred",
    }
    raw["meta"]["answer_format"] = "SymPy-parseable strings; fractions as a/b; distractor_misconceptions map choice→misconception"

    BANK.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    counts = {}
    forms = {}
    for it in raw["items"]:
        counts[it["skill"]] = counts.get(it["skill"], 0) + 1
        forms[it.get("form", "?")] = forms.get(it.get("form", "?"), 0) + 1
    print(f"Bank now {len(raw['items'])} items (+{added})")
    print("skills:", counts)
    print("forms:", forms)


if __name__ == "__main__":
    main()
