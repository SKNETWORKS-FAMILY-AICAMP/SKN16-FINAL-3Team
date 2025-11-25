"""
초기 데이터 생성 스크립트 (개선된 버전)
컨테이너 재시작 시에도 안전하게 실행되도록 중복 생성 방지 로직 추가
RAG 데이터 자동 인덱싱 포함
"""
from sqlmodel import Session, select, delete
from sqlalchemy import or_
from app.database import engine
from app.models.user import User, UserRole
from app.models.mentor import MentorMenteeRelation, ExamScore, ChatHistory
from app.models.document import Document, DocumentChunk
from app.utils.auth import get_password_hash
import json
from datetime import datetime
import sys
from pathlib import Path
import asyncio


def create_initial_users(session: Session):
    """초기 사용자 생성 (중복 방지)"""
    print("📋 초기 사용자 확인 및 생성 중...")
    
    # 기존 사용자 확인
    existing_admin = session.exec(select(User).where(User.email == "admin@bank.com")).first()
    if existing_admin:
        print("✅ 관리자 계정이 이미 존재합니다. 스킵합니다.")
        return
    
    users = [
        # 관리자
        User(
            email="admin@bank.com",
            hashed_password=get_password_hash("admin123"),
            name="관리자",
            role=UserRole.ADMIN,
            team="운영팀",
            phone="010-1111-1111",
            is_active=True
        ),
        # 멘토
        User(
            email="mentor@bank.com",
            hashed_password=get_password_hash("mentor123"),
            name="김멘토",
            role=UserRole.MENTOR,
            team="영업1팀",
            phone="010-2222-2222",
            interests="금융투자, 리더십",
            hobbies="독서, 테니스",
            mbti="ENFJ",
            encouragement_message="함께 성장해나가요! 언제든 편하게 질문하세요."
        ),
        User(
            email="mentor2@bank.com",
            hashed_password=get_password_hash("mentor123"),
            name="이멘토",
            role=UserRole.MENTOR,
            team="영업2팀",
            phone="010-2222-3333",
            interests="재무분석, 컨설팅",
            hobbies="골프, 영화감상",
            mbti="ISTJ",
            encouragement_message="체계적으로 배워나가면 반드시 성공할 수 있어요!"
        ),
        # 멘티
        User(
            email="mentee@bank.com",
            hashed_password=get_password_hash("mentee123"),
            name="박신입",
            role=UserRole.MENTEE,
            team="영업1팀",
            phone="010-3333-3333",
            interests="디지털금융, 마케팅",
            hobbies="운동, 여행",
            is_active=True
        ),
    ]
    
    for user in users:
        session.add(user)
    
    session.commit()
    print(f"✅ {len(users)}명의 사용자 생성 완료")
    
    # 생성된 사용자 확인
    for user in users:
        print(f"   - {user.role}: {user.email} / {'admin123' if user.role == UserRole.ADMIN else 'mentor123' if user.role == UserRole.MENTOR else 'mentee123'}")


def create_mentor_relations(session: Session):
    """멘토-멘티 관계 생성 (중복 방지)"""
    print("📋 멘토-멘티 관계 확인 및 생성 중...")
    
    # 기존 관계 확인
    existing_relation = session.exec(select(MentorMenteeRelation)).first()
    if existing_relation:
        print("✅ 멘토-멘티 관계가 이미 존재합니다. 스킵합니다.")
        return
    
    # 멘토와 멘티 조회
    mentor1 = session.exec(select(User).where(User.email == "mentor@bank.com")).first()
    mentee1 = session.exec(select(User).where(User.email == "mentee@bank.com")).first()
    
    if not all([mentor1, mentee1]):
        print("⚠️ 멘토 또는 멘티 사용자를 찾을 수 없습니다. 관계 생성을 스킵합니다.")
        return
    
    relations = [
        MentorMenteeRelation(
            mentor_id=mentor1.id,
            mentee_id=mentee1.id,
            is_active=True,
            notes="같은 팀 배정. 적극적이고 학습 의지가 높음."
        ),
    ]
    
    for relation in relations:
        session.add(relation)
    
    session.commit()
    print(f"✅ {len(relations)}개의 멘토-멘티 관계 생성 완료")


