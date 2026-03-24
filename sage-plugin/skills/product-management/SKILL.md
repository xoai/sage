---
name: "product-management"
description: "Product management process — JTBD analysis, opportunity mapping, user interview design, and PRD writing. Discovery → Planning → Delivery."
version: "1.1.0"
type: bundle
includes:
  - "jtbd"
  - "opportunity-map"
  - "user-interview"
  - "prd"
requires:
  sage: ">=1.0.0"
tags: [product-management, jtbd, prd, discovery, planning]
sources:
  - "Jobs to be Done — Anthony Ulwick"
  - "The Jobs to be Done Playbook — Jim Kalbach"
  - "INSPIRED — Marty Cagan"
  - "Continuous Discovery Habits — Teresa Torres"
---

# Product Management

Installs 4 skills spanning the PM lifecycle:

## Discovery Phase
- **jtbd** — Jobs-to-be-Done analysis (job performer, job map, desired outcomes, opportunity scoring)
- **opportunity-map** — Prioritize and sequence opportunities (pursue/monitor/defer)

## Planning Phase
- **user-interview** — Design research packages (switch interviews, validation studies)
- **prd** — JTBD-grounded PRD (job stories, MoSCoW, Given/When/Then, inline ⚠️ markers)

## Workflow
JTBD → Opportunity Map → User Interview (validation) → PRD (specification)

Each skill works independently. Install the bundle for the full chain,
or install individual skills for specific capabilities.
