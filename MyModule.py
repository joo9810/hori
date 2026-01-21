import os
import json
import math
import requests
from datetime import datetime, timedelta

ADDRESS_API_KEY = "17a519eccd6f79f1bbbc522ec7defba6"
WEATHER_API_KEY = "09834c917ca499fc931a9e925cbf582f6b830a9ef8211ad99759c18ceb1af7a5"
keyword_url = "https://dapi.kakao.com/v2/local/search/keyword.json"
address_url = "https://dapi.kakao.com/v2/local/search/address.json"
weather_url = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"

# 도구 함수 정의
def get_current_time():
    now = datetime.now()
    hour = now.hour
    minute = now.minute
    second = now.second
    return {
        "hour": hour,
        "minute": minute,
        "second": second
    }

def get_current_date():
    now = datetime.now()
    year = now.year
    month = now.month
    day = now.day
    day_of_week = now.strftime("%A")
    return {
        "year": year,
        "month": month,
        "day": day,
        "day_of_week": day_of_week
    }

def convert_to_grid(lat, lon):
    # 기상청 변환 상수
    RE = 6371.00877  # 지구 반경(km)
    GRID = 5.0       # 격자 간격(km)
    SLAT1 = 30.0     # 투영 위도1(degree)
    SLAT2 = 60.0     # 투영 위도2(degree)
    OLON = 126.0     # 기준점 경도(degree)
    OLAT = 38.0      # 기준점 위도(degree)
    XO = 43          # 기준점 X좌표(GRID)
    YO = 136         # 기준점 Y좌표(GRID)

    DEGRAD = math.pi / 180.0
    
    re = RE / GRID
    slat1 = SLAT1 * DEGRAD
    slat2 = SLAT2 * DEGRAD
    olon = OLON * DEGRAD
    olat = OLAT * DEGRAD

    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = math.pow(sf, sn) * math.cos(slat1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re * sf / math.pow(ro, sn)
    
    ra = math.tan(math.pi * 0.25 + (lat) * DEGRAD * 0.5)
    ra = re * sf / math.pow(ra, sn)
    theta = lon * DEGRAD - olon
    if theta > math.pi: theta -= 2.0 * math.pi
    if theta < -math.pi: theta += 2.0 * math.pi
    theta *= sn
    
    nx = math.floor(ra * math.sin(theta) + XO + 0.5)
    ny = math.floor(ro - ra * math.cos(theta) + YO + 0.5)
    
    return nx, ny

def convert_base_time():
    base_time_list = [2300, 2000, 1700, 1400, 1100, 800, 500, 200]

    current_int_time = int(datetime.now().strftime("%H%M")) - 10

    for base_time in base_time_list:
        if current_int_time >= base_time:
            return f"{base_time:>04}"

def get_weather(city: str):
    if city == "현재위치": city = "대구 신당동"

    address_headers = {"Authorization": f"KakaoAK {ADDRESS_API_KEY}"}
    address_params = {"query": city}

    address_response = requests.get(address_url, headers=address_headers, params=address_params)
    address_data = address_response.json()  

    documents = address_data['documents'][0]
    lon = float(documents['x'])
    lat = float(documents['y'])
    nx, ny = convert_to_grid(lat, lon)

    city_info = documents['address']['address_name']

    weather_params ={'serviceKey' : WEATHER_API_KEY, 
         'pageNo' : '1', 
         'numOfRows' : '10', 
         'dataType' : 'JSON', 
         'base_date' : datetime.now().strftime("%Y%m%d"), 
         'base_time' : convert_base_time(), 
         'nx' : str(nx), 
         'ny' : str(ny)
    }

    weather_response = requests.get(weather_url, weather_params)
    weather_data = weather_response.json()

    try:
        weather_info = dict()
        weather_info['city'] = city_info

        SKY_dict = {'1': '맑음', '3': '구름많음', '4': '흐림'}
        PTY_dict = {'0': '없음', '1': '비', '2': '비/눈', '3': '눈', '4': '소나기'}

        for item in weather_data['response']['body']['items']['item']:
            category = item['category']
            if category == 'SKY':
                weather_info['sky_condition'] = SKY_dict[item['fcstValue']]
            if category == 'PTY':
                weather_info['precipitation_type'] = PTY_dict[item['fcstValue']]
            if category == 'TMP':
                temp = int(item['fcstValue'])
                if temp >= 0:
                    weather_info['temperature'] = item['fcstValue'] + '도'
                else:
                    weather_info['temperature'] = '영하 ' + item['fcstValue'][1:] + '도'

        print(weather_info)

        return weather_info

    except:
        no_weather_info = {
            "city": city,
            "message": 'city not found'
        }

        # print(no_weather_info)

        return no_weather_info

def search_address(location):

    headers = {"Authorization": f"KakaoAK {ADDRESS_API_KEY}"}
    params = {"query": location}

    address_response = requests.get(keyword_url, headers=headers, params=params)
    address_data = address_response.json()

    # print(address_data)

    try:
        road_address_name = address_data['documents'][0]['road_address_name']
        place_name = address_data['documents'][0]['place_name']

        address_info = {
            "road_address_name": road_address_name,
            "place_name": place_name
        }

        print(address_info)

        return address_info
    
    except :
        no_address_info = {
            "location": location,
            "message": "location not found"
        }

        # print(no_address_info)

        return no_address_info

ALARM_FILE = "alarms.json"

def get_alarms():
    """현재 등록된 모든 알람 목록을 가져옴"""
    if not os.path.exists(ALARM_FILE):
        return {"alarms": [], "count": 0, "message": "현재 설정된 알람이 없습니다."}
    
    with open(ALARM_FILE, "r", encoding="utf-8") as f:
        alarms = json.load(f)

    print(alarms)

    return {
        "alarms": alarms,
        "count": len(alarms),
        "message": "알람 목록을 성공적으로 불러왔습니다." if alarms else "현재 설정된 알람이 없습니다."
    }

def set_alarms(message=None, year=None, month=None, day=None, hour=None, minute=None, relative_day=0):
    """
    relative_day: 오늘=0, 내일=1, 모레=2 등으로 LLM이 숫자를 넘겨줌
    """
    data = get_alarms()
    alarms = data["alarms"] if isinstance(data, dict) else []

    # 기준 시간 설정 (현재 시간)
    now = datetime.now()

    # 날짜 계산
    target_date = datetime(
        year if year else now.year,
        month if month else now.month,
        day if day else now.day,
        hour if hour else now.hour,
        minute if minute else 0
    )

    # relative_day가 있으면 날짜를 더함
    if relative_day:
        target_date = target_date + timedelta(days=relative_day)

    # 최종 문자열 생성 (YYYYMMDDTHHMM)
    alarm_time = target_date.strftime("%Y%m%dT%H%M")

    if message == None:
        message = f"{target_date.month}월 {target_date.day}일 {target_date.hour}시 {target_date.minute}분 알람"

    # 중복 체크
    for alarm in alarms:
        if alarm['time'] == alarm_time and alarm['message'] == message:
                
                print(alarms)

                return {
                    "status": "error",
                    "time": alarm_time,
                    "message_content": message,
                    "message": f"같은 시간에 동일한 내용의 알람이 등록되어 있습니다."
                }
        
    # 등록
    new_alarm = {"time": alarm_time, "message": message}
    alarms.append(new_alarm)

    with open(ALARM_FILE, "w", encoding="utf-8") as f:
        json.dump(alarms, f, ensure_ascii=False, indent=4)

    print(alarms)

    return {
        "status": "success",
        "time": alarm_time,
        "message_content": message,
        "message": "알람을 성공적으로 설정했습니다."
    }

def delete_alarm(message=None, year=None, month=None, day=None, hour=None, minute=None, relative_day=0):
    """
    입력된 시간과 메시지 정보를 조합하여 일치하는 알람을 찾아 삭제
    """
    data = get_alarms()
    alarms = data["alarms"] if isinstance(data, dict) else []

    if not alarms:
        print(alarms)
        return {
            "status": "error",
            "message": "삭제할 알람이 없습니다."
        }

    # 시간 정보가 하나라도 들어왔을 때만 시간 비교 수행
    has_time_input = any([year, month, day, hour, minute, relative_day != 0])
    target_time_str = None

    if has_time_input:
        now = datetime.now()
        # 입력되지 않은 값은 현재 시간 기준으로 채우기
        target_date = datetime(
            year if year else now.year,
            month if month else now.month,
            day if day else now.day,
            hour if hour else now.hour,
            minute if minute else 0
        )
        # 상대 날짜 계산 적용
        if relative_day:
            target_date = target_date + timedelta(days=relative_day)

        target_time_str = target_date.strftime("%Y%m%dT%H%M")

    new_alarms = []
    deleted_count = 0
    found_time_but_different_message = False

    for alarm in alarms:
        is_time_match = (target_time_str is None) or (alarm['time'] == target_time_str) # 시간을 말하지 않았거나 시간이 일치할때
        is_message_match = (message is None) or (message in alarm['message']) # 알람 내용을 말하지 않았거나 일치할때

        if is_time_match and is_message_match:
            deleted_count += 1 # 삭제 대상
        else:
            new_alarms.append(alarm) # 유지 대상

    # 결과에 따른 응답 처리
    if deleted_count == 0: # 삭제된 알람이 없을때
        if has_time_input and message: # 시간과 알람 내용이 모두 있을때
            return {
                "status": "fail",
                "message": f"{target_date.hour}시에는 '{message}' 알람이 등록되어 있지 않습니다."
            }
        elif has_time_input: # 시간만 있을때
            return {
                "status": "fail",
                "message": f"{target_date.hour}시에는 등록된 알람이 없습니다."
            }
        else:
            return {
                "status": "fail",
                "message": f"'{message}' 내용을 포함한 알람을 찾을 수 없습니다."
            }
    
    # 최종 결과 저장
    with open(ALARM_FILE, "w", encoding="utf-8") as f:
        json.dump(new_alarms, f, ensure_ascii=False, indent=4)

    return {
        "status": "success",
        "message": f"성공적으로 {deleted_count}개의 알람을 삭제했습니다."
    }