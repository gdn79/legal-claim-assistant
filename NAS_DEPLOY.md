# Деплой на Synology NAS (DS720+) через Container Manager

## Перенос файлов на NAS

1. Скопируйте архив `legal-claim-assistant-deploy.zip` на NAS через **File Station**
2. Распакуйте в **отдельную папку**, например: `/docker/legal-claim-assistant/`
3. Убедитесь, что в папке есть файлы: `Dockerfile`, `docker-compose.yml`, `.env.example`, `entrypoint.sh`, `.dockerignore`, `src/`, `data/references/`

## Подготовка .env

Скопируйте `.env.example` в `.env` (в той же папке) и настройте:

### OpenAI
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1
OPENAI_BASE_URL=https://api.artemox.com/v1
OPENAI_TIMEOUT_SECONDS=300
```

### Yandex GPT
```env
LLM_PROVIDER=yandex
YANDEX_API_KEY=...
YANDEX_FOLDER_ID=...
YANDEX_MODEL=yandexgpt/latest
YANDEX_TIMEOUT_SECONDS=300
```

### OCR (контейнер)
```env
TESSERACT_CMD=tesseract
OCR_ENABLED=true
OCR_TIMEOUT_SECONDS=90
```

**Важно:** `TESSERACT_CMD=tesseract` — иначе OCR не найдёт tesseract в Linux.

## Деплой — два варианта

### Вариант A: Container Manager (Project)

1. **Container Manager** → **Project** → **Create**
2. Название: `legal-claim-assistant`
3. Выберите **docker-compose.yml** → укажите путь к папке проекта
4. **Create** → **Apply**

Container Manager начнёт сборку образа. Это может занять 5-10 минут.

### Вариант B: SSH (если сборка в Container Manager не работает)

1. Включите SSH на NAS: **Панель управления** → **Терминал и SNMP** → разрешить SSH
2. Подключитесь: `ssh admin@AI.9901.ru`
3. Перейдите в папку проекта и запустите сборку:
   ```bash
   cd /volume1/docker/legal-claim-assistant
   docker build -t legal-claim-assistant .
   ```
4. Затем в Container Manager: **Project** → **Create**, выберите `docker-compose.yml`

> **Почему не собирается?** На DS720+ стандартный Docker есть, но Container Manager
> может не показывать подробный лог ошибки. Через SSH вы увидите точную причину.

## Если всё равно не работает — быстрый старт без сборки

Если проблема с самой сборкой (нет интернета на NAS, не хватает памяти и т.п.):

1. Откройте **Container Manager** → **Image** → **Add** → **Run from Docker Hub**
2. Введите: `python:3.12-slim` → нажмите **Run**
3. В командной строке контейнера: `bash`
4. Вручную выполните:
   ```bash
   apt-get update && apt-get install -y tesseract-ocr tesseract-ocr-rus
   pip install openai python-dotenv Flask python-docx PyMuPDF pydantic
   ```
5. Скопируйте исходники через File Station в контейнер (вручную)

*Этот вариант громоздкий — лучше разобраться со сборкой через SSH.*

## Частые проблемы сборки

| Проблема | Решение |
|----------|---------|
| Нет доступа в интернет | Проверьте, что NAS может выходить в интернет (DNS, шлюз) |
| Не хватает места | Очистите неиспользуемые Docker-образы / мусор |
| Ошибка `COPY` | Извлеките файлы в короткий путь (не длиннее 50 символов) |
| `exec format error` | Проверьте, что процессор NAS — x86_64 (DS720+ подходит) |
| `no matching manifest` | Установите флаг `--platform linux/amd64` в Dockerfile |

## Доступ

После успешного деплоя откройте:

```
http://AI.9901.ru:8000/bot
```

## Логи

- Container Manager → **Container** → `legal-claim-assistant` → **Log**
- Или SSH: `docker logs -f legal-claim-assistant`
- Логи также пишутся в `logs/assistant.log` (на смонтированном томе)

## Пути на NAS

| Папка контейнера | Назначение |
|-----------------|------------|
| `/app/data` | Дела, промпты, справочники |
| `/app/logs` | Логи |
| `/app/.tmp` | Временные файлы OCR |
