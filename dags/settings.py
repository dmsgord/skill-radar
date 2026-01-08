# -*- coding: utf-8 -*-
import re

# ==============================================================================
# 1. КОНФИГУРАЦИЯ ИНФРАСТРУКТУРЫ
# ==============================================================================
KAFKA_SERVERS = ['kafka:9092']
KAFKA_TOPIC = "vacancies_enriched"

# ==============================================================================
# 2. ЦЕЛЕВЫЕ КОМПАНИИ (TARGET_COMPANIES)
# Сборная солянка: Топ IT, Банки, Ритейл, Телеком
# ==============================================================================
TARGET_COMPANIES = {
    # --- 🔵 IT GIANTS & ECOSYSTEMS ---
    1740: "Yandex",
    15478: "VK",
    84585: "Avito",
    3529: "Sber",  # Sberbank
    78638: "T-Bank", # Tinkoff
    2180: "Ozon",
    87021: "Wildberries",
    
    # --- 🟢 TELECOM & BIG TECH ---
    3776: "MTS",
    4934: "Beeline",
    4219: "Tele2",
    2748: "Rostelecom",
    64174: "2GIS",
    1122: "Kaspersky",
    
    # --- 🏦 FINTECH & BANKING (TOP-20) ---
    80: "AlfaBank",
    4181: "VTB",
    3388: "Gazprombank",
    7944: "Sovcombank",
    198082: "Raiffeisen",
    4496: "Rosbank",
    909569: "Otkritie",
    51789: "DomRF",
    
    # --- 🛒 RETAIL & E-COMM (TECH DIVISIONS) ---
    4233: "X5 Group",
    23427: "X5 Tech",
    4352: "Magnit",
    4352: "Magnit Tech",
    780654: "Lamoda",
    208707: "VseInstrumenti",
    1532045: "Samokat",
    9694561: "Samokat Tech",
    906557: "SberMarket",
    
    # --- 🏭 INDUSTRY & RESOURCES ---
    3809: "SIBUR",
    6041: "Severstal",
    988387: "NLMK",
    39305: "Gazprom Neft",
    3195: "Rosatom",
    
    # --- 💻 SYSTEM INTEGRATORS & SOFT ---
    1373: "CROC",
    1686: "IBS",
    6093: "SKB Kontur",
    5982: "Lanit",
    26624: "Positive Technologies",
    8550: "CFT",
    23186: "Diasoft",
    1102601: "Astra Linux",
    6769: "Tender Tech",
    1272486: "SberSolutions",
    
    # --- 🎓 EDTECH ---
    769666: "Skyeng",
    2324317: "Skillbox",
    3959104: "GeekBrains",
    4468661: "Netology",
    1437894: "Uchi.ru"
}

