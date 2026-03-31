from prepare_data import extract_text, find_abbreviation_section

PDF_PATH = "C:/Users/user/Desktop\extract_abbreviations\extracting-abbreviations\documents\TPRTITUF-1123597508-171025-1540-582.pdf"

def inspect_pdf(pdf_path):
    text = extract_text(pdf_path)
    print(f"Текст файла: {pdf_path}")
    text = extract_text(pdf_path)   
    print(text)

if __name__ == "__main__":
    inspect_pdf(PDF_PATH)