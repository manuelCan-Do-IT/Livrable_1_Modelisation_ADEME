"""CVRPTW : recherche tabou (SWAP, DEPLACER, ECHANGER LES FINS), étude expérimentale et objectif configurable.

Exécution : python cvrptw_analyse_solomon.py
Graphiques : pip install matplotlib (si nécessaire)
Instances de Solomon (mode "solomon") : pip install vrplib
Cas de test : python tests_cvrptw.py
"""

import csv
import math
import random
import statistics
import time
from collections import deque
from pathlib import Path

# Tolérance sur les horaires. Avec des distances décimales (Solomon),
# Python calcule par exemple 0.1 + 0.2 = 0.30000000000000004 : un camion
# qui arrive pile à la fermeture serait refusé à tort sans cette marge.
EPS = 1e-6


# ============================================================
# 1. GENERER UNE INSTANCE COHERENTE
# ============================================================

def generer_instance(nb_clients, nb_camions, graine=42,
                     repartition="groupes", fenetres_type="larges"):
    """Génère des données et une tournée témoin réalisable.

    repartition : 'groupes' ou 'disperses'
    fenetres_type : 'larges' ou 'serrees'
    La tournée témoin sert uniquement au démarrage de l'algorithme.
    """
    if not 1 <= nb_camions <= nb_clients:
        raise ValueError("Nombre de camions invalide")
    if repartition not in ("groupes", "disperses"):
        raise ValueError("Répartition inconnue")
    if fenetres_type not in ("larges", "serrees"):
        raise ValueError("Type de fenêtres inconnu")

    hasard = random.Random(graine)
    centres = [(hasard.randint(20, 80), hasard.randint(20, 80))
               for _ in range(nb_camions)]
    positions = [(50, 50)]             # Le dépôt a le numéro 0
    groupes = [[] for _ in range(nb_camions)]

    for client in range(1, nb_clients + 1):
        camion = (client - 1) % nb_camions
        if repartition == "groupes":
            x, y = centres[camion]
            position = (x + hasard.randint(-10, 10),
                        y + hasard.randint(-10, 10))
        else:
            position = (hasard.randint(5, 95), hasard.randint(5, 95))
        positions.append(position)
        groupes[camion].append(client)

    # Temps fixes de trajet en minutes, calculés à partir des positions.
    distances = [
        [0 if i == j else max(1, math.ceil(math.dist(positions[i], positions[j]) * 0.6))
         for j in range(nb_clients + 1)]
        for i in range(nb_clients + 1)
    ]
    demandes = [0] + [hasard.randint(1, 4) for _ in range(nb_clients)]
    fenetres = [(480, 1080)] + [(0, 0)] * nb_clients  # Dépôt : 8h-18h
    solution_depart = []

    # Chaque scénario conserve au moins une solution faisable :
    # les fenêtres sont construites autour des passages d'une tournée témoin.
    avant, apres = (20, 30) if fenetres_type == "serrees" else (90, 120)
    for groupe in groupes:
        hasard.shuffle(groupe)
        heure = hasard.randint(480, 660)
        precedent = 0
        for client in groupe:
            heure += distances[precedent][client]
            fenetres[client] = (max(480, heure - avant),
                                min(1080, heure + apres))
            precedent = client
        if heure + distances[precedent][0] > 1080:
            raise ValueError("Tournée témoin trop longue : réduire le nombre de clients")
        solution_depart.append([0] + groupe[:] + [0])

    # Capacité commune : suffisante pour les tournées témoins.
    capacite = max(sum(demandes[c] for c in groupe) for groupe in groupes)
    return {
        "nb_clients": nb_clients, "nb_camions": nb_camions,
        "capacite": capacite, "demandes": demandes,
        "durees_service": [0] * (nb_clients + 1),
        "distances": distances, "fenetres": fenetres,
        "solution_depart": solution_depart,
        "repartition": repartition, "fenetres_type": fenetres_type,
    }


# ============================================================
# 2. SIMULER UNE TOURNEE ET VERIFIER LES HORAIRES
# ============================================================

def simuler_tournee(tournee, instance):
    """Renvoie départ, retour, durée et heures de livraison ; sinon None.

    Les livraisons durent 0 minute sur les instances générées.
    Un import externe peut fournir des durées non nulles.
    L'heure de départ peut être choisie
    librement entre 8h et 18h, sous réserve du retour avant 18h.
    """
    distances = instance.get("temps_trajet", instance["distances"])
    fenetres = instance["fenetres"]
    # Par défaut, livraison instantanée ; peut être renseigné par un import externe.
    services = instance.get("durees_service", [0] * len(fenetres))
    if len(tournee) < 3 or tournee[0] != 0 or tournee[-1] != 0:
        return None

    # Calcul à rebours : dernière heure possible pour chaque client.
    limite = fenetres[0][1]
    for i in range(len(tournee) - 2, 0, -1):
        client, suivant = tournee[i], tournee[i + 1]
        limite = min(fenetres[client][1], limite - distances[client][suivant] - services[client])
        if limite < fenetres[client][0] - EPS:
            return None

    depart = max(fenetres[0][0], limite - distances[0][tournee[1]])
    if limite - distances[0][tournee[1]] < fenetres[0][0] - EPS:
        return None

    # Simulation dans l'ordre : trajet, attente éventuelle, livraison.
    heure = depart
    livraisons = []
    for precedent, client in zip(tournee, tournee[1:]):
        heure += distances[precedent][client]
        if client != 0:
            heure = max(heure, fenetres[client][0])
            if heure > fenetres[client][1] + EPS:
                return None
            livraisons.append((client, heure))
            heure += services[client]

    if heure > fenetres[0][1] + EPS:
        return None
    return {"depart": depart, "retour": heure,
            "duree": heure - depart, "livraisons": livraisons}


def verifier_solution(solution, instance):
    """Vérifie les livraisons uniques, les capacités et les horaires."""
    if not 1 <= len(solution) <= instance["nb_camions"]:
        return False
    clients = []
    for tournee in solution:
        if len(tournee) < 3 or 0 in tournee[1:-1]:
            return False
        if sum(instance["demandes"][c] for c in tournee[1:-1]) > instance["capacite"]:
            return False
        if simuler_tournee(tournee, instance) is None:
            return False
        clients.extend(tournee[1:-1])
    return sorted(clients) == list(range(1, instance["nb_clients"] + 1))


