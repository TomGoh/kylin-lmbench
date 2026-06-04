#!/usr/bin/env bash
# Idempotent: 把所有已知的 KylinOS 噪声服务（system-level + user-level）
# 全部 systemctl mask 并 stop 一遍。mask 状态写入：
#   - 系统级: /etc/systemd/system/*.service -> /dev/null  （root 写，重启后保留）
#   - 用户级: ~/.config/systemd/user/*.service -> /dev/null  （kylin 写，重启后保留）
# 之后哪怕物理重启或 user session 重新登录，这些都不会被启动。
#
# 在每个 lmbench 配置切换前都跑一遍，确保所有目标全 mask（idempotent，重复 mask 无副作用）。

set -u

SYS_NOISY=(
  # 系统级 Kylin / UKUI / 桌面 daemon
  accounts-daemon
  activationSnUpdate
  biometric-authentication
  boltd
  colord
  com.kylin.kysdk.SyncConfig
  dbus-com.kylin.kysdk.applicationsec
  dbus-com.kylin.secriskbox.system
  ksc-defender-daemon
  ksc-defender-init
  kyfs-fuse
  kylin-ai-cryptojacking-detect
  kylin-boxadm-daemon
  kylin-core-dump-monitor
  kylin-daq
  kylin-endisk-daemon
  kylin-os-manager-driver-acquirer
  kylin-printer-applet-dbus
  kylin-process-manager-daemon
  kylin-process-resource-manager-daemon
  kylin-software-center-plugin
  kylin-software-center-plugin-preprocessing
  kylin-software-center-plugin-synchrodata
  kylin-source-update
  kylin-source-update-timer
  kylin-system-updater
  kylin-system-updater-control
  kylin-unattended-upgrades
  kylin-update-rescue
  kylin-upgrade
  kysdk-conf2
  kysdk-dbus
  kysdk-systime
  kysec-sync-record
  kytensor
  lightdm
  ModemManager
  packagekit
  pvm-manage
  udisks2
  ukui-bluetooth
  ukui-input-gather
  ukui-media-control-mute-led
  upower
  # day-3 增补：reboot 后才暴露的几个
  kyseclogd
  avahi-daemon
  avahi-daemon.socket
  cron
  kalertd
  kysec-set-system
  # day-3 verify 又揭露一批：
  ksaf-label-manager
  ksaf-devctl-sync-daemon
  ksaf-policy-init
  kysec-scene-init
  ksc-vulnerability-repair-daemon
  ksc-defender
  cups
  cups-browsed
  cups-pdf
  nginx
  strongswan
  strongswan-starter
  charon
  ipsec
  dnsmasq
  tee-supplicant
  kydima-daemon
  kylin-software-properties-service
  kylin-nm-netctrl
  ostree-maintain.timer
  serial-getty@ttyAMA0
  getty@tty1
  # day-3 第三波
  bluetooth
  smartd
  smartmontools
  rsyslog
  wpsupdateserver
  timermanager
  activation-daemon
  kylin-assistant-systemdaemon
  kylin-assistant
  ostree-maintain
  ostree-maintain-daemon
  fcron
  saned
  x-kernel
  # day-3 第四波 verify 揭露
  activation-daemon-init
  activation-init
  kylin-activation-check
  activationSnUpdate.timer
)

USER_NOISY=(
  # 用户级（systemd --user 触发） Kylin AI + 桌面
  com.cvte.exceedshare
  km-ses-dbusproxy
  kyai-data-management-service
  kylin-ai-document-qa-service
  kylin-ai-knowledgebase-service
  kylin-ai-vector-engine
  kylin-software-center-plugin-preprocessing
  kylin-software-center-plugin-synchrodata
  pulseaudio
  pulseaudio-x11
  ukui-session-service-manager
  ukui-volume-control
)

# --- 1. system-level mask ---
echo "[apply-masks] system-level: ${#SYS_NOISY[@]} services"
for svc in "${SYS_NOISY[@]}"; do
  sudo systemctl stop "${svc}.service" 2>/dev/null
  sudo systemctl mask "${svc}.service" 2>/dev/null
done

# --- 1b. socket masks ---
sudo systemctl stop pulseaudio.socket 2>/dev/null
sudo systemctl mask pulseaudio.socket 2>/dev/null

# --- 2. user-level mask ---
echo "[apply-masks] user-level: ${#USER_NOISY[@]} services"
for svc in "${USER_NOISY[@]}"; do
  systemctl --user stop "${svc}.service" 2>/dev/null
  systemctl --user mask "${svc}.service" 2>/dev/null
done
systemctl --user stop pulseaudio.socket 2>/dev/null
systemctl --user mask pulseaudio.socket 2>/dev/null

# --- 3. 一次性强杀残留（不依赖 systemd 关停） ---
KILL_PATTERN='kylin-ai|kyai-data-management|kylin-software-center|kylin-software-properties|kylin-system-updater|kylin-upgrade|kylin-source-update|kylin-assistant|kylin-nm-netctrl|ksc-defender|ksc-vulnerability|pulseaudio|biometric-auth|kylin-core-dump|ukui-input-gather|ukui-search|ukui-volume|pvm-manage|crosvm|kyseclogd|kalertd|kydima|ksaf-label|ksaf-devctl|ksaf-policy|kysec-scene|cupsd|cups-browsed|nginx|charon|ipsec|dnsmasq|tee-supplicant|bluetoothd|smartd|rsyslogd|wpsupdateserver|timermanager|activation-daemon|ostree-maintain|avahi-daemon|cron|kylin-printer'
sudo pkill -9 -f "$KILL_PATTERN" 2>/dev/null

# --- 4. default target ---
sudo systemctl set-default multi-user.target 2>/dev/null

echo "[apply-masks] done"
