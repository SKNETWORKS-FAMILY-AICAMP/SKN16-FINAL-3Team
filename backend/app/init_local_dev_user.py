"""
로컬 개발 환경에서 Vite (`npm run dev`)로 빠르게 UI를 확인할 수 있도록
고정 테스트 계정을 보장하는 스크립트입니다.

- 이메일: 202504075@bank.com
- 비밀번호: 19990512
- 이름: 임동우
"""
from sqlmodel import Session, select

from app.database import engine
from app.models.user import User, UserRole
from app.utils.auth import get_password_hash, verify_password


DEV_USER = {
    "email": "202504075@bank.com",
    "password": "19990512",
    "name": "임동우",
    "employee_number": "202504075",
    "phone": "010-9905-4075",
    "team": "디지털혁신부",
    "team_number": "1팀",
    "position": "사원",
    "join_year": 2025,
    "mbti": "ENTJ",
}


def ensure_dev_user():
    """지정된 가상 계정을 생성하거나 업데이트합니다."""
    with Session(engine) as session:
        existing = session.exec(
            select(User).where(User.email == DEV_USER["email"])
        ).first()

        if existing:
            updated = False
            for field in ["name", "employee_number", "phone", "team", "team_number", "position", "join_year", "mbti"]:
                value = DEV_USER.get(field)
                if value is not None and getattr(existing, field) != value:
                    setattr(existing, field, value)
                    updated = True

            if not verify_password(DEV_USER["password"], existing.hashed_password):
                existing.hashed_password = get_password_hash(DEV_USER["password"])
                updated = True

            if existing.role != UserRole.MENTEE:
                existing.role = UserRole.MENTEE
                updated = True

            if updated:
                session.add(existing)
                session.commit()
                print("✅ 로컬 개발 계정을 최신 상태로 업데이트했습니다.")
            else:
                print("ℹ️ 로컬 개발 계정이 이미 최신 상태입니다.")
            return existing

        user = User(
            email=DEV_USER["email"],
            hashed_password=get_password_hash(DEV_USER["password"]),
            name=DEV_USER["name"],
            role=UserRole.MENTEE,
            employee_number=DEV_USER["employee_number"],
            phone=DEV_USER["phone"],
            team=DEV_USER["team"],
            team_number=DEV_USER["team_number"],
            position=DEV_USER["position"],
            join_year=DEV_USER["join_year"],
            mbti=DEV_USER["mbti"],
        )
        session.add(user)
        session.commit()
        print("🎉 로컬 개발 계정을 새로 생성했습니다.")
        return user


if __name__ == "__main__":
    ensure_dev_user()

