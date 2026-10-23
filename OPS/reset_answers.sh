#!/usr/bin/env bash
# Delete every stored answer (with its claims, evidence links and citations) so a rehearsal starts clean.
# The documents are kept. Benchmark results (files) are not touched.
set -euo pipefail
docker exec truthguard-db psql -U truthguard -d truthguard -q -c "TRUNCATE answers CASCADE"
echo "All stored answers deleted. Documents kept: $(docker exec truthguard-db psql -U truthguard -d truthguard -tA -c 'select count(*) from documents')"
