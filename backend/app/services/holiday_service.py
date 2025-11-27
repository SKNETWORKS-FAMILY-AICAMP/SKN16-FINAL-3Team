"""
공휴일 동기화/조회 서비스
"""
import calendar
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

import requests
from sqlmodel import Session, select, delete

from app.config import settings
from app.models.holiday import Holiday

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService"
HOLIDAY_ENDPOINT = "getHoliDeInfo"
STALE_AFTER_DAYS = 30
REQUEST_TIMEOUT = 10

# 최소 연도별 수동 데이터 (API 장애 시 사용)
# 한국의 주요 공휴일: 신정, 설날, 3·1절, 어린이날, 부처님 오신 날, 현충일, 광복절, 추석, 개천절, 한글날, 성탄절
FALLBACK_HOLIDAYS: Dict[int, List[Dict[str, str]]] = {
    2024: [
        {"date": "2024-01-01", "name": "신정"},
        {"date": "2024-02-09", "name": "설 연휴"},
        {"date": "2024-02-10", "name": "설날"},
        {"date": "2024-02-11", "name": "설 연휴"},
        {"date": "2024-02-12", "name": "대체공휴일(설날)"},
        {"date": "2024-03-01", "name": "3·1절"},
        {"date": "2024-05-05", "name": "어린이날"},
        {"date": "2024-05-06", "name": "대체공휴일(어린이날)"},
        {"date": "2024-05-15", "name": "부처님 오신 날"},
        {"date": "2024-06-06", "name": "현충일"},
        {"date": "2024-08-15", "name": "광복절"},
        {"date": "2024-09-16", "name": "추석 연휴"},
        {"date": "2024-09-17", "name": "추석"},
        {"date": "2024-09-18", "name": "추석 연휴"},
        {"date": "2024-10-03", "name": "개천절"},
        {"date": "2024-10-09", "name": "한글날"},
        {"date": "2024-12-25", "name": "성탄절"},
    ],
    2025: [
        {"date": "2025-01-01", "name": "신정"},
        {"date": "2025-01-28", "name": "설 연휴"},
        {"date": "2025-01-29", "name": "설날"},
        {"date": "2025-01-30", "name": "설 연휴"},
        {"date": "2025-03-01", "name": "3·1절"},
        {"date": "2025-05-05", "name": "어린이날"},
        {"date": "2025-05-05", "name": "부처님 오신 날"},
        {"date": "2025-06-06", "name": "현충일"},
        {"date": "2025-08-15", "name": "광복절"},
        {"date": "2025-10-03", "name": "개천절"},
        {"date": "2025-10-06", "name": "추석 연휴"},
        {"date": "2025-10-07", "name": "추석"},
        {"date": "2025-10-08", "name": "추석 연휴"},
        {"date": "2025-10-09", "name": "한글날"},
        {"date": "2025-12-25", "name": "성탄절"},
    ],
    2026: [
        {"date": "2026-01-01", "name": "신정"},
        {"date": "2026-02-16", "name": "설 연휴"},
        {"date": "2026-02-17", "name": "설날"},
        {"date": "2026-02-18", "name": "설 연휴"},
        {"date": "2026-03-01", "name": "3·1절"},
        {"date": "2026-05-05", "name": "어린이날"},
        {"date": "2026-05-24", "name": "부처님 오신 날"},
        {"date": "2026-06-06", "name": "현충일"},
        {"date": "2026-08-15", "name": "광복절"},
        {"date": "2026-09-24", "name": "추석 연휴"},
        {"date": "2026-09-25", "name": "추석"},
        {"date": "2026-09-26", "name": "추석 연휴"},
        {"date": "2026-10-03", "name": "개천절"},
        {"date": "2026-10-09", "name": "한글날"},
        {"date": "2026-12-25", "name": "성탄절"},
    ],
    2027: [
        {"date": "2027-01-01", "name": "신정"},
        {"date": "2027-02-06", "name": "설 연휴"},
        {"date": "2027-02-07", "name": "설날"},
        {"date": "2027-02-08", "name": "설 연휴"},
        {"date": "2027-03-01", "name": "3·1절"},
        {"date": "2027-05-05", "name": "어린이날"},
        {"date": "2027-05-13", "name": "부처님 오신 날"},
        {"date": "2027-06-06", "name": "현충일"},
        {"date": "2027-08-15", "name": "광복절"},
        {"date": "2027-09-14", "name": "추석 연휴"},
        {"date": "2027-09-15", "name": "추석"},
        {"date": "2027-09-16", "name": "추석 연휴"},
        {"date": "2027-10-03", "name": "개천절"},
        {"date": "2027-10-09", "name": "한글날"},
        {"date": "2027-12-25", "name": "성탄절"},
    ],
    2028: [
        {"date": "2028-01-01", "name": "신정"},
        {"date": "2028-01-26", "name": "설 연휴"},
        {"date": "2028-01-27", "name": "설날"},
        {"date": "2028-01-28", "name": "설 연휴"},
        {"date": "2028-01-29", "name": "대체공휴일(설날)"},
        {"date": "2028-03-01", "name": "3·1절"},
        {"date": "2028-05-05", "name": "어린이날"},
        {"date": "2028-05-02", "name": "부처님 오신 날"},
        {"date": "2028-06-06", "name": "현충일"},
        {"date": "2028-08-15", "name": "광복절"},
        {"date": "2028-10-01", "name": "추석 연휴"},
        {"date": "2028-10-02", "name": "추석"},
        {"date": "2028-10-03", "name": "개천절"},
        {"date": "2028-10-04", "name": "추석 연휴"},
        {"date": "2028-10-09", "name": "한글날"},
        {"date": "2028-12-25", "name": "성탄절"},
    ],
    2029: [
        {"date": "2029-01-01", "name": "신정"},
        {"date": "2029-02-12", "name": "설 연휴"},
        {"date": "2029-02-13", "name": "설날"},
        {"date": "2029-02-14", "name": "설 연휴"},
        {"date": "2029-02-15", "name": "대체공휴일(설날)"},
        {"date": "2029-03-01", "name": "3·1절"},
        {"date": "2029-05-05", "name": "어린이날"},
        {"date": "2029-05-21", "name": "부처님 오신 날"},
        {"date": "2029-06-06", "name": "현충일"},
        {"date": "2029-08-15", "name": "광복절"},
        {"date": "2029-09-20", "name": "추석 연휴"},
        {"date": "2029-09-21", "name": "추석"},
        {"date": "2029-09-22", "name": "추석 연휴"},
        {"date": "2029-09-23", "name": "대체공휴일(추석)"},
        {"date": "2029-10-03", "name": "개천절"},
        {"date": "2029-10-09", "name": "한글날"},
        {"date": "2029-12-25", "name": "성탄절"},
    ],
    2030: [
        {"date": "2030-01-01", "name": "신정"},
        {"date": "2030-02-02", "name": "설 연휴"},
        {"date": "2030-02-03", "name": "설날"},
        {"date": "2030-02-04", "name": "설 연휴"},
        {"date": "2030-02-05", "name": "대체공휴일(설날)"},
        {"date": "2030-03-01", "name": "3·1절"},
        {"date": "2030-05-05", "name": "어린이날"},
        {"date": "2030-05-10", "name": "부처님 오신 날"},
        {"date": "2030-06-06", "name": "현충일"},
        {"date": "2030-08-15", "name": "광복절"},
        {"date": "2030-09-10", "name": "추석 연휴"},
        {"date": "2030-09-11", "name": "추석"},
        {"date": "2030-09-12", "name": "추석 연휴"},
        {"date": "2030-10-03", "name": "개천절"},
        {"date": "2030-10-09", "name": "한글날"},
        {"date": "2030-12-25", "name": "성탄절"},
    ],
}


