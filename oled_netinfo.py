#!/usr/bin/env python3

# Copyright (C) Yuriy Bogdanov.  2025.  All Rights Reserved.

# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:

# The above copyright notice and this permission notice (including the
# next paragraph) shall be included in all copies or substantial
# portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE COPYRIGHT OWNER(S) AND/OR ITS SUPPLIERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

#  *******************************************************************  #/
#                                                                       #/
#    * Authors:                                                         #/
#        - Yuriy Bogdanov <git@ioi.sh>                                  #/
#                                                                       #/
#  *******************************************************************  #/


import os
import socket
import fcntl
import struct
import time
import signal
import sys
import yaml

from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import ImageFont

class OLEDNetInfo:
    def load_config(self, path):
        with open(path, "r") as f:
            return yaml.safe_load(f)

    def __init__(self, config_path):
        self.running = True
        self.config = self.load_config(config_path)

        self.exclude_prefixes = tuple(self.config["network"]["exclude_prefixes"])
        self.update_interval = self.config.get("update_interval", 0.2)
        self.pages = [p["name"] for p in self.config["pages"]]
        self.page_interval = self.config["page_rotation"]["interval"]
        self.current_page = 0
        self.last_page_switch = time.time()

        self._setup_signal_handlers()
        self._setup_display()
        self._load_fonts()

    # ---------------- Signal Handling ----------------
    def _setup_signal_handlers(self):
        signal.signal(signal.SIGTERM, self._stop)
        signal.signal(signal.SIGINT, self._stop)

    def _stop(self, *_):
        self.running = False

    # ---------------- Display Setup ----------------
    def _setup_display(self):
        i2c_cfg = self.config["i2c"]
        serial = i2c(port=i2c_cfg["port"], address=i2c_cfg["address"])
        self.device = ssd1306(
            serial,
            width=i2c_cfg["width"],
            height=i2c_cfg["height"]
        )

    def _load_fonts(self):
        fonts_cfg = self.config["fonts"]
        self.font_title = ImageFont.truetype(
            fonts_cfg["title"]["path"], fonts_cfg["title"]["size"]
        )
        self.font_body = ImageFont.truetype(
            fonts_cfg["body"]["path"], fonts_cfg["body"]["size"]
        )

    # ---------------- Helpers ----------------
    def _valid_iface(self, iface):
        return not iface.startswith(self.exclude_prefixes)

    def _is_up(self, iface):
        try:
            with open(f"/sys/class/net/{iface}/operstate") as f:
                return f.read().strip() == "up"
        except OSError:
            return False

    def _get_ip(self, iface):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            return socket.inet_ntoa(
                fcntl.ioctl(
                    s.fileno(),
                    0x8915,
                    struct.pack("256s", iface[:15].encode())
                )[20:24]
            )
        except OSError:
            return None

    def _get_speed(self, iface):
        try:
            with open(f"/sys/class/net/{iface}/speed") as f:
                return f.read().strip()
        except (OSError, ValueError):
            return "?"

    def _get_mac(self, iface):
        try:
            with open(f"/sys/class/net/{iface}/address") as f:
                return f.read().strip()
        except OSError:
            return None

    def get_active_interface(self):
        for iface in os.listdir("/sys/class/net"):
            if not self._valid_iface(iface):
                continue
            if not self._is_up(iface):
                continue

            ip = self._get_ip(iface)
            if ip:
                return iface, ip
        return None, None

    def _text_size(self, text, font):
        bbox = font.getbbox(text)
        # text_width = bbox[2] - bbox[0]
        # return max((self.device.width - text_width) // 2, 0)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    def _text_position (
            self,
            line1,
            line2,
            ft,
            fb
        ):
        w1, h1 = self._text_size(line1, ft)
        w2, h2 = self._text_size(line2, fb)

        # Predifined first line on the display
        y1 = 2

        x1 = (self.device.width - w1) // 2
        x2 = (self.device.width - w2) // 2
        y2 =  y1 + h1 + 6

        return x1, y1, x2, y2

    # ---------------- Page Draw Functions ----------------
    def draw_net_page(self, iface, ip):
        x1, y1, x2, y2 = self._text_position(iface, ip, ft=self.font_title, fb=self.font_body)
        with canvas(self.device) as draw:
            draw.text((x1, y1), iface, fill=255, font=self.font_title)
            draw.text((x2, y2), ip,fill=255, font=self.font_body)

    def draw_speed_page(self, iface):
        speed = self._get_speed(iface)
        x1, y1, x2, y2 = self._text_position("Link Speed", f"{speed} Mbps", ft=self.font_title, fb=self.font_body)
        with canvas(self.device) as draw:
            draw.text((x1, y1), "Link Speed", fill=255, font=self.font_title)
            draw.text((x2, y2), f"{speed} Mbps" ,fill=255, font=self.font_body)

    def draw_mac_page(self, iface):
        mac = self._get_mac(iface) or "-"
        x1, y1, x2, y2 = self._text_position("MAC Address", mac.upper(), ft=self.font_title, fb=self.font_body)
        with canvas(self.device) as draw:
            draw.text((x1, y1), "MAC Address", fill=255, font=self.font_title)
            draw.text((x2, y2), mac.upper() ,fill=255, font=self.font_body)

    # ---------------- Page Rotation ----------------
    def _rotate_page(self):
        now = time.time()
        if now - self.last_page_switch >= self.page_interval:
            self.current_page = (self.current_page + 1) % len(self.pages)
            self.last_page_switch = now

    # ---------------- Main Loop ----------------
    def run(self):
        while self.running:
            iface, ip = self.get_active_interface()

            if iface:
                page = self.pages[self.current_page]
                if page == "net":
                    self.draw_net_page(iface, ip)
                elif page == "speed":
                    self.draw_speed_page(iface)
                elif page == "mac":
                    self.draw_mac_page(iface)
            else:
                with canvas(self.device) as draw:
                    x1, y1, x2, y2 = self._text_position("NO NETWORK", "...", ft=self.font_title, fb=self.font_body)
                    draw.text((x1, y1 + 10), "NO NETWORK", fill=255, font=self.font_title)

            self._rotate_page()
            time.sleep(self.update_interval)

        self.device.clear()

# ---------------- ENTRY POINT ----------------
def main():
    if len(sys.argv) != 2:
        print("Usage: oled_netinfo.py /path/to/config.yaml")
        sys.exit(1)

    app = OLEDNetInfo(sys.argv[1])
    app.run()

if __name__ == "__main__":
    main()
