from llama_cpp import Llama
import os
import gc
from memory_monitor import MemoryMonitor

# Initialize Memory Monitor
monitor = MemoryMonitor()
monitor.print_usage("Initial")

# 1. 모델 로드 (경로는 실제 파일 위치로 수정하세요)
# n_gpu_layers=-1로 하면 GPU를 사용합니다. (CPU만 쓸 경우 0)
# model_path = "./models/qwen2.5-1.5b-instruct-q4_k_m.gguf", # 좀 멍청함
model_path = "./models/qwen2.5-3b-instruct-q4_k_m.gguf"  # 나쁜 애들 중 나음
# model_path = "./models/llama-3.2-3b-instruct-q4_k_m.gguf", # 성능 떨어짐
# model_path = "./models/Qwen3-30B-A3B-Instruct-2507-Q3_K_S-2.70bpw.gguf"  # 좋음: (RAM: 12130.95 MB | VRAM: 6985.18 MB), byteshape
# model_path = "./models/Qwen3-30B-A3B-Instruct-2507-Q3_K_S-3.18bpw.gguf"  # 좋음: (RAM: 12126.89 MB | VRAM: 7005.80 MB), byteshape
# model_path = "./models/Qwen3-30B-A3B-Instruct-2507-IQ4_XS-4.67bpw.gguf"  # 좋음: (RAM: 12688.71 MB | VRAM: 6794.07 MB), byteshape
# model_path = "./models/Qwen3-30B-A3B-Instruct-2507-Q4_K_S-3.92bpw.gguf"  # 좋음: (RAM: 12347.30 MB | VRAM: 6879.61 MB), byteshape

model_name = os.path.basename(model_path).lower()
print(f"Loading model: {model_name}")

llm = Llama(
    model_path=model_path,
    n_ctx=2048,  # context length
    n_gpu_layers=-1,  # use GPU
    verbose=False,  # suppress verbose logging
)

monitor.print_usage("Model Loaded")

# system prompt
system_content = """너의 이름은 '호리'야. 너는 사용자와 대화하는 다정한 로봇 친구야.

[대화 규칙]
1. 말투: 친절한 말투로 존댓말을 사용해.
2. 금지: 반말, 그리고 이모티콘(😊, 🤖 등)은 절대 쓰지 마.
3. 행동: 사용자의 말을 따라 하거나 문장을 완성하려 하지 말고, 질문에 대한 '너의 생각'이나 '대답'을 해.
4. 길이: 일상 대화는 최대 4문장까지로 대답해. 이야기 등을 요청할 땐 10문장 안에 핵심만 축약해서 정중히 대답해.
5. 제한: 할 수 없는 일에 대해선 "죄송하지만 그건 할 수 없어요."라고 정중히 말해.
"""

# use different history format based on model
if "gemma" in model_name:
    # Gemma는 system role 미지원 및 user/assistant 교대 필수 규칙이 있음
    history = [
        {"role": "user", "content": system_content},
        {
            "role": "assistant",
            "content": "네, 알겠습니다! 말씀하신 규칙대로 다정한 로봇 친구 '호리'가 되어 대화할게요. 궁금한 게 있나요?",
        },
    ]
else:  # qwen, llama 등
    history = [{"role": "system", "content": system_content}]

print("🤖 호리: 안녕하세요~! (종료하려면 'q' 입력)")

while True:
    user_input = input("\n👤 나: ")
    if user_input.lower() == "q":
        break

    # append user message to history
    history.append({"role": "user", "content": user_input})

    # create chat completion
    output = llm.create_chat_completion(
        messages=history,
        temperature=0.4,  # creativity
        repeat_penalty=1.1,  # repetition penalty
        top_k=40,  # diversity
        top_p=0.9,  # diversity
        max_tokens=1024,  # max response length
        stream=True,  # Enable streaming
    )

    # print bot reply
    print("🤖 호리: ", end="", flush=True)
    bot_reply = ""
    for chunk in output:
        delta = chunk["choices"][0]["delta"]
        if "content" in delta:
            content = delta["content"]
            print(content, end="", flush=True)
            bot_reply += content
    print()

    # append bot reply to history (to maintain context)
    history.append({"role": "assistant", "content": bot_reply})

print("\n🧹 호리: 정리를 시작할게요...")
del llm
gc.collect()
monitor.print_usage("After Cleanup")
print("✨ 호리: 안녕히 가세요!")
