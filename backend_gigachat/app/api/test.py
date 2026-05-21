from fastapi import APIRouter, HTTPException
from app.services.gigachat_service import gigachat_service

router = APIRouter(prefix="/test", tags=["test"])

@router.get("/gigachat")
def test_gigachat():
    try:
        content = gigachat_service.chat(
            messages=[
                {"role": "system", "content": "Ты помощник для учителей."},
                {"role": "user", "content": "Придумай 2 коротких вопроса по теме фотосинтез."}
            ],
            temperature=0.2
        )
        return {"ok": True, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))