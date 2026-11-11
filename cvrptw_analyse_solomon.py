"""CVRPTW : recherche tabou (SWAP), étude expérimentale et objectif configurable.

Exécution : python cvrptw_analyse_pret.py
Graphiques : pip install matplotlib (si nécessaire)
Aucune autre bibliothèque externe n'est requise.
"""

import csv
import math
import random
import statistics
import time
from collections import deque
from pathlib import Path


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
        if limite < fenetres[client][0]:
            return None

    depart = limite - distances[0][tournee[1]]
    if depart < fenetres[0][0]:
        return None

    # Simulation dans l'ordre : trajet, attente éventuelle, livraison.
    heure = depart
    livraisons = []
    for precedent, client in zip(tournee, tournee[1:]):
        heure += distances[precedent][client]
        if client != 0:
            heure = max(heure, fenetres[client][0])
            if heure > fenetres[client][1]:
                return None
            livraisons.append((client, heure))
            heure += services[client]

    if heure > fenetres[0][1]:
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
# 3. RECHERCHE TABOU : ECHANGER DEUX CLIENTS (SWAP)
# ============================================================

def recherche_tabou(instance, iterations=80, taille_tabou=12,
                    max_voisins=250, graine=123, objectif="duree"):
    """Améliore la solution initiale et renvoie l'historique de convergence."""
    if objectif not in ("duree", "distance"):
        raise ValueError("Objectif inconnu : choisir 'duree' ou 'distance'")
    hasard = random.Random(graine)
    courante = [t[:] for t in instance["solution_depart"]]
    if not verifier_solution(courante, instance):
        raise ValueError("Solution initiale invalide : fournir une solution_depart réalisable")

    # Coûts et charges des tournées : on évite de tout recalculer à chaque SWAP.
    couts = [cout_tournee(t, instance, objectif) for t in courante]
    charges = [sum(instance["demandes"][c] for c in t[1:-1]) for t in courante]
    cout_courant = sum(couts)
    cout_initial = cout_courant
    meilleur_cout = cout_courant
    meilleure = [t[:] for t in courante]
    historique = [meilleur_cout]
    tabous = deque(maxlen=taille_tabou)

    # Positions des clients, les dépôts (0) ne sont jamais échangés.
    positions = [(k, i) for k, t in enumerate(courante)
                 for i in range(1, len(t) - 1)]
    n = len(positions)
    nb_paires = n * (n - 1) // 2

    for _ in range(iterations):
        choix = None
        cout_choix = math.inf

        # Examiner tous les SWAP si peu de clients, sinon un échantillon.
        if nb_paires == 0:
            break
        if nb_paires <= max_voisins:
            paires = [(a, b) for a in range(n) for b in range(a + 1, n)]
        else:
            paires = set()
            while len(paires) < max_voisins:
                a, b = hasard.sample(range(n), 2)
                paires.add((min(a, b), max(a, b)))

        for a, b in paires:
            k1, i1 = positions[a]
            k2, i2 = positions[b]
            c1, c2 = courante[k1][i1], courante[k2][i2]
            mouvement = tuple(sorted((c1, c2)))

            # Un échange dans une même tournée conserve sa charge.
            if k1 != k2:
                charge1 = charges[k1] - instance["demandes"][c1] + instance["demandes"][c2]
                charge2 = charges[k2] - instance["demandes"][c2] + instance["demandes"][c1]
                if charge1 > instance["capacite"] or charge2 > instance["capacite"]:
                    continue

            # Échanger provisoirement les clients et évaluer les tournées modifiées.
            courante[k1][i1], courante[k2][i2] = c2, c1
            info1 = simuler_tournee(courante[k1], instance)
            info2 = simuler_tournee(courante[k2], instance) if k1 != k2 else info1
            if info1 is not None and info2 is not None:
                cout1 = cout_tournee(courante[k1], instance, objectif, info1)
                cout2 = (cout_tournee(courante[k2], instance, objectif, info2)
                         if k1 != k2 else cout1)
            courante[k1][i1], courante[k2][i2] = c1, c2

            if info1 is None or info2 is None:
                continue

            # Ne recalculer que les tournées modifiées.
            nouveau_cout = cout_courant - couts[k1] + cout1
            if k1 != k2:
                nouveau_cout += cout2 - couts[k2]

            # Exception tabou : autoriser un nouveau record global.
            if mouvement in tabous and nouveau_cout >= meilleur_cout:
                continue
            if nouveau_cout < cout_choix:
                cout_choix = nouveau_cout
                choix = (k1, i1, k2, i2, cout1, cout2, mouvement)

        if choix is None:
            break

        k1, i1, k2, i2, cout1, cout2, mouvement = choix
        courante[k1][i1], courante[k2][i2] = courante[k2][i2], courante[k1][i1]
        charges[k1] = sum(instance["demandes"][c] for c in courante[k1][1:-1])
        charges[k2] = sum(instance["demandes"][c] for c in courante[k2][1:-1])
        couts[k1] = cout1
        couts[k2] = cout2
        cout_courant = cout_choix
        tabous.append(mouvement)

        if cout_courant < meilleur_cout:
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
# 4. CONFIGURATION : UNE SEULE LIGNE A CHANGER
# ============================================================