# ==============================================================================
# 3. STOP-LIST (Фильтр мусора + HOTFIX T-BANK)
# ==============================================================================
STOP_WORDS = [
    # --- Ритейл и Сфера услуг ---
    r'кассир', r'продавец', r'консультант', r'мерчандайзер', r'работн.*зала',
    r'повар', r'официант', r'бариста', r'пекарь', r'кондитер', r'су-шеф',
    r'уборщ', r'клинер', r'мойщик', r'горничная', r'хостес', r'гардеробщик',
    r'грузчик', r'комплектовщик', r'сборщик', r'упаковщик', r'кладовщик',
    
    # --- Транспорт и Логистика ---
    r'водитель', r'курьер', r'такси', r'экспедитор', r'диспетчер', r'логист',
    r'машинист', r'механик', r'слесарь', r'монтажник', r'электрик',
    
    # --- Продажи и Работа с клиентами (Враг №1) ---
    r'менеджер по продажам', r'sales manager', 
    r'менеджер по работе с клиентами', r'клиентский менеджер',
    r'персональный менеджер', r'менеджер.*отделения',
    r'операционист', r'кредитный', r'страховой', r'взыскани',
    r'оператор call', r'оператор колл', r'контактн.*центр', r'телемаркетолог',
    r'торговый представитель', r'супервайзер', r'промоутер',
    
    # --- 🚨 HOTFIX: Специфика Т-Банка и Финтеха ---
    r'представитель',       # "Представитель Т-Банка" (курьер)
    r'выездной',            # Выездные менеджеры
    r'встреч.*клиент',      # Назначение встреч
    r'убытк',               # Урегулирование убытков
    r'задолженн',           # Взыскание задолженности
    r'коллектор',           # Коллекторы
    r'страхован',           # Страховые агенты
    r'верификатор',         # Проверка документов
    r'андеррайтер',         # Оценка рисков
    r'брокер',              # Страховые/кредитные брокеры
    
    # --- Офис и Админка (не IT) ---
    r'секретарь', r'ассистент', r'делопроизводитель', r'офис-менеджер',
    r'юрист', r'бухгалтер', r'экономист', r'финансист', 
    r'lawyer', r'accountant', r'auditor', r'coordinator',
    
    # --- Другое ---
    r'врач', r'медсестра', r'фармацевт', r'провизор',
    r'преподаватель', r'учитель', r'воспитатель'
]

