from __future__ import annotations

import logging
import os
import shutil
import subprocess
import uuid
from pathlib import Path

from .utils import compact_text

logger = logging.getLogger(__name__)


class TesseractOcr:
    def __init__(
        self,
        tesseract_cmd: str | None = None,
        language: str = "rus+eng",
        timeout_seconds: int = 90,
    ) -> None:
        self.tesseract_cmd = tesseract_cmd
        self.language = language
        self.timeout_seconds = timeout_seconds

    def recognize_pdf(self, path: Path, dpi: int = 220) -> str:
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("PyMuPDF не установлен. Установите зависимости из requirements.txt.") from exc

        tesseract_cmd = self._resolve_tesseract_cmd()
        texts: list[str] = []
        zoom = dpi / 72
        matrix = fitz.Matrix(zoom, zoom)

        temp_path = self._temp_root()
        with fitz.open(path) as pdf:
            for page_index, page in enumerate(pdf, start=1):
                logger.info("OCR page %s/%s: %s", page_index, len(pdf), path.name)
                page_token = f"{path.stem}-{uuid.uuid4().hex}-page-{page_index:04d}"
                image_path = temp_path / f"{page_token}.png"
                output_base = temp_path / page_token
                output_text = Path(f"{output_base}.txt")

                pix = page.get_pixmap(matrix=matrix, alpha=False)
                try:
                    image_path.write_bytes(pix.tobytes("png"))
                except Exception as exc:
                    raise RuntimeError(
                        f"OCR не смог сохранить временное изображение страницы {page_index}. "
                        f"Проверьте права на папку {temp_path.resolve()}."
                    ) from exc

                command = [
                    tesseract_cmd,
                    str(image_path),
                    str(output_base),
                    "-l",
                    self.language,
                ]
                try:
                    completed = subprocess.run(
                        command,
                        capture_output=True,
                        text=True,
                        timeout=self.timeout_seconds,
                        check=False,
                    )
                except subprocess.TimeoutExpired as exc:
                    raise TimeoutError(
                        f"OCR превысил лимит {self.timeout_seconds} сек. на странице "
                        f"{page_index} файла {path.name}."
                    ) from exc

                if completed.returncode != 0:
                    message = (completed.stderr or completed.stdout or "").strip()
                    raise RuntimeError(
                        f"Tesseract OCR завершился с ошибкой на странице {page_index}: {message}"
                    )

                texts.append(output_text.read_text(encoding="utf-8", errors="ignore"))
                _safe_unlink(image_path)
                _safe_unlink(output_text)

        return compact_text("\n".join(texts))

    def _resolve_tesseract_cmd(self) -> str:
        candidates = [
            self.tesseract_cmd,
            shutil.which("tesseract"),
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return str(candidate)
        raise RuntimeError(
            "Tesseract OCR не найден. Укажите TESSERACT_CMD в .env, например "
            r"C:\Program Files\Tesseract-OCR\tesseract.exe."
        )

    @staticmethod
    def _temp_root() -> Path:
        temp_root = Path(os.environ.get("LEGAL_CLAIM_TMP_DIR", ".tmp")) / "ocr"
        temp_root.mkdir(parents=True, exist_ok=True)
        test_file = temp_root / f"write-test-{uuid.uuid4().hex}.txt"
        try:
            test_file.write_text("ok", encoding="utf-8")
        except Exception as exc:
            raise RuntimeError(f"OCR не смог писать во временную папку {temp_root.resolve()}: {exc}") from exc
        finally:
            _safe_unlink(test_file)
        return temp_root


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except PermissionError:
        logger.debug("Cannot delete temporary OCR file: %s", path)
