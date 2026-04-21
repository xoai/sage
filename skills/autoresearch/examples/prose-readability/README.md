# Example: Prose Readability Improvement

## Setup

1. Have markdown documentation in `docs/` and/or `README.md`
2. Copy `brief.md` and `autoresearch.sh` to `.sage/work/YYYYMMDD-readability/`
3. The verify script uses a Python approximation of Flesch-Kincaid — no pip install needed

## Run

```
/autoresearch
```

## What the agent will try

Typical winning patterns for readability improvement:
- Shorten sentences (aim for 15-20 words)
- Replace jargon with plain language
- Break long paragraphs into shorter ones
- Use active voice instead of passive
- Replace abstract nouns with concrete verbs
- Add transition words between ideas

## Notes

- The frozen scope protects API docs and CHANGELOG from being simplified
- Grade level 8 means readable by a 14-year-old — this is the standard for technical docs
- The metric is Flesch-Kincaid grade level (lower = simpler)
- Budget is short (30s) since there's no build step — just text analysis
