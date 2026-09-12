# mindx-review-bot migration to QQ Workflow v10

- Host baseline: `3370dd287a7e346441f7eed8aca678636cc1a88b` (last active v9.1.2 main).
- v10 source pin: `Banhtalon/qq-ai-workflow@e0c1944268bb328f992b6716cff72a64bc72a936` (`10.0.0-rc.1`).
- Active v9 controller/risk/attempt scripts are removed from the v10 branch; Git history preserves them for audit.
- Existing product history such as GitHub Issue #11 remains project history, but v10 mutable execution packets live under ignored `.workflow-local/`.
- Adoption starts in ASSISTED mode. LOCAL_AUTO is not valid until real Windows account/model probes, a real two-provider repair pilot, quota drill and activation receipt pass.
- Final merge remains an explicit Owner action after CI, independent technical review and functional acceptance where applicable.
