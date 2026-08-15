# 05 · Pipeline 模式：多 Stage 的配置方式

**源码**：
- [`code/vllm-omni/vllm_omni/config/pipeline_registry.py`](../../code/vllm-omni/vllm_omni/config/pipeline_registry.py)
- [`code/vllm-omni/vllm_omni/model_executor/stage_configs/`](../../code/vllm-omni/vllm_omni/model_executor/stage_configs/)
- 各个模型的 `pipeline.py` 文件

## Pipeline 是什么

在 vLLM-Omni 中，"Pipeline"描述了一个模型如何被拆成多个 Stage：

```
Pipeline = "一个模型 的 Stage 拆分方案"
         = 几个 Stage + 每个 Stage 的类型 + Stage 间的连接方式
```

每个逻辑模型的 `pipeline.py` 文件定义了该模型的 Pipeline。例如：

```python
# qwen2_5_omni/pipeline.py
QWEN2_5_OMNI_PIPELINE = PipelineConfig(
    model_type="qwen2_5_omni",
    model_arch="Qwen2_5OmniForConditionalGeneration",
    stages=(
        StagePipelineConfig(
            stage_id=0,
            model_stage="thinker",
            execution_type=StageExecutionType.LLM_AR,
            model_arch="Qwen2_5OmniThinkerModel",
        ),
        StagePipelineConfig(
            stage_id=1,
            model_stage="talker",
            execution_type=StageExecutionType.LLM_AR,
            model_arch="Qwen2_5OmniTalkerModel",
        ),
        StagePipelineConfig(
            stage_id=2,
            model_stage="code2wav",
            execution_type=StageExecutionType.LLM_GENERATION,
            model_arch="Qwen2_5OmniToken2WavModel",
        ),
    ),
)
```

## Pipeline 配置的两个来源

### 1. YAML 配置文件

[`stage_configs/`](../../code/vllm-omni/vllm_omni/model_executor/stage_configs/) 目录下存放了 YAML 格式的 Stage 配置：

```yaml
# 示例 YAML 配置（stage_configs/ 下的文件结构）
stage_args:
  - stage_id: 0
    stage_type: llm
    engine_args:
      model_stage: thinker
      worker_type: ar
      model_arch: Qwen2_5OmniThinkerModel
  - stage_id: 1
    stage_type: llm
    engine_args:
      model_stage: talker
      worker_type: ar
      model_arch: Qwen2_5OmniTalkerModel
```

### 2. Python 代码

很多模型在 `pipeline.py` 中定义了 `PipelineConfig` 配置变量（如 `QWEN2_5_OMNI_PIPELINE`），以编程方式生成 Stage 配置。

### PipelineRegistry

[`pipeline_registry.py`](../../code/vllm-omni/vllm_omni/config/pipeline_registry.py) 统一管理所有模型的 Pipeline 配置：

```python
# config/pipeline_registry.py
_OMNI_PIPELINES = {
    # model_type -> (module_path, variable_name)
    "qwen2_5_omni": (
        "vllm_omni.model_executor.models.qwen2_5_omni.pipeline",
        "QWEN2_5_OMNI_PIPELINE",
    ),
    "qwen3_omni_moe": (
        "vllm_omni.model_executor.models.qwen3_omni.pipeline",
        "QWEN3_OMNI_PIPELINE",
    ),
    # ... 其他模型；首次查找时延迟 import 对应模块
}
```

## Stage 配置的关键字段

| 字段 | 含义 | 示例 |
|------|------|------|
| `stage_id` | Stage 编号（从 0 开始） | `0` |
| `model_stage` | Stage 类型 | `"thinker"`, `"talker"`, `"code2wav"` |
| `worker_type` | Worker 类型 | `"ar"`, `"generation"` |
| `model_arch` | 该 Stage 的模型架构 | `"Qwen2_5OmniThinkerModel"` |
| `final_output` | 是否是最终输出 Stage | `true` |
| `engine_output_type` | 输出类型 | `"audio"`, `"image"` |
| `hf_config_name` | HF 配置中的子配置名 | `"thinker_config"` |
| `stage_connector_config` | Stage 间连接器 | `{"name": "SharedMemoryConnector"}` |

## Stage 间数据转换

`stage_input_processors/` 目录下的文件定义了 Stage 之间的数据转换逻辑：

### 数据转换函数

每个模型的输入处理器包含一个或多个转换函数：

```python
# 示例：qwen3_omni.py 中的转换函数
def thinker2talker(source_outputs, prompt):
    """
    Thinker 输出 → Talker 输入
    提取：文本 token + 音频控制 signal + additional_information
    """
    ...

def talker2code2wav(source_outputs, prompt):
    """
    Talker 输出 → Code2Wav 输入
    提取：声学特征 code
    """
    ...
```

### 已注册的输入处理器

| 文件 | 模型 |
|------|------|
| `qwen2_5_omni.py` | Qwen2.5-Omni |
| `qwen3_omni.py` | Qwen3-Omni |
| `qwen3_tts.py` | Qwen3-TTS |
| `cosyvoice3.py` | CosyVoice3 |
| `fish_speech.py` | Fish Speech |
| `mimo_audio.py` | MiMo Audio |
| `ming_flash_omni.py` | Ming-Flash-Omni |
| `glm_image.py` | GLM Image |
| `bagel.py` | OmniBagel |
| `hunyuan_image3.py` | HunyuanImage3 |
| `mammoth_moda2.py` | MammothModa2 |
| `omnivoice.py` | OmniVoice |
| `voxcpm.py` | VoxCPM |
| `voxtral_tts.py` | Voxtral TTS |
| `dynin_omni.py` | Dynin Omni |
| `tts_utils.py` | TTS 共享工具 |
| `chunk_size_utils.py` | Chunk 大小计算工具 |

## 如何为新模型添加 Pipeline

添加一个新模型的 Pipeline 大致需要：

1. **模型实现**：在 `model_executor/models/<my_model>/` 下实现模型类
2. **注册模型**：在 `registry.py` 的 `_OMNI_MODELS` 中添加映射
3. **Pipeline 配置**：在 `model_executor/stage_configs/` 或者模型目录下添加 Stage 配置
4. **输入处理器**：在 `stage_input_processors/` 下添加 Stage 间的数据转换函数
5. **（可选）扩散管线**：如果模型有扩散部分，在 `diffusion/models/<my_model>/` 下添加，并在 `diffusion/registry.py` 中注册

## 阅读时间

约 20 分钟。理解 Pipeline 的配置方式能帮你快速定位"一个模型有几个 Stage、各是什么类型"。
