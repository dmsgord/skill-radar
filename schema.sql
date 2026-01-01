CREATE DATABASE IF NOT EXISTS skill_radar;

USE skill_radar;

CREATE TABLE IF NOT EXISTS vacancies
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