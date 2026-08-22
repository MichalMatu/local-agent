# Local Deterministic Agent — Project Blueprint

## 1. Cel projektu

Ten dokument opisuje architekturę lokalnego agenta wykonawczego, który pozwala sterować pracą nad repozytorium przez prostą, deterministyczną kolejkę zadań.

Podstawowa idea:

```text
ChatGPT / operator
        |
        v
  zadanie JSON
        |
        v
  branch kontrolny
   `agent-control`
        |
        v
  lokalny daemon
    `agentd.py`
        |
        v
 checkout/reset repo roboczego
        |
        v
 deterministyczne komendy shell
        |
        v
 testy / build / flash / analiza
        |
        v
 wynik JSON
        |
        v
 branch `agent-control`
```

Agent **nie potrzebuje lokalnego LLM**, żeby działać. Krytyczna ścieżka jest deterministyczna:

```text
prompt -> task JSON -> daemon -> shell -> wynik
```

Lokalny model może być kiedyś dodany jako opcjonalne narzędzie pomocnicze, ale nie powinien być wymagany do wykonywania zadań produkcyjnych.

---

## 2. Dlaczego to nadaje się na osobny projekt

Ten mechanizm nie jest specyficzny dla ESP32 ani jednego repozytorium. Można go rozszerzyć do:

- automatycznego wykonywania testów,
- buildów,
- lintów,
- statycznej analizy,
- publikacji,
- flashowania urządzeń,
- testów hardware-in-the-loop,
- generowania raportów,
- automatycznych audytów,
- wykonywania migracji,
- zarządzania wieloma repozytoriami,
- wykonywania zadań CI poza GitHub Actions,
- lokalnych testów zależnych od sprzętu,
- pracy z agentami AI,
- kolejek warunkowych,
- automatycznych retry,
- zbierania benchmarków,
- długich soak-testów.

Największa wartość projektu polega na oddzieleniu:

```text
DECYZJI
od
WYKONANIA
```

Model / operator decyduje **co zrobić**, a daemon wykonuje **dokładnie to, co dostał**.

---

# 3. Aktualna implementacja

## Repozytorium robocze

Aktualnie używany projekt:

```text
MichalMatu/esp32s3_LiteGraph
```

Lokalne repo robocze:

```text
~/agent-workspace/work
```

Lokalne repo kontrolne:

```text
~/agent-workspace/control
```

Daemon:

```text
/Users/michal/local-agent/agentd.py
```

Log:

```text
~/Library/Logs/local-agent.log
```

Branch kontrolny:

```text
agent-control
```

---

# 4. Separacja repo roboczego i kontrolnego

## Repo robocze

```text
~/agent-workspace/work
```

Służy do:

- checkout branchy produkcyjnych,
- zmian w kodzie,
- testów,
- buildów,
- commitów,
- flashowania,
- lokalnych eksperymentów.

## Repo kontrolne

```text
~/agent-workspace/control
```

Służy wyłącznie do komunikacji:

```text
.agent/tasks/
.agent/results/
.agent/patches/
```

Dzięki temu zadania i wyniki nie mieszają się z aktualnym stanem worktree.

---

# 5. Struktura katalogów sterujących

Minimalna struktura:

```text
.agent/
├── tasks/
│   ├── 000-example-task.json
│   ├── 001-build.json
│   └── ...
├── results/
│   ├── example-task.json
│   ├── build.json
│   └── ...
└── patches/
    └── optional-helper-files.py
```

Można później rozszerzyć:

```text
.agent/
├── tasks/
├── results/
├── patches/
├── artifacts/
├── locks/
├── state/
├── schemas/
├── profiles/
├── tools/
└── workflows/
```

---

# 6. Format zadania

Aktualny podstawowy format:

```json
{
  "id": "example-task-001",
  "mode": "commands",
  "work_branch": "main",
  "allow_write": true,
  "commands": [
    "git status --short",
    "pio run"
  ],
  "command_timeout": 7200
}
```

## Pola

### `id`

Unikalny identyfikator zadania. Przykład:

```text
ble-rtc-status-contract-060
```

Daemon nie powinien wykonywać zadania ponownie, jeśli wynik dla tego samego `id` już istnieje.

### `mode`

Aktualnie:

```text
commands
```

W przyszłości można dodać:

```text
patch
workflow
script
python
hardware-test
flash
benchmark
soak
publish
multi-repo
```

### `work_branch`

Branch, na którym daemon ma przygotować worktree.

Przykład:

```text
main
fix/nodeflow-live-input-preview
```

### `allow_write`

```json
true
```

Pozwala zadaniu modyfikować pliki.

```json
false
```

Powinno oznaczać audyt / test / read-only.

### `commands`

Lista deterministycznych komend shell wykonywanych kolejno.

Przykład:

```json
[
  "git diff --check",
  "pio run -c platformio.tests.ini -e test-all-host",
  "pio run"
]
```

Jeśli jedna komenda kończy się błędem, zadanie powinno się zatrzymać.

### `command_timeout`

Limit czasu. Aktualnie często używane:

```json
7200
```

czyli 2 godziny.

---

# 7. Kolejka zadań

Daemon cyklicznie:

