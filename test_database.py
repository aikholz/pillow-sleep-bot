from bot.database.db import (
    init_db,
    get_user_statistics,
    get_checkins_for_analysis,
)

init_db()

print("База успешно инициализирована.")
print("Проверка завершена.")