def cout_tournee(tournee, instance, objectif="duree", info=None):
    """Coût d'une tournée valide selon l'objectif choisi.

    - duree : trajet + attente + services, en unités de temps ;
    - distance : somme des distances sur les arcs (sans attente/service).
    """
    if objectif == "duree":
        if info is None:
            info = simuler_tournee(tournee, instance)
        return math.inf if info is None else info["duree"]
    if objectif == "distance":
        distances = instance["distances"]
        return sum(distances[a][b] for a, b in zip(tournee, tournee[1:]))
    raise ValueError("Objectif inconnu : choisir 'duree' ou 'distance'")


def calcul_cout(solution, instance, objectif="duree"):
    """Coût total ; retourne l'infini si la solution est irréalisable."""
    if objectif not in ("duree", "distance"):
        raise ValueError("Objectif inconnu : choisir 'duree' ou 'distance'")
    if not verifier_solution(solution, instance):
        return math.inf
    return sum(cout_tournee(t, instance, objectif) for t in solution)


def calcul_gap_solomon(solution, instance, distance_reference, vehicules_reference=None):
    """Écart de distance (%) vis-à-vis d'une référence Solomon.

    Exige des distances et contraintes comparables à celles de la référence.
    Ne charge PAS Solomon et ne vérifie PAS la concordance des conventions
    (arrondis, véhicules, etc.). La comparaison des véhicules reste distincte.
    """
    if distance_reference <= 0:
        raise ValueError("La distance de référence doit être strictement positive")
    distance = calcul_cout(solution, instance, objectif="distance")
    if not math.isfinite(distance):
        raise ValueError("Solution non réalisable : GAP impossible")
    bilan = {
        "distance_solution": distance,
        "distance_reference": distance_reference,
        "gap_distance_pourcent": 100 * (distance - distance_reference) / distance_reference,
        "vehicules_solution": len(solution),
        "vehicules_reference": vehicules_reference,
    }
    if vehicules_reference is not None:
        bilan["ecart_vehicules"] = len(solution) - vehicules_reference
    return bilan


# ============================================================
# 3. LIRE UNE INSTANCE DE SOLOMON (VRPLIB) ET CONSTRUIRE UN DEPART
# ============================================================

# Optimums publiés : distance totale minimale connue pour chaque instance,
# distances tronquées à une décimale. 2 instances par classe :
# C = clients groupés, R = dispersés, RC = mélange ;
# 1 = horizon court et petits camions, 2 = horizon long et gros camions.
OPTIMUMS_SOLOMON = {
    25: {"C101": 191.3, "C102": 190.3, "C201": 214.7, "C202": 214.7,
         "R101": 617.1, "R102": 547.1, "R201": 463.3, "R202": 410.5,
         "RC101": 461.1, "RC102": 351.8, "RC201": 360.2, "RC202": 338.0},
    50: {"C101": 362.4, "C102": 361.4, "C201": 360.2, "C202": 360.2,
         "R101": 1044.0, "R102": 909.0, "R201": 791.9, "R202": 698.5,
         "RC101": 944.0, "RC102": 822.5, "RC201": 684.8, "RC202": 613.6},
    100: {"C101": 827.3, "C102": 827.3, "C201": 589.1, "C202": 589.1,
          "R101": 1637.7, "R102": 1466.6, "R201": 1143.2, "R202": 1029.6,
          "RC101": 1619.8, "RC102": 1457.4, "RC201": 1261.8, "RC202": 1092.3},
}
DOSSIER_INSTANCES = Path(__file__).resolve().parent / "instances" / "solomon"


def charger_solomon(nom, nb_clients):
    """Lit une instance de Solomon avec vrplib, au même format que generer_instance.

    Dans Solomon, le temps de trajet T_ij est égal à la distance d_ij.
    Les distances sont tronquées à une décimale, comme pour les optimums publiés.
    La solution de départ est construite par insertion gloutonne.
    """
    try:
        import vrplib
    except ImportError:
        raise ImportError("Instances de Solomon : pip install vrplib") from None
    chemin = DOSSIER_INSTANCES / str(nb_clients) / f"{nom}.txt"
    donnees = vrplib.read_instance(str(chemin), instance_format="solomon")
    distances = [[math.floor(d * 10) / 10 for d in ligne]
                 for ligne in donnees["edge_weight"].tolist()]
    instance = {
        "nom": f"{nom}.{nb_clients}", "classe": nom[:-2],
        "nb_clients": len(donnees["demand"]) - 1,   # le dépôt est le sommet 0
        "nb_camions": donnees["vehicles"], "capacite": donnees["capacity"],
        "demandes": donnees["demand"].tolist(),
        "durees_service": donnees["service_time"].tolist(),
        "distances": distances,
        "fenetres": [tuple(f) for f in donnees["time_window"].tolist()],
        "optimum": OPTIMUMS_SOLOMON[nb_clients][nom],
    }
    instance["solution_depart"] = solution_insertion(instance)
    return instance


def solution_insertion(instance):
    """Première solution valide par insertion gloutonne.

    Les clients sont pris par heure de fermeture croissante. Chacun est placé
    là où il allonge le moins la distance, sans dépasser la capacité ni les
    horaires. Si aucune place ne convient, un nouveau camion part du dépôt.
    """
    distances = instance["distances"]
    demandes = instance["demandes"]
    clients = sorted(range(1, instance["nb_clients"] + 1),
                     key=lambda c: instance["fenetres"][c][1])
    solution, charges = [], []
    for client in clients:
        meilleur = None                     # (surcoût, tournée, position)
        for k, tournee in enumerate(solution):
            if charges[k] + demandes[client] > instance["capacite"]:
                continue
            for p in range(1, len(tournee)):
                a, b = tournee[p - 1], tournee[p]
                surcout = distances[a][client] + distances[client][b] - distances[a][b]
                if meilleur is not None and surcout >= meilleur[0]:
                    continue
                if simuler_tournee(tournee[:p] + [client] + tournee[p:], instance):
                    meilleur = (surcout, k, p)
        if meilleur is None:
            solution.append([0, client, 0])
            charges.append(demandes[client])
        else:
            _, k, p = meilleur
            solution[k].insert(p, client)
            charges[k] += demandes[client]
    if len(solution) > instance["nb_camions"]:
        raise ValueError("Insertion : plus de tournées que de camions disponibles")
    return solution


# ============================================================
# 4. RECHERCHE TABOU : SWAP, DEPLACER UN CLIENT, ECHANGER LES FINS
# ============================================================