```text
1. checkout agent-control
2. git pull --rebase origin agent-control
3. przegląda .agent/tasks/
4. sortuje nazwy alfabetycznie
5. ignoruje task, jeśli istnieje result o tym samym id
6. bierze pierwsze oczekujące zadanie
7. przygotowuje repo robocze
8. wykonuje komendy
9. zapisuje wynik
10. commit/push wyniku na agent-control
11. wraca do pętli
```

Aktualny polling:

```text
~15 sekund
```

Przykładowy log w stanie idle:

```text
exec: git checkout agent-control
exec finished exit=0 ...
exec: git pull --rebase origin agent-control
exec finished exit=0 ...
no pending tasks
```

---

# 8. Wykonanie zadania

Przykładowa sekwencja:

```text
starting task final-golden-audit-resume-057
exec: ...
[CMD] ...
exec finished exit=0 ...
published result final-golden-audit-resume-057
```

Daemon powinien logować:

- task id,
- czas startu,
- każdą komendę,
- kod wyjścia,
- czas wykonania,
- stdout,
- stderr,
- końcowy status.

---

# 9. Format wyniku

Minimalny przykład:

```json
{
  "id": "example-task-001",
  "status": "done",
  "started_at": "2026-08-21T15:09:45Z",
  "finished_at": "2026-08-21T15:44:57Z",
  "commands": [
    {
      "command": "git diff --check",
      "exit_code": 0,
      "elapsed_seconds": 0.2
    }
  ]
}
```

Wersja rozszerzona powinna zawierać:

```json
{
  "id": "...",
  "status": "done",
  "host": "...",
  "repo": "...",
  "branch": "...",
  "base_sha": "...",
  "head_sha": "...",
  "started_at": "...",
  "finished_at": "...",
  "elapsed_seconds": 0,
  "commands": [],
  "artifacts": [],
  "metrics": {},
  "failure_reason": null
}
```

---

# 10. Statusy zadań

Warto ustandaryzować:

```text
pending
running
done
failed
cancelled
timeout
blocked
patch_failed
publish_failed
```

Dodatkowe pola:

```text
retryable: true/false
failure_stage: checkout|patch|test|build|flash|push
```

---

# 11. Determinizm

Główna zasada:

> Daemon nie powinien sam interpretować intencji użytkownika.

Powinien wykonywać tylko jawnie zdefiniowane operacje.

Dobre:

```json
"commands": [
  "npm run check",
  "npm run test"
]
```

Złe:

```text
"napraw frontend"
```

Interpretacja należy do warstwy wyżej:

```text
ChatGPT / operator / planner
```

Daemon jest wykonawcą.

---

# 12. Lokalny LLM

Aktualna architektura **nie używa Qwen/Ollama w krytycznej ścieżce**.

```text
ChatGPT
   |
task JSON
   |
daemon
   |
shell
```

To jest zaleta:

- mniej nieprzewidywalności,
- łatwiejszy debug,
- łatwe odtworzenie,
- łatwa kontrola zmian,
- brak zależności od GPU / modelu,
- mniejsze ryzyko niekontrolowanych zmian.

Opcjonalny model przyszłości:

```text
planner -> optional local LLM -> proposal -> deterministic validator -> executor
```

Bezpieczniejszy wariant:

```text
LLM generuje propozycję JSON
        |
schema validator
        |
policy engine
        |
daemon
```

---

# 13. Git i SSH

W aktualnym środowisku połączenie GitHub przez SSH na porcie 22 miało problemy.

Zastosowano:

```bash
git -C ~/agent-workspace/work remote set-url origin \
  ssh://git@ssh.github.com:443/MichalMatu/esp32s3_LiteGraph.git

git -C ~/agent-workspace/control remote set-url origin \
  ssh://git@ssh.github.com:443/MichalMatu/esp32s3_LiteGraph.git
```

Test:

```bash
ssh -T -p 443 git@ssh.github.com
```

Oczekiwany wynik:

```text
Hi <user>! You've successfully authenticated, but GitHub does not provide shell access.
```

---

# 14. Bardzo ważna lekcja: push bieżącego worktree

Repo robocze może pracować na branchu technicznym, np.:

```text
agent-work
```

Dlatego:

```bash
git push origin main
```

może wypchnąć **lokalny branch main**, a nie aktualny HEAD.

Poprawny wariant przy publikowaniu aktualnego worktree do remote `main`:

```bash
git push origin HEAD:main
```

Jeśli świadomie pomijamy hook po wcześniejszych pełnych testach:

```bash
git push --no-verify origin HEAD:main
```

Używać tylko wtedy, gdy wcześniejsze gate'y zostały już wykonane i wynik jest znany.

---

# 15. Git hooks i kosztowna walidacja

Pre-push hook może odpalać pełny test suite.

To może powodować:

- wielokrotne uruchamianie tych samych testów,
- bardzo długie zadania,
- timeouty,
- błędną interpretację jako failure kodu.

Zasada:

```text
targeted tests po zmianie
+
pełny audit tylko raz na końcu
```

Nie uruchamiać wielokrotnie pełnego test suite, jeśli kod produkcyjny się nie zmienił.

---

# 16. Patchowanie kodu — lekcje

## Problem 1

Patch zapisany jako:

```text
*** Begin Patch
...
*** End Patch
```

został przekazany do:

```bash
git apply
```

`git apply` tego formatu nie rozumie.

Wynik:

```text
No valid patches in input
```

## Problem 2

Źle wygenerowany unified diff:

```text
corrupt patch at line ...
```

## Lepszy model

