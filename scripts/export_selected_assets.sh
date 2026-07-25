#!/usr/bin/env bash
set -u

if [[ $# -ne 2 ]]; then
  echo "usage: $0 DATA_STAGING REPOSITORY" >&2
  exit 2
fi

staging=$1
repository=$2
raw_root="$staging/raw/assets"
public_root="$staging/public/assets"
work_root="$staging/public/.export-work"
log_root="$staging/public/export-logs"

mkdir -p "$public_root" "$work_root" "$log_root"

summary="$log_root/export-summary.tsv"
if [[ ! -f "$summary" ]]; then
  printf 'asset_id\tstatus\ttrace_status\twork_path\n' > "$summary"
fi

for source in "$raw_root"/*; do
  [[ -d "$source" ]] || continue
  asset=${source##*/}
  destination="$public_root/$asset"

  # This operator-history asset has already been transformed into the audited
  # content-addressed representation and is intentionally not duplicated here.
  if [[ "$asset" == "reference-frank-operator-history-20260722" ]]; then
    continue
  fi
  if [[ -d "$destination" ]]; then
    continue
  fi

  work=$(mktemp -d "$work_root/${asset}.XXXXXX")
  log="$log_root/${asset}.log"
  trace_status=complete

  if [[ "$asset" == "v2-2026101202-137751696b87" ]]; then
    python3 "$repository/scripts/redact_export.py" "$source" "$work" \
      --omit-glob 'data-v2/v2.*.tmp' \
      --omit-glob 'snapshots/**' \
      --omit-glob 'ctf-originals/**' > "$log" 2>&1
  else
    python3 "$repository/scripts/redact_export.py" "$source" "$work" \
      --omit-glob 'data-v2/v2.*.tmp' \
      --omit-glob 'snapshots/**' \
      --omit-glob 'ctf-originals/**' \
      --omit-glob 'data-v2/tasks/**' > "$log" 2>&1
  fi
  if [[ $? -ne 0 ]]; then
    printf '%s\tredaction_failed\tnot_run\t%s\n' "$asset" "$work" >> "$summary"
    continue
  fi

  python3 "$repository/scripts/audit_trace_completeness.py" "$work" \
    --output "$work/TRACE_COMPLETENESS.json" >> "$log" 2>&1
  if [[ $? -ne 0 ]]; then
    trace_status=partial
    python3 "$repository/scripts/audit_trace_completeness.py" "$work" \
      --allow-partial --output "$work/TRACE_COMPLETENESS.json" >> "$log" 2>&1
    if [[ $? -ne 0 ]]; then
      printf '%s\ttrace_failed\tunreadable\t%s\n' "$asset" "$work" >> "$summary"
      continue
    fi
  fi

  python3 "$repository/scripts/build_public_manifest.py" "$work" >> "$log" 2>&1 || {
    printf '%s\tmanifest_build_failed\t%s\t%s\n' "$asset" "$trace_status" "$work" >> "$summary"
    continue
  }
  python3 "$repository/scripts/scan_secrets.py" "$work" >> "$log" 2>&1 || {
    printf '%s\tsecret_scan_failed\t%s\t%s\n' "$asset" "$trace_status" "$work" >> "$summary"
    continue
  }
  python3 "$repository/scripts/verify_manifest.py" "$work/PUBLIC_MANIFEST.json" \
    --root "$work" --reject-extra >> "$log" 2>&1 || {
    printf '%s\tmanifest_verify_failed\t%s\t%s\n' "$asset" "$trace_status" "$work" >> "$summary"
    continue
  }

  mv "$work" "$destination"
  printf '%s\tcomplete\t%s\t-\n' "$asset" "$trace_status" >> "$summary"
done

