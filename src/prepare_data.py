import json
import os
import re
from collections import defaultdict

ABBR_PATTERN = r"[А-ЯЁA-Z][А-Яа-яЁёA-Za-z]{1,15}"
STOPWORDS_RU = {
    "И",
    "А",
    "НО",
    "ИЛИ",
    "ДА",
    "ЛИ",
    "ЖЕ",
    "БЫ",
    "В",
    "ВО",
    "НА",
    "К",
    "КО",
    "О",
    "ОБ",
    "ОБО",
    "ОТ",
    "ДО",
    "ПО",
    "ПРИ",
    "ПРО",
    "ДЛЯ",
    "С",
    "СО",
    "У",
    "ИЗ",
    "БЕЗ",
    "ПОД",
    "ПЕРЕД",
    "ЧЕРЕЗ",
    "МЕЖДУ",
}
STOPWORDS_EN = {"of", "the", "and", "for", "in", "on", "to"}


# Извлечение текста из pdf
def extract_text(path):
    import fitz

    pages = []
    with fitz.open(path) as doc:
        for page in doc:
            pages.append(page.get_text("text"))
    text = "\n".join(pages)
    text = re.sub(r"([А-Яа-яЁёA-Za-z])\-\s*\n\s*([А-Яа-яЁёA-Za-z])", r"\1\2", text)
    return text


# Проверка первых букв
def check_first_letters(abbr, definition):
    words = re.findall(r"[А-Яа-яЁёA-Za-z0-9]+", definition)
    initials = "".join(
        w[0].upper() for w in words if w and w.upper() not in STOPWORDS_RU
    )
    return abbr.upper() == initials[: len(abbr)]

#Сопоставление первых букв с конца, поддержка предлогов и усечённых слов
def match_abbr_from_end(abbr, words):
    abbr_chars = list(abbr)
    i = len(abbr_chars) - 1
    j = len(words) - 1

    used_words = []

    while i >= 0 and j >= 0:
        ch = abbr_chars[i]
        word = words[j]

        # пропускаем служебные слова
        if word.lower() in STOPWORDS_EN:
            j -= 1
            continue

        # строчная буква — предлог
        if ch.islower():
            if word.lower() == ch:
                used_words.append(word)
                i -= 1
                j -= 1
            else:
                j -= 1
            continue

        # обычное сопоставление первой буквы
        if word[0].upper() == ch.upper():
            used_words.append(word)
            i -= 1
            j -= 1
            continue
        j -= 1
    if i < 0:
        return list(reversed(used_words))
    return None



# Выбор только слов с первыми буквами
def crop_definition_to_abbr(abbr, definition):
    words = re.findall(r"[А-Яа-яЁёA-Za-z\-]+", definition)
    if not words:
        return None
    matched = match_abbr_from_end(abbr, words)
    if matched:
        return " ".join(matched)
    # fallback для очень коротких аббревиатур: ЭС, ИИ, НС
    if len(abbr) <= 3 and len(words) >= len(abbr):
        return " ".join(words[-len(abbr):])
    return None


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
        before = re.search(r"([А-Яа-яЁёA-Za-z\s\-]{10,120})$", context)
        if before:
            definition_raw = before.group(1).strip(" -\n\t")
            definition = crop_definition_to_abbr(abbr, definition_raw)
            if not definition:
                print(f"[SKIP] {abbr} <- '{definition_raw}'")
                words = re.findall(r"[А-Яа-яЁёA-Za-z\-]+", definition_raw)
                if len(abbr) <= 3 and len(words) >= len(abbr):
                    definition = " ".join(words[-len(abbr):])
                else:
                    continue
            confidence = 0.9
            results.append((abbr, definition, confidence))

    return results


# 2. АББР — определение (в основном тексте)
def pattern_p2_checked(text):
    results = []
    matches = re.findall(rf"({ABBR_PATTERN})\s*[—-]\s*([А-Яа-яёЁA-Za-z\s\-]{{2,80}})", text)
    for abbr, definition in matches:
        abbr = abbr.upper().strip()
        definition = definition.strip()
        definition_cropped = crop_definition_to_abbr(abbr, definition)
        if not definition_cropped:
            continue
        confidence = 0.8 if check_first_letters(abbr, definition_cropped) else 0.6
        results.append((abbr, definition_cropped, confidence))
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
            definition_cropped = crop_definition_to_abbr(abbr, definition)
            if not definition_cropped:
                continue
            results.append((abbr, definition_cropped, 0.95))
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
    else:
        return [f"В документах расшифровка аббревиатуры '{abbr}' не найдена."]