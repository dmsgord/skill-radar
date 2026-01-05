from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import requests
import json
import logging
import time
import os
from kafka import KafkaProducer

# --- КОНФИГУРАЦИЯ ---
HH_API_SEARCH = "https://api.hh.ru/vacancies"
KAFKA_TOPIC = "vacancies_enriched"
KAFKA_BOOTSTRAP_SERVERS = ['kafka:9092']

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2023, 1, 1),
    'retries': 2,
    'retry_delay': timedelta(minutes=2),
}

dag = DAG(
    'skillradar_production_v4',
    default_args=default_args,
    description='Парсер v4: Stable',
    schedule_interval='@daily',
    catchup=False,
)

# --- УТИЛИТЫ ---
def categorize_vacancy(name):
    if not name: return None
    name_lower = name.lower()
    stop_words = ['продаж', 'консультант', 'оператор', 'кассир', 'водитель', 'курьер', 'уборщ', 'охран', 'склад']
    if any(w in name_lower for w in stop_words): return None
    
    cats = {
        'Backend': ['backend', 'бэкенд', 'java', 'python', 'php', 'node', 'golang'],
        'Frontend': ['frontend', 'фронтенд', 'react', 'vue', 'angular', 'javascript'],
        'Mobile': ['ios', 'android', 'mobile', 'flutter'],
        'QA': ['qa', 'test', 'тестиров'],
        'DevOps': ['devops', 'sre', 'linux', 'k8s'],
        'Data': ['data', 'analyst', 'sql', 'etl'],
    }
    for cat, kws in cats.items():
        if any(k in name_lower for k in kws): return cat
    return 'Other'

# --- ЗАДАЧИ ---
def step_1_search_vacancies(**context):
    params = {'text': 'IT OR разработчик', 'area': 113, 'per_page': 100, 'page': 0}
    found = []
    for page in range(5): # Для теста 5 страниц
        params['page'] = page
        try:
            r = requests.get(HH_API_SEARCH, params=params, timeout=10)
            r.raise_for_status()
            items = r.json().get('items', [])
            if not items: break
            found.extend(items)
            time.sleep(0.5)
        except Exception as e:
            logging.error(f"Error: {e}")
            break
            
    clean = []
    for item in found:
        cat = categorize_vacancy(item.get('name'))
        if cat:
            item['custom_category'] = cat
            clean.append(item)
    return clean

def step_2_enrich_and_send(**context):
    items = context['task_instance'].xcom_pull(task_ids='search_vacancies')
    if not items: return

    # ВАЖНО: Сериализатор для JSONEachRow
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    
    count = 0
    session = requests.Session()
    
    for item in items:
        try:
            r = session.get(f"{HH_API_SEARCH}/{item['id']}", timeout=5)
            if r.status_code == 200:
                full = r.json()
                msg = {
                    'id': int(item['id']),
                    'published_at': item['published_at'], # ClickHouse сам распарсит ISO строку
                    'name': item['name'],
                    'category': item.get('custom_category', 'Other'),
                    'employer_name': (item.get('employer') or {}).get('name', 'Unknown'),
                    'salary_from': (item.get('salary') or {}).get('from'),
                    'salary_to': (item.get('salary') or {}).get('to'),
                    'currency': (item.get('salary') or {}).get('currency'),
                    'gross': 1 if (item.get('salary') or {}).get('gross') else 0, # Int для ClickHouse
                    'experience': (full.get('experience') or {}).get('name', ''),
                    'schedule': (full.get('schedule') or {}).get('name', ''),
                    'employment': (full.get('employment') or {}).get('name', ''),
                    'key_skills': [s['name'] for s in full.get('key_skills', [])],
                    'professional_roles': [r['name'] for r in full.get('professional_roles', [])],
                    'description': full.get('description', ''),
                    'alternate_url': item.get('alternate_url', '')
                }
                producer.send(KAFKA_TOPIC, msg)
                count += 1
            time.sleep(0.2)
        except Exception as e:
            logging.error(f"Err {item['id']}: {e}")

    producer.flush()
    logging.info(f"Sent {count} vacancies")

search_task = PythonOperator(task_id='search_vacancies', python_callable=step_1_search_vacancies, dag=dag)
enrich_task = PythonOperator(task_id='enrich_and_send', python_callable=step_2_enrich_and_send, provide_context=True, dag=dag)

search_task >> enrich_task