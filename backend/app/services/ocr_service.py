import os
import io
import logging
from typing import Tuple, Dict, Any, Optional
import pymupdf
from PIL import Image, ImageEnhance, ImageFilter
from app.core.config import settings

logger = logging.getLogger(__name__)

# Configure tesseract executable if available
try:
    import pytesseract
    if os.path.exists(settings.TESSERACT_CMD):
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
except Exception as e:
    logger.warning(f"Tesseract module initialization note: {e}")

class OCRService:
    @staticmethod
    def preprocess_image(image: Image.Image) -> Image.Image:
        """
        Enhance image quality for OCR:
        - Convert to grayscale
        - Resize if too small
        - Enhance contrast
        - Apply slight median filter for noise reduction
        """
        # Convert to Grayscale
        gray = image.convert("L")

        # Resize if width < 1200px
        if gray.width < 1200:
            scale = 1200 / float(gray.width)
            new_height = int(float(gray.height) * scale)
            gray = gray.resize((1200, new_height), Image.Resampling.LANCZOS)

        # Enhance contrast
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(1.8)

        # Noise reduction
        denoised = enhanced.filter(ImageFilter.MedianFilter(size=3))
        return denoised

    @classmethod
    def extract_from_pdf(cls, file_path: str) -> Tuple[str, Dict[str, Any]]:
        """
        Extract text from digital or scanned multipage PDF.
        Returns: (extracted_text, metadata)
        """
        extracted_pages = []
        is_scanned = False
        doc = pymupdf.open(file_path)
        total_pages = len(doc)

        for page_num in range(total_pages):
            page = doc[page_num]
            text = page.get_text("text").strip()

            if len(text) > 30:
                # Digital text present
                extracted_pages.append(text)
            else:
                # Page seems scanned or image-based, attempt OCR fallback
                is_scanned = True
                pix = page.get_pixmap(dpi=200)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                processed_img = cls.preprocess_image(img)

                ocr_text = cls._run_tesseract(processed_img)
                if ocr_text:
                    extracted_pages.append(ocr_text)
                else:
                    extracted_pages.append(text)

        doc.close()
        full_text = "\n\n".join(extracted_pages).strip()

        metadata = {
            "total_pages": total_pages,
            "extraction_method": "Tesseract OCR" if is_scanned else "PyMuPDF Digital Parser",
            "is_scanned": is_scanned,
        }
        return full_text, metadata

    @classmethod
    def extract_from_image(cls, file_path: str) -> Tuple[str, Dict[str, Any]]:
        """
        Extract text from image resume (JPG, JPEG, PNG).
        """
        img = Image.open(file_path)
        processed_img = cls.preprocess_image(img)
        text = cls._run_tesseract(processed_img)
        metadata = {
            "total_pages": 1,
            "extraction_method": "Tesseract OCR Image Processing",
            "is_scanned": True,
        }
        return text, metadata

    @classmethod
    def _run_tesseract(cls, image: Image.Image) -> str:
        """Run pytesseract if installed, otherwise log clear note."""
        try:
            import pytesseract
            if os.path.exists(settings.TESSERACT_CMD) or os.system("where tesseract >nul 2>&1") == 0:
                return pytesseract.image_to_string(image).strip()
            else:
                logger.info("Tesseract binary not found at configured path. Returning empty image OCR.")
                return ""
        except Exception as e:
            logger.warning(f"OCR execution warning: {e}")
            return ""

    @classmethod
    def process_file(cls, file_path: str, mime_type: str) -> Tuple[str, Dict[str, Any]]:
        """Unified entry point for resume file extraction."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Resume file not found at: {file_path}")

        mime_type = mime_type.lower()
        if "pdf" in mime_type or file_path.lower().endswith(".pdf"):
            return cls.extract_from_pdf(file_path)
        elif any(ext in mime_type for ext in ["jpeg", "jpg", "png"]) or any(
            file_path.lower().endswith(ext) for ext in [".jpeg", ".jpg", ".png"]
        ):
            return cls.extract_from_image(file_path)
        else:
            raise ValueError(f"Unsupported file format: {mime_type}")
