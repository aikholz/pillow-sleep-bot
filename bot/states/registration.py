from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    name = State()
    age = State()
    category = State()
    schedule = State()