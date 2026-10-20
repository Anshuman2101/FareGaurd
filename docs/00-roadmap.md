# Roadmap &amp; Decisions Log

## Confirmed decisions (2026-10-20)
| Topic | Decision |
|---|---|
| Domain | Travel booking fraud / sub-agent credit-line monitoring (mirrors a real resume bullet, synthetic data only) |
| New skills to learn (in build order) | Kafka (event-driven) → gRPC → Agentic AI (tool-calling) → Observability (Prometheus/Grafana) → Kubernetes |
| Skills to polish | C++, Python, microservices, REST/Protobuf, CI/CD, PCI-DSS/security mindset |
| Language split | Python for most services; one performance-critical service in C++ (credit-line/velocity rules engine) |
| Deployment | Local only — Docker Compose for dev, kind/minikube + Helm for the Kubernetes phase. No paid cloud. |
| CI/CD | GitHub Actions for build/test/lint/security-scan (SAST-style, matching PCI-DSS/SDL background) |
| Time budget | ~3-4 hrs/day |
| Code ownership | Agent (Copilot) writes most code; every phase gets an HLD note, an LLD note, and a learning-note *before* code is written, so the user understands it without reading line-by-line |

## How we work (process, not just output)
For each phase:
1. **HLD step** — talk through the phase's design interactively (system context, components,
   data flow) in chat; user answers Socratic questions before the doc is finalized.
2. **LLD step** — once HLD for that phase is agreed, write a detailed LLD doc (interfaces, data
   models, sequence diagrams) — again interactively for any new concept.
3. **Learning note** — for any brand-new skill introduced in that phase, a standalone
   `docs/learning-notes/*.md` explaining the concept in plain English first.
4. **Build** — agent implements the phase.
5. **Verify** — run it, confirm it works, update docs if reality diverged from plan.

## Phases
| Phase | Goal | New skill introduced | Status |
|---|---|---|---|
| 0 | Repo skeleton, domain model, synthetic data generator | — | In progress |
| 1 | Core booking API (Python/FastAPI) + C++ rules engine (credit-line limit, velocity checks) via REST/Protobuf | — (polish only) | Not started |
| 2 | Event-driven fraud pipeline: booking events → Kafka → async fraud-signal consumer | Kafka | Not started |
| 3 | Convert gateway ↔ rules-engine call to gRPC | gRPC | Not started |
| 4 | AI Investigation Agent: ReAct-style tool-calling agent that investigates flagged bookings | Agentic AI | Not started |
| 5 | Metrics + dashboards: Prometheus exporters on each service, Grafana dashboards | Observability | Not started |
| 6 | Containerize everything, deploy to local Kubernetes via Helm | Kubernetes | Not started |
| 7 | CI/CD hardening: GitHub Actions pipeline, SAST/dependency scanning, secrets handling | — (polish, PCI-DSS tie-in) | Not started |
| 8 | Optional: lightweight case-review UI, polish, interview-guide write-up | — | Not started |

## Explicitly out of scope / notes
- No real PII — all bookings, agents, and credit-line data are synthetically generated.
- Not a copy of any employer system; names, schemas, and logic are original.
- LLM agent in Phase 4 investigates and explains; it never auto-approves/rejects a transaction —
  deterministic rules own that decision (safety-first pattern, same philosophy as PCI-DSS work).
