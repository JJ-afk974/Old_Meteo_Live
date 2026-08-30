import requests
import pandas as pd
import time
import os
import json
from datetime import datetime, timedelta, timezone

# ============================================================
# CONFIGURATION
# ============================================================

FICHIER = "poly_live.csv"

VILLES = {
    "new_york": "new-york",
    "miami": "miami",
}

TYPES_TEMPERATURE = {
    "highest": "highest-temperature",
    "lowest": "lowest-temperature",
}

TIMEOUT = 10


# ============================================================
# SESSION HTTP
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": "Mozilla/5.0 (GitHub Actions Polymarket collector)"
})


# ============================================================
# CONSTRUCTION DU SLUG
# ============================================================

def make_slug(city_slug, date, temperature_type):
    """
    Exemples :

    highest-temperature-in-new-york-on-august-30-2026
    lowest-temperature-in-new-york-on-august-30-2026
    highest-temperature-in-miami-on-august-31-2026
    lowest-temperature-in-miami-on-august-31-2026
    """

    month = date.strftime("%B").lower()
    day = date.day
    year = date.year

    temperature_slug = TYPES_TEMPERATURE[temperature_type]

    return (
        f"{temperature_slug}-in-{city_slug}-on-"
        f"{month}-{day}-{year}"
    )


# ============================================================
# RÉCUPÉRATION DE L'ÉVÉNEMENT
# ============================================================

def fetch_event(slug):

    url = f"https://gamma-api.polymarket.com/events/slug/{slug}"

    try:
        response = session.get(
            url,
            timeout=TIMEOUT
        )

        if response.status_code != 200:
            print(
                f"[EVENT] HTTP {response.status_code} "
                f"pour {slug}"
            )
            return None

        return response.json()

    except requests.RequestException as e:
        print(
            f"[EVENT] Erreur réseau pour {slug}: {e}"
        )
        return None

    except ValueError as e:
        print(
            f"[EVENT] JSON invalide pour {slug}: {e}"
        )
        return None


# ============================================================
# RÉCUPÉRATION DU CARNET
# ============================================================

def fetch_order_book(token_id):

    url = "https://clob.polymarket.com/book"

    try:

        response = session.get(
            url,
            params={"token_id": token_id},
            timeout=TIMEOUT
        )

        if response.status_code != 200:
            print(
                f"[BOOK] HTTP {response.status_code} "
                f"pour token {token_id}"
            )
            return None

        return response.json()

    except requests.RequestException as e:
        print(
            f"[BOOK] Erreur réseau pour {token_id}: {e}"
        )
        return None

    except ValueError as e:
        print(
            f"[BOOK] JSON invalide pour {token_id}: {e}"
        )
        return None


# ============================================================
# BEST BID / BEST ASK
# ============================================================

def get_best_prices(book):

    bids = book.get("bids", [])
    asks = book.get("asks", [])

    # Best bid = prix le plus élevé
    if bids:
        best_bid = max(
            bids,
            key=lambda x: float(x.get("price", 0))
        )
    else:
        best_bid = {
            "price": None,
            "size": None
        }

    # Best ask = prix le plus faible
    if asks:
        best_ask = min(
            asks,
            key=lambda x: float(x.get("price", 999))
        )
    else:
        best_ask = {
            "price": None,
            "size": None
        }

    return best_bid, best_ask


# ============================================================
# PROGRAMME PRINCIPAL
# ============================================================

