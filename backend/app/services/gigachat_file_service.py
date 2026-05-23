import json
import mimetypes
import os
import tempfile

from gigachat import GigaChat

from app.core.config import settings
from app.core.logger import logger
from app.schemas.material import SourceFragment


class GigaChatFileService:
    def _extract_json(self, raw_text: str) -> dict:
        raw_text = raw_text.strip()

        if raw_text.startswith("```"):
            raw_text = raw_text.replace("```json", "").replace("```", "").strip()

        return json.loads(raw_text)

    def _guess_content_type(self, filename: str) -> str:
        content_type, _ = mimetypes.guess_type(filename)
        return content_type or "application/octet-stream"

    def extract_fragments_from_file(self, filename: str, content: bytes) -> list[SourceFragment]:
        logger.info(f"GIGACHAT_FILE_FALLBACK_START filename={filename} size={len(content)}")

        content_type = self._guess_content_type(filename)

        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            with GigaChat(
                credentials=settings.GIGACHAT_AUTH_KEY,
                scope=settings.GIGACHAT_SCOPE,
                model=settings.GIGACHAT_MODEL,
                ca_bundle_file=settings.GIGACHAT_CA_BUNDLE_FILE,
                verify_ssl_certs=True
            ) as giga:

                with open(tmp_path, "rb") as f:
                    uploaded = giga.upload_file(
                        file=(filename, f.read(), content_type)
                    )

                file_id = getattr(uploaded, "id_", None) or getattr(uploaded, "id", None)

                if not file_id:
                    raise ValueError("Не удалось получить file_id после загрузки файла в GigaChat")

                prompt = f"""
Ты анализируешь загруженный учебный материал и извлекаешь из него смысловые фрагменты для генерации школьной викторины.

Верни только валидный JSON без markdown и пояснений в формате:
{{
  "fragments": [
    {{
      "fragment_id": "file_fragment_1",
      "source_type": "file_fallback",
      "source_name": "{filename}",
      "text": "короткий осмысленный фрагмент текста"
    }}
  ]
}}

Требования:
- Извлеки только важные учебные фрагменты.
- Если файл содержит сканы, изображения или текст на картинках — распознай их содержательно.
- Верни от 3 до 8 фрагментов, если материал позволяет.
- Каждый fragment_id должен быть уникален.
- text должен быть кратким, но содержательным.
- Не пиши ничего вне JSON.
"""

                response = giga.chat({
                    "messages": [
                        {"role": "system", "content": "Ты возвращаешь только валидный JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "attachments": [file_id],
                    "temperature": 0.2,
                })

                raw = response.choices[0].message.content
                logger.info(f"GIGACHAT_FILE_FALLBACK_RAW: {raw[:2000]}")

                data = self._extract_json(raw)

                fragments = []
                for item in data.get("fragments", []):
                    fragments.append(
                        SourceFragment(
                            fragment_id=item["fragment_id"],
                            source_type=item.get("source_type", "file_fallback"),
                            source_name=item.get("source_name", filename),
                            text=item["text"]
                        )
                    )

                logger.info(
                    f"GIGACHAT_FILE_FALLBACK_SUCCESS filename={filename} fragments_count={len(fragments)}"
                )

                return fragments

        except Exception as e:
            logger.error(f"GIGACHAT_FILE_FALLBACK_ERROR filename={filename} error={str(e)}")
            raise

        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass


gigachat_file_service = GigaChatFileService()