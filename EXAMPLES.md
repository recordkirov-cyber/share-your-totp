# Share Your TOTP - Примеры использования

## 1. Быстрый старт через Docker

```bash
# Скачать репозиторий
git clone <repo-url> share-your-totp
cd share-your-totp

# Собрать и запустить
docker build -t share-your-totp .
docker run -d --name totp-server -p 8000:8000 share-your-totp

# Открыть браузер
open http://localhost:8000
```

## 2. API примеры

### Python

```python
import requests
import json

# Создать ссылку через API
payload = {
    "secret": "JBSWY3DPEHPK3PXP",
    "algorithm": "SHA1",
    "digits": 6,
    "hours": 2,
    "burn_after_read": True
}

response = requests.post(
    "http://localhost:8000/api/create",
    json=payload
)

link = response.json()["url"]
print(f"Ссылка: {link}")

# Получить TOTP через ссылку
reveal_response = requests.post(f"{link}/reveal")
print(reveal_response.text)
```

### cURL

```bash
# Создать ссылку
curl -X POST http://localhost:8000/api/create \
  -H "Content-Type: application/json" \
  -d '{
    "secret": "JBSWY3DPEHPK3PXP",
    "algorithm": "SHA256",
    "digits": 8,
    "hours": 0.5,
    "burn_after_read": false
  }'

# Результат:
# {"url":"http://localhost:8000/secret/abc123..."}

# Просмотреть TOTP
curl -X POST http://localhost:8000/secret/abc123.../reveal
```

### JavaScript/Node.js

```javascript
const fetch = require('node-fetch');

const payload = {
  secret: "JBSWY3DPEHPK3PXP",
  algorithm: "SHA512",
  digits: 6,
  hours: 1,
  burn_after_read: true
};

fetch('http://localhost:8000/api/create', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload)
})
.then(r => r.json())
.then(data => console.log('Ссылка:', data.url));
```

## 3. Использование с разными TOTP-секретами

### Base32 секрет (стандарт)

```bash
# Создать с Base32 секретом
curl -X POST http://localhost:8000/api/create \
  -H "Content-Type: application/json" \
  -d '{
    "secret": "JBSWY3DPEHPK3PXP",
    "algorithm": "SHA1",
    "digits": 6,
    "hours": 1
  }'
```

### Текстовый секрет

```bash
# Приложение автоматически преобразует текст в Base32
curl -X POST http://localhost:8000/api/create \
  -H "Content-Type: application/json" \
  -d '{
    "secret": "my-secret-key",
    "algorithm": "SHA1",
    "digits": 6,
    "hours": 1
  }'
```

## 4. Burn After Read (самоудаление)

```bash
# С флагом burn_after_read: после первого просмотра ссылка удалится
curl -X POST http://localhost:8000/api/create \
  -H "Content-Type: application/json" \
  -d '{
    "secret": "JBSWY3DPEHPK3PXP",
    "burn_after_read": true,
    "hours": 24
  }'

# Первый просмотр - работает
curl -X POST http://localhost:8000/secret/<token>/reveal

# Второй просмотр - ошибка 404
curl -X POST http://localhost:8000/secret/<token>/reveal
# {"detail":"Ссылка устарела или не существует"}
```

## 5. Разные алгоритмы хеширования

```bash
# SHA1 (классический, быстрый)
curl -X POST http://localhost:8000/api/create \
  -H "Content-Type: application/json" \
  -d '{"secret":"JBSWY3DPEHPK3PXP","algorithm":"SHA1","digits":6,"hours":1}'

# SHA256 (более безопасный)
curl -X POST http://localhost:8000/api/create \
  -H "Content-Type: application/json" \
  -d '{"secret":"JBSWY3DPEHPK3PXP","algorithm":"SHA256","digits":6,"hours":1}'

# SHA512 (максимальная безопасность)
curl -X POST http://localhost:8000/api/create \
  -H "Content-Type: application/json" \
  -d '{"secret":"JBSWY3DPEHPK3PXP","algorithm":"SHA512","digits":6,"hours":1}'
```

## 6. Разные длины кодов

```bash
# 6 цифр (стандарт, 999999 комбинаций)
curl -X POST http://localhost:8000/api/create \
  -H "Content-Type: application/json" \
  -d '{"secret":"JBSWY3DPEHPK3PXP","digits":6,"hours":1}'
# Результат: 123456

# 7 цифр (9999999 комбинаций)
curl -X POST http://localhost:8000/api/create \
  -H "Content-Type: application/json" \
  -d '{"secret":"JBSWY3DPEHPK3PXP","digits":7,"hours":1}'
# Результат: 1234567

# 8 цифр (99999999 комбинаций, максимум)
curl -X POST http://localhost:8000/api/create \
  -H "Content-Type: application/json" \
  -d '{"secret":"JBSWY3DPEHPK3PXP","digits":8,"hours":1}'
# Результат: 12345678
```