def create_exam_scores(session: Session):
    """샘플 시험 점수 생성 (중복 방지)"""
    print("📋 시험 점수 확인 및 생성 중...")
    
    # 기존 점수 확인
    existing_score = session.exec(select(ExamScore)).first()
    if existing_score:
        print("✅ 시험 점수가 이미 존재합니다. 스킵합니다.")
        return
    
    # 멘티 조회
    mentee1 = session.exec(select(User).where(User.email == "mentee@bank.com")).first()
    
    if not mentee1:
        print("⚠️ 멘티 사용자를 찾을 수 없습니다. 시험 점수 생성을 스킵합니다.")
        return
    
    exams = [
        ExamScore(
            mentee_id=mentee1.id,
            exam_name="1차 종합평가",
            exam_date=datetime.utcnow(),
            score_data=json.dumps({
                "은행업무": 85,
                "상품지식": 78,
                "고객응대": 92,
                "법규준수": 88,
                "IT활용": 75,
                "영업실적": 80
            }, ensure_ascii=False),
            total_score=83.0,
            grade="B+",
            feedback="전반적으로 우수합니다. 특히 고객응대 능력이 뛰어납니다. IT 활용 능력을 더 향상시키면 좋겠습니다."
        ),
    ]
    
    for exam in exams:
        session.add(exam)
    
    session.commit()
    print(f"✅ {len(exams)}개의 시험 점수 생성 완료")


def sync_filesystem_with_database(session: Session):
    """파일 시스템과 데이터베이스 동기화"""
    print("🔄 파일 시스템과 데이터베이스 동기화 중...")
    
    try:
        # 모든 문서 조회
        statement = select(Document)
        documents = session.exec(statement).all()
        
        deleted_count = 0
        
        for document in documents:
            file_path = Path(document.file_path)
            
            # 파일이 존재하지 않으면 DB에서 삭제
            if not file_path.exists():
                print(f"   - 파일 없음, DB 레코드 삭제: {document.file_path}")
                
                # 관련 청크 삭제 (CASCADE DELETE를 위해 먼저 삭제)
                chunk_statement = select(DocumentChunk).where(DocumentChunk.document_id == document.id)
                chunks = session.exec(chunk_statement).all()
                for chunk in chunks:
                    session.delete(chunk)
                
                # 청크 삭제 커밋
                session.commit()
                
                # 문서 삭제
                session.delete(document)
                session.commit()
                deleted_count += 1
        
        print(f"   - ✅ 동기화 완료: {deleted_count}개 레코드 삭제")
        print(f"   - 남은 문서 수: {len(documents) - deleted_count}")
        
    except Exception as e:
        print(f"   - ❌ 동기화 오류: {e}")
        session.rollback()


def verify_data_integrity(session: Session):
    """데이터 무결성 확인"""
    print("🔍 데이터 무결성 확인 중...")
    
    # 사용자 수 확인
    user_count = session.exec(select(User)).all()
    print(f"   - 총 사용자 수: {len(user_count)}")
    
    # 관리자 계정 확인
    admin = session.exec(select(User).where(User.email == "admin@bank.com")).first()
    if admin:
        print(f"   - ✅ 관리자 계정 확인: {admin.name} ({admin.email})")
    else:
        print("   - ❌ 관리자 계정을 찾을 수 없습니다!")
        return False
    
    # 멘토 계정 확인
    mentors = session.exec(select(User).where(User.role == UserRole.MENTOR)).all()
    print(f"   - 멘토 수: {len(mentors)}")
    
    # 멘티 계정 확인
    mentees = session.exec(select(User).where(User.role == UserRole.MENTEE)).all()
    print(f"   - 멘티 수: {len(mentees)}")
    
    return True


