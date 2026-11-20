#!/usr/bin/env bash
# Steam 入口：《异界锁链》1.0.1 原生重编译。跑哪个版本由 astral-native/current 决定，
# 升级发布不需要改这里；全新 Deck 把本文件装到 ~/native-recomp/launchers/ 即可复原入口。
# 存档与着色器缓存在 astral-native/data（current/run.sh 里指过去），换 release 不会换档。
# A=确认 B=取消、60 帧默认、原生陀螺仪；X11 视频驱动与两塞尔达一致（不需要 wayland portal）。
set -euo pipefail
ulimit -c 0
export SteamDeck=1
export SDL_VIDEO_DRIVER=x11 SDL_VIDEODRIVER=x11
exec "$HOME/native-recomp/astral-native/current/run.sh"
