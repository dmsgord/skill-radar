CREATE DATABASE IF NOT EXISTS skill_radar;

-- Основная таблица
CREATE TABLE IF NOT EXISTS skill_radar.vacancies_categorized (
    id UInt64,
    published_at DateTime,
    name String,
    category String,
    employer_name String,
    salary_from Nullable(Float64),
    salary_to Nullable(Float64),
    currency Nullable(String),
    gross Nullable(UInt8),
    experience String,
    schedule String,
    employment String,
    key_skills Array(String),
    professional_roles Array(String),
    description String,
    alternate_url String,
    processed_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(processed_at)
ORDER BY (category, published_at, id);

-- Очередь Kafka (JSONEachRow - автопарсинг JSON)
CREATE TABLE IF NOT EXISTS skill_radar.kafka_queue (
    id UInt64,
    published_at String,
    name String,
    category String,
    employer_name String,
    salary_from Nullable(Float64),
    salary_to Nullable(Float64),
    currency Nullable(String),
    gross Nullable(UInt8),
    experience String,
    schedule String,
    employment String,
    key_skills Array(String),
    professional_roles Array(String),
    description String,
    alternate_url String
) ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'vacancies_enriched',
    kafka_group_name = 'clickhouse_group',
    kafka_format = 'JSONEachRow',
    kafka_num_consumers = 1;

-- Materialized View
CREATE MATERIALIZED VIEW IF NOT EXISTS skill_radar.vacancies_mv
TO skill_radar.vacancies_categorized
AS
SELECT
    id,
    parseDateTimeBestEffort(published_at) AS published_at,
    name,
    category,
    employer_name,
    salary_from,
    salary_to,
    currency,
    gross,
    experience,
    schedule,
    employment,
    key_skills,
    professional_roles,
    description,
    alternate_url
FROM skill_radar.kafka_queue;