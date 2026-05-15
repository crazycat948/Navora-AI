from typing import Dict, List, Optional

from pydantic import BaseModel


class TripChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = None


class TripChatActionExecute(BaseModel):
    action: Dict
