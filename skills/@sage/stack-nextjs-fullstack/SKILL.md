---
name: "@sage/stack-nextjs-fullstack"
description: "Integration patterns for Next.js + Tailwind CSS + Prisma + Auth.js — the seams between frameworks"
version: "1.0.0"
type: composite
layer: stack
requires:
  sage: ">=1.0.0"
  skills:
    - "@sage/web"
    - "@sage/react"
    - "@sage/nextjs"
activates-when:
  detected: [next, tailwindcss, prisma]
tags: [next,tailwindcss,prisma]
---

# @sage/stack-nextjs-fullstack

**Layer 3 — Stack Composition**

Integration patterns for the most common Next.js fullstack combination:
Next.js App Router + Tailwind CSS + Prisma ORM + Auth.js.

## Philosophy

Individual framework docs tell you how each tool works in isolation. They don't
tell you how they work TOGETHER. Where does the Prisma client go in a Next.js
project? How does Auth.js middleware interact with App Router layouts? What
happens when Tailwind's utility classes meet server components?

These integration points — the **seams** between frameworks — are where most
bugs live. Each framework team documents their own tool. Nobody documents the
gaps between tools. That's what this pack does.

## What's Included

| Type | Files | Coverage |
|------|-------|----------|
| Integration patterns | 4 | Prisma + Next.js, Auth.js + Next.js, Tailwind + Next.js, Full-stack project structure |
| Anti-patterns | 3 | Prisma client instantiation, auth in wrong layer, Tailwind in server components |
| Constitution | 1 | 5 stack integration principles |

## Prerequisites

This pack requires `@sage/web`, `@sage/react`, and `@sage/nextjs` to be
installed. It activates when the codebase-scan detects Next.js, Tailwind CSS,
and Prisma in the project dependencies.

## What This Pack Does NOT Cover

- How Prisma works (queries, migrations, schema) — that's Prisma's docs
- How Auth.js providers work (OAuth, credentials) — that's Auth.js's docs
- How Tailwind utility classes work — that's Tailwind's docs
- This pack covers the integration BETWEEN them, not each one individually
