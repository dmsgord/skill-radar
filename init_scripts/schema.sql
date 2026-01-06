CREATE DATABASE IF NOT EXISTS skill_radar;

-- Основная таблица (ReplacingMergeTree)
CREATE TABLE IF NOT EXISTS skill_radar.vacancies_categorized (
    id UInt64,
    employer_id UInt64,
    employer_name String,
    url String,
    published_at DateTime,
    processed_at DateTime DEFAULT now(),
    
    name String,
    category String,
    
    salary_from Nullable(Float64),
    salary_to Nullable(Float64),
    currency Nullable(String),
    gross Nullable(UInt8),
    
    experience_id String,
    schedule String,
    employment String,
    area_name String,
    
    key_skills Array(String),
    extracted_skills Array(String),
    description String
) 
-- Важно: Сортируем по ID в конце, чтобы ReplacingMergeTree корректно схлопывал дубли
ENGINE = ReplacingMergeTree(processed_at)
ORDER BY (category, employer_id, published_at, id);

-- Kafka Queue
CREATE TABLE IF NOT EXISTS skill_radar.kafka_queue (
    id UInt64,
    employer_id UInt64,
    employer_name String,
    url String,
    published_at String,
    name String,
    category String,
    salary_from Nullable(Float64),
    salary_to Nullable(Float64),
    currency Nullable(String),
    gross Nullable(UInt8),
    experience_id String,
    schedule String,
    employment String,
    area_name String,
    key_skills Array(String),
    extracted_skills Array(String),
    description String
) ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'vacancies_enriched',
    kafka_group_name = 'clickhouse_group_v10',
    kafka_format = 'JSONEachRow',
    kafka_num_consumers = 1;

-- Materialized View
CREATE MATERIALIZED VIEW IF NOT EXISTS skill_radar.vacancies_mv
TO skill_radar.vacancies_categorized
AS SELECT
    id, employer_id, employer_name, url,
    parseDateTimeBestEffort(published_at) AS published_at,
    now() as processed_at,
    name, category, 
    salary_from, salary_to, currency, gross,
    experience_id, schedule, employment, area_name,
    key_skills, extracted_skills, description
FROM skill_radar.kafka_queue;