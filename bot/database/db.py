import os
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Date, DateTime,
    UniqueConstraint, text, func,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import inspect

# ============================================================
# ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ (для Bothost)
# ============================================================

DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "sleepy.db"
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"
connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)

Base = declarative_base()


# -------------------------
# Модели таблиц
# -------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    name = Column(String, nullable=False)
    age = Column(Integer, nullable=False)
    category = Column(String, nullable=False)
    schedule = Column(String, nullable=False)
    created_at = Column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class Checkin(Base):
    __tablename__ = "checkins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, nullable=False, index=True)
    checkin_date = Column(Date, nullable=False)

    sleep_time = Column(String)
    wake_time = Column(String)
    sleep_duration = Column(Float, nullable=False)
    sleep_quality = Column(Integer, nullable=False)
    mood = Column(Integer, nullable=False)
    energy = Column(Integer, nullable=False)

    nap_taken = Column(Integer, nullable=False)
    nap_duration = Column(String)

    caffeine = Column(String)
    caffeine_time = Column(String)
    screen_time = Column(String)
    physical_activity = Column(String)
    stress = Column(Integer)

    shift_type = Column(String)
    study_load = Column(Integer, default=0)

    # НОВОЕ: статус курса (collecting, analyzing, stabilizing, completed)
    status = Column(String, default="collecting")

    created_at = Column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        UniqueConstraint(
            "telegram_id",
            "checkin_date",
            name="uq_checkins_telegram_date",
        ),
    )


# -------------------------
# Инициализация базы
# -------------------------

def init_db():
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    Base.metadata.create_all(engine)

    if DATABASE_URL.startswith("sqlite") and "checkins" in existing_tables:
        columns = {
            column["name"]
            for column in inspector.get_columns("checkins")
        }

        migrations = {
            "sleep_time": "TEXT",
            "wake_time": "TEXT",
            "caffeine": "TEXT",
            "caffeine_time": "TEXT",
            "screen_time": "TEXT",
            "physical_activity": "TEXT",
            "stress": "INTEGER",
            "shift_type": "TEXT",
            "study_load": "INTEGER",
            "status": "TEXT", # НОВОЕ
        }

        with engine.begin() as connection:
            for column_name, column_type in migrations.items():
                if column_name not in columns:
                    connection.execute(
                        text(
                            f"ALTER TABLE checkins "
                            f"ADD COLUMN {column_name} {column_type}"
                        )
                    )


# -------------------------
# Пользователи
# -------------------------

def add_user(telegram_id: int, name: str, age: int, category: str, schedule: str):
    with SessionLocal() as session:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()

        if user:
            user.name = name
            user.age = age
            user.category = category
            user.schedule = schedule
        else:
            session.add(
                User(
                    telegram_id=telegram_id,
                    name=name,
                    age=age,
                    category=category,
                    schedule=schedule,
                )
            )

        session.commit()


def get_user(telegram_id: int):
    with SessionLocal() as session:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()

        if not user:
            return None

        return (
            user.telegram_id,
            user.name,
            user.age,
            user.category,
            user.schedule,
        )


def user_exists(telegram_id: int) -> bool:
    with SessionLocal() as session:
        return session.query(User).filter_by(telegram_id=telegram_id).first() is not None


def get_all_users():
    with SessionLocal() as session:
        rows = session.query(User.telegram_id).all()
        return [row[0] for row in rows]


# -------------------------
# Отметки сна
# -------------------------

def add_checkin(
        telegram_id,
        checkin_date,
        sleep_time,
        wake_time,
        sleep_duration,
        sleep_quality,
        mood,
        energy,
        nap_taken,
        nap_duration,
        caffeine,
        caffeine_time,
        screen_time,
        physical_activity,
        stress,
        shift_type=None,
        study_load=0,
):
    if isinstance(checkin_date, str):
        checkin_date = date.fromisoformat(checkin_date)

    with SessionLocal() as session:
        checkin = session.query(Checkin).filter_by(
            telegram_id=telegram_id,
            checkin_date=checkin_date,
        ).first()

        values = {
            "sleep_time": sleep_time,
            "wake_time": wake_time,
            "sleep_duration": sleep_duration,
            "sleep_quality": sleep_quality,
            "mood": mood,
            "energy": energy,
            "nap_taken": nap_taken,
            "nap_duration": nap_duration,
            "caffeine": caffeine,
            "caffeine_time": caffeine_time,
            "screen_time": screen_time,
            "physical_activity": physical_activity,
            "stress": stress,
            "shift_type": shift_type,
            "study_load": study_load,
        }

        if checkin:
            for key, value in values.items():
                setattr(checkin, key, value)
        else:
            session.add(
                Checkin(
                    telegram_id=telegram_id,
                    checkin_date=checkin_date,
                    **values,
                )
            )

        session.commit()


def has_checkin_for_date(telegram_id, checkin_date) -> bool:
    if isinstance(checkin_date, str):
        checkin_date = date.fromisoformat(checkin_date)

    with SessionLocal() as session:
        return (
                session.query(Checkin)
                .filter_by(telegram_id=telegram_id, checkin_date=checkin_date)
                .first()
                is not None
        )


def update_user_status(telegram_id, new_status):
    """Обновляет статус курса для пользователя."""
    with SessionLocal() as session:
        # Берем последний чек-ин
        last_checkin = session.query(Checkin).filter_by(
            telegram_id=telegram_id
        ).order_by(Checkin.checkin_date.desc()).first()
        if last_checkin:
            last_checkin.status = new_status
            session.commit()


