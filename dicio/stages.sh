#!/bin/bash
# The fixes one by one (cumulative builds in dicio/apk: s1 = translation fix, s2 = + temperature 0.2,
# s5 = + new tools, settings and the review fixes, s6 = + stricter translation/open routing and the date in the
# prompt): per stage, rebuild the snapshot with that branch build, then the text fallback (only in TEXT_STAGES, the
# stages that change it) and the LLM fallback with each model in MODELS -> results-dicio-<stage>.
cd "$(dirname "$0")/.." || exit 1
setup() {  # the snapshot with the current dicio/apk/branch.apk; the emulator crashes now and then
  for i in 1 2 3 4 5; do  # a fresh emulator crashes less when it gets a few seconds before the setup
    finetune/run/emu-headless.sh > /dev/null; sleep 15
    dicio/setup.sh >> dicio/setup.log 2>&1 && return 0
    echo "[stages] $(date +%T) setup failed (attempt $i)"
  done
  return 1
}
for st in ${STAGES:-s1 s2 s5 s6}; do
  echo "[stages] $(date +%T) $st"
  cp "dicio/apk/$st.apk" dicio/apk/branch.apk && setup || exit 1
  if [[ " ${TEXT_STAGES:-s1 s6} " == *" $st "* ]]; then
    dicio/run.sh --variant branch-text --out "results-dicio-$st" || exit 1
  fi
  OUT="results-dicio-$st" dicio/models.sh || exit 1
done
cp dicio/apk/r0.apk dicio/apk/branch.apk && setup
echo "[stages] $(date +%T) done"
