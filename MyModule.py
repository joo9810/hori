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
    if city == "현재위치": city = "대구 달서구"

    address_headers = {"Authorization": f"KakaoAK {ADDRESS_API_KEY}"}
    address_params = {"query": city}

    try:
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

        # print(weather_info)

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
        return {"alarms": [], "count": 0}
    
    with open(ALARM_FILE, "r", encoding="utf-8") as f:
        alarms = json.load(f)

    # print(alarms)

    return {"alarms": alarms, "count": len(alarms)}

def set_alarms(
        hour: int,
        minute: int = 0,
        relative_date: int = None,
        label: str = "알람",
        days: list = None,
        repeat: bool = False
    ):
    """
    사용자가 말한 시간과 요일 정보를 바탕으로 알람을 등록
    """
    if days is None:
        days = [0] * 7

    data = get_alarms()
    alarms = data["alarms"]
    days_list = ["월", "화", "수", "목", "금", "토", "일"]

    # 요일이 명시되었다면 relative_date는 계산하지 않음
    # 만약에 오늘이 화요일인데 사용자가 "모레 수요일 저녁 7시에 식사 알람 등록해줘." <= 모순 발생
    # 일반적으로 relative_date보다 days가 더 구체적인 의도일 가능성이 높으므로 days를 우선적으로 사용
    if any(day == 1 for day in days):   # 리스트의 값 중에 하나라도 1이 있으면 해당 요일을 명시했다는 의미이므로 그 요일을 사용
        pass
    elif relative_date is not None:
        weekday_num = (datetime.today().weekday() + relative_date) % 7
        days[weekday_num] = 1

    # 병합된 알람이 있을 시에 None이 아니게 됨
    target_alarm = None

    # 기존 알람 탐색 및 중복 요일 체크
    for alarm in alarms:
        # 알람의 시간과 내용이 모두 같을 경우 (중복 처리 할지, 요일을 합칠지)
        if alarm['hour'] == hour and alarm['minute'] == minute and alarm['label'] == label:
            # 요일 리스트 합치기
            merged_days = [x + y for x, y in zip(days, alarm['days'])]
            # 예) a = [1, 0, 0, 0, 0, 0, 1], b = [0, 1, 0, 0, 0, 0, 0]
            # 결과) [1, 1, 0, 0, 0, 0, 1]

            overlap_days_list = [days_list[idx] for idx, day in enumerate(merged_days) if day >= 2]
            # 리스트에 2이상(겹치는 경우)의 부분이 존재하면 중복 안내
            # if any(day >= 2 for day in merged_days):
            if overlap_days_list:
                return {
                    "status": "error",
                    "message": f"이미 해당 시간에 겹치는 요일{overlap_days_list}의 알람이 있습니다."
                }
            # 안내 메시지용 요일 리스트
            bef_alarm_days_list = [days_list[idx] for idx, day in enumerate(alarm['days']) if day == 1]
            add_alarm_days_list = [days_list[idx] for idx, day in enumerate(days) if day == 1]
            # 업데이트 할 타겟 알람 설정
            target_alarm = alarm
            target_alarm['days'] = merged_days  # 중복 없으면 병합된 리스트 적용
            break

    # 새 알람 추가 또는 업데이트
    if target_alarm:    # 병합이 된 경우
        message = f"기존 알람{bef_alarm_days_list}에 요일{add_alarm_days_list}을 추가했습니다."
        final_days = target_alarm['days']
    else:   # 병합이 안 된 경우
        new_alarm = {
            "hour": hour,
            "minute": minute,
            "label": label,
            "days": days,
            "repeat": repeat
        }
        alarms.append(new_alarm)
        message = "알람을 성공적으로 설정했습니다."
        final_days = days

    # 파일 저장
    with open(ALARM_FILE, "w", encoding="utf-8") as f:
        json.dump(alarms, f, ensure_ascii=False, indent=4)

    return {
        "status": "success",
        "hour": hour,
        "minute": minute,
        "label": label,
        "days": final_days,
        "repeat": repeat,
        "message": message
    }

def delete_alarms(
        hour: int = None,
        minute: int = None,
        label: str = None,
        repeat_days: list = None
    ):
    """
    등록된 알람 중 조건(시간, 이름, 요일)이 일치하는 알람을 찾아 삭제
    """
    data = get_alarms()
    alarms = data["alarms"] if isinstance(data, dict) else []

    if not alarms:
        return {"status": "error", "message": "삭제할 알람이 없습니다."}

    new_alarms = []
    deleted_alarms = []
    deleted_count = 0

    for alarm in alarms:
        # 매칭 조건 확인 (입력된 값이 있는 경우에만 비교)
        is_match = True

        if hour is not None and alarm.get('hour') != hour:
            is_match = False
        if minute is not None and alarm.get('minute') != minute:
            is_match = False
        if label is not None and (label not in alarm.get('label')):
            is_match = False
        if repeat_days is not None and alarm.get('repeat_days') != repeat_days:
            is_match = False

        # 모든 입력 조건이 일치하면 삭제 대상으로 간주
        if is_match and any([hour is not None, label is not None, repeat_days is not None]):
            deleted_count += 1
            deleted_alarms.append(alarm)
        else:
            new_alarms.append(alarm)

    if deleted_count == 0:
        return {"status": "fail", "message": "일치하는 알람을 찾을 수 없습니다."}
    
    # 파일 저장
    with open(ALARM_FILE, "w", encoding="utf-8") as f:
        json.dump(new_alarms, f, ensure_ascii=False, indent=4)

    return {
        "status": "success",
        "deleted_count": deleted_count,
        "deleted_alarms": deleted_alarms,
        "message": f"성공적으로 {deleted_count}개의 알람을 삭제했습니다."
    }