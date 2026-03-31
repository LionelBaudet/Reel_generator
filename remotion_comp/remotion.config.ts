// Configuration Remotion pour le générateur de reels @ownyourtime.ai
import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);

// Dimensions verticales Instagram Reels
Config.overrideWebpackConfig((config) => {
  return config;
});