def get_user_status(telegram_id):
    """Возвращает текущий статус курса."""
    with SessionLocal() as session:
        last_checkin = session.query(Checkin).filter_by(
            telegram_id=telegram_id
        ).order_by(Checkin.checkin_date.desc()).first()
        return last_checkin.status if last_checkin else "collecting"


# -------------------------
# Статистика
# -------------------------

def get_user_statistics(telegram_id):
    with SessionLocal() as session:
        days = (
            session.query(Checkin.id)
            .filter(Checkin.telegram_id == telegram_id)
            .count()
        )

        stats = session.query(
            func.avg(Checkin.sleep_duration),
            func.avg(Checkin.sleep_quality),
            func.avg(Checkin.mood),
            func.avg(Checkin.energy),
            func.sum(Checkin.nap_taken),
            func.avg(Checkin.stress),
        ).filter(Checkin.telegram_id == telegram_id).first()

        avg_sleep = stats[0]
        avg_quality = stats[1]
        avg_mood = stats[2]
        avg_energy = stats[3]
        nap_days = stats[4] or 0
        avg_stress = stats[5]

        return (
            days,
            avg_sleep,
            avg_quality,
            avg_mood,
            avg_energy,
            nap_days,
            avg_stress,
        )


def get_first_checkin_date(telegram_id):
    with SessionLocal() as session:
        result = session.query(
            func.min(Checkin.checkin_date)
        ).filter(Checkin.telegram_id == telegram_id).scalar()

        return result


def get_checkins_for_period(telegram_id, start_date, end_date):
    if isinstance(start_date, str):
        start_date = date.fromisoformat(start_date)

    if isinstance(end_date, str):
        end_date = date.fromisoformat(end_date)

    with SessionLocal() as session:
        rows = session.query(
            Checkin.checkin_date,
            Checkin.sleep_duration,
            Checkin.sleep_quality,
            Checkin.mood,
            Checkin.energy,
            Checkin.nap_taken,
            Checkin.nap_duration,
            Checkin.caffeine,
            Checkin.screen_time,
            Checkin.physical_activity,
            Checkin.stress,
            Checkin.sleep_time,
            Checkin.wake_time,
        ).filter(
            Checkin.telegram_id == telegram_id,
            Checkin.checkin_date.between(start_date, end_date),
        ).order_by(
            Checkin.checkin_date
        ).all()

        return [tuple(row) for row in rows]


def get_checkins_for_analysis(telegram_id):
    with SessionLocal() as session:
        rows = session.query(
            Checkin.sleep_duration,
            Checkin.sleep_quality,
            Checkin.mood,
            Checkin.energy,
            Checkin.stress,
            Checkin.caffeine,
            Checkin.caffeine_time,
            Checkin.screen_time,
            Checkin.physical_activity,
            Checkin.nap_taken,
            Checkin.nap_duration,
            Checkin.sleep_time,
            Checkin.shift_type,
            Checkin.study_load,
        ).filter(
            Checkin.telegram_id == telegram_id
        ).order_by(
            Checkin.checkin_date
        ).all()

        return [tuple(row) for row in rows]


def get_checkins_with_dates(telegram_id):
    with SessionLocal() as session:
        rows = session.query(
            Checkin.checkin_date,
            Checkin.sleep_duration,
            Checkin.sleep_quality,
            Checkin.mood,
            Checkin.energy,
            Checkin.stress,
            Checkin.caffeine,
            Checkin.screen_time,
            Checkin.physical_activity,
            Checkin.shift_type,
        ).filter(
            Checkin.telegram_id == telegram_id
        ).order_by(
            Checkin.checkin_date
        ).all()

        return [tuple(row) for row in rows]


# -------------------------
# Тестовые данные (без изменений)
# -------------------------

def create_test_data(telegram_id):
    # ... (оставляем как было)
    pass


def create_personal_test_data(telegram_id):
    # ... (оставляем как было)
    pass


def get_users_without_recent_checkin(days: int = 2):
    threshold = date.today() - timedelta(days=days)
    with SessionLocal() as session:
        all_users = session.query(User.telegram_id).all()
        all_ids = {row[0] for row in all_users}
        active_ids = {
            row[0] for row in session.query(Checkin.telegram_id)
            .filter(Checkin.checkin_date >= threshold)
            .distinct().all()
        }
        return list(all_ids - active_ids)


def get_active_users_count(days: int = 7) -> int:
    start_date = date.today() - timedelta(days=days)
    with SessionLocal() as session:
        result = session.query(
            func.count(func.distinct(Checkin.telegram_id))
        ).filter(Checkin.checkin_date >= start_date).scalar()
        return result or 0


def get_top_users(limit: int = 5):
    with SessionLocal() as session:
        rows = session.query(
            User.name,
            func.count(Checkin.id).label("checkins_count"),
        ).join(
            Checkin,
            User.telegram_id == Checkin.telegram_id,
        ).group_by(
            User.telegram_id,
            User.name,
        ).order_by(
            func.count(Checkin.id).desc()
        ).limit(limit).all()
        return [(row[0], row[1]) for row in rows]


def get_recent_users(limit: int = 5):
    with SessionLocal() as session:
        rows = session.query(
            User.name,
            User.age,
            User.category,
            User.created_at,
        ).order_by(
            User.created_at.desc()
        ).limit(limit).all()
        return [tuple(row) for row in rows]