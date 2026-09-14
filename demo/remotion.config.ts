import { Config } from "@remotion/cli/config";

// Chrome Headless Shell с remotion.media в этой сети не скачивается (ECONNRESET),
// поэтому рендерим системным Chrome — он есть и уже проверен на съёмке экранов.
Config.setBrowserExecutable("/usr/bin/google-chrome");
Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
Config.setConcurrency(2);