def recherche_tabou(instance, iterations=80, taille_tabou=12,
                    max_voisins=250, graine=123, objectif="duree"):
    """Améliore la solution initiale et renvoie l'historique de convergence.

    À chaque itération, max_voisins mouvements sont tirés au hasard, entre
    un client c1 et l'un de ses voisins proches c2 :
    - ECHANGER LES FINS (2-opt*) : couper les deux tournées après c1 et c2,
      puis échanger leurs fins ; utile pour les longues tournées ;
    - SWAP : échanger c1 et c2, dans une tournée ou entre deux tournées ;
    - DEPLACER : mettre c1 juste avant ou après c2, ou dans un camion vide.
      Il change le nombre de clients d'un camion, peut vider une tournée
      (un camion en moins) ou en ouvrir une (un camion en plus).
    Le meilleur mouvement non tabou est appliqué, même s'il dégrade le coût.
    """
    if objectif not in ("duree", "distance"):
        raise ValueError("Objectif inconnu : choisir 'duree' ou 'distance'")
    hasard = random.Random(graine)
    courante = [t[:] for t in instance["solution_depart"]]
    if not verifier_solution(courante, instance):
        raise ValueError("Solution initiale invalide : fournir une solution_depart réalisable")
    demandes, capacite = instance["demandes"], instance["capacite"]

    def evaluer(tournee):
        """Coût d'une tournée modifiée, ou None si elle viole les horaires."""
        if len(tournee) == 2:          # tournée vidée : le camion reste au dépôt
            return 0
        info = simuler_tournee(tournee, instance)
        return None if info is None else cout_tournee(tournee, instance, objectif, info)

    # Coûts et charges des tournées : on ne recalcule que les tournées modifiées.
    couts = [cout_tournee(t, instance, objectif) for t in courante]
    charges = [sum(demandes[c] for c in t[1:-1]) for t in courante]
    cout_courant = sum(couts)
    cout_initial = cout_courant
    meilleur_cout = cout_courant
    meilleure = [t[:] for t in courante]
    historique = [meilleur_cout]
    tabous = deque(maxlen=taille_tabou)

    # Liste de candidats : pour chaque client, ses NB_PROCHES voisins les plus
    # proches. On ne tente que des mouvements entre clients proches.
    distances = instance["distances"]
    proches = {c: sorted((v for v in range(1, instance["nb_clients"] + 1) if v != c),
                         key=lambda v: distances[c][v])[:NB_PROCHES]
               for c in range(1, instance["nb_clients"] + 1)}

    for _ in range(iterations):
        # Où est chaque client : numéro de tournée et position dans la tournée.
        ou = {c: (k, i) for k, t in enumerate(courante) for i, c in enumerate(t) if c != 0}
        choix = None
        cout_choix = math.inf

        for _ in range(max_voisins):
            # Tirer un client c1, puis c2 : le plus souvent un voisin proche,
            # parfois n'importe quel client (pour explorer plus loin).
            c1 = hasard.randint(1, instance["nb_clients"])
            if hasard.random() < PROBA_PROCHE:
                c2 = hasard.choice(proches[c1])
            else:
                c2 = hasard.randint(1, instance["nb_clients"])
                if c2 == c1:
                    continue
            (k1, i1), (k2, i2) = ou[c1], ou[c2]
            tirage = hasard.random()
            if tirage < 1 / 3 and k1 != k2:
                # ECHANGER LES FINS : couper la tournée k1 après c1 et la
                # tournée k2 après c2, puis échanger les deux fins (2-opt*).
                mouvement = ("fins", min(c1, c2), max(c1, c2))
                t1 = courante[k1][:i1 + 1] + courante[k2][i2 + 1:]
                t2 = courante[k2][:i2 + 1] + courante[k1][i1 + 1:]
                if (sum(demandes[c] for c in t1[1:-1]) > capacite
                        or sum(demandes[c] for c in t2[1:-1]) > capacite):
                    continue
            elif tirage < 2 / 3:
                # SWAP : échanger les clients c1 et c2.
                mouvement = ("swap", min(c1, c2), max(c1, c2))
                if k1 != k2 and (
                        charges[k1] - demandes[c1] + demandes[c2] > capacite
                        or charges[k2] - demandes[c2] + demandes[c1] > capacite):
                    continue
                t1 = courante[k1][:]
                if k1 == k2:
                    t1[i1], t1[i2] = c2, c1
                    t2 = t1
                else:
                    t2 = courante[k2][:]
                    t1[i1], t2[i2] = c2, c1
            else:
                # DEPLACER : sortir c1 de sa tournée et le mettre juste avant
                # ou juste après c2, ou parfois dans un camion encore vide.
                mouvement = ("deplacer", c1)
                t1 = courante[k1][:i1] + courante[k1][i1 + 1:]
                apres = hasard.randint(0, 1)
                if (hasard.random() < PROBA_NOUVEAU_CAMION and len(t1) > 2
                        and len(courante) < instance["nb_camions"]):
                    k2 = len(courante)             # nouveau camion, ajouté à la fin
                    t2 = [0, c1, 0]
                elif k1 != k2 and charges[k2] + demandes[c1] > capacite:
                    continue
                elif k1 == k2:
                    t1.insert(t1.index(c2) + apres, c1)
                    if t1 == courante[k1]:
                        continue
                    t2 = t1
                else:
                    t2 = courante[k2][:]
                    t2.insert(i2 + apres, c1)

            # Évaluer seulement les tournées modifiées.
            cout1 = evaluer(t1)
            cout2 = cout1 if k1 == k2 else evaluer(t2)
            if cout1 is None or cout2 is None:
                continue
            nouveau_cout = cout_courant - couts[k1] + cout1
            if k1 != k2:
                nouveau_cout += cout2 - (couts[k2] if k2 < len(couts) else 0)

            # Exception tabou : autoriser un nouveau record global.
            if mouvement in tabous and nouveau_cout >= meilleur_cout - EPS:
                continue
            if nouveau_cout < cout_choix:
                cout_choix = nouveau_cout
                choix = (k1, k2, t1, t2, cout1, cout2, mouvement)

        if choix is not None:
            k1, k2, t1, t2, cout1, cout2, mouvement = choix
            if k2 == len(courante):           # un camion de plus
                courante.append(t2)
                couts.append(cout2)
                charges.append(0)
            courante[k1], couts[k1] = t1, cout1
            courante[k2], couts[k2] = t2, cout2
            charges[k1] = sum(demandes[c] for c in t1[1:-1])
            charges[k2] = sum(demandes[c] for c in t2[1:-1])
            tabous.append(mouvement)
            if len(courante[k1]) == 2:     # tournée vide : un camion en moins
                del courante[k1], couts[k1], charges[k1]
            cout_courant = sum(couts)
            if cout_courant < meilleur_cout - EPS:
                meilleur_cout = cout_courant
                meilleure = [t[:] for t in courante]
        historique.append(meilleur_cout)

    if not verifier_solution(meilleure, instance):
        raise RuntimeError("La recherche tabou a produit une solution invalide")
    if not math.isclose(calcul_cout(meilleure, instance, objectif), meilleur_cout, rel_tol=1e-9, abs_tol=1e-7):
        raise RuntimeError("Incohérence entre la solution et son coût")
    return {
        "solution": meilleure, "initial": cout_initial, "final": meilleur_cout,
        "iterations": len(historique) - 1, "historique": historique,
        "objectif": objectif,
    }


