import os
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    Date,
    DateTime,
    UniqueConstraint,
    text,
    func,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import inspect

# ============================================================
# ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    DB_PATH = BASE_DIR / "sleepy.db"
    DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"
    connect_args = {"check_same_thread": False}
else:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace(
            "postgres://",
            "postgresql://",
            1,
        )
    connect_args = {}

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

    # НОВОЕ: поле для учебной нагрузки (1 - была, 0 - не была)
    study_load = Column(Integer, default=0)

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
            Checkin.study_load,  # <-- ДОБАВЛЕНО (индекс 13)
        ).filter(
            Checkin.telegram_id == telegram_id
        ).order_by(
            Checkin.checkin_date
        ).all()

        return [tuple(row) for row in rows]


def get_checkins_with_dates(telegram_id):
    """Для экспорта: возвращает дату + все поля."""
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
# Тестовые данные: 7 дней
# -------------------------

def create_test_data(telegram_id):
    today = date.today()

    test_data = [
        (7.5, 4, 4, 4, 0, None, "1 чашка", "08:00", "До 30 минут", "Средняя", 2, "Утро"),
        (6.5, 3, 3, 3, 1, "До 30 минут", "2 чашки", "16:00", "30–60 минут", "Средняя", 3, "Ночь"),
        (5.5, 2, 2, 2, 0, None, "3 и более", "19:00", "Больше часа", "Высокая", 5, "Ночь"),
        (7.0, 4, 4, 4, 1, "30–60 минут", "2 чашки", "15:00", "30–60 минут", "Средняя", 4, "Выходной"),
        (7.0, 4, 4, 4, 0, None, "1 чашка", "09:00", "До 30 минут", "Лёгкая", 2, "Утро"),
        (8.0, 5, 5, 5, 0, None, "Не пил(а)", None, "Не смотрел(а)", "Средняя", 1, "Выходной"),
        (7.5, 4, 4, 5, 0, None, "1 чашка", "10:00", "До 30 минут", "Лёгкая", 2, "День"),
    ]

    with SessionLocal() as session:
        for i, data in enumerate(test_data):
            (
                sleep_duration, sleep_quality, mood, energy,
                nap_taken, nap_duration, caffeine, caffeine_time,
                screen_time, physical_activity, stress, shift_type,
            ) = data

            checkin_date = today - timedelta(days=6 - i)

            checkin = session.query(Checkin).filter_by(
                telegram_id=telegram_id,
                checkin_date=checkin_date,
            ).first()

            values = {
                "sleep_time": "23:30",
                "wake_time": "07:00",
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
                "study_load": 0,
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


# -------------------------
# Тестовые данные: 28 дней
# -------------------------

def create_personal_test_data(telegram_id):
    today = date.today()

    # Формат: (sleep, quality, mood, energy, stress, shift_type, screen, activity, caffeine, caf_time, study_load)
    # study_load: 0 - нет учебы, 1 - средняя, 2 - сильная
    test_data = [
        # Неделя 1
        (8.5, 5, 5, 5, 1, "Выходной", "До 30 минут", "Высокая", "1 чашка", "10:00", 0),
        (8.0, 5, 5, 5, 1, "Учёба: Утро", "До 30 минут", "Средняя", "1 чашка", "09:00", 1),
        (7.5, 4, 4, 4, 2, "Учёба: День", "30–60 минут", "Средняя", "2 чашки", "14:00", 1),
        (6.5, 3, 3, 3, 4, "Учёба: Вечер", "Больше часа", "Не было", "3 и более", "19:00", 2),
        (5.5, 2, 2, 2, 5, "Учёба: Ночь", "Больше часа", "Не было", "3 и более", "20:00", 2),
        (8.0, 5, 4, 5, 1, "Выходной", "До 30 минут", "Высокая", "1 чашка", "11:00", 0),
        (7.5, 4, 4, 4, 2, "Учёба: Утро", "До 30 минут", "Средняя", "1 чашка", "09:00", 1),

        # Неделя 2
        (7.0, 4, 4, 4, 2, "Учёба: День", "30–60 минут", "Средняя", "2 чашки", "15:00", 1),
        (6.0, 2, 2, 2, 4, "Учёба: Вечер", "Больше часа", "Не было", "3 и более", "18:30", 2),
        (6.5, 3, 3, 3, 4, "Учёба: Ночь", "Больше часа", "Не было", "3 и более", "19:30", 2),
        (8.5, 5, 5, 5, 1, "Выходной", "До 30 минут", "Высокая", "1 чашка", "10:30", 0),
        (8.0, 5, 5, 5, 1, "Учёба: Утро", "До 30 минут", "Средняя", "1 чашка", "08:00", 1),
        (7.5, 4, 4, 4, 2, "Учёба: День", "30–60 минут", "Средняя", "2 чашки", "13:00", 1),
        (5.5, 2, 2, 2, 5, "Учёба: Вечер", "Больше часа", "Не было", "3 и более", "20:00", 2),

        # Неделя 3
        (6.5, 3, 3, 3, 4, "Учёба: Ночь", "Больше часа", "Не было", "3 и более", "19:00", 2),
        (8.0, 5, 5, 4, 1, "Выходной", "До 30 минут", "Высокая", "1 чашка", "10:00", 0),
        (7.5, 4, 4, 4, 2, "Учёба: Утро", "До 30 минут", "Средняя", "1 чашка", "09:30", 1),
        (7.0, 4, 4, 4, 2, "Учёба: День", "30–60 минут", "Средняя", "2 чашки", "15:30", 1),
        (6.0, 3, 3, 3, 4, "Учёба: Вечер", "Больше часа", "Не было", "3 и более", "18:00", 2),
        (6.5, 3, 3, 3, 4, "Учёба: Ночь", "Больше часа", "Не было", "3 и более", "19:00", 2),
        (8.5, 5, 5, 5, 1, "Выходной", "До 30 минут", "Высокая", "1 чашка", "11:30", 0),

        # Неделя 4
        (8.0, 5, 5, 5, 1, "Учёба: Утро", "До 30 минут", "Средняя", "1 чашка", "09:00", 1),
        (7.5, 4, 4, 4, 2, "Учёба: День", "30–60 минут", "Средняя", "2 чашки", "14:30", 1),
        (5.5, 2, 2, 2, 5, "Учёба: Вечер", "Больше часа", "Не было", "3 и более", "20:30", 2),
        (6.5, 3, 3, 3, 4, "Учёба: Ночь", "Больше часа", "Не было", "3 и более", "19:30", 2),
        (8.0, 5, 4, 5, 1, "Выходной", "До 30 минут", "Высокая", "1 чашка", "10:00", 0),
        (7.5, 4, 4, 4, 2, "Учёба: Утро", "До 30 минут", "Средняя", "1 чашка", "09:00", 1),
        (7.0, 4, 4, 4, 2, "Учёба: День", "30–60 минут", "Средняя", "2 чашки", "15:00", 1),
    ]

    with SessionLocal() as session:
        for i, data in enumerate(test_data):
            (
                sleep_duration, sleep_quality, mood, energy, stress,
                shift_type, screen_time, physical_activity,
                caffeine, caffeine_time, study_load
            ) = data

            checkin_date = today - timedelta(days=27 - i)

            session.query(Checkin).filter_by(
                telegram_id=telegram_id,
                checkin_date=checkin_date,
            ).delete()

            # Время сна и подъема
            if "Ночь" in shift_type:
                sleep_time, wake_time = "02:00", "08:30"
            else:
                sleep_time, wake_time = "23:30", "07:30"

            values = {
                "sleep_time": sleep_time,
                "wake_time": wake_time,
                "sleep_duration": sleep_duration,
                "sleep_quality": sleep_quality,
                "mood": mood,
                "energy": energy,
                "nap_taken": 0,
                "nap_duration": None,
                "caffeine": caffeine,
                "caffeine_time": caffeine_time,
                "screen_time": screen_time,
                "physical_activity": physical_activity,
                "stress": stress,
                "shift_type": shift_type,
                "study_load": study_load,
            }

            session.add(
                Checkin(
                    telegram_id=telegram_id,
                    checkin_date=checkin_date,
                    **values,
                )
            )

        session.commit()
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