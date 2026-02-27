import json
import os
import re
import fitz


# Извлечение текста из pdf
def extract_text(path):
    text = ""
    doc = fitz.open(path)
    for page in doc:
        page_text = page.get_text().replace("\n", " ")
        text += page_text
    return text


# Проверка первых букв
def check_first_letters(abbr, definition):
    words = definition.split()
    initials = ''.join([w[0].upper() for w in words if w])
    return abbr.upper() == initials[:len(abbr)]


# Поиск раздела с сокращениями
def find_abbreviation_section(text):
    match = re.search(
        r"(?:сокращени[яей]|обозначени[яей]|термины и определения)[^\n]*\n(.*?)(?=\n[А-ЯЁ][А-ЯЁ\s]{3,}\n|\Z)",
        text, re.IGNORECASE | re.DOTALL
    )
    return match.group(1) if match else None


# 1. Определение (АББР)
def pattern_p1_checked(text):
    results = []
    matches = re.findall(r"\(([А-ЯЁA-Z]{2,10})\)", text)
    for abbr in matches:
        before = re.search(r"([А-Яа-яёЁ\s\-]{2,50})\s*\(" + re.escape(abbr) + r"\)", text)
        if before:
            definition = before.group(1).strip()
            confidence = 0.85 if check_first_letters(abbr, definition) else 0.65
            results.append((abbr, definition, confidence))
    return results


# 2. АББР — определение (в основном тексте)
def pattern_p2_checked(text):
    results = []
    matches = re.findall(r"([А-ЯЁA-Z]{2,10})\s*[—-]\s*([А-Яа-яёЁ\s\-]{2,50})", text)
    for abbr, definition in matches:
        confidence = 0.8 if check_first_letters(abbr, definition) else 0.6
        results.append((abbr, definition.strip(), confidence))
    return results


# 3. Поиск только в разделе с сокращениями
def pattern_p3_checked(text):
    results = []
    section = find_abbreviation_section(text)
    if not section:
        return results
    lines = section.splitlines()
    for line in lines:
        match = re.match(r"([А-ЯЁA-Z]{2,10})\s*[–—-]\s*(.+)", line)
        if match:
            abbr = match.group(1).strip()
            definition = match.group(2).strip()
            results.append((abbr, definition, 0.95))
    return results


# Дедупликация с сохранением максимального confidence
def deduplicate(abbrs):
    best = {}
    for abbr, definition, confidence in abbrs:
        key = (abbr, definition)
        if key not in best or confidence > best[key]:
            best[key] = confidence
    return [{"abbr": a, "definition": d, "confidence": c} for (a, d), c in best.items()]


# Общая функция
def extract_abbreviations(text):
    abbrs = []
    abbrs.extend(pattern_p1_checked(text))
    abbrs.extend(pattern_p2_checked(text))
    abbrs.extend(pattern_p3_checked(text))
    return deduplicate(abbrs)


def process_pdf_folder(folder_path, output_json="abbreviations.json"):
    database = {}
    for filename in os.listdir(folder_path):
        if filename.lower().endswith(".pdf"):
            path = os.path.join(folder_path, filename)
            text = extract_text(path)
            abbrs = extract_abbreviations(text)
            for item in abbrs:
                abbr = item["abbr"]
                if abbr not in database:
                    database[abbr] = []
                database[abbr].append({
                    "definition": item["definition"],
                    "source": filename,
                    "confidence": item["confidence"]
                })
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(database, f, ensure_ascii=False, indent=2)
    return database


def answer_query(query, database):
    abbr = query.strip().upper()
    if abbr in database:
        answers = database[abbr]
        return [f"{item['definition']} (источник: {item['source']}, confidence={item['confidence']})"
                for item in answers]
    else:
        return [f"В документах расшифровка аббревиатуры '{abbr}' не найдена."]