"""
멘토-멘티 매칭 서비스 (N차원 분류)
"""
from __future__ import annotations

from datetime import date, datetime
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, delete
from sqlmodel import Session, select

from app.models.matching import MatchingReport, MatchingResult
from app.models.training_center import TrainingCenterRecord
from app.models.user import User, UserRole
from app.models.mentor import ExamScore, ExamType


class LearningHistoryNotInitializedError(Exception):
    """Raised when mentees do not have initial learning history scores."""


class MatchingService:
    """N차원 분류 기반 멘토-멘티 매칭 서비스"""

    # 가중치: 팀 > 약점-강점 > 커리어/거주지/입사년도/연령 > 취미 > 전공 > 성별
    # 밸런스 조정: 분포를 중앙으로 몰기 위해 연속형 요소 비중 확장
    WEIGHT_TEAM = 2.5
    WEIGHT_WEAKNESS_STRENGTH = 2.0
    WEIGHT_CAREER = 1.2
    WEIGHT_CITY = 1.0
    WEIGHT_JOIN_YEAR = 1.0
    WEIGHT_BIRTH_YEAR = 0.8
    WEIGHT_HOBBY = 0.8
    WEIGHT_MAJOR = 0.5
    WEIGHT_GENDER = 0.2

    MAX_MENTEES_PER_MENTOR = 2

    def __init__(self, session: Session):
        self.session = session

    def match_all(self, cohort_date: Optional[date] = None) -> Dict[str, Any]:
        """모든 멘티와 멘토를 매칭"""
        mentee_query = select(TrainingCenterRecord).where(
            TrainingCenterRecord.employee_type == "mentee"
        )
        mentor_query = select(TrainingCenterRecord).where(
            TrainingCenterRecord.employee_type == "mentor"
        )
        if cohort_date:
            mentee_query = mentee_query.where(
                TrainingCenterRecord.cohort_date == cohort_date
            )
            mentor_query = mentor_query.where(
                TrainingCenterRecord.cohort_date == cohort_date
            )

        mentees = self.session.exec(mentee_query).all()
        mentors = self.session.exec(mentor_query).all()

        if not mentees or not mentors:
            return {
                "message": "멘티 또는 멘토가 없습니다.",
                "matched_count": 0,
                "overall_score": 0.0,
            }

        # 학습 이력(초기 성적) 선행 여부 확인
        self._ensure_learning_history_initialized(mentees)

        cohort_label = mentees[0].cohort_label if mentees else None

        # 기존 결과 정리 (해당 cohort)
        mentee_ids = [m.id for m in mentees]
        if mentee_ids:
            self.session.exec(
                delete(MatchingResult).where(
                    MatchingResult.mentee_id.in_(mentee_ids)
                )
            )
            self.session.commit()

        # 매칭 수행
        matches: List[MatchingResult] = []
        team_statistics: Dict[str, Dict[str, Any]] = {}
        mentor_assignment_counts = defaultdict(int)
        user_pairs: List[Tuple[int, int]] = []

        for mentee in mentees:
            best_match = self._find_best_mentor(
                mentee,
                mentors,
                mentor_assignment_counts,
                self.MAX_MENTEES_PER_MENTOR,
            )
            if best_match:
                match_result = MatchingResult(
                    mentee_id=mentee.id,
                    mentor_id=best_match["mentor"].id,
                    total_score=best_match["total_score"],
                    team_score=best_match["team_score"],
                    city_score=best_match["city_score"],
                    hobby_score=best_match["hobby_score"],
                    weakness_strength_score=best_match["weakness_strength_score"],
                    career_score=best_match["career_score"],
                    major_score=best_match["major_score"],
                    matching_details=best_match["details"],
                    is_active=True,
                )
                self.session.add(match_result)
                matches.append(match_result)
                mentor_assignment_counts[best_match["mentor"].id] += 1

                # 팀별 통계 업데이트
                team = mentee.team
                if team not in team_statistics:
                    team_statistics[team] = {
                        "matched_count": 0,
                        "total_score": 0.0,
                        "team_score": 0.0,
                        "city_score": 0.0,
                        "hobby_score": 0.0,
                        "weakness_strength_score": 0.0,
                        "career_score": 0.0,
                        "major_score": 0.0,
                    }
                team_statistics[team]["matched_count"] += 1
                team_statistics[team]["total_score"] += best_match["total_score"]
                team_statistics[team]["team_score"] += best_match["team_score"]
                team_statistics[team]["city_score"] += best_match["city_score"]
                team_statistics[team]["hobby_score"] += best_match["hobby_score"]
                team_statistics[team]["weakness_strength_score"] += best_match["weakness_strength_score"]
                team_statistics[team]["career_score"] += best_match["career_score"]
                team_statistics[team]["major_score"] += best_match["major_score"]

        self.session.commit()

        # 전체 평균 점수 계산
        overall_score = (
            sum(m.total_score for m in matches) / len(matches) if matches else 0.0
        )

        # 팀별 평균 점수 계산
        for team in team_statistics:
            stats = team_statistics[team]
            count = stats["matched_count"]
            if count > 0:
                stats["average_total_score"] = stats["total_score"] / count
                stats["average_team_score"] = stats["team_score"] / count
                stats["average_city_score"] = stats["city_score"] / count
                stats["average_hobby_score"] = stats["hobby_score"] / count
                stats["average_weakness_strength_score"] = stats["weakness_strength_score"] / count
                stats["average_career_score"] = stats["career_score"] / count
                stats["average_major_score"] = stats["major_score"] / count

        # 리포트 생성
        report = MatchingReport(
            report_name=f"{cohort_label or '전체'} 매칭 리포트 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            total_mentees=len(mentees),
            total_mentors=len(mentors),
            total_matched=len(matches),
            overall_score=overall_score,
            team_statistics=team_statistics,
            report_data={
                "cohort": {
                    "label": cohort_label,
                    "date": cohort_date.isoformat() if cohort_date else None,
                },
                "matches": [
                    {
                        "mentee_id": m.mentee_id,
                        "mentor_id": m.mentor_id,
                        "total_score": m.total_score,
                        "team_score": m.team_score,
                        "city_score": m.city_score,
                        "hobby_score": m.hobby_score,
                        "weakness_strength_score": m.weakness_strength_score,
                        "career_score": m.career_score,
                        "major_score": m.major_score,
                    }
                    for m in matches
                ]
            },
        )
        self.session.add(report)
        self.session.commit()

        # 매칭 결과를 멘토-멘티 관계에 자동 반영
        user_pairs = self._update_mentor_mentee_relations(matches)

        return {
            "message": "매칭 완료",
            "matched_count": len(matches),
            "total_mentees": len(mentees),
            "total_mentors": len(mentors),
            "overall_score": overall_score,
            "team_statistics": team_statistics,
            "report_id": report.id,
        }
    
    def _update_mentor_mentee_relations(
        self, matches: List[MatchingResult]
    ) -> List[Tuple[int, int]]:
        """매칭 결과를 멘토-멘티 관계에 자동 반영"""
        from app.models.mentor import MentorMenteeRelation
        from app.models.user import User
        
        # 기존 활성 관계 비활성화
        if not matches:
            return []

        mentee_record_ids = [match.mentee_id for match in matches]
        mentee_records = {
            record.id: record
            for record in self.session.exec(
                select(TrainingCenterRecord).where(
                    TrainingCenterRecord.id.in_(mentee_record_ids)
                )
            ).all()
        }
        employee_numbers = [
            record.employee_number
            for record in mentee_records.values()
            if record
        ]
        mentee_users = self.session.exec(
            select(User).where(User.employee_number.in_(employee_numbers))
        ).all()
        mentee_user_map = {user.employee_number: user for user in mentee_users}

        user_pairs: List[Tuple[int, int]] = []

        # 비활성화 대상 관계 한정
        mentee_ids_for_deactivation = [
            user.id for user in mentee_users if user
        ]
        if mentee_ids_for_deactivation:
            existing_relations = self.session.exec(
                select(MentorMenteeRelation).where(
                    MentorMenteeRelation.mentee_id.in_(mentee_ids_for_deactivation)
                )
            ).all()
            for relation in existing_relations:
                relation.is_active = False

        for match in matches:
            mentee_record = mentee_records.get(match.mentee_id)
            mentor_record = self.session.get(TrainingCenterRecord, match.mentor_id)
            
            if not mentee_record or not mentor_record:
                continue
            
            # User 찾기 (employee_number로)
            mentee_user = mentee_user_map.get(mentee_record.employee_number)
            mentor_user = self.session.exec(
                select(User).where(User.employee_number == mentor_record.employee_number)
            ).first()
            
            if not mentee_user or not mentor_user:
                continue
            
            # 기존 관계 확인
            existing = self.session.exec(
                select(MentorMenteeRelation).where(
                    MentorMenteeRelation.mentee_id == mentee_user.id,
                    MentorMenteeRelation.is_active == True
                )
            ).first()
            
            if existing:
                # 기존 관계 업데이트
                existing.mentor_id = mentor_user.id
                existing.is_active = True
                existing.matched_at = datetime.utcnow()
            else:
                # 새 관계 생성
                new_relation = MentorMenteeRelation(
                    mentor_id=mentor_user.id,
                    mentee_id=mentee_user.id,
                    matched_at=datetime.utcnow(),
                    is_active=True,
                    notes=f"매칭 시스템 자동 생성 (점수: {match.total_score:.2f})"
                )
                self.session.add(new_relation)
            user_pairs.append((mentor_user.id, mentee_user.id))
        
        self.session.commit()
        return user_pairs

    def _ensure_learning_history_initialized(
        self, mentees: List[TrainingCenterRecord]
    ) -> None:
        """모든 멘티 계정에 초기 학습 이력(초기 점수)이 존재하는지 확인."""
        if not mentees:
            return

        employee_numbers = {
            mentee.employee_number for mentee in mentees if mentee.employee_number
        }
        if not employee_numbers:
            raise LearningHistoryNotInitializedError(
                "멘티 사번 정보가 없어 학습 이력 상태를 확인할 수 없습니다. 연수원 데이터를 다시 동기화한 뒤 시도해주세요."
            )

        mentee_users = self.session.exec(
            select(User).where(
                User.employee_number.in_(employee_numbers),
                User.role == UserRole.MENTEE,
                User.is_active == True,  # noqa: E712
            )
        ).all()

        if not mentee_users:
            raise LearningHistoryNotInitializedError(
                "멘티 사용자 계정이 아직 생성되지 않았습니다. 연수원 연동에서 '계정 생성'과 학습 이력의 '초기 성적 생성'을 완료한 뒤 매칭을 실행해주세요."
            )

        user_ids = [user.id for user in mentee_users]
        scored_user_ids = set(
            self.session.exec(
                select(ExamScore.mentee_id).where(
                    ExamScore.mentee_id.in_(user_ids),
                    ExamScore.exam_type == ExamType.BEGINNING,
                )
            ).scalars().all()
        )

        missing_users = [user for user in mentee_users if user.id not in scored_user_ids]
        if missing_users:
            preview = ", ".join(
                f"{user.name or '미등록'}({user.employee_number or user.email})"
                for user in missing_users[:5]
            )
            additional = (
                f" (예: {preview})" if preview else ""
            )
            raise LearningHistoryNotInitializedError(
                f"학습 이력(초기 평가) 성적이 없는 멘티가 {len(missing_users)}명 있습니다.{additional} "
                "관리자 대시보드 > 학습 이력 탭에서 '성적 생성'을 먼저 실행한 뒤 다시 시도해주세요."
            )

    def _find_best_mentor(
        self,
        mentee: TrainingCenterRecord,
        mentors: List[TrainingCenterRecord],
        mentor_assignment_counts: Dict[int, int],
        max_per_mentor: int,
    ) -> Optional[Dict[str, Any]]:
        """멘티에 가장 적합한 멘토 찾기"""
        best_match = None
        best_score = -1.0

        for mentor in mentors:
            if mentor_assignment_counts[mentor.id] >= max_per_mentor:
                continue

            # 매칭 점수 계산
            team_score = self._calculate_team_score(mentee.team, mentor.team)
            city_score = self._calculate_city_score(mentee.city, mentor.city)

            # 취미 매칭 (취미1 또는 취미2가 일치하면 점수 부여)
            hobby_score = 0.0
            mentee_hobbies = {mentee.hobby1, mentee.hobby2}
            mentor_hobbies = {mentor.hobby1, mentor.hobby2}
            mentee_hobbies.discard(None)
            mentor_hobbies.discard(None)

            if mentee_hobbies and mentor_hobbies:
                common_hobbies = mentee_hobbies.intersection(mentor_hobbies)
                if common_hobbies:
                    hobby_score = len(common_hobbies) / max(
                        len(mentee_hobbies), len(mentor_hobbies)
                    )

            # 약점-강점 매칭 (멘티의 약점 분야를 멘토가 잘하는지)
            weakness_strength_score = self._calculate_weakness_strength_match(mentee, mentor)

            # 커리어 경로 매칭
            career_score = 1.0 if mentee.career_goal == mentor.career_goal else 0.0

            # 전공 매칭
            major_score = 1.0 if mentee.major == mentor.major else 0.0

            # 입사년도/연령/성별 매칭
            join_year_score = self._calculate_join_year_score(mentee, mentor)
            birth_year_score = self._calculate_birth_year_score(mentee, mentor)
            gender_score = self._calculate_gender_score(mentee, mentor)

            # 가중 평균 점수 계산
            total_weight = (
                self.WEIGHT_TEAM 
                + self.WEIGHT_CITY 
                + self.WEIGHT_HOBBY 
                + self.WEIGHT_WEAKNESS_STRENGTH
                + self.WEIGHT_CAREER
                + self.WEIGHT_MAJOR
                + self.WEIGHT_JOIN_YEAR
                + self.WEIGHT_BIRTH_YEAR
                + self.WEIGHT_GENDER
            )
            
            total_score = (
                team_score * self.WEIGHT_TEAM
                + city_score * self.WEIGHT_CITY
                + hobby_score * self.WEIGHT_HOBBY
                + weakness_strength_score * self.WEIGHT_WEAKNESS_STRENGTH
                + career_score * self.WEIGHT_CAREER
                + major_score * self.WEIGHT_MAJOR
                + join_year_score * self.WEIGHT_JOIN_YEAR
                + birth_year_score * self.WEIGHT_BIRTH_YEAR
                + gender_score * self.WEIGHT_GENDER
            ) / total_weight

            if total_score > best_score:
                best_score = total_score
                best_match = {
                    "mentor": mentor,
                    "total_score": total_score,
                    "team_score": team_score,
                    "city_score": city_score,
                    "hobby_score": hobby_score,
                    "weakness_strength_score": weakness_strength_score,
                    "career_score": career_score,
                    "major_score": major_score,
                    "join_year_score": join_year_score,
                    "birth_year_score": birth_year_score,
                    "gender_score": gender_score,
                    "details": {
                        "mentee_team": mentee.team,
                        "mentor_team": mentor.team,
                        "mentee_city": mentee.city,
                        "mentor_city": mentor.city,
                        "mentee_hobbies": [h for h in [mentee.hobby1, mentee.hobby2] if h],
                        "mentor_hobbies": [h for h in [mentor.hobby1, mentor.hobby2] if h],
                        "mentee_major": mentee.major,
                        "mentor_major": mentor.major,
                        "mentee_career_goal": mentee.career_goal,
                        "mentor_career_goal": mentor.career_goal,
                        "mentee_join_year": mentee.join_year,
                        "mentor_join_year": mentor.join_year,
                        "mentee_birth": mentee.birth.isoformat() if mentee.birth else None,
                        "mentor_birth": mentor.birth.isoformat() if mentor.birth else None,
                        "mentee_gender": mentee.gender,
                        "mentor_gender": mentor.gender,
                    },
                }

        return best_match

    def _calculate_weakness_strength_match(
        self, mentee: TrainingCenterRecord, mentor: TrainingCenterRecord
    ) -> float:
        """멘티의 약점 분야를 멘토가 잘하는지 계산
        
        멘티의 가장 낮은 점수 분야에서 멘토가 높은 점수를 받았으면 높은 점수 부여
        """
        if not mentee.section_scores or not mentor.section_scores:
            return 0.0
        
        # 멘티의 가장 약한 분야 2개 찾기
        mentee_sections = sorted(
            mentee.section_scores.items(), 
            key=lambda x: x[1]
        )[:2]  # 가장 낮은 2개 분야
        
        if not mentee_sections:
            return 0.0
        
        # 멘토가 해당 분야에서 얼마나 잘하는지 확인
        weakness_match_scores = []
        for section, mentee_score in mentee_sections:
            mentor_score = mentor.section_scores.get(section, 0)
            # 멘토 점수가 8점 이상이면 1.0, 6점 이상이면 0.7, 4점 이상이면 0.4
            if mentor_score >= 8:
                weakness_match_scores.append(1.0)
            elif mentor_score >= 6:
                weakness_match_scores.append(0.7)
            elif mentor_score >= 4:
                weakness_match_scores.append(0.4)
            else:
                weakness_match_scores.append(0.0)
        
        return sum(weakness_match_scores) / len(weakness_match_scores) if weakness_match_scores else 0.0

    # ------------------------------------------------------------------ #
    # 유사도 계산 헬퍼 (연속형/부분 일치 점수)
    # ------------------------------------------------------------------ #
    def _calculate_team_score(self, mentee_team: str, mentor_team: str) -> float:
        if mentee_team == mentor_team:
            return 1.0
        mentee_group = self._extract_team_group(mentee_team)
        mentor_group = self._extract_team_group(mentor_team)
        if mentee_group and mentee_group == mentor_group:
            return 0.75
        return 0.4

    def _extract_team_group(self, team: Optional[str]) -> Optional[str]:
        if not team:
            return None
        if "창구" in team:
            return "창구"
        if "VIP" in team:
            return "VIP"
        if "외환" in team:
            return "외환"
        if "디지털" in team:
            return "디지털"
        if "기업" in team:
            return "기업"
        return team

    def _calculate_city_score(self, mentee_city: Optional[str], mentor_city: Optional[str]) -> float:
        if not mentee_city or not mentor_city:
            return 0.5
        if mentee_city == mentor_city:
            return 1.0
        if mentee_city[:2] == mentor_city[:2]:
            return 0.7
        return 0.4

    def _calculate_join_year_score(
        self, mentee: TrainingCenterRecord, mentor: TrainingCenterRecord
    ) -> float:
        if not mentee.join_year or not mentor.join_year:
            return 0.6
        gap = mentee.join_year - mentor.join_year
        if gap <= 0:
            return 0.45
        if gap >= 10:
            return 1.0
        return 0.45 + (gap / 10) * 0.55  # 0.45~1.0 범위

    def _calculate_birth_year_score(
        self, mentee: TrainingCenterRecord, mentor: TrainingCenterRecord
    ) -> float:
        if not mentee.birth or not mentor.birth:
            return 0.6
        mentee_age = self._calculate_age(mentee.birth)
        mentor_age = self._calculate_age(mentor.birth)
        age_gap = abs(mentee_age - mentor_age)
        if age_gap <= 3:
            return 1.0
        if age_gap >= 15:
            return 0.4
        return min(1.0, max(0.4, 1 - (age_gap - 3) / 15))

    def _calculate_gender_score(
        self, mentee: TrainingCenterRecord, mentor: TrainingCenterRecord
    ) -> float:
        if not mentee.gender or not mentor.gender:
            return 0.8
        return 1.0 if mentee.gender == mentor.gender else 0.8

    def _calculate_age(self, birth_date) -> int:
        today = datetime.now().date()
        return today.year - birth_date.year - (
            (today.month, today.day) < (birth_date.month, birth_date.day)
        )

    def get_latest_report(self) -> Optional[MatchingReport]:
        """최신 매칭 리포트 조회"""
        return self.session.exec(
            select(MatchingReport).order_by(MatchingReport.report_date.desc()).limit(1)
        ).first()

    def get_matching_results(
        self, page: int = 1, page_size: int = 20
    ) -> Dict[str, Any]:
        """매칭 결과 조회 (페이징)"""
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)

        query = (
            select(MatchingResult)
            .where(MatchingResult.is_active == True)
            .order_by(MatchingResult.total_score.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        results = self.session.exec(query).all()

        total = self.session.exec(
            select(func.count())
            .select_from(MatchingResult)
            .where(MatchingResult.is_active == True)
        ).one()

        return {
            "results": [
                {
                    "id": r.id,
                    "mentee_id": r.mentee_id,
                    "mentor_id": r.mentor_id,
                    "total_score": r.total_score,
                    "team_score": r.team_score,
                    "city_score": r.city_score,
                    "hobby_score": r.hobby_score,
                    "weakness_strength_score": r.weakness_strength_score,
                    "career_score": r.career_score,
                    "major_score": r.major_score,
                    "matched_at": r.matched_at.isoformat(),
                }
                for r in results
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

