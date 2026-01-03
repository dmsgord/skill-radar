"""
SkillRadar ETL Pipeline - HeadHunter Vacancy Parser
====================================================
Назначение: Сбор вакансий с HH.ru API и отправка в Kafka
Автор: SkillRadar Team
Версия: 2.0.0
"""

import json
import os
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict

import pendulum
import requests
from kafka import KafkaProducer
from kafka.errors import KafkaError

from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from airflow.utils.log.logging_mixin import LoggingMixin

# ============================================
# КОНФИГУРАЦИЯ
# ============================================

@dataclass
class Config:
    """Централизованная конфигурация проекта"""
    
    # Роли для поиска
    TARGET_ROLES: List[str] = None
    
    # ID компаний HH.ru
    TARGET_COMPANIES: List[int] = None
    
    # Регион (113 = Россия)
    AREA_ID: int = 113
    
    # Kafka настройки
    KAFKA_BOOTSTRAP_SERVERS: List[str] = None
    KAFKA_TOPIC: str = "raw_vacancies"
    
    # Лимиты API
    MAX_PAGES_PER_QUERY: int = 5
    ITEMS_PER_PAGE: int = 20
    REQUEST_TIMEOUT: int = 10
    
    # Rate limiting (HH.ru ограничения)
    DELAY_BETWEEN_PAGES: tuple = (0.3, 0.6)
    DELAY_DETAIL_REQUEST: float = 1.1  # Минимум 1 секунда для деталей
    
    # Retry настройки
    MAX_RETRIES: int = 3
    RETRY_BACKOFF_FACTOR: int = 2
    
    # User-Agent для API
    USER_AGENT: str = "SkillRadar/2.0 (academic_research; contact@skillradar.local)"
    
    def __post_init__(self):
        """Инициализация значений по умолчанию"""
        if self.TARGET_ROLES is None:
            self.TARGET_ROLES = [
                "Аналитик данных",
                "Data Engineer",
                "Product Manager",
                "Java Developer",
                "QA Automation Engineer",
                "Python Developer",
                "DevOps Engineer"
            ]
        
        if self.TARGET_COMPANIES is None:
            self.TARGET_COMPANIES = [
                3529,   # Сбер
                78638,  # Т-Банк (Тинькофф)
                1740,   # Яндекс
                4181,   # Ozon
                39305,  # Wildberries
                3776,   # МТС
                2180,   # VK
                1122,   # Авито
            ]
        
        if self.KAFKA_BOOTSTRAP_SERVERS is None:
            kafka_servers = Variable.get(
                "KAFKA_BOOTSTRAP_SERVERS", 
                default_var=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
            )
            self.KAFKA_BOOTSTRAP_SERVERS = [kafka_servers]

# Глобальный конфиг и logger
config = Config()
logger = LoggingMixin().log

# ============================================
# МОДЕЛИ ДАННЫХ
# ============================================

@dataclass
class VacancyData:
    """Модель данных вакансии для ClickHouse"""
    id: int
    name: str
    area_name: str
    employer_name: str
    published_at: str  # ISO 8601 формат для ClickHouse
    salary_from: Optional[float]
    salary_to: Optional[float]
    currency: Optional[str]
    key_skills: List[str]
    search_query: str
    
    def to_dict(self) -> Dict:
        """Конвертация в словарь для JSON сериализации"""
        return asdict(self)

# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

class APIRateLimitError(Exception):
    """Исключение при превышении rate limit"""
    pass

