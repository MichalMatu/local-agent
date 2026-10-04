# Next chat prompt — live Superchat acceptance

Paste the following into one new ChatGPT window. This is the parent Superchat; do not start from a child window.

---

Kontynuujemy `MichalMatu/local-agent`, ale nie korzystaj z pamięci poprzedniego czatu jako źródła prawdy. To jest **live acceptance Superchatu na realnym kodzie**, nie kolejny audyt projektu ani kolejna runda projektowania.

Najpierw przeczytaj z aktualnego `main`:

1. `AGENTS.md`
2. `docs/CURRENT_HANDOFF.md`
3. `docs/conversation_fabric/CHECKPOINT_2026-10-04_SUPERCHAT_READY.md`
4. `docs/conversation_fabric/CURRENT_PLAN.md`
5. `docs/GOLDEN_STANDARD.md`
6. `docs/OPERATIONS.md`

Następnie sprawdź świeży stan GitHub i produkcji: aktualny `main`, `daemon_version`, `self_revision`, Chat Bridge, dokładny control record tego nowego czatu oraz stan/configuration Conversation Operator. Nie zakładaj, że operator intake jest włączony. Jeśli do bounded live proof trzeba go włączyć, użyj wyłącznie istniejącej wspieranej ścieżki i zapisz dokładny stan przed/po. Nie obchodź zabezpieczeń i nie wracaj do ręcznych pętli Chrome/login/Cloudflare.

Cel tego okna: **mam zobaczyć jeden Superchat, który realnie deleguje i orkiestruje zadania.**

Wybierz jeden mały, realny cel na prawdziwym kodzie w repozytorium z `execution_enabled=true` (preferuj `growclip`, jeżeli po świeżej inspekcji ma sensowny bounded task). Rodzic ma pozostać jedynym koordynatorem.

Wykonaj acceptance w tej kolejności:

- utwórz co najmniej dwa reasoning-only podczaty o niepokrywających się rolach;
- child A niech zrobi wąski audyt kodu/architektury wybranego fragmentu;
- child B niech niezależnie przeanalizuje testy, failure modes i jakość proponowanego kierunku;
- przypnij dzieciom konkretny repo/commit i bounded output; dzieci nie mogą wykonywać komend ani tworzyć `.agent/tasks`;
- obserwuj ich realne wyniki i pokaż mi krótko, co każde dziecko ustaliło;
- jako rodzic porównaj wyniki, rozstrzygnij rozbieżności i podejmij decyzję;
- tylko jeśli zmiana w kodzie jest uzasadniona, utwórz **dokładnie jedno** zadanie Local Agent w prawdziwym repo targetowym, z jego dokładnym `agent_binding` i stabilnym branch-scoped `dedupe_key` dla tego intentu;
- sprawdź, że wykonało się tylko jedno zadanie i nie pojawił się drugi identyczny build/test;
- zweryfikuj wynik na realnym kodzie i pokaż trwałe evidence;
- na końcu uporządkuj/wycofaj bounded child lifecycle oraz przywróć zamierzony paused/disabled state operatora, jeśli proof został zakończony.

Nie rób szerokiego fan-outu ani stress testu. Nie twórz pracy „dla demonstracji”, jeżeli inspekcja nie uzasadnia zmiany — w takim przypadku dzieci mogą zakończyć realnym audytem, ale nadal musisz udowodnić delegację/orchestration i jasno powiedzieć, że execution było niepotrzebne.

Stop i zgłoś konkretny blocker zamiast osłabiać kontrakty, jeśli auth/ownership dziecka jest niejednoznaczny, binding targetu jest niepewny, pojawiają się dwie autorytatywne instancje dziecka, dziecko uzyskuje machine authority albo równoważna kosztowna praca uruchamia się drugi raz.

Na końcu daj jeden werdykt: `PASS`, `PARTIAL` albo `FAIL`, z dokładnymi SHA/ID/evidence oraz maksymalnie jednym następnym blockerem.

---
