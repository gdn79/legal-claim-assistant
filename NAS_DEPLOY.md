# Deploy на Synology NAS (DS720+)

## Предварительные требования

- Container Manager (Docker) установлен
- SSH-доступ к NAS (`gdn79@NAS720`)
- Проброшен порт 9000 → 8000 контейнера (настройки роутера)

## Быстрый деплой

### 1. Скопировать архив на NAS

Через File Station (веб-интерфейс DSM):
- Загрузить `legal-claim-assistant-deploy.zip` в `/volume1/docker/legal-claim-assistant/`

Или через SCP (из PowerShell на Windows):
```powershell
scp D:\CODEX\Assistent\legal-claim-assistant-deploy.zip gdn79@NAS720:/volume1/docker/legal-claim-assistant/
```
> **Важно:** если SCP падает с `subsystem request failed on channel 0`, используйте File Station.

### 2. Распаковать и собрать (через SSH на NAS)

```bash
cd /volume1/docker/legal-claim-assistant
unzip -o legal-claim-assistant-deploy.zip
cp -r legal-claim-assistant-deploy/* .
```

Если `entrypoint.sh` отсутствует — создать вручную:

```bash
cat > entrypoint.sh << 'SCRIPT'
#!/bin/sh
set -e
if [ ! -f "data/references/arbitration_courts_ru.json" ]; then
    mkdir -p data/references
    cp -r /app/references.bundled/* data/references/
fi
exec "$@"
SCRIPT
chmod +x entrypoint.sh
```

### 3. Собрать образ

```bash
sudo docker compose build --no-cache
sudo docker compose up -d
```

> `--no-cache` обязателен при первом деплое или после изменения исходников,
> чтобы не подхватились старые кэшированные слои.

### 4. Проверить

```bash
sudo docker compose logs --tail=20
```

Убедиться, что URL YandexGPT — `v1/chat/completions`, а не `foundationModels/v1`.

## Обновление (без замены всех файлов)

Если изменились только исходники Python:

```bash
# С Windows — скопировать изменённые файлы
scp src/legal_claim_assistant/yandex_client.py gdn79@NAS720:/volume1/docker/legal-claim-assistant/src/legal_claim_assistant/
scp src/legal_claim_assistant/prompts.py gdn79@NAS720:/volume1/docker/legal-claim-assistant/src/legal_claim_assistant/
scp src/legal_claim_assistant/readiness.py gdn79@NAS720:/volume1/docker/legal-claim-assistant/src/legal_claim_assistant/

# На NAS — пересобрать
cd /volume1/docker/legal-claim-assistant
sudo docker compose build --no-cache
sudo docker compose up -d
```

## Сброс промптов (если иск короткий)

Если после обновления иск всё ещё короткий — старые промпты могли сохраниться в volume:

```bash
sudo rm /volume1/docker/legal-claim-assistant/data/prompts.json
sudo docker compose restart
```

Или через веб-интерфейс: http://9901.ru:9000/prompts → кнопка «Сбросить».

## Важные файлы

| Файл | Назначение |
|------|------------|
| `Dockerfile` | Production-сборка (python:3.12-slim + Tesseract) |
| `docker-compose.yml` | Порт 9000:8000, volumes data/ logs/ |
| `entrypoint.sh` | Копирует справочники в volume при первом запуске |
| `.env` | Переменные окружения (YANDEX_API_KEY, YANDEX_FOLDER_ID, LLM_PROVIDER=yandex) |
| `src/legal_claim_assistant/yandex_client.py` | Клиент YandexGPT (BASE_URL = v1, max_tokens = 8000) |
| `src/legal_claim_assistant/prompts.py` | Промпты для генерации иска (3–5 страниц) |
| `src/legal_claim_assistant/readiness.py` | Проверка готовности (без блокировки по приложениям/дате) |
