import os
import re
import json
import time
import threading
from datetime import datetime
from llama_cpp import Llama
from transformers import AutoTokenizer
from collections import deque
from pyjosa.josa import Josa
from MyModule import get_current_time, get_current_date, get_weather, search_address

import sys
sys.path.append("/home/user/work/MeloTTS")
from melo.api import TTS
import subprocess
from num2words import num2words
import torch

# 메모리 모니터링 함수
import psutil
def get_memory_usage(label=""):
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()

    # RAM (MB)
    ram_mb = memory_info.rss / 1024 / 1024

    # GPU (MB) - CUDA 사용 중일 때
    if torch.cuda.is_available():
        gpu_mb = torch.cuda.memory_allocated() / 1024 / 1024
        print(f"[{label}] RAM: {ram_mb:.2f}MB | GPU: {gpu_mb:.2f}MB")
    else:
        print(f"[{label}] RAM: {ram_mb:.2f}MB | GPU: N/A")

    return ram_mb

get_memory_usage("초기 상태")

# 모델 & 토크나이저 준비
model_path = "/home/user/work/model/kanana_q4_k_m_8B_v2.gguf"
tokenizer_path = "/home/user/work/model/kanana-1.5-8b-instruct-2505"

llm = Llama(
    model_path = model_path,
    n_gpu_layers = -1, # GPU
    n_ctx = 2048,       # 문맥 길이
    flash_attn = True,  # 메모리 연산 최적화
    verbose = False     # 실행 정보 띄우는거
)

get_memory_usage("Kanana 로드 후")

tokenizer = AutoTokenizer.from_pretrained(
    tokenizer_path,
    # fix_mistral_regex = True
    trust_remote_code=True,
    legacy=False
)

get_memory_usage("토크나이저 로드 후")

speed = 1.3
device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
tts_model = TTS(language='KR', device=device)
speaker_ids = tts_model.hps.data.spk2id

get_memory_usage("MeloTTS 로드 후")

# --- [도구 함수 정의] ---
TOOLS = {
    "get_current_time": get_current_time,
    "get_current_date": get_current_date,
    "get_weather": get_weather,
    "search_address": search_address
}

