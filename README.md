# 西西编程伙伴

面向小学 C++ 启蒙课堂的卡通数字人网页应用。学生输入问题后，系统优先从已上传教材中检索依据，再由 OpenAI 兼容接口生成少儿友好的改述答案；未配置模型时使用本地规则改述，不直接朗读教材原文。浏览器可以使用系统中文音色，也可以通过本机 GPT-SoVITS 使用已授权的真人参考音频。

## 快速启动

```powershell
./run.ps1
```

如果希望关闭 PowerShell 窗口后服务仍保持运行：

```powershell
./run.ps1 -Background
```

首次启动会创建 `.venv` 并安装依赖。打开 `http://localhost:8000`。同一局域网的设备可访问控制台显示的本机地址，例如 `http://192.168.1.20:8000`。

注意：`8000` 是课堂网页端口；`9880` 只用于 GPT-SoVITS 语音 API，不能当作课堂网页地址打开。

默认教师密码为 `teacher123`。正式使用前请在 PowerShell 中设置：

```powershell
$env:ADMIN_PASSWORD = "换成你的强密码"
./run.ps1
```

进入“教师管理”后可上传 DOCX、PDF、TXT 或 Markdown，删除资料、重建索引，以及配置 OpenAI 兼容服务的 Base URL、模型名和 API Key。示例 Base URL：`https://api.deepseek.com/v1`。API Key 仅保存在本机 `data/settings.json`，不会提交到 Git。

## 真人声音

推荐使用 [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) 的本地 API。先按其 Windows 文档下载模型并启动 `api_v2.py`（默认 `http://127.0.0.1:9880`），再在教师管理中上传已经获得本人授权的 10–30 秒 WAV/MP3/FLAC/M4A/OGG 参考录音，填写逐字稿和语气标签。录音文件只保存在 `data/voice_samples/`，默认不会上传云端，也不应上传儿童声音。

语气标签只影响音色参考和表达风格，不会把录音文字直接复制到答案。未配置样本或 GPT-SoVITS 不可用时，Windows 会先用已安装的中文系统音色在本机生成音频；若本机音色不可用，或在其他操作系统上，则回退到浏览器朗读。回答下方可重播声音。关闭设备音色降级后则只显示文字，不播放声音。

## 目录

- `app/main.py`：HTTP API、静态页面和管理接口
- `app/knowledge.py`：文档提取、切片、中文 BM25 检索
- `app/llm.py`：OpenAI 兼容 Chat Completions 客户端
- `app/style.py`：教材改述、回答重合检测、情绪分类
- `app/tts.py`：GPT-SoVITS API 适配和白名单声音样本库
- `app/static/`：学生端、教师管理端与角色素材
- `data/uploads/`：知识库原始资料
- `data/voice_samples/`：教师授权参考音频
- `data/tts_cache/`：本地临时合成音频

## 说明

角色素材由用户提供的 Q 版人物参考图裁切、透明化并用于课堂状态动画。项目的语音交互分层参考 Open-LLM-VTuber，但未复制其前端代码或 Live2D 示例模型。详见 `OPEN_SOURCE_NOTICES.md`。