# ============================================================
# 5. CONFIGURATION : UNE SEULE LIGNE A CHANGER
# ============================================================

# Modes possibles : "instances", "parametres", "grandes_tailles", "demo",
# "solomon", "objectifs", "demo_solomon"
MODE = "instances"

# Seulement pour le mode demo : "duree" (ADEME) ou "distance" (Solomon).
# Les trois études sur instances générées utilisent toujours "duree".
# Les modes Solomon utilisent "distance", la seule mesure comparable
# aux optimums publiés (sauf le mode "objectifs", qui compare les deux).
OBJECTIF_DEMO = "duree"

# Réglage commun à l'étude des 60 instances et à la démonstration.
# Les valeurs sont des choix de référence, PAS des optimums démontrés.
ITERATIONS = 80
TAILLE_TABOU = 12
MAX_VOISINS = 250
NB_PROCHES = 10        # taille de la liste de candidats (voisins proches)
PROBA_PROCHE = 1.0     # part des mouvements tentés entre clients proches
PROBA_NOUVEAU_CAMION = 0.05   # part des DEPLACER vers un camion encore vide
GRAINE_RECHERCHE = 123

# Pour le mode "demo" uniquement.
NB_CLIENTS_DEMO = 30
NB_CAMIONS_DEMO = 5
GRAINE_DEMO = 42

# Pour les modes Solomon (instances lues avec vrplib, dossier instances/solomon).
INSTANCES_SOLOMON = ("C101", "C102", "C201", "C202", "R101", "R102",
                     "R201", "R202", "RC101", "RC102", "RC201", "RC202")
TAILLES_SOLOMON = (25, 50, 100)
GRAINES_SOLOMON = (1, 2, 3)          # 3 exécutions par instance
ITERATIONS_SOLOMON = 5000
# Mesuré sur les 36 instances (graine 1) : avec une liste de 12, la recherche
# tourne en rond sur les longues tournées (gap moyen 13 % à 100 clients) ;
# avec 120, le gap moyen tombe à 6 %.
TAILLE_TABOU_SOLOMON = 120
DEMOS_SOLOMON = (("C101", 25), ("R101", 25), ("RC101", 25))

DOSSIER_RESULTATS = Path(__file__).resolve().parent / "resultats_cvrptw"


# ============================================================
# 6. AFFICHAGE ET SAUVEGARDE
# ============================================================

def format_heure(minutes):
    minutes = round(minutes)
    return f"{minutes // 60:02d}h{minutes % 60:02d}"


def afficher_solution(instance, resultat):
    solomon = "optimum" in instance        # instance lue avec vrplib
    print("\n=== MEILLEURE SOLUTION ===")
    if solomon:
        print("Instance :", instance["nom"])
    print("Valide :", verifier_solution(resultat["solution"], instance))
    objectif = resultat.get("objectif", "duree")
    unite = "minutes" if objectif == "duree" else "unités de distance"
    print("Objectif :", objectif)
    print("Coût initial :", round(resultat["initial"], 1), unite)
    print("Coût final   :", round(resultat["final"], 1), unite)
    print(f"Amélioration : {pourcentage_gain(resultat):.2f} %")
    print("Itérations effectuées :", resultat["iterations"])
    if solomon:
        bilan = calcul_gap_solomon(resultat["solution"], instance, instance["optimum"])
        print(f"Distance : {bilan['distance_solution']:.1f} | optimum publié : "
              f"{instance['optimum']} | gap : {bilan['gap_distance_pourcent']:.2f} %")
    for numero, tournee in enumerate(resultat["solution"], 1):
        info = simuler_tournee(tournee, instance)
        charge = sum(instance["demandes"][c] for c in tournee[1:-1])
        print(f"\nCamion {numero} : {' -> '.join(map(str, tournee))}")
        if solomon:   # les temps de Solomon ne sont pas des heures d'horloge
            print(f"  Départ : {info['depart']:.1f} | Retour : {info['retour']:.1f}")
        else:
            print(f"  Départ : {format_heure(info['depart'])} | Retour : {format_heure(info['retour'])}")
        unite_duree = "" if solomon else " min"
        print(f"  Charge : {charge}/{instance['capacite']} | Durée : {info['duree']:.1f}{unite_duree}")


def pourcentage_gain(resultat):
    initial = resultat["initial"]
    return 100 * (initial - resultat["final"]) / initial if initial else 0.0


def lancer_recherche(instance, iterations, taille_tabou, max_voisins,
                     graine_recherche=GRAINE_RECHERCHE, objectif="duree"):
    debut = time.perf_counter()
    resultat = recherche_tabou(instance, iterations=iterations,
                               taille_tabou=taille_tabou,
                               max_voisins=max_voisins,
                               graine=graine_recherche, objectif=objectif)
    duree = time.perf_counter() - debut  # Le temps de génération n'est pas inclus.
    valide = verifier_solution(resultat["solution"], instance)
    if not valide:
        raise RuntimeError("Solution finale invalide")
    return resultat, duree, valide


def enregistrer_csv(chemin, lignes):
    if not lignes:
        raise ValueError("Aucune donnée à enregistrer")
    with chemin.open("w", newline="", encoding="utf-8-sig") as fichier:
        writer = csv.DictWriter(fichier, fieldnames=lignes[0].keys(), delimiter=";")
        writer.writeheader()
        writer.writerows(lignes)


def moyenne(lignes, cle):
    return statistics.mean(ligne[cle] for ligne in lignes)


