from dataclasses import asdict

from fastapi import APIRouter, HTTPException, status

from app.generator import GeneratorOptions, generate
from app.schemas import GenerateParams, PasswordIn, StrengthOut
from app.strength import check

router = APIRouter(prefix="/api/tools", tags=["Инструменты"])


@router.post("/generate")
def generate_passwords(params: GenerateParams) -> dict[str, list[dict]]:
    opts = GeneratorOptions(**params.model_dump(exclude={"count"}))
    try:
        passwords = [generate(opts) for _ in range(params.count)]
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return {"passwords": [{"password": p, "strength": asdict(check(p))} for p in passwords]}


@router.post("/check", response_model=StrengthOut)
def check_password(data: PasswordIn) -> dict:
    # POST, а не GET: пароль не должен попадать в URL и логи веб-сервера
    return asdict(check(data.password))