class VacancyTransformer:
    """Трансформация данных вакансий"""
    
    @staticmethod
    def transform(raw_data: Dict, search_query: str) -> VacancyData:
        """
        Преобразование сырых данных HH.ru в структурированный формат
        
        Args:
            raw_data: Сырые данные от API
            search_query: Поисковый запрос (роль)
            
        Returns:
            VacancyData object
            
        Raises:
            ValueError: Если данные невалидны
        """
        try:
            vacancy_id = int(raw_data['id'])
        except (KeyError, ValueError, TypeError) as e:
            raise ValueError(f"Invalid vacancy ID: {e}")
        
        # Зарплата
        salary = raw_data.get('salary') or {}
        salary_from = salary.get('from')
        salary_to = salary.get('to')
        
        # Навыки
        skills = [
            skill['name'] 
            for skill in raw_data.get('key_skills', []) 
            if skill.get('name')
        ]
        
        # ВАЖНО: published_at оставляем как строку в ISO 8601
        # ClickHouse сам распарсит её через parseDateTime64BestEffort
        published_at = raw_data.get('published_at', '')
        
        return VacancyData(
            id=vacancy_id,
            name=raw_data.get('name', '').strip() or 'Без названия',
            area_name=raw_data.get('area', {}).get('name', 'Unknown'),
            employer_name=raw_data.get('employer', {}).get('name', 'Unknown'),
            published_at=published_at,
            salary_from=float(salary_from) if salary_from is not None else None,
            salary_to=float(salary_to) if salary_to is not None else None,
            currency=salary.get('currency'),
            key_skills=skills,
            search_query=search_query
        )

class HHAPIClient:
    """Клиент для работы с API HeadHunter"""
    
    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': config.USER_AGENT
        })
        
    def _request_with_retry(
        self, 
        url: str, 
        params: Optional[Dict] = None,
        max_retries: Optional[int] = None
    ) -> Optional[requests.Response]:
        """HTTP запрос с повторами при ошибках"""
        max_retries = max_retries or self.config.MAX_RETRIES
        
        for attempt in range(max_retries):
            try:
                response = self.session.get(
                    url, 
                    params=params, 
                    timeout=self.config.REQUEST_TIMEOUT
                )
                
                # Обработка rate limit
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(
                        f"⏳ Rate limit reached. Waiting {retry_after}s... "
                        f"(Attempt {attempt + 1}/{max_retries})"
                    )
                    
                    if attempt < max_retries - 1:
                        time.sleep(retry_after)
                        continue
                    else:
                        raise APIRateLimitError(f"Rate limit exceeded after {max_retries} retries")
                
                response.raise_for_status()
                return response
                
            except requests.exceptions.RequestException as e:
                wait_time = self.config.RETRY_BACKOFF_FACTOR ** attempt
                
                if attempt == max_retries - 1:
                    logger.error(f"❌ Request failed after {max_retries} attempts: {e}")
                    return None
                
                logger.warning(
                    f"⚠️ Request failed (attempt {attempt + 1}/{max_retries}). "
                    f"Retrying in {wait_time}s... Error: {e}"
                )
                time.sleep(wait_time)
        
        return None
    
    def search_vacancies(
        self, 
        role: str, 
        company_id: int, 
        page: int = 0
    ) -> Optional[Dict]:
        """Поиск вакансий по роли и компании"""
        params = {
            'text': role,
            'employer_id': company_id,
            'area': self.config.AREA_ID,
            'per_page': self.config.ITEMS_PER_PAGE,
            'page': page
        }
        
        response = self._request_with_retry(
            'https://api.hh.ru/vacancies',
            params=params
        )
        
        return response.json() if response else None
    
    def get_vacancy_details(self, vacancy_id: str) -> Optional[Dict]:
        """Получение детальной информации о вакансии"""
        response = self._request_with_retry(
            f'https://api.hh.ru/vacancies/{vacancy_id}'
        )
        
        return response.json() if response else None

