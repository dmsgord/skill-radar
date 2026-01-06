"""
SkillRadar Configuration v10.
Лежит в dags/settings.py
"""
import re

# 1. ЦЕЛЕВЫЕ КОМПАНИИ
TARGET_COMPANIES = {
    1740: "Yandex",
    3529: "Sber",
    78638: "Tinkoff",
    3776: "MTS",
    15478: "VK",
    84585: "Avito",
    2180: "Ozon",
    64174: "2GIS",
    1122: "Kaspersky",
    4181: "VTB",
    80: "AlfaBank",
    3388: "Gazprombank",
    87021: "Wildberries",
    906557: "SberMarket",
    23427: "X5 Tech",
    1532045: "Samokat",
    3127: "Lamoda"
}

# 2. СТОП-СЛОВА (Regex для точности)
# Ищем частичное совпадение (search), но игнорируем регистр
STOP_WORDS = [
    r'водитель', r'курьер', r'грузчик', r'кладовщик', r'комплектовщик', r'сборщик',
    r'упаковщик', r'такси', r'логист', r'диспетчер', r'экспедитор',
    r'кассир', r'продавец', r'повар', r'официант', r'бариста', r'пекарь', r'кондитер',
    r'уборщ', r'клинер', 'мойщик', r'горничная', r'хостес', r'мерчандайзер',
    r'менеджер по продажам', r'sales manager', r'оператор call', r'оператор пк',
    r'секретарь', r'ассистент', r'делопроизводитель', r'юрист', r'бухгалтер',
    r'экономист', r'финансист', r'lawyer', r'accountant', r'администратор магазина',
    r'1[сc]', r'битрикс', # 1С и Bitrix
    r'консультант'
]

# 3. ГЛУБОКИЙ СЛОВАРЬ (Regex Escaped)
# Словарь для поиска ВНУТРИ текста.
# Используем списки. В коде они превратятся в regex с \b (границы слов).
SKILL_DICTIONARY = {
    'Languages': [
        'python', 'java', 'golang', 'go', 'c++', 'c#', 'php', 
        'typescript', 'javascript', 'rust', 'swift', 'kotlin', 'scala', 'ruby'
    ],
    'Frameworks': [
        'django', 'fastapi', 'spring', 'react', 'vue', 'angular', 'laravel', 
        'symfony', '.net core', 'flask', 'pandas', 'numpy', 'pytorch', 'tensorflow',
        'hibernate', 'aiohttp', 'pydantic'
    ],
    'Databases': [
        'postgresql', 'postgres', 'mysql', 'clickhouse', 'mongodb', 'redis', 
        'kafka', 'rabbitmq', 'oracle', 'mssql', 'elasticsearch', 'cassandra'
    ],
    'DevOps': [
        'docker', 'kubernetes', 'k8s', 'ansible', 'terraform', 'jenkins', 
        'gitlab ci', 'linux', 'bash', 'nginx', 'prometheus', 'grafana', 'helm'
    ],
    'Architecture': [
        'microservices', 'rest api', 'soap', 'graphql', 'solid', 'dry', 
        'ci/cd', 'tdd', 'ddd', 'clean architecture'
    ],
    'Management': [
        'agile', 'scrum', 'kanban', 'jira', 'confluence', 'team lead'
    ]
}

# 4. ПРАВИЛА КАТЕГОРИЙ
CATEGORIES_RULES = {
    'Top Management': ['ceo', 'cto', 'cpo', 'cio', 'cmo', 'hrd', 'head of', 'директор по', 'vp '],
    'Backend': ['backend', 'бэкенд', 'java', 'python', 'php', 'node', 'golang', 'c++', 'c#', '.net', 'scala'],
    'Frontend': ['frontend', 'фронтенд', 'react', 'vue', 'angular', 'javascript', 'typescript'],
    'Mobile': ['ios', 'android', 'mobile', 'flutter', 'swift', 'kotlin'],
    'QA': ['qa', 'test', 'тестиров', 'aqa', 'sdet'],
    'DevOps/SRE': ['devops', 'sre', 'linux', 'k8s', 'kubernetes', 'docker', 'admin', 'платформ'],
    'Data/AI': ['data', 'analyst', 'sql', 'etl', 'bi ', 'ml ', 'ds ', 'vision', 'gpt', 'nlp', 'big data'],
    'Product/Project': ['product', 'owner', 'manager', 'продукт', 'проект', 'delivery', 'agile'],
    'Design': ['design', 'ux', 'ui', 'дизайн', 'art'],
    'HR': ['hr', 'recruiter', 'рекрутер', 'talent', 'devrel'],
    'Security': ['security', 'безопасност', 'soc', 'pentest', 'appsec', 'ciso']
}