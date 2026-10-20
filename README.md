# FareGuard — Real-Time Travel Booking Fraud & Credit-Line Monitoring Platform

> A clean-room, portfolio project — not affiliated with or derived from any employer codebase.
> Mirrors the *shape* of a real problem (sub-agent credit-line abuse in travel booking) using
> entirely synthetic data and a from-scratch architecture.

## Why this project
Built to deepen skills already on my resume (C++, Python, microservices, REST/Protobuf, CI/CD,
PCI-DSS-style security thinking) while deliberately learning new ones:
1. **Event-driven architecture** (Kafka) — async fraud-signal pipeline
2. **Agentic AI / tool-calling agents** — a ReAct-style investigation agent (not just RAG lookup)
3. **Observability** (Prometheus + Grafana) — metrics, dashboards, alerting
4. **Kubernetes** — real hands-on local deployment (kind/minikube + Helm)
5. **gRPC** — service-to-service calls using the Protobuf schemas already defined

Every new concept gets a plain-English explainer doc in `docs/learning-notes/` *before* it's used
in code, written for understanding first, implementation second.

## Status
Phase 0 complete (domain model + synthetic data generator). Next: Phase 1. See
[docs/00-roadmap.md](docs/00-roadmap.md) for the phased build plan and
[docs/hld/](docs/hld/) for the system design built up interactively.

Generate sample data: `python3 tools/datagen/generate.py` (output in `data/generated/`).

## Repo layout (will grow per phase)
```
docs/
  00-roadmap.md         Phased plan, decisions log
  hld/                  High-level design docs (system context, components, data flow)
  lld/                  Low-level design docs per service (written before that service is coded)
  learning-notes/       "What is X and why are we using it" — one topic per file
  decisions/            ADRs — short records of why a choice was made
  glossary.md           Running glossary of terms introduced
tools/datagen/          Synthetic data generator + tests (Phase 0)
services/               Added as each phase is built
```