Dla małych mechanicznych zmian bardzo dobrze działa deterministyczny Python:

```python
from pathlib import Path

path = Path("file.ts")
text = path.read_text()

old = "dokładny fragment"
new = "nowy fragment"

if text.count(old) != 1:
    raise SystemExit("unexpected source state")

path.write_text(text.replace(old, new, 1))
```

Zalety:

- dokładnie jedno oczekiwane dopasowanie,
- brak zgadywania,
- failure przy niespodziewanym stanie kodu,
- łatwy audit.

---

# 17. Zasada expected-state

Każda automatyczna modyfikacja powinna sprawdzać stan wejściowy.

Przykład:

```python
if text.count(old) != 1:
    raise RuntimeError("source changed unexpectedly")
```

To chroni przed:

```text
task przygotowany dla starej wersji kodu
+
repo już się zmieniło
=
niekontrolowana podmiana
```

---

# 18. Pre-flight

Przed modyfikacją warto uruchamiać:

```bash
git status --short
git diff --check
git log -1 --oneline
git rev-parse HEAD
```

Można wymagać:

```json
"expected_head": "abc123..."
```

Jeśli HEAD się nie zgadza:

```text
status = blocked
```

---

# 19. Repo reset przed zadaniem

Dobry flow:

```bash
git fetch origin
git checkout <work_branch>
git reset --hard origin/<work_branch>
```

`git clean -fd` powinien być konfigurowalny, ponieważ może usunąć lokalne pliki potrzebne przez użytkownika.

Bezpieczniej:

```json
"workspace_policy": "reset-to-remote"
```

lub:

```json
"workspace_policy": "preserve"
```

---

# 20. Typowe komendy w obecnym projekcie

## Host tests

```bash
pio run -c platformio.tests.ini -e test-all-host
```

W tym repo nie używać jako zamiennika:

```bash
pio test
```

## Firmware

```bash
pio run
```

## Firmware bez frontendu

```bash
SKIP_FRONTEND=1 pio run
```

## Firmware embedded web

```bash
pio run -e esp32s3-firmware-embedded-web
```

## Upload

```bash
pio run -e esp32s3-firmware-embedded-web \
  -t upload \
  --upload-port /dev/cu.usbserial-110
```

---

# 21. Flash / hardware-in-the-loop

To jeden z najciekawszych kierunków rozwoju osobnego projektu.

Daemon może posiadać tool typu:

```json
{
  "tool": "flash_esp32",
  "environment": "esp32s3-firmware-embedded-web",
  "port": "/dev/cu.usbserial-110"
}
```

Następnie:

```text
build
 -> upload
 -> serial smoke
 -> parse boot
 -> PASS/FAIL
```

Przykładowy PASS:

```text
BOOT_SUMMARY total_ms=5311 safe_mode_active=false
SERIAL_SMOKE_OK lines=3
```

---

# 22. Narzędzia zamiast surowych komend

Docelowo zamiast wszystkiego przez shell można dodać typed tools.

Przykład:

```json
{
  "mode": "tools",
  "steps": [
    { "tool": "git.status" },
    {
      "tool": "platformio.test",
      "environment": "test-all-host"
    },
    {
      "tool": "platformio.build",
      "environment": "esp32s3-firmware-embedded-web"
    }
  ]
}
```

Zalety:

- walidacja argumentów,
- polityki bezpieczeństwa,
- mniej quoting bugs,
- lepsze raportowanie,
- łatwiejsze GUI.

---

# 23. Plugin architecture

Proponowana struktura:

```text
local-agent/
├── agentd.py
├── core/
│   ├── scheduler.py
│   ├── executor.py
│   ├── result_writer.py
│   ├── policies.py
│   ├── workspace.py
│   └── schemas.py
├── tools/
│   ├── shell.py
│   ├── git.py
│   ├── platformio.py
│   ├── npm.py
│   ├── python.py
│   ├── serial.py
│   ├── esp32.py
│   └── filesystem.py
├── plugins/
│   ├── github/
│   ├── esp32/
│   ├── node/
│   └── docker/
├── workflows/
├── schemas/
└── tests/
```

---

# 24. Interfejs toola

Przykład Python:

```python
class Tool:
    name: str

    def validate(self, args: dict) -> None:
        ...

    def run(self, context, args: dict):
        ...
```

Przykład:

```python
class GitStatusTool(Tool):
    name = "git.status"

    def run(self, context, args):
        return run_command(
            ["git", "status", "--short"],
            cwd=context.worktree
        )
```

---

# 25. Policy engine

Przed wykonaniem toola:

```text
task
 |
 v
schema validation
 |
 v
policy validation
 |
 v
execution
```

Przykładowe reguły:

```text
deny rm -rf /
deny sudo
deny chmod on system dirs
deny writes outside workspace
deny force push by default
deny secrets in task JSON
deny arbitrary external upload
```

Poziomy:

```text
safe
write
publish
hardware
dangerous
```

Przykład permissions:

```json
"permissions": [
  "repo.read",
  "repo.write",
  "tests.run"
]
```

Publikacja:

```json
"permissions": [
  "repo.publish"
]
```

---

# 26. Locking

Dla jednego worktree powinien istnieć lock:

```text
.agent/locks/work.lock
```

Nie pozwalać na:

```text
task A modyfikuje repo
task B jednocześnie resetuje repo
```

Docelowo:

