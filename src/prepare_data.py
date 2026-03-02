import json
import os
import re
from collections import defaultdict

ABBR_PATTERN = r"[А-ЯЁA-Z]{2,10}"

# Извлечение текста из pdf
def extract_text(path):
    import fitz

    pages = []
    with fitz.open(path) as doc:
        for page in doc:
            pages.append(page.get_text("text"))
    return "\n".join(pages)


# Проверка первых букв
def check_first_letters(abbr, definition):
    words = re.findall(r"[А-Яа-яЁёA-Za-z0-9]+", definition)
    initials = "".join(w[0].upper() for w in words if w)
    return abbr.upper() == initials[: len(abbr)]

# Выбор только слов с первыми буквами
def crop_definition_to_abbr(abbr, definition):
    words = re.findall(r"[А-Яа-яЁёA-Za-z0-9\-]+", definition)
    if not words:
        return definition.strip()
    kept = []
    initials = []
    for word in words:
        kept.append(word)
        initials.append(word[0].upper())
        if len(initials) >= len(abbr):
            break

    cropped = " ".join(kept).strip()
    return cropped if cropped else definition.strip()

# Поиск раздела с сокращениями
def find_abbreviation_section(text):
    heading = r"(?:сокращени[яей]|обозначени[яей]|термины и определения)"
    match = re.search(
        rf"{heading}[^\n]*\n(.*?)(?=\n[А-ЯЁ][А-ЯЁ\s]{{3,}}\n|\Z)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    return match.group(1) if match else None


# 1. Определение (АББР)
def pattern_p1_checked(text):
    results = []
    for match in re.finditer(rf"\(({ABBR_PATTERN})\)", text):
        abbr = match.group(1).upper()
        start = max(0, match.start() - 120)
        context = text[start: match.start()]
        before = re.search(r"([А-Яа-яёЁA-Za-z\s\-]{2,80})$", context)
        if before:
            definition = before.group(1).strip(" -\n\t")
            definition = crop_definition_to_abbr(abbr, definition)
            confidence = 0.85 if check_first_letters(abbr, definition) else 0.65
            results.append((abbr, definition, confidence))
    return results


# 2. АББР — определение (в основном тексте)
def pattern_p2_checked(text):
    results = []
    matches = re.findall(rf"({ABBR_PATTERN})\s*[—-]\s*([А-Яа-яёЁA-Za-z\s\-]{{2,80}})", text)
    for abbr, definition in matches:
        abbr = abbr.upper().strip()
        definition = definition.strip()
        definition = crop_definition_to_abbr(abbr, definition)
        confidence = 0.8 if check_first_letters(abbr, definition) else 0.6
        results.append((abbr, definition, confidence))
    return results


# 3. Поиск только в разделе с сокращениями
def pattern_p3_checked(text):
    results = []
    section = find_abbreviation_section(text)
    if not section:
        return results
    for line in section.splitlines():
        match = re.match(rf"({ABBR_PATTERN})\s*[–—-]\s*(.+)", line.strip())
        if match:
            abbr = match.group(1).upper().strip()
            definition = match.group(2).strip()
            definition = crop_definition_to_abbr(abbr, definition)
            results.append((abbr, definition, 0.95))
    return results


# Дедупликация с сохранением максимального confidence
def deduplicate(abbrs):
    best = {}
    for abbr, definition, confidence in abbrs:
        key = (abbr, definition)
        if key not in best or confidence > best[key]:
            best[key] = confidence
    return [
        {"abbr": abbr, "definition": definition, "confidence": conf}
        for (abbr, definition), conf in sorted(best.items())
    ]


# Общая функция
def extract_abbreviations(text):
    abbrs = []
    abbrs.extend(pattern_p1_checked(text))
    abbrs.extend(pattern_p2_checked(text))
    abbrs.extend(pattern_p3_checked(text))
    return deduplicate(abbrs)


def process_pdf_folder(folder_path, output_json="abbreviations.json"):
    database = defaultdict(list)
    for filename in os.listdir(folder_path):
        if not filename.lower().endswith(".pdf"):
            continue

        path = os.path.join(folder_path, filename)
        text = extract_text(path)
        abbrs = extract_abbreviations(text)

        for item in abbrs:
            database[item["abbr"]].append(
                {
                    "definition": item["definition"],
                    "source": filename,
                    "confidence": item["confidence"]
                }
            )
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(database, f, ensure_ascii=False, indent=2)
    return dict(database)

def _extract_query_abbr(query):
    candidates = re.findall(ABBR_PATTERN, query.upper())
    return candidates[-1] if candidates else query.strip().upper()

def answer_query(query, database):
    abbr = _extract_query_abbr(query)
    if abbr in database:
        answers = database[abbr]
        return [
            f"{item['definition']} (источник: {item['source']}, confidence={item['confidence']})"
            for item in answers
        ]
        return [f"В документах расшифровка аббревиатуры '{abbr}' не найдена."]