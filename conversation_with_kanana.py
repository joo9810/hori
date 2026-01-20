import os
import re
import time
import json
import warnings
from datetime import datetime
from llama_cpp import Llama
from transformers import AutoTokenizer
from MyModule import get_current_time, get_current_date, get_weather, search_address

# 모델 & 토크나이저 준비
model_path = "/home/user/work/model/kanana_q4_k_m.gguf"
tokenizer_path = "/home/user/work/kanana_merged_temp"

llm = Llama(
    model_path = model_path,
    n_gpu_layers = -1, # GPU
    n_ctx = 1024,       # 문맥 길이
    flash_attn = True,  # 메모리 연산 최적화
    verbose = False     # 실행 정보 띄우는거
)

tokenizer = AutoTokenizer.from_pretrained(
    tokenizer_path,
    fix_mistral_regex = True
)

# --- [도구 함수 정의] ---
TOOLS = {
    "get_current_time": get_current_time,
    "get_current_date": get_current_date,
    "get_weather": get_weather,
    "search_address": search_address,
}

TOOL_DEFINITIONS = [
    {
        "name": "get_current_time",
        "description": "현재 시간을 반환합니다",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_current_date",
        "description": "현재 날짜를 반환합니다",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_weather",
        "description": "특정 지역의 날씨 정보를 조회합니다",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "지역 이름"
                }
            },
            "required": ["city"]
        }
    },
    {
        "name": "search_address",
        "description": "주소를 검색합니다",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "검색어"
                }
            },
            "required": ["location"]
        }
    }
]

# --- [모델 예열] ---
def warmup_llm():
    dummy_messages = [{"role": "user", "content": "안녕"}]

    prompt = tokenizer.apply_chat_template(
        dummy_messages,
        tokenize=False,
        add_generation_prompt=True,
        add_bos=False,
        tools=TOOL_DEFINITIONS
    )

    if prompt.startswith("<|begin_of_text|>"):
        prompt =prompt[len("<|begin_of_text|>"):]

    _ = llm( 
        prompt, 
        max_tokens=1, 
        temperature=0.0, 
        top_p=1.0, 
        top_k=0, 
        stream=False 
    )

print("시스템 최적화 및 예열 중...", end="", flush=True)
warmup_llm()
print("\n준비 완료\n")


def ask_hori(question):
    messages = [{"role": "user", "content": question}]

    formatted_text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        tools=TOOL_DEFINITIONS
    )

    # BOS 수동 제거 
    if formatted_text.startswith("<|begin_of_text|>"): 
        formatted_text = formatted_text[len("<|begin_of_text|>"):]

    # 추론 수행
    print("A: ", end="", flush=True)
    full_response = ""

    output = llm(
        formatted_text,
        max_tokens=1024,
        stop=[tokenizer.eos_token],
        temperature=0.1,
        top_p=0.95,
        top_k=50,
        stream=True # 실시간 텍스트를 만들어줌
    )

    for chunk in output:
        text = chunk['choices'][0]['text']
        print(text, end="", flush=True)
        full_response += text

    print() # 줄바꿈

    # --- [패턴 매칭 로직] ---
    pattern = r'<function=(\w+)>(.+?)</function>' 
    match = re.search(pattern, full_response)

    if match: 
        func_name = match.group(1) 
        args_str = match.group(2) 
        
        args = json.loads(args_str)

        tool_result = TOOLS[func_name](**args)

        messages.append({
            "role": "assistant",
            "content": full_response
        })
        messages.append({
            "role": "tool",
            "content": json.dumps(tool_result, ensure_ascii=False)
        })

        formatted_text_2 = tokenizer.apply_chat_template( 
            messages, 
            tokenize=False, 
            add_generation_prompt=True,
            tools=TOOL_DEFINITIONS
        )

        # BOS 수동 제거
        if formatted_text_2.startswith("<|begin_of_text|>"): 
            formatted_text_2 = formatted_text_2[len("<|begin_of_text|>"):]

        output2 = llm( 
            formatted_text_2, 
            max_tokens=1024, 
            stop=[tokenizer.eos_token], 
            temperature=0.1, 
            top_p=0.95, 
            top_k=50, 
            stream=True 
        )

        final_response = "" 
        for chunk in output2: 
            text = chunk['choices'][0]['text'] 
            print(text, end="", flush=True) 
            final_response += text 
            
        return final_response 
    
    return full_response

# 실행
if __name__ == "__main__": 
    print("\n[Kanana AI 챗봇 모드]") 
    print("'exit'을 입력하면 대화가 종료됩니다.\n") 
    
    while True: 
        # 사용자 입력 받기
        user_input = input("User (질문 입력): ").strip()
        
        # 종료 조건 체크
        if user_input.lower() == 'exit': 
            print("대화를 종료합니다.") 
            break
        
        if not user_input: 
            continue 
        
        # 모델에게 질문하기
        try: 
            print("-" * 30)
            ask_hori(user_input)
            print("\n" + "-" * 30 + "\n")
        except Exception as e: 
            print(f"\n[오류 발생]: {e}")