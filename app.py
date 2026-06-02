import os
import random
import hashlib
import hmac
import time
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


def verify_slack_signature(req):
    if not SLACK_SIGNING_SECRET:
        return True
    ts = req.headers.get("X-Slack-Request-Timestamp", "")
    if abs(time.time() - float(ts)) > 300:
        return False
    body = req.get_data(as_text=True)
    sig_base = f"v0:{ts}:{body}"
    my_sig = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode(),
        sig_base.encode(),
        hashlib.sha256
    ).hexdigest()
    slack_sig = req.headers.get("X-Slack-Signature", "")
    return hmac.compare_digest(my_sig, slack_sig)


def fetch_restaurants():
    url = "https://dapi.kakao.com/v2/local/search/category.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    restaurants = []
    last_status = None
    last_body = None
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
        res = requests.get(url, headers=headers, params=params, timeout=5)
        last_status = res.status_code
        last_body = res.text[:200]
        if res.status_code != 200:
            break
        data = res.json()
        docs = data.get("documents", [])
        restaurants.extend(docs)
        if data.get("meta", {}).get("is_end"):
            break
    filtered = []
    for r in restaurants:
        combined = r.get("category_name", "") + r.get("place_name", "")
        if not any(kw in combined for kw in HEAVY_KEYWORDS):
            filtered.append(r)
    result = filtered if filtered else restaurants
    return result, last_status, last_body


def build_response(place):
    name = place.get("place_name", "알 수 없음")
    category = place.get("category_name", "").split(" > ")[-1]
    address = place.get("road_address_name") or place.get("address_name", "")
    distance = place.get("distance", "")
    url = place.get("place_url", "")
    phone = place.get("phone", "전화번호 없음")
    dist_text = f"{int(distance)}m" if distance else "거리 미상"
    text = (
        f"오늘 점심은 여기 어때요?\n\n"
        f"*{name}* ({category})\n"
        f"{address} ({dist_text})\n"
        f"{phone}\n"
        f"<{url}|카카오맵에서 보기>"
    )
    return {"response_type": "in_channel", "text": text}


@app.route("/lunch", methods=["POST"])
def lunch():
    if not verify_slack_signature(request):
        return jsonify({"error": "Invalid signature"}), 403
    try:
        restaurants, status, body = fetch_restaurants()
    except Exception as e:
        return jsonify({"response_type": "ephemeral", "text": f"오류: {e}"})
    if not restaurants:
        return jsonify({"response_type": "ephemeral", "text": f"음식점 없음. API 상태: {status}, 응답: {body}"})
    pick = random.choice(restaurants)
    return jsonify(build_response(pick))


@app.route("/", methods=["GET"])
def health():
    return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
