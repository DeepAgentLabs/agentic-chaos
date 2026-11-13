# Core concepts

| Concept | Meaning |
| --- | --- |
| Call wrapper | chaos_call forwards to the real function unless an active session selects a relevant fault. |
| Fault configuration | Names use default settings; fault instances allow explicit parameter values. |
| Event | A record of injected behavior and its outcome; not a declaration that recovery was adequate. |
| Experiment target | The application path being stressed, including its error handling and fallback behavior. |
| Fidelity vs drift | Fidelity concerns degraded-output quality; drift concerns changes between recorded snapshots. |
