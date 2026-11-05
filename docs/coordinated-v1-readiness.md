# Coordinated v1.0 engineering readiness

Chaos 0.11.0 remains the resilience/containment/ChaosHub baseline. Its native
reports and existing 0.4-draft Run exports continue to be cited as producer-owned
evidence. The coordinated installed-wheel matrix tests Chaos alongside the new
companion exporters/validators without moving fault execution or resilience
scoring into those packages. Optional existing ranges remain sufficient; no
Chaos runtime change or patch release is required.

See the organization repository's [candidate matrix](https://github.com/DeepAgentLabs/.github/blob/feat/coordinated-v1-readiness/release/candidate.json)
and revision-pinned [isolated-wheel acceptance runner](https://github.com/DeepAgentLabs/.github/blob/81343e3/scripts/accept_ecosystem.py)
for source pins and validation. [Organization PR 67](https://github.com/DeepAgentLabs/.github/pull/67)
introduces these artifacts; the matrix branch tracks the reviewed source pins. These internal runs do
not establish independent AIOS acceptance, production deployment safety or
exhaustive capture of behavior.

Independent acceptance, live/deployment evidence and the stable freeze remain
separate gates. See the [shared release policy](https://github.com/DeepAgentLabs/.github/blob/main/profile/RELEASE_POLICY.md).
