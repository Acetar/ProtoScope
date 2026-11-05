import {Config} from '@remotion/cli/config';

// 输出视频的帧图格式：jpeg 更快，png 更清晰（体积更大）
Config.setVideoImageFormat('jpeg');
Config.setOverwriteOutput(true);
// 本机 demo 固定 2 路并发；生产 1080p 建议 1，720p 可 2
Config.setConcurrency(2);
