from airflow import DAG
from airflow.operators.python import PythonOperator
import pendulum
import requests
import json
import time
from kafka import KafkaProducer

# --- НАСТРОЙКИ ---
# EMPLOYER_IDS = [3529, 78638, 1740] # СТАРЫЙ СПИСОК (Только 3 компании)
# Чтобы искать ПО ВСЕМУ РЫНКУ, мы вообще уберем фильтр по employer_id в параметрах ниже
VACANCY_TEXT = "Аналитик данных"
AREA_ID = 113 # Россия (или 1 - Москва)

# ВНУТРИ Docker мы используем внутреннее имя 'kafka' и порт 29092
KAFKA_BOOTSTRAP_SERVERS = ['kafka:29092']
KAFKA_TOPIC = 'raw_vacancies'

HEADERS = {
    "User-Agent": "SkillRadar/Airflow (tvoy_email@gmail.com)"
}

def fetch_hh_data():
    """Эта функция будет выполняться внутри Airflow"""
    print("🚀 [Airflow] Начинаем МАСШТАБНЫЙ сбор данных...")
    
    try:
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda x: json.dumps(x, ensure_ascii=False).encode('utf-8')
        )
    except Exception as e:
        print(f"❌ Не удалось подключиться к Kafka: {e}")
        return

    total_sent = 0

    # ЦИКЛ ПО СТРАНИЦАМ (Листаем до 20 страниц = 2000 вакансий)
    for page in range(20):
        print(f"🔎 Скачиваем страницу {page}...")
        
        url = "https://api.hh.ru/vacancies"
        params = {
            "text": VACANCY_TEXT,
            "area": AREA_ID,
            "per_page": 100,    # <--- БЕРЕМ МАКСИМУМ
            "page": page,       # <--- ЛИСТАЕМ СТРАНИЦЫ
            # "employer_id": ... # Убрали фильтр по конкретным компаниям, ищем везде!
        }
        
        try:
            resp = requests.get(url, params=params, headers=HEADERS)
            resp.raise_for_status()
            
            items = resp.json().get('items', [])
            if not items:
                print("🏁 Вакансии кончились, останавливаемся.")
                break # Если страница пустая, выходим из цикла
                
            ids = [item['id'] for item in items]
        except Exception as e:
            print(f"   ⚠️ Ошибка получения списка (стр {page}): {e}")
            time.sleep(5) # Если ошибка сети, чуть ждем
            continue

        # Обрабатываем каждую вакансию со страницы
        for v_id in ids:
            details_url = f"https://api.hh.ru/vacancies/{v_id}"
            try:
                # Пауза меньше, так как запросов много, но не менее 0.1 сек
                time.sleep(0.2) 
                r_det = requests.get(details_url, headers=HEADERS)
                
                if r_det.status_code == 200:
                    data = r_det.json()
                    data['search_query'] = VACANCY_TEXT
                    
                    producer.send(KAFKA_TOPIC, value=data)
                    total_sent += 1
                    
                    if total_sent % 10 == 0:
                        print(f"   ...отправлено {total_sent} шт.")
                        
            except Exception as e:
                print(f"   ⚠️ Ошибка вакансии {v_id}: {e}")

    producer.flush()
    print(f"🏁 Готово! Всего собрано и отправлено вакансий: {total_sent}")

# --- ОПИСАНИЕ DAG ---
with DAG(
    dag_id='hh_vacancy_parser',
    schedule_interval='@daily',
    start_date=pendulum.datetime(2023, 1, 1, tz="UTC"),
    catchup=False,
    tags=['skill_radar']
) as dag:

    task_fetch = PythonOperator(
        task_id='fetch_from_hh',
        python_callable=fetch_hh_data
    )

    task_fetch