# Modes possibles : "instances", "parametres", "grandes_tailles", "demo"
MODE = "instances"

# Seulement pour le mode demo : "duree" (ADEME) ou "distance" (Solomon).
# Les trois études utilisent toujours "duree", pour conserver leurs résultats.
OBJECTIF_DEMO = "duree"

# Réglage commun à l'étude des 60 instances et à la démonstration.
# Les valeurs sont des choix de référence, PAS des optimums démontrés.
ITERATIONS = 80
TAILLE_TABOU = 12
MAX_VOISINS = 250
GRAINE_RECHERCHE = 123

# Pour le mode "demo" uniquement.
NB_CLIENTS_DEMO = 30
NB_CAMIONS_DEMO = 5
GRAINE_DEMO = 42

DOSSIER_RESULTATS = Path(__file__).resolve().parent / "resultats_cvrptw"


# ============================================================
# 5. AFFICHAGE ET SAUVEGARDE
# ============================================================

def format_heure(minutes):
    return f"{minutes // 60:02d}h{minutes % 60:02d}"


def afficher_solution(instance, resultat):
    print("\n=== MEILLEURE SOLUTION ===")
    print("Valide :", verifier_solution(resultat["solution"], instance))
    objectif = resultat.get("objectif", "duree")
    unite = "minutes" if objectif == "duree" else "unités de distance"
    print("Objectif :", objectif)
    print("Coût initial :", resultat["initial"], unite)
    print("Coût final   :", resultat["final"], unite)
    print(f"Amélioration : {pourcentage_gain(resultat):.2f} %")
    print("Itérations effectuées :", resultat["iterations"])
    for numero, tournee in enumerate(resultat["solution"], 1):
        info = simuler_tournee(tournee, instance)
        charge = sum(instance["demandes"][c] for c in tournee[1:-1])
        print(f"\nCamion {numero} : {' -> '.join(map(str, tournee))}")
        print(f"  Départ : {format_heure(info['depart'])} | Retour : {format_heure(info['retour'])}")
        print(f"  Charge : {charge}/{instance['capacite']} | Durée : {info['duree']} min")


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
        fichier.write("temps de trajet fixes, voisinage SWAP uniquement, service nul.\n")
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
# 6. ETUDE 1 : 60 INSTANCES / 4 SCENARIOS / 3 TAILLES
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
# 7. ETUDE 2 : INFLUENCE DES PARAMETRES
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
# 8. ETUDE 3 : GRANDES INSTANCES
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
# 9. EXECUTION : CHANGER UNIQUEMENT MODE (EN HAUT DU SCRIPT)
# ============================================================

def main():
    modes = ("instances", "parametres", "grandes_tailles", "demo")
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

    dossier = DOSSIER_RESULTATS / {
        "instances": "01_instances",
        "parametres": "02_parametres",
        "grandes_tailles": "03_grandes_tailles",
    }[MODE]
    dossier.mkdir(parents=True, exist_ok=True)
    print(f"\n=== MODE : {MODE.upper()} ===")
    if MODE == "instances":
        etude_experimentale(dossier)
    elif MODE == "parametres":
        etude_parametres(dossier)
    else:
        etude_grandes_tailles(dossier)
    print("\nFichiers enregistrés dans :", dossier)
    print("Note : aucun GAP n'est calculé sans référence comparable.")


if __name__ == "__main__":
    main()
