"""
시험 결과 분석 및 AI 피드백 생성 서비스
시험 점수를 바탕으로 개인화된 피드백과 학습 추천 생성
"""
import json
from typing import Dict, List, Optional
from sqlmodel import Session, select
from app.models.mentor import ExamScore, LearningTopic, ExamResult
from app.services.rag_service import RAGService


class FeedbackService:
    """시험 결과 피드백 서비스"""
    
    def __init__(self, session: Session):
        self.session = session
        self.rag_service = RAGService(session)
    
    async def generate_exam_feedback(self, exam_score_id: int, user_name: str) -> Dict:
        """
        시험 결과 기반 개인화 피드백 생성
        
        Args:
            exam_score_id: 시험 점수 ID
            user_name: 사용자 이름
        
        Returns:
            피드백 딕셔너리
        """
        # 시험 점수 조회
        exam_score = self.session.get(ExamScore, exam_score_id)
        if not exam_score:
            raise ValueError("시험 점수를 찾을 수 없습니다.")
        
        # 시험 결과 상세 조회
        exam_results = self.session.exec(
            select(ExamResult).where(ExamResult.exam_score_id == exam_score_id)
        ).all()
        
        # 점수 데이터 파싱
        section_scores = json.loads(exam_score.score_data) if exam_score.score_data else {}
        
        # 취약점 분석
        weak_topics = self._analyze_weaknesses(exam_results)
        strong_topics = self._analyze_strengths(exam_results)
        
        # RAG로 관련 학습 자료 검색
        learning_materials = []
        if weak_topics:
            for topic in weak_topics[:3]:  # 상위 3개 취약점만
                materials = await self.rag_service.similarity_search(topic, k=2)
                learning_materials.extend(materials)
        
        # AI 피드백 생성
        feedback = await self._generate_ai_feedback(
            user_name=user_name,
            total_score=exam_score.total_score,
            grade=exam_score.grade,
            section_scores=section_scores,
            weak_topics=weak_topics,
            strong_topics=strong_topics,
            learning_materials=learning_materials
        )
        
        # 피드백 저장
        exam_score.feedback = feedback
        self.session.add(exam_score)
        self.session.commit()
        
        return {
            "feedback": feedback,
            "total_score": exam_score.total_score,
            "grade": exam_score.grade,
            "section_scores": section_scores,
            "weak_topics": weak_topics,
            "strong_topics": strong_topics,
            "learning_recommendations": [
                {
                    "topic": topic,
                    "priority": "high" if topic in weak_topics[:3] else "medium"
                }
                for topic in weak_topics[:5]
            ]
        }
    
    def _analyze_weaknesses(self, exam_results: List[ExamResult]) -> List[str]:
        """취약점 분석"""
        wrong_topics = []
        
        for result in exam_results:
            if not result.is_correct:
                wrong_topics.append(result.learning_topic)
        
        # 빈도순으로 정렬
        from collections import Counter
        topic_counts = Counter(wrong_topics)
        
        return [topic for topic, count in topic_counts.most_common()]
    
    def _analyze_strengths(self, exam_results: List[ExamResult]) -> List[str]:
        """강점 분석"""
        correct_topics = []
        
        for result in exam_results:
            if result.is_correct:
                correct_topics.append(result.learning_topic)
        
        # 빈도순으로 정렬
        from collections import Counter
        topic_counts = Counter(correct_topics)
        
        return [topic for topic, count in topic_counts.most_common()]
    
    async def _generate_ai_feedback(
        self,
        user_name: str,
        total_score: float,
        grade: str,
        section_scores: Dict,
        weak_topics: List[str],
        strong_topics: List[str],
        learning_materials: List[Dict]
    ) -> str:
        """AI 피드백 생성"""
        
        # 섹션별 점수 분석
        section_analysis = self._analyze_section_scores(section_scores)
        
        # 학습 자료 컨텍스트 구성
        context = "\n\n".join([
            f"[{doc.get('title', '학습 자료')}]\n{doc.get('content', '')[:500]}..."
            for doc in learning_materials[:3]
        ])
        
        # 피드백 프롬프트 구성
        prompt = f"""당신은 은행 신입사원을 위한 따뜻하고 격려하는 AI 멘토입니다. 🐻

신입사원 정보:
- 이름: {user_name}
- 전체 점수: {total_score}점
- 등급: {grade}

섹션별 점수:
{self._format_section_scores(section_scores)}

강점 영역:
{', '.join(strong_topics[:3]) if strong_topics else '없음'}

취약 영역:
{', '.join(weak_topics[:3]) if weak_topics else '없음'}

관련 학습 자료:
{context if context else '기본 학습 자료를 활용하세요.'}

위 정보를 바탕으로 다음 형식으로 피드백을 작성하세요:

📊 **시험 결과 분석**
(축하 메시지로 시작하며 전체 점수와 등급 언급)

✅ **잘하셨어요!**
(강점 파트 2-3가지 구체적으로 칭찬)

⚠️ **함께 보완해요**
(취약 파트 설명 + 공감하며 격려)

🎯 **맞춤 학습 추천**
1. [주제명] - 예상 시간: 15분
   → 핵심: 구체적인 학습 포인트
   
2. [주제명] - 예상 시간: 20분
   → 핵심: 구체적인 학습 포인트

3. [주제명] - 예상 시간: 10분
   → 핵심: 구체적인 학습 포인트

💪 **응원합니다!**
(격려 메시지로 마무리)

답변은 친절하고 격려하는 톤으로 작성하세요.
이모지를 적절히 사용해 가독성을 높이세요.
길이는 500-800자 정도로 작성하세요."""

        # GPT API 호출
        return self.rag_service._call_gpt(prompt)
    
    def _analyze_section_scores(self, section_scores: Dict) -> Dict:
        """섹션별 점수 분석"""
        analysis = {
            "excellent": [],  # 90점 이상
            "good": [],       # 80-89점
            "fair": [],       # 70-79점
            "needs_improvement": []  # 70점 미만
        }
        
        for section, data in section_scores.items():
            score = data.get('score', 0)
            if score >= 90:
                analysis["excellent"].append(section)
            elif score >= 80:
                analysis["good"].append(section)
            elif score >= 70:
                analysis["fair"].append(section)
            else:
                analysis["needs_improvement"].append(section)
        
        return analysis
    
    def _format_section_scores(self, section_scores: Dict) -> str:
        """섹션별 점수를 문자열로 포맷팅"""
        formatted = []
        for section, data in section_scores.items():
            score = data.get('score', 0)
            correct = data.get('correct', 0)
            total = data.get('total', 0)
            formatted.append(f"- {section}: {score}점 ({correct}/{total})")
        
        return "\n".join(formatted)
    
    def get_learning_recommendations(self, user_id: int, limit: int = 5) -> List[Dict]:
        """개인화된 학습 추천 목록 조회"""
        # 사용자의 최근 시험 점수 조회
        recent_exam = self.session.exec(
            select(ExamScore)
            .where(ExamScore.mentee_id == user_id)
            .order_by(ExamScore.exam_date.desc())
            .limit(1)
        ).first()
        
        if not recent_exam:
            return []
        
        # 취약점 기반 학습 주제 조회
        learning_topics = self.session.exec(
            select(LearningTopic)
            .where(LearningTopic.mentee_id == user_id)
            .order_by(LearningTopic.priority_score.desc())
            .limit(limit)
        ).all()
        
        recommendations = []
        for topic in learning_topics:
            recommendations.append({
                "topic_name": topic.topic_name,
                "category": topic.topic_category,
                "priority_score": topic.priority_score,
                "is_studied": topic.is_studied,
                "estimated_time": self._estimate_study_time(topic.topic_name),
                "weak_areas": json.loads(topic.weak_areas) if topic.weak_areas else []
            })
        
        return recommendations
    
    def _estimate_study_time(self, topic_name: str) -> int:
        """학습 주제별 예상 학습 시간 계산 (분)"""
        # 주제별 난이도에 따른 학습 시간 추정
        time_mapping = {
            "예금상품의 이해": 15,
            "여신상품의 분류": 20,
            "외환업무 기초": 18,
            "통합자산관리상품": 25,
            "파생결합증권": 30,
            "보험상품 이해": 20,
            "고객응대 기본": 15,
            "민원 처리": 20,
            "고객 언어": 12,
            "자금세탁방지": 25,
            "소비자 보호": 18,
            "내부통제": 22,
            "디지털 금융 혁신": 20,
            "금융 보안": 18,
            "AI와 자동화": 15,
            "KPI와 성과 관리": 20,
            "고객 관리 전략": 18,
            "데이터 기반 영업": 15
        }
        
        return time_mapping.get(topic_name, 20)  # 기본값 20분

