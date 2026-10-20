# FareGuard — Context Handoff / Resume-Here Doc

> Read this first if you're picking this project back up on a new machine or in a new chat
> session. It captures everything decided so far so no context is lost.

## 1. Background (why this project exists)
User is a Software Development Engineer (3+ yrs, Amadeus Software Labs) with a resume covering
C++, Python, microservices, REST/Protobuf, CI/CD (Jenkins/GitHub Actions/ArgoCD), PCI-DSS/SDL
security leadership, and a GenAI RAG project ("Invoice Bot"). The user explicitly said the
Invoice Bot and an "AI-Quant TradeStack" project (found at
`Personal Project/ai-quant-tradestack/`) were **not** real learning — those were built end-to-end
by an AI assistant without the user understanding the internals, and the user **does not want
that again**.

This new project, **FareGuard**, is being designed so the user:
- Understands the system at HLD/LLD level through interactive, step-by-step design discussion
  (not just handed a finished repo)
- Has a plain-English learning-note for every *new* concept before it's coded
- Still has the agent write most of the actual code (user won't read it line-by-line, but will
  understand *what* it does and *why* via docs)

## 2. Project concept
**FareGuard** — a clean-room (synthetic data, original design) simulation of a travel-booking
fraud / sub-agent credit-line monitoring platform. Deliberately mirrors the shape of a real
resume bullet ("real-time credit-line limit blocking for sub-agents... 1.5M+ annual bookings")
so the user can go deep in interviews, while adding a modern distributed-systems stack they
haven't used hands-on before.

**Interview pitch** (already agreed): *"At Amadeus I built real-time credit-line blocking for
sub-agent bookings at 1.5M+ annual transaction scale — this is a clean-room rebuild of that
problem class, designed from scratch so I own every decision, extended with Kafka, gRPC,
Kubernetes, observability, and a real tool-calling AI investigation agent."*

Key differentiator for interviews: the AI agent **investigates and explains** flagged bookings;
a deterministic rules engine owns the actual accept/reject decision (safety-first LLM pattern,
same philosophy as the user's PCI-DSS/SDL background).

## 3. Confirmed decisions
| Topic | Decision |
|---|---|
| Location | `C:\Users\an2kumar\OneDrive - Amadeus Workplace\Desktop\Personal Project\fareguard\` |
| Domain | Travel booking fraud / sub-agent credit-line monitoring (synthetic data only) |
| New skills to learn, in build order | Kafka (event-driven) → gRPC → Agentic AI (tool-calling) → Observability (Prometheus/Grafana) → Kubernetes |
| Skills to polish | C++, Python, microservices, REST/Protobuf, CI/CD, PCI-DSS/security mindset |
| Language split | Python for most services; one performance-critical service in C++ (credit-line/velocity rules engine) |
| Deployment | Local only — Docker Compose for dev, kind/minikube + Helm for the Kubernetes phase. No paid cloud. |
| CI/CD | GitHub Actions for build/test/lint/security-scan |
| Time budget | ~3-4 hrs/day |
| Code ownership | Agent writes most code; every phase gets HLD note + LLD note + learning-note(s) *before* code, written for understanding |
| GitHub repo (intended) | `https://github.com/Anshuman2101/FareGaurd.git` — **not yet created, see blocker below** |

Full phase breakdown is in [docs/00-roadmap.md](docs/00-roadmap.md) (8 phases, 0 through 8).

## 4. Blocker resolved — git/gh now available
Resolved on the current machine (2026-10-20): `git` (2.52.0) and `gh` (2.97.0) are installed and
on PATH. Completed:
1. Confirmed `git --version` and `gh --version` work.
2. Ran `git init` inside `fareguard/`, added `.gitignore` (Python/C++/Docker/Helm/secrets), made
   the first commit on branch `main`.
3. Authenticated `gh` (device flow, logged in as `Anshuman2101`). The GitHub repo
   `https://github.com/Anshuman2101/FareGaurd` already existed (empty) — added as `origin` and
   pushed `main`.
4. Continuing from "Next steps" below (domain model doc, then synthetic data generator).

## 5. Progress so far (files that exist today)
```
fareguard/
  README.md                        Project pitch, repo layout overview
  docs/
    00-roadmap.md                  Phases 0-8, decisions log, how-we-work process
    hld/
      01-system-context.md         Actors, system boundary, context diagram
      02-domain-model.md           Agency/SubAgent/CreditLine/Booking, limits, lifecycle,
                                    closed decisions (integer minor units, sub_limit policy)
    lld/
      00-synthetic-data-generator.md
  tools/datagen/
    generate.py                    Deterministic synthetic data generator (stdlib, Py3.9+)
    test_generate.py               unittest invariants (utilization, FK, labels, determinism)
```
**Phase 0 is complete** (2026-10-20). Run `python3 tools/datagen/generate.py` to produce
`data/generated/*.jsonl` (git-ignored); tests: `python3 -m unittest discover -s tools/datagen`.

## 6. Next steps (in order, once resumed)
1. **Phase 1**: Core booking API (Python/FastAPI) + C++ rules engine (credit-line limit, velocity
   checks), talking over REST/Protobuf. Polish-only phase (no new skill), but first real code.
   Start with the Phase 1 HLD (interactive), then LLD (including `FraudCase` entity and whether
   a "settled" booking state is needed), then build.
2. **Phase 2 onward**: follow `docs/00-roadmap.md` phase table (Kafka → gRPC → Agentic AI →
   Observability → Kubernetes → CI/CD hardening → optional UI/polish).

## 7. How to resume this conversation elsewhere
Open this folder (`fareguard/`) as the VS Code workspace, point the agent at this file
(`docs/CONTEXT_HANDOFF.md`) and `docs/00-roadmap.md`, and say "continue FareGuard from where we
left off." All decisions and rationale needed to pick back up are in this file — no need to
re-explain the background.
