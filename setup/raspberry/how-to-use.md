### required edits

If you need wifi access, make sure to edit `wpa_supplicant.conf` with your network details.

### where to put these files
Use these files when you flash an SD card for Raspberry Pi.

You should have two partitions mounted.

Use the boot partition. Drop into the root of that partition with all the other files.

The `ls` before you add the files looks like:

~~~
bcm2708-rpi-0-w.dtb       bcm2710-rpi-cm3.dtb  fixup_db.dat      overlays
bcm2708-rpi-b.dtb         bootcode.bin         fixup_x.dat       start_cd.elf
bcm2708-rpi-b-plus.dtb    cmdline.txt          issue.txt         start_db.elf
bcm2708-rpi-cm.dtb        config.txt           kernel7.img       start.elf
bcm2709-rpi-2-b.dtb       COPYING.linux        kernel.img        start_x.elf
bcm2710-rpi-3-b.dtb       fixup_cd.dat         LICENCE.broadcom
bcm2710-rpi-3-b-plus.dtb  fixup.dat            LICENSE.oracle

~~~
