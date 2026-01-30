import math
import requests
from datetime import datetime

WEATHER_API_KEY = ""
ADDRESS_API_KEY = ""
keyword_url = "https://dapi.kakao.com/v2/local/search/keyword.json"
address_url = "https://dapi.kakao.com/v2/local/search/address.json"
weather_url = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"

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
            'numOfRows' : '50', 
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