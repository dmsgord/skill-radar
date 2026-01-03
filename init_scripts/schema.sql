DROP DATABASE IF EXISTS skill_radar;
CREATE DATABASE IF NOT EXISTS skill_radar;
USE skill_radar;

-- 1. ОСНОВНАЯ ТАБЛИЦА
CREATE TABLE IF NOT EXISTS vacancies
(
    id UInt64,
    name String,
    area_name String,
    employer_name String,
    published_at DateTime,
    inserted_at DateTime DEFAULT now(),
    salary_from Nullable(Float64),
    salary_to Nullable(Float64),
    currency Nullable(String),
    key_skills Array(String),
    search_query String,
    salary_rub_from Nullable(Float64),
    salary_rub_to Nullable(Float64),
    skills_count UInt16 DEFAULT length(key_skills)
)
ENGINE = ReplacingMergeTree()
PARTITION BY toYYYYMM(published_at)
ORDER BY (id, published_at)
SETTINGS index_granularity = 8192;

-- 2. KAFKA ENGINE
CREATE TABLE IF NOT EXISTS kafka_queue
(
    id UInt64,
    name String,
    area_name String,
    employer_name String,
    published_at String,
    salary_from Nullable(Float64),
    salary_to Nullable(Float64),
    currency Nullable(String),
    key_skills Array(String),
    search_query String
)
ENGINE = Kafka()
SETTINGS 
    kafka_broker_list = 'kafka:29092',
    kafka_topic_list = 'raw_vacancies',
    kafka_group_name = 'clickhouse_consumer_group',
    kafka_format = 'JSONEachRow',
    kafka_num_consumers = 1;

-- 3. MATERIALIZED VIEW
CREATE MATERIALIZED VIEW IF NOT EXISTS vacancies_mv TO vacancies AS
SELECT
    id,
    name,
    area_name,
    employer_name,
    parseDateTime64BestEffort(published_at) AS published_at,
    now() AS inserted_at,
    salary_from,
    salary_to,
    currency,
    key_skills,
    search_query,
    -- Конвертация в рубли (упрощенная)
    multiIf(currency = 'RUR', salary_from, currency = 'USD', salary_from * 90, currency = 'EUR', salary_from * 100, NULL) AS salary_rub_from,
    multiIf(currency = 'RUR', salary_to, currency = 'USD', salary_to * 90, currency = 'EUR', salary_to * 100, NULL) AS salary_rub_to,
    length(key_skills) AS skills_count
FROM kafka_queue;