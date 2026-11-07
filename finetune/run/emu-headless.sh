#!/bin/bash
# (Re)start the uinav-test emulator without a window (Mesa llvmpipe, no focus stealing) and wait for boot.
S=$(cd "$(dirname "$0")" && pwd)
EMU='qemu-system-x86.*(-avd uinav-test .*-port 5560|-port 5560 .*-avd uinav-test)( |$)'  # only this AVD, not other emulators
for p in $(pgrep -f "$EMU"); do kill "$p"; done; sleep 5
for p in $(pgrep -f "$EMU"); do kill -9 "$p"; done; sleep 2
for try in 1 2; do  # a start now and then segfaults; one retry
  rm -f ~/.android/avd/uinav-test.avd/*.lock  # left behind by a killed emulator; nothing runs this AVD now
  # the emulator takes 1-2.1 GiB of VRAM even with llvmpipe (measured): lease it on the shared GPU (lessor), so leased
  # training jobs are not pushed into OOM; hold execs the emulator, so the lease lasts as long as it runs
  __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe \
    setsid lessor hold gpu0 --need vram=2300M --priority background --wait 600 -- ~/Android/Sdk/emulator/emulator -avd uinav-test -no-window -no-audio -no-boot-anim -gpu host -port 5560 \
    -snapshot uinav-home-apps -no-snapshot-save >> "$S/emulator-headless.log" 2>&1 < /dev/null &
  for i in $(seq 1 400); do  # up to ~13 min: the VRAM lease may have to wait (--wait 600)
    [ "$(timeout 5 adb -s emulator-5560 shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = 1 ] && { echo "[emu] up after $((i*2))s"; exit 0; }
    [ $i -gt 5 ] && ! pgrep -f "$EMU" > /dev/null && ! pgrep -f "^lessor hold gpu0 .*-avd uinav-test" > /dev/null \
      && break  # it died (after the launcher's start-up; a hold still waiting for its VRAM is alive): retry
    sleep 2
  done
  for p in $(pgrep -f "$EMU"); do kill -9 "$p"; done; sleep 2
done
echo "[emu] did not come up"; exit 1