class KafkaPublisher:
    """Публикация данных в Kafka"""
    
    def __init__(self, config: Config):
        self.config = config
        self.producer = None
        self._init_producer()
    
    def _init_producer(self):
        """Инициализация Kafka producer"""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.config.KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(
                    v, ensure_ascii=False
                ).encode('utf-8'),
                acks='all',
                retries=3,
                max_in_flight_requests_per_connection=1,
                compression_type='gzip'
            )
            logger.info(
                f"✅ Kafka producer initialized: "
                f"{self.config.KAFKA_BOOTSTRAP_SERVERS}"
            )
        except Exception as e:
            logger.error(f"❌ Failed to initialize Kafka producer: {e}")
            raise
    
    def send(self, vacancy: VacancyData) -> bool:
        """Отправка вакансии в Kafka"""
        try:
            future = self.producer.send(
                self.config.KAFKA_TOPIC,
                value=vacancy.to_dict()
            )
            future.get(timeout=10)
            return True
            
        except KafkaError as e:
            logger.error(f"❌ Failed to send vacancy {vacancy.id} to Kafka: {e}")
            return False
    
    def close(self):
        """Закрытие producer"""
        if self.producer:
            self.producer.flush()
            self.producer.close()
            logger.info("🔒 Kafka producer closed")

# ============================================
# ОСНОВНАЯ ЛОГИКА ETL
# ============================================

class VacancyCollector:
    """Основной класс сборщика вакансий"""
    
    def __init__(self, config: Config):
        self.config = config
        self.api_client = HHAPIClient(config)
        self.kafka_publisher = KafkaPublisher(config)
        self.transformer = VacancyTransformer()
        
        # Статистика
        self.stats = {
            'processed_ids': set(),
            'sent_count': 0,
            'error_count': 0,
            'skipped_duplicates': 0,
            'start_time': None,
            'end_time': None
        }
    
    def collect(self):
        """Основной метод сбора вакансий"""
        self.stats['start_time'] = datetime.now()
        
        logger.info(
            f"🚀 Starting vacancy collection:\n"
            f"   Roles: {len(self.config.TARGET_ROLES)}\n"
            f"   Companies: {len(self.config.TARGET_COMPANIES)}\n"
            f"   Max pages per query: {self.config.MAX_PAGES_PER_QUERY}"
        )
        
        try:
            for role in self.config.TARGET_ROLES:
                for company_id in self.config.TARGET_COMPANIES:
                    self._collect_for_role_company(role, company_id)
        finally:
            self.kafka_publisher.close()
            self._print_statistics()
    
    def _collect_for_role_company(self, role: str, company_id: int):
        """Сбор вакансий для конкретной роли и компании"""
        logger.info(f"🔎 Searching: '{role}' @ Company ID {company_id}")
        
        page = 0
        while page < self.config.MAX_PAGES_PER_QUERY:
            search_result = self.api_client.search_vacancies(
                role, company_id, page
            )
            
            if not search_result:
                logger.warning(f"⚠️ Failed to fetch page {page}")
                break
            
            items = search_result.get('items', [])
            total_pages = search_result.get('pages', 1)
            
            if not items or page >= total_pages:
                logger.debug(f"✓ No more results at page {page}")
                break
            
            logger.debug(f"   Page {page + 1}/{total_pages}: {len(items)} vacancies")
            
            for item in items:
                self._process_vacancy(item, role)
            
            page += 1
            if page < total_pages:
                time.sleep(random.uniform(*self.config.DELAY_BETWEEN_PAGES))
    
    def _process_vacancy(self, item: Dict, role: str):
        """Обработка одной вакансии"""
        try:
            vacancy_id = str(item['id'])
            
            # Пропускаем дубликаты
            if vacancy_id in self.stats['processed_ids']:
                self.stats['skipped_duplicates'] += 1
                logger.debug(f"⏭️  Skipping duplicate: {vacancy_id}")
                return
            
            self.stats['processed_ids'].add(vacancy_id)
            
            # Rate limiting для детальных запросов
            time.sleep(self.config.DELAY_DETAIL_REQUEST)
            
            # Получаем детальную информацию
            details = self.api_client.get_vacancy_details(vacancy_id)
            
            if not details:
                self.stats['error_count'] += 1
                logger.warning(f"⚠️ Failed to fetch details: {vacancy_id}")
                return
            
            # Трансформация данных
            try:
                vacancy_data = self.transformer.transform(details, role)
            except ValueError as e:
                self.stats['error_count'] += 1
                logger.warning(f"⚠️ Invalid data for {vacancy_id}: {e}")
                return
            
            # Отправка в Kafka
            if self.kafka_publisher.send(vacancy_data):
                self.stats['sent_count'] += 1
                
                if self.stats['sent_count'] % 50 == 0:
                    logger.info(
                        f"✅ Progress: {self.stats['sent_count']} sent, "
                        f"{self.stats['error_count']} errors, "
                        f"{self.stats['skipped_duplicates']} duplicates"
                    )
            else:
                self.stats['error_count'] += 1
                
        except Exception as e:
            self.stats['error_count'] += 1
            logger.error(f"❌ Unexpected error processing vacancy: {e}")
    
    def _print_statistics(self):
        """Вывод финальной статистики"""
        self.stats['end_time'] = datetime.now()
        duration = self.stats['end_time'] - self.stats['start_time']
        
        logger.info(
            f"\n"
            f"🏁 Collection completed!\n"
            f"{'=' * 50}\n"
            f"Duration: {duration}\n"
            f"Total processed IDs: {len(self.stats['processed_ids'])}\n"
            f"✅ Successfully sent: {self.stats['sent_count']}\n"
            f"⏭️  Skipped duplicates: {self.stats['skipped_duplicates']}\n"
            f"❌ Errors: {self.stats['error_count']}\n"
            f"{'=' * 50}"
        )

