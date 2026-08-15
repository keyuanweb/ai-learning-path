# 02 · OpenAI 兼容 API：Chat / Image / Audio / Video

**源码**：[`code/vllm-omni/vllm_omni/entrypoints/openai/`](../../code/vllm-omni/vllm_omni/entrypoints/openai/)

## OpenAI 兼容的 API 端点

vLLM-Omni 扩展了 vLLM 的 OpenAI 兼容 API，新增了对图像、音频、视频生成的支持：

| 端点 | 功能 | 对应文件 |
|------|------|---------|
| `/v1/chat/completions` | 对话（含多模态输入） | `serving_chat.py` |
| `/v1/images/generations` | 文生图 | `serving_chat.py`（多 Stage 模型）/ `api_server.py`（单 Stage 扩散） |
| `/v1/audio/generate` | 文生音频 / 语音合成 | `serving_audio_generate.py` |
| `/v1/audio/speech` | TTS 语音合成 | `serving_speech.py` |
| `/v1/audio/speech/stream` | TTS 流式输出 | `serving_speech_stream.py` |
| `/v1/videos` | 文生视频 | `serving_video.py` |
| `/v1/video/chat/stream` | 视频流式输出 | `serving_video_stream.py` |
| `/v1/realtime` | 实时对话（WebSocket） | `realtime_connection.py` |

## API 服务器入口

[`api_server.py`](../../code/vllm-omni/vllm_omni/entrypoints/openai/api_server.py) 使用 FastAPI/asyncio 启动 HTTP 服务器：

```python
# 简化版流程
app = FastAPI()
async_omni = AsyncOmni(model="...")

@app.post("/v1/chat/completions")
async def chat(request: ChatCompletionRequest):
    return await serving_chat.handle_request(request, async_omni)

@app.post("/v1/audio/speech")
async def speech(request: SpeechRequest):
    return await serving_speech.handle_request(request, async_omni)
```

## Chat Completions —— 多模态对话

[`serving_chat.py`](../../code/vllm-omni/vllm_omni/entrypoints/openai/serving_chat.py) 处理对话请求。请求中可以包含：

- **文本**：普通文字消息
- **图片**：`image_url` 形式的图片（理解图片内容）
- **音频**：`audio_url` 形式的音频（语音输入）
- **视频**：视频帧（理解视频内容）

协议定义在 [`protocol/chat_completion.py`](../../code/vllm-omni/vllm_omni/entrypoints/openai/protocol/chat_completion.py)。

## Audio / Speech —— 语音合成

`serving_speech.py` 和 `serving_speech_stream.py` 处理 TTS 请求。关键参数：

- `model`：TTS 模型名
- `input`：要朗读的文字
- `voice`：音色（speaker/voice preset）
- `response_format`：输出格式（wav/mp3 等）
- `speed`：语速

协议定义：[`protocol/audio.py`](../../code/vllm-omni/vllm_omni/entrypoints/openai/protocol/audio.py)

### 流式 TTS

```python
# serving_speech_stream.py
# 不等待整个音频生成完才开始播放，而是"生成一段，播放一段"
async def handle_stream(request):
    async for audio_chunk in generate_audio_stream(request):
        yield audio_chunk
```

## Image Generations —— 文生图

图像生成 API 遵循 OpenAI 的 image generations 格式：

```json
{
  "model": "FluxPipeline",
  "prompt": "a cat sitting on a sofa",
  "n": 1,
  "size": "1024x1024"
}
```

`image_api_utils.py` 处理请求参数转换和结果格式化。

## Video Generations —— 文生视频

视频生成是最复杂的端点之一。相关文件：

- `serving_video.py`：处理单次视频生成请求
- `serving_video_stream.py`：流式返回视频帧
- `video_stream_context.py` / `video_stream_session.py`：管理视频流会话
- `video_frame_filter.py`：后处理视频帧
- `video_api_utils.py`：请求参数转换

视频生成通常分为两个阶段：
1. DiT 扩散模型生成视频帧（潜空间）
2. VAE Decoder 解码 + 后处理（帧插值、颜色校正等）

## Stage 参数管理

[`stage_params.py`](../../code/vllm-omni/vllm_omni/entrypoints/openai/stage_params.py) 负责将"用户的 API 请求参数"映射为"每个 Stage 需要的采样参数"。

因为不同的 Stage 需要不同的 `SamplingParams`（比如 Stage 0 需要 `max_tokens`，Stage 1 不需要），这个文件包含了参数拆分和映射的逻辑。

## 存储系统

[`storage.py`](../../code/vllm-omni/vllm_omni/entrypoints/openai/storage.py) 和 [`stores.py`](../../code/vllm-omni/vllm_omni/entrypoints/openai/stores.py) 实现了生成结果的存储和检索：

- 生成的图片/音频/视频需要保存到磁盘或对象存储
- 返回给用户的 API 响应中包含下载 URL

## 阅读时间

约 30 分钟。建议按需阅读——关注你感兴趣的具体 API 端点对应的文件即可。
