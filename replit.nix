{ pkgs }: {
  deps = [
    pkgs.nodejs_20
    pkgs.chromium
    pkgs.nss
    pkgs.glib
    pkgs.gtk3
    pkgs.atk
    pkgs.cups
    pkgs.dbus
    pkgs.xorg.libX11
    pkgs.xorg.libXcomposite
    pkgs.xorg.libXdamage
    pkgs.xorg.libXrandr
    pkgs.xorg.libxcb
    pkgs.xorg.libxkbfile
    pkgs.xorg.libXScrnSaver
    pkgs.alsa-lib
  ];
  env = {
    PUPPETEER_SKIP_DOWNLOAD = "true";
    PUPPETEER_SKIP_CHROMIUM_DOWNLOAD = "true";
    PUPPETEER_EXECUTABLE_PATH = "${pkgs.chromium}/bin/chromium";
    WHATSAPP_WEB_CHROME_PATH = "${pkgs.chromium}/bin/chromium";
  };
}
