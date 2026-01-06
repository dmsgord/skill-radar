# SkillRadar 🎯

**SkillRadar** — ETL-пайплайн для анализа рынка труда.
Проект собирает вакансии с HH.ru, отправляет их в Kafka, загружает в ClickHouse и даёт аналитику через Metabase.
Оркестрация — через **Apache Airflow + Postgres**.

## 🧩 Архитектура (что за что отвечает)

- **Airflow 2.7 + Postgres (LocalExecutor)** — оркестрация задач и расписание.
- **Kafka + Zookeeper** — буфер/очередь для потока вакансий.
- **ClickHouse** — аналитическое хранилище.
- **Metabase** — дашборды поверх ClickHouse.
- **Docker Compose** — поднимает весь стек одной командой.

## ✅ Предrequirements

- Docker Desktop (или Docker Engine) + plugin Docker Compose (`docker compose`).

## 🚀 Быстрый старт (пошагово)

### 1) Запуск инфраструктуры

Открой терминал в корне репозитория (где лежит `docker-compose.yaml`) и выполни:

```bash
docker compose up airflow-init
```

Это **одноразовый** шаг. Контейнер `airflow-init`:
- создаёт/инициализирует метаданные Airflow в Postgres (`airflow db init`)
- применяет миграции (`airflow db migrate`)
- создаёт админа (логин/пароль ниже)

После этого подними остальные сервисы:

```bash
docker compose up -d
```

### 2) Проверка, что всё поднялось

```bash
docker compose ps
```

Ожидаем увидеть:
- `skillradar_airflow_webserver` — Up
- `skillradar_airflow_scheduler` — Up
- `skillradar_postgres` — Up (healthy)
- `skillradar_kafka` — Up (healthy)
- `skillradar_clickhouse` — Up (healthy)
- `skillradar_metabase` — Up

### 3) Открыть UI

- **Airflow**: http://localhost:8081
  - логин: `admin`
  - пароль: `admin`
- **Metabase**: http://localhost:3000
- **ClickHouse**:
  - HTTP: `http://localhost:8123`
  - Native: `localhost:9000`

### 4) Запуск DAG

В Airflow:
1. Открой DAG-список
2. Найди DAG `skillradar_v3_enrichment`
3. Переведи тумблер слева в `ON`
4. Нажми ▶️ (Trigger DAG)

## 📌 Полезные команды

Остановить проект (данные сохранятся в docker volumes):

```bash
docker compose down
```

Полный сброс (удалить все volumes, включая Airflow metadb):

```bash
docker compose down -v
```

Посмотреть логи Airflow:

```bash
docker compose logs -f airflow-webserver
docker compose logs -f airflow-scheduler
```

## 🛠️ Если Airflow не стартует

### 1) Самая частая причина: метаданные не инициализированы

Симптом:
- в логах `You need to initialize the database. Please run airflow db init`.

Решение:

```bash
docker compose down
# если хочется начать «чисто», добавь -v
docker compose up airflow-init
docker compose up -d
```

### 2) Проверить Postgres

```bash
docker compose logs -f postgres_airflow
```

Если Postgres не healthy, Airflow корректно не взлетит.

---

Если хочешь — дальше можно добавить автосоздание подключения к ClickHouse/Kafka через env (`AIRFLOW_CONN_...`) или через init-скрипты, но для локальной разработки текущего достаточно.
