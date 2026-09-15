import re
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


PASSWORD_POLICY = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$")
MUNICIPAL_EMAIL_SUFFIX = "@cochabamba.bo"


def is_municipal_email(email: str) -> bool:
    return str(email).strip().lower().endswith(MUNICIPAL_EMAIL_SUFFIX)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserPublic(BaseModel):
    id: UUID
    email: EmailStr
    username: str | None = None
    first_name: str
    last_name: str
    document_number: str | None = None
    professional_reg: str | None = None
    auxiliary_email: EmailStr | None = None
    roles: list[str] = []
    must_have_professional_reg: bool = True
    must_change_password: bool = False

    model_config = {"from_attributes": True}


class LoginIn(BaseModel):
    login: str = Field(min_length=3, description="Usuario, correo o correo auxiliar")
    password: str = Field(min_length=6)


class RegisterIn(BaseModel):
    first_name: str = Field(min_length=2, max_length=120)
    last_name: str = Field(min_length=2, max_length=120)
    document_number: str = Field(min_length=5, max_length=40)
    professional_reg: str | None = Field(
        default=None,
        max_length=40,
        description="Nº registro Colegio de Arquitectos (obligatorio salvo correo @cochabamba.bo)",
    )
    email: EmailStr
    username: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8)
    password_confirm: str = Field(min_length=8)

    @field_validator("username")
    @classmethod
    def username_ok(cls, v: str) -> str:
        v = v.strip()
        if "@" in v:
            if not re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", v, flags=re.IGNORECASE):
                raise ValueError("Usuario no válido")
            return v.lower()
        if not re.fullmatch(r"[A-Za-z0-9._-]{3,40}", v):
            raise ValueError("Usuario solo puede tener letras, números, punto, guion o guion bajo")
        return v

    @field_validator("password")
    @classmethod
    def password_policy(cls, v: str) -> str:
        if not PASSWORD_POLICY.match(v):
            raise ValueError(
                "La contraseña debe tener al menos 8 caracteres, mayúsculas, minúsculas, números y un carácter especial"
            )
        return v

    @model_validator(mode="after")
    def passwords_and_reg(self) -> "RegisterIn":
        if self.password != self.password_confirm:
            raise ValueError("Las contraseñas no coinciden")
        email = str(self.email).lower()
        reg = (self.professional_reg or "").strip()
        self.username = email
        if is_municipal_email(email):
            self.professional_reg = reg or None
        else:
            if len(reg) < 3:
                raise ValueError("El número de registro del Colegio de Arquitectos es obligatorio")
            self.professional_reg = reg
        return self


class AuthResponse(BaseModel):
    token: TokenOut
    user: UserPublic


class ProfileUpdateIn(BaseModel):
    first_name: str = Field(min_length=2, max_length=120)
    last_name: str = Field(min_length=2, max_length=120)
    document_number: str = Field(min_length=5, max_length=40)
    auxiliary_email: EmailStr | None = None


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=6)
    password: str = Field(min_length=8)
    password_confirm: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def password_policy(cls, v: str) -> str:
        if not PASSWORD_POLICY.match(v):
            raise ValueError(
                "La contraseña debe tener al menos 8 caracteres, mayúsculas, minúsculas, números y un carácter especial"
            )
        return v

    @model_validator(mode="after")
    def passwords_match(self) -> "PasswordChangeIn":
        if self.password != self.password_confirm:
            raise ValueError("Las contraseñas no coinciden")
        return self
