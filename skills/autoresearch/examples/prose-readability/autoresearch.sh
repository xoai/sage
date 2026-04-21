#!/bin/bash
set -e

# Calculate Flesch-Kincaid grade level for all markdown files in scope
# Requires: pip install textstat (or use the Python stdlib approximation below)

TOTAL_WORDS=0
TOTAL_SENTENCES=0
TOTAL_SYLLABLES=0

for f in docs/*.md README.md; do
  [ -f "$f" ] || continue
  # Count words, sentences, syllables using Python
  python3 -c "
import re, sys
text = open('$f').read()
words = re.findall(r'\b[a-zA-Z]+\b', text)
sentences = max(1, len(re.findall(r'[.!?]+', text)))
# Approximate syllable count
def syllables(w):
    w = w.lower()
    count = len(re.findall(r'[aeiouy]+', w))
    return max(1, count)
total_syl = sum(syllables(w) for w in words)
print(f'{len(words)} {sentences} {total_syl}')
" 2>/dev/null
done | awk '{w+=$1; s+=$2; y+=$3} END {
  if (w > 0 && s > 0) {
    fk = 0.39 * (w/s) + 11.8 * (y/w) - 15.59
    printf "METRIC grade_level=%.1f\n", fk
  } else {
    print "METRIC grade_level=0"
  }
}'
