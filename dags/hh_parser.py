"""
SkillRadar ETL Pipeline v3.1
Architecture: ELT (Extract-Load-Transform) with Auth Support
"""

import json
import os
import re
import html
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

import pendulum
import requests
from kafka import KafkaProducer

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.log.logging_mixin import LoggingMixin
from airflow.models import Variable

# ИМПОРТ НАСТРОЕК ИЗ СОСЕДНЕГО ФАЙЛА
try:
    from settings import TARGET_COMPANIES, EXCLUDED_KEYWORDS, HH_API_TOKEN
except ImportError:
    # Fallback если запуск не из Airflow окружения
    TARGET_COMPANIES = []
    EXCLUDED_KEYWORDS = []
    HH_API_TOKEN = None

# ============================================
# CONFIGURATION CLASS
# ============================================

@dataclass
class Config:
    # Данные берутся из settings.py
    TARGET_COMPANIES: List[int] = None
    EXCLUDED_KEYWORDS: List[str] = None
    HH_API_TOKEN: Optional[str] = None
    
    AREA_ID: int = 113  # Россия
    KAFKA_TOPIC: str = "raw_vacancies"
    
    # Лимиты и тайминги
    MAX_PAGES_PER_COMPANY: int = 5    # Max 500 вакансий на компанию
    ITEMS_PER_PAGE: int = 100
    REQUEST_TIMEOUT: int = 15
    
    # Задержки (безопасные для анонимов)
    DELAY_BETWEEN_PAGES: tuple = (1.0, 2.0)
    DELAY_DETAIL_REQUEST: float = 1.5
    MAX_RETRIES: int = 3
    
    USER_AGENT: str = "SkillRadar/3.1 (academic_research)"
    
    def __post_init__(self):
        # Привязываем импортированные настройки
        self.TARGET_COMPANIES = TARGET_COMPANIES
        self.EXCLUDED_KEYWORDS = EXCLUDED_KEYWORDS
        self.HH_API_TOKEN = HH_API_TOKEN
        
        self.KAFKA_BOOTSTRAP_SERVERS = [
            Variable.get("KAFKA_BOOTSTRAP_SERVERS", default_var="kafka:29092")
        ]

config = Config()
logger = LoggingMixin().log

# ============================================
# DATA MODELS & UTILS
# ============================================

@dataclass
class VacancyData:
    id: int
    name: str
    area_name: str
    employer_name: str
    employer_id: int
    published_at: str
    salary_from: Optional[float]
    salary_to: Optional[float]
    currency: Optional[str]
    key_skills: List[str]
    description: str       # Полный текст
    
    def to_dict(self) -> Dict:
        return asdict(self)

class TextProcessor:
    TAG_RE = re.compile(r'<[^>]+>')
    WHITESPACE_RE = re.compile(r'\s+')

    @classmethod
    def clean_html(cls, raw_html: str) -> str:
        if not raw_html: return ""
        text = html.unescape(raw_html)
        text = cls.TAG_RE.sub(' ', text)
        return cls.WHITESPACE_RE.sub(' ', text).strip()

# ============================================
# API CLIENT (WITH AUTH)
# ============================================

class HHAPIClient:
    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        
        headers = {
            'User-Agent': config.USER_AGENT,
            'Accept': 'application/json'
        }
        
        # Если есть токен - добавляем его
        if config.HH_API_TOKEN:
            headers['Authorization'] = f'Bearer {config.HH_API_TOKEN}'
            logger.info("🔑 API Client: AUTHENTICATED mode")
        else:
            logger.info("👤 API Client: ANONYMOUS mode")
            
        self.session.headers.update(headers)
        
    def _request(self, url: str, params: dict = None):
        for attempt in range(self.config.MAX_RETRIES):
            try:
                response = self.session.get(
                    url, params=params, timeout=self.config.REQUEST_TIMEOUT
                )
                
                # Rate Limit (429)
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"⏳ Rate limit. Sleeping {retry_after}s...")
                    time.sleep(retry_after)
                    continue
                
                # Token Expired (403)
                if response.status_code == 403 and self.config.HH_API_TOKEN:
                    logger.error("⛔ Token expired or forbidden!")
                    raise Exception("Auth Token Forbidden")

                response.raise_for_status()
                return response
                
            except requests.exceptions.RequestException as e:
                time.sleep(2 ** attempt)
        return None

    def get_company_vacancies(self, company_id: int, page: int = 0):
        params = {
            'employer_id': company_id,
            'area': self.config.AREA_ID,
            'per_page': self.config.ITEMS_PER_PAGE,
            'page': page
        }
        resp = self._request('https://api.hh.ru/vacancies', params)
        return resp.json() if resp else None

    def get_details(self, vacancy_id: str):
        resp = self._request(f'https://api.hh.ru/vacancies/{vacancy_id}')
        return resp.json() if resp else None

