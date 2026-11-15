# Агент конкурентной разведки

Текущая активная тема исследования. Цель — сформировать проверяемый MVP агента, который исследует конкурентов, сохраняет источники и историю запусков, а также сравнивает результат с материалами БАШГРУПП.

## Индекс материалов

- [`discovery/competitive-intelligence-discovery.md`](discovery/competitive-intelligence-discovery.md) — журнал discovery и зафиксированные решения по MVP; начат 2026-11-06; статус: рабочий.
- [`briefs/competitive-intelligence-brief.md`](briefs/competitive-intelligence-brief.md) — основной бриф для совместной сессии; начат 2026-11-06; статус: требует дальнейшего заполнения.
- [`meetings/meeting-2026-11-08-summary.md`](meetings/meeting-2026-11-08-summary.md) — конспект встречи 8 ноября 2026 года; основан на автоматической расшифровке, выводы сверены по смысловому контексту.
- [`decisions/multi-agent-mvp-design.md`](decisions/multi-agent-mvp-design.md) — утвержденная основа двух независимых сценариев MVP: разведки объектов и разведки конкурентов.
- [`decisions/object-intelligence-input-context.md`](decisions/object-intelligence-input-context.md) — первоначальный контекст промпта для агента разведки объектов.
- [`decisions/object-intelligence-context-loading.md`](decisions/object-intelligence-context-loading.md) — правила выборочной подгрузки материалов и защиты от галлюцинаций.
- [`decisions/capability-knowledge-storage.md`](decisions/capability-knowledge-storage.md) — что хранится в базе возможностей БАШГРУПП и как агент использует эти данные.
- [`decisions/agent-storage-abstraction.md`](decisions/agent-storage-abstraction.md) — принцип независимости агента от конкретного хранилища через предметный слой контекста.
- [`sources/object-intelligence-source-registry.md`](sources/object-intelligence-source-registry.md) — расширяемый реестр источников для поиска объектов.
- [`todos/data-storage-schema.md`](todos/data-storage-schema.md) — разработать схему хранения данных о возможностях БАШГРУПП.

## Следующие типы материалов

- `answers/` — ответы на вопросы по теме, в том числе перенесённые из Google Docs.
- `todos/` — отдельные открытые действия, не вошедшие в бриф или конспект встречи.
- `decisions/` — согласованные архитектурные и продуктовые решения по теме.

Создаём эти каталоги при появлении первого материала и сразу обновляем этот индекс и [`../README.md`](../README.md).
