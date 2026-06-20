# TruthSeeker 45s Promo

交付物为 45 秒、1920x1080 的 HTML Canvas 宣传片母版，面向评委路演优先设计。画面无水印，包含中文字幕、合成 BGM/SFX、系统截图与 Logo。

## 播放

用 Chrome 或 Edge 打开：

```text
truthseeker-promo.html
```

快捷键：

- Space：播放 / 暂停
- R：从 0 秒开始录制
- Record WebM：浏览器内录制 WebM，录制完成后页面会出现下载链接

录制时会隐藏控制栏，并把 WebAudio 合成音轨写入录制流。

## 预览参数

```text
truthseeker-promo.html?t=16&clean=1
```

- `t`：指定预览秒数
- `clean=1`：隐藏控制栏和提示条，便于截图
- `record=1`：打开页面后自动开始录制

## MP4 导出说明

当前已提供自动导出脚本：

```powershell
node promo-video\export-video.mjs
```

脚本会：

- 使用本机 Chrome/Edge 打开 HTML 母版
- 自动录制 45 秒 WebM
- 使用 `ffmpeg-static` 转为 H.264 MP4
- 输出到 `promo-video/dist/truthseeker-promo.mp4`

依赖当前安装在 `promo-video/promo-video/` 下，脚本会从该目录加载 `playwright` 和 `ffmpeg-static`。
