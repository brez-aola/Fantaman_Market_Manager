# Git branching strategy (GitFlow)

Questo progetto usa una variante semplice di GitFlow per mantenere stabilità sul branch `main` e permettere sviluppo parallelo.

Branch principali
- `main`: branch di produzione, sempre deployable. Proteggerlo con PR obbligatorie e almeno 1 approvatore.
- `develop`: branch di integrazione per feature complete che saranno testate prima del release.

Branch temporanei
- `feature/<nome-descrittivo>`: per nuove funzionalità. Derivare da `develop`. Merge in `develop` tramite PR.
- `hotfix/<descrizione>`: correzioni urgenti da derivare da `main` e merge sia in `main` sia in `develop`.
- `release/<versione>`: preparazione alla release, consente fix e testing prima del merge in `main`.

Regole e protezioni consigliate
- Abilitare branch protection su `main` con: richieste di PR, `pre-commit`/CI green e almeno 1 reviewer approvante.
- Abilitare protezione su `develop` per evitare merge diretto.
- Forzare merge tramite PR (no merge diretto) e preferire squash merging per mantenere history leggibile.
- Aggiungere controllo di sicurezza: scansione SAST/Dependency checks in CI.

Flusso di lavoro tipico
1. Crea `feature/my-feature` da `develop`.
2. Lavoraci localmente, apri PR verso `develop` quando pronta.
3. CI esegue lint, test e security scans.
4. Dopo approvazione e verifica, merge in `develop`.
5. Per release: creare `release/x.y.z` da `develop`, eseguire test, poi merge in `main` e creare tag/release.
