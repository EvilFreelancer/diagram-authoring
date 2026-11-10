# Case: agent-turn

A technical brief to hand a fresh agent. The agent turns it into a diagram
following the output contract in `evals/prompt.md`. The brief is written in
Russian on purpose: a good diagram reads in English even when the source
material is not English.

## Brief

Coddy получает сообщение пользователя через web UI, Telegram или консоль. Общий session manager создаёт ход агента. Агент читает правила и скиллы, обращается к LLM, при необходимости вызывает инструменты и MCP. Результат сохраняется в файловой сессии и транслируется обратно во все поверхности. Фоновые задачи могут разбудить агента после завершения хода.
