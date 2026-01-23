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
        return {"alarms": [], "count": 0, "message": "현재 설정된 알람이 없습니다."}
    
    with open(ALARM_FILE, "r", encoding="utf-8") as f:
        alarms = json.load(f)

    print(alarms)

    return {
        "alarms": alarms,
        "count": len(alarms),
        "message": "알람 목록을 성공적으로 불러왔습니다." if alarms else "현재 설정된 알람이 없습니다."
    }

def set_alarms(
        message=None, 
        year=None, month=None, day=None, 
        hour=None, minute=0, 
        relative_day=0, 
        week_offset=0,      # 이번 주=0, 다음 주=1
        day_of_week=None,   # "월요일", "화요일" 등
        is_ampm_specified=False
    ):
    """
    relative_day: 오늘=0, 내일=1, 모레=2 등으로 LLM이 숫자를 넘겨줌
    """
    data = get_alarms()
    alarms = data["alarms"] if isinstance(data, dict) else []

    # 기준 시간 설정 (현재 시간)
    now = datetime.now()

    # 요일 처리 로직 (day_of_week가 있을 경우)
    if day_of_week:
        # 요일 매핑 (0:월, 1:화, ..., 6:일)
        days_map = {"월요일": 0, "화요일": 1, "수요일": 2, "목요일": 3, "금요일": 4, "토요일": 5, "일요일": 6}
        target_weekday = days_map.get(day_of_week)

        if target_weekday is not None:
            # 현재 요일과 목표 요일 차이 계산
            days_ahead = target_weekday - now.weekday()

            # 다음 주라면 7일을 더함, 이번 주인데 이미 지났어도 7일을 더함
            if week_offset > 0:
                days_ahead += 7 * week_offset
            elif days_ahead < 0: # 이번 주라고 했는데 이미 지난 요일인 경우(사용자 실수) 다음 주로 넘김
                days_ahead += 7

            relative_day = days_ahead

    # 날짜 계산
    target_date = datetime(
        year if year else now.year,
        month if month else now.month,
        day if day else now.day,
        hour if hour is not None else now.hour,
        minute if minute is not None else 0
    )

    # relative_day가 있으면 날짜를 더함
    if relative_day:
        target_date = target_date + timedelta(days=relative_day)

    # 생성된 시간이 '현재보다 과거'일 때만 작동
    if target_date <= now:
        # 사용자가 "오전/오후"를 명확히 말했다면, 12시간 보정을 하지 않고 바로 다음날로 넘김
        if is_ampm_specified:
            target_date = target_date + timedelta(days=1)
        # "오전/오후"를 말하지 않았을 경우
        else:
            # 예) 7시에 알람 설정해줘
            if hour is not None and hour < 12:
                future_attempt = target_date + timedelta(hours=12)
                # 현재가 오후 6시일 경우 12시간 뒤인 오후 7시에 알람이 설정
                if future_attempt > now:
                    target_date = future_attempt
                # 현재가 오후 8시일 경우 12시간 뒤인 오후 7시도 과거이기 때문에 하루 뒤인 내일 오전 7시에 알람이 설정
                else:
                    target_date = target_date + timedelta(days=1)
            # 예) 19시에 알람 설정해줘
            else:
                target_date = target_date + timedelta(days=1)
        

    # 최종 문자열 생성 (YYYYMMDDTHHMM)
    alarm_time = target_date.strftime("%Y%m%dT%H%M")

    if message == None:
        message = f"{target_date.month}월 {target_date.day}일 {target_date.hour}시 {target_date.minute}분 알람"

    # 중복 체크
    for alarm in alarms:
        if alarm['time'] == alarm_time and alarm['message'] == message:
                
                # print(alarms)

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

    # print(alarms)

    days_ko = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    target_weekday_str = days_ko[target_date.weekday()]

    return {
        "status": "success",
        "time": alarm_time,
        "day_of_week": target_weekday_str,  # 요일 정보 추가 (예: "금요일")
        "message_content": message,
        "message": "알람을 성공적으로 설정했습니다."
    }