# ==============================================================================
# 4. MEGA-СЛОВАРЬ НАВЫКОВ (v13 Standard)
# ==============================================================================
SKILL_DICTIONARY = {
    'Languages (Backend/General)': [
        'python', 'питон', 'пайтон', 'python3', 'asyncio', 'aiohttp',
        'java', 'джава', 'java core', 'jvm', 'jdk', 'jre',
        'golang', 'go', 'голанг', 'goroutine',
        'c++', 'cpp', 'плюсы', 'с++',
        'c#', 'csharp', 'c sharp', 'си шарп', '.net', 'dotnet', 'asp.net',
        'php', 'пхп', 'laravel', 'symfony', 'yii',
        'ruby', 'ruby on rails', 'ror', 'руби',
        'rust', 'раст', 'actix',
        'elixir', 'erlang', 'phoenix',
        '1с', '1c', 'один эс', '1с:предприятие', 'битрикс'
    ],
    'Frontend & Web': [
        'javascript', 'js', 'джаваскрипт', 'es6',
        'typescript', 'ts', 'тайпскрипт',
        'react', 'reactjs', 'реакт', 'redux', 'mobx', 'next.js',
        'vue', 'vuejs', 'вью', 'vuex', 'nuxt',
        'angular', 'ангуляр', 'rxjs',
        'html', 'css', 'html5', 'css3', 'верстка', 'bem', 'бэм',
        'sass', 'less', 'scss', 'tailwind', 'bootstrap',
        'webpack', 'vite', 'babel',
        'svelte', 'jquery', 'ajax', 'json', 'dom'
    ],
    'Mobile Development': [
        'ios', 'swift', 'свифт', 'objective-c', 'obj-c', 'uikit', 'swiftui',
        'android', 'kotlin', 'котлин', 'java android', 'jetpack compose',
        'flutter', 'dart', 'флаттер',
        'react native', 'rn',
        'kmp', 'kotlin multiplatform',
        'mobile', 'мобильн'
    ],
    'Data Science & ML': [
        'python', 'pandas', 'numpy', 'scipy',
        'machine learning', 'ml', 'машинное обучение',
        'deep learning', 'dl', 'нейросети',
        'pytorch', 'tensorflow', 'keras',
        'nlp', 'cv', 'computer vision', 'computervision', 'opencv',
        'llm', 'gpt', 'bert', 'huggingface', 'transformers',
        'scikit-learn', 'sklearn', 'xgboost', 'catboost', 'lightgbm',
        'matplotlib', 'seaborn', 'plotly',
        'spark', 'pyspark', 'hadoop', 'big data', 'bigdata', 'бигдата',
        'airflow', 'dbt', 'tableau', 'powerbi', 'clickhouse'
    ],
    'DevOps, SRE & Cloud': [
        'docker', 'докер', 'container',
        'kubernetes', 'k8s', 'kube', 'кубер', 'кубернетес', 'helm',
        'linux', 'линукс', 'bash', 'shell', 'zsh', 'centos', 'ubuntu',
        'ansible', 'ансибл', 'chef', 'puppet',
        'terraform', 'терраформ', 'iac',
        'jenkins', 'gitlab ci', 'github actions', 'ci/cd', 'ci cd', 'teamcity',
        'prometheus', 'grafana', 'elk', 'kibana', 'zabbix', 'opentelemetry',
        'nginx', 'haproxy', 'traefik', 'envoy',
        'aws', 'amazon web services', 's3', 'ec2', 'lambda',
        'gcp', 'google cloud',
        'azure',
        'yandex cloud', 'yc', 'яндекс облако',
        'kafka', 'rabbit', 'rabbitmq'
    ],
    'Databases (SQL & NoSQL)': [
        'sql', 'sql server', 'mssql', 'transact-sql', 't-sql',
        'postgresql', 'postgres', 'pg', 'постгрес', 'постгря',
        'mysql', 'mariadb',
        'oracle', 'pl/sql',
        'mongodb', 'mongo', 'монго',
        'redis', 'редис', 'memcached',
        'clickhouse', 'кликхаус',
        'elasticsearch', 'elastic', 'эластик', 'solr',
        'cassandra', 'tarantool', 'dynamodb'
    ],
    'QA & Testing': [
        'qa', 'тестирование', 'тестировщик',
        'selenium', 'selenide', 'playwright', 'cypress', 'pupeteer',
        'junit', 'pytest', 'testng', 'mockito',
        'postman', 'soapui', 'charles', 'fiddler', 'swagger',
        'manual testing', 'ручное тестирование',
        'automation', 'автотесты', 'aqa', 'sdet'
    ],
    'Management Tools': [
        'jira', 'джира', 'confluence', 'trello', 'notion', 'miro',
        'agile', 'scrum', 'скрам', 'kanban', 'канбан',
        'waterfall', 'safe', 'less'
    ],
    'HR Tools & Skills': [
        '1c зуп', '1с:зуп', 'zup', 'huntflow', 'хантфлоу', 'potok', 'поток',
        'e-staff', 'estaff', 'естафф', 'greenhouse', 'lever',
        'sourcing', 'сорсинг', 'recruiting', 'рекрутинг',
        'headhunting', 'хедхантинг', 'boolean search', 'x-ray',
        'onboarding', 'адаптация', 'c&b', 'компенсации и льготы',
        'talent management', 'управление талантами',
        'hr brand', 'hr-бренд', 'marhr', 'марчар',
        'devrel', 'деврел', 'internal communications', 'внутриком'
    ],
    'Architecture & Patterns': [
        'microservices', 'микросервисы',
        'monolith', 'монолит',
        'rest', 'rest api', 'soap', 'graphql', 'grpc', 'websocket',
        'solid', 'dry', 'kiss', 'oop', 'ооп',
        'ddd', 'tdd', 'bdd',
        'design patterns', 'паттерны', 'gof'
    ],
    'Design (UI/UX)': [
        'figma', 'sketch', 'photoshop', 'illustrator',
        'ui/ux', 'ux/ui', 'дизайн интерфейсов',
        'zeplin', 'invision', 'tilda'
    ]
}

