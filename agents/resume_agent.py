import os
from PyPDF2 import PdfReader
from loguru import logger

class ResumeAgent:
    def __init__(self, resumes_dir: str = "data/resumes"):
        self.resumes_dir = resumes_dir

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        try:
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
            return text.strip()
        except Exception as e:
            logger.error(f"Failed to read PDF {pdf_path}: {e}")
            return ""

    def get_all_resumes(self) -> dict[str, str]:
        """Returns a dict of filename -> extracted text"""
        resumes = {}
        if not os.path.exists(self.resumes_dir):
            os.makedirs(self.resumes_dir)
            logger.warning(f"Resumes directory {self.resumes_dir} was empty/missing.")
            return resumes

        for filename in os.listdir(self.resumes_dir):
            if filename.endswith(".pdf"):
                full_path = os.path.join(self.resumes_dir, filename)
                text = self.extract_text_from_pdf(full_path)
                if text:
                    resumes[filename] = text
        return resumes
