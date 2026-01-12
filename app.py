import requests
import json
import datetime
import math
from flask import Flask, render_template, jsonify, request
import os
from dotenv import load_dotenv
load_dotenv()
ODPT_API_KEY = os.getenv("ODPT_API_KEY")
app = Flask(__name__)


# 主要路線定義
LINES_DB = [
    # --- JR東日本 ---
    {"id": "odpt.Railway:JR-East.ChuoRapid", "name": "JR 中央線快速"},
    {"id": "odpt.Railway:JR-East.Yamanote", "name": "JR 山手線"},
    {"id": "odpt.Railway:JR-East.KeihinTohokuNegishi", "name": "JR 京浜東北線"},
    {"id": "odpt.Railway:JR-East.ChuoSobueLocal", "name": "JR 総武線(各停)"},
    {"id": "odpt.Railway:JR-East.SaikyoKawagoe", "name": "JR 埼京線"},
    {"id": "odpt.Railway:JR-East.JobanRapid", "name": "JR 常磐線(快速)"},
    {"id": "odpt.Railway:JR-East.JobanLocal", "name": "JR 常磐線(各停)"},
    {"id": "odpt.Railway:JR-East.ShonanShinjuku", "name": "JR 湘南新宿ライン"},
    # --- 東京メトロ ---
    {"id": "odpt.Railway:TokyoMetro.Ginza", "name": "東京メトロ 銀座線"},
    {"id": "odpt.Railway:TokyoMetro.Marunouchi", "name": "東京メトロ 丸ノ内線"},
    {"id": "odpt.Railway:TokyoMetro.Hibiya", "name": "東京メトロ 日比谷線"},
    {"id": "odpt.Railway:TokyoMetro.Tozai", "name": "東京メトロ 東西線"},
    {"id": "odpt.Railway:TokyoMetro.Chiyoda", "name": "東京メトロ 千代田線"},
    {"id": "odpt.Railway:TokyoMetro.Yurakucho", "name": "東京メトロ 有楽町線"},
    {"id": "odpt.Railway:TokyoMetro.Hanzomon", "name": "東京メトロ 半蔵門線"},
    {"id": "odpt.Railway:TokyoMetro.Namboku", "name": "東京メトロ 南北線"},
    {"id": "odpt.Railway:TokyoMetro.Fukutoshin", "name": "東京メトロ 副都心線"},
    # --- 都営地下鉄 ---
    {"id": "odpt.Railway:Toei.Asakusa", "name": "都営 浅草線"},
    {"id": "odpt.Railway:Toei.Mita", "name": "都営 三田線"},
    {"id": "odpt.Railway:Toei.Shinjuku", "name": "都営 新宿線"},
    {"id": "odpt.Railway:Toei.Oedo", "name": "都営 大江戸線"},
    {"id": "odpt.Railway:Toei.NipporiToneri", "name": "都営 日暮里・舎人ライナー"},
    # --- 私鉄 ---
    {"id": "odpt.Railway:Keio.Keio", "name": "京王電鉄 京王線"},
    {"id": "odpt.Railway:Keio.Inokashira", "name": "京王電鉄 井の頭線"},
    {"id": "odpt.Railway:Odakyu.Odawara", "name": "小田急電鉄 小田原線"},
]

DEFAULT_LAT = 35.690921
DEFAULT_LON = 139.700258

# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def get_train_status(railway_id):
    """運行情報テキストを取得"""
    url = "https://api.odpt.org/api/v4/odpt:TrainInformation"
    params = {"acl:consumerKey": ODPT_API_KEY, "odpt:railway": railway_id}
    try:
        res = requests.get(url, params=params, timeout=2)
        data = res.json()
        if data:
            return data[0].get("odpt:trainInformationText", {}).get("ja", "平常運転")
        return "平常運転"
    except: return "情報なし"

