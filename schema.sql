DROP DATABASE IF EXISTS skill_radar;
CREATE DATABASE skill_radar;
USE skill_radar;

CREATE TABLE vacancies
(
    id UInt64,
    published_at DateTime,
    created_at DateTime,
    name String,
    employer_name String,
    area_name String,
    salary_from Nullable(Float64),
    salary_to Nullable(Float64),
    currency Nullable(String),
    gross Nullable(UInt8),
    experience String,
    schedule String,
    employment String,
    key_skills Array(String),
    description String,
    alternate_url String,
    search_query String
)
ENGINE = ReplacingMergeTree(published_at)
ORDER BY id;

CREATE TABLE kafka_queue
(
    message String
)
ENGINE = Kafka
SETTINGS kafka_broker_list = 'kafka:29092',
         kafka_topic_list = 'raw_vacancies',
         kafka_group_name = 'clickhouse_group',
         kafka_format = 'JSONAsString';

CREATE MATERIALIZED VIEW vacancies_mv TO vacancies AS
SELECT
    JSONExtractUInt(message, 'id') AS id,
    toDateTime(parseDateTimeBestEffortOrNull(JSONExtractString(message, 'published_at'))) AS published_at,
    toDateTime(parseDateTimeBestEffortOrNull(JSONExtractString(message, 'created_at'))) AS created_at,
    JSONExtractString(message, 'name') AS name,
    JSONExtractString(message, 'employer', 'name') AS employer_name,
    JSONExtractString(message, 'area', 'name') AS area_name,
    JSONExtractFloat(message, 'salary', 'from') AS salary_from,
    JSONExtractFloat(message, 'salary', 'to') AS salary_to,
    JSONExtractString(message, 'salary', 'currency') AS currency,
    if(JSONExtractString(message, 'salary', 'gross') = 'true', 1, 0) AS gross,
    JSONExtractString(message, 'experience', 'id') AS experience,
    JSONExtractString(message, 'schedule', 'id') AS schedule,
    JSONExtractString(message, 'employment', 'id') AS employment,
    arrayMap(x -> JSONExtractString(x, 'name'), JSONExtractArrayRaw(message, 'key_skills')) AS key_skills,
    JSONExtractString(message, 'description') AS description,
    JSONExtractString(message, 'alternate_url') AS alternate_url,
    JSONExtractString(message, 'search_query') AS search_query
FROM kafka_queue;