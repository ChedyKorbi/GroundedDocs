# GroundedDocs — CV Content

Ready-to-paste bullets for a "Selected Projects" / "Projets clés" section.
Every number is taken from the repository's evaluation reports and phase docs.
Versions are in English and French (French written natively, not translated).

---

## English

### Short version (2–3 bullets, one-page CV)

- **Built GroundedDocs**, a production hybrid RAG system for enterprise
  documentation — dense + BM25 retrieval fused with Reciprocal Rank Fusion,
  reranking, and per-claim citation verification. Measured **96.3% faithfulness**
  and **88.2% citation accuracy** on a 48-question golden set.
- **Designed the evaluation harness** (LLM-as-judge metrics, **100% judge↔human
  calibration**, chunking-strategy comparison) plus a CI eval gate that blocks
  regressions — **107 unit tests** and strict typing across the codebase.
- **Shipped it** as a Dockerized FastAPI service with observability
  (stage-level latency, token/cost per query, p50/p95), zero-downtime
  reindexing, and a Next.js dashboard.

### Extended version (5–7 bullets, portfolio / LinkedIn featured)

- Built **GroundedDocs**, a production-grade hybrid RAG system for enterprise
  documentation: ingestion with three chunking strategies, dense (multilingual
  e5-large) + BM25 retrieval, RRF fusion, cross-encoder reranking, grounded
  generation, and post-hoc citation verification.
- **Hybrid retrieval lifted recall@3 to 100% vs 88.9% dense-only** on the
  retrieval golden set; the full pipeline scored **96.3% faithfulness** and
  **88.2% citation accuracy** on a 48-question set spanning easy, multi-hop,
  ambiguous, and unanswerable questions.
- Engineered the **anti-hallucination layer**: per-claim↔citation LLM
  verification, **100% correct refusal** on unanswerable questions
  (0% hallucination), and a composite confidence score.
- Built the **evaluation framework**: LLM-as-judge faithfulness/relevance
  metrics, **100% judge↔human calibration** (both fabricated answers caught), a
  chunking-strategy shootout (fixed 81.0% vs structure 74.4% vs semantic 70.4%
  recall@1), and automated failure analysis.
- Shipped a **production FastAPI** with per-stage latency tracking, token +
  estimated cost per query, p50/p95/p99, request-id tracing, API-key auth, rate
  limiting, and **zero-downtime reindexing** via versioned Qdrant collections.
- Set up **CI** with lint, strict mypy typing, 107 unit tests + 6 real-stack
  integration tests, dependency audit, Docker build, and an **eval gate** that
  fails the build below 85% faithfulness / 80% citation accuracy.
- Built a **Next.js dashboard** (Ask / Documents / Performance) rendering
  citations, confidence, and live telemetry, consuming a frozen API contract.

---

## Français

### Version courte (2–3 puces, CV une page)

- **Conçu GroundedDocs**, un système de RAG hybride de production pour la
  documentation d'entreprise — fusion dense + BM25 (Reciprocal Rank Fusion),
  re-ranking et vérification de chaque citation. Fidélité mesurée à
  **96,3 %** et précision des citations à **88,2 %** sur un jeu d'évaluation
  de 48 questions.
- **Bâti le framework d'évaluation** (métriques par LLM-juge, calibration
  juge/humain à **100 %**, comparaison des stratégies de découpage) avec une
  porte qualité CI qui bloque toute régression — **107 tests unitaires** et
  typage strict.
- **Livré** en service FastAPI dockerisé avec observabilité complète (latence
  par étape, tokens + coût par requête, p50/p95), réindexation sans
  interruption et dashboard Next.js.

### Version détaillée (5–7 puces, portfolio / section LinkedIn)

- Conçu **GroundedDocs**, un système de RAG hybride de production pour la
  documentation d'entreprise : ingestion avec trois stratégies de découpage,
  recherche dense (multilingual e5-large) + BM25, fusion RRF, re-ranking par
  cross-encoder, génération ancrée sur les sources et vérification des
  citations a posteriori.
- La **recherche hybride porte le recall@3 à 100 % contre 88,9 % en dense
  seul** sur le jeu d'évaluation de retrieval ; la chaîne complète atteint
  **96,3 % de fidélité** et **88,2 % de précision des citations** sur un jeu
  de 48 questions (faciles, multi-étapes, ambiguës, non-répondables).
- Conçu la **couche anti-hallucination** : vérification LLM de chaque
  paire affirmation↔citation, **refus correct à 100 %** sur les questions
  hors-corpus (0 % d'hallucination) et score de confiance composite.
- Développé le **framework d'évaluation** : métriques de fidélité et de
  pertinence par LLM-juge, **calibration juge/humain à 100 %** (les deux
  réponses fabriquées détectées), comparaison des stratégies de découpage
  (fixe 81,0 % vs structure 74,4 % vs sémantique 70,4 % en recall@1) et
  analyse automatique des échecs.
- Mis en production une **API FastAPI** avec latence mesurée par étape, suivi
  des tokens et du coût estimé par requête, p50/p95/p99, traçabilité par
  request-id, authentification par clé API, limitation de débit et
  **réindexation sans interruption** via des collections Qdrant versionnées.
- Mise en place d'une **CI** complète (lint, mypy strict, 107 tests unitaires +
  6 tests d'intégration réels, audit de dépendances, build Docker) et d'une
  **porte qualité d'évaluation** qui fait échouer le build sous 85 % de
  fidélité / 80 % de précision des citations.
- Développé un **dashboard Next.js** (Questions / Documents / Performance)
  affichant citations, confiance et télémétrie temps réel, adossé à un contrat
  API figé.