def ecrire_resume(dossier, titre, lignes, champs):
    """Petit résumé directement réutilisable lors de la rédaction."""
    with (dossier / "resume.txt").open("w", encoding="utf-8") as fichier:
        fichier.write(titre + "\n" + "=" * len(titre) + "\n\n")
        fichier.write("Mesures sur instances artificielles, pas de GAP / optimum connu.\n")
        fichier.write("Temps mesures : recherche tabou seule (generation exclue).\n")
        fichier.write("Cout : somme des durees de tournee, attente incluse.\n")
        fichier.write("Le gain mesure seulement l'amelioration sur la solution initiale.\n\n")
        fichier.write(f"Nombre d'executions : {len(lignes)}\n")
        fichier.write(f"Solutions valides : {sum(l['valide'] for l in lignes)}/{len(lignes)}\n")
        for nom, valeur in champs.items():
            fichier.write(f"{nom} : {valeur}\n")
        fichier.write("\nLimites : instances construites autour d'une solution initiale realisable ;\n")
        fichier.write("temps de trajet fixes, voisinage SWAP + DEPLACER + ECHANGER LES FINS, service nul.\n")
        fichier.write("Les variations de taille changent aussi le nombre de camions.\n")


def graphique(plt, chemin, xlabel, ylabel, titre, categories, valeurs, barres=False):
    plt.figure(figsize=(7, 4.5))
    if barres:
        plt.bar(categories, valeurs)
    else:
        plt.plot(categories, valeurs, marker="o")
        plt.grid(alpha=0.3)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(titre)
    plt.tight_layout()
    plt.savefig(chemin, dpi=160)
    plt.close()


def charger_graphiques():
    try:
        import matplotlib.pyplot as plt
        return plt
    except ImportError:
        print("Graphiques non générés. Installer matplotlib : pip install matplotlib")
        return None


# ============================================================
# 7. ETUDE 1 : 60 INSTANCES / 4 SCENARIOS / 3 TAILLES
# ============================================================

def etude_experimentale(dossier):
    """60 problèmes : 2 répartitions x 2 fenêtres x 3 tailles x 5 graines.

    Les cinq graines changent les INSTANCES, pas la graine de recherche.
    Nombre de camions et nombre de clients augmentent ensemble.
    """
    lignes = []
    historique_exemple = None
    for repartition in ("groupes", "disperses"):
        for largeur in ("larges", "serrees"):
            for nb_clients, nb_camions in ((12, 3), (30, 5), (60, 8)):
                for graine_instance in (1, 2, 3, 4, 5):
                    instance = generer_instance(nb_clients, nb_camions,
                                                graine=graine_instance,
                                                repartition=repartition,
                                                fenetres_type=largeur)
                    resultat, secondes, valide = lancer_recherche(
                        instance, ITERATIONS, TAILLE_TABOU, MAX_VOISINS)
                    lignes.append({
                        "repartition": repartition,
                        "fenetres": largeur,
                        "clients": nb_clients,
                        "camions": nb_camions,
                        "graine_instance": graine_instance,
                        "graine_recherche": GRAINE_RECHERCHE,
                        "iterations_max": ITERATIONS,
                        "taille_tabou": TAILLE_TABOU,
                        "max_voisins": MAX_VOISINS,
                        "cout_initial": resultat["initial"],
                        "cout_final": resultat["final"],
                        "gain_pourcent": round(pourcentage_gain(resultat), 4),
                        "temps_secondes": round(secondes, 6),
                        "iterations_effectuees": resultat["iterations"],
                        "valide": valide,
                    })
                    if (repartition, largeur, nb_clients, graine_instance) == (
                            "groupes", "larges", 30, 1):
                        historique_exemple = resultat["historique"]
                    print(f"{len(lignes):2d}/60 | {repartition:9} | {largeur:7} | "
                          f"{nb_clients:3d} clients | gain {pourcentage_gain(resultat):5.1f} % "
                          f"| {secondes:.3f} s")

    enregistrer_csv(dossier / "resultats_60_instances.csv", lignes)

    # Un CSV de synthèse pour Excel et la rédaction.
    synthese = []
    for repartition in ("groupes", "disperses"):
        for largeur in ("larges", "serrees"):
            for clients in (12, 30, 60):
                sous = [l for l in lignes if l["repartition"] == repartition
                        and l["fenetres"] == largeur and l["clients"] == clients]
                synthese.append({
                    "repartition": repartition, "fenetres": largeur, "clients": clients,
                    "nb_tests": len(sous),
                    "gain_moyen_pourcent": round(moyenne(sous, "gain_pourcent"), 4),
                    "ecart_type_gain_points": round(statistics.stdev(l["gain_pourcent"] for l in sous), 4),
                    "temps_moyen_secondes": round(moyenne(sous, "temps_secondes"), 6),
                    "ecart_type_temps_secondes": round(statistics.stdev(l["temps_secondes"] for l in sous), 6),
                    "solutions_valides": sum(l["valide"] for l in sous),
                })
    enregistrer_csv(dossier / "synthese_12_scenarios.csv", synthese)

    print("\n=== BILAN DE L'ETUDE 1 ===")
    print(f"Instances valides : {sum(l['valide'] for l in lignes)}/{len(lignes)}")
    print(f"Gain moyen : {moyenne(lignes, 'gain_pourcent'):.2f} %")
    print(f"Écart-type global du gain : {statistics.stdev(l['gain_pourcent'] for l in lignes):.2f} points")
    for n in (12, 30, 60):
        sous = [l for l in lignes if l["clients"] == n]
        print(f"{n:3d} clients : {moyenne(sous, 'temps_secondes'):.3f} s | "
              f"gain {moyenne(sous, 'gain_pourcent'):.2f} %")
    ecrire_resume(dossier, "ETUDE 1 - 60 INSTANCES", lignes, {
        "Iterations maximum": ITERATIONS,
        "Taille de la liste tabou": TAILLE_TABOU,
        "Voisins examines au maximum": MAX_VOISINS,
        "Graine de recherche": GRAINE_RECHERCHE,
        "Gain moyen global (%)": f"{moyenne(lignes, 'gain_pourcent'):.2f}",
        "Ecart-type global des gains (points)":
            f"{statistics.stdev(l['gain_pourcent'] for l in lignes):.2f}",
    })
    creer_graphiques_instances(lignes, historique_exemple, dossier)
    return lignes


