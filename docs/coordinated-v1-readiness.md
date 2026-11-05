# Coordinated v1.0 engineering readiness

Chaos 0.11.0 remains the resilience/containment/ChaosHub baseline. Its native
reports and existing 0.4-draft Run exports continue to be cited as producer-owned
evidence. The coordinated installed-wheel matrix tests Chaos alongside the new
companion exporters/validators without moving fault execution or resilience
scoring into those packages. Optional existing ranges remain sufficient; no
Chaos runtime change or patch release is required.

See the organization repository's release/candidate.json and isolated-wheel
acceptance runner for exact source pins and validation. These internal runs do
not establish independent AIOS acceptance, production deployment safety or
exhaustive capture of behavior.

Independent acceptance, live/deployment evidence and the stable freeze remain
separate gates. See the [shared release policy](https://github.com/DeepAgentLabs/.github/blob/main/profile/RELEASE_POLICY.md).
