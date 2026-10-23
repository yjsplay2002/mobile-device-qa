#!/usr/bin/env bash
# adb helper for Android device QA. Works from Git Bash on Windows too.
#   export ADB_SERIAL=<serial>  ADB_PKG=<package>
#   ./android.sh shot out.png | tap X Y | swipe X1 Y1 X2 Y2 [ms] | text 'abc' | back-key
#                | install app.apk | launch | stop | log-start | log-stop out.txt
#                | ue 'console command' | wifi on|off | airplane on|off | info
set -euo pipefail
export MSYS_NO_PATHCONV=1   # keep /sdcard/... from being rewritten into a Windows path
S=${ADB_SERIAL:?set ADB_SERIAL}
PKG=${ADB_PKG:-}
A() { adb -s "$S" "$@"; }

case "${1:-}" in
  info)    A shell getprop ro.product.model; A shell getprop ro.build.version.release
           A shell wm size; A shell getprop gsm.sim.state; A shell df -h /data | tail -1 ;;
  shot)    A exec-out screencap -p > "$2" ;;
  tap)     A shell input tap "$2" "$3" ;;
  swipe)   A shell input swipe "$2" "$3" "$4" "$5" "${6:-300}" ;;
  text)    A shell input text "$2" ;;
  back-key) A shell input keyevent KEYCODE_BACK ;;   # may close the app; prefer the in-app back button
  install) A install -r "$2" ;;
  launch)  A shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 >/dev/null ;;
  stop)    A shell am force-stop "$PKG" ;;
  log-start) A logcat -c; (A logcat -v time > /tmp/adb_logcat.txt &) ;;
  log-stop)  pkill -f "adb -s $S logcat" || true; cp /tmp/adb_logcat.txt "$2" ;;
  ue)      A shell "am broadcast -a android.intent.action.RUN -e cmd '$2'" ;;   # UE non-Shipping console cmd
  wifi)    A shell svc wifi "$([ "$2" = on ] && echo enable || echo disable)" ;;
  airplane) A shell cmd connectivity airplane-mode "$([ "$2" = on ] && echo enable || echo disable)" ;;
  *) sed -n '2,8p' "$0"; exit 1 ;;
esac