def load_learning_materials():
    """학습 자료 텍스트 파일 로드"""
    materials_file = Path(__file__).parent / "data" / "learning_materials_for_RAG.txt"
    
    if not materials_file.exists():
        print(f"⚠️ 학습 자료 파일을 찾을 수 없습니다: {materials_file}")
        return None
    
    try:
        with open(materials_file, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"❌ 학습 자료 로드 중 오류: {e}")
        return None


def create_rag_document(session: Session, content: str) -> int:
    """RAG 학습 자료 문서 생성"""
    print("📚 RAG 학습 자료 문서 확인 중...")
    
    # 기존 RAG 학습 자료 문서 확인
    existing_doc = session.exec(
        select(Document).where(
            Document.category == "RAG",
            Document.title == "RAG - 은행 신입사원 연수 학습 자료집"
        )
    ).first()
    
    if existing_doc and existing_doc.is_indexed:
        print(f"✅ RAG 학습 자료가 이미 인덱싱되어 있습니다. 스킵합니다.")
        return existing_doc.id
    
    # 기존 문서가 있지만 인덱싱되지 않은 경우 삭제
    if existing_doc:
        # 관련 청크 삭제
        chunks = session.exec(
            select(DocumentChunk).where(DocumentChunk.document_id == existing_doc.id)
        ).all()
        for chunk in chunks:
            session.delete(chunk)
        session.delete(existing_doc)
        session.commit()
        print("   - 기존 미인덱싱 문서 삭제 완료")
    
    # 새 문서 생성
    document = Document(
        title="RAG - 은행 신입사원 연수 학습 자료집",
        category="RAG",
        file_path="learning_materials_for_RAG.txt",
        file_type="txt",
        file_size=len(content.encode('utf-8')),
        description="AI 멘토링 시스템을 위한 RAG 데이터베이스 구축용 학습자료",
        uploaded_by=1,  # 시스템 관리자 ID
        is_indexed=False
    )
    
    session.add(document)
    session.commit()
    session.refresh(document)
    
    print(f"✅ RAG 학습 자료 문서 생성 완료 (ID: {document.id})")
    return document.id


async def index_rag_document_async(session: Session, document_id: int, content: str):
    """RAG 문서를 비동기로 인덱싱"""
    from app.services.rag_indexer import index_document_from_text
    
    document = session.get(Document, document_id)
    if not document:
        print("❌ 문서를 찾을 수 없습니다.")
        return False
    
    print("🔍 RAG 학습 자료 인덱싱 중...")
    try:
        await index_document_from_text(session, document, content)
        print("✅ RAG 학습 자료 인덱싱 완료")
        return True
    except Exception as e:
        print(f"❌ RAG 인덱싱 실패: {e}")
        return False


def index_rag_document(session: Session, document_id: int, content: str):
    """RAG 문서를 동기적으로 인덱싱 (비동기 함수 래핑)"""
    return asyncio.run(index_rag_document_async(session, document_id, content))


