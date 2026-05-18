from aiogram.fsm.state import State, StatesGroup


class CustomerBookingFlow(StatesGroup):
    choosing_main_service = State()
    choosing_addons = State()
    choosing_date = State()
    choosing_slot = State()
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_vehicle_plate = State()
    confirming = State()