def creer_graphiques_instances(lignes, historique, dossier):
    plt = charger_graphiques()
    if plt is None:
        return
    tailles = (12, 30, 60)
    temps = [moyenne([l for l in lignes if l["clients"] == n], "temps_secondes")
             for n in tailles]
    gains = [moyenne([l for l in lignes if l["clients"] == n], "gain_pourcent")
             for n in tailles]
    graphique(plt, dossier / "temps_calcul.png", "Nombre de clients",
             "Temps moyen (s)", "Temps selon la taille de l'instance", tailles, temps)
    graphique(plt, dossier / "amelioration.png", "Nombre de clients",
             "Gain moyen (%)", "Gain sur la solution initiale", [str(n) for n in tailles],
             gains, barres=True)
    if historique is not None:
        graphique(plt, dossier / "convergence.png", "Itération",
                 "Meilleur coût (min)",
                 "Convergence : 30 clients, groupes/larges, graine instance 1",
                 list(range(len(historique))), historique)
        # La série complète permet de recréer ou d'expliquer le graphique.
        enregistrer_csv(dossier / "convergence_30_clients.csv", [
            {"iteration": i, "meilleur_cout": cout}
            for i, cout in enumerate(historique)
        ])
    noms, valeurs = [], []
    for rep in ("groupes", "disperses"):
        for larg in ("larges", "serrees"):
            noms.append(rep + "\n" + larg)
            sous = [l for l in lignes if l["repartition"] == rep and l["fenetres"] == larg]
            valeurs.append(moyenne(sous, "gain_pourcent"))
    graphique(plt, dossier / "scenarios.png", "Scénario", "Gain moyen (%)",
             "Influence de la géographie et des fenêtres", noms, valeurs, barres=True)
    print("4 graphiques enregistrés dans :", dossier)


# ============================================================
# 8. ETUDE 2 : INFLUENCE DES PARAMETRES
# ============================================================

def etude_parametres(dossier):
    """Un seul paramètre change à la fois, sur les 3 mêmes instances."""
    reglages = [
        ("reference", ITERATIONS, TAILLE_TABOU, MAX_VOISINS),
        ("iterations_160", 160, TAILLE_TABOU, MAX_VOISINS),
        ("tabou_5", ITERATIONS, 5, MAX_VOISINS),
        ("tabou_20", ITERATIONS, 20, MAX_VOISINS),
        ("voisins_100", ITERATIONS, TAILLE_TABOU, 100),
        ("voisins_400", ITERATIONS, TAILLE_TABOU, 400),
    ]
    lignes = []
    for graine_instance in (1, 2, 3):
        instance = generer_instance(30, 5, graine=graine_instance)
        for nom, iterations, taille_tabou, max_voisins in reglages:
            resultat, secondes, valide = lancer_recherche(
                instance, iterations, taille_tabou, max_voisins)
            lignes.append({
                "reglage": nom, "clients": 30, "camions": 5,
                "graine_instance": graine_instance,
                "graine_recherche": GRAINE_RECHERCHE,
                "iterations_max": iterations, "taille_tabou": taille_tabou,
                "max_voisins": max_voisins,
                "cout_initial": resultat["initial"],
                "cout_final": resultat["final"],
                "gain_pourcent": round(pourcentage_gain(resultat), 4),
                "temps_secondes": round(secondes, 6),
                "iterations_effectuees": resultat["iterations"],
                "valide": valide,
            })
            print(f"{len(lignes):2d}/18 | {nom:16} | "
                  f"gain {pourcentage_gain(resultat):5.1f} % | {secondes:.3f} s")
    enregistrer_csv(dossier / "etude_parametres.csv", lignes)
    synthese = []
    for nom, *_ in reglages:
        sous = [l for l in lignes if l["reglage"] == nom]
        synthese.append({"reglage": nom, "nb_tests": len(sous),
                         "gain_moyen_pourcent": round(moyenne(sous, "gain_pourcent"), 4),
                         "temps_moyen_secondes": round(moyenne(sous, "temps_secondes"), 6)})
    enregistrer_csv(dossier / "synthese_parametres.csv", synthese)
    print("\n=== BILAN DE L'ETUDE 2 ===")
    for ligne in synthese:
        print(f"{ligne['reglage']:16} : gain {ligne['gain_moyen_pourcent']:.2f} % "
              f"| temps {ligne['temps_moyen_secondes']:.3f} s")
    ecrire_resume(dossier, "ETUDE 2 - PARAMETRES", lignes, {
        "Reference": f"iterations={ITERATIONS}, tabou={TAILLE_TABOU}, voisins={MAX_VOISINS}",
        "Instances": "30 clients, 5 camions, graines 1/2/3, groupes et fenêtres larges",
        "Configurations": ", ".join(nom for nom, *_ in reglages),
    })
    plt = charger_graphiques()
    if plt is not None:
        graphique(plt, dossier / "comparaison_parametres.png", "Configuration",
                 "Gain moyen (%)", "Sensibilité aux paramètres",
                 [l["reglage"] for l in synthese],
                 [l["gain_moyen_pourcent"] for l in synthese], barres=True)
    return lignes


# ============================================================
# 9. ETUDE 3 : GRANDES INSTANCES
# ============================================================

def etude_grandes_tailles(dossier):
    """Un essai par taille : test de faisabilité, pas une étude statistique."""
    lignes = []
    for n, camions in ((500, 50), (1000, 100), (2000, 200)):
        debut_generation = time.perf_counter()
        instance = generer_instance(n, camions, graine=42)
        secondes_generation = time.perf_counter() - debut_generation
        resultat, secondes, valide = lancer_recherche(
            instance, iterations=80, taille_tabou=TAILLE_TABOU, max_voisins=100)
        lignes.append({
            "clients": n, "camions": camions,
            "graine_instance": 42, "graine_recherche": GRAINE_RECHERCHE,
            "iterations_max": 80, "taille_tabou": TAILLE_TABOU,
            "max_voisins": 100,
            "cout_initial": resultat["initial"], "cout_final": resultat["final"],
            "gain_pourcent": round(pourcentage_gain(resultat), 4),
            "temps_generation_secondes": round(secondes_generation, 6),
            "temps_secondes": round(secondes, 6),
            "iterations_effectuees": resultat["iterations"],
            "valide": valide,
        })
        print(f"{n:4d} clients | génération {secondes_generation:.2f} s | "
              f"recherche {secondes:.2f} s | gain {pourcentage_gain(resultat):.2f} %")
    enregistrer_csv(dossier / "etude_grandes_tailles.csv", lignes)
    ecrire_resume(dossier, "ETUDE 3 - GRANDES TAILLES", lignes, {
        "Tailles": "500, 1000, 2000 clients",
        "Budget": "80 iterations, 100 voisins max, même graine de recherche",
        "Précision": "1 instance par taille : faisabilité, pas robustesse",
    })
    plt = charger_graphiques()
    if plt is not None:
        graphique(plt, dossier / "temps_grandes_tailles.png", "Nombre de clients",
                 "Temps de la recherche tabou (s)", "Passage à l'échelle",
                 [l["clients"] for l in lignes],
                 [l["temps_secondes"] for l in lignes])
    return lignes


