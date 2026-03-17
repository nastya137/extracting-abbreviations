import re
import pdfplumber
from prepare_data import extract_text, find_abbreviation_section

PDF_PATH = r"C:\Users\user\Desktop\extracting-abbreviations\documents\TPRTITUF-1123597508-171025-1540-582.pdf"

def clean_cell(text):
    if text is None:
        return ""
    return str(text).strip()

def extract_first_two_columns(pdf_path):
    results = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            table_list = page.extract_tables()
            if not table_list:
                start = page_text[:200]
                end = page_text[-200:] if len(page_text) > 200 else page_text
                print(f"--- Страница {page_num} (нет таблиц) ---")
                print(f"Начало страницы: {start}")
                print(f"Конец страницы: {end}")
                continue

            start = page_text[:200]
            end = page_text[-200:] if len(page_text) > 200 else page_text
            print(f"--- Страница {page_num} ---")
            print(f"Начало страницы: {start}")
            print(f"Конец страницы: {end}")

            for table_num, table in enumerate(table_list, start=1):
                for row in table:
                    if not row:
                        continue
                    cell1 = clean_cell(row[0] if len(row) > 0 else None)
                    cell2 = clean_cell(row[1] if len(row) > 1 else None)
                    if cell1 or cell2:
                        abbr = cell1.replace("\n", " ").strip()
                        abbr = abbr.removeprefix("Чтотакое").removeprefix("Ктотакой").removesuffix("?")
                        definition = cell2.replace("\n", " ").strip()
                        results.append((abbr, definition))
                        print(f"АББР: {abbr}\nОпределение: {definition}\n")
    return results

def inspect_pdf(pdf_path):
    print(f"Анализ файла: {pdf_path}")
    text = extract_text(pdf_path)
    pairs = extract_first_two_columns(pdf_path)
    return pairs

if __name__ == "__main__":
    inspect_pdf(PDF_PATH)