# Техническая карта и продолжение разработки

## 1. Текущая архитектура

```text
Браузер
  │ HTTP :80
  ▼
Nginx → ui/dist → React + встроенные демоданные + localStorage

Отдельно на том же VPS:
PostgreSQL 16 (:5432 loopback / Unix socket)
  ├── bashgroup / app
  ├── Alembic 0001_initial
  ├── seed материалов и скилла
  └── systemd backup timer

Связующего API пока нет.
```

## 2. Исходники

```text
PROJECT_CONTEXT.md
docs/
  TECHNICAL_SPEC.md
  TECHNICAL_MAP.md
  CUSTOMER_MATERIALS.md
ui/
  package.json, package-lock.json, tsconfig.json, index.html
  src/main.tsx                 оболочка, страницы, решения и КП
  src/style.css               общий утверждённый стиль
  src/AgentDemos.tsx           рынок, проекты, закупки, их карточки/отчёты
  src/agents.css              стили новых разделов
  deploy/nginx.conf           конфигурация сайта
backend/
  requirements.txt            диапазоны обновления
  requirements.lock           проверенные версии Python 3.12
  db_config.py                чтение root-only серверных реквизитов
  alembic.ini
  migrations/env.py
  migrations/versions/0001_initial.py
  scripts/provision.py        одноразовая подготовка ролей и БД
  scripts/seed.py              идемпотентная регистрация материалов
  scripts/backup.py            dump, lock, atomic publish, retention
  scripts/verify.py            интеграционные проверки и restore
  deploy/*.service, *.timer
competitor_agent/skills/SKILL.md
katalog-produktsii.md
cases/*.md
```

`dist`, `node_modules`, `.venv`, дампы и реквизиты не хранятся в Git. Сборка воспроизводится из lockfile.

## 3. Сборка UI

Из каталога `ui`:

```sh
npm ci
npm run build
npm run dev
```

Build включает `tsc && vite build`. Node нужен для сборки, не для обслуживания готовой статики. UI не требует локальной БД для просмотра демо.

Навигация на React state, без отдельного router. Нельзя пока ожидать deep links на каждый экран. localStorage — демонстрационное, не постоянное multi-user хранение.

## 4. Развёртывание UI

Серверный корень: `/opt/agents/bashgroup-ai-agent`. Активная статика: `ui/dist`. Nginx site: `/etc/nginx/sites-available/bashgroup-ui`, ссылка в `sites-enabled`.

При обновлении сначала передаются новые хешированные assets, затем заменяется index. Сохранять актуальные исходники вместе со сборкой. Сайт работает независимо от SSH-сессии.

Проверки:

```sh
nginx -t
systemctl is-active nginx
curl -I http://81.222.148.50/
```

В `ui/deploy/nginx.conf` есть `try_files` для SPA, gzip и cache policy. Правила наследования `add_header` Nginx учитывать отдельно; конфиг не проходил полный production-аудит.

При первичной публикации исходников серверная рабочая копия не обновляется автоматически. Не применять reset/clean к untracked UI/скиллу/БД. Перед синхронизацией fetch и сравнение с файлами на VPS.

## 5. PostgreSQL и миграции

Полная инструкция: [backend/README.md](../backend/README.md).

На VPS под root:

```sh
/opt/agents/bashgroup-ai-agent/.venv/bin/alembic -c /opt/agents/bashgroup-ai-agent/backend/alembic.ini current
/opt/agents/bashgroup-ai-agent/.venv/bin/alembic -c /opt/agents/bashgroup-ai-agent/backend/alembic.ini upgrade head
/opt/agents/bashgroup-ai-agent/.venv/bin/python /opt/agents/bashgroup-ai-agent/backend/scripts/seed.py
```

Миграции явно используют owner. Runtime имеет только CRUD. При добавлении миграций не давать API пароли migrator. Технические роли БД не заменяют авторизацию сотрудников.

Текущие таблицы: `agents`, `skill_versions`, `materials`, `companies`, `runs`, `sources`, `fetch_attempts`, `documents`, `evidence`, `claims`, `claim_evidence`, `reports`, `recommendations`, `decisions`, `alembic_version`.

Даты — timestamptz, БД UTC. Тип даты события и её точность из скилла ещё предстоит формализовать в последующих сущностях.

## 6. Backup и восстановление

```sh
systemctl start bashgroup-db-backup.service
systemctl list-timers bashgroup-db-backup.timer
journalctl -u bashgroup-db-backup.service --no-pager
/opt/agents/bashgroup-ai-agent/.venv/bin/python /opt/agents/bashgroup-ai-agent/backend/scripts/verify.py
```

`verify.py` создаёт отдельную временную БД, не восстанавливает поверх рабочей. Для сравнения нужна свежая копия и отсутствие конкурентной записи. Скрипт чистит только свою уникально названную тестовую БД.

Копии находятся на VPS. Внешнее хранилище ещё нужно выбрать. Пароли ролей и внешние файлы не являются частью pg_dump этой БД.

## 7. Доступ с ноутбука

С настроенным SSH-ключом:

```sh
ssh -i ~/.ssh/id_ed25519_arcvps -o IdentitiesOnly=yes -N \
  -L 15432:127.0.0.1:5432 root@81.222.148.50
```

DB-клиент: localhost:15432, база bashgroup, отдельные выданные реквизиты. Пароли не копировать в команды/Git/чат. Файл конфигурации `/etc/bashgroup/database.json` доступен только root.

## 8. Предлагаемая рабочая архитектура

Следующая схема — план, не установленная система:

```text
React → API + аутентификация/права → PostgreSQL
                    │
                    ├── задачи / отчёты / решения
                    ├── компании / источники / evidence
                    └── очередь → workers
                                  ├── поиск/загрузка
                                  ├── извлечение/OCR
                                  ├── версии/diff
                                  ├── YandexGPT
                                  ├── валидация
                                  └── сохранение результата

Планировщик → очередь
Результаты → важные уведомления
Согласованный документ → выбранный канал отправки
```

FastAPI предложен как API-слой; окончательно утвердить при реализации. PostgreSQL/SQLAlchemy/Alembic уже используются. Очередь, поиск, файловое хранилище, retrieval/RAG и векторная БД пока не выбраны. Не добавлять их автоматически только из-за упоминания AI.

## 9. Что потребуется для YandexGPT

- folder_id каталога Yandex Cloud;
- сервисный аккаунт, права и способ аутентификации;
- модель/версия, параметры, лимиты и бюджет;
- таймауты, ограниченные повторы и журнал расходов;
- разрешённые категории данных;
- сохранение версии скилла и входных материалов каждого запуска;
- проверка выхода и evidence IDs.

Модель не должна придумывать snapshot/hash, существующие ID, расчёты и источники. Извлечение текста и загрузки выполняет программа.

## 10. Следующие изменения структуры

Предстоит определить пользователей/доступ, версии профилей, события мониторинга и связи дублей, отдельные источники утверждений, проекты/закупки, версии КП, согласования, отправки, затраты и аудит.

Текущий `ProposalContext` UI содержит `{id,title,need,origin}`; текст `need` объединяет ограничения. Это демотип, не согласованный API-контракт. Для backend нужны структурированные данные и ссылки на evidence.

## 11. С чего продолжить

1. Прочитать контекст и скилл.
2. Проверить Git и сервисы, сохранить текущую БД.
3. Утвердить контракт ручной задачи/отчёта/решения.
4. API + вход + runtime-only реквизиты.
5. Перевести решения и отчёты на сервер, сохранив UI.
6. Подключить один реальный сценарий конкурентной разведки и провести оценку качества.
