import requests
import pandas as pd
import os
from datetime import datetime

URL = "https://api.weather.com/v3/wx/observations/current"
PARAMS_BASE = {
    "apiKey": os.environ["WEATHER_API_KEY"],  # on ne mettra plus la clé en dur dans le code
    "language": "en-US",
    "units": "m",
    "format": "json",
    "icaoCode": "LFPB",
}

FICHIER = "lfpb_live.csv"

def fetch_lfpb():
    r = requests.get(URL, params=PARAMS_BASE, timeout=10)
    if r.status_code != 200:
        print(f"Erreur {r.status_code} -> {r.text}")
        return None
    return r.json()

data = fetch_lfpb()
if data:
    data["_collecte_le"] = datetime.now().isoformat()
    df = pd.DataFrame([data])
    df.to_csv(FICHIER, mode="a", header=not os.path.exists(FICHIER), index=False)
    print("Donnée enregistrée")
