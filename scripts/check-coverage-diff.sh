#!/bin/bash
# Coverage diff guard (P2): compare two coverage JSON results.
# Usage: check-coverage-diff.sh --base <base.json> --head <head.json>
#   JSON shape: {"summary": {"linecoverage": <number>}} (same key CI reads).
# Exit: 0 head coverage >= base coverage; 1 head lower (regression); 2 bad args.
set -e
BASE=""
HEAD=""
while [ $# -gt 0 ]; do
  case "$1" in
    --base) BASE="$2"; shift 2;;
    --head) HEAD="$2"; shift 2;;
    *) echo "usage: $0 --base <json> --head <json>" >&2; exit 2;;
  esac
done
if [ -z "$BASE" ] || [ -z "$HEAD" ]; then
  echo "usage: $0 --base <json> --head <json>" >&2
  exit 2
fi
if [ ! -f "$BASE" ] || [ ! -f "$HEAD" ]; then
  echo "missing input file" >&2
  exit 2
fi
get_cov() {
  python -c "import json,sys; print(json.load(open(sys.argv[1],encoding='utf-8'))['summary']['linecoverage'])" "$1"
}
B=$(get_cov "$BASE")
H=$(get_cov "$HEAD")
echo "base=${B}% head=${H}%"
if [ "$(awk -v b="$B" -v h="$H" 'BEGIN { print (h < b) ? 1 : 0 }')" -eq 1 ]; then
  echo "FAIL: coverage regressed ${B}% -> ${H}%"
  exit 1
fi
echo "OK: no regression"
exit 0