def get_line_realtime_details(railway_id):
    """リアルタイム混雑度(遅延度)を算出"""
    url = "https://api.odpt.org/api/v4/odpt:Train"
    params = {"acl:consumerKey": ODPT_API_KEY, "odpt:railway": railway_id}
    try:
        res = requests.get(url, params=params, timeout=3)
        trains = res.json()
        if not trains:
            return {"level": 0, "msg": "稼働なし", "train_count": 0, "max_delay": 0}

        train_count = len(trains)
        delays = [t.get("odpt:delay", 0) for t in trains]
        max_delay_min = math.ceil(max(delays) / 60) if delays else 0

        if max_delay_min >= 10:
            return {"level": 3, "msg": f"🔴 激混み (最大{max_delay_min}分遅れ)", "train_count": train_count, "max_delay": max_delay_min}
        elif max_delay_min >= 3:
            return {"level": 2, "msg": f"🟡 混雑 (最大{max_delay_min}分遅れ)", "train_count": train_count, "max_delay": max_delay_min}
        else:
            return {"level": 1, "msg": "🟢 スムーズ", "train_count": train_count, "max_delay": 0}
    except Exception as e:
        print(f"Train API Error: {e}")
        return {"level": 0, "msg": "データ取得不可", "train_count": 0, "max_delay": 0}

def get_station_geo(station_id):
    if not station_id: return None
    url = "https://api.odpt.org/api/v4/odpt:Station"
    params = {"acl:consumerKey": ODPT_API_KEY, "owl:sameAs": station_id}
    try:
        res = requests.get(url, params=params).json()
        if res:
            return {"lat": res[0]["geo:lat"], "lon": res[0]["geo:long"]}
    except: pass
    return None

def get_bike_ports_by_location(lat, lon):
    """シェアサイクルポート検索 (既存機能)"""
    if not lat or not lon: return []
    info_url = "https://api-public.odpt.org/api/v4/gbfs/docomo-cycle-tokyo/station_information.json"
    status_url = "https://api-public.odpt.org/api/v4/gbfs/docomo-cycle-tokyo/station_status.json"
    params = {"acl:consumerKey": ODPT_API_KEY}
    
    try:
        info_res = requests.get(info_url, params=params).json()
        status_res = requests.get(status_url, params=params).json()
        stations_info = {s["station_id"]: s for s in info_res.get("data", {}).get("stations", [])}
        stations_status = {s["station_id"]: s for s in status_res.get("data", {}).get("stations", [])}
        
        results = []
        for st_id, info in stations_info.items():
            status = stations_status.get(st_id)
            if not status: continue
            
            p_lat, p_lon = info["lat"], info["lon"]
            d_lat = p_lat - lat
            d_lon = p_lon - lon
            dist_km = math.sqrt(d_lat**2 + d_lon**2) * 111
            
            if dist_km > 0.5: continue
            
            results.append({
                "type": "bike",
                "name": info["name"], "lat": p_lat, "lon": p_lon,
                "bikes_available": status["num_bikes_available"],
                "docks_available": status["num_docks_available"], 
                "dist": round(dist_km * 1000)
            })
        
        results.sort(key=lambda x: x['dist'])
        return results[:10]
    except: return []

# ★【新規追加】バス停検索関数
def get_bus_stops_by_location(lat, lon):
    """現在地周辺のバス停を検索 (OpenStreetMap利用)"""
    if not lat or not lon: return []
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": "bus stop",
        "format": "json",
        "limit": 10,
        "viewbox": f"{lon-0.005},{lat-0.005},{lon+0.005},{lat+0.005}", # 約500m範囲
        "bounded": 1,
        "countrycodes": "jp"
    }
    headers = {'User-Agent': 'RailEscapeApp/1.0'}
    
    try:
        res = requests.get(url, params=params, headers=headers).json()
        results = []
        # バス路線情報の例（実際のAPIやオープンデータから取得可能）
        bus_line_info = {
            "渋谷": {"line": "都営バス 渋谷営業所", "destination": "新宿駅"},
            "新宿": {"line": "京王バス", "destination": "池袋駅"},
            "東京": {"line": "都営バス", "destination": "浜松町"},
            "品川": {"line": "京急バス", "destination": "羽田空港"},
            "池袋": {"line": "東武バス", "destination": "赤坂見附"},
            "上野": {"line": "都営バス", "destination": "浅草"},
            "浅草": {"line": "都営バス", "destination": "押上"},
            "秋葉原": {"line": "都営バス", "destination": "大手町"},
        }
        
        for item in res:
            p_lat, p_lon = float(item["lat"]), float(item["lon"])
            d_lat = p_lat - lat
            d_lon = p_lon - lon
            dist_km = math.sqrt(d_lat**2 + d_lon**2) * 111
            
            name = item["display_name"].split(",")[0]
            
            # バス停名から路線情報を抽出（簡易版）
            bus_line = "バス路線"
            bus_dest = "目的地"
            for key, info in bus_line_info.items():
                if key in name:
                    bus_line = info["line"]
                    bus_dest = info["destination"]
                    break

            results.append({
                "type": "bus",
                "name": name, 
                "lat": p_lat, 
                "lon": p_lon,
                "line": bus_line,
                "destination": bus_dest,
                "bikes_available": 99, # ダミー値
                "docks_available": 99,
                "dist": round(dist_km * 1000)
            })
        
        results.sort(key=lambda x: x['dist'])
        return results
    except Exception as e:
        print(f"Bus API Error: {e}")
        return []

