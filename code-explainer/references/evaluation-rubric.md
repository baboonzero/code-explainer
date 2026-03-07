# Explanation Quality Rubric

`code-explainer` should fail if the output is generic, vague, or unsupported.

## Required qualities

1. Clarity: the overview should use short, direct sentences and avoid placeholder language.
2. Specificity: the output should name real modules, entrypoints, and flow steps from the repository.
3. Grounding: the explainer should cite concrete files or docs as evidence.
4. Usefulness: the overview should tell a new reader where to start and where change risk lives.
5. Diagram usefulness: diagrams should answer clear onboarding questions, not just mirror folder names.
6. Honesty: caveats should be explicit when entrypoints, docs, or dependency edges are weak.

## Passing bar

- Overall explanation quality score must be `>= 80`.
- No individual dimension may be below `60`.
- The self-audit fixture runs must both pass quality gates.

## Failure examples

- Output says "service layer" or "core module" without tying that phrase to real files.
- Diagrams are generic chains that could fit almost any repository.
- The overview never tells the reader where to start.
- The explainer sounds confident even though no docs or entrypoints were found.
