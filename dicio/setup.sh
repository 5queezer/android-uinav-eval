#!/bin/bash
# Build the `dicio` emulator snapshot from uinav-home-apps: install every Dicio APK of variants.json
# (all permissions granted), seed three contacts, launch each Dicio once, save.
cd "$(dirname "$0")/.." || exit 1
A() { adb -s emulator-5560 shell "$@" < /dev/null; }
for i in 1 2 3; do  # the console may not accept connections right after boot
  timeout 90 adb -s emulator-5560 emu avd snapshot load uinav-home-apps | grep -q OK && break
  [ $i = 3 ] && exit 1; sleep 10
done
until [ "$(A getprop sys.boot_completed | tr -d '\r')" = 1 ]; do sleep 1; done
for apk in $(python3 -c "import json; print(' '.join(sorted({v['apk'] for v in json.load(open('dicio/variants.json')).values()})))"); do
  adb -s emulator-5560 install -r -g "$apk" | tail -1
done
contact() {  # $1 name, $2 number
  A content insert --uri content://com.android.contacts/raw_contacts --bind account_type:n: --bind account_name:n:
  id=$(A content query --uri content://com.android.contacts/raw_contacts --projection _id | tail -1 | sed 's/.*_id=//')
  A "content insert --uri content://com.android.contacts/data --bind raw_contact_id:i:$id \
    --bind mimetype:s:vnd.android.cursor.item/name --bind 'data1:s:$1'"
  A "content insert --uri content://com.android.contacts/data --bind raw_contact_id:i:$id \
    --bind mimetype:s:vnd.android.cursor.item/phone_v2 --bind 'data1:s:$2' --bind data2:i:2"
}
contact "Anna Berger" "+43 660 1234567"
contact "Tom Müller" "+43 664 7654321"
contact "Mama" "+43 650 1112223"
A content query --uri content://com.android.contacts/data/phones --projection display_name:data1
for pkg in $(python3 -c "import json; print(' '.join(sorted({v['package'] for v in json.load(open('dicio/variants.json')).values()})))"); do
  A am start -n $pkg/org.stypox.dicio.MainActivity > /dev/null; sleep 6; A am force-stop $pkg
done
for pkg in com.google.android.youtube com.google.android.apps.maps com.android.chrome com.google.android.calendar \
           com.google.android.apps.messaging com.google.android.contacts com.google.android.dialer; do
  A pm grant $pkg android.permission.POST_NOTIFICATIONS 2>/dev/null  # no permission dialog on top of the app
done
A input keyevent KEYCODE_HOME
timeout 120 adb -s emulator-5560 emu avd snapshot save dicio | grep -q OK || exit 1
# a snapshot saved at a bad moment loads with adb staying offline: check it once
timeout 90 adb -s emulator-5560 emu avd snapshot load dicio | grep -q OK || exit 1
for i in $(seq 1 30); do [ "$(timeout 5 adb -s emulator-5560 shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = 1 ] && exit 0; sleep 1; done
echo "the saved dicio snapshot does not come back"; exit 1
