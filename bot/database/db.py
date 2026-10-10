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
#
# Локально (разработка) — SQLite (файл sleepy.db).
# На хостинге — PostgreSQL через переменную DATABASE_URL.
#
# Если в .env есть DATABASE_URL — используется он.
# Иначе — SQLite по пути sleepy.db в корне проекта.
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Fallback: локальная SQLite
    DB_PATH = BASE_DIR / "sleepy.db"
    DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"
    connect_args = {"check_same_thread": False}
else:
    # PostgreSQL: SQLAlchemy понимает URL вида postgresql://...
    # Railway часто отдаёт postgres://, а SQLAlchemy 2.x требует postgresql://
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
    pool_pre_ping=True,     # проверка соединения перед запросом
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
    """
    Создаёт таблицы, если их ещё нет.
    Для SQLite дополнительно добавляет недостающие столбцы
    (миграции для старых баз).
    Для PostgreSQL create_all создаст всё с нуля.
    """
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    # Создаём отсутствующие таблицы
    Base.metadata.create_all(engine)

    # Миграции только для SQLite (на случай старой базы)
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

def add_user(
    telegram_id: int,
    name: str,
    age: int,
    category: str,
    schedule: str,
):
    with SessionLocal() as session:
        user = session.query(User).filter_by(
            telegram_id=telegram_id
        ).first()

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
        user = session.query(User).filter_by(
            telegram_id=telegram_id
        ).first()

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
    """Проверка: зарегистрирован ли пользователь."""
    with SessionLocal() as session:
        return (
            session.query(User)
            .filter_by(telegram_id=telegram_id)
            .first()
            is not None
        )


def get_all_users():
    """Возвращает список telegram_id всех пользователей."""
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
    """Проверяет, есть ли уже чек-ин за указанную дату."""
    if isinstance(checkin_date, str):
        checkin_date = date.fromisoformat(checkin_date)

    with SessionLocal() as session:
        return (
            session.query(Checkin)
            .filter_by(
                telegram_id=telegram_id,
                checkin_date=checkin_date,
            )
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
        ).filter(
            Checkin.telegram_id == telegram_id
        ).first()

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
        ).filter(
            Checkin.telegram_id == telegram_id
        ).scalar()

        return result


def get_checkins_for_period(
    telegram_id,
    start_date,
    end_date,
):
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
        (7.5, 4, 4, 4, 0, None, "1 чашка", "08:00", "До 30 минут", "Средняя", 2),
        (6.5, 3, 3, 3, 1, "До 30 минут", "2 чашки", "16:00", "30–60 минут", "Средняя", 3),
        (5.5, 2, 2, 2, 0, None, "3 и более", "19:00", "Больше часа", "Высокая", 5),
        (6.0, 3, 3, 3, 1, "30–60 минут", "2 чашки", "15:00", "30–60 минут", "Средняя", 4),
        (7.0, 4, 4, 4, 0, None, "1 чашка", "09:00", "До 30 минут", "Лёгкая", 2),
        (8.0, 5, 5, 5, 0, None, "Не пил(а)", None, "Не смотрел(а)", "Средняя", 1),
        (7.5, 4, 4, 5, 0, None, "1 чашка", "10:00", "До 30 минут", "Лёгкая", 2),
    ]

    with SessionLocal() as session:
        for i, data in enumerate(test_data):
            (
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

    test_data = [
        (6.5, 2, 2, 2, 4),
        (7.0, 3, 3, 3, 3),
        (7.5, 4, 4, 4, 2),
        (8.0, 5, 5, 5, 1),
        (8.0, 5, 5, 5, 1),
        (8.5, 4, 4, 4, 2),
        (7.0, 3, 3, 3, 3),

        (6.0, 2, 2, 2, 5),
        (7.0, 3, 3, 3, 4),
        (7.5, 4, 4, 4, 2),
        (8.0, 5, 5, 5, 1),
        (8.0, 5, 5, 5, 1),
        (8.5, 4, 4, 4, 2),
        (7.5, 4, 4, 4, 2),

        (6.5, 2, 2, 2, 4),
        (7.0, 3, 3, 3, 3),
        (7.5, 4, 4, 4, 2),
        (8.0, 5, 5, 5, 1),
        (8.0, 5, 5, 5, 1),
        (8.5, 4, 4, 4, 2),
        (7.0, 3, 3, 3, 3),

        (6.0, 2, 2, 2, 5),
        (7.0, 3, 3, 3, 4),
        (7.5, 4, 4, 4, 2),
        (8.0, 5, 5, 5, 1),
        (8.0, 5, 5, 5, 1),
        (8.5, 4, 4, 4, 2),
        (7.5, 4, 4, 4, 2),
    ]

    with SessionLocal() as session:
        for i, data in enumerate(test_data):
            sleep_duration, sleep_quality, mood, energy, stress = data
            checkin_date = today - timedelta(days=27 - i)

            checkin = session.query(Checkin).filter_by(
                telegram_id=telegram_id,
                checkin_date=checkin_date,
            ).first()

            values = {
                "sleep_time": "23:30",
                "wake_time": "07:30",
                "sleep_duration": sleep_duration,
                "sleep_quality": sleep_quality,
                "mood": mood,
                "energy": energy,
                "nap_taken": 0,
                "nap_duration": None,
                "caffeine": "1 чашка",
                "caffeine_time": "10:00",
                "screen_time": "До 30 минут",
                "physical_activity": "Средняя",
                "stress": stress,
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
    # Статистика для админа
    # -------------------------

    def get_active_users_count(days: int = 7) -> int:
        """Сколько уникальных пользователей писали чек-ин за N дней."""
        from datetime import date, timedelta

        start_date = date.today() - timedelta(days=days)

        with SessionLocal() as session:
            result = session.query(
                func.count(func.distinct(Checkin.telegram_id))
            ).filter(
                Checkin.checkin_date >= start_date
            ).scalar()

            return result or 0

    def get_top_users(limit: int = 5):
        """Топ-N пользователей по количеству чек-инов."""
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
        """Последние зарегистрированные пользователи."""
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

        # -------------------------
        # Статистика для админа
        # -------------------------

        def get_active_users_count(days: int = 7) -> int:
            """Сколько уникальных пользователей писали чек-ин за N дней."""
            from datetime import date, timedelta

            start_date = date.today() - timedelta(days=days)

            with SessionLocal() as session:
                result = session.query(
                    func.count(func.distinct(Checkin.telegram_id))
                ).filter(
                    Checkin.checkin_date >= start_date
                ).scalar()

                return result or 0

        def get_top_users(limit: int = 5):
            """Топ-N пользователей по количеству чек-инов."""
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
            """Последние зарегистрированные пользователи."""
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