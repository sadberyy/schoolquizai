import base64
from io import BytesIO

from PIL import Image, UnidentifiedImageError
from fastapi import HTTPException, UploadFile


class ImageService:
    MAX_UPLOAD_BYTES = 5 * 1024 * 1024
    MAX_WIDTH = 1024
    WEBP_QUALITY = 80
    ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}

    async def compress_upload_to_data_uri(self, file: UploadFile) -> str:
        """Сжимает загруженную картинку в WebP и возвращает data URI."""
        if file.content_type not in self.ALLOWED_MIME:
            raise HTTPException(415, f"Неподдерживаемый формат: {file.content_type}")

        contents = await file.read()
        if len(contents) == 0:
            raise HTTPException(400, "Пустой файл")
        if len(contents) > self.MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Файл слишком большой (макс. 5 МБ)")

        try:
            img = Image.open(BytesIO(contents))
            img.load()
        except (UnidentifiedImageError, OSError):
            raise HTTPException(400, "Файл не является корректным изображением")

        if img.width > self.MAX_WIDTH:
            img.thumbnail((self.MAX_WIDTH, self.MAX_WIDTH), Image.LANCZOS)

        if img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            mask = img.split()[-1] if img.mode in ("RGBA", "LA") else None
            background.paste(img, mask=mask)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        buffer = BytesIO()
        img.save(buffer, format="WEBP", quality=self.WEBP_QUALITY, method=6)
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")

        return f"data:image/webp;base64,{encoded}"

    def decode_data_uri(self, data_uri: str) -> tuple[bytes, str]:
        """Разбирает data URI на бинарь + MIME для отдачи через Response."""
        header, b64data = data_uri.split(",", 1)
        mime = header.split(";")[0].replace("data:", "")
        return base64.b64decode(b64data), mime


image_service = ImageService()