# ============================================================
# 10. ETUDE 4 : VALIDATION SUR LES INSTANCES DE SOLOMON (VRPLIB)
# ============================================================

CLASSES_SOLOMON = ("C1", "C2", "R1", "R2", "RC1", "RC2")


def ecart_type(valeurs):
    valeurs = list(valeurs)
    return statistics.stdev(valeurs) if len(valeurs) > 1 else 0.0


def etude_solomon(dossier):
    """12 instances x 3 tailles x 3 graines de recherche, objectif distance.

    Le gap compare la distance trouvée à l'optimum publié de chaque instance.
    La durée totale (trajet + livraison + attente) est notée en plus.
    """
    lignes = []
    historique_exemple = None
    total = len(INSTANCES_SOLOMON) * len(TAILLES_SOLOMON) * len(GRAINES_SOLOMON)
    for nb_clients in TAILLES_SOLOMON:
        for nom in INSTANCES_SOLOMON:
            instance = charger_solomon(nom, nb_clients)
            optimum = instance["optimum"]
            depart = calcul_cout(instance["solution_depart"], instance, "distance")
            for graine in GRAINES_SOLOMON:
                resultat, secondes, valide = lancer_recherche(
                    instance, ITERATIONS_SOLOMON, TAILLE_TABOU_SOLOMON, MAX_VOISINS,
                    graine_recherche=graine, objectif="distance")
                bilan = calcul_gap_solomon(resultat["solution"], instance, optimum)
                lignes.append({
                    "instance": nom, "classe": instance["classe"],
                    "clients": nb_clients, "graine_recherche": graine,
                    "iterations_max": ITERATIONS_SOLOMON,
                    "optimum_publie": optimum,
                    "distance_insertion": round(depart, 1),
                    "gap_insertion_pourcent": round(100 * (depart - optimum) / optimum, 2),
                    "distance_finale": round(bilan["distance_solution"], 1),
                    "gap_pourcent": round(bilan["gap_distance_pourcent"], 2),
                    "camions": len(resultat["solution"]),
                    "duree_totale": round(calcul_cout(resultat["solution"], instance, "duree"), 1),
                    "temps_secondes": round(secondes, 3),
                    "valide": valide,
                })
                if (nom, nb_clients, graine) == ("RC101", 100, GRAINES_SOLOMON[0]):
                    historique_exemple = [100 * (c - optimum) / optimum
                                          for c in resultat["historique"]]
                print(f"{len(lignes):3d}/{total} | {instance['nom']:9} | graine {graine} | "
                      f"gap {lignes[-1]['gap_pourcent']:6.2f} % | {secondes:.1f} s")

    enregistrer_csv(dossier / "resultats_solomon.csv", lignes)

    # Synthèse par taille et par classe : moyenne, écart-type, pire cas.
    synthese = []
    for nb_clients in TAILLES_SOLOMON:
        for classe in CLASSES_SOLOMON + ("toutes",):
            sous = [l for l in lignes if l["clients"] == nb_clients
                    and classe in ("toutes", l["classe"])]
            synthese.append({
                "clients": nb_clients, "classe": classe, "nb_executions": len(sous),
                "gap_insertion_moyen": round(moyenne(sous, "gap_insertion_pourcent"), 2),
                "gap_moyen_pourcent": round(moyenne(sous, "gap_pourcent"), 2),
                "ecart_type_gap_points": round(ecart_type(l["gap_pourcent"] for l in sous), 2),
                "gap_max_pourcent": max(l["gap_pourcent"] for l in sous),
                "temps_moyen_secondes": round(moyenne(sous, "temps_secondes"), 2),
            })
    enregistrer_csv(dossier / "synthese_solomon.csv", synthese)

    print("\n=== BILAN DE L'ETUDE 4 (SOLOMON) ===")
    print(f"Solutions valides : {sum(l['valide'] for l in lignes)}/{len(lignes)}")
    for ligne in synthese:
        if ligne["classe"] == "toutes":
            print(f"{ligne['clients']:3d} clients : gap moyen {ligne['gap_moyen_pourcent']:.2f} % "
                  f"(insertion seule {ligne['gap_insertion_moyen']:.2f} %) | "
                  f"pire {ligne['gap_max_pourcent']:.2f} % | {ligne['temps_moyen_secondes']:.1f} s")
    with (dossier / "resume.txt").open("w", encoding="utf-8") as fichier:
        fichier.write("ETUDE 4 - INSTANCES DE SOLOMON (VRPLIB)\n\n")
        fichier.write("Objectif : distance totale (temps de trajet T_ij = distance d_ij).\n")
        fichier.write("Gap = 100 x (distance - optimum publie) / optimum publie.\n")
        fichier.write(f"{len(INSTANCES_SOLOMON)} instances, tailles {TAILLES_SOLOMON}, "
                      f"graines {GRAINES_SOLOMON}, {ITERATIONS_SOLOMON} iterations, "
                      f"{MAX_VOISINS} voisins tires, liste tabou {TAILLE_TABOU_SOLOMON}.\n\n")
        for ligne in synthese:
            fichier.write(f"{ligne['clients']:3d} clients | {ligne['classe']:6} | "
                          f"gap moyen {ligne['gap_moyen_pourcent']:6.2f} % | "
                          f"ecart-type {ligne['ecart_type_gap_points']:5.2f} | "
                          f"pire {ligne['gap_max_pourcent']:6.2f} % | "
                          f"{ligne['temps_moyen_secondes']:.1f} s\n")
    creer_graphiques_solomon(lignes, historique_exemple, dossier)
    return lignes