# ============================================
# ETL LOGIC
# ============================================

class VacancyTransformer:
    @staticmethod
    def transform(raw_data: Dict) -> VacancyData:
        try:
            vacancy_id = int(raw_data['id'])
        except:
            raise ValueError("Invalid ID")
            
        salary = raw_data.get('salary') or {}
        skills = [s.get('name') for s in raw_data.get('key_skills', []) if s.get('name')]
        clean_desc = TextProcessor.clean_html(raw_data.get('description', ''))
        employer = raw_data.get('employer', {})
        
        return VacancyData(
            id=vacancy_id,
            name=raw_data.get('name', '') or 'Unknown',
            area_name=raw_data.get('area', {}).get('name', 'Unknown'),
            employer_name=employer.get('name', 'Unknown'),
            employer_id=int(employer.get('id', 0)),
            published_at=raw_data.get('published_at', ''),
            salary_from=salary.get('from'),
            salary_to=salary.get('to'),
            currency=salary.get('currency'),
            key_skills=skills,
            description=clean_desc
        )

class KafkaPublisher:
    def __init__(self, config: Config):
        self.producer = KafkaProducer(
            bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode('utf-8'),
            compression_type='gzip',
            acks='all',
            retries=3
        )
    def send(self, data: VacancyData):
        self.producer.send(config.KAFKA_TOPIC, value=data.to_dict()).get(timeout=10)
    def close(self):
        self.producer.flush(); self.producer.close()

class VacancyCollector:
    def __init__(self, config: Config):
        self.config = config
        self.client = HHAPIClient(config)
        self.publisher = KafkaPublisher(config)
        self.processed_ids = set()
        self.metrics = {'found': 0, 'sent': 0, 'excluded': 0, 'errors': 0}

    def collect(self):
        logger.info(f"Targets: {len(self.config.TARGET_COMPANIES)} companies")
        try:
            for cid in self.config.TARGET_COMPANIES:
                self._process_company(cid)
        finally:
            self.publisher.close()
            logger.info(f"Stats: {self.metrics}")

    def _process_company(self, company_id: int):
        page = 0
        while page < self.config.MAX_PAGES_PER_COMPANY:
            data = self.client.get_company_vacancies(company_id, page)
            if not data or not data.get('items'): break
            
            items = data['items']
            logger.info(f"Company {company_id}: Page {page}, Items {len(items)}")
            self.metrics['found'] += len(items)

            for item in items:
                self._process_vacancy(item)
            
            if page >= data.get('pages', 0) - 1: break
            page += 1
            time.sleep(random.uniform(*self.config.DELAY_BETWEEN_PAGES))

    def _process_vacancy(self, item: dict):
        v_id = str(item['id'])
        if v_id in self.processed_ids: return
        self.processed_ids.add(v_id)
        
        # Blacklist check
        name = item.get('name', '').lower()
        if any(w in name for w in self.config.EXCLUDED_KEYWORDS):
            self.metrics['excluded'] += 1
            return

        time.sleep(self.config.DELAY_DETAIL_REQUEST)
        details = self.client.get_details(v_id)
        if details:
            try:
                self.publisher.send(VacancyTransformer.transform(details))
                self.metrics['sent'] += 1
            except Exception: self.metrics['errors'] += 1

# ============================================
# AIRFLOW DAG
# ============================================

def run_etl(**context): 
    VacancyCollector(config).collect()

default_args = {
    'owner': 'skillradar',
    'start_date': pendulum.parse('2025-01-01', tz='UTC'),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG('skillradar_hh_parser', default_args=default_args, schedule_interval='0 3 * * *', catchup=False) as dag:
    PythonOperator(task_id='collect_vacancies', python_callable=run_etl)