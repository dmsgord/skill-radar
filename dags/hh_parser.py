from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from datetime import datetime, timedelta, timezone
import requests
import json
import logging
import time
import random
import re
import os
import backoff
from bs4 import BeautifulSoup
from kafka import KafkaProducer
from functools import lru_cache

# Импортируем локальный settings.py
import settings

# --- КОНФИГУРАЦИЯ ---
HH_API_VACANCIES = "https://api.hh.ru/vacancies"
KAFKA_TOPIC = "vacancies_enriched"
KAFKA_SERVERS = ['kafka:9092'] # Исправил опечатку

# User-Agent для "Дзен" режима
HH_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json'
}

default_args = {
    'owner': 'airflow',
    'start_date': datetime(2023, 1, 1),
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=24) # Дзен-режим может быть долгим
}

dag = DAG(
    'skillradar_zen_v10',
    default_args=default_args,
    description='Zen Parser v10: Fixes, UTC Time, Regex Mining',
    schedule_interval='@daily',
    catchup=False,
    max_active_runs=1
)

# --- STATE MANAGEMENT (POSTGRES) ---
class StateManager:
    def __init__(self):
        self.hook = PostgresHook(postgres_conn_id='airflow_db')
        self._init_table()

    def _init_table(self):
        # Используем TIMESTAMP WITH TIME ZONE (TIMESTAMPTZ)
        sql = """
        CREATE TABLE IF NOT EXISTS parsing_state (
            employer_id BIGINT PRIMARY KEY,
            employer_name TEXT,
            last_published_at TIMESTAMPTZ, 
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
        self.hook.run(sql)

    def get_last_date(self, emp_id):
        sql = "SELECT last_published_at FROM parsing_state WHERE employer_id = %s"
        row = self.hook.get_first(sql, parameters=(emp_id,))
        if row and row[0]:
            return row[0] # Возвращает datetime с tzinfo (обычно UTC)
        return None

    def update_state(self, emp_id, name, last_pub_dt):
        sql = """
        INSERT INTO parsing_state (employer_id, employer_name, last_published_at, updated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (employer_id) DO UPDATE SET
            last_published_at = GREATEST(parsing_state.last_published_at, EXCLUDED.last_published_at),
            updated_at = NOW();
        """
        self.hook.run(sql, parameters=(emp_id, name, last_pub_dt))

# --- УТИЛИТЫ ---

@backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=10)
def safe_request(url, params=None):
    """Безопасный запрос с экспоненциальным ожиданием при ошибках"""
    r = requests.get(url, params=params, headers=HH_HEADERS, timeout=30)
    r.raise_for_status()
    return r

def clean_html(raw_html):
    if not raw_html: return ""
    return BeautifulSoup(raw_html, "html.parser").get_text(separator=" ").strip()

@lru_cache(maxsize=1)
def get_compiled_skills():
    """
    Компилирует Regex один раз. 
    Превращает ['go', 'java'] в r'\b(go|java)\b' (с границами слов).
    """
    compiled = {}
    for group, skills in settings.SKILL_DICTIONARY.items():
        # Экранируем спецсимволы (c++, c#)
        escaped_skills = [re.escape(s) for s in skills]
        # Собираем паттерн: границы слова + (или|или) + границы
        # Используем (?i) для игнора регистра
        pattern = re.compile(r'\b(' + '|'.join(escaped_skills) + r')\b', re.IGNORECASE)
        compiled[group] = pattern
    return compiled

def deep_skill_mining(description_text):
    """Поиск навыков с помощью Regex"""
    if not description_text: return []
    
    patterns = get_compiled_skills()
    found = set()
    
    for group, pattern in patterns.items():
        # findall вернет список совпадений
        matches = pattern.findall(description_text)
        for m in matches:
            found.add(m.lower()) # Сохраняем в нижнем регистре
            
    return list(found)

def categorize_and_filter(name):
    """
    Возвращает категорию или None (если стоп-слово).
    Сначала проверяем стоп-слова, потом категории.
    """
    name_lower = name.lower()
    
    # 1. Stop-words (Regex search)
    for bad_regex in settings.STOP_WORDS:
        if re.search(bad_regex, name_lower, re.IGNORECASE):
            return None # Drop it
            
    # 2. Categories
    for cat, kws in settings.CATEGORIES_RULES.items():
        if any(k in name_lower for k in kws):
            return cat
            
    return 'Uncategorized' # Keep it

def random_sleep(min_s=1.0, max_s=3.0):
    time.sleep(random.uniform(min_s, max_s))

# --- ОСНОВНАЯ ЗАДАЧА ---
def run_parser_v10(**context):
    state = StateManager()
    producer = None
    
    try:
        producer = KafkaProducer(
            bootstrap_servers=KKA_SERVERS, # В коде выше мы исправили константу, но используем переменную из imports
            # KafkaProducer требует строку или список. Исправим на KAFKA_SERVERS из конфига
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
    except NameError: 
         # Если вдруг забыли поправить константу, хардкод для надежности
         producer = KafkaProducer(
            bootstrap_servers=['kafka:9092'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

    logging.info(f"🧘‍♂️ Zen Parser v10 Started. Companies: {len(settings.TARGET_COMPANIES)}")
    
    for emp_id, emp_name in settings.TARGET_COMPANIES.items():
        logging.info(f"🏢 START: {emp_name} (ID: {emp_id})")
        
        # 1. WATERMARK
        last_date = state.get_last_date(emp_id)
        if last_date:
            # Важно: HH требует ISO формат с таймзоной. 
            # last_date из Postgres уже с TZ (UTC).
            date_from = last_date.isoformat()
            logging.info(f"   Delta load: > {date_from}")
        else:
            # 30 дней назад, с UTC таймзоной
            date_from = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            logging.info(f"   First load: > {date_from} (30 days)")

        # 2. ITERATE
        page = 0
        total_pages = 1 # Заглушка, обновится после первого запроса
        max_pub_date = None
        new_count = 0
        
        while page < total_pages:
            params = {
                'employer_id': emp_id,
                'date_from': date_from,
                'per_page': 100,
                'page': page,
                'order_by': 'publication_time', # Сортировка по времени
                'sort_order': 'asc'             # От старых к новым (чтобы ватермарк рос безопасно)
            }
            
            try:
                random_sleep(1.0, 2.5) # Пауза перед листингом
                resp = safe_request(HH_API_VACANCIES, params=params)
                data = resp.json()
                
                # Обновляем инфо о страницах
                total_pages = data.get('pages', 0)
                items = data.get('items', [])
                
                if not items:
                    break
                
                for item in items:
                    # Трекаем самую свежую дату для сохранения стейта
                    # HH отдает: "2023-10-05T12:00:00+0300"
                    pub_dt = datetime.fromisoformat(item['published_at'])
                    if not max_pub_date or pub_dt > max_pub_date:
                        max_pub_date = pub_dt

                    # ФИЛЬТРАЦИЯ
                    category = categorize_and_filter(item.get('name', ''))
                    if not category:
                        continue # Стоп-лист
                    
                    # ДЕТАЛИЗАЦИЯ
                    random_sleep(0.5, 1.5) # Пауза перед чтением детализации
                    
                    try:
                        full = safe_request(f"{HH_API_VACANCIES}/{item['id']}").json()
                        
                        desc_clean = clean_html(full.get('description', ''))
                        extracted = deep_skill_mining(desc_clean)
                        hh_keys = [s['name'] for s in full.get('key_skills', [])]
                        
                        # Собираем ПОЛНЫЙ пакет данных (как просило ревью)
                        msg = {
                            'id': int(item['id']),
                            'employer_id': emp_id,
                            'employer_name': emp_name,
                            'url': item.get('alternate_url'),
                            'published_at': item['published_at'], # Оставляем строку ISO
                            'name': item['name'],
                            'category': category,
                            
                            # Деньги
                            'salary_from': (item.get('salary') or {}).get('from'),
                            'salary_to': (item.get('salary') or {}).get('to'),
                            'currency': (item.get('salary') or {}).get('currency'),
                            'gross': 1 if (item.get('salary') or {}).get('gross') else 0,
                            
                            # Мета
                            'experience_id': (full.get('experience') or {}).get('id'),
                            'schedule': (full.get('schedule') or {}).get('name'),
                            'employment': (full.get('employment') or {}).get('name'),
                            'area_name': (full.get('area') or {}).get('name'),
                            
                            # Скиллы
                            'key_skills': hh_keys,
                            'extracted_skills': extracted,
                            'description': desc_clean
                        }
                        
                        producer.send(KAFKA_TOPIC, msg)
                        new_count += 1
                        
                    except Exception as e:
                        logging.error(f"Error fetching details {item['id']}: {e}")
                        continue
                
                logging.info(f"   Page {page+1}/{total_pages} done. New: {new_count}")
                page += 1
                
            except Exception as e:
                logging.error(f"Critical error on {emp_name} page {page}: {e}")
                # Если упали - не идем дальше по этой компании, но сохраним то, что успели (если сортировка была правильной)
                break

        # КОНЕЦ КОМПАНИИ
        producer.flush()
        if max_pub_date:
            state.update_state(emp_id, emp_name, max_pub_date)
            logging.info(f"✅ {emp_name} Finished. State updated to {max_pub_date}")
        else:
            logging.info(f"💤 {emp_name} No new vacancies.")
            
        logging.info("☕ Coffee break 10s...")
        time.sleep(10)

    if producer:
        producer.close()

parser_task = PythonOperator(
    task_id='zen_parser_v10',
    python_callable=run_parser_v10,
    dag=dag
)