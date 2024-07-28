import os
from PyPDF2 import PdfReader

def check_pdf_metadata(pdf_path):
    if not os.path.exists(pdf_path):
        print(f"File {pdf_path} does not exist.")
        return None

    with open(pdf_path, "rb") as f:
        reader = PdfReader(f)
        
        if reader.is_encrypted:
            try:
                reader.decrypt('')
            except:
                print(f"Failed to decrypt {pdf_path}")
                return None
        
        info = reader.metadata
        
        if info:
            print(f"Metadata for {pdf_path}:")
            print(f"  Title: {info.title if info.title else 'N/A'}")
            print(f"  Author: {info.author if info.author else 'N/A'}")
            print(f"  Subject: {info.subject if info.subject else 'N/A'}")
            print(f"  Producer: {info.producer if info.producer else 'N/A'}")
            print(f"  Creation Date: {info.creation_date if info.creation_date else 'N/A'}")
            print(f"  Mod Date: {info.modification_date if info.modification_date else 'N/A'}")
            return info
        else:
            print(f"No metadata found in {pdf_path}")
            return None

# Example usage
pdf_path = "/Users/paruparu/github/summarize_arxv/Depth-of-Field.pdf"  # これは絶対パスでも相対パスでも構いません
metadata = check_pdf_metadata(pdf_path)