# ---------------------------------------------------------
# Routes
# ---------------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/lines')
def api_lines():
    return jsonify(LINES_DB)

@app.route('/api/stations_list')
def api_stations_list():
    line_id = request.args.get('line_id')
    if not line_id: return jsonify([])
    
    # 路線情報(順序)と駅情報(座標)を取得
    railway_url = "https://api.odpt.org/api/v4/odpt:Railway"
    railway_params = {"acl:consumerKey": ODPT_API_KEY, "owl:sameAs": line_id}
    
    station_url = "https://api.odpt.org/api/v4/odpt:Station"
    station_params = {"acl:consumerKey": ODPT_API_KEY, "odpt:railway": line_id}

    try:
        railway_res = requests.get(railway_url, params=railway_params).json()
        station_res = requests.get(station_url, params=station_params).json()
        
        if not railway_res or not station_res: return jsonify([])

        station_map = {}
        for s in station_res:
            s_id = s["owl:sameAs"]
            station_map[s_id] = {
                "id": s_id,
                "name": s["odpt:stationTitle"]["ja"],
                "lat": s.get("geo:lat"),
                "lon": s.get("geo:long")
            }

        ordered_stations = []
        station_order_list = railway_res[0].get("odpt:stationOrder", [])
        
        for item in station_order_list:
            st_id = item["odpt:station"]
            if st_id in station_map:
                ordered_stations.append(station_map[st_id])
        
        used_ids = set([s["id"] for s in ordered_stations])
        for s_id, s_data in station_map.items():
            if s_id not in used_ids:
                ordered_stations.append(s_data)

        return jsonify(ordered_stations)

    except Exception as e:
        print(f"Station List Error: {e}")
        return jsonify([])

@app.route('/api/search_place')
def search_place():
    q = request.args.get('q')
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": q, "format": "json", "countrycodes": "jp", "limit": 1}
    try:
        headers = {'User-Agent': 'RailEscapeApp/1.0'}
        res = requests.get(url, params=params, headers=headers).json()
        if len(res) > 0:
            top = res[0]
            return jsonify({"name": top['display_name'].split(',')[0], "lat": float(top['lat']), "lon": float(top['lon'])})
    except: pass
    return jsonify({"error": "Not found"})

