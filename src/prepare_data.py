import json
import os
import re
from collections import defaultdict
import pdfplumber

ABBR_PATTERN = r"[А-ЯЁA-Z][А-Яа-яЁёA-Za-z]{1,15}"
STOPWORDS_RU = {
    "И", "А", "НО", "ИЛИ", "ДА",
    "ЛИ", "ЖЕ", "БЫ", "В", "ВО",
    "НА", "К", "О", "ОБ", "ОБО", "ОТ",
    "ДО", "ПО", "ПРИ", "ПРО", "ДЛЯ",  "С",
    "СО", "У", "ИЗ", "БЕЗ", "ПОД",
    "ПЕРЕД",  "ЧЕРЕЗ",   "МЕЖДУ"
}
STOPWORDS_EN = {"of", "the", "and", "for", "in", "on", "to"}


# Извлечение текста из pdf
def extract_text(path):
    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:  # проверяем, что текст не None
                pages.append(text)
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
        if word.lower() in STOPWORDS_EN:
            j -= 1
            continue

        if ch.islower():
            if word.lower() == ch:
                used_words.append(word)
                i -= 1
                j -= 1
            else:
                j -= 1
            continue
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
    return None

# Поиск раздела с сокращениями
def find_abbreviation_section(text):
    heading_patterns = [
        r'^(?:\d+\.?\s*)?Термины,\s*определения\s+и\сокращения\s*[:.]?\s*$',
        r'^(?:\d+\.?\s*)?Список\s+сокращений\s*[:.]?\s*$',
        r'^(?:\d+\.?\s*)?Обозначения\s+и\сокращения\s*[:.]?\s*$',
        r'^(?:\d+\.?\s*)?Глоссарий\s*[:.]?\s*$',
        r'(?:Термины,\s*определения\s+и\сокращения|Сокращения|Обозначения)',
    ]
    match = None
    for pat in heading_patterns:
        match = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
        if match:
            break
    if not match:
        return None

    start = match.end()
    rest = text[start:].lstrip('\n')
    lines = rest.splitlines()
    section_lines = []

    i = 0
    found_start = False
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        has_dash_colon = any(c in stripped for c in ('–', '-', ':'))
        first_word = stripped.split()[0] if stripped.split() else ''
        is_abbr_start = is_abbreviation(first_word)
        if has_dash_colon or is_abbr_start:
            found_start = True
            break
        else:
            i += 1

    if not found_start:
        return None

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            section_lines.append(line)
            i += 1
            continue


        if '–' not in stripped and '-' not in stripped and ':' not in stripped:
            first_word = stripped.split()[0] if stripped.split() else ''
            if not is_abbreviation(first_word) and not line.startswith((' ', '\t')) and not stripped[0].islower():
                break

        section_lines.append(line)
        i += 1

    while section_lines and not section_lines[-1].strip():
        section_lines.pop()

    return '\n'.join(section_lines)

def is_abbreviation(word):
        word = word.rstrip('.,;:!?')
        if re.fullmatch(r'[А-ЯЁA-Z]{2,7}(?:[.-][А-ЯЁA-Z]{2,7})*', word):
            return True
        if word.isupper() and 2 <= len(word) <= 7:
            return True
        return False

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
            confidence = 0.8 if check_first_letters(abbr, definition) else 0.6
            results.append((abbr, definition, confidence))

    return results


# 2. АББР — определение (в основном тексте)
def pattern_p2_checked(text):
    results = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = re.match(rf"({ABBR_PATTERN})\s*[–—-]\s*(.+)", line)
        if match:
            abbr = match.group(1).upper()
            definition = match.group(2).strip()
            definition_cropped = crop_definition_to_abbr(abbr, definition)
            
            if definition_cropped:
                words = definition_cropped.split()
                if words and all(len(w) == 1 for w in words):
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
        line = line.strip()
        if not line:
            continue
        match = re.match(rf"({ABBR_PATTERN})\s*[–—-]\s*(.+)", line)
        if match:
            abbr = match.group(1).upper()
            definition = match.group(2).strip()
            definition_cropped = crop_definition_to_abbr(abbr, definition)
            if definition_cropped:
                results.append((abbr, definition_cropped, 0.95))
    return results