def creer_graphiques_solomon(lignes, historique, dossier):
    plt = charger_graphiques()
    if plt is None:
        return
    # 1. Gap moyen par classe, une barre par taille.
    plt.figure(figsize=(8, 4.5))
    largeur = 0.8 / len(TAILLES_SOLOMON)
    for j, n in enumerate(TAILLES_SOLOMON):
        valeurs = [moyenne([l for l in lignes if l["clients"] == n and l["classe"] == c],
                           "gap_pourcent") for c in CLASSES_SOLOMON]
        plt.bar([i + j * largeur for i in range(len(CLASSES_SOLOMON))], valeurs,
                width=largeur, label=f"{n} clients")
    plt.xticks([i + largeur * (len(TAILLES_SOLOMON) - 1) / 2
                for i in range(len(CLASSES_SOLOMON))], CLASSES_SOLOMON)
    plt.axhline(10, color="red", linestyle="--", label="seuil de 10 %")
    plt.xlabel("Classe d'instances")
    plt.ylabel("Gap moyen (%)")
    plt.title("Écart à l'optimum publié selon la classe et la taille")
    plt.legend()
    plt.tight_layout()
    plt.savefig(dossier / "gap_par_classe.png", dpi=160)
    plt.close()

    # 2. Distribution des gaps : une boîte par taille.
    plt.figure(figsize=(7, 4.5))
    plt.boxplot([[l["gap_pourcent"] for l in lignes if l["clients"] == n]
                 for n in TAILLES_SOLOMON])
    plt.xticks(range(1, len(TAILLES_SOLOMON) + 1), [f"{n} clients" for n in TAILLES_SOLOMON])
    plt.axhline(10, color="red", linestyle="--")
    plt.ylabel("Gap (%)")
    plt.title("Distribution des gaps (toutes instances et graines)")
    plt.tight_layout()
    plt.savefig(dossier / "distribution_gaps.png", dpi=160)
    plt.close()

    # 3. Temps de calcul selon la taille.
    graphique(plt, dossier / "temps_solomon.png", "Nombre de clients",
              "Temps moyen (s)", "Temps de la recherche tabou selon la taille",
              list(TAILLES_SOLOMON),
              [moyenne([l for l in lignes if l["clients"] == n], "temps_secondes")
               for n in TAILLES_SOLOMON])

    # 4. Convergence : gap du meilleur coût au fil des itérations.
    if historique is not None:
        graphique(plt, dossier / "convergence_solomon.png", "Itération",
                  "Gap du meilleur coût (%)", "Convergence : RC101, 100 clients, graine 1",
                  list(range(len(historique))), historique)
    print("4 graphiques enregistrés dans :", dossier)


# ============================================================
# 11. ETUDE 5 : DUREE OU DISTANCE ? (CAS ADEME)
# ============================================================

def etude_objectifs(dossier, nb_clients=25):
    """Même instance, deux objectifs : ce que l'on gagne en durée, ce que
    l'on perd en distance. Graine 1, mêmes paramètres que l'étude 4."""
    lignes = []
    for nom in INSTANCES_SOLOMON:
        instance = charger_solomon(nom, nb_clients)
        mesures = {}
        for objectif in ("distance", "duree"):
            resultat, _, _ = lancer_recherche(
                instance, ITERATIONS_SOLOMON, TAILLE_TABOU_SOLOMON, MAX_VOISINS,
                graine_recherche=GRAINES_SOLOMON[0], objectif=objectif)
            mesures[objectif] = (calcul_cout(resultat["solution"], instance, "distance"),
                                 calcul_cout(resultat["solution"], instance, "duree"))
        (d_dist, t_dist), (d_duree, t_duree) = mesures["distance"], mesures["duree"]
        lignes.append({
            "instance": instance["nom"],
            "distance_si_objectif_distance": round(d_dist, 1),
            "duree_si_objectif_distance": round(t_dist, 1),
            "distance_si_objectif_duree": round(d_duree, 1),
            "duree_si_objectif_duree": round(t_duree, 1),
            "duree_gagnee_pourcent": round(100 * (t_dist - t_duree) / t_dist, 2),
            "distance_en_plus_pourcent": round(100 * (d_duree - d_dist) / d_dist, 2),
        })
        print(f"{instance['nom']:9} | durée gagnée {lignes[-1]['duree_gagnee_pourcent']:6.2f} % "
              f"| distance en plus {lignes[-1]['distance_en_plus_pourcent']:6.2f} %")
    enregistrer_csv(dossier / "duree_ou_distance.csv", lignes)
    print(f"\nEn moyenne : durée gagnée {moyenne(lignes, 'duree_gagnee_pourcent'):.2f} %, "
          f"distance en plus {moyenne(lignes, 'distance_en_plus_pourcent'):.2f} %")
    return lignes


# ============================================================
# 12. EXECUTION : CHANGER UNIQUEMENT MODE (EN HAUT DU SCRIPT)
# ============================================================

def main():
    modes = ("instances", "parametres", "grandes_tailles", "demo",
             "solomon", "objectifs", "demo_solomon")
    if MODE not in modes:
        raise ValueError(f"MODE inconnu : {MODE}. Choisir parmi {modes}")

    if MODE == "demo":
        instance = generer_instance(NB_CLIENTS_DEMO, NB_CAMIONS_DEMO,
                                    graine=GRAINE_DEMO)
        resultat, secondes, _ = lancer_recherche(
            instance, ITERATIONS, TAILLE_TABOU, MAX_VOISINS,
            objectif=OBJECTIF_DEMO)
        print(f"Temps de recherche tabou : {secondes:.3f} s")
        afficher_solution(instance, resultat)
        return

    if MODE == "demo_solomon":
        for nom, nb_clients in DEMOS_SOLOMON:
            instance = charger_solomon(nom, nb_clients)
            resultat, secondes, _ = lancer_recherche(
                instance, ITERATIONS_SOLOMON, TAILLE_TABOU_SOLOMON, MAX_VOISINS,
                graine_recherche=GRAINES_SOLOMON[0], objectif="distance")
            print(f"\nTemps de recherche tabou : {secondes:.1f} s")
            afficher_solution(instance, resultat)
        return

    dossier = DOSSIER_RESULTATS / {
        "instances": "01_instances",
        "parametres": "02_parametres",
        "grandes_tailles": "03_grandes_tailles",
        "solomon": "04_solomon",
        "objectifs": "05_duree_ou_distance",
    }[MODE]
    dossier.mkdir(parents=True, exist_ok=True)
    print(f"\n=== MODE : {MODE.upper()} ===")
    if MODE == "instances":
        etude_experimentale(dossier)
    elif MODE == "parametres":
        etude_parametres(dossier)
    elif MODE == "grandes_tailles":
        etude_grandes_tailles(dossier)
    elif MODE == "solomon":
        etude_solomon(dossier)
    else:
        etude_objectifs(dossier)
    print("\nFichiers enregistrés dans :", dossier)
    if MODE in ("instances", "parametres", "grandes_tailles"):
        print("Note : aucun GAP n'est calculé sans référence comparable.")


if __name__ == "__main__":
    main()