@app.route('/api/station_timetable')
def api_station_timetable():
    req_st_id = request.args.get('station_id') 
    line_id = request.args.get('line_id')
    target_time_str = request.args.get('time', '08:00')
    user_cal = request.args.get('calendar') 
    if not req_st_id or not line_id: return jsonify([])
    if not user_cal:
        user_cal = "SaturdayHoliday" if datetime.datetime.now().weekday() >= 5 else "Weekday"

    url = "https://api.odpt.org/api/v4/odpt:StationTimetable"
    params = {"acl:consumerKey": ODPT_API_KEY, "odpt:station": req_st_id, "odpt:railway": line_id}
    
    try:
        res = requests.get(url, params=params).json()
        if not res:
            parts = req_st_id.split(':')
            if len(parts) == 2:
                body_parts = parts[1].split('.')
                if len(body_parts) >= 3:
                    alt_id = f"{parts[0]}:{body_parts[0]}.{body_parts[-1]}"
                    params["odpt:station"] = alt_id
                    res = requests.get(url, params=params).json()
        if not res:
            params.pop("odpt:railway")
            res = requests.get(url, params=params).json()
        if not res: return jsonify([])
        
        def to_mins(t_str):
            h, m = map(int, t_str.split(':'))
            return h * 60 + m
        target_mins = to_mins(target_time_str)
        candidates = []

        for tt in res:
            data_line = tt.get("odpt:railway", "")
            if line_id and data_line and data_line != line_id and "JR-East" not in line_id:
                continue

            cal_id = tt.get("odpt:calendar", "")
            is_match = False
            if user_cal == "Weekday":
                if "Weekday" in cal_id: is_match = True
            else:
                if "Saturday" in cal_id or "Holiday" in cal_id: is_match = True
            
            if not is_match and len(res) <= 3: is_match = True
            if not is_match: continue

            for train in tt.get("odpt:stationTimetableObject", []):
                dep = train.get("odpt:departureTime")
                if not dep: continue
                if target_mins - 30 <= to_mins(dep) <= target_mins + 30:
                    dest = train.get("odpt:destinationStation", [])
                    d_name = dest[0].split('.')[-1] if dest else "Unknown"
                    t_type = train.get("odpt:trainType", "").split('.')[-1].replace('JR-East.', '')
                    candidates.append({"time": dep, "dest": d_name, "type": t_type})
        
        seen = set()
        unique = []
        for c in candidates:
            k = f"{c['time']}-{c['dest']}"
            if k not in seen:
                seen.add(k)
                unique.append(c)
        unique.sort(key=lambda x: x['time'])
        return jsonify(unique)
    except: return jsonify([])

