# Sage Skills

All installable capabilities for Sage. A **skill** is any bundle of knowledge,
process, or judgment that makes the AI agent better at a specific job.

## Namespaces

| Namespace | Meaning |
|-----------|---------|
| `` | Official skills maintained by the Sage team |
| `` | Community-contributed skills (verified) |
| `` | User's own private skills |

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
| [web](web/) | domain | Accessibility, performance, security, SEO |
| [api](api/) | domain | REST/GraphQL patterns, error handling |
| [mobile](mobile/) | domain | Mobile UX, offline-first, gestures |
| [baas](baas/) | domain | Backend-as-a-Service patterns |
| [react](react/) | framework | React 18/19 patterns, hooks, state |
| [nextjs](nextjs/) | framework | Next.js App Router, RSC, data fetching |
| [flutter](flutter/) | framework | Flutter/Dart widget patterns |
| [react-native](react-native/) | framework | React Native mobile patterns |

### Composite Skills (Stacks)

| Skill | Composes | Description |
|-------|----------|-------------|
| [stack-nextjs-supabase](stack-nextjs-supabase/) | web + react + nextjs + baas | Full-stack Next.js + Supabase |
| [stack-nextjs-fullstack](stack-nextjs-fullstack/) | web + react + nextjs + api | Full-stack Next.js |
| [stack-flutter-firebase](stack-flutter-firebase/) | mobile + flutter + baas | Flutter + Firebase |
| [stack-react-native-expo](stack-react-native-expo/) | mobile + react-native | React Native + Expo |

### Process Skills (Methodology)

| Skill | Discipline | Description |
|-------|-----------|-------------|
| [jtbd](jtbd/) | PM | Jobs-to-be-Done analysis |
| [opportunity-map](opportunity-map/) | PM | Opportunity prioritization |
| [user-interview](user-interview/) | PM | Research design |
| [prd](prd/) | PM | JTBD-grounded PRD |
| [ux-audit](ux-audit/) | UX | Design audit |
| [ux-research](ux-research/) | UX | Category benchmarking |
| [ux-evaluate](ux-evaluate/) | UX | Design evaluation |
| [ux-brief](ux-brief/) | UX | Design brief |
| [ux-discovery](ux-discovery/) | UX | User context discovery |
| [ux-specify](ux-specify/) | UX | UX specification |
| [ux-plan-tasks](ux-plan-tasks/) | UX | UX task planning |
| [ux-heuristic-review](ux-heuristic-review/) | UX | Heuristic evaluation |
| [ux-writing](ux-writing/) | UX | Voice & tone, microcopy |

### Bundle Skills (Metapackages)

| Bundle | Installs | Description |
|--------|----------|-------------|
| [product-management](product-management/) | jtbd + opportunity-map + user-interview + prd | Full PM chain |
| [ux-design](ux-design/) | 9 UX skills | Full UX chain |
| [skill-builder](skill-builder/) | 5 builder skills | Skill authoring |

## Compatibility

Skills follow a progressive enhancement model:

- **Layer 0:** Any folder with a SKILL.md works (community Claude Code skills)
- **Layer 1:** Add type/version frontmatter for smarter integration
- **Layer 2:** Full Sage manifest with relationships and dependencies