TOOL_DEFINITIONS = [
    {
        "name": "get_current_time",
        "description": "현재 시간을 반환합니다.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_current_date",
        "description": "현재 날짜를 반환합니다.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_weather",
        "description": "특정 도시의 날씨 정보를 조회합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "도시"
                }
            },
            "required": ["city"]
        }
    },
    {
        "name": "search_address",
        "description": "주소를 검색합니다.",
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

SYSTEM_INSTRUCTION = """사용자가 구체적인 지역명을 언급하지 않았다면, 이전 대화의 지역을 유추하지 말고 입력된 텍스트에서만 지역명을 추출하세요."""

# --- [모델 예열] ---
def warmup_llm():
    dummy_messages = [{"role": "user", "content": "안녕"}]

    prompt = tokenizer.apply_chat_template(
        # [{"role": "system", "content": SYSTEM_INSTRUCTION}] + dummy_messages,
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

    # 더미 파일 생성
    tts_model.tts_to_file("테스트", speaker_ids['KR'], "output.wav", speed=speed)

print("시스템 최적화 및 예열 중...", end="", flush=True)
warmup_llm()
print("\n준비 완료\n")

MAX_HISTORY = 20
history_messages = deque(maxlen=MAX_HISTORY)
alarm_list = []

def ask_hori(question):
    history_messages.append(
        {"role": "user", "content": question}
    )

    # messages_for_llm = [{"role": "system", "content": SYSTEM_INSTRUCTION}] + list(history_messages)
    messages_for_llm = list(history_messages)

    formatted_text = tokenizer.apply_chat_template(
        messages_for_llm,
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
        max_tokens=2048,
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
    get_memory_usage("1차 응답 생성 직후")
    print() # 줄바꿈

    # --- [패턴 매칭 로직] ---
    pattern = r'<function=(\w+)>(.+?)</function>' 
    matches = re.finditer(pattern, full_response)

    # 보조 도구 실행 내역을 담을 리스트
    tool_calls_found = list(matches)

    if tool_calls_found:
        # 어시스턴트의 '생각(도구 호출 요청)'을 대화 기록에 추가
        history_messages.append({
            "role": "assistant",
            "content": full_response
        })

        for match in tool_calls_found:
            func_name = match.group(1)
            args_str = match.group(2)

            args = json.loads(args_str)

            tool_result = TOOLS[func_name](**args)

            # 도구 실행 결과
            print(tool_result)

            # 도구 실행 결과를 대화 기록에 각각 추가
            history_messages.append({
            "role": "tool",
            "content": json.dumps(tool_result, ensure_ascii=False)
            })

        # messages_for_final = [{"role": "system", "content": SYSTEM_INSTRUCTION}] + list(history_messages)
        messages_for_final = list(history_messages)

        formatted_text_2 = tokenizer.apply_chat_template( 
            messages_for_final, 
            tokenize=False, 
            add_generation_prompt=True,
            tools=TOOL_DEFINITIONS
        )

        # BOS 수동 제거
        if formatted_text_2.startswith("<|begin_of_text|>"): 
            formatted_text_2 = formatted_text_2[len("<|begin_of_text|>"):]

        output2 = llm( 
            formatted_text_2, 
            max_tokens=2048, 
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
        # get_memory_usage("2차 응답 생성 직후")

        history_messages.append({
            "role": "assistant",
            "content": final_response
        })

        # 최종 답변 재생
        play_audio(final_response)

        print(history_messages)

        return final_response 
    
    history_messages.append({
        "role": "assistant",
        "content": full_response
    })

    # 일반 답변 재생
    play_audio(full_response)

    print(history_messages)

    return full_response

def preprocess_text(text):
    # 고유어 변환용 맵
    pure_korean_map = {
        '1': '한', '2': '두', '3': '세', '4': '네', '5': '다섯',
        '01': '한', '02': '두', '03': '세', '04': '네', '05': '다섯',
        '6': '여섯', '7': '일곱', '8': '여덟', '9': '아홉', '10': '열',
        '06': '여섯', '07': '일곱', '08': '여덟', '09': '아홉',
        '11': '열한', '12': '열두'# , '13': '열세', '14': '열네', '15': '열다섯',
        # '16': '열여섯', '17': '열일곱', '18': '열여덟', '19': '열아홉'
    }

    # '시' 앞의 숫자 처리
    def time_replacer(match):
        num = match.group(1)
        unit = match.group(2)
        if num in pure_korean_map:
            return pure_korean_map[num] + unit
        return num + unit
    
    try:
        # 태그 제거 (<function=...> 등)
        text = re.sub(r'<[^>]*>', '', text)

        # 특수기호 없애기
        # , → .
        text = re.sub(r', ', '.', text) # 네, 노인 기초연금 수급 대상은~ -> 네.노인 기초연급 수급 대상은
        text = re.sub(r'[,]', '', text) # 20,000 -> 20000
        text = re.sub(r"[']", '', text) # '불이야!' -> 불이야!

        text = re.sub(r'(\d+)\s*\+\s*(\d+)', r'\1 더하기 \2', text)
        text = re.sub(r'(\d+)\s*-\s*(\d+)', r'\1 빼기 \2', text)
        text = re.sub(r'(\d+)\s*x\s*(\d+)', r'\1 곱하기 \2', text)
        text = re.sub(r'(\d+)\s*/\s*(\d+)', r'\1 나누기 \2', text)

        # '시', '개', '명', '살' 등의 단위 앞에 오는 숫자를 처리
        text = re.sub(r'(\d+)\s*(시|개|명|살|알|팩|마리|조각)', time_replacer, text)

        # 나머지 숫자는 기존 num2words로 처리
        text = re.sub(r'\d+', lambda m: num2words(int(m.group()), lang='ko'), text)

        if "=" in text:
            split_text = text.split("=")
            text = Josa.get_full_string(split_text[0], "는") + " " + split_text[1]

        # 마침표 주변 정리
        text = re.sub(r'\s*\.\s*', '. ', text)

        # 중복 공백 제거
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    except Exception as e:
        print(f"\n[오류 발생1]: {e}")
        return

error_text = "죄송합니다. 해당 질문에는 답변 해드릴 수 없습니다."

def play_audio(text):
    try:
        # --- TTS 파일 생성 ---
        output_path = "temp_response.wav"

        clean_text = preprocess_text(text)

        # MeloTTS 실행
        tts_model.tts_to_file(clean_text, speaker_id=0, output_path=output_path, speed=1.2)
        
        # PowerShell을 이용한 윈도우 재생
        subprocess.run([
            "ffplay.exe", 
            "-nodisp", 
            "-autoexit", 
            "-loglevel", "quiet", 
            os.path.abspath(output_path)
        ])
    except Exception as e:
        print(f"\n[오류 발생2]: {e}")
        # MeloTTS 실행
        tts_model.tts_to_file(error_text, speaker_id=0, output_path=output_path, speed=1.2)
        
        history_messages.pop()
        history_messages.pop()

        # PowerShell을 이용한 윈도우 재생
        subprocess.run([
            "ffplay.exe", 
            "-nodisp", 
            "-autoexit", 
            "-loglevel", "quiet", 
            os.path.abspath(output_path)
        ])

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
            get_memory_usage("추론 후")
        except Exception as e: 
            print(f"\n[오류 발생3]: {e}")
            play_audio(error_text)