# ==============================================================================
# 5. ПРАВИЛА КАТЕГОРИЙ
# ==============================================================================
CATEGORIES_RULES = {
    'Top Management': [
        'ceo', 'chief executive officer', 'генеральный директор',
        'cto', 'chief technology officer', 'технический директор',
        'cpo', 'chief product officer', 'директор по продукту',
        'cio', 'chief information officer', 'it-директор', 'it director',
        'cmo', 'chief marketing officer', 'директор по маркетингу',
        'coo', 'chief operating officer', 'операционный директор',
        'hrd', 'hr director', 'human resources director', 'директор по персоналу',
        'ciso', 'chief information security officer',
        'vp of', 'vice president', 'вице-президент',
        'head of', 'руководитель направления', 'руководитель департамента', 
        'руководитель управления', 'начальник управления',
        'general manager'
    ],
    'HR': [
        'hrbp', 'hr business partner', 'hr-business partner', 
        'hr бизнес-партнер', 'hr бизнес партнер', 'hr-партнер',
        'people partner', 'пипл партнер', 'пипл-партнер',
        'hr generalist', 'hr-generalist', 'hr дженералист', 'hr-дженералист',
        'дженералист', 'generalist',
        'recruiter', 'рекрутер', 'it-рекрутер', 'it recruiter',
        'talent acquisition', 'ta specialist', 'менеджер по подбору',
        'sourcer', 'сорсер', 'ресечер', 'researcher',
        'devrel', 'developer relations',
        'marhr', 'марчар', 'hr brand', 'hr-бренд', 'бренд работодателя',
        'internal comms', 'internal communications', 'внутриком', 
        'менеджер по внутренним коммуникациям',
        'c&b', 'compensation and benefits', 'компенсации и льготы',
        'кдп', 'кадровое делопроизводство', 'специалист по кадрам',
        'hr admin', 'hr ops', 'hr operations',
        'l&d', 'learning and development', 't&d', 'training and development',
        'менеджер по обучению', 'корпоративный тренер'
    ],
    'Product/Project': [
        'product owner', 'product manager', 'owner', 'po', 'pm',
        'project manager', 'менеджер проекта', 'менеджер продукта',
        'delivery manager', 'scrum master', 'agile coach', 'prod',
        'продуктовый', 'проджект'
    ],
    'Data/AI': [
        'data scientist', 'data analyst', 'system analyst', 'business analyst',
        'аналитик данных', 'системный аналитик', 'бизнес-аналитик',
        'machine learning', 'ml engineer', 'ml-инженер', 'cv engineer',
        'nlp', 'ai researcher', 'data engineer', 'дата инженер',
        'etl', 'dwh', 'bi developer', 'bi-разработчик'
    ],
    'DevOps/SRE': [
        'devops', 'sre', 'site reliability engineer', 'девопс',
        'системный администратор', 'sysadmin', 'linux administrator',
        'platform engineer', 'cloud engineer', 'инженер по инфраструктуре',
        'dba', 'администратор баз данных', 'сетевой инженер'
    ],
    'QA': [
        'qa', 'tester', 'тестировщик', 'quality assurance',
        'sdet', 'test automation', 'автотестировщик', 'нагрузочное',
        'test lead', 'qa lead'
    ],
    'Mobile': [
        'ios', 'android', 'mobile', 'мобильный', 'flutter', 'react native'
    ],
    'Frontend': [
        'frontend', 'front-end', 'фронтенд', 'фронт',
        'javascript developer', 'react developer', 'vue', 'angular', 
        'верстальщик', 'web developer', 'веб-разработчик'
    ],
    'Backend': [
        'backend', 'back-end', 'бэкенд', 'бэк',
        'developer', 'разработчик', 'programmer', 'программист', 'engineer',
        'java', 'python', 'php', 'golang', 'go', 'c++', 'c#', '.net',
        'ruby', 'scala', 'node', '1с', '1c', 'битрикс'
    ],
    'Design': [
        'designer', 'дизайнер', 'ux', 'ui', 'product designer', 'art director'
    ],
    'Security': [
        'security', 'cyber', 'information security', 'безопасность', 'soc', 'pentest'
    ],
    'Support': [
        'technical support', 'техническая поддержка', 
        'helpdesk', 'service desk', 'инженер технической поддержки'
    ]
}