from airflow import DAG
from airflow.operators.python import PythonOperator
import pendulum
import requests
import json
import time
from kafka import KafkaProducer

# --- НАСТРОЙКИ ---
EMPLOYER_IDS = [3529, 78638, 1740]  # Сбер, Т-Банк, Яндекс
VACANCY_TEXT = "Аналитик данных"
AREA_ID = 113

# ВНУТРИ Docker мы используем внутреннее имя 'kafka' и порт 29092
KAFKA_BOOTSTRAP_SERVERS = ['kafka:29092']
KAFKA_TOPIC = 'raw_vacancies'

HEADERS = {
    "User-Agent": "SkillRadar/Airflow (tvoy_email@gmail.com)"
}

def fetch_hh_data():
    """Эта функция будет выполняться внутри Airflow"""
    print("🚀 [Airflow] Начинаем сбор данных...")
    
    # Подключаемся к Kafka (внутри сети Docker)
    try:
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda x: json.dumps(x, ensure_ascii=False).encode('utf-8')
        )
    except Exception as e:
        print(f"❌ Не удалось подключиться к Kafka: {e}")
        return

    total_sent = 0

    for emp_id in EMPLOYER_IDS:
        print(f"🔎 Обрабатываем компанию {emp_id}...")
        
        # 1. Получаем ID вакансий
        url = "https://api.hh.ru/vacancies"
        params = {
            "employer_id": emp_id,
            "text": VACANCY_TEXT,
            "area": AREA_ID,
            "per_page": 5, # Берем по 5 штук для теста
            "page": 0
        }
        
        try:
            resp = requests.get(url, params=params, headers=HEADERS)
            resp.raise_for_status()
            items = resp.json().get('items', [])
            ids = [item['id'] for item in items]
        except Exception as e:
            print(f"   ⚠️ Ошибка списка вакансий: {e}")
            continue

        # 2. Получаем детали и отправляем
        for v_id in ids:
            details_url = f"https://api.hh.ru/vacancies/{v_id}"
            try:
                time.sleep(0.5) # Вежливость
                r_det = requests.get(details_url, headers=HEADERS)
                if r_det.status_code == 200:
                    data = r_det.json()
                    data['search_query'] = VACANCY_TEXT
                    
                    # Отправка в Kafka
                    producer.send(KAFKA_TOPIC, value=data)
                    total_sent += 1
            except Exception as e:
                print(f"   ⚠️ Ошибка вакансии {v_id}: {e}")

    producer.flush()
    print(f"🏁 Готово! Отправлено вакансий: {total_sent}")

# --- ОПИСАНИЕ DAG (ИНСТРУКЦИЯ) ---
with DAG(
    dag_id='hh_vacancy_parser',      # Имя робота в списке
    schedule_interval='@daily',      # Запускать раз в день
    start_date=pendulum.datetime(2023, 1, 1, tz="UTC"),
    catchup=False,                   # Не пытаться запустить за прошлые годы
    tags=['skill_radar']
) as dag:

    # Задача 1: Запустить Python функцию
    task_fetch = PythonOperator(
        task_id='fetch_from_hh',
        python_callable=fetch_hh_data
    )

    task_fetch