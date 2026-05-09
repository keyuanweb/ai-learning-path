# 从零实现 Mini-Transformer

> 阅读千行不如手写一遍。本章用约 250 行 PyTorch 代码实现一个完整的 Decoder-Only Transformer（GPT 风格），包含所有前面章节讲解的组件。

---

## 完整代码

```python
import torch
import torch.nn as nn
import torch.nn.functional as F
import math

# ==================== 1. Causal Self-Attention (with GQA support) ====================
class CausalSelfAttention(nn.Module):
    """
    解决: 每个token如何从之前的token中聚合上下文信息
    作用: Q查、K标、V取 -- 因果掩码确保不看未来
    """
    def __init__(self, d_model, n_heads, n_kv_heads, block_size, dropout=0.1):
        super().__init__()
        assert d_model % n_heads == 0 and n_heads % n_kv_heads == 0
        self.n_heads = n_heads
        self.n_kv_heads = n_kv_heads
        self.d_k = d_model // n_heads
        self.n_groups = n_heads // n_kv_heads  # GQA 组数

        # QKV 投影
        self.q_proj = nn.Linear(d_model, n_heads * self.d_k, bias=False)
        self.k_proj = nn.Linear(d_model, n_kv_heads * self.d_k, bias=False)
        self.v_proj = nn.Linear(d_model, n_kv_heads * self.d_k, bias=False)
        self.out_proj = nn.Linear(d_model, d_model, bias=False)
        self.dropout = nn.Dropout(dropout)

        # 因果掩码 (下三角矩阵) -- 确保生成时不能偷看未来
        mask = torch.tril(torch.ones(block_size, block_size))
        self.register_buffer('mask', mask.view(1, 1, block_size, block_size))

    def forward(self, x, cos, sin):
        B, T, C = x.shape

        # 投影并分头
        q = self.q_proj(x).view(B, T, self.n_heads, self.d_k).transpose(1, 2)
        k = self.k_proj(x).view(B, T, self.n_kv_heads, self.d_k).transpose(1, 2)
        v = self.v_proj(x).view(B, T, self.n_kv_heads, self.d_k).transpose(1, 2)

        # RoPE: 旋转位置编码 -- 让Attention内积天然包含相对位置
        q = apply_rotary_emb(q, cos, sin)
        k = apply_rotary_emb(k, cos, sin)

        # GQA: 将 KV 头扩展/重复以匹配 Q 头数
        if self.n_groups > 1:
            k = k.repeat_interleave(self.n_groups, dim=1)
            v = v.repeat_interleave(self.n_groups, dim=1)

        # Scaled Dot-Product Attention
        # 缩放 √d_k: 防止大维度导致内积方差爆炸 -> softmax梯度消失
        att = (q @ k.transpose(-2, -1)) / math.sqrt(self.d_k)
        att = att.masked_fill(self.mask[:, :, :T, :T] == 0, float('-inf'))
        att = F.softmax(att, dim=-1)
        att = self.dropout(att)

        y = att @ v
        y = y.transpose(1, 2).contiguous().view(B, T, C)
        return self.out_proj(y)

# ==================== 2. RoPE 工具函数 ====================
def precompute_rope_cos_sin(d_k, max_len, base=10000.0):
    """预计算cos/sin表 -- 避免每步重复计算"""
    theta = 1.0 / (base ** (torch.arange(0, d_k, 2).float() / d_k))
    positions = torch.arange(max_len).float()
    freqs = torch.outer(positions, theta)  # [max_len, d_k/2]
    cos = freqs.cos().view(1, 1, max_len, -1)  # 重复最后一个维度
    cos = torch.cat([cos, cos], dim=-1)
    sin = freqs.sin().view(1, 1, max_len, -1)
    sin = torch.cat([sin, sin], dim=-1)
    return cos, sin

def apply_rotary_emb(x, cos, sin):
    """对 Q/K 的每两个维度应用 2D 旋转变换"""
    d = x.shape[-1] // 2
    x1, x2 = x[..., :d], x[..., d:]
    cos_slice = cos[..., :x.shape[-2], :]
    sin_slice = sin[..., :x.shape[-2], :]
    return torch.cat([
        x1 * cos_slice[..., :d] - x2 * sin_slice[..., :d],
        x1 * sin_slice[..., :d] + x2 * cos_slice[..., :d]
    ], dim=-1)

# ==================== 3. SwiGLU FFN ====================
class FeedForward(nn.Module):
    """
    解决: Attention是线性加权, 需要非线性变换来做信息加工
    作用: 门控FFN (SwiGLU) -- Gate控制信号流量, Up提供信号, Down压缩
    """
    def __init__(self, d_model, d_ff, dropout=0.1):
        super().__init__()
        self.gate_proj = nn.Linear(d_model, d_ff, bias=False)  # 门控
        self.up_proj = nn.Linear(d_model, d_ff, bias=False)    # 信号
        self.down_proj = nn.Linear(d_ff, d_model, bias=False)  # 降维
        self.dropout = nn.Dropout(dropout)

    def forward(self, x):
        gate = F.silu(self.gate_proj(x))  # SiLU 提供非单调非线性
        up = self.up_proj(x)
        return self.dropout(self.down_proj(gate * up))  # gate * up = 门控信号

# ==================== 4. Transformer Block ====================
class TransformerBlock(nn.Module):
    """
    组合 Attention + FFN, 使用 Pre-Norm + 残差连接
    Pre-Norm: 归一化在子层之前 -> 残差路径无LN梯度压缩 -> 训练稳定
    """
    def __init__(self, d_model, n_heads, n_kv_heads, d_ff, block_size, dropout=0.1):
        super().__init__()
        self.attn_norm = nn.RMSNorm(d_model)  # 只缩放不中心化, 比LayerNorm快
        self.ffn_norm = nn.RMSNorm(d_model)
        self.attn = CausalSelfAttention(d_model, n_heads, n_kv_heads, block_size, dropout)
        self.ffn = FeedForward(d_model, d_ff, dropout)

    def forward(self, x, cos, sin):
        x = x + self.attn(self.attn_norm(x), cos, sin)  # Pre-Norm + 残差
        x = x + self.ffn(self.ffn_norm(x))
        return x

# ==================== 5. MiniGPT ====================
class MiniGPT(nn.Module):
    def __init__(self, vocab_size, d_model=512, n_heads=8, n_kv_heads=8,
                 n_layers=8, d_ff=1376, block_size=256, dropout=0.1):
        super().__init__()
        self.d_model = d_model
        self.block_size = block_size

        self.tok_emb = nn.Embedding(vocab_size, d_model)
        self.dropout = nn.Dropout(dropout)

        self.blocks = nn.ModuleList([
            TransformerBlock(d_model, n_heads, n_kv_heads, d_ff, block_size, dropout)
            for _ in range(n_layers)
        ])

        self.ln_final = nn.RMSNorm(d_model)
        self.lm_head = nn.Linear(d_model, vocab_size, bias=False)

        # 共享 embedding 和 lm_head 权重 -- 省 ~30% 参数
        self.tok_emb.weight = self.lm_head.weight

        # 预计算 RoPE 的 cos/sin
        d_k = d_model // n_heads
        cos, sin = precompute_rope_cos_sin(d_k, block_size)
        self.register_buffer('cos', cos)
        self.register_buffer('sin', sin)

        self.apply(self._init_weights)

    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            nn.init.normal_(module.weight, mean=0.0, std=0.02 / math.sqrt(2 * self.n_layers))
        if isinstance(module, nn.Embedding):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward(self, x, targets=None):
        B, T = x.shape
        assert T <= self.block_size

        # Token Embedding (不用额外加Position Embedding, RoPE在Attention中处理)
        h = self.dropout(self.tok_emb(x))

        for block in self.blocks:
            h = block(h, self.cos[:, :, :T], self.sin[:, :, :T])

        h = self.ln_final(h)
        logits = self.lm_head(h)  # [B, T, vocab_size]

        loss = None
        if targets is not None:
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)),
                                    targets.view(-1))
        return logits, loss

    @torch.no_grad()
    def generate(self, x, max_new_tokens, temperature=1.0, top_k=None):
        """自回归生成 -- 每次生成一个token, 拼接到输入序列"""
        for _ in range(max_new_tokens):
            x_cond = x[:, -self.block_size:]  # 截断到最大长度
            logits, _ = self(x_cond)
            logits = logits[:, -1, :] / temperature  # 温度: 控制确定性 vs 创意
            if top_k is not None:
                v, _ = torch.topk(logits, top_k)
                logits[logits < v[:, [-1]]] = float('-inf')
            probs = F.softmax(logits, dim=-1)
            next_token = torch.multinomial(probs, 1)
            x = torch.cat([x, next_token], dim=1)
        return x


# ==================== 6. 训练脚本 ====================
def train_shakespeare():
    # 数据准备
    text = open('shakespeare.txt', 'r').read()
    chars = sorted(list(set(text)))
    vocab_size = len(chars)
    stoi = {ch: i for i, ch in enumerate(chars)}  # char → id
    itos = {i: ch for i, ch in enumerate(chars)}  # id → char

    data = torch.tensor([stoi[c] for c in text], dtype=torch.long)
    split = int(0.9 * len(data))
    train_data, val_data = data[:split], data[split:]

    # 模型 (约 10M 参数)
    model = MiniGPT(vocab_size=vocab_size, d_model=512, n_heads=8,
                    n_kv_heads=8, n_layers=8, d_ff=1376, block_size=256)
    model = model.to('cuda')
    print(f"参数量: {sum(p.numel() for p in model.parameters()) / 1e6:.1f}M")

    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=0.1)

    for epoch in range(10):
        for step in range(200):
            # 随机采样 batch
            ix = torch.randint(0, len(train_data) - 257, (32,))
            x = torch.stack([train_data[i:i+256] for i in ix])
            y = torch.stack([train_data[i+1:i+257] for i in ix])
            x, y = x.to('cuda'), y.to('cuda')

            logits, loss = model(x, y)
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

        print(f"Epoch {epoch}: loss={loss.item():.4f}")

    # 生成
    context = torch.tensor([[stoi['R'], stoi['O'], stoi['M'], stoi['E'], stoi['O'], stoi[':']]], device='cuda')
    output = model.generate(context, max_new_tokens=200, temperature=0.8)
    print(''.join(itos[i] for i in output[0].tolist()))

if __name__ == '__main__':
    train_shakespeare()
```

