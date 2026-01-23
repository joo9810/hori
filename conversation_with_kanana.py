import os
import re
import json
import time
import threading
from datetime import datetime
from llama_cpp import Llama
from transformers import AutoTokenizer
from collections import deque
from MyModule import get_current_time, get_current_date, get_weather, search_address, get_alarms, set_alarms, delete_alarms

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
model_path = "/home/user/work/model/kanana_q4_k_m_v3.gguf"
tokenizer_path = "/home/user/work/model/kanana-1.5-2.1b-instruct-2505"

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
    "search_address": search_address,
    "get_alarms": get_alarms,
    "set_alarms": set_alarms,
    "delete_alarm": delete_alarms,
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
                    "description": "사용자가 언급힌 도시 이름을 그대로 사용하세요."
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
    },
    {
        "name": "get_alarms",
        "description": "현재 등록된 모든 알람 목록을 확인합니다."
    },
    {
        "name": "set_alarms",
        "description": "새로운 알람을 예약합니다. 사용자가 명시한 시간과 날짜 정보를 모두 추출하여 반드시 포함해야 합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "알람 시 알려줄 내용"
                },
                "year": {
                    "type": "integer",
                    "description": "연도 (4자리 숫자)"
                },
                "month": {
                    "type": "integer",
                    "description": "월 (1-12)"
                },
                "day": {
                    "type": "integer",
                    "description": "일 (1-31)"
                },
                "hour": {
                    "type": "integer",
                    "description": "시 (0-23)"
                },
                "minute": {
                    "type": "integer",
                    "description": "분 (0-59)"
                },
                "relative_day": {
                    "type": "integer",
                    "description": "오늘 기준 날짜 차이. 오늘=0, 내일=1, 모레=2, 글피=3 등등"
                },
                "week_offset": {
                    "type": "integer",
                    "description": "주 단위 차이. 이번 주=0, 다음 주=1"
                },
                "day_of_week": {
                    "type": "string",
                    "description": "요일 (예: '월요일', '화요일', ..., '일요일')"
                },
                "is_ampm_specified": {
                    "type": "boolean",
                    "description": "사용자가 '오전', '오후', '아침', '밤' 등 시간을 지정했다면 True, 지정하지 않았다면 False를 주세요."
                }
            },
            "required": ["hour"]
        }
    },
    {
        "name": "delete_alarms",
        "description": "등록된 알람을 삭제합니다",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "삭제할 알람의 메시지 내용"
                },
                "year": {
                    "type": "integer",
                    "description": "연도 (4자리 숫자)"
                },
                "month": {
                    "type": "integer",
                    "description": "월 (1-12)"
                },
                "day": {
                    "type": "integer",
                    "description": "일 (1-31)"
                },
                "hour": {
                    "type": "integer",
                    "description": "시 (0-23)"
                },
                "minute": {
                    "type": "integer",
                    "description": "분 (0-59)"
                },
                "relative_day": {
                    "type": "integer",
                    "description": "오늘 기준 날짜 차이. 오늘=0, 내일=1, 모레=2, 글피=3 등등"
                },
                "week_offset": {
                    "type": "integer",
                    "description": "주 단위 차이. 이번 주=0, 다음 주=1"
                },
                "day_of_week": {
                    "type": "string",
                    "description": "요일 (예: '월요일', '화요일', ..., '일요일')"
                },
                "is_ampm_specified": {
                    "type": "boolean",
                    "description": "사용자가 '오전', '오후', '아침', '밤' 등 시간을 지정했다면 True, 지정하지 않았다면 False를 주세요."
                }
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

    # 더미 파일 생성
    tts_model.tts_to_file("테스트", speaker_ids['KR'], "output.wav", speed=speed)

print("시스템 최적화 및 예열 중...", end="", flush=True)
warmup_llm()
print("\n준비 완료\n")

MAX_HISTORY = 20
total_messages = deque(maxlen=MAX_HISTORY)
alarm_list = []

def ask_hori(question):
    total_messages.append(
        {"role": "user", "content": question}
    )

    formatted_text = tokenizer.apply_chat_template(
        list(total_messages),
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
        total_messages.append({
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
            total_messages.append({
            "role": "tool",
            "content": json.dumps(tool_result, ensure_ascii=False)
            })


        formatted_text_2 = tokenizer.apply_chat_template( 
            list(total_messages), 
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

        total_messages.append({
            "role": "assistant",
            "content": final_response
        })

        # 최종 답변 재생
        play_audio(final_response)
        return final_response 
    
    total_messages.append({
        "role": "assistant",
        "content": full_response
    })

    # 일반 답변 재생
    play_audio(full_response)
    return full_response

def number_to_korean(text):
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
    
    # '시', '개', '명', '살' 등의 단위 앞에 오는 숫자를 처리
    text = re.sub(r'(\d+)\s*(시|개|명|살|마리)', time_replacer, text)

    # 나머지 숫자는 기존 num2words로 처리
    text = re.sub(r'\d+', lambda m: num2words(int(m.group()), lang='ko'), text)

    return text

def play_audio(text):
    if not text: 
        return
    
    # 1. 태그 제거 (<function=...> 등)
    clean_text = re.sub(r'<[^>]*>', '', text)

    # 2. 숫자 → 한글 변환
    clean_text = number_to_korean(clean_text)

    # 3. 쉼표와 줄바꿈을 마침표로 변환
    # , → .
    clean_text = re.sub(r'[,]', '.', clean_text)

    # 4. 허용 문자만 남기기 (. 은 유지)
    # clean_text = re.sub(r'[^가-힣a-zA-Z0-9.\s]', ' ', clean_text)

    # 5. 마침표 주변 정리
    clean_text = re.sub(r'\s*\.\s*', '. ', clean_text)

    # 6. 중복 공백 제거
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    if not clean_text: 
        return

    # --- TTS 파일 생성 ---
    output_path = "temp_response.wav"

    try:
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
    except FileNotFoundError:
        print("ffplay.exe를 찾을 수 없습니다. 윈도우에 ffmpeg가 설치되어 있는지 확인하세요.")

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
            print(f"\n[오류 발생]: {e}")
            play_audio("죄송합니다. 해당 질문에는 답변 해드릴 수 없습니다.")