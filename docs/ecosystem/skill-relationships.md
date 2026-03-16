# Skill Relationships

Skills relate to each other in three ways. All relationships are optional.
The default behavior is peaceful coexistence.

## complements (default behavior)

"I cover different concerns for the same area."

```yaml
complements:
  - "@sage/react"
```

Both skills are active simultaneously. No conflict expected.
If accidental overlap occurs, the skill declared later in config wins.

**Example:** `@sage/react-testing` complements `@sage/react`. One teaches
component patterns, the other teaches testing patterns. No conflict.

## extends

"I'm a stricter or modified version. I override specific patterns."

```yaml
extends: "@sage/react"
```

The extending skill overrides patterns it declares. The base skill provides
everything else. At most ONE skill can extend a given base.

**Example:** `@community/react-strict` extends `@sage/react`. It enforces
stricter rules on state management while inheriting all other React patterns.

## replaces

"I'm a complete alternative. Deactivate the other skill."

```yaml
replaces: "@sage/jtbd"
```

The original skill is deactivated entirely. Only one can be active.
User is warned at install time.

**Example:** `@community/jtbd-kalbach` replaces `@sage/jtbd`. They use
incompatible methodologies — running both would produce confused output.

## No Declaration = Peaceful Coexistence

When a skill declares no relationships (including all external community
skills), it coexists with everything. The agent receives all active skills'
content and synthesizes. This is the safe default.
