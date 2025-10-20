"""
초기 데이터 생성 스크립트 (개선된 버전)
컨테이너 재시작 시에도 안전하게 실행되도록 중복 생성 방지 로직 추가
"""
from sqlmodel import Session, select
from app.database import engine
from app.models.user import User, UserRole
from app.models.mentor import MentorMenteeRelation, ExamScore
from app.models.document import Document, DocumentChunk
from app.utils.auth import get_password_hash
import json
from datetime import datetime
import sys
from pathlib import Path


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
        User(
            email="mentee2@bank.com",
            hashed_password=get_password_hash("mentee123"),
            name="최신입",
            role=UserRole.MENTEE,
            team="영업2팀",
            phone="010-3333-4444",
            interests="고객관리, 상품기획",
            hobbies="그림그리기, 음악감상",
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
    mentor2 = session.exec(select(User).where(User.email == "mentor2@bank.com")).first()
    mentee1 = session.exec(select(User).where(User.email == "mentee@bank.com")).first()
    mentee2 = session.exec(select(User).where(User.email == "mentee2@bank.com")).first()
    
    if not all([mentor1, mentor2, mentee1, mentee2]):
        print("⚠️ 멘토 또는 멘티 사용자를 찾을 수 없습니다. 관계 생성을 스킵합니다.")
        return
    
    relations = [
        MentorMenteeRelation(
            mentor_id=mentor1.id,
            mentee_id=mentee1.id,
            is_active=True,
            notes="같은 팀 배정. 적극적이고 학습 의지가 높음."
        ),
        MentorMenteeRelation(
            mentor_id=mentor2.id,
            mentee_id=mentee2.id,
            is_active=True,
            notes="꼼꼼한 성격. 이론적 학습 선호."
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
    mentee2 = session.exec(select(User).where(User.email == "mentee2@bank.com")).first()
    
    if not all([mentee1, mentee2]):
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
        ExamScore(
            mentee_id=mentee2.id,
            exam_name="1차 종합평가",
            exam_date=datetime.utcnow(),
            score_data=json.dumps({
                "은행업무": 90,
                "상품지식": 88,
                "고객응대": 82,
                "법규준수": 95,
                "IT활용": 85,
                "영업실적": 78
            }, ensure_ascii=False),
            total_score=86.3,
            grade="A-",
            feedback="이론적 지식이 탄탄합니다. 실제 영업 상황에서의 경험을 더 쌓아보세요."
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
        if existing_admin:
            print("✅ Data already exists. Skipping initialization...")
            print("\nTest accounts:")
            print("  Admin:  admin@bank.com / admin123")
            print("  Mentor: mentor@bank.com / mentor123")
            print("  Mentee: mentee@bank.com / mentee123")
            return
        
        create_initial_users(session)
        create_mentor_relations(session)
        create_exam_scores(session)
    
    print("\n✅ All data initialized successfully!\n")
    print("Test accounts:")
    print("  Admin:  admin@bank.com / admin123")
    print("  Mentor: mentor@bank.com / mentor123")
    print("  Mentee: mentee@bank.com / mentee123")


if __name__ == "__main__":
    init_all_data()