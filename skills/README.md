# Sage Skills

All installable capabilities for Sage. A **skill** is any bundle of knowledge,
process, or judgment that makes the AI agent better at a specific job.

## Namespaces

| Namespace | Meaning |
|-----------|---------|
| `@sage/` | Official skills maintained by the Sage team |
| `@community/` | Community-contributed skills (verified) |
| `@custom/` | User's own private skills |

## Skill Types

| Type | What It Does | Examples |
|------|-------------|---------|
| `knowledge` | Technology-specific patterns and judgment | react, nextjs, web |
| `process` | Methodology with steps and references | jtbd, prd, ux-writing |
| `composite` | Composes multiple knowledge skills for a stack | stack-nextjs-supabase |
| `bundle` | Metapackage that installs related skills | product-management, ux-design |

## Official Skills

### Knowledge Skills (Technology)

| Skill | Layer | Description |
|-------|-------|-------------|
| [@sage/web](@sage/web/) | domain | Accessibility, performance, security, SEO |
| [@sage/api](@sage/api/) | domain | REST/GraphQL patterns, error handling |
| [@sage/mobile](@sage/mobile/) | domain | Mobile UX, offline-first, gestures |
| [@sage/baas](@sage/baas/) | domain | Backend-as-a-Service patterns |
| [@sage/react](@sage/react/) | framework | React 18/19 patterns, hooks, state |
| [@sage/nextjs](@sage/nextjs/) | framework | Next.js App Router, RSC, data fetching |
| [@sage/flutter](@sage/flutter/) | framework | Flutter/Dart widget patterns |
| [@sage/react-native](@sage/react-native/) | framework | React Native mobile patterns |

### Composite Skills (Stacks)

| Skill | Composes | Description |
|-------|----------|-------------|
| [@sage/stack-nextjs-supabase](@sage/stack-nextjs-supabase/) | web + react + nextjs + baas | Full-stack Next.js + Supabase |
| [@sage/stack-nextjs-fullstack](@sage/stack-nextjs-fullstack/) | web + react + nextjs + api | Full-stack Next.js |
| [@sage/stack-flutter-firebase](@sage/stack-flutter-firebase/) | mobile + flutter + baas | Flutter + Firebase |
| [@sage/stack-react-native-expo](@sage/stack-react-native-expo/) | mobile + react-native | React Native + Expo |

### Process Skills (Methodology)

| Skill | Discipline | Description |
|-------|-----------|-------------|
| [@sage/jtbd](@sage/jtbd/) | PM | Jobs-to-be-Done analysis |
| [@sage/opportunity-map](@sage/opportunity-map/) | PM | Opportunity prioritization |
| [@sage/user-interview](@sage/user-interview/) | PM | Research design |
| [@sage/prd](@sage/prd/) | PM | JTBD-grounded PRD |
| [@sage/ux-audit](@sage/ux-audit/) | UX | Design audit |
| [@sage/ux-research](@sage/ux-research/) | UX | Category benchmarking |
| [@sage/ux-evaluate](@sage/ux-evaluate/) | UX | Design evaluation |
| [@sage/ux-brief](@sage/ux-brief/) | UX | Design brief |
| [@sage/ux-discovery](@sage/ux-discovery/) | UX | User context discovery |
| [@sage/ux-specify](@sage/ux-specify/) | UX | UX specification |
| [@sage/ux-plan-tasks](@sage/ux-plan-tasks/) | UX | UX task planning |
| [@sage/ux-heuristic-review](@sage/ux-heuristic-review/) | UX | Heuristic evaluation |
| [@sage/ux-writing](@sage/ux-writing/) | UX | Voice & tone, microcopy |

### Bundle Skills (Metapackages)

| Bundle | Installs | Description |
|--------|----------|-------------|
| [@sage/product-management](@sage/product-management/) | jtbd + opportunity-map + user-interview + prd | Full PM chain |
| [@sage/ux-design](@sage/ux-design/) | 9 UX skills | Full UX chain |
| [@sage/skill-builder](@sage/skill-builder/) | 5 builder skills | Skill authoring |

## Compatibility

Skills follow a progressive enhancement model:

- **Layer 0:** Any folder with a SKILL.md works (community Claude Code skills)
- **Layer 1:** Add type/version frontmatter for smarter integration
- **Layer 2:** Full Sage manifest with relationships and dependencies
