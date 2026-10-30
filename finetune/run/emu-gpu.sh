#!/bin/bash
# (Re)start the uinav-test emulator without a window (Mesa llvmpipe, no focus stealing) and wait for boot.
S=$(cd "$(dirname "$0")" && pwd)
EMU='qemu-system-x86.*(-avd uinav-test .*-port 5560|-port 5560 .*-avd uinav-test)( |$)'  # only this AVD, not other emulators
for p in $(pgrep -f "$EMU"); do kill "$p"; done; sleep 5
for p in $(pgrep -f "$EMU"); do kill -9 "$p"; done; sleep 2
DISPLAY=:0 XAUTHORITY=$(ls /run/user/1000/xauth_* | head -1) \
  setsid ~/Android/Sdk/emulator/emulator -avd uinav-test -no-audio -no-boot-anim -gpu host -port 5560 \
  -snapshot uinav-home-apps -no-snapshot-save >> "$S/emulator-headless.log" 2>&1 < /dev/null &
for i in $(seq 1 90); do
  [ "$(timeout 5 adb -s emulator-5560 shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = 1 ] && { echo "[emu] up after $((i*2))s"; exit 0; }
  sleep 2
done
echo "[emu] did not come up"; exit 1
