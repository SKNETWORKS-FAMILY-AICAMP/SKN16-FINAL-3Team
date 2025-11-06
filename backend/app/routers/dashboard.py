"""
대시보드 API 라우터
멘토/멘티별 대시보드 데이터 제공
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func
from typing import List, Dict
from collections import Counter
import json

from app.database import get_session
from app.models.user import User, UserRead, UserRole
from app.models.mentor import (
    MentorMenteeRelation, ExamScore, ChatHistory,
    MentorDashboard, MenteeDashboard, LearningProgress, Feedback, FeedbackComment,
    SimulationRecording
)
from app.utils.auth import get_current_user, get_current_active_mentor, get_current_active_admin

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/mentee", response_model=MenteeDashboard)
async def get_mentee_dashboard(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    멘티 대시보드 데이터
    - 담당 멘토 정보
    - 시험 점수
    - 학습 진행도
    - 최근 채팅 기록
    """
    # 담당 멘토 정보 조회
    mentor_info = None
    relation_statement = select(MentorMenteeRelation).where(
        MentorMenteeRelation.mentee_id == current_user.id,
        MentorMenteeRelation.is_active == True
    )
    relation = session.exec(relation_statement).first()
    
    if relation:
        mentor_statement = select(User).where(User.id == relation.mentor_id)
        mentor = session.exec(mentor_statement).first()
        if mentor:
            mentor_info = {
                "id": mentor.id,
                "name": mentor.name,
                "team": mentor.team,
                "mbti": mentor.mbti,
                "interests": mentor.interests,
                "hobbies": mentor.hobbies,
                "encouragement_message": mentor.encouragement_message,
                "photo_url": mentor.photo_url
            }
    
    # 시험 점수 조회
    exam_statement = (
        select(ExamScore)
        .where(ExamScore.mentee_id == current_user.id)
        .order_by(ExamScore.exam_date.desc())
    )
    exams = session.exec(exam_statement).all()
    
    exam_scores = []
    for exam in exams:
        exam_scores.append({
            "id": exam.id,
            "exam_name": exam.exam_name,
            "exam_date": exam.exam_date.isoformat(),
            "score_data": json.loads(exam.score_data) if exam.score_data else {},
            "total_score": exam.total_score,
            "grade": exam.grade,
            "feedback": exam.feedback
        })
    
    # 학습 진행도
    chat_count_statement = select(func.count(ChatHistory.id)).where(
        ChatHistory.user_id == current_user.id
    )
    total_chats = session.exec(chat_count_statement).first() or 0
    
    # 최근 대화 주제 추출
    recent_chats_statement = (
        select(ChatHistory)
        .where(ChatHistory.user_id == current_user.id)
        .order_by(ChatHistory.created_at.desc())
        .limit(20)
    )
    recent_chats_data = session.exec(recent_chats_statement).all()
    
    recent_topics = []
    recent_chats = []
    for chat in recent_chats_data[:5]:  # 최근 5개만
        recent_chats.append({
            "user_message": chat.user_message,
            "bot_response": chat.bot_response,
            "created_at": chat.created_at.isoformat()
        })
    
    # 간단한 주제 추출 (첫 50자)
    for chat in recent_chats_data:
        if chat.user_message:
            topic = chat.user_message[:50]
            recent_topics.append(topic)
    
    learning_progress = LearningProgress(
        mentee_id=current_user.id,
        total_chats=total_chats,
        documents_accessed=0,  # 추후 구현
        recent_topics=recent_topics[:10],
        progress_percentage=min(100, total_chats * 5)  # 간단한 진행도 계산
    )
    
    # 6가지 지표 성적 데이터 (실제 시험 점수에서 추출)
    performance_scores = {
        "banking": 0,  # 은행업무
        "product_knowledge": 0,  # 상품지식
        "customer_service": 0,  # 고객응대
        "compliance": 0,  # 법규준수
        "it_usage": 0,  # IT활용
        "sales_performance": 0  # 영업실적
    }
    
    # 실제 시험 점수에서 성과 지표 추출
    if exams:
        latest_exam = exams[0]  # 가장 최근 시험
        if latest_exam.score_data:
            score_data = json.loads(latest_exam.score_data)
            performance_scores = {
                "banking": score_data.get("은행업무", 0),
                "product_knowledge": score_data.get("상품지식", 0),
                "customer_service": score_data.get("고객응대", 0),
                "compliance": score_data.get("법규준수", 0),
                "it_usage": score_data.get("IT활용", 0),
                "sales_performance": score_data.get("영업실적", 0)
            }
    
    # 최근 피드백 조회
    feedbacks_statement = (
        select(Feedback)
        .where(Feedback.mentee_id == current_user.id)
        .order_by(Feedback.created_at.desc())
        .limit(5)
    )
    recent_feedbacks = session.exec(feedbacks_statement).all()
    
    feedback_list = []
    for feedback in recent_feedbacks:
        mentor_statement = select(User).where(User.id == feedback.mentor_id)
        mentor = session.exec(mentor_statement).first()
        
        feedback_list.append({
            "id": feedback.id,
            "feedback_text": feedback.feedback_text,
            "feedback_type": feedback.feedback_type,
            "color_section": feedback.color_section,
            "is_read": feedback.is_read,
            "created_at": feedback.created_at.isoformat(),
            "mentor_name": mentor.name if mentor else "알 수 없음"
        })
    
    return MenteeDashboard(
        mentee_id=current_user.id,
        mentor_info=mentor_info,
        exam_scores=exam_scores,
        learning_progress=learning_progress,
        recent_chats=recent_chats,
        performance_scores=performance_scores,
        recent_feedbacks=feedback_list
    )