class HolidayService:
    """공휴일 데이터를 외부 API와 동기화"""

    @classmethod
    def get_holidays(
        cls,
        session: Session,
        year: int,
        month: Optional[int] = None,
        force_refresh: bool = False,
    ) -> List[Holiday]:
        start_date, end_date = cls._date_range(year, month)
        existing = cls._get_existing(session, start_date, end_date)

        needs_refresh = force_refresh or not existing or cls._is_stale(existing)

        if needs_refresh:
            synced = cls._sync_from_remote(session, year, month, start_date, end_date)
            if synced:
                return cls._get_existing(session, start_date, end_date)

            # API 실패 시 수동 데이터 적용
            fallback_payload = cls._load_fallback(year, month)
            if fallback_payload:
                cls._replace_range(session, fallback_payload, start_date, end_date)
                return cls._get_existing(session, start_date, end_date)

        return existing

    @classmethod
    def _sync_from_remote(
        cls,
        session: Session,
        year: int,
        month: Optional[int],
        start_date: date,
        end_date: date,
    ) -> bool:
        api_key = settings.HOLIDAY_API_KEY
        if not api_key:
            logger.warning("HOLIDAY_API_KEY가 설정되지 않아 공휴일 API 동기화를 건너뜁니다.")
            return False

        months: Sequence[int]
        if month:
            months = [month]
        else:
            months = range(1, 13)

        payloads: List[Dict] = []
        for month_value in months:
            try:
                month_payload = cls._fetch_month_from_api(api_key, year, month_value)
                payloads.extend(month_payload)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "공휴일 API 호출 실패: year=%s month=%s error=%s",
                    year,
                    month_value,
                    exc,
                    exc_info=True,
                )
                return False

        if not payloads:
            logger.warning(
                "공휴일 API에서 데이터를 받지 못했습니다. year=%s month=%s",
                year,
                month,
            )
            return False

        cls._replace_range(session, payloads, start_date, end_date)
        return True

    @classmethod
    def _fetch_month_from_api(cls, api_key: str, year: int, month: int) -> List[Dict]:
        base_url = settings.HOLIDAY_API_BASE_URL or DEFAULT_BASE_URL
        url = f"{base_url.rstrip('/')}/{HOLIDAY_ENDPOINT}"
        params = {
            "serviceKey": api_key,
            "_type": "json",
            "solYear": str(year),
            "solMonth": f"{month:02d}",
            "numOfRows": "31",
        }

        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        payload = response.json()

        items = (
            payload.get("response", {})
            .get("body", {})
            .get("items", {})
            .get("item", [])
        )

        if isinstance(items, dict):
            items = [items]

        parsed: List[Dict] = []
        for item in items or []:
            locdate = str(item.get("locdate"))
            try:
                holiday_date = datetime.strptime(locdate, "%Y%m%d").date()
            except (TypeError, ValueError):
                continue

            parsed.append(
                {
                    "date": holiday_date,
                    "name": item.get("dateName", "공휴일"),
                    "is_public_holiday": str(item.get("isHoliday", "")).upper() == "Y",
                    "holiday_type": item.get("dateKind"),
                    "raw_code": str(item.get("seq")) if item.get("seq") is not None else None,
                    "data_source": "data.go.kr",
                }
            )

        return parsed

    @classmethod
    def _replace_range(
        cls,
        session: Session,
        payloads: List[Dict],
        start_date: date,
        end_date: date,
    ) -> None:
        session.exec(
            delete(Holiday).where(
                Holiday.holiday_date >= start_date,
                Holiday.holiday_date <= end_date,
            )
        )

        now = datetime.utcnow()
        for payload in payloads:
            holiday_date: date = payload["date"]
            if holiday_date < start_date or holiday_date > end_date:
                continue

            session.add(
                Holiday(
                    holiday_date=holiday_date,
                    name=payload.get("name", "공휴일"),
                    is_public_holiday=payload.get("is_public_holiday", True),
                    holiday_type=payload.get("holiday_type"),
                    data_source=payload.get("data_source", "manual"),
                    raw_code=payload.get("raw_code"),
                    created_at=now,
                    updated_at=now,
                )
            )

        session.commit()

    @staticmethod
    def _get_existing(session: Session, start_date: date, end_date: date) -> List[Holiday]:
        statement = (
            select(Holiday)
            .where(
                Holiday.holiday_date >= start_date,
                Holiday.holiday_date <= end_date,
            )
            .order_by(Holiday.holiday_date.asc(), Holiday.name.asc())
        )
        return session.exec(statement).all()

    @staticmethod
    def _date_range(year: int, month: Optional[int]) -> Tuple[date, date]:
        if month:
            last_day = calendar.monthrange(year, month)[1]
            start = date(year, month, 1)
            end = date(year, month, last_day)
        else:
            start = date(year, 1, 1)
            end = date(year, 12, 31)
        return start, end

    @staticmethod
    def _is_stale(holidays: Sequence[Holiday]) -> bool:
        if not holidays:
            return True
        newest = max((holiday.updated_at for holiday in holidays if holiday.updated_at), default=None)
        if not newest:
            return True
        return datetime.utcnow() - newest >= timedelta(days=STALE_AFTER_DAYS)

    @classmethod
    def _load_fallback(cls, year: int, month: Optional[int]) -> List[Dict]:
        data = FALLBACK_HOLIDAYS.get(year, [])
        if month:
            prefix = f"{year}-{month:02d}"
            data = [entry for entry in data if entry["date"].startswith(prefix)]

        converted = []
        for entry in data:
            try:
                holiday_date = datetime.strptime(entry["date"], "%Y-%m-%d").date()
            except ValueError:
                continue

            converted.append(
                {
                    "date": holiday_date,
                    "name": entry["name"],
                    "is_public_holiday": entry.get("is_public_holiday", True),
                    "holiday_type": entry.get("holiday_type", "manual"),
                    "raw_code": entry.get("raw_code"),
                    "data_source": "manual",
                }
            )
        return converted


