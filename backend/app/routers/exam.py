"""
시험 관련 API 라우터
시험 응시, 채점, 결과 조회, 학습 추천 등
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List, Dict, Optional
from pydantic import BaseModel

from app.database import get_session
from app.models.user import User
from app.services.exam_service import ExamScoringService
from app.services.feedback_service import FeedbackService
from app.utils.auth import get_current_user

router = APIRouter(prefix="/exam", tags=["Exam"])


class ExamAnswerRequest(BaseModel):
    """시험 답안 제출 요청"""
    answers: Dict[str, str]  # {q_id: user_answer}


class ExamAnswerResponse(BaseModel):
    """시험 답안 제출 응답"""
    exam_score_id: int
    total_score: float
    section_scores: Dict[str, Dict]
    grade: str
    weak_topics: List[str]
    strong_topics: List[str]
    feedback: Optional[str] = None


class LearningRecommendation(BaseModel):
    """학습 추천 응답"""
    topic_name: str
    category: str
    priority_score: float
    is_studied: bool
    weak_areas: List[str]


@router.post("/submit", response_model=ExamAnswerResponse)
async def submit_exam(
    request: ExamAnswerRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    시험 답안 제출 및 채점
    """
    try:
        exam_service = ExamScoringService(session)
        
        # 시험 채점
        result = exam_service.grade_exam(current_user.id, request.answers)
        
        # AI 피드백 생성
        feedback_service = FeedbackService(session)
        feedback_result = await feedback_service.generate_exam_feedback(
            result["exam_score_id"], 
            current_user.name
        )
        
        return ExamAnswerResponse(
            exam_score_id=result["exam_score_id"],
            total_score=result["total_score"],
            section_scores=result["section_scores"],
            grade=result["grade"],
            weak_topics=result["weak_topics"],
            strong_topics=result["strong_topics"],
            feedback=feedback_result["feedback"]
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"시험 채점 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/questions")
async def get_exam_questions(
    section_id: Optional[int] = None,
    session: Session = Depends(get_session)
):
    """
    시험 문제 조회
    """
    try:
        exam_service = ExamScoringService(session)
        questions = exam_service.get_exam_questions(section_id)
        
        return {
            "questions": questions,
            "total_count": len(questions)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"시험 문제 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/recommendations", response_model=List[LearningRecommendation])
async def get_learning_recommendations(
    limit: int = 5,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    개인화된 학습 추천 목록 조회
    """
    try:
        feedback_service = FeedbackService(session)
        recommendations = feedback_service.get_learning_recommendations(current_user.id, limit)
        
        return [
            LearningRecommendation(**rec) for rec in recommendations
        ]
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"학습 추천 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/study-complete")
async def mark_study_complete(
    topic_name: str,
    duration: int = 0,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    학습 완료 표시
    """
    try:
        exam_service = ExamScoringService(session)
        success = exam_service.mark_topic_studied(current_user.id, topic_name, duration)
        
        if success:
            return {"message": f"'{topic_name}' 학습 완료로 표시되었습니다."}
        else:
            raise HTTPException(
                status_code=404,
                detail="해당 학습 주제를 찾을 수 없습니다."
            )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"학습 완료 처리 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/sections")
async def get_exam_sections(session: Session = Depends(get_session)):
    """
    시험 섹션 정보 조회
    """
    return {
        "sections": [
            {
                "section_id": 1,
                "section_name": "은행업무",
                "description": "예금, 대출, 외환 등 기본 은행업무에 대한 이해",
                "total_questions": 20
            },
            {
                "section_id": 2,
                "section_name": "상품지식",
                "description": "ISA, IRP, 파생결합증권 등 금융상품에 대한 이해",
                "total_questions": 20
            },
            {
                "section_id": 3,
                "section_name": "고객응대",
                "description": "고객 서비스, 민원 처리, 고객 언어 등 응대 스킬",
                "total_questions": 20
            },
            {
                "section_id": 4,
                "section_name": "법규준수",
                "description": "자금세탁방지, 소비자 보호, 내부통제 등 법규 준수",
                "total_questions": 20
            },
            {
                "section_id": 5,
                "section_name": "IT활용",
                "description": "핀테크, 디지털 금융, 보안 등 IT 관련 지식",
                "total_questions": 20
            },
            {
                "section_id": 6,
                "section_name": "영업실적",
                "description": "KPI, 고객 관리, 데이터 기반 영업 등 성과 관리",
                "total_questions": 20
            }
        ]
    }


@router.get("/results/{exam_score_id}")
async def get_exam_result(
    exam_score_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    특정 시험 결과 상세 조회
    """
    try:
        from app.models.mentor import ExamScore, ExamResult
        
        # 시험 점수 조회
        exam_score = session.get(ExamScore, exam_score_id)
        if not exam_score or exam_score.mentee_id != current_user.id:
            raise HTTPException(
                status_code=404,
                detail="시험 결과를 찾을 수 없습니다."
            )
        
        # 상세 결과 조회
        results = session.exec(
            session.query(ExamResult)
            .where(ExamResult.exam_score_id == exam_score_id)
            .order_by(ExamResult.q_id)
        ).all()
        
        return {
            "exam_score": {
                "id": exam_score.id,
                "exam_name": exam_score.exam_name,
                "exam_date": exam_score.exam_date.isoformat(),
                "total_score": exam_score.total_score,
                "grade": exam_score.grade,
                "feedback": exam_score.feedback
            },
            "detailed_results": [
                {
                    "q_id": result.q_id,
                    "user_answer": result.user_answer,
                    "is_correct": result.is_correct,
                    "learning_topic": result.learning_topic
                }
                for result in results
            ]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"시험 결과 조회 중 오류가 발생했습니다: {str(e)}"
        )
