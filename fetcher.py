import requests
import time
import json

# --- КОНФИГУРАЦИЯ ---
# ID компаний: 3529 (Сбер), 78638 (Т-Банк), 1740 (Яндекс)
EMPLOYER_IDS = [3529, 78638, 1740] 
VACANCY_TEXT = "Аналитик данных"
AREA_ID = 113  # 113 = Вся Россия

# Заголовки (Представляемся сайту)
HEADERS = {
    "User-Agent": "SkillRadar/1.0 (tvoy_email@gmail.com)" 
}

def get_vacancies_ids(employer_id):
    """
    Шаг 1. Запрашиваем список вакансий компании.
    Возвращает список ID (например: ['12345', '67890'])
    """
    url = "https://api.hh.ru/vacancies"
    params = {
        "employer_id": employer_id,
        "text": VACANCY_TEXT,
        "area": AREA_ID,
        "per_page": 5,  # Для теста берем всего 5 штук с компании
        "page": 0
    }
    
    print(f"🔎 [Компания {employer_id}] Ищем вакансии '{VACANCY_TEXT}'...")
    
    try:
        response = requests.get(url, params=params, headers=HEADERS)
        response.raise_for_status() # Проверка на ошибки (404, 500)
        
        data = response.json()
        items = data.get('items', [])
        ids = [item['id'] for item in items]
        
        print(f"   ✅ Найдено: {len(ids)} вакансий.")
        return ids
        
    except Exception as e:
        print(f"   ❌ Ошибка поиска: {e}")
        return []

def get_vacancy_details(vacancy_id):
    """
    Шаг 2. Скачиваем подробности по одной вакансии.
    Возвращает JSON с полными данными (навыки, описание, даты).
    """
    url = f"https://api.hh.ru/vacancies/{vacancy_id}"
    
    try:
        # Пауза перед запросом (Вежливость!)
        time.sleep(0.5)
        
        response = requests.get(url, headers=HEADERS)
        
        # Если превысили лимит (429) - ждем и возвращаем None
        if response.status_code == 429:
            print("   ⏳ Лимит запросов. Спим 5 сек...")
            time.sleep(5)
            return None
            
        response.raise_for_status()
        return response.json()
        
    except Exception as e:
        print(f"   ❌ Ошибка получения деталей {vacancy_id}: {e}")
        return None

def main():
    print("🚀 Запуск сборщика данных...")
    print("="*40)

    # 1. Бежим по списку компаний
    for emp_id in EMPLOYER_IDS:
        vac_ids = get_vacancies_ids(emp_id)
        
        # 2. Бежим по найденным ID вакансий
        for v_id in vac_ids:
            details = get_vacancy_details(v_id)
            
            if details:
                # 3. Выводим результат (Тест)
                name = details.get('name')
                skills = [s['name'] for s in details.get('key_skills', [])]
                # Берем первые 50 символов описания для проверки
                desc_preview = details.get('description', '')[:50] + "..."
                
                print(f"   📄 [{v_id}] {name}")
                print(f"      💡 Навыки: {skills}")
                print(f"      📝 Описание: {desc_preview}")
                print("-" * 20)

    print("\n🏁 Работа завершена.")

if __name__ == "__main__":
    main()