---

## 每个组件的"解决问题 → 设计决策"映射

| 组件 | 解决的问题 | 具体设计 |
|------|-----------|---------|
| **Causal Mask** | 生成时不能看到未来 | 下三角掩码（上三角 = -∞ → softmax后=0） |
| **√dₖ 缩放** | 大维度内积方差爆炸 → softmax梯度消失 | 除以 $\sqrt{d_k}$ 将方差恢复为1 |
| **RoPE** | Attention本身不感知位置 | 旋转Q和K使内积包含相对位置 |
| **GQA** | MHA的KV Cache太大 | K/V头数少于Q头数，组内共享 |
| **SwiGLU FFN** | 需要非线性但ReLU太粗暴 | SiLU门控 + 线性信号，自适应流量控制 |
| **RMSNorm** | LayerNorm中心化不必要 | 只缩放不中心化，计算更快 |
| **Pre-Norm** | Post-Norm梯度被压缩 | 归一化在子层之前，残差路径无损 |
| **残差连接** | 深层梯度消失 | +1的无损梯度通道 |
| **weight tying** | embedding和lm_head参数冗余 | 两者共享权重 |

这个 ~250 行的实现包含了现代 LLM 的所有核心设计思想。在莎士比亚文本上训练几个 epoch 后模型就能生成看起来像古英语的文本——证明你理解了 Transformer 的每一个角落。