```text
1 worktree = 1 active writer
```

---

# 27. Multi-worktree

Dalszy rozwój:

```text
~/agent-workspace/worktrees/
├── task-123/
├── task-124/
└── task-125/
```

Tworzenie przez:

```bash
git worktree add ...
```

Zalety:

- równoległe zadania,
- brak wzajemnego resetowania repo,
- łatwe izolowanie branchy,
- lepsze lokalne CI.

---

# 28. Multi-repo

Task może mieć:

```json
{
  "repositories": [
    {
      "name": "firmware",
      "url": "...",
      "branch": "main"
    },
    {
      "name": "frontend",
      "url": "...",
      "branch": "main"
    }
  ]
}
```

---

# 29. Workflow engine

Zamiast ręcznie wypisywać długą listę komend można mieć workflow:

```yaml
name: esp32-golden-audit

steps:
  - git.diff_check
  - platformio.host_tests
  - frontend.check
  - frontend.lint
  - frontend.test
  - firmware.build
  - firmware.flash
  - serial.smoke
```

Task:

```json
{
  "id": "golden-audit-001",
  "mode": "workflow",
  "workflow": "esp32-golden-audit"
}
```

---

# 30. Resume / checkpoints

Bardzo ważne dla długich audytów.

Jeśli:

```text
host tests PASS
frontend PASS
ASAN PASS
coverage FAIL przez brak gcovr
```

nie powinno się powtarzać całego procesu.

Wynik powinien zapisywać:

```json
{
  "completed_steps": [
    "host-tests",
    "frontend",
    "asan"
  ],
  "failed_step": "coverage"
}
```

Następny task:

```json
{
  "resume_from": "coverage"
}
```

---

# 31. Retry policy

Przykład:

```json
{
  "retry": {
    "max_attempts": 3,
    "on": [
      "network_error",
      "git_fetch_error"
    ]
  }
}
```

Nie retry automatycznie:

```text
compiler_error
unit_test_failure
source_mismatch
```

---

# 32. Conditional steps

Przykład:

```json
{
  "if_changed": [
    {
      "glob": "interface/**",
      "run": "frontend-full-suite"
    },
    {
      "glob": "lib/automation/**",
      "run": "nodeflow-host-tests"
    }
  ]
}
```

---

# 33. Test selection — golden standard

```text
mała zmiana
 -> targeted tests

zmiana public contract
 -> targeted + contract tests

zmiana produkcyjna zakończona
 -> pełny gate raz

brak zmian po pełnym gate
 -> NIE powtarzać gate
```

---

# 34. Artefakty

Task może produkować:

```text
coverage report
firmware binary
map file
screenshots
benchmark CSV
serial log
diff
build report
```

Przykład:

```json
"artifacts": [
  {
    "type": "coverage",
    "path": "build/test/coverage/html/index.html"
  }
]
```

---

# 35. Metrics

Warto automatycznie zbierać:

```text
elapsed time
peak RSS
CPU time
disk writes
test count
coverage
binary size
RAM usage
flash usage
serial boot time
warnings
```

Przykład:

```json
"metrics": {
  "tests_passed": 1925,
  "tests_failed": 0,
  "firmware_flash_bytes": 4871378,
  "firmware_ram_bytes": 78784
}
```

---

# 36. Web UI

Naturalny kolejny etap:

```text
Local Agent
├── Queue
├── Running
├── History
├── Workspaces
├── Tools
├── Hardware
└── Settings
```

Task card:

```text
ID
branch
status
elapsed
current command
stdout tail
PASS/FAIL
artifacts
```

---

# 37. API

Przykładowy lokalny REST API:

```text
POST /tasks
GET  /tasks
GET  /tasks/{id}
POST /tasks/{id}/cancel
GET  /tasks/{id}/logs
GET  /tools
GET  /health
```

---

# 38. Event stream

Do live UI:

```text
GET /events
```

SSE albo WebSocket.

Event:

```json
{
  "task_id": "abc",
  "type": "command_started",
  "command": "npm run test",
  "timestamp": "..."
}
```

---

# 39. CLI

Przykład:

```bash
agent task create task.json
agent task list
agent task watch abc
agent task cancel abc
agent tools
agent health
```

---

# 40. ChatGPT integration

Najprostszy model:

```text
ChatGPT generuje JSON
        |
commit do agent-control
        |
daemon wykonuje
        |
wynik trafia do agent-control
        |
ChatGPT czyta wynik
```

Lepsza wersja przyszłości:

```text
ChatGPT
  |
HTTP API
  |
local-agent
```

Branch `agent-control` nadal może pozostać jako audit log i fallback.

---

# 41. Git jako message bus

Aktualna wersja używa Git jako prostego transportu komunikatów.

Zalety:

- działa bez otwierania portów,
- historia,
- audit,
- wersjonowanie,
- łatwy dostęp z GitHub,
- bardzo proste wdrożenie.

Wady:

- polling,
- latency,
- konflikty,
- commit noise,
- wolniejsze od API/message queue.

Projekt może obsługiwać transporty:

```text
git
local filesystem
HTTP
WebSocket
Redis
NATS
MQTT
```

Interfejs:

```python
class TaskTransport:
    def list_pending(self):
        ...

    def publish_result(self, result):
        ...
```

---

# 42. MQTT jako transport

Dla embedded / lab automation to naturalne rozszerzenie.