@router.get("/mentee/recordings")
async def get_mentee_recordings(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    멘티의 시뮬레이션 녹화 목록 조회 (멘티만 접근 가능)
    """
    # 권한 체크: 멘티만 접근 가능
    if current_user.role != "mentee":
        raise HTTPException(
            status_code=403,
            detail="멘티만 접근할 수 있습니다."
        )
    
    # 녹화 기록 조회
    recordings_statement = (
        select(SimulationRecording)
        .where(SimulationRecording.mentee_id == current_user.id)
        .order_by(SimulationRecording.created_at.desc())
    )
    recordings = session.exec(recordings_statement).all()
    
    recordings_list = []
    for recording in recordings:
        recordings_list.append({
            "id": recording.id,
            "simulation_id": recording.simulation_id,
            "persona_id": recording.persona_id,
            "situation_id": recording.situation_id,
            "video_url": recording.video_url,
            "filename": recording.filename,
            "file_size": recording.file_size,
            "duration": recording.duration,
            "created_at": recording.created_at.isoformat()
        })
    
    return {
        "recordings": recordings_list,
        "total_count": len(recordings_list)
    }


# ===== 시험 결과 반영 API =====
@router.post("/mentee/{mentee_id}/exam-results")
async def submit_exam_results(
    mentee_id: int,
    request: dict,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """사용자 시험 정오표(문항코드: 0/1)로 6가지 성과 지표 점수를 산출하고 ExamScore에 저장"""
    # 권한: 본인 또는 멘토/관리자만 허용 (간단히 본인 허용)
    if current_user.role != "admin" and current_user.id != mentee_id:
        # 멘토 권한 허용: 멘토-멘티 관계 존재 여부 확인
        rel = session.exec(
            select(MentorMenteeRelation).where(
                MentorMenteeRelation.mentor_id == current_user.id,
                MentorMenteeRelation.mentee_id == mentee_id,
                MentorMenteeRelation.is_active == True,
            )
        ).first() if current_user.role == "mentor" else None
        if not rel:
            raise HTTPException(status_code=403, detail="권한이 없습니다")

    results: dict = request.get("results", {})
    if not isinstance(results, dict) or not results:
        raise HTTPException(status_code=400, detail="results가 필요합니다")

    # 지표별 집계
    buckets = {
        "BO": "banking",
        "PK": "product_knowledge",
        "CS": "customer_service",
        "CO": "compliance",
        "IT": "it_usage",
        "SP": "sales_performance",
    }
    correct_counts = {v: 0 for v in buckets.values()}
    total_counts = {v: 0 for v in buckets.values()}
    wrong_codes: list[str] = []

    for code, value in results.items():
        if not isinstance(code, str):
            continue
        prefix = code[:2].upper()
        bucket = buckets.get(prefix)
        if not bucket:
            continue
        total_counts[bucket] += 1
        if int(value) == 1:
            correct_counts[bucket] += 1
        else:
            wrong_codes.append(code)

    # 점수 산출 (문항당 5점, 20문항 가정)
    performance_scores = {
        k: min(100, correct_counts[k] * 5) for k in correct_counts
    }

    # 학습 권고 생성 - 데이터 파일에서 주제/해설을 가져와 간략 권고 구성
    recommendations: list[str] = []
    try:
        import json, os
        data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "bank_training_exam.json")
        materials_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "learning_materials_for_RAG.txt")
        topics_map = {}
        if os.path.exists(data_path):
            with open(data_path, "r", encoding="utf-8") as f:
                bank_data = json.load(f)
                # 기대 구조: {section: {questions: [{code, topic, explanation}]}}
                def walk(node):
                    if isinstance(node, dict):
                        if "questions" in node and isinstance(node["questions"], list):
                            for q in node["questions"]:
                                code = q.get("code") or q.get("id") or q.get("문제번호")
                                if code:
                                    topics_map[str(code)] = {
                                        "topic": q.get("topic") or q.get("학습주제") or "",
                                        "explanation": q.get("explanation") or q.get("해설") or "",
                                    }
                        for v in node.values():
                            walk(v)
                    elif isinstance(node, list):
                        for v in node:
                            walk(v)
                walk(bank_data)

        # 보조 학습자료(텍스트) 로드
        materials_text = ""
        if os.path.exists(materials_path):
            try:
                with open(materials_path, "r", encoding="utf-8") as mf:
                    materials_text = mf.read()
            except Exception:
                materials_text = ""

        def find_snippet(keyword: str) -> str:
            if not materials_text or not keyword:
                return ""
            # 단순 키워드 매칭으로 앞뒤 문장 일부 추출
            idx = materials_text.find(keyword)
            if idx == -1:
                return ""
            start = max(0, idx - 120)
            end = min(len(materials_text), idx + 180)
            snippet = materials_text[start:end].replace('\n', ' ').strip()
            return snippet

        for code in wrong_codes[:10]:  # 너무 길어지지 않게 최대 10개
            info = topics_map.get(code, {})
            topic = (info.get("topic") or "").strip()
            expl = (info.get("explanation") or "문제 해설을 복습하세요").strip()
            extra = find_snippet(topic) if topic else ""
            if extra:
                recommendations.append(f"{code}: {topic} - {expl} | 참고: {extra}")
            else:
                recommendations.append(f"{code}: {topic or '관련 주제 확인 필요'} - {expl}")
    except Exception:
        # 파일이 없거나 파싱 실패 시 코드만 표시
        recommendations = [f"{c}: 복습 필요" for c in wrong_codes[:10]]

    # ExamScore 저장
    import json
    total = sum(performance_scores.values()) / 6
    grade = "A+" if total >= 90 else "A" if total >= 85 else "B+" if total >= 80 else "B" if total >= 75 else "C+" if total >= 70 else "C"
    exam_score = ExamScore(
        mentee_id=mentee_id,
        exam_name="지표 평가",
        exam_date=func.now(),
        score_data=json.dumps({
            "은행업무": performance_scores["banking"],
            "상품지식": performance_scores["product_knowledge"],
            "고객응대": performance_scores["customer_service"],
            "법규준수": performance_scores["compliance"],
            "IT활용": performance_scores["it_usage"],
            "영업실적": performance_scores["sales_performance"],
        }, ensure_ascii=False),
        total_score=round(total, 1),
        grade=grade,
        feedback="\n".join(recommendations)
    )
    session.add(exam_score)
    session.commit()

    return {
        "message": "시험 결과가 반영되었습니다",
        "performance_scores": performance_scores,
        "recommendations": recommendations
    }


@router.get("/mentor", response_model=MentorDashboard)
async def get_mentor_dashboard(
    current_user: User = Depends(get_current_active_mentor),
    session: Session = Depends(get_session)
):
    """
    멘토 대시보드 데이터
    - 담당 멘티 목록
    - 멘티별 성적
    - 자주 묻는 질문 키워드
    """
    # 담당 멘티 목록
    relation_statement = select(MentorMenteeRelation).where(
        MentorMenteeRelation.mentor_id == current_user.id,
        MentorMenteeRelation.is_active == True
    )
    relations = session.exec(relation_statement).all()
    
    mentees = []
    mentee_scores = {}
    all_questions = []
    
    for relation in relations:
        # 멘티 정보
        mentee_statement = select(User).where(User.id == relation.mentee_id)
        mentee = session.exec(mentee_statement).first()
        
        if mentee:
            # 멘티 기본 정보
            mentee_info = {
                "id": mentee.id,
                "name": mentee.name,
                "email": mentee.email,
                "team": mentee.team,
                "mbti": mentee.mbti,
                "interests": mentee.interests,
                "photo_url": mentee.photo_url
            }
            
            # 멘티의 최근 시험 점수
            exam_statement = (
                select(ExamScore)
                .where(ExamScore.mentee_id == mentee.id)
                .order_by(ExamScore.exam_date.desc())
                .limit(1)
            )
            recent_exam = session.exec(exam_statement).first()
            
            if recent_exam:
                mentee_info["recent_score"] = recent_exam.total_score
                mentee_info["recent_exam"] = recent_exam.exam_name
                mentee_scores[mentee.name] = {
                    "total_score": recent_exam.total_score,
                    "score_data": json.loads(recent_exam.score_data) if recent_exam.score_data else {}
                }
                
                # 개별 성과 지표 추가 (멘토 대시보드용)
                score_data = json.loads(recent_exam.score_data) if recent_exam.score_data else {}
                mentee_info["performance_scores"] = {
                    "banking": score_data.get("은행업무", recent_exam.total_score),
                    "product_knowledge": score_data.get("상품지식", recent_exam.total_score),
                    "customer_service": score_data.get("고객응대", recent_exam.total_score),
                    "compliance": score_data.get("법규준수", recent_exam.total_score),
                    "it_usage": score_data.get("IT활용", recent_exam.total_score),
                    "sales_performance": score_data.get("영업실적", recent_exam.total_score)
                }
            
            # 멘티의 채팅 통계
            chat_count_statement = select(func.count(ChatHistory.id)).where(
                ChatHistory.user_id == mentee.id
            )
            chat_count = session.exec(chat_count_statement).first() or 0
            mentee_info["chat_count"] = chat_count
            
            mentees.append(mentee_info)
            
            # 멘티의 질문 수집 (워드클라우드용)
            chat_statement = (
                select(ChatHistory)
                .where(ChatHistory.user_id == mentee.id)
                .order_by(ChatHistory.created_at.desc())
                .limit(50)
            )
            chats = session.exec(chat_statement).all()
            for chat in chats:
                all_questions.append(chat.user_message)
    
    # 자주 묻는 질문 키워드 추출 (간단한 버전)
    frequent_questions = _extract_keywords(all_questions)
    
    return MentorDashboard(
        mentor_id=current_user.id,
        mentees=mentees,
        frequent_questions=frequent_questions,
        mentee_scores=mentee_scores
    )


@router.post("/assign-mentor")
async def assign_mentor(
    request: dict,
    current_user: User = Depends(get_current_active_mentor),
    session: Session = Depends(get_session)
):
    """
    멘토-멘티 매칭 (관리자/멘토가 수행)
    """
    mentee_id = request.get("mentee_id")
    mentor_id = request.get("mentor_id")
    notes = request.get("notes", "")
    # 멘티와 멘토 확인
    mentee_statement = select(User).where(User.id == mentee_id)
    mentee = session.exec(mentee_statement).first()
    
    mentor_statement = select(User).where(User.id == mentor_id)
    mentor = session.exec(mentor_statement).first()
    
    if not mentee or not mentor:
        raise HTTPException(status_code=404, detail="User not found")
    
    if mentee.role != "mentee":
        raise HTTPException(status_code=400, detail="User is not a mentee")
    
    if mentor.role not in ["mentor", "admin"]:
        raise HTTPException(status_code=400, detail="User is not a mentor")
    
    # 기존 관계 비활성화
    existing_statement = select(MentorMenteeRelation).where(
        MentorMenteeRelation.mentee_id == mentee_id,
        MentorMenteeRelation.is_active == True
    )
    existing_relations = session.exec(existing_statement).all()
    for rel in existing_relations:
        rel.is_active = False
        session.add(rel)
    
    # 새 관계 생성
    relation = MentorMenteeRelation(
        mentor_id=mentor_id,
        mentee_id=mentee_id,
        is_active=True,
        notes=notes
    )
    session.add(relation)
    session.commit()
    
    return {"message": "Mentor assigned successfully"}


@router.post("/exam-score")
async def add_exam_score(
    mentee_id: int,
    exam_name: str,
    score_data: Dict,
    total_score: float,
    grade: str = None,
    current_user: User = Depends(get_current_active_mentor),
    session: Session = Depends(get_session)
):
    """
    시험 점수 추가 (멘토/관리자가 수행)
    """
    from datetime import datetime
    
    exam = ExamScore(
        mentee_id=mentee_id,
        exam_name=exam_name,
        exam_date=datetime.utcnow(),
        score_data=json.dumps(score_data, ensure_ascii=False),
        total_score=total_score,
        grade=grade
    )
    
    session.add(exam)
    session.commit()
    session.refresh(exam)
    
    return {"message": "Exam score added successfully", "exam_id": exam.id}


def _extract_keywords(questions: List[str], top_k: int = 20) -> List[Dict]:
    """
    질문에서 키워드 추출 (간단한 버전)
    실제로는 형태소 분석 등을 사용하면 더 좋습니다.
    """
    # 간단한 공백 기반 단어 분리
    words = []
    for question in questions:
        words.extend(question.split())
    
    # 단어 빈도 계산
    word_counts = Counter(words)
    
    # 상위 키워드 반환
    frequent_words = word_counts.most_common(top_k)
    
    return [
        {"word": word, "count": count}
        for word, count in frequent_words
    ]


@router.post("/feedback")
async def create_feedback(
    request: dict,
    current_user: User = Depends(get_current_active_mentor),
    session: Session = Depends(get_session)
):
    """
    멘토가 멘티에게 피드백 전송
    """
    mentee_id = request.get("mentee_id")
    feedback_text = request.get("feedback_text")
    feedback_type = request.get("feedback_type", "general")
    
    if not mentee_id or not feedback_text:
        raise HTTPException(
            status_code=400,
            detail="mentee_id와 feedback_text는 필수입니다."
        )
    # 멘토-멘티 관계 확인
    relation_statement = select(MentorMenteeRelation).where(
        MentorMenteeRelation.mentor_id == current_user.id,
        MentorMenteeRelation.mentee_id == mentee_id,
        MentorMenteeRelation.is_active == True
    )
    relation = session.exec(relation_statement).first()
    
    if not relation:
        raise HTTPException(
            status_code=403,
            detail="해당 멘티와의 관계가 없거나 비활성화되어 있습니다."
        )
    
    # 피드백 생성
    feedback = Feedback(
        mentor_id=current_user.id,
        mentee_id=mentee_id,
        feedback_text=feedback_text,
        feedback_type=feedback_type
    )
    
    session.add(feedback)
    session.commit()
    session.refresh(feedback)
    
    return {
        "message": "피드백이 성공적으로 전송되었습니다.",
        "feedback_id": feedback.id
    }


@router.get("/feedback/{mentee_id}")
async def get_feedbacks_for_mentee(
    mentee_id: int,
    current_user: User = Depends(get_current_active_mentor),
    session: Session = Depends(get_session)
):
    """
    특정 멘티에 대한 피드백 목록 조회 (멘토용)
    """
    # 멘토-멘티 관계 확인
    relation_statement = select(MentorMenteeRelation).where(
        MentorMenteeRelation.mentor_id == current_user.id,
        MentorMenteeRelation.mentee_id == mentee_id,
        MentorMenteeRelation.is_active == True
    )
    relation = session.exec(relation_statement).first()
    
    if not relation:
        raise HTTPException(
            status_code=403,
            detail="해당 멘티와의 관계가 없거나 비활성화되어 있습니다."
        )
    
    # 피드백 목록 조회
    feedbacks_statement = (
        select(Feedback)
        .where(Feedback.mentee_id == mentee_id)
        .order_by(Feedback.created_at.desc())
    )
    feedbacks = session.exec(feedbacks_statement).all()
    
    return [
        {
            "id": feedback.id,
            "feedback_text": feedback.feedback_text,
            "feedback_type": feedback.feedback_type,
            "is_read": feedback.is_read,
            "created_at": feedback.created_at.isoformat(),
            "read_at": feedback.read_at.isoformat() if feedback.read_at else None
        }
        for feedback in feedbacks
    ]


@router.get("/mentee/feedbacks")
async def get_mentee_feedbacks(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    멘티가 받은 피드백 목록 조회
    """
    # 멘티가 받은 피드백 조회
    feedbacks_statement = (
        select(Feedback)
        .where(Feedback.mentee_id == current_user.id)
        .order_by(Feedback.created_at.desc())
        .limit(10)
    )
    feedbacks = session.exec(feedbacks_statement).all()
    
    # 멘토 정보도 함께 조회
    feedback_list = []
    for feedback in feedbacks:
        mentor_statement = select(User).where(User.id == feedback.mentor_id)
        mentor = session.exec(mentor_statement).first()
        
        feedback_list.append({
            "id": feedback.id,
            "feedback_text": feedback.feedback_text,
            "feedback_type": feedback.feedback_type,
            "color_section": feedback.color_section,
            "is_read": feedback.is_read,
            "created_at": feedback.created_at.isoformat(),
            "mentor_name": mentor.name if mentor else "알 수 없음",
            "mentor_team": mentor.team if mentor else None
        })
    
    return feedback_list


@router.put("/feedback/{feedback_id}/read")
async def mark_feedback_as_read(
    feedback_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    피드백을 읽음으로 표시
    """
    feedback_statement = select(Feedback).where(
        Feedback.id == feedback_id,
        Feedback.mentee_id == current_user.id
    )
    feedback = session.exec(feedback_statement).first()
    
    if not feedback:
        raise HTTPException(
            status_code=404,
            detail="피드백을 찾을 수 없습니다."
        )
    
    feedback.is_read = True
    feedback.read_at = datetime.utcnow()
    
    session.add(feedback)
    session.commit()
    
    return {"message": "피드백을 읽음으로 표시했습니다."}


# ============ 피드백 댓글 API ============

@router.post("/feedback/{feedback_id}/comments")
async def create_comment(
    feedback_id: int,
    request: dict,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    피드백에 댓글 작성 (멘토 또는 멘티)
    """
    comment_text = request.get("comment_text")
    
    if not comment_text:
        raise HTTPException(
            status_code=400,
            detail="comment_text는 필수입니다."
        )
    
    # 피드백 존재 여부 확인
    feedback_statement = select(Feedback).where(Feedback.id == feedback_id)
    feedback = session.exec(feedback_statement).first()
    
    if not feedback:
        raise HTTPException(
            status_code=404,
            detail="피드백을 찾을 수 없습니다."
        )
    
    # 권한 확인: 피드백의 멘토 또는 멘티만 댓글 작성 가능
    if current_user.id not in [feedback.mentor_id, feedback.mentee_id]:
        raise HTTPException(
            status_code=403,
            detail="이 피드백에 댓글을 작성할 권한이 없습니다."
        )
    
    # 댓글 생성
    comment = FeedbackComment(
        feedback_id=feedback_id,
        user_id=current_user.id,
        comment_text=comment_text
    )
    
    session.add(comment)
    session.commit()
    session.refresh(comment)
    
    return {
        "message": "댓글이 성공적으로 작성되었습니다.",
        "comment_id": comment.id
    }


@router.get("/feedback/{feedback_id}/comments")
async def get_comments(
    feedback_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    특정 피드백의 댓글 목록 조회
    """
    # 피드백 존재 및 권한 확인
    feedback_statement = select(Feedback).where(Feedback.id == feedback_id)
    feedback = session.exec(feedback_statement).first()
    
    if not feedback:
        raise HTTPException(
            status_code=404,
            detail="피드백을 찾을 수 없습니다."
        )
    
    # 권한 확인
    if current_user.id not in [feedback.mentor_id, feedback.mentee_id]:
        raise HTTPException(
            status_code=403,
            detail="이 피드백의 댓글을 볼 권한이 없습니다."
        )
    
    # 댓글 조회
    comments_statement = (
        select(FeedbackComment)
        .where(
            FeedbackComment.feedback_id == feedback_id,
            FeedbackComment.is_deleted == False
        )
        .order_by(FeedbackComment.created_at.asc())
    )
    comments = session.exec(comments_statement).all()
    
    comment_list = []
    for comment in comments:
        # 작성자 정보 조회
        user_statement = select(User).where(User.id == comment.user_id)
        user = session.exec(user_statement).first()
        
        comment_list.append({
            "id": comment.id,
            "user_id": comment.user_id,
            "user_name": user.name if user else "알 수 없음",
            "user_role": user.role if user else None,
            "comment_text": comment.comment_text,
            "created_at": comment.created_at.isoformat(),
            "updated_at": comment.updated_at.isoformat()
        })
    
    return {
        "feedback_id": feedback_id,
        "comments": comment_list
    }


@router.delete("/feedback/comments/{comment_id}")
async def delete_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    댓글 삭제 (작성자만 가능)
    """
    comment_statement = select(FeedbackComment).where(
        FeedbackComment.id == comment_id
    )
    comment = session.exec(comment_statement).first()
    
    if not comment:
        raise HTTPException(
            status_code=404,
            detail="댓글을 찾을 수 없습니다."
        )
    
    # 권한 확인: 작성자만 삭제 가능
    if comment.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="댓글을 삭제할 권한이 없습니다."
        )
    
    # Soft delete
    comment.is_deleted = True
    session.add(comment)
    session.commit()
    
    return {"message": "댓글이 성공적으로 삭제되었습니다."}


# ==================== 관리자 매칭 대시보드 API ====================

@router.get("/admin/matching-dashboard")
async def get_matching_dashboard(
    current_user: User = Depends(get_current_active_admin),
    session: Session = Depends(get_session)
):
    """
    관리자 매칭 대시보드 데이터 조회
    - 모든 멘토 목록 (현재 멘티 수 포함)
    - 모든 멘티 목록 (배정 상태 포함)
    - 현재 매칭 관계
    """
    # 모든 멘토 조회
    mentors_statement = select(User).where(User.role == "mentor", User.is_active == True)
    mentors = session.exec(mentors_statement).all()
    
    # 모든 멘티 조회
    mentees_statement = select(User).where(User.role == "mentee", User.is_active == True)
    mentees = session.exec(mentees_statement).all()
    
    # 멘토별 현재 멘티 수 계산
    mentor_data = []
    for mentor in mentors:
        mentee_count_statement = select(func.count(MentorMenteeRelation.id)).where(
            MentorMenteeRelation.mentor_id == mentor.id,
            MentorMenteeRelation.is_active == True
        )
        mentee_count = session.exec(mentee_count_statement).first() or 0
        
        mentor_data.append({
            "id": mentor.id,
            "name": mentor.name,
            "email": mentor.email,
            "team": mentor.team,
            "team_number": mentor.team_number,
            "position": mentor.position,
            "specialties": mentor.specialties,
            "mbti": mentor.mbti,
            "current_mentee_count": mentee_count,
            "max_mentees": 3,  # 기본 최대 멘티 수
            "is_available": mentee_count < 3
        })
    
    # 멘티별 배정 상태 확인
    mentee_data = []
    for mentee in mentees:
        # 현재 멘토 확인
        current_relation = session.exec(
            select(MentorMenteeRelation).where(
                MentorMenteeRelation.mentee_id == mentee.id,
                MentorMenteeRelation.is_active == True
            )
        ).first()
        
        current_mentor = None
        if current_relation:
            mentor_statement = select(User).where(User.id == current_relation.mentor_id)
            current_mentor = session.exec(mentor_statement).first()
        
        mentee_data.append({
            "id": mentee.id,
            "name": mentee.name,
            "email": mentee.email,
            "team": mentee.team,
            "team_number": mentee.team_number,
            "mbti": mentee.mbti,
            "interests": mentee.interests,
            "join_year": mentee.join_year,
            "is_assigned": current_relation is not None,
            "current_mentor": {
                "id": current_mentor.id,
                "name": current_mentor.name,
                "email": current_mentor.email
            } if current_mentor else None
        })
    
    # 현재 모든 매칭 관계 조회
    relations_statement = select(MentorMenteeRelation).where(MentorMenteeRelation.is_active == True)
    relations = session.exec(relations_statement).all()
    
    matching_data = []
    for relation in relations:
        mentor_statement = select(User).where(User.id == relation.mentor_id)
        mentee_statement = select(User).where(User.id == relation.mentee_id)
        mentor = session.exec(mentor_statement).first()
        mentee = session.exec(mentee_statement).first()
        
        # mentor나 mentee가 None인 경우 건너뛰기
        if not mentor or not mentee:
            continue
            
        matching_data.append({
            "relation_id": relation.id,
            "mentor": {
                "id": mentor.id,
                "name": mentor.name,
                "email": mentor.email
            },
            "mentee": {
                "id": mentee.id,
                "name": mentee.name,
                "email": mentee.email
            },
            "matched_at": relation.matched_at,
            "notes": relation.notes
        })
    
    return {
        "mentors": mentor_data,
        "mentees": mentee_data,
        "current_matches": matching_data,
        "statistics": {
            "total_mentors": len(mentor_data),
            "total_mentees": len(mentee_data),
            "assigned_mentees": len([m for m in mentee_data if m["is_assigned"]]),
            "unassigned_mentees": len([m for m in mentee_data if not m["is_assigned"]]),
            "available_mentors": len([m for m in mentor_data if m["is_available"]])
        }
    }


@router.post("/admin/assign-mentor")
async def admin_assign_mentor(
    request: dict,
    current_user: User = Depends(get_current_active_admin),
    session: Session = Depends(get_session)
):
    """
    관리자가 멘토-멘티 매칭 수행
    """
    mentee_id = request.get("mentee_id")
    mentor_id = request.get("mentor_id")
    notes = request.get("notes", "")
    # 멘티와 멘토 확인
    mentee_statement = select(User).where(User.id == mentee_id)
    mentee = session.exec(mentee_statement).first()
    
    mentor_statement = select(User).where(User.id == mentor_id)
    mentor = session.exec(mentor_statement).first()
    
    if not mentee or not mentor:
        raise HTTPException(status_code=404, detail="User not found")
    
    if mentee.role != "mentee":
        raise HTTPException(status_code=400, detail="User is not a mentee")
    
    if mentor.role != "mentor":
        raise HTTPException(status_code=400, detail="User is not a mentor")
    
    # 멘토의 현재 멘티 수 확인
    mentee_count_statement = select(func.count(MentorMenteeRelation.id)).where(
        MentorMenteeRelation.mentor_id == mentor_id,
        MentorMenteeRelation.is_active == True
    )
    mentee_count = session.exec(mentee_count_statement).first() or 0
    
    if mentee_count >= 3:  # 최대 멘티 수 제한
        raise HTTPException(status_code=400, detail="Mentor has reached maximum mentee limit")
    
    # 멘티의 기존 관계 확인 및 비활성화
    existing_relation = session.exec(
        select(MentorMenteeRelation).where(
            MentorMenteeRelation.mentee_id == mentee_id,
            MentorMenteeRelation.is_active == True
        )
    ).first()
    
    if existing_relation:
        existing_relation.is_active = False
        session.add(existing_relation)
    
    # 새 관계 생성
    relation = MentorMenteeRelation(
        mentor_id=mentor_id,
        mentee_id=mentee_id,
        is_active=True,
        notes=notes
    )
    
    session.add(relation)
    session.commit()
    session.refresh(relation)
    
    return {
        "message": "Mentor assigned successfully", 
        "relation_id": relation.id,
        "mentor_name": mentor.name,
        "mentee_name": mentee.name
    }


@router.delete("/admin/unassign-mentor/{relation_id}")
async def admin_unassign_mentor(
    relation_id: int,
    current_user: User = Depends(get_current_active_admin),
    session: Session = Depends(get_session)
):
    """
    관리자가 멘토-멘티 관계 해제
    """
    relation_statement = select(MentorMenteeRelation).where(MentorMenteeRelation.id == relation_id)
    relation = session.exec(relation_statement).first()
    
    if not relation:
        raise HTTPException(status_code=404, detail="Relation not found")
    
    # 관계 비활성화
    relation.is_active = False
    session.add(relation)
    session.commit()
    
    return {"message": "Mentor-mentee relationship deactivated successfully"}


@router.post("/mentor/select-mentee")
async def mentor_select_mentee(
    request: dict,
    current_user: User = Depends(get_current_active_mentor),
    session: Session = Depends(get_session)
):
    """
    멘토가 멘티를 직접 선택하는 API
    """
    mentee_id = request.get("mentee_id")
    # 멘토의 현재 멘티 수 확인
    mentee_count_statement = select(func.count(MentorMenteeRelation.id)).where(
        MentorMenteeRelation.mentor_id == current_user.id,
        MentorMenteeRelation.is_active == True
    )
    mentee_count = session.exec(mentee_count_statement).first() or 0
    
    if mentee_count >= 3:  # 최대 멘티 수 제한
        raise HTTPException(status_code=400, detail="멘토가 최대 멘티 수에 도달했습니다")
    
    # 멘티 확인
    mentee_statement = select(User).where(User.id == mentee_id)
    mentee = session.exec(mentee_statement).first()
    
    if not mentee:
        raise HTTPException(status_code=404, detail="멘티를 찾을 수 없습니다")
    
    if mentee.role != "mentee":
        raise HTTPException(status_code=400, detail="선택한 사용자가 멘티가 아닙니다")
    
    # 멘티의 기존 관계 확인
    existing_relation = session.exec(
        select(MentorMenteeRelation).where(
            MentorMenteeRelation.mentee_id == mentee_id,
            MentorMenteeRelation.is_active == True
        )
    ).first()
    
    if existing_relation:
        raise HTTPException(status_code=400, detail="이미 다른 멘토에게 배정된 멘티입니다")
    
    # 새 관계 생성
    relation = MentorMenteeRelation(
        mentor_id=current_user.id,
        mentee_id=mentee_id,
        is_active=True,
        notes="멘토가 직접 선택"
    )
    
    session.add(relation)
    session.commit()
    session.refresh(relation)
    
    return {
        "message": "멘티가 성공적으로 선택되었습니다", 
        "relation_id": relation.id,
        "mentee_name": mentee.name
    }


@router.get("/mentor/available-mentees")
async def get_available_mentees(
    current_user: User = Depends(get_current_active_mentor),
    session: Session = Depends(get_session)
):
    """
    멘토가 선택할 수 있는 멘티 목록 조회 (미배정된 멘티들)
    """
    # 모든 멘티 조회
    mentees_statement = select(User).where(User.role == "mentee", User.is_active == True)
    mentees = session.exec(mentees_statement).all()
    
    available_mentees = []
    for mentee in mentees:
        # 현재 멘토 확인
        current_relation = session.exec(
            select(MentorMenteeRelation).where(
                MentorMenteeRelation.mentee_id == mentee.id,
                MentorMenteeRelation.is_active == True
            )
        ).first()
        
        # 미배정된 멘티만 추가
        if not current_relation:
            available_mentees.append({
                "id": mentee.id,
                "name": mentee.name,
                "email": mentee.email,
                "team": mentee.team,
                "team_number": mentee.team_number,
                "mbti": mentee.mbti,
                "interests": mentee.interests,
                "join_year": mentee.join_year
            })
    
    return {"available_mentees": available_mentees}


@router.get("/matching")
async def get_matching_dashboard(
    current_user: User = Depends(get_current_active_admin),
    session: Session = Depends(get_session)
):
    """
    관리자 매칭 대시보드 데이터
    - 전체 멘토/멘티 목록
    - 현재 매칭 현황
    - 매칭 통계
    """
    # 전체 멘토 목록
    mentors_statement = select(User).where(User.role == "MENTOR")
    mentors = session.exec(mentors_statement).all()
    
    # 전체 멘티 목록
    mentees_statement = select(User).where(User.role == "MENTEE")
    mentees = session.exec(mentees_statement).all()
    
    # 현재 매칭 현황
    relations_statement = select(MentorMenteeRelation).where(MentorMenteeRelation.is_active == True)
    relations = session.exec(relations_statement).all()
    
    # 매칭된 멘티 ID 목록
    matched_mentee_ids = {relation.mentee_id for relation in relations}
    
    # 매칭 통계 계산
    total_mentors = len(mentors)
    total_mentees = len(mentees)
    assigned_mentees = len(matched_mentee_ids)
    unassigned_mentees = total_mentees - assigned_mentees
    
    # 멘토별 현재 멘티 수 계산
    mentor_mentee_counts = {}
    for relation in relations:
        if relation.mentor_id not in mentor_mentee_counts:
            mentor_mentee_counts[relation.mentor_id] = 0
        mentor_mentee_counts[relation.mentor_id] += 1
    
    # 멘토 목록에 현재 멘티 수 추가
    mentors_data = []
    for mentor in mentors:
        mentors_data.append({
            "id": mentor.id,
            "name": mentor.name,
            "email": mentor.email,
            "team": mentor.team,
            "current_mentee_count": mentor_mentee_counts.get(mentor.id, 0),
            "is_available": mentor_mentee_counts.get(mentor.id, 0) < 3  # 최대 3명까지 담당 가능
        })
    
    # 멘티 목록에 매칭 상태 추가
    mentees_data = []
    for mentee in mentees:
        # 현재 멘토 찾기
        current_mentor = None
        for relation in relations:
            if relation.mentee_id == mentee.id:
                mentor_statement = select(User).where(User.id == relation.mentor_id)
                mentor = session.exec(mentor_statement).first()
                if mentor:
                    current_mentor = {
                        "id": mentor.id,
                        "name": mentor.name,
                        "email": mentor.email
                    }
                break
        
        mentees_data.append({
            "id": mentee.id,
            "name": mentee.name,
            "email": mentee.email,
            "team": mentee.team,
            "is_assigned": mentee.id in matched_mentee_ids,
            "current_mentor": current_mentor
        })
    
    # 현재 매칭 목록
    current_matches = []
    for relation in relations:
        mentor_statement = select(User).where(User.id == relation.mentor_id)
        mentor = session.exec(mentor_statement).first()
        
        mentee_statement = select(User).where(User.id == relation.mentee_id)
        mentee = session.exec(mentee_statement).first()
        
        if mentor and mentee:
            current_matches.append({
                "relation_id": relation.id,
                "mentor": {
                    "id": mentor.id,
                    "name": mentor.name,
                    "email": mentor.email
                },
                "mentee": {
                    "id": mentee.id,
                    "name": mentee.name,
                    "email": mentee.email
                },
                "matched_at": relation.matched_at,
                "notes": relation.notes
            })
    
    return {
        "statistics": {
            "total_mentors": total_mentors,
            "total_mentees": total_mentees,
            "assigned_mentees": assigned_mentees,
            "unassigned_mentees": unassigned_mentees
        },
        "mentors": mentors_data,
        "mentees": mentees_data,
        "current_matches": current_matches
    }


@router.delete("/mentor-relations/{relation_id}")
async def unassign_mentor(
    relation_id: int,
    current_user: User = Depends(get_current_active_admin),
    session: Session = Depends(get_session)
):
    """
    멘토-멘티 관계 해제 (관리자 전용)
    """
    # 관계 조회
    relation_statement = select(MentorMenteeRelation).where(MentorMenteeRelation.id == relation_id)
    relation = session.exec(relation_statement).first()
    
    if not relation:
        raise HTTPException(status_code=404, detail="관계를 찾을 수 없습니다")
    
    if not relation.is_active:
        raise HTTPException(status_code=400, detail="이미 비활성화된 관계입니다")
    
    # 관계 비활성화
    relation.is_active = False
    session.add(relation)
    session.commit()
    session.refresh(relation)
    
    return {"message": "멘토-멘티 관계가 성공적으로 해제되었습니다"}


# 멘토가 자신의 멘티를 해제하는 엔드포인트
@router.post("/mentor/unassign")
async def mentor_unassign_mentee(
    request: dict,
    current_user: User = Depends(get_current_active_mentor),
    session: Session = Depends(get_session)
):
    """멘토가 본인에게 배정된 특정 멘티와의 관계를 해제"""
    mentee_id = int(request.get("mentee_id", 0))
    if not mentee_id:
        raise HTTPException(status_code=400, detail="mentee_id가 필요합니다")

    relation = session.exec(
        select(MentorMenteeRelation).where(
            MentorMenteeRelation.mentor_id == current_user.id,
            MentorMenteeRelation.mentee_id == mentee_id,
            MentorMenteeRelation.is_active == True,
        )
    ).first()

    if not relation:
        raise HTTPException(status_code=404, detail="활성 관계를 찾을 수 없습니다")

    relation.is_active = False
    session.add(relation)
    session.commit()
    session.refresh(relation)

    return {"message": "멘토-멘티 관계가 성공적으로 해제되었습니다", "relation_id": relation.id}


# CSV 파일을 통한 일괄 시험 결과 처리 (관리자 전용)
@router.post("/bulk-exam-results")
async def process_bulk_exam_results(
    current_user: User = Depends(get_current_active_admin),
    session: Session = Depends(get_session)
):
    """
    CSV 파일을 읽어서 모든 멘티의 시험 결과를 자동 처리
    """
    import csv
    import os
    from datetime import datetime
    
    # 여러 경로 시도 (로컬/AWS 환경 모두 지원)
    possible_paths = [
        "/app/data/mentee_exam_result.csv",  # Docker 컨테이너 경로
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "mentee_exam_result.csv"),  # 상대 경로
    ]
    
    csv_path = None
    for path in possible_paths:
        if os.path.exists(path):
            csv_path = path
            break
    
    if not csv_path:
        raise HTTPException(status_code=404, detail=f"CSV 파일을 찾을 수 없습니다. 확인한 경로: {possible_paths}")
    
    processed_count = 0
    errors = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                mentee_name = row.get('응시자', '').strip()
                if not mentee_name:
                    continue
                
                # DB에서 해당 이름의 멘티 찾기
                mentee = session.exec(
                    select(User).where(
                        User.name == mentee_name,
                        User.role == UserRole.MENTEE
                    )
                ).first()
                
                if not mentee:
                    errors.append(f"멘티 '{mentee_name}'을 찾을 수 없습니다")
                    continue
                
                # 각 섹션별 점수 계산
                sections = {
                    '은행업무': [k for k in row.keys() if k.startswith('BO')],
                    '상품지식': [k for k in row.keys() if k.startswith('PK')],
                    '고객응대': [k for k in row.keys() if k.startswith('CS')],
                    '법규준수': [k for k in row.keys() if k.startswith('CO')],
                    'IT활용': [k for k in row.keys() if k.startswith('IT')],
                    '영업실적': [k for k in row.keys() if k.startswith('SP')]
                }
                
                performance_scores = {}
                wrong_answers = []
                
                for section_name, questions in sections.items():
                    correct_count = sum(1 for q in questions if row.get(q, '0') == '1')
                    score = correct_count * 5
                    performance_scores[section_name] = score
                    
                    # 오답 문제 찾기
                    for q in questions:
                        if row.get(q, '0') == '0':
                            wrong_answers.append(q)
                
                total_score = sum(performance_scores.values())
                grade = 'A+' if total_score >= 570 else 'A' if total_score >= 540 else 'B+' if total_score >= 510 else 'B'
                
                # 개선 피드백 생성
                feedback_result = generate_personalized_feedback(mentee_name, performance_scores, wrong_answers)
                feedback = feedback_result["header"] + feedback_result["feedback"]
                
                # 기존 ExamScore 업데이트 또는 새로 생성
                existing_exam = session.exec(
                    select(ExamScore).where(ExamScore.mentee_id == mentee.id)
                ).first()
                
                if existing_exam:
                    existing_exam.score_data = json.dumps(performance_scores, ensure_ascii=False)
                    existing_exam.total_score = total_score
                    existing_exam.grade = grade
                    existing_exam.feedback = feedback
                    existing_exam.exam_date = datetime.utcnow()
                else:
                    new_exam = ExamScore(
                        mentee_id=mentee.id,
                        exam_name='은행 신입사원 종합평가',
                        exam_date=datetime.utcnow(),
                        score_data=json.dumps(performance_scores, ensure_ascii=False),
                        total_score=total_score,
                        grade=grade,
                        feedback=feedback
                    )
                    session.add(new_exam)
                
                processed_count += 1
        
        session.commit()
        
        return {
            "message": f"✅ {processed_count}명의 멘티 시험 결과를 처리했습니다",
            "processed_count": processed_count,
            "errors": errors
        }
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"일괄 처리 중 오류 발생: {str(e)}")


