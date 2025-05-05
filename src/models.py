from pydantic import BaseModel
from typing import List, Optional

class StrikeLevel(BaseModel):
    strike: float
    call_OI: int
    put_OI: int
    iv: Optional[float] = None
    GEX: Optional[float] = None

class OptionLevelsResponse(BaseModel):
    ticker: str
    expiry: str
    center_price: float
    width: int
    strikes: List[StrikeLevel]
