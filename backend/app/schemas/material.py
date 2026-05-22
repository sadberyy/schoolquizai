from pydantic import BaseModel

class SourceFragment(BaseModel):
    fragment_id: str
    source_type: str
    source_name: str
    text: str