Przykład:

```text
local-agent/tasks/<host>
local-agent/results/<host>
```

Dzięki temu jeden controller może sterować wieloma runnerami.

---

# 43. Remote runners

```text
            controller
                |
    +-----------+-----------+
    |           |           |
  Mac runner   Pi runner   Lab runner
    |           |           |
 frontend     linux       hardware
```

Każdy runner publikuje capabilities:

```json
{
  "host": "macbook",
  "tools": [
    "git",
    "node",
    "platformio",
    "esp32-flash"
  ]
}
```

---

# 44. Capability discovery

Endpoint:

```text
GET /capabilities
```

Przykład:

```json
{
  "os": "macOS",
  "arch": "arm64",
  "tools": {
    "git": "2.x",
    "python": "3.x",
    "node": "22.x",
    "platformio": "installed"
  },
  "devices": [
    {
      "type": "serial",
      "path": "/dev/cu.usbserial-110"
    }
  ]
}
```

---

# 45. Hardware registry

Przykład:

```yaml
devices:
  esp32s3-main:
    port: /dev/cu.usbserial-110
    platformio_env: esp32s3-firmware-embedded-web
```

Task:

```json
{
  "tool": "esp32.flash",
  "device": "esp32s3-main"
}
```

---

# 46. Secrets

Nigdy nie wkładać sekretów bezpośrednio do task JSON.

Zamiast:

```json
{
  "token": "ghp_..."
}
```

używać:

```json
{
  "secret_ref": "github/default"
}
```

Daemon pobiera sekret lokalnie z Keychain / credential store / env.

---

# 47. Sandboxing

Przyszła wersja może wspierać:

```text
native
docker
podman
VM
```

Task:

```json
{
  "sandbox": "docker",
  "image": "node:22"
}
```

Dla hardware task zwykle:

```text
native
```

---

# 48. Cancellation

Daemon powinien obsługiwać:

```text
SIGTERM
task cancel
timeout
```

Procesy uruchamiać w osobnej process group.

Przy cancel:

```text
TERM
wait
KILL jeśli konieczne
```

---

# 49. Heartbeat daemona

Health state:

```json
{
  "status": "ok",
  "last_poll": "...",
  "running_task": null,
  "version": "0.1.0"
}
```

---

# 50. Log rotation

Aktualny log:

```text
~/Library/Logs/local-agent.log
```

Docelowo rotacja np.:

```text
10 MB x 5
```

---

# 51. Obserwacja lokalna

```bash
tail -f ~/Library/Logs/local-agent.log
```

Snapshot:

```bash
tail -n 80 ~/Library/Logs/local-agent.log
```

Procesy:

```bash
ps -axo pid,ppid,etime,%cpu,%mem,command | \
grep -E "platformio|pio |npm|node|python3|clang|gcovr|serial" | \
grep -v grep
```

---

# 52. Lessons learned z praktycznych zadań

## 058

Task nie wystartował poprawnie, ponieważ patch miał format `*** Begin Patch`, a wykonawca używał `git apply`.

Wniosek: nie mieszać formatów patchy.

## 059

Unified diff był uszkodzony:

```text
corrupt patch at line ...
```

Wniosek: dla małych zmian lepszy jest deterministyczny Python / structured edit.

## 060

Structured edit + testy:

```text
targeted tests PASS
npm run check PASS
npm run lint PASS
full frontend tests PASS
npm run build PASS
git diff --check PASS
```

To jest dobry wzorzec zadania walidacyjnego.

## 061

Commit powstał, ale pre-push hook ponownie uruchomił kosztowny suite i proces push zakończył się niepowodzeniem.

Wniosek:

```text
walidacja i publikacja powinny być osobnymi fazami
```

## 062

Push `git push origin main` próbował wypchnąć lokalny `main`, mimo że commit był na technicznym branchu worktree.

Wniosek:

```bash
git push origin HEAD:main
```

## 063

Poprawna publikacja:

```bash
git push --no-verify origin HEAD:main
```

po wcześniejszej pełnej walidacji.

---

# 53. Dwie fazy: validate i publish

To powinien być core design osobnego projektu.

## Phase A — Validate

```text
apply changes
targeted tests
lint/check
full tests jeśli potrzebne
build
diff check
```

Wynik:

```text
VALIDATED_SHA
```

## Phase B — Publish

Publikuje **dokładnie VALIDATED_SHA**.

Nie modyfikuje kodu.

Sprawdza:

```text
HEAD == validated SHA
```

---

# 54. Immutable validated revision

Po walidacji:

```json
{
  "validated_sha": "abc123",
  "tests": {
    "frontend": "pass",
    "host": "pass"
  }
}
```

Publikacja powinna odmówić jeśli:

```text
HEAD != validated_sha
```

---

# 55. Artifact attestation

W przyszłości:

```json
{
  "sha": "abc123",
  "validation": {
    "test_suite": "pass",
    "build": "pass"
  },
  "created_at": "..."
}
```

---

# 56. Nazwa projektu

Kilka sensownych nazw:

```text
LocalForge
AgentForge
TaskForge
LocalOps
RunForge
Deterministic Agent
Local Agent Control
```

Dobra nazwa robocza:

```text
LocalForge
```

Opis:

> Deterministic local task runner and hardware-aware development agent.

---

# 57. MVP osobnego projektu

Pierwsza wersja powinna mieć tylko:

```text
1. daemon
2. JSON schema
3. filesystem/git transport
4. shell tool
5. git tool
6. task result
7. logs
8. timeout
9. locking
10. CLI watch
```

Nie dodawać od razu LLM.

---

# 58. MVP task schema

```json
{
  "schema_version": 1,
  "id": "task-001",
  "repo": "esp32s3_LiteGraph",
  "branch": "main",
  "workspace_policy": "reset-to-remote",
  "permissions": [
    "repo.read",
    "repo.write",
    "tests.run"
  ],
  "steps": [
    {
      "type": "command",
      "run": "git diff --check",
      "timeout": 60
    }
  ],
  "publish": false
}
```

---

# 59. Rozszerzony schema

```json
{
  "schema_version": 1,
  "id": "task-001",
  "repo": {
    "name": "esp32s3_LiteGraph",
    "remote": "origin",
    "branch": "main"
  },
  "workspace": {
    "policy": "reset-to-remote",
    "expected_head": null
  },
  "permissions": [
    "repo.read",
    "repo.write",
    "tests.run"
  ],
  "steps": [
    {
      "id": "diff-check",
      "tool": "shell",
      "args": {
        "command": "git diff --check"
      },
      "timeout": 60
    }
  ],
  "retry": {
    "max_attempts": 1
  },
  "publish": {
    "enabled": false
  }
}
```

---

# 60. Project config

Plik:

```text
local-agent.yaml
```

Przykład:

```yaml
runner:
  poll_interval_seconds: 15
  log_file: ~/Library/Logs/local-agent.log

workspace:
  root: ~/agent-workspace

transport:
  type: git
  control_repo: ~/agent-workspace/control
  branch: agent-control

repositories:
  esp32s3_LiteGraph:
    path: ~/agent-workspace/work
    remote: origin
```

---

# 61. Daemon loop — pseudocode

```python
while True:
    transport.sync()

    task = transport.next_pending_task()

    if task is None:
        log("no pending tasks")
        sleep(poll_interval)
        continue

    if results.exists(task.id):
        continue

    try:
        validate_schema(task)
        workspace.prepare(task)
        result = executor.run(task)
    except Exception as exc:
        result = failed_result(task, exc)

    transport.publish_result(result)
```

---

# 62. Executor — pseudocode

```python
def run(task):
    started = now()

    for step in task.steps:
        validate_permissions(step)
        result = execute_step(step)

        if result.exit_code != 0:
            return {
                "status": "failed",
                "failed_step": step.id
            }

    return {
        "status": "done",
        "started_at": started,
        "finished_at": now()
    }
```

---

# 63. Safe subprocess

W Pythonie preferować:

```python
subprocess.Popen(
    command,
    cwd=workspace,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    start_new_session=True
)
```

Nie wszędzie `shell=True`.

Jeśli trzeba wspierać shell expressions, jawnie oznaczać task jako shell i traktować jako wyższy poziom uprawnień.

---

# 64. Command output

Nie trzymać nieograniczonego outputu w RAM.

Model:

```text
stdout -> log file
       -> ring buffer last N KB
       -> optional result excerpt
```

Result JSON:

```json
{
  "stdout_tail": "...",
  "log_path": "..."
}
```

---

# 65. Duże wyniki

Nie commitować wielomegabajtowych logów do Git.

Result powinien zawierać:

```text
summary
path / artifact reference
hash
size
```

---

# 66. Hash artefaktów

Dla buildów:

```text
SHA256 firmware.bin
SHA256 report.json
```

---

# 67. Repo-specific profiles

Profil ESP32:

```yaml
profiles:
  esp32-platformio:
    test:
      - pio run -c platformio.tests.ini -e test-all-host
    build:
      - pio run -e esp32s3-firmware-embedded-web
```

Frontend:

```yaml
  svelte:
    check:
      - npm run check
    lint:
      - npm run lint
    test:
      - npm run test
    build:
      - npm run build
```

---

# 68. Dynamic test plan

Planner może wygenerować:

```json
{
  "changed_areas": [
    "interface/src/lib/features/ble"
  ],
  "recommended_tests": [
    "ble-targeted",
    "frontend-check"
  ]
}
```

Executor nadal wykonuje tylko zatwierdzony plan.

---

# 69. Human approval gates

Przykład:

```json
{
  "steps": [
    { "tool": "tests.run" },
    {
      "approval": "required",
      "before": "git.publish"
    }
  ]
}
```

Daemon zatrzymuje task:

```text
status = blocked_for_approval
```

---

# 70. Publish policies

Bezpieczne domyślne:

```text
force push = disabled
delete branch = disabled
push to protected branch = approval
tag = approval
release = approval
```

---

# 71. Hardware policies

```text
flash = allowed only registered device
erase flash = approval
efuse = deny
factory reset = approval
```

---

# 72. Project extensibility

Rdzeń powinien znać tylko:

```text
Task
Step
Tool
Workspace
Transport
Result
Policy
```

Wszystko inne jako plugin:

```text
Git
PlatformIO
Docker
ESP32
npm
pytest
serial
MQTT
GitHub
SSH
```

---

# 73. Potencjalne zastosowania poza kodem

Ten sam daemon może później robić:

```text
backup
media conversion
data processing
scheduled scripts
home lab management
server maintenance
device flashing
IoT fleet testing
benchmarking
ML experiments
```