# 4. АББР (...определение)
def pattern_p4_checked(text):
    results = []
    for match in re.finditer(rf"({ABBR_PATTERN})\s*[\(（](.*?)[\)）]", text, re.DOTALL):
        abbr = match.group(1).upper()
        inner = match.group(2)

        inner_clean = re.sub(
            r"\b(акроним от|аббревиатур[аы]?|сокращени[еия]|англ\.)\b",
            "", inner, flags=re.IGNORECASE)
        inner_clean = re.sub(r"\([^)]*\)", "", inner_clean)
        inner_clean = re.sub(r"[«»]", "", inner_clean).strip()
        if re.search(r'[^А-Яа-яЁёA-Za-z\s\-]', inner_clean):
            continue

        words = re.findall(r"[А-Яа-яЁёA-Za-z\-]+", inner_clean)
        if len(words) < len(abbr):   
            continue

        matched = match_abbr_from_end(abbr, words)
        if matched:
            definition = " ".join(matched)
            results.append((abbr, definition, 0.85))

    return results

# 5. Извлечение из таблицы вида "Вопрос-ответ" 
def extract_from_tables_p5(pdf_path):
    results = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if len(row) >= 2:
                        cell1 = row[0] if row[0] is not None else ''
                        cell2 = row[1] if row[1] is not None else ''

                        cell1_clean = str(cell1).replace('\n', '').strip()
                        cell2_clean = str(cell2).replace('\n', '').strip()

                        modified = cell1_clean
                        for prefix in ["Чтотакое", "Ктотакой"]:
                            if modified.startswith(prefix):
                                modified = modified[len(prefix):]
                        if modified.endswith("?"):
                            modified = modified[:-1]
                        modified = modified.strip()

                        if modified and modified != cell1_clean:
                            results.append({
                                "abbr": modified,
                                "definition": cell2_clean,
                                "confidence": 0.95
                            })
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


# Общая функция извлечения
def extract_abbreviations(text):
    abbrs = []
    abbrs.extend(pattern_p1_checked(text))
    abbrs.extend(pattern_p2_checked(text))
    abbrs.extend(pattern_p3_checked(text))
    abbrs.extend(pattern_p4_checked(text))
    return deduplicate(abbrs)

#Дедупликация
def merge_duplicate_definitions(database):
    merged_db = {}
    for abbr, entries in database.items():
        unique = {}
        for entry in entries:
            norm_def = entry['definition'].strip().lower()
            if norm_def not in unique:
                unique[norm_def] = {
                    'definition': entry['definition'],
                    'confidence': entry['confidence'],
                    'sources': [entry['source']]
                }
            else:
                if entry['confidence'] > unique[norm_def]['confidence']:
                    unique[norm_def]['confidence'] = entry['confidence']
                    unique[norm_def]['definition'] = entry['definition']
                if entry['source'] not in unique[norm_def]['sources']:
                    unique[norm_def]['sources'].append(entry['source'])
        merged_db[abbr] = sorted(unique.values(), key=lambda x: x['confidence'], reverse=True)
    return merged_db

def process_pdf_folder(folder_path, output_json="abbreviations.json"):

    if os.path.exists(output_json):
        with open(output_json, "r", encoding="utf-8") as f:
            existing = json.load(f)
        database = defaultdict(list)
        existing_keys = set()
        for abbr, entries in existing.items():
            for entry in entries:
                definition = entry['definition']
                confidence = entry['confidence']
                for source in entry['sources']:
                    flat_entry = {
                        'definition': definition,
                        'source': source,
                        'confidence': confidence
                    }
                    database[abbr].append(flat_entry)
                    key = (abbr, definition, source)
                    existing_keys.add(key)
    else:
        database = defaultdict(list)
        existing_keys = set()

    for filename in os.listdir(folder_path):
        if not filename.lower().endswith(".pdf"):
            continue

        path = os.path.join(folder_path, filename)
        text = extract_text(path)
        abbrs = extract_abbreviations(text)  
        table_abbrs = extract_from_tables_p5(path)  

        all_abbrs = abbrs + table_abbrs

        for item in all_abbrs:
            abbr = item["abbr"]
            definition = item["definition"].lower()   
            source = filename
            confidence = item["confidence"]
            key = (abbr, definition, source)

            if key not in existing_keys:
                database[abbr].append({
                    "definition": definition,
                    "source": source,
                    "confidence": confidence
                })
                existing_keys.add(key)

    database = merge_duplicate_definitions(database)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(dict(database), f, ensure_ascii=False, indent=2)

    return dict(database)

def _extract_query_abbr(query):
    candidates = re.findall(ABBR_PATTERN, query.upper())
    return candidates[-1] if candidates else query.strip().upper()

def answer_query(query, database):
    abbr = _extract_query_abbr(query)
    if abbr in database:
        answers = database[abbr]
        return [
            f"{item['definition']} (источник: {', '.join(item['sources'])}, confidence={item['confidence']})"
            for item in answers if item['confidence'] > 0.6
        ]
    else:
        return [f"В документах расшифровка аббревиатуры '{abbr}' не найдена."]
