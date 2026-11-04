# Contributing a recipe

Fork DeepAgentLabs/agentic-chaos, and create a branch. Run
`agentic-chaos hub push recipe.yaml /path/to/your/checkout` to validate without
importing targets and stage `hub/recipes/NAME.json`. JSON is a YAML subset;
contributions use JSON so downloads work without the optional YAML extra.
Add its name and description to `hub/index.json`, include an offline test and
open a pull request. CI validates the catalog and experiments. Maintainers
review executable target paths, bounds and fault claims before merging.
Never include secrets, provider credentials or production endpoints.

Core bundled recipes also live in `src/agentic_chaos/hub/recipes`; update both
copies when changing one. Community-only registry entries need not be bundled.
Consumers pin the reviewed merge commit SHA. A commit pin fixes content; it
is not a trust endorsement. Pull never executes or imports the recipe.
