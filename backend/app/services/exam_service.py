"""
시험 채점 및 분석 서비스
실제 시험 데이터를 기반으로 채점, 분석, 피드백 생성
"""
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import Counter, defaultdict
from sqlmodel import Session, select

from app.models.mentor import ExamQuestion, ExamResult, ExamScore, LearningTopic
from app.models.user import User


class ExamScoringService:
    """시험 채점 서비스"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def grade_exam(self, user_id: int, exam_answers: Dict[str, str]) -> Dict:
        """
        시험 채점 및 결과 저장
        
        Args:
            user_id: 사용자 ID
            exam_answers: {q_id: user_answer} 형태의 답안
        
        Returns:
            채점 결과 딕셔너리
        """
        # 모든 문제 조회
        questions = self.session.exec(select(ExamQuestion)).all()
        question_map = {q.q_id: q for q in questions}
        
        # 채점 결과 계산
        scoring_results = self._calculate_scores(exam_answers, question_map)
        
        # 시험 점수 저장
        exam_score = self._save_exam_score(user_id, scoring_results)
        
        # 상세 결과 저장
        self._save_detailed_results(user_id, exam_score.id, exam_answers, question_map)
        
        # 취약점 분석 및 학습 주제 생성
        self._analyze_weaknesses(user_id, scoring_results)
        
        return {
            "exam_score_id": exam_score.id,
            "total_score": scoring_results["total_score"],
            "section_scores": scoring_results["section_scores"],
            "grade": scoring_results["grade"],
            "weak_topics": scoring_results["weak_topics"],
            "strong_topics": scoring_results["strong_topics"]
        }
    
    def _calculate_scores(self, exam_answers: Dict[str, str], question_map: Dict) -> Dict:
        """채점 결과 계산"""
        section_scores = defaultdict(lambda: {"correct": 0, "total": 0, "questions": []})
        total_correct = 0
        total_questions = len(exam_answers)
        weak_topics = []
        strong_topics = []
        
        # 문제별 채점
        for q_id, user_answer in exam_answers.items():
            if q_id not in question_map:
                continue
                
            question = question_map[q_id]
            is_correct = user_answer.strip() == question.correct_answer.strip()
            
            # 섹션별 점수 계산
            section_name = question.section_name
            section_scores[section_name]["total"] += 1
            section_scores[section_name]["questions"].append({
                "q_id": q_id,
                "question": question.question,
                "user_answer": user_answer,
                "correct_answer": question.correct_answer,
                "is_correct": is_correct,
                "learning_topic": question.learning_topic,
                "difficulty": question.difficulty
            })
            
            if is_correct:
                section_scores[section_name]["correct"] += 1
                total_correct += 1
            else:
                # 틀린 문제의 학습 주제 수집
                weak_topics.append(question.learning_topic)
        
        # 섹션별 점수 계산
        final_section_scores = {}
        for section_name, data in section_scores.items():
            score = (data["correct"] / data["total"]) * 100 if data["total"] > 0 else 0
            final_section_scores[section_name] = {
                "score": round(score, 1),
                "correct": data["correct"],
                "total": data["total"],
                "questions": data["questions"]
            }
            
            # 강점/취약점 분류 (80점 기준)
            if score >= 80:
                strong_topics.extend([q["learning_topic"] for q in data["questions"] if q["is_correct"]])
            else:
                weak_topics.extend([q["learning_topic"] for q in data["questions"] if not q["is_correct"]])
        
        # 전체 점수 계산
        total_score = (total_correct / total_questions) * 100 if total_questions > 0 else 0
        
        # 등급 계산
        grade = self._calculate_grade(total_score)
        
        return {
            "total_score": round(total_score, 1),
            "total_correct": total_correct,
            "total_questions": total_questions,
            "section_scores": final_section_scores,
            "grade": grade,
            "weak_topics": list(set(weak_topics)),  # 중복 제거
            "strong_topics": list(set(strong_topics))
        }
    
    def _calculate_grade(self, score: float) -> str:
        """등급 계산"""
        if score >= 90:
            return "A+"
        elif score >= 85:
            return "A"
        elif score >= 80:
            return "B+"
        elif score >= 75:
            return "B"
        elif score >= 70:
            return "C+"
        elif score >= 65:
            return "C"
        else:
            return "D"
    
    def _save_exam_score(self, user_id: int, scoring_results: Dict) -> ExamScore:
        """시험 점수 저장"""
        exam_score = ExamScore(
            mentee_id=user_id,
            exam_name="은행 신입사원 연수원 종합평가 시험",
            exam_date=datetime.utcnow(),
            score_data=json.dumps(scoring_results["section_scores"], ensure_ascii=False),
            total_score=scoring_results["total_score"],
            grade=scoring_results["grade"]
        )
        
        self.session.add(exam_score)
        self.session.commit()
        self.session.refresh(exam_score)
        
        return exam_score
    
    def _save_detailed_results(self, user_id: int, exam_score_id: int, 
                             exam_answers: Dict[str, str], question_map: Dict):
        """상세 시험 결과 저장"""
        for q_id, user_answer in exam_answers.items():
            if q_id not in question_map:
                continue
                
            question = question_map[q_id]
            is_correct = user_answer.strip() == question.correct_answer.strip()
            
            result = ExamResult(
                mentee_id=user_id,
                exam_score_id=exam_score_id,
                q_id=q_id,
                user_answer=user_answer,
                is_correct=is_correct,
                learning_topic=question.learning_topic
            )
            
            self.session.add(result)
        
        self.session.commit()
    
    def _analyze_weaknesses(self, user_id: int, scoring_results: Dict):
        """취약점 분석 및 학습 주제 생성"""
        # 기존 학습 주제 삭제
        existing_topics = self.session.exec(
            select(LearningTopic).where(LearningTopic.mentee_id == user_id)
        ).all()
        
        for topic in existing_topics:
            self.session.delete(topic)
        
        # 취약점 기반 학습 주제 생성
        weak_topics = scoring_results["weak_topics"]
        topic_counts = Counter(weak_topics)
        
        for topic_name, count in topic_counts.items():
            # 카테고리 결정 (간단한 매핑)
            category = self._determine_category(topic_name)
            
            # 우선순위 점수 계산 (틀린 횟수 기반)
            priority_score = min(100, count * 20)  # 틀린 횟수당 20점
            
            learning_topic = LearningTopic(
                mentee_id=user_id,
                topic_name=topic_name,
                topic_category=category,
                priority_score=priority_score,
                weak_areas=json.dumps([topic_name], ensure_ascii=False)
            )
            
            self.session.add(learning_topic)
        
        self.session.commit()
    
    def _determine_category(self, topic_name: str) -> str:
        """학습 주제의 카테고리 결정"""
        if any(keyword in topic_name for keyword in ["예금", "대출", "외환", "여신"]):
            return "은행업무"
        elif any(keyword in topic_name for keyword in ["ISA", "IRP", "ELS", "ELD", "보험", "연금"]):
            return "상품지식"
        elif any(keyword in topic_name for keyword in ["응대", "고객", "민원"]):
            return "고객응대"
        elif any(keyword in topic_name for keyword in ["자금세탁", "AML", "KYC", "소비자보호", "내부통제"]):
            return "법규준수"
        elif any(keyword in topic_name for keyword in ["핀테크", "IT", "디지털", "보안", "AI"]):
            return "IT활용"
        elif any(keyword in topic_name for keyword in ["KPI", "성과", "고객관리", "영업"]):
            return "영업실적"
        else:
            return "기타"
    
    def get_exam_questions(self, section_id: Optional[int] = None) -> List[Dict]:
        """시험 문제 조회"""
        query = select(ExamQuestion)
        
        if section_id:
            query = query.where(ExamQuestion.section_id == section_id)
        
        questions = self.session.exec(query).all()
        
        result = []
        for q in questions:
            result.append({
                "q_id": q.q_id,
                "question": q.question,
                "question_type": q.question_type,
                "options": json.loads(q.options),
                "difficulty": q.difficulty,
                "learning_topic": q.learning_topic,
                "section_id": q.section_id,
                "section_name": q.section_name
            })
        
        return result
    
    def get_learning_recommendations(self, user_id: int, limit: int = 5) -> List[Dict]:
        """학습 추천 목록 조회"""
        topics = self.session.exec(
            select(LearningTopic)
            .where(LearningTopic.mentee_id == user_id)
            .order_by(LearningTopic.priority_score.desc())
            .limit(limit)
        ).all()
        
        recommendations = []
        for topic in topics:
            recommendations.append({
                "topic_name": topic.topic_name,
                "category": topic.topic_category,
                "priority_score": topic.priority_score,
                "is_studied": topic.is_studied,
                "weak_areas": json.loads(topic.weak_areas)
            })
        
        return recommendations
    
    def mark_topic_studied(self, user_id: int, topic_name: str, duration: int = 0):
        """학습 완료 표시"""
        topic = self.session.exec(
            select(LearningTopic).where(
                LearningTopic.mentee_id == user_id,
                LearningTopic.topic_name == topic_name
            )
        ).first()
        
        if topic:
            topic.is_studied = True
            topic.study_date = datetime.utcnow()
            topic.study_duration = duration
            topic.updated_at = datetime.utcnow()
            
            self.session.add(topic)
            self.session.commit()
            
            return True
        
        return False

