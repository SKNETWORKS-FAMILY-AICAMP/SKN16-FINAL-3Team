from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import List, Sequence

import pandas as pd


DATASET_PATH = Path(__file__).resolve().parent / "data/rag_sources/dbquiz_eval.csv"
DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parent / "data/final_quiz.json"
DEFAULT_EXAM_TITLE = "최종평가"
FIXED_CATEGORY_ORDER: List[str] = [
    "금융영업",
    "상품개발 및 운용",
    "신용분석 및 리스크관리",
    "외환",
    "은행지식 및 관련법률",
    "하경은행",
]


def _get_target_categories(
    df: pd.DataFrame,
    requested: Sequence[str] | None,
    per_category: int,
) -> List[str]:
    counts = df["category"].value_counts()
    categories = list(requested) if requested else FIXED_CATEGORY_ORDER

    missing = [cat for cat in categories if cat not in counts]
    if missing:
        raise ValueError(f"Unknown categories requested: {missing}")

    shortages = {
        cat: counts[cat] for cat in categories if counts[cat] < per_category
    }
    if shortages:
        raise ValueError(
            "Not enough questions per category: "
            + ", ".join(f"{cat} ({count})" for cat, count in shortages.items())
        )

    return categories


def _sample_category_questions(
    df: pd.DataFrame,
    category: str,
    per_category: int,
    rng: random.Random,
) -> List[dict]:
    subset = df[df["category"] == category]
    sampled = subset.sample(
        n=per_category,
        random_state=rng.randint(0, 2**32 - 1),
    )
    questions: List[dict] = []
    for _, row in sampled.iterrows():
        questions.append(
            {
                "q_id": int(row["id"]),
                "question": row["question"],
                "보기 1": row["choice1"],
                "보기 2": row["choice2"],
                "보기 3": row["choice3"],
                "보기 4": row["choice4"],
                "answer": row["answer"],
                "comment": row["comment"],
            }
        )
    return questions


def build_quiz_json(
    *,
    dataset_path: Path = DATASET_PATH,
    per_category: int = 10,
    categories: Sequence[str] | None = None,
    seed: int | None = None,
    exam_title: str = DEFAULT_EXAM_TITLE,
) -> dict:
    df = pd.read_csv(dataset_path, encoding="utf-8-sig")
    rng = random.Random(seed)
    target_categories = _get_target_categories(df, categories, per_category)

    category_blocks = []
    for cat in target_categories:
        questions = _sample_category_questions(df, cat, per_category, rng)
        rng.shuffle(questions)
        category_blocks.append(
            {
                "category_name": cat,
                "questions": questions,
            }
        )

    q_counter = 1
    for block in category_blocks:
        updated_questions = []
        for question in block["questions"]:
            updated_questions.append(
                {
                    "q_no": q_counter,
                    **question,
                }
            )
            q_counter += 1
        block["questions"] = updated_questions

    exam = {
        "exam_info": {
            "title": exam_title,
            "total_questions": len(category_blocks) * per_category,
            "total_categories": len(category_blocks),
        },
        "category": category_blocks,
    }
    return exam


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a balanced quiz JSON file.",
    )
    parser.add_argument("--per-category", type=int, default=10)
    parser.add_argument(
        "--categories",
        nargs="+",
        default=None,
        help="Optional list of categories to include. Defaults to the fixed exam order.",
    )
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--title", type=str, default=DEFAULT_EXAM_TITLE)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DATASET_PATH,
        help="Path to the source CSV.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Destination JSON path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    exam_json = build_quiz_json(
        dataset_path=args.dataset,
        per_category=args.per_category,
        categories=args.categories,
        seed=args.seed,
        exam_title=args.title,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(exam_json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"Wrote {exam_json['exam_info']['total_questions']} questions "
        f"across {exam_json['exam_info']['total_categories']} categories "
        f"to {args.output}"
    )


if __name__ == "__main__":
    main()