def init_rag_data(session: Session):
    """RAG 데이터 초기화"""
    print("\n📚 RAG 데이터 초기화 시작...")
    
    # 학습 자료 로드
    content = load_learning_materials()
    if not content:
        print("⚠️ RAG 학습 자료를 로드할 수 없습니다. 스킵합니다.")
        return
    
    print(f"📊 학습 자료 정보:")
    print(f"  - 파일 크기: {len(content)} 글자")
    print(f"  - 줄 수: {len(content.splitlines())}")
    
    try:
        # 문서 생성
        document_id = create_rag_document(session, content)
        
        # 문서가 이미 인덱싱되어 있는지 확인
        document = session.get(Document, document_id)
        if document and document.is_indexed:
            print("✅ RAG 데이터 초기화 완료 (이미 인덱싱됨)")
            return
        
        # RAG 인덱싱
        success = index_rag_document(session, document_id, content)
        
        if success:
            print("✅ RAG 데이터 초기화 완료")
            # 인덱싱된 문서 확인
            session.refresh(document)
            if document.is_indexed:
                print(f"📈 문서 '{document.title}'이 RAG 시스템에 성공적으로 인덱싱되었습니다.")
            else:
                print("⚠️ 문서 인덱싱 상태를 확인해주세요.")
        else:
            print("⚠️ RAG 인덱싱에 실패했습니다.")
            
    except Exception as e:
        print(f"❌ RAG 데이터 초기화 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()


def init_all_data():
    """모든 초기 데이터 생성"""
    print("\n🚀 Initializing data...\n")
    
    # 먼저 데이터베이스 테이블 생성
    from app.database import init_db
    init_db()
    
    with Session(engine) as session:
        # 파일 시스템과 데이터베이스 동기화 (임시 비활성화)
        # sync_filesystem_with_database(session)
        
        # 기존 사용자 확인
        existing_admin = session.exec(select(User).where(User.email == "admin@bank.com")).first()
        
        # 사용자 데이터가 없으면 생성
        if not existing_admin:
            create_initial_users(session)
            create_mentor_relations(session)
            create_exam_scores(session)
            print("\n✅ User data initialized successfully!\n")
        else:
            print("✅ User data already exists. Skipping user initialization...")
        
        # RAG 데이터 초기화 (항상 확인)
        init_rag_data(session)
        
        # 기존 불필요 계정 정리
        cleanup_extra_users(session)

        # 고정 테스트 데이터 생성 (12월 테스트 기수)
        try:
            from app.init_fixed_test_data import (
                create_fixed_test_data,
                FIXED_MENTORS,
                FIXED_MENTEES,
            )
            create_fixed_test_data(session)
        except Exception as e:
            print(f"⚠️ 고정 테스트 데이터 생성 중 오류 (무시 가능): {e}")
        
        # 대규모 기수 데이터 생성 (9, 10, 11월 기수)
        try:
            from app.init_large_cohort_data import create_large_cohort_data
            create_large_cohort_data(session)
        except Exception as e:
            print(f"⚠️ 대규모 기수 데이터 생성 중 오류 (무시 가능): {e}")
    
    print("\n✅ All data initialized successfully!\n")
    print("Test accounts:")
    print("  Admin:  admin@bank.com / admin123")
    print("  Mentor: mentor@bank.com / mentor123")
    print("  Mentee: mentee@bank.com / mentee123")


def cleanup_extra_users(session: Session):
    """요구된 계정 외의 사용자 제거"""
    try:
        from app.init_fixed_test_data import FIXED_MENTORS, FIXED_MENTEES
    except Exception:
        FIXED_MENTORS = []
        FIXED_MENTEES = []
    
    allowed_emails = {
        "admin@bank.com",
        "mentor@bank.com",
        "mentor2@bank.com",
        "mentee@bank.com",
    }
    allowed_emails.update(entry["email"] for entry in FIXED_MENTORS)
    allowed_emails.update(entry["email"] for entry in FIXED_MENTEES)
    
    users_to_remove = session.exec(
        select(User).where(~User.email.in_(list(allowed_emails)))
    ).all()
    
    if not users_to_remove:
        return
    
    print(f"🧹 불필요 계정 {len(users_to_remove)}개 정리 중...")
    user_ids = [user.id for user in users_to_remove if user.id]
    if user_ids:
        session.exec(
            delete(MentorMenteeRelation).where(
                or_(
                    MentorMenteeRelation.mentor_id.in_(user_ids),
                    MentorMenteeRelation.mentee_id.in_(user_ids),
                )
            )
        )
        session.exec(delete(ExamScore).where(ExamScore.mentee_id.in_(user_ids)))
        session.exec(delete(ChatHistory).where(ChatHistory.user_id.in_(user_ids)))
    
    for user in users_to_remove:
        session.delete(user)
    session.commit()


if __name__ == "__main__":
    init_all_data()