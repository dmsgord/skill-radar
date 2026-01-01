import requests
import time
import json
from kafka import KafkaProducer

# --- КОНФИГУРАЦИЯ ---
EMPLOYER_IDS = [3529, 78638, 1740] 
VACANCY_TEXT = "Аналитик данных"
AREA_ID = 113

# Настройки Kafka
KAFKA_BOOTSTRAP_SERVERS = ['localhost:9092']
KAFKA_TOPIC = 'raw_vacancies'

HEADERS = {
    "User-Agent": "SkillRadar/1.0 (vash_email@gmail.com)" # <-- ВСТАВЬ EMAIL
}

# Инициализация Продюсера (Отправителя)
producer = KafkaProducer(
    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
    value_serializer=lambda x: json.dumps(x, ensure_ascii=False).encode('utf-8')
)

def get_vacancies_ids(employer_id):
    url = "https://api.hh.ru/vacancies"
    params = {
        "employer_id": employer_id,
        "text": VACANCY_TEXT,
        "area": AREA_ID,
        "per_page": 5,
        "page": 0
    }
    try:
        response = requests.get(url, params=params, headers=HEADERS)
        response.raise_for_status()
        return [item['id'] for item in response.json().get('items', [])]
    except Exception as e:
        print(f"❌ Ошибка поиска: {e}")
        return []

def get_vacancy_details(vacancy_id):
    url = f"https://api.hh.ru/vacancies/{vacancy_id}"
    try:
        time.sleep(0.5)
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 429:
            time.sleep(5)
            return None
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Ошибка деталей {vacancy_id}: {e}")
        return None

def main():
    print("🚀 Запуск отправки в Kafka...")
    
    for emp_id in EMPLOYER_IDS:
        vac_ids = get_vacancies_ids(emp_id)
        print(f"Компания {emp_id}: найдено {len(vac_ids)} вакансий.")
        
        for v_id in vac_ids:
            details = get_vacancy_details(v_id)
            
            if details:
                # ВАЖНО: Добавляем мета-информацию для фильтров
                # (Чтобы потом в ClickHouse знать, кого мы искали)
                details['search_query'] = VACANCY_TEXT 
                
                # ОТПРАВКА В KAFKA
                producer.send(KAFKA_TOPIC, value=details)
                
                print(f"   📨 Отправлено: {details.get('name')}")

    # Обязательно сбрасываем буфер перед выходом
    producer.flush()
    print("🏁 Готово. Данные в трубе.")

if __name__ == "__main__":
    main()