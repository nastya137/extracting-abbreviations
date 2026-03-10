import sys
import re
from prepare_data import extract_text, find_abbreviation_section

PDF_PATH = "C:/Users/user/Desktop\extracting-abbreviations\documents\TPRTITUF-1175220058-030226-1204-2997.pdf"

def inspect_pdf(pdf_path):
    text = extract_text(pdf_path)
    print(f"Анализ файла: {pdf_path}")
    text = extract_text(pdf_path)   
    section = find_abbreviation_section(text)
    if section:
        print(f"\n--- РАЗДЕЛ СОКРАЩЕНИЙ (длина {len(section)} символов) ---")
        lines = section.splitlines()
        print(f"Всего строк в разделе: {len(lines)}")
        print(section)
    else:
        print("\n--- РАЗДЕЛ СОКРАЩЕНИЙ НЕ НАЙДЕН ---")

if __name__ == "__main__":
    inspect_pdf(PDF_PATH)