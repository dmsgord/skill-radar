"""
Настройки проекта SkillRadar
Здесь хранятся списки компаний, стоп-слова и конфигурация.
"""
from airflow.models import Variable

# ============================================
# 1. СПИСОК ЦЕЛЕВЫХ КОМПАНИЙ (ID с HH.ru)
# ============================================
# Сбер, Т-Банк, Яндекс, Ozon, WB, МТС, VK, Авито
DEFAULT_COMPANIES = [3529, 78638, 1740, 4181, 39305, 3776, 2180, 1122]

# Пытаемся взять список из Airflow Variable (если настроено в UI),
# иначе берем список по умолчанию.
try:
    TARGET_COMPANIES = Variable.get(
        "HH_TARGET_COMPANIES",
        default_var=DEFAULT_COMPANIES,
        deserialize_json=True
    )
except:
    TARGET_COMPANIES = DEFAULT_COMPANIES


# ============================================
# 2. ЧЕРНЫЙ СПИСОК (GATEKEEPER)
# ============================================
# Если эти слова есть в названии - вакансия игнорируется
DEFAULT_EXCLUDED = [
    "юрист", "lawyer", "legal", "counsel",
    "бухгалтер", "accountant", "счетовод",
    "продавец", "sales", "продаж", "кассир",
    "водитель", "driver", "курьер", "логист",
    "уборщик", "cleaner", "клининг",
    "официант", "повар", "cook", "бармен",
    "секретарь", "secretary", "делопроизводитель",
    "охранник", "security", "сторож", "вахтер"
]

try:
    EXCLUDED_KEYWORDS = Variable.get(
        "HH_EXCLUDED_KEYWORDS",
        default_var=DEFAULT_EXCLUDED,
        deserialize_json=True
    )
except:
    EXCLUDED_KEYWORDS = DEFAULT_EXCLUDED


# ============================================
# 3. АВТОРИЗАЦИЯ (ТОКЕН)
# ============================================
# Берем токен из Airflow Variables. Если нет - None (анонимный режим)
try:
    HH_API_TOKEN = Variable.get("HH_API_TOKEN", default_var=None)
except:
    HH_API_TOKEN = None