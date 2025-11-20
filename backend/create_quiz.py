from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Literal, Optional, Sequence, Set, Tuple

import pandas as pd


DATASET_PATH = Path(__file__).resolve().parent / "data/rag_sources/dbquiz_eval.csv"
DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parent / "data/generated_quiz.json"
DEFAULT_EXAM_TITLE = "은행 신입사원 평가"
DEFAULT_TOTAL_QUESTIONS = 60
CATEGORY_ORDER = [
    "금융영업",
    "상품개발 및 운용",
    "신용분석 및 리스크관리",
    "외환",
    "은행지식 및 관련법률",
    "하경은행",
]


@dataclass
class UserQuizProfile:
    """사용자 맞춤형 세트를 위한 데이터 컨테이너."""

    wrong_question_ids: List[int] = field(default_factory=list)
    recent_category_scores: Dict[str, float] = field(default_factory=dict)
    cumulative_category_scores: Dict[str, float] = field(default_factory=dict)


class QuizDataSource:
    """CSV 데이터에서 퀴즈 문항을 로딩하고 샘플링하는 유틸리티."""

    def __init__(self, dataset_path: Path = DATASET_PATH):
        self.dataset_path = dataset_path
        self.df = pd.read_csv(dataset_path, encoding="utf-8-sig")
        self.df["id"] = self.df["id"].astype(int)
        self.df_by_id = self.df.set_index("id")
        # CSV에 존재하는 카테고리와 기본 카테고리 순서를 조합
        existing_categories = [cat for cat in CATEGORY_ORDER if cat in self.df["category"].unique()]
        remaining = [
            cat for cat in self.df["category"].unique() if cat not in CATEGORY_ORDER
        ]
        self.categories: List[str] = existing_categories + remaining

    def _row_to_question(self, row: pd.Series) -> Dict:
        raw_sources = row.get("source_files")
        sources: List[str] = []
        if isinstance(raw_sources, str):
            for item in raw_sources.split(","):
                cleaned = item.strip()
                if cleaned:
                    sources.append(Path(cleaned).name)
        return {
            "q_id": int(row["id"]),
            "category_name": row["category"],
            "question": row["question"],
            "보기 1": row["choice1"],
            "보기 2": row["choice2"],
            "보기 3": row["choice3"],
            "보기 4": row["choice4"],
            "answer": row["answer"],
            "comment": row["comment"],
            "source_files": sources,
        }

    def sample_from_category(
        self,
        category: str,
        count: int,
        rng: random.Random,
        exclude_ids: Set[int],
    ) -> List[Dict]:
        if count <= 0:
            return []
        subset = self.df[self.df["category"] == category]
        subset = subset[~subset["id"].isin(exclude_ids)]
        available = len(subset)
        if available == 0:
            return []
        n = min(count, available)
        sampled = subset.sample(n=n, random_state=rng.randint(0, 2**32 - 1))
        return [self._row_to_question(row) for _, row in sampled.iterrows()]

    def sample_globally(self, count: int, rng: random.Random, exclude_ids: Set[int]) -> List[Dict]:
        if count <= 0:
            return []
        subset = self.df[~self.df["id"].isin(exclude_ids)]
        available = len(subset)
        if available == 0:
            return []
        n = min(count, available)
        sampled = subset.sample(n=n, random_state=rng.randint(0, 2**32 - 1))
        return [self._row_to_question(row) for _, row in sampled.iterrows()]

    def sample_from_ids(
        self,
        question_ids: Sequence[int],
        count: int,
        rng: random.Random,
        exclude_ids: Set[int],
    ) -> List[Dict]:
        if count <= 0 or not question_ids:
            return []
        candidates = [qid for qid in question_ids if qid in self.df_by_id.index and qid not in exclude_ids]
        if not candidates:
            return []
        n = min(count, len(candidates))
        sampled_ids = rng.sample(candidates, n)
        rows = self.df_by_id.loc[sampled_ids]
        if isinstance(rows, pd.Series):
            rows = rows.to_frame().T
        return [self._row_to_question(row) for _, row in rows.iterrows()]


