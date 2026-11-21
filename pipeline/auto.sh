#!/usr/bin/env bash
# Automatikus feldolgozás: a data/bejovo/ mappába másolt fotókból vagy videóból 3D modell.
#
# Minden új adag fotó/videó kap egy saját mappát (data/modell_1, data/modell_2, …): a képek
# átkerülnek a <mappa>/images-be (a videó a <mappa>/video-ba, és belőle a legélesebb
# képkockák kerülnek az images-be), majd lefut a rekonstrukció, a Blender-tisztítás
# és az előnézet. A napló: <mappa>/run.log. Ezután a minőségellenőrző ágens (agent/qa.py, Claude)
# nevet, leírást, címkéket javasol és ítél; egy kérdés után (Feltöltsem így? / szerkesztés) publish.py → commit + push → ha a SITE be van állítva, megvárja, hogy az élő oldalon megjelenjen.
# Ez a fix sorrendű tartalék lánc; az ágens-vezérelt változat: agent/controller.py.
#
# Használat:
#   ./pipeline/auto.sh              # ami most a bejovo/-ben van, feldolgozza, majd kilép
#   ./pipeline/auto.sh --watch      # figyel, és minden új adagot feldolgoz (Ctrl+C: leállítás)
# Kapcsolók:
#   --frames 150   videóból összesen ennyi képkocka (több videónál elosztva; alap 150)
#   --size 0.28    a tárgy leghosszabb mérete méterben (alap 0.2; utólag a cleanup újrafuttatható)
#   --mask         háttér kivágása a rekonstrukció előtt (zavaros háttérnél)
#   --max 1600     max képméret (alap 2000; kisebb = gyorsabb, kevesebb VRAM)
#   --settle 15    ennyi másodpercig nem változhat a bejovo/, mielőtt hozzányúl (másolás vége)
#   --no-open      a végén ne nyissa meg az előnézeti képet
#   --no-publish   ne kérdezzen rá a feltöltésre (terminál nélkül, pl. háttérben futva, magától kimarad)
#   --no-ai        ne kérjen AI-javaslatot (agent/qa.py), mindent kézzel kérdezzen
set -euo pipefail
cd "$(dirname "$0")/.."

inbox=data/bejovo
size=0.2 frames=150 mask=0 watch=0 max=2000 settle=15 open=1 offer=1 use_ai=1
site=${SITE-https://r3dy-web.vercel.app}   # live site; SITE= (empty) skips waiting for the deploy
while (($#)); do
  case $1 in
    --watch) watch=1 ;;
    --size) size=$2; shift ;;
    --frames) frames=$2; shift ;;
    --mask) mask=1 ;;
    --max) max=$2; shift ;;
    --settle) settle=$2; shift ;;
    --no-open) open=0 ;;
    --no-publish) offer=0 ;;
    --no-ai) use_ai=0 ;;
    -h|--help) sed -n '2,/^set /p' "$0" | sed '$d; s/^# \{0,1\}//'; exit 0 ;;
    *) echo "Ismeretlen kapcsoló: $1 (súgó: --help)" >&2; exit 2 ;;
  esac
  shift
done
mkdir -p "$inbox"

