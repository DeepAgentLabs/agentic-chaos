# Troubleshooting

Check the failing boundary before changing application behavior.

- No fault outside the CLI/session: the wrapper is a pass-through outside an active chaos context.
- Fault report exists but application succeeds: verify whether a fallback actually met the task requirement.
- Missing optional integration: install only the relevant extra for that workflow.

## Verify your environment

Run commands from the environment where you installed the package. Confirm the input file exists and matches the expected artifact contract. Keep the original evidence when diagnosing a failure.