## 7. Короткие и длинные ссылки

```bash
# Ссылка живёт 15 минут (0.25 часа)
curl -X POST http://localhost:8000/api/create \
  -H "Content-Type: application/json" \
  -d '{"secret":"JBSWY3DPEHPK3PXP","hours":0.25}'

# Ссылка живёт 24 часа (максимум с хорошей приватностью)
curl -X POST http://localhost:8000/api/create \
  -H "Content-Type: application/json" \
  -d '{"secret":"JBSWY3DPEHPK3PXP","hours":24}'

# Ссылка живёт 48 часов (максимум вообще)
curl -X POST http://localhost:8000/api/create \
  -H "Content-Type: application/json" \
  -d '{"secret":"JBSWY3DPEHPK3PXP","hours":48}'
```

## 8. Тестирование в браузере

### Шаг 1: Создать ссылку
- Откройте `http://localhost:8000`
- Введите TOTP-секрет: `JBSWY3DPEHPK3PXP`
- Выберите параметры
- Нажмите "Создать приватную ссылку"

### Шаг 2: Скопировать ссылку
- Скопируйте сгенерированную ссылку
- Отправьте кому-нибудь

### Шаг 3: Просмотреть код
- Получатель открывает ссылку
- Видит кнопку "Просмотреть ТОТР"
- Нажимает кнопку
- Видит 6-значный TOTP-код

### Шаг 4: Проверка burn_after_read
- Если отмечен флаг, повторная попытка вернёт ошибку 404

## 9. Интеграция в приложение

### Отправить секрет через форму
```html
<form method="post" action="http://localhost:8000/create">
  <input name="secret" placeholder="TOTP-секрет" required>
  <input name="hours" type="number" value="1" min="0.01" max="48">
  <label>
    <input type="checkbox" name="burn_after_read" value="true">
    Уничтожить после просмотра
  </label>
  <button type="submit">Создать ссылку</button>
</form>
```

### Встроить в iframe
```html
<iframe src="http://localhost:8000/secret/<token>" 
        width="600" height="400" 
        sandbox="allow-same-origin allow-forms">
</iframe>
```

## 10. Продвинутые сценарии

### Автоматическое создание ссылок для нескольких пользователей

```bash
#!/bin/bash

SECRETS=(
  "JBSWY3DPEHPK3PXP"
  "GA2DMRSGUNLW2ZIM"
  "GE3GOXTVGE6TCZSI"
)

for secret in "${SECRETS[@]}"; do
  response=$(curl -s -X POST http://localhost:8000/api/create \
    -H "Content-Type: application/json" \
    -d "{\"secret\":\"$secret\",\"hours\":24,\"burn_after_read\":true}")
  
  url=$(echo $response | jq -r '.url')
  echo "Share this link: $url"
done
```

### Webhook интеграция

```python
from fastapi import FastAPI
import requests

app = FastAPI()

@app.post("/generate-totp-link")
async def generate_link(user_email: str, secret: str):
    """Генерирует TOTP-ссылку и отправляет по email"""
    
    # Создать ссылку
    response = requests.post(
        "http://localhost:8000/api/create",
        json={
            "secret": secret,
            "hours": 1,
            "burn_after_read": True
        }
    )
    
    link = response.json()["url"]
    
    # Отправить по email
    # send_email(user_email, f"Your TOTP link: {link}")
    
    return {"link": link}
```

## Безопасность и приватность

- ✅ Приватный ключ не сохраняется на диск
- ✅ Данные только в памяти (теряются при перезагрузке)
- ✅ Нет аутентификации — нет логов пользователей
- ✅ Коды TOTP удаляются автоматически через 30 сек
- ✅ `burn_after_read` гарантирует удаление после просмотра
- ✅ Кнопка "Просмотреть" защищает от предпросмотра браузером

## Вопросы и ответы

**Q: Могу ли я развернуть это на продакшене?**  
A: Да, но с учетом того, что данные в памяти. Рекомендуется использовать с несколькими инстансами за балансировщиком (sticky sessions).

**Q: Что произойдет при перезагрузке?**  
A: Все ссылки и коды будут потеряны (по дизайну, для приватности).

**Q: Могу ли я использовать с базой данных?**  
A: Да, замените `STORE` на подключение к Redis или PostgreSQL в `app/main.py`.

**Q: Это соответствует RFC 6238?**  
A: Да, используется стандартный TOTP алгоритм с SHA1/SHA256/SHA512.