def main():

    maintenant = datetime.now(timezone.utc)

    date_j0 = maintenant.date()
    date_j1 = date_j0 + timedelta(days=1)

    dates = [
        ("J+0", date_j0),
        ("J+1", date_j1),
    ]

    rows = []

    print("=" * 80)
    print("COLLECTE POLYMARKET - TEMPERATURE")
    print("=" * 80)
    print(f"Date UTC : {maintenant.isoformat()}")
    print()

    # ========================================================
    # VILLES
    # ========================================================

    for ville, ville_slug in VILLES.items():

        # ====================================================
        # HIGHEST / LOWEST
        # ====================================================

        for temperature_type in TYPES_TEMPERATURE:

            # ================================================
            # J+0 / J+1
            # ================================================

            for jour, date in dates:

                slug = make_slug(
                    ville_slug,
                    date,
                    temperature_type
                )

                print("-" * 80)
                print(f"Ville       : {ville}")
                print(f"Température : {temperature_type}")
                print(f"Jour        : {jour}")
                print(f"Date        : {date}")
                print(f"Slug        : {slug}")

                # ============================================
                # EVENT
                # ============================================

                event = fetch_event(slug)

                if event is None:
                    print("Aucun événement récupéré.")
                    continue

                markets = event.get("markets", [])

                if not markets:
                    print(
                        "Événement trouvé mais aucun market."
                    )
                    continue

                print(
                    f"{len(markets)} markets trouvés."
                )

                collecte_le = datetime.now(
                    timezone.utc
                ).isoformat()

                # ============================================
                # MARKETS
                # ============================================

                for market in markets:

                    option = market.get(
                        "groupItemTitle"
                    )

                    if not option:
                        print(
                            "Market sans groupItemTitle, "
                            "ignoré."
                        )
                        continue

                    # ========================================
                    # TOKENS
                    # ========================================

                    try:

                        token_ids = json.loads(
                            market.get(
                                "clobTokenIds",
                                "[]"
                            )
                        )

                    except (
                        json.JSONDecodeError,
                        TypeError
                    ):

                        print(
                            f"Token IDs invalides pour "
                            f"{option}"
                        )
                        continue

                    if not token_ids:
                        print(
                            f"Aucun token pour {option}"
                        )
                        continue

                    # Premier token = YES
                    token_yes = token_ids[0]

                    # ========================================
                    # ORDER BOOK
                    # ========================================

                    book = fetch_order_book(
                        token_yes
                    )

                    if book is None:
                        continue

                    best_bid, best_ask = (
                        get_best_prices(book)
                    )

                    # ========================================
                    # ENREGISTREMENT
                    # ========================================

                    rows.append({

                        "ville": ville,

                        "temperature_type":
                            temperature_type,

                        "jour": jour,

                        "date": str(date),

                        "slug": slug,

                        "option": option,

                        "token_yes": token_yes,

                        "bestBid":
                            best_bid.get("price"),

                        "bidVolume":
                            best_bid.get("size"),

                        "bestAsk":
                            best_ask.get("price"),

                        "askVolume":
                            best_ask.get("size"),

                        "_collecte_le":
                            collecte_le,
                    })

                    print(
                        f"  {option} | "
                        f"bid={best_bid.get('price')} | "
                        f"ask={best_ask.get('price')}"
                    )

                    time.sleep(0.1)

    # ========================================================
    # DATAFRAME
    # ========================================================

    colonnes = [
        "ville",
        "temperature_type",
        "jour",
        "date",
        "slug",
        "option",
        "token_yes",
        "bestBid",
        "bidVolume",
        "bestAsk",
        "askVolume",
        "_collecte_le",
    ]

    data = pd.DataFrame(
        rows,
        columns=colonnes
    )

    # ========================================================
    # AUCUNE DONNÉE
    # ========================================================

    if data.empty:

        print()
        print("=" * 80)
        print("AUCUNE DONNÉE RÉCUPÉRÉE")
        print("=" * 80)

        # Création du fichier s'il n'existe pas
        if not os.path.exists(FICHIER):

            data.to_csv(
                FICHIER,
                index=False
            )

            print(
                f"Fichier vide créé : {FICHIER}"
            )

        else:

            print(
                f"{FICHIER} existe déjà."
            )

        return

    # ========================================================
    # CHARGEMENT DE L'HISTORIQUE
    # ========================================================

    if os.path.exists(FICHIER):

        try:

            ancien = pd.read_csv(
                FICHIER
            )

            data_final = pd.concat(
                [
                    ancien,
                    data
                ],
                ignore_index=True
            )

        except Exception as e:

            print(
                f"Impossible de lire {FICHIER}: {e}"
            )

            data_final = data

    else:

        data_final = data

    # ========================================================
    # SAUVEGARDE
    # ========================================================

    data_final.to_csv(
        FICHIER,
        index=False
    )

    # ========================================================
    # RÉSUMÉ
    # ========================================================

    print()
    print("=" * 80)
    print("COLLECTE TERMINÉE")
    print("=" * 80)

    print(
        f"Nouvelles lignes : {len(data)}"
    )

    print(
        f"Total CSV        : {len(data_final)}"
    )

    print(
        f"Fichier          : {FICHIER}"
    )

    print()
    print("Répartition :")

    print(
        data.groupby(
            [
                "ville",
                "temperature_type",
                "jour"
            ]
        ).size()
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
