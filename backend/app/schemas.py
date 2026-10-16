from pydantic import BaseModel
from typing import Optional

# Base properties shared across creation and reading
class ChurchBase(BaseModel):
    name: str

# What the frontend sends when creating a church
class ChurchCreate(ChurchBase):
    pass

# What the API returns to the frontend
class ChurchResponse(ChurchBase):
    id: int
    qr_code_hash: str

    class Config:
        # Tells Pydantic to read data even if it's not a dict (like a SQLAlchemy model)
        from_attributes = True

# What the operator console sends to log in
class OperatorLoginRequest(BaseModel):
    email: str
    password: str

# What the API returns after a successful operator login
class OperatorLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    church_id: int

# What the API returns for the authenticated operator
class OperatorProfileResponse(BaseModel):
    email: str
    church_id: int

# What the API returns after a successful QR scan
class GuestJoinResponse(BaseModel):
    status: str
    user_id: int              # The silent guest ID
    church_name: str
    is_live: bool             # The traffic cop flag (True = Live Room, False = Waiting Room)
    room_id: Optional[int]    # Null if not live, an Integer if live

    class Config:
        from_attributes = True