def delete_alarms(
        message=None, 
        year=None, month=None, day=None, 
        hour=None, minute=0,
        relative_day=0, 
        week_offset=0,      # 이번 주=0, 다음 주=1
        day_of_week=None,   # "월요일", "화요일" 등
        is_ampm_specified=False):
    """
    입력된 시간과 메시지 정보를 조합하여 일치하는 알람을 찾아 삭제
    """
    data = get_alarms()
    alarms = data["alarms"] if isinstance(data, dict) else []

    if not alarms:
        # print(alarms)
        return {"status": "error", "message": "삭제할 알람이 없습니다."}
    
    now = datetime.now()

    # 요일 및 주차 계산 로직
    if day_of_week:
        # 요일 매핑 (0:월, 1:화, ..., 6:일)
        days_map = {"월요일": 0, "화요일": 1, "수요일": 2, "목요일": 3, "금요일": 4, "토요일": 5, "일요일": 6}
        target_weekday = days_map.get(day_of_week)

        if target_weekday is not None:
            # 현재 요일과 목표 요일 차이 계산
            days_ahead = target_weekday - now.weekday()

            # 다음 주라면 7일을 더함, 이번 주인데 이미 지났어도 7일을 더함
            if week_offset > 0:
                days_ahead += 7 * week_offset
            elif days_ahead < 0: # 이번 주라고 했는데 이미 지난 요일인 경우(사용자 실수) 다음 주로 넘김
                days_ahead += 7

            relative_day = days_ahead

    # 시간 정보가 하나라도 들어왔을 때만 시간 비교 수행
    has_time_input = any([year, month, day, hour is not None, minute, relative_day != 0, day_of_week])
    # hour를 is not None으로 둔 이유는 사용자가 자정(12시)
    target_time_str = None

    if has_time_input:
        # 입력되지 않은 값은 현재 시간 기준으로 채우기
        target_date = datetime(
            year if year else now.year,
            month if month else now.month,
            day if day else now.day,
            hour if hour is not None else now.hour,
            minute if minute is not None else 0
        )
        # 상대 날짜 계산 적용
        if relative_day:
            target_date = target_date + timedelta(days=relative_day)

        # 생성된 시간이 '현재보다 과거'일 때만 작동
        if target_date <= now:
            # "오전/오후"를 명확하게 언급했을 경우
            if is_ampm_specified:
                target_date = target_date + timedelta(days=1)
            # "오전/오후"를 언급하지 않았을 경우
            else:
                if hour is not None and hour < 12:
                    future_attempt = target_date + timedelta(hours=12)
                    if future_attempt > now:
                        target_date = future_attempt
                    else:
                        target_date = target_date + timedelta(days=1)
                else:
                    target_date = target_date + timedelta(days=1)

        target_time_str = target_date.strftime("%Y%m%dT%H%M")

    new_alarms = []
    deleted_alarms = []
    deleted_count = 0

    # 날짜 정보는 있지만 구체적인 시(hour)가 입력되지 않았는지 확인
    # hour is None이면 해당 날짜는 모든 알람을 대상으로 함
    is_date_only_search = has_time_input and (hour is None) # 예) "일요일 알람 모두 삭제해줘"

    for alarm in alarms:
        # 시간 매칭 로직 변경
        if target_time_str is None: # 시간을 말하지 않고 메시지만 말했을때 (예: 당뇨약 알람 삭제해줘)
            is_time_match = True
        elif is_date_only_search:
            # 시간(hour)을 안썼다면 날짜 부분(앞 8자리, 예: 20260125)만 일치하는지 확인
            is_time_match = alarm['time'].startswith(target_date.strftime("%Y%m%d"))
        else:
            # 시간까지 썼다면 전체 문자열 일치 확인
            is_time_match = (alarm['time'] == target_time_str)

        is_message_match = (message is None) or (message in alarm['message']) # 알람 내용을 말하지 않았거나 일치할때

        if is_time_match and is_message_match:
            deleted_count += 1 # 삭제 대상
            deleted_alarms.append(alarm)
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
        "deleted_alarms": deleted_alarms,
        "message": f"성공적으로 {deleted_count}개의 알람을 삭제했습니다."
    }