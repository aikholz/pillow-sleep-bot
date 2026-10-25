from aiogram.fsm.state import State, StatesGroup


class CheckinStates(StatesGroup):
    sleep_time = State()
    wake_time = State()
    sleep_quality = State()
    mood = State()
    energy = State()
    nap = State()
    nap_duration = State()
    caffeine = State()
    screen_time = State()
    physical_activity = State()
    stress = State()
    caffeine_time = State()

    # Тип смены
    shift_type = State()

    # НОВОЕ: Учебная нагрузка (когда учился)
    study_load = State()