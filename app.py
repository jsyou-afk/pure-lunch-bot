import os
import random
import hashlib
import hmac
import time
import threading
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")
KAKAO_REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "")

LAT = 37.5445
LNG = 127.0557
RADIUS = 1000

HEAVY_KEYWORDS = [
    "곱창", "막창", "대창", "보쌈", "족발", "삼겹살", "갈비", "갈비탕",
    "순대", "뼈다귀", "고기집", "구이",
    "양고기", "소곱창", "닭발", "닭볶음탕",
    "훠궈", "스테이크", "바베큐", "BBQ", "양꼬치", "회",
    "이자카야", "술집", "호프", "포장마차",
]


def fetch_restaurants():
    url = "https://dapi.kakao.com/v2/local/search/category.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    restaurants = []
    for page in range(1, 4):
        params = {
            "category_group_code": "FD6",
            "x": LNG,
            "y": LAT,
            "radius": RADIUS,
            "size": 15,
            "page": page,
            "sort": "distance",
        }
        res = requests.get(url, headers=headers, params=params, timeout=10)
        if res.status_code != 200:
            raise Exception(f"Kakao API {res.status_code}: {res.text[:100]}")
        data = res.json()
        docs = data.get("documents", [])
        restaurants.extend(docs)
        if data.get("meta", {}).get("is_end"):
            break
    filtered = [
        r for r in restaurants
        if not any(kw in r.get("category_name", "") + r.get("place_name", "") for kw in HEAVY_KEYWORDS)
    ]
    return filtered if filtered else restaurants


def build_text(place):
    name = place.get("place_name", "알 수 없음")
    category = place.get("category_name", "").split(" > ")[-1]
    address = place.get("road_address_name") or place.get("address_name", "")
    distance = place.get("distance", "")
    url = place.get("place_url", "")
    phone = place.get("phone", "전화번호 없음")
    dist_text = f"{int(distance)}m" if distance else "거리 미상"
    return (
        f"오늘 점심은 여기 어때요?\n\n"
        f"*{name}* ({category})\n"
        f"{address} ({dist_text})\n"
        f"{phone}\n"
        f"<{url}|카카오맵에서 보기>"
    )


def process_lunch(response_url):
    try:
        restaurants = fetch_restaurants()
        if not restaurants:
            text = "근처 음식점을 찾지 못했어요."
        else:
            text = build_text(random.choice(restaurants))
        payload = {"response_type": "in_channel", "text": text}
    except Exception as e:
        payload = {"response_type": "ephemeral", "text": f"오류: {e}"}
    requests.post(response_url, json=payload, timeout=10)


@app.route("/lunch", methods=["POST"])
def lunch():
    response_url = request.form.get("response_url")
    t = threading.Thread(target=process_lunch, args=(response_url,))
    t.daemon = True
    t.start()
    return "", 200


@app.route("/", methods=["GET"])
def health():
    return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