class QuizBuilder:
    """랜덤/맞춤형 알고리즘을 구현한 클래스."""

    def __init__(self, data_source: QuizDataSource):
        self.source = data_source

    def generate_random_quiz(
        self,
        total_questions: int,
        seed: Optional[int] = None,
    ) -> Dict:
        rng = random.Random(seed)
        categories = self.source.categories or CATEGORY_ORDER
        base = total_questions // len(categories)
        remainder = total_questions % len(categories)

        questions: List[Dict] = []
        used_ids: Set[int] = set()
        category_summary: Dict[str, int] = defaultdict(int)

        for category in categories:
            batch = self.source.sample_from_category(category, base, rng, used_ids)
            questions.extend(batch)
            for item in batch:
                used_ids.add(item["q_id"])
                category_summary[item["category_name"]] += 1

        if remainder > 0:
            leftover = self.source.sample_globally(remainder, rng, used_ids)
            questions.extend(leftover)
            for item in leftover:
                used_ids.add(item["q_id"])
                category_summary[item["category_name"]] += 1

        return self._format_payload("random", questions, category_summary)

    def generate_custom_quiz(
        self,
        total_questions: int,
        profile: UserQuizProfile,
        seed: Optional[int] = None,
    ) -> Dict:
        rng = random.Random(seed)
        questions: List[Dict] = []
        used_ids: Set[int] = set()
        category_summary: Dict[str, int] = defaultdict(int)

        def add_batch(batch: List[Dict]) -> None:
            for item in batch:
                if item["q_id"] in used_ids:
                    continue
                questions.append(item)
                used_ids.add(item["q_id"])
                category_summary[item["category_name"]] += 1

        base_chunk = max(total_questions // 4, 1)

        # Step A: 최근 틀린 문항
        target = min(base_chunk, total_questions - len(questions))
        add_batch(self.source.sample_from_ids(profile.wrong_question_ids, target, rng, used_ids))

        # Step B: 최근 점수가 낮은 카테고리 2개
        remaining = total_questions - len(questions)
        if remaining > 0:
            b_categories = self._pick_lowest_categories(
                profile.recent_category_scores, desired=2, exclude=set()
            )
            add_batch(
                self._sample_from_category_set(
                    b_categories,
                    min(base_chunk, remaining),
                    rng,
                    used_ids,
                )
            )
        else:
            b_categories = []

        # Step C: 누계 점수가 낮은 카테고리 2개 (B에서 뽑은 카테고리는 제외)
        remaining = total_questions - len(questions)
        if remaining > 0:
            exclude_for_c = set(b_categories)
            c_categories = self._pick_lowest_categories(
                profile.cumulative_category_scores,
                desired=2,
                exclude=exclude_for_c,
            )
            add_batch(
                self._sample_from_category_set(
                    c_categories,
                    min(base_chunk, remaining),
                    rng,
                    used_ids,
                )
            )
        else:
            c_categories = []

        # Step D: 나머지 카테고리에서 채우기
        remaining = total_questions - len(questions)
        if remaining > 0:
            excluded = set(b_categories) | set(c_categories)
            fallback_categories = [cat for cat in self.source.categories if cat not in excluded]
            if not fallback_categories:
                fallback_categories = self.source.categories
            add_batch(self._sample_from_category_set(fallback_categories, remaining, rng, used_ids))

        # 부족분이 남으면 전체에서 랜덤 추출
        remaining = total_questions - len(questions)
        if remaining > 0:
            add_batch(self.source.sample_globally(remaining, rng, used_ids))

        return self._format_payload("custom", questions, category_summary)

    def _sample_from_category_set(
        self,
        categories: Sequence[str],
        total_needed: int,
        rng: random.Random,
        exclude_ids: Set[int],
    ) -> List[Dict]:
        if total_needed <= 0 or not categories:
            return []
        base = total_needed // len(categories)
        remainder = total_needed % len(categories)
        batch: List[Dict] = []
        for category in categories:
            batch.extend(self.source.sample_from_category(category, base, rng, exclude_ids))
        if remainder:
            extra_categories = rng.sample(list(categories), min(remainder, len(categories)))
            for category in extra_categories:
                batch.extend(self.source.sample_from_category(category, 1, rng, exclude_ids))
        return batch

    def _pick_lowest_categories(
        self,
        score_map: Dict[str, float],
        desired: int,
        exclude: Set[str],
    ) -> List[str]:
        available = [
            (cat, score_map.get(cat, float("inf")))
            for cat in self.source.categories
            if cat not in exclude
        ]
        available.sort(key=lambda item: item[1])
        selected = [cat for cat, _ in available[:desired]]
        if len(selected) < desired:
            for cat in self.source.categories:
                if cat not in exclude and cat not in selected:
                    selected.append(cat)
                if len(selected) == desired:
                    break
        return selected[:desired]

    def _format_payload(
        self,
        mode: Literal["random", "custom"],
        questions: List[Dict],
        category_summary: Dict[str, int],
    ) -> Dict:
        formatted = []
        for idx, item in enumerate(questions, start=1):
            formatted.append(
                {
                    "q_no": idx,
                    **item,
                }
            )
        return {
            "exam_info": {
                "title": DEFAULT_EXAM_TITLE,
                "mode": mode,
                "total_questions": len(formatted),
            },
            "category_summary": category_summary,
            "questions": formatted,
        }


def load_user_profile(path: Optional[Path]) -> UserQuizProfile:
    if path is None:
        raise ValueError("맞춤형 세트를 생성하려면 사용자 데이터를 제공해야 합니다.")
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return UserQuizProfile(
        wrong_question_ids=data.get("wrong_question_ids", []),
        recent_category_scores=data.get("recent_category_scores", {}),
        cumulative_category_scores=data.get("cumulative_category_scores", {}),
    )


def write_output(payload: Dict, destination: Optional[Path]) -> None:
    if destination is None:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="은행 연수원 퀴즈 세트 생성기")
    parser.add_argument("--mode", choices=["random", "custom"], default="random")
    parser.add_argument("--total-questions", type=int, default=DEFAULT_TOTAL_QUESTIONS)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument(
        "--user-stats",
        type=Path,
        default=None,
        help="맞춤형 세트를 위한 사용자 통계 JSON 경로",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_source = QuizDataSource(args.dataset)
    builder = QuizBuilder(data_source)
    if args.mode == "random":
        payload = builder.generate_random_quiz(args.total_questions, seed=args.seed)
    else:
        profile = load_user_profile(args.user_stats)
        payload = builder.generate_custom_quiz(args.total_questions, profile, seed=args.seed)
    write_output(payload, args.output)
    print(
        f"[{payload['exam_info']['mode']}] "
        f"{payload['exam_info']['total_questions']}문항 생성 → {args.output}"
    )


if __name__ == "__main__":
    main()