---

# 74. Uruchamianie jako usługa

Na macOS:

```text
launchd
```

Na Linux:

```text
systemd
```

Na Android/Termux:

```text
Termux:Boot
```

---

# 75. Systemd — przykład

```ini
[Unit]
Description=Local Agent

[Service]
ExecStart=/usr/bin/python3 /opt/local-agent/agentd.py
Restart=always
WorkingDirectory=/opt/local-agent

[Install]
WantedBy=multi-user.target
```

---

# 76. Versioning

Daemon powinien raportować:

```json
{
  "agent_version": "0.1.0",
  "task_schema_version": 1
}
```

Task z nowszym schema powinien kończyć się:

```text
unsupported_schema
```

---

# 77. Database

Na początku wystarczy filesystem + JSON.

Później SQLite:

```text
tasks
steps
runs
artifacts
runners
devices
```

Git pozostaje opcjonalnym transportem.

---

# 78. SQLite schema — szkic

```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    payload_json TEXT NOT NULL
);
```

---

# 79. Scheduler

W przyszłości:

```text
priority
dependencies
resource locks
runner capabilities
scheduled time
```

Task:

```json
{
  "priority": 50,
  "requires": [
    "platformio",
    "device:esp32s3-main"
  ]
}
```

---

# 80. DAG workflows

```text
          lint
         /    \
       test   build
         \    /
          flash
            |
          smoke
```

---

# 81. Soak tasks

Przykład:

```json
{
  "mode": "soak",
  "duration": "24h",
  "checks": [
    "serial-alive",
    "heap",
    "queue-depth"
  ]
}
```

Daemon zbiera serię metryk.

---

# 82. Monitoring

Można dodać Prometheus / JSON health / Grafana.

Metryki:

```text
tasks_total
tasks_failed
task_duration_seconds
active_tasks
runner_idle_seconds
```

---

# 83. Notifications

Pluginy:

```text
email
Slack
Discord
Telegram
ntfy
```

Tylko po istotnych stanach:

```text
failed
done
approval required
```

---

# 84. Security model

Minimalny model zagrożeń:

- task JSON może zawierać złośliwą komendę,
- planner może się pomylić,
- repo może zawierać złośliwy hook,
- build script może zrobić coś niebezpiecznego,
- task może próbować wyjść poza workspace.

Dlatego:

```text
permissions
path sandbox
tool allowlist
timeouts
no sudo
no secrets in payload
audit log
```

---

# 85. Audit log

Każde zadanie powinno zapisywać:

```text
kto utworzył
kiedy
payload hash
workspace SHA
commands
exit codes
result
publish SHA
```

---

# 86. Idempotency

Task ID jest kluczem idempotencji.

Jeśli istnieje:

```text
result/task-123.json
```

daemon nie wykonuje go ponownie.

Retry powinien mieć nowy run id.

---

# 87. Dead letter queue

Po kilku błędach infrastruktury:

```text
.agent/dead-letter/
```

żeby jeden task nie blokował całej kolejki.

---

# 88. Priority queue

Obecnie kolejność można wymuszać nazwami:

```text
000-
001-
002-
```

Docelowo lepiej mieć:

```json
"priority": 100
```

---

# 89. Dependency task

```json
{
  "depends_on": [
    "build-001"
  ]
}
```

---

# 90. Runner labels

```json
{
  "requires_runner_labels": [
    "macos",
    "arm64",
    "esp32-connected"
  ]
}
```

---

# 91. Reproducibility

Result powinien zapisać:

```text
git SHA
OS
Python version
Node version
PlatformIO version
tool versions
```

---

# 92. Example full task

```json
{
  "schema_version": 1,
  "id": "ble-contract-fix-001",
  "repo": {
    "name": "esp32s3_LiteGraph",
    "branch": "main"
  },
  "workspace": {
    "policy": "reset-to-remote"
  },
  "permissions": [
    "repo.read",
    "repo.write",
    "tests.run"
  ],
  "steps": [
    {
      "id": "preflight",
      "tool": "shell",
      "args": {
        "command": "git diff --check"
      }
    },
    {
      "id": "edit",
      "tool": "python.script",
      "args": {
        "path": ".agent/patches/fix_ble_contract.py"
      }
    },
    {
      "id": "targeted-tests",
      "tool": "npm.test",
      "args": {
        "pattern": "ble"
      }
    },
    {
      "id": "diff-check",
      "tool": "shell",
      "args": {
        "command": "git diff --check"
      }
    }
  ],
  "publish": {
    "enabled": false
  }
}
```

---

# 93. Example validation result

```json
{
  "id": "ble-contract-fix-001",
  "status": "done",
  "validated_sha": "abc123",
  "commands": [
    {
      "id": "preflight",
      "exit_code": 0
    },
    {
      "id": "targeted-tests",
      "exit_code": 0,
      "summary": "68/68 PASS"
    }
  ]
}
```

---

# 94. Example publish task

```json
{
  "schema_version": 1,
  "id": "publish-ble-contract-001",
  "repo": {
    "name": "esp32s3_LiteGraph",
    "branch": "main"
  },
  "workspace": {
    "expected_head": "abc123"
  },
  "permissions": [
    "repo.publish"
  ],
  "steps": [
    {
      "tool": "git.push",
      "args": {
        "source": "HEAD",
        "destination": "main"
      }
    }
  ]
}
```

---

