import requests
import time

HH_API_BASE = "https://api.hh.ru"
HH_HEADERS = {
    'User-Agent': 'SkillRadar/1.0 (admin@skillradar.com)',
    'Accept': 'application/json'
}

def test_api():
    print("--- Testing HH.ru API ---")
    try:
        # 1. Ping
        r = requests.get(f"{HH_API_BASE}/dictionaries", headers=HH_HEADERS)
        print(f"1. Dictionaries: {r.status_code} {'✅' if r.status_code == 200 else '❌'}")
        
        # 2. Search
        r = requests.get(f"{HH_API_BASE}/vacancies", params={'text': 'Python', 'per_page': 1}, headers=HH_HEADERS)
        print(f"2. Search: {r.status_code} {'✅' if r.status_code == 200 else '❌'}")
        
        # 3. Vacancy Detail (берем ID из поиска)
        if r.status_code == 200:
            item_id = r.json()['items'][0]['id']
            r = requests.get(f"{HH_API_BASE}/vacancies/{item_id}", headers=HH_HEADERS)
            print(f"3. Details ({item_id}): {r.status_code} {'✅' if r.status_code == 200 else '❌'}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_api()