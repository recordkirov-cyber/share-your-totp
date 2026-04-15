# Share Your TOTP

Приватное веб-приложение для безопасного обмена TOTP-ключами через одноразовые ссылки.  
Полная приватность: без аутентификации, без хранения метаданных, данные только в памяти.

## Архитектура

- **Backend**: FastAPI на Python
- **Хранилище**: только оперативная память (in-memory) 
- **Безопасность**:
  - Приватный ключ используется только для генерации TOTP, не сохраняется
  - Каждые 30 секунд автоматически удаляются просроченные коды
  - Поддержка `burn_after_read`: код удаляется после просмотра
  - Никаких метаданных пользователя, никакой аутентификации
  - Данные **не гарантируются** после перезагрузки сервера (ради приватности)
- **Защита от предпросмотра**: кнопка "Просмотреть ТОТР" перед показом кода

## Запуск

### Docker из GitHub Container Registry (самый просто)

```bash
docker run --rm -p 8000:8000 ghcr.io/recordkirov-cyber/share-your-totp:main
```

Откройте `http://localhost:8000`

### Docker (локальная сборка)

```bash
docker build -t share-your-totp .
docker run --rm -p 8000:8000 share-your-totp
```

Откройте `http://localhost:8000`

### Локально без Docker

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API

### POST /api/create

Создать одноразовую ссылку на TOTP.

**Запрос:**
```json
{
  "secret": "JBSWY3DPEHPK3PXP",
  "algorithm": "SHA1",
  "digits": 6,
  "hours": 1,
  "burn_after_read": true
}
```

- `secret` (string, required) — Base32 или текстовый секрет  
- `algorithm` (string) — "SHA1", "SHA256" или "SHA512" (default: SHA1)
- `digits` (int) — 6, 7 или 8 (default: 6)
- `hours` (float) — время жизни в часах, до 48 часов (default: 1)
- `burn_after_read` (boolean) — удалить после просмотра (default: false)

**Ответ:**
```json
{
  "url": "http://localhost:8000/secret/ce05087009fc43eea5884f1d551053ed"
}
```

**Пример:**
```bash
curl -X POST http://localhost:8000/api/create \
  -H "Content-Type: application/json" \
  -d '{"secret":"JBSWY3DPEHPK3PXP","algorithm":"SHA1","digits":6,"hours":1,"burn_after_read":true}'
```

## Веб-форма

Главная страница `http://localhost:8000` содержит форму с полями:

- **Приватный ключ TOTP** — Base32 или текстовый секрет
- **Алгоритм** — SHA1, SHA256, SHA512
- **Количество цифр** — 6, 7, 8
- **Ссылка живёт, часов** — время жизни
- **Уничтожить после просмотра** — флаг burn_after_read

## Поведение

1. Пользователь создает ссылку с TOTP-секретом
2. Система генерирует **все** коды TOTP на время жизни ссылки и сохраняет их в памяти
3. Приватный ключ **удаляется** из памяти
4. Пользователь, перейшя по ссылке, видит кнопку "Просмотреть ТОТР"
5. При нажатии кнопки показывается актуальный TOTP-код для текущего 30-секундного интервала
6. Если включен `burn_after_read`:
   - Код удаляется после просмотра
   - Ссылка больше не доступна
   - При закрытии страницы отправляется `navigator.sendBeacon` для гарантийного удаления

## Тестирование

### Создать тестовую ссылку через API

```powershell
$body = @{
  secret='JBSWY3DPEHPK3PXP'
  algorithm='SHA1'
  digits=6
  hours=1
  burn_after_read=$true
} | ConvertTo-Json

curl -X POST http://localhost:8000/api/create `
  -H "Content-Type: application/json" `
  -d $body
```

### Просмотреть TOTP

```bash
curl -X POST http://localhost:8000/secret/<token>/reveal
```

### Веб-браузер

1. Откройте `http://localhost:8000`
2. Введите TOTP-секрет (например, `JBSWY3DPEHPK3PXP`)
3. Установите время жизни (1 час)
4. Отметьте "Уничтожить после просмотра" (опционально)
5. Нажмите "Создать приватную ссылку"
6. По ссылке нажмите "Просмотреть ТОТР"
7. Увидите 6-значный TOTP-код

## Структура проекта

```
share-your-totp/
├── app/
│   └── main.py           # основная логика FastAPI
├── requirements.txt       # зависимости Python
├── Dockerfile            # конфигурация Docker
├── .gitignore            # исключения для git
├── .github/
│   └── workflows/
│       └── publish-to-ghcr.yml  # CI/CD для GHCR
├── README.md             # этот файл
├── LICENSE               # GPLv3 лицензия
```

## Container Registry

Контейнер автоматически публикуется в [GitHub Container Registry](https://github.com/recordkirov-cyber/share-your-totp/pkgs/container/share-your-totp):

```bash
# Использовать последний образ из main ветки
docker run -p 8000:8000 ghcr.io/recordkirov-cyber/share-your-totp:main

# Или конкретный тег версии
docker run -p 8000:8000 ghcr.io/recordkirov-cyber/share-your-totp:v1.0.0
```

Образ автоматически собирается и загружается при каждом push в main ветку и при создании git тегов.

## Требования

- Python 3.12+
- FastAPI 0.111.0
- Uvicorn 0.27.0
- python-multipart >= 0.0.7

## Лицензия

[GNU General Public License v3](LICENSE) — свободное ПО