# 95. Co zachować z obecnego systemu

Zdecydowanie zachować:

- osobny branch `agent-control`,
- osobne repo control/work,
- task JSON,
- result JSON,
- deterministyczne shell execution,
- sortowaną kolejkę,
- unikalne task IDs,
- poll loop,
- pełne logowanie,
- możliwość lokalnego monitorowania,
- oddzielenie walidacji od publikacji,
- brak obowiązkowego lokalnego LLM.

---

# 96. Co poprawić w nowym projekcie

Najważniejsze:

1. typed tools zamiast samych shell strings,
2. JSON Schema,
3. explicit permissions,
4. expected SHA,
5. immutable validated SHA,
6. publish jako osobna faza,
7. resumable workflows,
8. per-step checkpoint,
9. retry policy,
10. file locking,
11. multi-worktree,
12. artifact handling,
13. structured metrics,
14. process cancellation,
15. log rotation.

---

# 97. Golden architecture

```text
                  ┌─────────────────┐
                  │  ChatGPT / CLI  │
                  │  UI / API       │
                  └────────┬────────┘
                           │
                           v
                  ┌─────────────────┐
                  │   Task Planner  │
                  └────────┬────────┘
                           │
                           v
                  ┌─────────────────┐
                  │ Schema Validator│
                  └────────┬────────┘
                           │
                           v
                  ┌─────────────────┐
                  │  Policy Engine  │
                  └────────┬────────┘
                           │
                           v
              ┌────────────────────────┐
              │       Scheduler        │
              └──────────┬─────────────┘
                         │
               ┌─────────┴──────────┐
               │                    │
               v                    v
       ┌───────────────┐    ┌───────────────┐
       │ Local Runner  │    │ Remote Runner │
       └───────┬───────┘    └───────┬───────┘
               │                    │
               v                    v
       ┌────────────────────────────────────┐
       │ Tools                              │
       │ Git / Shell / npm / PIO / Serial  │
       │ Docker / Python / ESP32 / MQTT    │
       └────────────────────────────────────┘
                         │
                         v
                 ┌──────────────┐
                 │ Result Store │
                 └──────────────┘
```

---

# 98. Najważniejsza zasada projektu

Projekt powinien być:

```text
AI-friendly
ale
nie AI-dependent
```

Czyli:

- AI może planować,
- AI może analizować,
- AI może proponować zmiany,
- ale wykonanie jest jawne,
- walidowalne,
- deterministyczne,
- audytowalne.

---

# 99. Minimalna ścieżka do osobnego repo

## Etap 1

Przenieść `agentd.py` do osobnego repo.

## Etap 2

Dodać:

```text
README.md
pyproject.toml
schemas/task.schema.json
local_agent/
tests/
```

## Etap 3

Wyciągnąć hardcoded ścieżki do:

```text
local-agent.yaml
```

## Etap 4

Dodać `Tool` abstraction.

## Etap 5

Dodać CLI:

```bash
local-agent run
local-agent status
local-agent watch
```

## Etap 6

Dodać worktree isolation.

## Etap 7

Dodać HTTP API i prosty web UI.

---

# 100. Proponowana struktura nowego repo

```text
localforge/
├── README.md
├── LICENSE
├── pyproject.toml
├── localforge.example.yaml
├── schemas/
│   └── task.schema.json
├── localforge/
│   ├── __init__.py
│   ├── cli.py
│   ├── daemon.py
│   ├── scheduler.py
│   ├── executor.py
│   ├── transport/
│   │   ├── base.py
│   │   ├── filesystem.py
│   │   └── git.py
│   ├── workspace/
│   │   ├── manager.py
│   │   └── worktree.py
│   ├── policy/
│   │   └── engine.py
│   ├── tools/
│   │   ├── base.py
│   │   ├── shell.py
│   │   ├── git.py
│   │   ├── python.py
│   │   ├── npm.py
│   │   ├── platformio.py
│   │   └── serial.py
│   └── models/
│       ├── task.py
│       └── result.py
└── tests/
    ├── test_scheduler.py
    ├── test_executor.py
    ├── test_git_transport.py
    └── test_policy.py
```

---

# 101. Roadmap

## v0.1

```text
single host
single active task
filesystem/git transport
shell tool
git tool
JSON task/result
timeouts
logs
locking
CLI
```

## v0.2

```text
typed tools
worktrees
resume
artifacts
metrics
```

## v0.3

```text
HTTP API
web UI
remote runners
capability discovery
```

## v0.4

```text
plugins
hardware registry
ESP32 support
MQTT transport
```

## v1.0

```text
stable task schema
stable plugin API
security policy
multi-runner scheduler
```

---

# 102. Podsumowanie

Obecny system już udowodnił, że model:

```text
ChatGPT
  ->
task JSON
  ->
lokalny deterministic daemon
  ->
test/build/flash/publish
  ->
result JSON
```

działa praktycznie.

Najcenniejsze cechy:

- pełna kontrola nad lokalnym środowiskiem,
- możliwość testowania prawdziwego hardware,
- brak zależności od chmurowego CI,
- możliwość wykonywania bardzo długich testów,
- deterministyczne wykonanie,
- prosty audit,
- naturalna integracja z AI,
- łatwa rozbudowa o nowe tools i runnerów.

To jest wystarczająco uniwersalny pomysł, żeby rozwijać go jako osobny projekt.
