"""
Сервис для работы с временными загрузками учителя.

Этот модуль отвечает за:
- создание записи о временно загруженном файле;
- сохранение отдельных текстовых блоков из загруженного материала;
- получение полного текста временной загрузки;
- очистку временных загрузок конкретного учителя.

Временные загрузки используются, когда учитель загружает PDF, DOCX, TXT,
презентацию или другой материал для генерации викторины, но ещё не сохраняет
его в постоянную библиотеку.
"""

from app.db.database import get_db_session
from app.db.models import TemporaryUpload, TemporaryBlock


def create_temporary_upload(
    teacher_id: str | None,
    original_filename: str,
    file_type: str,
    stored_path: str | None = None,
    extracted_text: str | None = None,
):
    """
    Создаёт запись о временно загруженном материале.

    Используется после того, как учитель загрузил файл или передал текст
    для генерации викторины.

    Если текст уже был извлечён из файла, загрузка сразу получает статус
    "processed". Если текста пока нет, статус будет "uploaded".

    Args:
        teacher_id: ID учителя, загрузившего материал. Может быть None,
            если загрузка не привязана к конкретному учителю.
        original_filename: исходное имя файла.
        file_type: тип файла или источника, например "pdf", "docx", "txt",
            "pptx", "manual_text".
        stored_path: путь к сохранённому файлу на диске или в файловом хранилище.
        extracted_text: уже извлечённый текст из файла, если он есть.

    Returns:
        ID созданной временной загрузки.
    """

    with get_db_session() as session:
        upload = TemporaryUpload(
            teacher_id=teacher_id,
            original_filename=original_filename,
            file_type=file_type,
            stored_path=stored_path,
            extracted_text=extracted_text,
            status="processed" if extracted_text else "uploaded",
        )

        session.add(upload)
        session.flush()
        session.refresh(upload)

        return upload.id


def add_temporary_block(
    upload_id: str,
    block_type: str,
    content: str,
    order_idx: int = 0,
    page_num: int | None = None,
    slide_num: int | None = None,
    image_path: str | None = None,
    meta: dict | None = None,
):
    """
    Добавляет текстовый или структурный блок к временной загрузке.

    После обработки файла его удобно разбивать на отдельные части:
    страницы, абзацы, слайды, таблицы или OCR-текст с изображений.
    Эти части сохраняются как TemporaryBlock.

    Args:
        upload_id: ID временной загрузки, к которой относится блок.
        block_type: тип блока, например "text", "paragraph", "page",
            "slide", "table", "image_ocr".
        content: текстовое содержимое блока.
        order_idx: порядковый номер блока внутри материала.
        page_num: номер страницы, если блок получен из PDF/документа.
        slide_num: номер слайда, если блок получен из презентации.
        image_path: путь к изображению, если блок связан с картинкой.
        meta: дополнительные метаданные блока в формате dict.

    Returns:
        ID созданного блока.
    """

    with get_db_session() as session:
        block = TemporaryBlock(
            upload_id=upload_id,
            block_type=block_type,
            content=content,
            order_idx=order_idx,
            page_num=page_num,
            slide_num=slide_num,
            image_path=image_path,
            meta=meta or {},
        )

        session.add(block)
        session.flush()
        session.refresh(block)

        return block.id


def get_temporary_upload_text(upload_id: str) -> str:
    """
    Возвращает полный текст временной загрузки из всех её блоков.

    Блоки сортируются по order_idx, чтобы восстановить исходный порядок
    текста в документе. Затем содержимое блоков объединяется через пустую строку.

    Args:
        upload_id: ID временной загрузки.

    Returns:
        Полный текст временной загрузки, собранный из блоков.
        Если блоков нет, вернётся пустая строка.
    """

    with get_db_session() as session:
        blocks = (
            session.query(TemporaryBlock)
            .filter(TemporaryBlock.upload_id == upload_id)
            .order_by(TemporaryBlock.order_idx)
            .all()
        )

        if blocks:
            return "\n\n".join(block.content for block in blocks)

        upload = (
            session.query(TemporaryUpload)
            .filter(TemporaryUpload.id == upload_id)
            .first()
        )
        return (upload.extracted_text or "") if upload else ""


def clear_teacher_temporary_uploads(teacher_id: str) -> int:
    """
    Удаляет все временные загрузки конкретного учителя.

    Args:
        teacher_id: ID учителя.

    Returns:
        Количество удалённых временных загрузок.
    """

    with get_db_session() as session:
        uploads = (
            session.query(TemporaryUpload)
            .filter(TemporaryUpload.teacher_id == teacher_id)
            .all()
        )

        deleted_count = len(uploads)

        for upload in uploads:
            session.delete(upload)

    print(f"[INFO] Удалено временных загрузок учителя {teacher_id}: {deleted_count}")

    return deleted_count