import os
import re
import time
import json
import warnings
from datetime import datetime
from llama_cpp import Llama
from transformers import AutoTokenizer

# 모델 & 토크나이저 준비
model_path = "/home/user/work/model/kanana_q4_k_m.gguf"
tokenizer_path = "/home/user/work/kanana_merged_temp"

llm = Llama(
    model_path = model_path,
    n_gpu_layers = 999, # GPU에 최대한 올리기
    n_ctx = 1024,       # 문맥 길이
    flash_attn = True,  # 메모리 연산 최적화
    verbose = False     # 실행 정보 띄우는거
)

tokenizer = AutoTokenizer.from_pretrained(
    tokenizer_path,
    fix_mistral_regex = True
)

# --- [도구 함수 정의] ---
def get_current_time():
    return datetime.now().strftime(f"현재 시간: %H시 %M분")

def get_current_date():
    
    date = datetime.now().strftime(f"%Y년 %m월 %d일 %H시 %M분")
    weekday = datetime.now().strftime("%A")

    if weekday == "Monday":
        return date + " 월요일"
    elif weekday == "Tuesday":
        return date + " 화요일"
    elif weekday == "Wednesday":
        return date + " 수요일"
    elif weekday == "Thursday":
        return date + " 목요일"
    elif weekday == "Saturday":
        return date + " 토요일"
    else:
        return date + " 일요일"

def get_weather(location):
    """날씨 정보 (더미)"""
    # 실제로는 API 호출
    return f"{location}의 날씨: 맑음, 23°C"

def search_address(query):
    """주소 검색 (더미)"""
    return f"{query} 검색 결과: 서울시 강남구 27번길"

TOOLS = {
    "get_current_time": get_current_time,
    "get_current_date": get_current_date,
    "get_weather": get_weather,
    "search_address": search_address,
}

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "현재 시간을 반환합니다",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_date",
            "description": "현재 날짜를 반환합니다",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "특정 지역의 날씨 정보를 조회합니다",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "지역 이름"}
                },
                "required": ["location"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_address",
            "description": "주소를 검색합니다",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "검색어"}
                },
                "required": ["query"]
            }
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
        add_bos=False,  # llama-cpp가 begin of sentence를 자체적으로 넣으므로 토크나이저에서는 끔
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
        temperature=0.5,
        top_p=1.0,
        top_k=10,
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
        params_str = match.group(2) 
        
        # 파라미터 파싱 
        params = {} 
        try: 
            params = json.loads(params_str) 
        except: 
            for part in params_str.split(","): 
                try: 
                    key, value = part.split("=") 
                    params[key.strip()] = value.strip().strip('"') 
                except: 
                    pass

        # 도구 실행
        information = TOOLS[func_name](**params)
        print(f"(시스템 정보 획득: {information})")

        # 2차 응답 구성
        messages.append({'role': 'system', 'content': f"""
                        [예시]
                        정보: 10시 30분
                        질문: 지금 운동 가도 될까?
                        답변: 현재 시간은 10시 30분입니다. 운동을 가시기에 충분한 시간입니다.

                        [실제 상황]
                        정보: {information}
                        질문: {user_input}
                        위 예시와 동일한 형식으로, 반드시 정보를 먼저 언급한 뒤 함수 추가 호출 없이 user의 질문에 답변하세요."""})
        
        formatted_text_2 = tokenizer.apply_chat_template( 
            messages, 
            tokenize=False, 
            add_generation_prompt=True, 
            add_bos=False,
            tools=TOOL_DEFINITIONS
        )

        # BOS 수동 제거
        if formatted_text_2.startswith("<|begin_of_text|>"): 
            formatted_text_2 = formatted_text_2[len("<|begin_of_text|>"):]

        output2 = llm( 
            formatted_text_2, 
            max_tokens=1024, 
            stop=[tokenizer.eos_token], 
            temperature=0.0, 
            top_p=1.0, 
            top_k=0, 
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