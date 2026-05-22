from enum import Enum
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from app.core.logger import logger
from app.schemas.quiz import DifficultyLevel
from app.schemas.material import SourceFragment
from app.services.material_service import material_service
from app.services.gigachat_service import gigachat_service
from app.services.quiz_service import quiz_service


router = APIRouter(prefix="/quiz", tags=["Quiz"])


class QuestionType(str, Enum):
    single_choice = "single_choice"
    multiple_choice = "multiple_choice"
    true_false = "true_false"


PLACEHOLDER_TEXTS = {"string", "source_text", "null", "none"}


def _normalize_source_text(value: str | None) -> str:
    text = (value or "").strip()
    if text.lower() in PLACEHOLDER_TEXTS:
        return ""
    return text


@router.post("/generate-from-materials")
async def generate_quiz_from_materials(
    subject: str = Form(...),
    grade: str = Form(...),
    topic: str = Form(...),
    question_count: int = Form(...),
    question_types: list[QuestionType] = Form(...),
    difficulty: DifficultyLevel = Form(...),
    source_text: str | None = Form(None),
    file: UploadFile | None = File(None),
    image: UploadFile | None = File(None),
):
    logger.info(
        f"START /quiz/generate-from-materials | subject={subject} | grade={grade} | "
        f"topic={topic} | question_count={question_count} | question_types={question_types} | "
        f"difficulty={difficulty}"
    )

    cleaned_source_text = _normalize_source_text(source_text)

    if not cleaned_source_text and file is None and image is None:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one source: source_text, file, or image."
        )

    parsed_question_types = [item.value for item in question_types]
    all_fragments: list[SourceFragment] = []

    if cleaned_source_text:
        logger.info(f"PROCESS SOURCE_TEXT | length={len(cleaned_source_text)}")
        all_fragments.append(
            SourceFragment(
                fragment_id="manual_1",
                source_type="manual_text",
                source_name="teacher_input",
                text=cleaned_source_text
            )
        )

    if file is not None:
        logger.info(
            f"PROCESS FILE | filename={file.filename} | content_type={file.content_type}"
        )
        file_content = await file.read()

        if not file_content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        try:
            file_type, file_fragments = material_service.extract_fragments(
                file.filename,
                file_content
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        logger.info(
            f"FILE PROCESSED | filename={file.filename} | file_type={file_type} | "
            f"fragments_count={len(file_fragments)}"
        )

        if file_type in {"pdf", "pptx", "docx", "doc"} and material_service.has_too_little_text(file_fragments):
            logger.info(f"FILE FALLBACK START | filename={file.filename} | file_type={file_type}")

            extracted_text = gigachat_service.extract_text_from_file(
                file.filename,
                file_content
            )

            if extracted_text and extracted_text.strip():
                file_fragments = [
                    SourceFragment(
                        fragment_id=f"{file_type}_fallback_1",
                        source_type=file_type,
                        source_name=file.filename,
                        text=extracted_text.strip()
                    )
                ]

            logger.info(
                f"FILE FALLBACK DONE | filename={file.filename} | "
                f"fallback_fragments_count={len(file_fragments)}"
            )

        all_fragments.extend(file_fragments)

    if image is not None:
        logger.info(
            f"PROCESS IMAGE | filename={image.filename} | content_type={image.content_type}"
        )
        image_content = await image.read()

        if not image_content:
            raise HTTPException(status_code=400, detail="Uploaded image is empty.")

        image_text = gigachat_service.extract_text_from_image(
            image.filename,
            image_content
        )

        if image_text and image_text.strip():
            all_fragments.append(
                SourceFragment(
                    fragment_id="image_1",
                    source_type="image",
                    source_name=image.filename,
                    text=image_text.strip()
                )
            )

        logger.info(
            f"IMAGE PROCESSED | filename={image.filename} | "
            f"extracted_len={len(image_text) if image_text else 0}"
        )

    merged_fragments = material_service.merge_fragments(None, all_fragments)

    if not merged_fragments:
        raise HTTPException(
            status_code=400,
            detail="Could not extract any usable text from provided sources."
        )

    logger.info(
        f"MERGED FRAGMENTS | count={len(merged_fragments)} | "
        f"fragment_ids={[fragment.fragment_id for fragment in merged_fragments]}"
    )

    result = quiz_service.generate_quiz_from_fragments(
        subject=subject,
        grade=grade,
        topic=topic,
        question_count=question_count,
        question_types=parsed_question_types,
        difficulty=difficulty,
        fragments=merged_fragments
    )

    logger.info(
        f"SUCCESS /quiz/generate-from-materials | title={result.quiz_title} | "
        f"questions_count={len(result.questions)}"
    )

    return result