images() { find "$inbox" -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' \) | sort; }
videos() { find "$inbox" -type f \( -iname '*.mp4' -o -iname '*.mov' -o -iname '*.mkv' -o -iname '*.webm' -o -iname '*.3gp' \) | sort; }
# Fingerprint of everything in the inbox (names + sizes): unchanged for $settle s = the copy is done.
snapshot() { find "$inbox" -type f -printf '%p %s\n' | sort | md5sum; }
notify() { command -v notify-send >/dev/null && notify-send "3D szkennelés" "$1" 2>/dev/null || true; }

wait_until_settled() {
  local a b
  a=$(snapshot)
  while sleep "$settle"; b=$(snapshot); [[ $a != "$b" ]]; do
    echo "… még másolódik, várok"
    a=$b
  done
}

next_dir() {
  local n=1
  while [[ -e data/modell_$n ]]; do n=$((n + 1)); done
  echo "data/modell_$n"
}

pipeline() {
  local dir=$1 count v k=0 n per
  if [[ -d $dir/video ]]; then
    n=$(find "$dir/video" -type f | wc -l)
    per=$(((frames + n - 1) / n))
    while IFS= read -r v; do
      k=$((k + 1))
      echo "== képkockák kivágása: $(basename "$v") → $per kocka"
      .venv/bin/python pipeline/extract_frames.py "$v" "$dir/images" --count "$per" --prefix "video${k}"
    done < <(find "$dir/video" -type f | sort)
  fi
  count=$(find "$dir/images" -type f | wc -l)
  echo "== $dir: $count kép  ($(date '+%F %T'))"
  ((count >= 20)) || echo "FIGYELEM: csak $count kép – 60+ ajánlott, kevésből könnyen nem áll össze."
  if ((mask)); then
    echo "== háttér kivágása"
    .venv/bin/python pipeline/mask.py "$dir/images" "$dir/masked"
  fi
  ./pipeline/reconstruct.sh "$dir" "$max"
  echo "== Blender: tisztítás (--size $size m)"
  ./blender/run.sh cleanup "$dir/model/model.obj" "$dir/model.glb" --size "$size" --blend
  echo "== előnézet"
  ./blender/run.sh preview "$dir/model.glb" "$dir/preview"
}

ask() { local a; read -rp "$1" a </dev/tty || a=; printf '%s' "$a"; }
# Editable answer, pre-filled with a suggestion (readline): Enter keeps it.
ask_edit() { local a; read -e -r -i "$2" -p "$1" a </dev/tty || a=$2; printf '%s' "$a"; }
is_yes() { [[ $1 =~ ^[iIyY] ]]; }
slug() { .venv/bin/python -c 'import sys; sys.path.insert(0, "pipeline"); from publish import slug; print(slug(sys.argv[1]))' "$1"; }

# The AI agent's suggestion (agent/qa.py → Claude). Sets ai_*; returns 1 when it is
# switched off or unreachable (the reason is in $dir/ai.err) – then everything is asked by hand.
ai_suggest() {
  local dir=$1 out f=()
  ((use_ai)) || return 1
  echo "AI-javaslat kérése (minőségellenőrző ágens, Claude)…"
  out=$(.venv/bin/python agent/qa.py "$dir" 2>"$dir/ai.err") || return 1
  mapfile -t f < <(printf '%s' "$out" | .venv/bin/python -c 'import json, sys
d = json.load(sys.stdin)
one = lambda s: " ".join(str(s).split())
for v in (d["nev"], d["leiras"], " ".join(d["cimkek"]), d["minoseg"], " | ".join(d["hibak"]), d.get("model", ""), d.get("size_cm", "")):
    print(one(v))' 2>>"$dir/ai.err")
  [[ -n ${f[0]-} ]] || return 1
  ai_name=${f[0]} ai_desc=${f[1]-} ai_tags=${f[2]-} ai_quality=${f[3]-} ai_issues=${f[4]-} ai_model=${f[5]-} ai_size=${f[6]-}
}

# After a successful run: AI suggestion (or questions), optional size fix, then publish, commit,
# push and wait for the live site.
publish_flow() {
  local dir=$1 a name="" base desc="" tags="" tagarr=() i cur=$size edit=1 label x
  echo
  if ai_suggest "$dir"; then
    case $ai_quality in jo) label="JÓ" ;; hibas) label="HIBÁS" ;; *) label="GYANÚS" ;; esac
    echo "── AI-javaslat (${ai_model:-?}) ──"
    echo "Név:      $ai_name"
    echo "Leírás:   $ai_desc"
    echo "Címkék:   $ai_tags"
    echo "Méret:    $ai_size"
    echo "Minőség:  $label"
    if [[ -n $ai_issues ]]; then
      echo "Észrevételek:"
      while IFS= read -r x; do echo "  - $x"; done <<<"${ai_issues// | /$'\n'}"
    fi
    name=$ai_name desc=$ai_desc tags=$ai_tags
    if [[ $ai_quality == hibas ]]; then
      echo "Az AI szerint a modell hibás – érdemes újrafotózni."
      a=$(ask "Feltöltsem mégis? [i/N, s = szerkesztés és feltöltés] ")
      case $a in [iIyY]*) edit=0 ;; [sS]*) edit=1 ;; *) echo "Nem töltöm fel."; return 0 ;; esac
    else
      a=$(ask "Feltöltsem így? [I/n, s = szerkesztés] ")
      case $a in [nN]*) echo "Nem töltöm fel."; return 0 ;; [sS]*) edit=1 ;; *) edit=0 ;; esac
    fi
  else
    if ((use_ai)) && [[ -s $dir/ai.err ]]; then
      echo "Az AI-javaslat most nem érhető el ($(tail -n1 "$dir/ai.err")) – kézi kitöltés."
    fi
    is_yes "$(ask "Feltöltsem a weboldalra? [i/N] ")" || {
      echo "Nem töltöm fel. Később: .venv/bin/python pipeline/publish.py $dir/model.glb --name \"Név\" --tags címke"
      return 0
    }
  fi
  if ((edit)); then
    while true; do
      a=$(ask "Méret: a leghosszabb oldal $cur m. Enter = jó, vagy új érték méterben (pl. 0.28): ")
      [[ -z $a ]] && break
      a=${a/,/.}
      if [[ $a =~ ^[0-9]*\.?[0-9]+$ ]] && [[ $a != 0 ]]; then
        echo "== Blender: tisztítás újra (--size $a m)"
        ./blender/run.sh cleanup "$dir/model/model.obj" "$dir/model.glb" --size "$a" --blend >>"$dir/run.log" 2>&1 \
          || { echo "HIBA a tisztításnál (napló: $dir/run.log)"; return 1; }
        ./blender/run.sh preview "$dir/model.glb" "$dir/preview" >>"$dir/run.log" 2>&1 || true
        cur=$a
      else
        echo "Nem szám: $a"
      fi
    done
    name=$(ask_edit "Név (ez látszik az oldalon): " "$name")
    tags=$(ask_edit "Címkék szóközzel: " "$tags")
    desc=$(ask_edit "Leírás (lehet üres): " "$desc")
  fi
  while true; do
    if [[ -z ${name// } ]]; then
      name=$(ask_edit "Név (ez látszik az oldalon, pl. Sportcipő): " "")
      continue
    fi
    base=$(slug "$name")
    [[ -e web/models/$base.glb ]] || break
    is_yes "$(ask "Már van ilyen modell az oldalon ($base.glb). Felülírjam? [i/N] ")" && break
    name=$(ask_edit "Másik név: " "$name")
  done
  read -r -a tagarr <<<"$tags"

  .venv/bin/python pipeline/publish.py "$dir/model.glb" --name "$name" --tags "${tagarr[@]}" --description "$desc" || return 1
  git add -- web/models
  git commit -q -m "Add: $name" -- web/models || { echo "HIBA: a commit nem sikerült"; return 1; }
  if ! git push -q; then
    echo "HIBA: a push nem sikerült – a commit helyben megvan, később: git push"
    return 1
  fi
  if [[ -z $site ]]; then
    echo "Feltöltve. (SITE nincs beállítva, az élesítést nem várom meg.)"
    return 0
  fi
  echo "Feltöltve, várom az élesítést…"
  for ((i = 0; i < 36; i++)); do
    if curl -fsS "$site/models/models.json" 2>/dev/null | grep -q "\"$base.glb\"" &&
       curl -fsSI -o /dev/null "$site/models/$base.glb" 2>/dev/null; then
      echo "ÉLES: $site  (modell: $site/models/$base.glb)"
      notify "Éles: $name"
      return 0
    fi
    sleep 5
  done
  echo "3 perc után még nem látszik az oldalon – nézd meg később: $site"
}

process_inbox() {
  [[ -n $(images)$(videos) ]] || return 0
  echo "Új fájlok a $inbox mappában – várok, amíg a másolás befejeződik (${settle} s nyugalom)."
  wait_until_settled

  local dir t0=$SECONDS rc
  dir=$(next_dir)
  mkdir -p "$dir/images"
  images | while IFS= read -r f; do mv -n -- "$f" "$dir/images/"; done
  if [[ -n $(videos) ]]; then
    mkdir -p "$dir/video"
    videos | while IFS= read -r f; do mv -n -- "$f" "$dir/video/"; done
  fi
  find "$inbox" -mindepth 1 -type d -empty -delete
  [[ -z $(images)$(videos) ]] || echo "FIGYELEM: néhány fájl névütközés miatt a $inbox mappában maradt."

  set +e
  (set -e; pipeline "$dir") 2>&1 | tee "$dir/run.log"
  rc=${PIPESTATUS[0]}
  set -e
  local min=$(((SECONDS - t0) / 60)) sec=$(((SECONDS - t0) % 60))
  if ((rc == 0)); then
    echo
    echo "KÉSZ: $dir/model.glb  (${min} perc ${sec} s)"
    echo "Előnézet: $dir/preview/view_0.png"
    notify "Kész: $dir (${min} perc ${sec} s)"
    if ((open)) && [[ -n ${DISPLAY:-}${WAYLAND_DISPLAY:-} ]]; then
      xdg-open "$dir/preview/view_0.png" >/dev/null 2>&1 &
    fi
    if ((offer)) && [[ -t 0 ]]; then
      publish_flow "$dir" || echo "A modell kész, csak a feltöltés maradt el: $dir/model.glb"
    else
      echo "Feltöltés:  .venv/bin/python pipeline/publish.py $dir/model.glb --name \"Név\" --tags címke"
    fi
  else
    echo
    echo "HIBA: $dir feldolgozása megállt (napló: $dir/run.log). A képek (és a videó) megmaradtak a $dir mappában;"
    echo "újrafuttatás kézzel: ./pipeline/reconstruct.sh $dir"
    notify "Hiba: $dir – lásd run.log"
  fi
  return "$rc"
}

if ((watch)); then
  echo "Figyelem a $inbox mappát (Ctrl+C: leállítás). Másold ide a fotókat vagy a videót."
  while true; do
    process_inbox || true
    sleep 5
  done
else
  if [[ -z $(images)$(videos) ]]; then
    echo "Nincs kép vagy videó a $inbox mappában. Másold ide őket (vagy indítsd --watch kapcsolóval)."
    exit 1
  fi
  process_inbox
fi