# ============================================
# AIRFLOW TASK FUNCTIONS
# ============================================

def collect_vacancies(**context):
    """Airflow task function для сбора вакансий"""
    logger.info("=" * 60)
    logger.info("Starting SkillRadar ETL Pipeline")
    logger.info("=" * 60)
    
    try:
        collector = VacancyCollector(config)
        collector.collect()
        
        # Передаем статистику в XCom
        context['ti'].xcom_push(
            key='collection_stats',
            value={
                'sent_count': collector.stats['sent_count'],
                'error_count': collector.stats['error_count'],
                'unique_vacancies': len(collector.stats['processed_ids']),
                'timestamp': datetime.now().isoformat()
            }
        )
        
        logger.info("✅ ETL pipeline completed successfully")
        
    except Exception as e:
        logger.error(f"❌ ETL pipeline failed: {e}")
        raise

def verify_kafka_connection(**context):
    """Проверка подключения к Kafka перед запуском"""
    logger.info("🔍 Verifying Kafka connection...")
    
    try:
        producer = KafkaProducer(
            bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
            request_timeout_ms=5000
        )
        producer.close()
        logger.info("✅ Kafka connection verified")
        
    except Exception as e:
        logger.error(f"❌ Kafka connection failed: {e}")
        raise

# ============================================
# AIRFLOW DAG DEFINITION
# ============================================

default_args = {
    'owner': 'skillradar',
    'depends_on_past': False,
    'start_date': pendulum.datetime(2025, 1, 1, tz='UTC'),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=3),
}

with DAG(
    dag_id='skillradar_hh_parser',
    default_args=default_args,
    description='SkillRadar: Парсинг вакансий с HeadHunter API',
    schedule_interval='0 3 * * *',  # Каждый день в 3:00 UTC
    catchup=False,
    max_active_runs=1,
    tags=['skillradar', 'etl', 'headhunter', 'production'],
    doc_md=__doc__,
) as dag:
    
    # Task 1: Проверка Kafka
    verify_kafka = PythonOperator(
        task_id='verify_kafka_connection',
        python_callable=verify_kafka_connection,
    )
    
    # Task 2: Основной сбор данных
    collect_data = PythonOperator(
        task_id='collect_hh_vacancies',
        python_callable=collect_vacancies,
    )
    
    # Последовательность выполнения
    verify_kafka >> collect_data