def load_exam_questions():
    """bank_training_exam.json 파일을 읽어서 문제별 learning_topic과 explanation을 매핑"""
    import os
    import json
    
    # 여러 경로 시도 (로컬/AWS 환경 모두 지원)
    possible_paths = [
        "/app/data/bank_training_exam.json",  # Docker 컨테이너 경로
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "bank_training_exam.json"),  # 상대 경로
    ]
    
    exam_path = None
    for path in possible_paths:
        if os.path.exists(path):
            exam_path = path
            break
    
    if not exam_path:
        print(f"⚠️ bank_training_exam.json not found in: {possible_paths}")
        return {}
    
    with open(exam_path, 'r', encoding='utf-8') as f:
        exam_data = json.load(f)
    
    question_info = {}
    for section in exam_data['sections']:
        for question in section['questions']:
            question_info[question['q_id']] = {
                'learning_topic': question.get('learning_topic', ''),
                'explanation': question.get('explanation', '')
            }
    
    return question_info


def load_learning_materials():
    """learning_materials_for_RAG.txt 파일을 읽어서 learning_topic별 학습 자료를 매핑"""
    import os
    import re
    
    # 여러 경로 시도 (로컬/AWS 환경 모두 지원)
    possible_paths = [
        "/app/data/learning_materials_for_RAG.txt",  # Docker 컨테이너 경로
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "learning_materials_for_RAG.txt"),  # 상대 경로
    ]
    
    materials_path = None
    for path in possible_paths:
        if os.path.exists(path):
            materials_path = path
            break
    
    if not materials_path:
        print(f"⚠️ learning_materials_for_RAG.txt not found in: {possible_paths}")
        return {}
    
    with open(materials_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 섹션별로 분리
    sections = {}
    
    # 섹션 헤더 찾기 (예: ## [BA01] 예금상품의 이해)
    section_pattern = r'## \[([A-Z]{2}\d{2})\] (.+?)(?=\n###|\n##|$)'
    section_matches = re.findall(section_pattern, content, re.DOTALL)
    
    for section_code, section_title in section_matches:
        # 해당 섹션의 내용 추출
        section_start = content.find(f'## [{section_code}]')
        if section_start != -1:
            # 다음 섹션까지의 내용 추출
            next_section = content.find('## [', section_start + 1)
            if next_section == -1:
                section_content = content[section_start:]
            else:
                section_content = content[section_start:next_section]
            
            sections[section_title] = {
                'code': section_code,
                'content': section_content.strip()
            }
    
    return sections


def get_learning_content_for_question(question_id: str, learning_materials: dict) -> str:
    """문제 ID에 해당하는 학습 자료 내용 반환 (섹션 기반 매칭)"""
    
    # 문제 ID에서 섹션 코드 추출 (예: BO014 -> BO)
    section_code = question_id[:2]
    
    # 섹션별 매핑 (섹션 코드 -> 관련 주제들)
    section_topics = {
        'BO': ['예금상품', '여신상품', '외환업무', '은행업무'],
        'PK': ['통합자산관리', '파생결합', '보험상품', '상품지식'],
        'CS': ['고객응대', '민원', '고객'],
        'CO': ['자금세탁', '소비자', '내부통제', '법규'],
        'IT': ['디지털', '금융', '보안', 'AI', '자동화'],
        'SP': ['KPI', '고객', '데이터', '영업', '성과']
    }
    
    topics = section_topics.get(section_code, [])
    
    # 해당 섹션의 학습 자료 찾기
    for topic_key, material in learning_materials.items():
        for topic in topics:
            if topic in topic_key:
                return material['content']
    
    return ""


def generate_personalized_feedback(mentee_name: str, performance_scores: dict, wrong_answers: list) -> dict:
    """개인화된 피드백 생성 (섹션 기반 동적 버전)"""

    # 학습 자료 로드
    learning_materials = load_learning_materials()

    # 문제별 설명 로드 (bank_training_exam.json에서)
    question_explanations = load_exam_questions()
    
    # 헤더 부분 제거 - 빈 문자열로 설정
    header = ""
    
    feedback = ""
    
    if wrong_answers:
        # 틀린 문제별로 개별 피드백 생성
        for i, wrong_question in enumerate(wrong_answers, 1):
            # 문제 ID에서 섹션 정보 추출
            section_name = ""
            if wrong_question.startswith('BO'):
                section_name = '은행업무'
            elif wrong_question.startswith('PK'):
                section_name = '상품지식'
            elif wrong_question.startswith('CS'):
                section_name = '고객응대'
            elif wrong_question.startswith('CO'):
                section_name = '법규준수'
            elif wrong_question.startswith('IT'):
                section_name = 'IT활용'
            elif wrong_question.startswith('SP'):
                section_name = '영업실적'
            
            # 해당 섹션의 점수
            section_score = performance_scores.get(section_name, 0)
            
            feedback += f"{section_name} - {wrong_question} ({section_score}점)\n"
            
            # 해당 문제에 대한 학습 자료 찾기
            question_content = get_learning_content_for_question(wrong_question, learning_materials)
            
            if question_content:
                # 학습 자료에서 내용 추출
                lines = question_content.split('\n')
                content_lines = []
                
                for line in lines:
                    # 헤더와 빈 줄 제외하고 실제 내용만 추출
                    if line.strip() and not line.startswith('#') and not line.startswith('---'):
                        # 마크다운 문법 제거 (구조는 유지)
                        clean_line = line.strip()
                        clean_line = clean_line.replace('**', '').replace('*', '')
                        if clean_line and len(clean_line) > 2:  # 너무 짧은 내용 제외
                            content_lines.append(clean_line)
                
                if content_lines:
                    # 중복 제거
                    unique_content = []
                    seen = set()
                    for content in content_lines:
                        if content not in seen:
                            seen.add(content)
                            unique_content.append(content)
                    
                    # 문제별 학습 내용 표시
                    feedback += f"   📚 학습 내용:\n"
                    for content in unique_content:
                        feedback += f"     • {content}\n"
            else:
                # 학습 자료에 없으면 문제 설명 사용
                explanation = question_explanations.get(wrong_question, {}).get('explanation', '해당 문제의 기본 개념 복습 필요')
                feedback += f"   • 문제 설명: {explanation}\n"
            
            feedback += "\n"
    
    # 종합 평가
    total_score = sum(performance_scores.values())
    if total_score >= 570:
        feedback += "💡 종합 평가:\n전반적으로 우수한 성적을 보여주고 있습니다. 특히 만점을 받은 영역이 있어 칭찬할 만합니다. 부족한 영역에 대한 집중적인 학습을 통해 더욱 발전하시길 바랍니다."
    elif total_score >= 540:
        feedback += "💡 종합 평가:\n양호한 성적을 보여주고 있습니다. 전반적인 이해도가 높지만, 일부 영역에서 보완이 필요합니다. 체계적인 학습을 통해 실력을 향상시키시길 바랍니다."
    else:
        feedback += "💡 종합 평가:\n기본적인 이해는 갖추고 있지만, 전반적인 학습이 필요합니다. 체계적인 학습 계획을 세우고 꾸준히 노력하시면 충분히 향상될 수 있습니다."
    
    return {
        "header": header,
        "feedback": feedback
    }
