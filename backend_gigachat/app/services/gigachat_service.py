from gigachat import GigaChat
from app.core.config import settings
from app.core.logger import logger


class GigaChatService:
    def __init__(self):
        pass

    def _get_client(self) -> GigaChat:
        return GigaChat(
            credentials=settings.GIGACHAT_AUTH_KEY,
            scope=settings.GIGACHAT_SCOPE,
            model=settings.GIGACHAT_MODEL,
            ca_bundle_file=settings.GIGACHAT_CA_BUNDLE_FILE,
            verify_ssl_certs=True
        )

    def chat(self, messages: list, temperature: float = 0.2) -> str:
        formatted_messages = []

        for message in messages:
            formatted_messages.append({
                "role": message["role"],
                "content": message["content"]
            })

        with self._get_client() as giga:
            response = giga.chat({
                "messages": formatted_messages,
                "temperature": temperature,
            })

        return response.choices[0].message.content

    def upload_file(self, filename: str, content: bytes):
        logger.info(f"START upload_file | filename={filename} | size={len(content)}")

        with self._get_client() as giga:
            response = giga.upload_file(
                file=(filename, content)
            )

        logger.info(f"SUCCESS upload_file | filename={filename}")
        return response

    def chat_with_attachments(self, messages: list, attachments: list[str], temperature: float = 0.2) -> str:
        formatted_messages = []

        for message in messages:
            formatted_messages.append({
                "role": message["role"],
                "content": message["content"]
            })

        with self._get_client() as giga:
            response = giga.chat({
                "messages": formatted_messages,
                "attachments": attachments,
                "temperature": temperature,
            })

        return response.choices[0].message.content

    def extract_text_from_image(self, filename: str, content: bytes) -> str:
        logger.info(f"START extract_text_from_image | filename={filename}")

        uploaded = self.upload_file(filename=filename, content=content)
        file_id = uploaded.id_

        prompt = (
            "Распознай весь текст на изображении. "
            "Верни только чистый текст без markdown, комментариев и пояснений. "
            "Если текста на изображении нет, верни пустую строку."
        )

        raw = self.chat_with_attachments(
            messages=[
                {"role": "system", "content": "Ты извлекаешь текст из изображения."},
                {"role": "user", "content": prompt}
            ],
            attachments=[file_id],
            temperature=0
        )

        logger.info(f"SUCCESS extract_text_from_image | filename={filename}")
        return raw.strip()

    def extract_text_from_file(self, filename: str, content: bytes) -> str:
        logger.info(f"START extract_text_from_file | filename={filename}")

        uploaded = self.upload_file(filename=filename, content=content)
        file_id = uploaded.id_

        prompt = (
            "Извлеки текст из прикрепленного файла. "
            "Верни только чистый текст без markdown, комментариев и пояснений. "
            "Если текст извлечь невозможно, верни пустую строку."
        )

        raw = self.chat_with_attachments(
            messages=[
                {"role": "system", "content": "Ты извлекаешь текст из файла."},
                {"role": "user", "content": prompt}
            ],
            attachments=[file_id],
            temperature=0
        )

        logger.info(f"SUCCESS extract_text_from_file | filename={filename}")
        return raw.strip()


gigachat_service = GigaChatService()