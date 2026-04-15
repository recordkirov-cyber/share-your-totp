import asyncio
import base64
import binascii
import hashlib
import hmac
import time
import threading
import uuid
from typing import Dict, List

from fastapi import FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field, validator

app = FastAPI(
    title="Share Your TOTP",
    description="Приватное одноразовое деление TOTP-секретами через временные ссылки.",
)

STORE_LOCK = threading.Lock()
STORE: Dict[str, Dict] = {}
CLEANUP_INTERVAL_SECONDS = 30
DEFAULT_STEP_SECONDS = 30
ALLOWED_ALGORITHMS = {"SHA1": "sha1", "SHA256": "sha256", "SHA512": "sha512"}
ALLOWED_DIGITS = {6, 7, 8}
MAX_LIFETIME_HOURS = 48


class CreatePayload(BaseModel):
    secret: str = Field(..., min_length=1)
    algorithm: str = Field("SHA1")
    digits: int = Field(6)
    hours: float = Field(...)
    burn_after_read: bool = Field(False)

    @validator("algorithm")
    def validate_algorithm(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in ALLOWED_ALGORITHMS:
            raise ValueError("Алгоритм должен быть SHA1, SHA256 или SHA512")
        return normalized

    @validator("digits")
    def validate_digits(cls, value: int) -> int:
        if value not in ALLOWED_DIGITS:
            raise ValueError("Количество цифр должно быть 6, 7 или 8")
        return value

    @validator("hours")
    def validate_hours(cls, value: float) -> float:
        if value <= 0 or value > MAX_LIFETIME_HOURS:
            raise ValueError(f"Время жизни должно быть от 0 до {MAX_LIFETIME_HOURS} часов")
        return value


def normalize_secret(secret: str) -> bytes:
    text = secret.strip().replace(" ", "")
    try:
        return base64.b32decode(text.upper(), casefold=True)
    except (binascii.Error, TypeError):
        return secret.encode("utf-8")


def totp_code(secret: bytes, counter: int, digits: int, algorithm: str) -> str:
    counter_bytes = counter.to_bytes(8, byteorder="big")
    digest_name = ALLOWED_ALGORITHMS[algorithm]
    digest = hmac.new(secret, counter_bytes, digest_name).digest()
    offset = digest[-1] & 0x0F
    code_int = int.from_bytes(digest[offset : offset + 4], byteorder="big") & 0x7FFFFFFF
    return str(code_int % (10**digits)).zfill(digits)


def generate_totp_slots(secret: bytes, digits: int, algorithm: str, expires_at: float) -> List[Dict]:
    now = time.time()
    start_counter = int(now) // DEFAULT_STEP_SECONDS
    end_counter = int(expires_at) // DEFAULT_STEP_SECONDS
    slots = []
    for counter in range(start_counter, end_counter + 1):
        slots.append(
            {
                "counter": counter,
                "code": totp_code(secret, counter, digits, algorithm),
                "expires_at": (counter + 1) * DEFAULT_STEP_SECONDS,
            }
        )
    return slots


def cleanup_expired_entries() -> None:
    now = time.time()
    with STORE_LOCK:
        expired = [token for token, entry in STORE.items() if entry["expires_at"] <= now]
        for token in expired:
            del STORE[token]


async def cleanup_loop() -> None:
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        cleanup_expired_entries()


def format_html(content: str) -> HTMLResponse:
    return HTMLResponse(
        f"""
        <!DOCTYPE html>
        <html lang="ru">
        <head>
          <meta charset="UTF-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1.0" />
          <title>Share Your TOTP</title>
          <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 24px; background: #f5f7fb; color: #202124; }}
            .page {{ max-width: 720px; margin: 0 auto; background: white; padding: 28px; border-radius: 14px; box-shadow: 0 18px 45px rgba(0,0,0,.08); }}
            input[type="text"], input[type="number"], input[type="email"], select {{ width: 100%; padding: 12px 14px; margin: 8px 0; border: 1px solid #cbd5e1; border-radius: 10px; box-sizing: border-box; }}
            input[type="checkbox"] {{ width: auto; margin: 0 8px 0 0; cursor: pointer; vertical-align: middle; }}
            label {{ display: block; margin: 12px 0 6px 0; font-weight: 500; }}
            label.checkbox-label {{ display: flex; align-items: center; margin: 12px 0; font-weight: normal; }}
            label.checkbox-label input {{ margin: 0 8px 0 0; }}
            button {{ width: 100%; padding: 12px 14px; margin: 8px 0; border: 1px solid #cbd5e1; border-radius: 10px; background: #2563eb; color: white; border: none; cursor: pointer; font-size: 1rem; }}
            button:hover {{ background: #1d4ed8; }}
            .small {{ font-size: 0.95rem; color: #4b5563; }}
            .alert {{ background: #eff6ff; padding: 12px 14px; border-left: 4px solid #2563eb; margin-bottom: 16px; border-radius: 8px; word-break: break-word; overflow-wrap: break-word; }}
            code {{ background: #f3f4f6; padding: 2px 4px; border-radius: 4px; font-size: 0.9rem; }}
            @media (max-width: 600px) {{
              body {{ padding: 16px; }}
              .page {{ padding: 16px; }}
              .alert {{ padding: 10px 12px; font-size: 0.9rem; }}
              button {{ font-size: 0.95rem; }}
            }}
          </style>
        </head>
        <body>
          <div class="page">
            {content}
          </div>
        </body>
        </html>
        """
    )


def get_entry(token: str) -> Dict:
    with STORE_LOCK:
        entry = STORE.get(token)
        if not entry:
            raise HTTPException(status_code=404, detail="Ссылка устарела или не существует")
        return entry


def delete_entry(token: str) -> None:
    with STORE_LOCK:
        STORE.pop(token, None)


def current_totp(entry: Dict) -> str:
    current_counter = int(time.time()) // DEFAULT_STEP_SECONDS
    for slot in entry["slots"]:
        if slot["counter"] == current_counter:
            return slot["code"]
    raise HTTPException(status_code=410, detail="Ссылка устарела или код уже недоступен")


@app.on_event("startup")
async def startup_event() -> None:
    app.state.cleanup_task = asyncio.create_task(cleanup_loop())


@app.on_event("shutdown")
async def shutdown_event() -> None:
    task = getattr(app.state, "cleanup_task", None)
    if task:
        task.cancel()


@app.get("/", response_class=HTMLResponse)
def homepage() -> HTMLResponse:
    return format_html(
        """
        <h1>Share Your TOTP</h1>
        <p class="small">
          Приватное хранение и одноразовый просмотр TOTP без аутентификации и без хранения метаданных.
        </p>
        <form method="post" action="/create">
          <label>Приватный ключ TOTP</label>
          <input type="text" name="secret" required placeholder="Base32 или текст" />

          <label>Алгоритм</label>
          <select name="algorithm">
            <option>SHA1</option>
            <option>SHA256</option>
            <option>SHA512</option>
          </select>

          <label>Количество цифр</label>
          <select name="digits">
            <option>6</option>
            <option>7</option>
            <option>8</option>
          </select>

          <label>Ссылка живёт, часов</label>
          <input name="hours" type="number" min="0.01" max="48" step="0.01" value="1" required />

          <label class="checkbox-label">
            <input type="checkbox" name="burn_after_read" value="true" />
            Уничтожить после просмотра
          </label>

          <button type="submit">Создать приватную ссылку</button>
        </form>
        <div class="alert">
          <strong>API:</strong> POST /api/create с JSON {"secret","algorithm","digits","hours","burn_after_read"} возвращает ссылку.
        </div>
        """
    )


@app.post("/create", response_class=HTMLResponse)
async def create_form(
    request: Request,
    secret: str = Form(...),
    algorithm: str = Form("SHA1"),
    digits: int = Form(6),
    hours: float = Form(...),
    burn_after_read: str = Form(None),
) -> HTMLResponse:
    payload = CreatePayload(
        secret=secret,
        algorithm=algorithm,
        digits=digits,
        hours=hours,
        burn_after_read=bool(burn_after_read),
    )
    token = await create_secret_entry(payload)
    link = str(request.url_for("view_secret", token=token))
    return format_html(
        f"""
        <h1>Ссылка создана</h1>
        <div class=\"alert\">Ссылка активна {payload.hours} ч.</div>
        <p>Используйте эту ссылку для просмотра TOTP:</p>
        <button id="copyBtn" style="width: 100%; padding: 12px 14px; margin: 8px 0; border: 1px solid #cbd5e1; border-radius: 10px; background: #f0f0f0; color: #202124; cursor: pointer;" onclick="copyToClipboard('{htmlescape(link)}')">
          📋 Скопировать ссылку
        </button>
        <p id="copyMsg" style="display: none; color: #10b981; font-weight: bold; margin-top: 8px;">✓ Скопировано в буфер!</p>
        <p><a href=\"{htmlescape(link)}\">Или открыть ссылку напрямую →</a></p>
        <script>
          function copyToClipboard(text) {{
            navigator.clipboard.writeText(text).then(() => {{
              const btn = document.getElementById('copyBtn');
              const msg = document.getElementById('copyMsg');
              btn.style.display = 'none';
              msg.style.display = 'block';
              setTimeout(() => {{
                btn.style.display = 'block';
                msg.style.display = 'none';
              }}, 2000);
            }});
          }}
        </script>
        """
    )


@app.post("/api/create")
async def api_create(request: Request, payload: CreatePayload) -> JSONResponse:
    token = await create_secret_entry(payload)
    link = str(request.url_for("view_secret", token=token))
    return JSONResponse({"url": link})


async def create_secret_entry(payload: CreatePayload) -> str:
    secret_bytes = normalize_secret(payload.secret)
    expires_at = time.time() + payload.hours * 3600
    slots = generate_totp_slots(secret_bytes, payload.digits, payload.algorithm, expires_at)
    token = uuid.uuid4().hex
    with STORE_LOCK:
        STORE[token] = {
            "slots": slots,
            "expires_at": expires_at,
            "burn_after_read": payload.burn_after_read,
            "digits": payload.digits,
            "algorithm": payload.algorithm,
        }
    return token


@app.get("/secret/{token}", response_class=HTMLResponse)
def view_secret(token: str) -> HTMLResponse:
    try:
        entry = get_entry(token)
    except HTTPException:
        return format_html(
            """
            <h1>❌ Ссылка устарела</h1>
            <p class="alert">Ссылка больше недоступна. Она могла истечь по времени или уже просмотрена с флагом "burn after read".</p>
            <p><a href="/">← Вернуться на главную</a></p>
            """
        )
    
    burn = "true" if entry["burn_after_read"] else "false"
    return format_html(
        f"""
        <h1>Просмотр TOTP</h1>
        <p class=\"small\">Нажмите кнопку ниже, чтобы увидеть ТОТР. Это защищает от предпросмотра ссылки.</p>
        <button id="revealBtn" type="button" onclick="revealTotp()">Просмотреть ТОТР</button>
        <div id="totpContainer" style="display: none; margin-top: 24px;">
          <div id="progressContainer" style="margin-bottom: 20px;">
            <div style="width: 100%; height: 8px; background: #e5e7eb; border-radius: 4px; overflow: hidden;">
              <div id="progressBar" style="height: 100%; background: #2563eb; width: 0%; transition: width 0.1s linear;"></div>
            </div>
            <p id="timeLeft" style="font-size: 0.9rem; color: #6b7280; margin-top: 8px; text-align: center;">Время до обновления: <strong id="secondsLeft">30</strong>с</p>
          </div>
          <p id="totpCode" style="font-size: 2.5rem; font-weight: bold; text-align: center; letter-spacing: 0.2em; background: #f3f4f6; padding: 20px; border-radius: 10px; font-family: monospace;">---</p>
          <p class="small" style="text-align: center; margin-top: 16px;"><span id="algorithmInfo\"></span></p>
        </div>
        <script>
          const token = '{htmlescape(token)}';
          const burnAfterRead = {burn};
          let updateInterval = null;
          
          function revealTotp() {{
            document.getElementById('revealBtn').style.display = 'none';
            document.getElementById('totpContainer').style.display = 'block';
            updateTotpCode();
            updateInterval = setInterval(updateTotpCode, 500);
          }}
          
          function updateTotpCode() {{
            fetch(`/secret/${{token}}/current`)
              .then(r => {{
                if (r.status === 410) {{
                  clearInterval(updateInterval);
                  document.getElementById('totpContainer').innerHTML = '<p style=\"color: #dc2626; font-weight: bold;\">⚠️ Ссылка устарела или уже просмотрена</p>';
                  return null;
                }}
                return r.json();
              }})
              .then(data => {{
                if (!data) return;
                document.getElementById('totpCode').textContent = data.code;
                document.getElementById('algorithmInfo').textContent = `Алгоритм: ${{data.algorithm}}, цифр: ${{data.digits}}`;
                
                const remaining = Math.ceil(data.seconds_left);
                const progress = ((30 - remaining) / 30) * 100;
                document.getElementById('progressBar').style.width = progress + '%';
                document.getElementById('secondsLeft').textContent = remaining;
              }})
              .catch(() => {{
                clearInterval(updateInterval);
                document.getElementById('totpContainer').innerHTML = '<p style=\"color: #dc2626;\">❌ Ошибка загрузки TOTP</p>';
              }});
          }}
          
          window.addEventListener('beforeunload', () => {{
            if (!burnAfterRead) return;
            navigator.sendBeacon(`/secret/${{token}}/cleanup`);
          }});
        </script>
        """
    )


@app.post("/secret/{token}/reveal", response_class=HTMLResponse)
def reveal_secret(token: str) -> HTMLResponse:
    entry = get_entry(token)
    try:
        code = current_totp(entry)
    except HTTPException as exc:
        raise exc
    burn = entry["burn_after_read"]
    if burn:
        delete_entry(token)
    return format_html(
        f"""
        <h1>Ваш TOTP</h1>
        <div class=\"alert\">Код действителен в текущем 30-секундном интервале.</div>
        <p><strong>{htmlescape(code)}</strong></p>
        <p class=\"small\">Алгоритм: {htmlescape(entry['algorithm'])}, цифр: {entry['digits']}</p>
        { '<p class="alert">Ссылка уничтожена после просмотра.</p>' if burn else '' }
        """
    )


@app.get("/secret/{token}/current")
def get_current_totp(token: str) -> JSONResponse:
    entry = get_entry(token)
    try:
        code = current_totp(entry)
    except HTTPException as exc:
        return JSONResponse(
            {"error": "Ссылка устарела или уже просмотрена"},
            status_code=410
        )
    
    current_counter = int(time.time()) // DEFAULT_STEP_SECONDS
    seconds_left = ((current_counter + 1) * DEFAULT_STEP_SECONDS) - time.time()
    
    return JSONResponse({
        "code": code,
        "algorithm": entry["algorithm"],
        "digits": entry["digits"],
        "seconds_left": seconds_left,
    })


@app.post("/secret/{token}/cleanup")
def cleanup_secret(token: str) -> JSONResponse:
    entry = STORE.get(token)
    if entry and entry["burn_after_read"]:
        delete_entry(token)
    return JSONResponse({"status": "ok"})


def htmlescape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )
