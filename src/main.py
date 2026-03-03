import os
from pathlib import Path
from src.prepare_data import answer_query, process_pdf_folder
#Используется для демонстрации работы модуля
def main():
    root_project = Path(__file__).absolute().parents[1]
    documents_dir = root_project/"documents"
    output_json = root_project/"data/abbreviations.json"

    if not os.path.isdir(documents_dir):
        raise FileNotFoundError(
            "Папка documents не найдена в корне проекта. "
            "Создайте её и положите туда PDF-файлы."
        )

    database = process_pdf_folder(documents_dir, output_json=output_json)
    print(f"Готово. Извлечено аббревиатур: {len(database)}")
    print(f"Результат сохранён в: {os.path.abspath(output_json)}")

    while(True):
        query = input("\nВведите аббревиатуру или вопрос (Enter чтобы выйти): ").strip()
        if not query:
            return

        for line in answer_query(query, database):
            print(f"- {line}")


if __name__ == "__main__":
    main()