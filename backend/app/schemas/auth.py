from typing import Any
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)
from pydantic.alias_generators import to_camel


class RegisterRequest(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )

    full_name: str = Field(..., min_length=1, max_length=150)
    email: EmailStr
    password: str = Field(..., min_length=8)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("fullName cannot be empty or whitespace only")
        if len(trimmed) > 150:
            raise ValueError("fullName cannot exceed 150 characters")
        return trimmed


class LoginRequest(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )

    email: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    id: str
    full_name: str
    email: str

    @model_validator(mode="before")
    @classmethod
    def map_user_attributes(cls, data: Any) -> Any:
        if hasattr(data, "user_id"):
            return {
                "id": str(data.user_id),
                "fullName": data.full_name,
                "email": data.email,
            }
        if isinstance(data, dict):
            mapped = dict(data)
            if "user_id" in mapped and "id" not in mapped:
                mapped["id"] = str(mapped["user_id"])
            elif "id" in mapped:
                mapped["id"] = str(mapped["id"])
            return mapped
        return data


class AuthResponse(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    access_token: str
    token_type: str = "bearer"
    user: UserOut
