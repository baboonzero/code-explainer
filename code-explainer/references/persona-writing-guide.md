# Persona Writing Guide

Target audiences:

1. PMs and designers.
2. Junior engineers.
3. Senior engineers doing fast onboarding.

## Tone and Structure

1. Explain purpose first, implementation second.
2. Use plain language, then link to deeper details.
3. Avoid unexplained acronyms.
4. Keep overview sections concise and actionable.
5. Tie every important explanation back to a real module, file, flow step, or doc.
6. Prefer concrete nouns from the repository over generic phrases like "service layer" or "core module".

## Overview Requirements

Must answer quickly:

1. What is this system?
2. Who uses it?
3. What are the core building blocks?
4. Where should each audience start?
5. What is uncertain or weakly supported?

## Deep Explainer Requirements

1. Architecture deep dive with context/container framing.
2. Module map with responsibilities and change-entry hints.
3. Request and data flows with sequence/flowcharts.
4. Dependency inventory and risk callouts.
5. Glossary for terms and internal jargon.

## Audience Focus Notes

- PM/Designer:
  - Prioritize user journeys and product surface mapping.
- Junior Engineer:
  - Prioritize entrypoints, layers, and safe first-change areas.
- Senior Engineer:
  - Prioritize dependency boundaries, critical paths, and trust boundaries.