# ★【変更点】ここが今回ロジックが変わった場所です
@app.route('/api/check_timeline', methods=['POST'])
def check_timeline():
    route_data = request.json
    rent_lat = float(request.args.get('lat', DEFAULT_LAT))
    rent_lon = float(request.args.get('lon', DEFAULT_LON))
    
    # ★ ここで「バス」か「自転車」かを受け取る
    escape_method = request.args.get('method', 'bike') 

    bike_target = request.json[0].get('bike_target') if route_data else None
    
    timeline_results = []
    has_trouble = False
    danger_words = ["遅れ", "見合わせ", "運休", "事故", "折返し"]
    
    for segment in route_data:
        if 'line_id' not in segment: continue
        status_text = get_train_status(segment['line_id'])
        is_alert = any(w in status_text for w in danger_words)
        
        realtime_info = get_line_realtime_details(segment['line_id'])
        
        if segment.get('force_delay'):
            status_text = "【TEST】運転見合わせ"
            is_alert = True
            realtime_info = {"level": 3, "msg": "🔴 TEST激混み (遅延大)", "train_count": 99, "max_delay": 30}
        
        if realtime_info['level'] >= 2: is_alert = True
        if is_alert: has_trouble = True
        
        start_geo = get_station_geo(segment.get('start_st_id'))
        
        timeline_results.append({
            "line_name": segment.get('line_name'),
            "start_station": segment.get('start_st_name'),
            "end_station": segment.get('end_st_name'),
            "start_geo": start_geo,
            "time": segment.get('time'),
            "status": status_text,
            "alert": is_alert,
            "congestion": realtime_info 
        })
    
    # ★ ここで分岐: 遅延時は「運行中の路線の駅」を起点/終点としてバスまたは自転車ポートを検索
    start_spots = []
    end_spots = []

    # デフォルトの出発/到着ポイント
    start_point = {"lat": rent_lat, "lon": rent_lon}
    end_point = None

    # 優先する目的地は JSON 内に渡された bike_target（例: 目的地の緯度経度）
    if bike_target and isinstance(bike_target, dict) and bike_target.get('lat') and bike_target.get('lon'):
        end_point = {"lat": float(bike_target['lat']), "lon": float(bike_target['lon'])}
    else:
        # 最終セグメントの降車駅を目的地とする（取れなければ開始駅を代用）
        try:
            last_seg = route_data[-1]
            last_end_geo = get_station_geo(last_seg.get('end_st_id'))
            if last_end_geo:
                end_point = last_end_geo
            else:
                end_point = get_station_geo(last_seg.get('start_st_id'))
        except Exception:
            end_point = None

    # 遅延がある場合、運行中の路線の駅を起点に設定する
    if has_trouble:
        # timeline_results と route_data のインデックスは対応している
        alert_idxs = [i for i, t in enumerate(timeline_results) if t.get('alert')]
        op_idxs = [i for i, t in enumerate(timeline_results) if not t.get('alert')]

        if alert_idxs:
            first_alert = alert_idxs[0]
            # 遅延より前に運行中の路線があればその降車駅を起点にする
            prev_ops = [i for i in op_idxs if i < first_alert]
            if prev_ops:
                idx = prev_ops[-1]
                seg = route_data[idx]
                geo = get_station_geo(seg.get('end_st_id'))
                if geo:
                    start_point = geo
            else:
                # 遅延より前に運行中の路線がない場合は、遅延路線の乗車駅を起点にする
                seg = route_data[first_alert]
                geo = get_station_geo(seg.get('start_st_id'))
                if geo:
                    start_point = geo

    # 指定手段に基づき起点/終点周辺のスポットを検索
    if escape_method == 'bus':
        start_spots = get_bus_stops_by_location(start_point.get('lat'), start_point.get('lon'))
        if end_point:
            end_spots = get_bus_stops_by_location(end_point.get('lat'), end_point.get('lon'))
    else:
        start_spots = get_bike_ports_by_location(start_point.get('lat'), start_point.get('lon'))
        if end_point:
            end_spots = get_bike_ports_by_location(end_point.get('lat'), end_point.get('lon'))

    # ★ バス代替案情報の生成
    bus_alternative_info = None
    if has_trouble and escape_method == 'bus':
        alert_idx = next((i for i, t in enumerate(timeline_results) if t.get('alert')), None)
        if alert_idx is not None:
            # 遅延している路線の降車駅周辺のバス停を検索
            alert_seg = route_data[alert_idx]
            alert_end_geo = get_station_geo(alert_seg.get('end_st_id'))
            
            if alert_end_geo:
                end_spots = get_bus_stops_by_location(alert_end_geo.get('lat'), alert_end_geo.get('lon'))
            
            if start_spots and end_spots:
                start_bus = start_spots[0]
                end_bus = end_spots[0]
                
                # バス移動時間を推定（起点と終点間の距離から）
                import math
                lat1, lon1 = start_point.get('lat'), start_point.get('lon')
                lat2, lon2 = end_bus.get('lat'), end_bus.get('lon')
                if lat1 and lon1 and lat2 and lon2:
                    # 2点間の直線距離（km）
                    d_lat = lat2 - lat1
                    d_lon = lon2 - lon1
                    dist_km = math.sqrt(d_lat**2 + d_lon**2) * 111
                    # バスの移動時間を推定（時速20km、信号待ちで約1分/km）
                    travel_time_min = max(int(dist_km * 3), 10)
                else:
                    travel_time_min = 20  # デフォルト20分
                
                # 到着時刻を計算
                original_time_str = timeline_results[alert_idx].get('time', '08:00')
                h, m = map(int, original_time_str.split(':'))
                arrival_min = (h * 60 + m + travel_time_min) % 1440
                arrival_h, arrival_m = arrival_min // 60, arrival_min % 60
                arrival_time_str = f"{arrival_h:02d}:{arrival_m:02d}"
                
                bus_alternative_info = {
                    "alert_idx": alert_idx,
                    "start_station": timeline_results[alert_idx].get('start_station'),
                    "end_station": timeline_results[alert_idx].get('end_station'),
                    "original_time": original_time_str,
                    "start_bus_stop": start_bus.get('name', "バス停不明"),
                    "start_bus_line": start_bus.get('line', 'バス路線'),
                    "start_bus_dest": start_bus.get('destination', '目的地'),
                    "end_bus_stop": end_bus.get('name', "バス停不明"),
                    "end_bus_line": end_bus.get('line', 'バス路線'),
                    "end_bus_dest": end_bus.get('destination', '目的地'),
                    "arrival_time": arrival_time_str,
                    "travel_time": travel_time_min
                }

    return jsonify({
        "timeline": timeline_results,
        "has_trouble": has_trouble,
        "rent_ports": start_spots,
        "return_ports": end_spots,
        "start_point": start_point,
        "end_point": end_point,
        "bus_alternative": bus_alternative_info
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)



# ngrok https 5000