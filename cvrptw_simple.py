import math
import random
from collections import deque

# ============================================================
# 1. GENERATION D'UNE INSTANCE ALEATOIRE REALISABLE
# ============================================================
def generer_instance(nb_clients=16, nb_camions=4, seed=42):
    rng = random.Random(seed)
    if nb_clients < 1 or nb_camions < 1:
        raise ValueError('Nombres de clients et de camions positifs requis')
    nb_camions = min(nb_clients, nb_camions)
    centres = [(rng.uniform(15, 85), rng.uniform(15, 85)) for _ in range(nb_camions)]
    positions = [(50, 50)]
    demandes = [0]
    groupes = [[] for _ in range(nb_camions)]
    for c in range(1, nb_clients + 1):
        k = (c - 1) % nb_camions
        x, y = centres[k]
        positions.append((x + rng.uniform(-9, 9), y + rng.uniform(-9, 9)))
        demandes.append(rng.randint(1, 5))
        groupes[k].append(c)
    distances = [[0 if i == j else math.ceil(math.dist(positions[i], positions[j]) * 1.2)
                  for j in range(nb_clients + 1)] for i in range(nb_clients + 1)]
    services = [0] + [5] * nb_clients
    fenetres = [(480, 1080)] + [(0, 0)] * nb_clients  # Depot : 8 h - 18 h
    temoin = []
    for groupe in groupes:
        rng.shuffle(groupe)
        heure, precedent = 480 + rng.randint(0, 40), 0
        for c in groupe:
            heure += distances[precedent][c]
            fenetres[c] = (max(480, heure - rng.randint(20, 40)),
                           heure + rng.randint(35, 60))
            heure += services[c]
            precedent = c
        if heure + distances[precedent][0] > 1080:
            raise ValueError('Instance trop grande pour la plage 8h-18h')
        temoin.append([0] + groupe + [0])
    return {
        'nb_clients': nb_clients, 'nb_camions': nb_camions,
        'capacite': max(sum(demandes[c] for c in g) for g in groupes) + 2,
        'depot': 0, 'demandes': demandes, 'distances': distances,
        'fenetres': fenetres, 'durees_service': services,
        'solution_temoin': temoin
    }


# ============================================================
# 2. SIMULATION ET VERIFICATION
# ============================================================
def simuler_tournee(tournee, instance):
    distances = instance['distances']
    fenetres = instance['fenetres']
    services = instance['durees_service']
    invalide = {'valide': False, 'depart': None, 'retour': None,
                'duree': None, 'livraisons': []}
    n = instance['nb_clients']
    if (len(tournee) < 3 or tournee[0] != 0 or tournee[-1] != 0
            or any(c < 1 or c > n for c in tournee[1:-1])):
        return invalide

    # Revenir en arriere depuis la fermeture du depot pour trouver
    # le depart le plus tardif realisable (et la duree minimale pour cet ordre).
    limite = fenetres[0][1]
    for i in range(len(tournee) - 2, 0, -1):
        c, suivant = tournee[i], tournee[i + 1]
        limite = min(fenetres[c][1], limite - distances[c][suivant] - services[c])
        if limite < fenetres[c][0]:
            return invalide
    depart = limite - distances[0][tournee[1]]
    if not fenetres[0][0] <= depart <= fenetres[0][1]:
        return invalide

    # Avancer dans le temps et enregistrer les livraisons.
    heure, livraisons = depart, []
    for i in range(1, len(tournee)):
        precedent, c = tournee[i - 1], tournee[i]
        arrivee = heure + distances[precedent][c]
        if c == 0:
            heure = arrivee
            if heure > fenetres[0][1]:
                return invalide
        else:
            livraison = max(arrivee, fenetres[c][0])
            if livraison > fenetres[c][1]:
                return invalide
            livraisons.append((c, livraison))
            heure = livraison + services[c]
    return {'valide': True, 'depart': depart, 'retour': heure,
            'duree': heure - depart, 'livraisons': livraisons}


def verifier_capacite(solution, instance):
    return all(sum(instance['demandes'][c] for c in t[1:-1]) <= instance['capacite']
               for t in solution)


def verifier_fenetres(solution, instance):
    return all(simuler_tournee(t, instance)['valide'] for t in solution)


def verifier_solution(solution, instance):
    if not (1 <= len(solution) <= instance['nb_camions']):
        return False
    clients = []
    for t in solution:
        if len(t) < 3 or t[0] != 0 or t[-1] != 0:
            return False
        clients += t[1:-1]
    if sorted(clients) != list(range(1, instance['nb_clients'] + 1)):
        return False
    return verifier_capacite(solution, instance) and verifier_fenetres(solution, instance)


def calcul_cout(solution, instance):
    if not verifier_solution(solution, instance):
        return math.inf
    return sum(simuler_tournee(t, instance)['duree'] for t in solution)


# ============================================================
# 3. SOLUTION INITIALE ET VOISINAGE
# ============================================================
def solution_initiale(instance):
    # La generation aleatoire construit au prealable des tournees realisables.
    # Elles servent de point de depart a la recherche tabou.
    return [t[:] for t in instance['solution_temoin']]


def voisinage(solution, instance):
    # SWAP : echange deux clients, y compris entre deux camions.
    positions = [(r, p) for r, t in enumerate(solution)
                 for p in range(1, len(t) - 1)]
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            r1, p1 = positions[i]
            r2, p2 = positions[j]
            voisin = [t[:] for t in solution]
            voisin[r1][p1], voisin[r2][p2] = voisin[r2][p2], voisin[r1][p1]
            if verifier_solution(voisin, instance):
                yield voisin

    # RELOCATE : deplacer un client a une autre position/tournee.
    for r1, p1 in positions:
        for r2 in range(len(solution)):
            for p2 in range(1, len(solution[r2])):
                if r1 == r2 and p2 in (p1, p1 + 1):
                    continue
                voisin = [t[:] for t in solution]
                c = voisin[r1].pop(p1)
                insertion = p2 - 1 if r1 == r2 and p2 > p1 else p2
                voisin[r2].insert(insertion, c)
                voisin = [t for t in voisin if len(t) > 2]
                if verifier_solution(voisin, instance):
                    yield voisin


def signature(solution):
    return tuple(sorted(tuple(t[1:-1]) for t in solution))


# ============================================================
# 4. RECHERCHE TABOU
# ============================================================
def recherche_tabou(instance, iter_max=100, taille_tabou=12):
    courante = solution_initiale(instance)
    meilleure = [t[:] for t in courante]
    meilleur_cout = calcul_cout(meilleure, instance)
    tabous = deque(maxlen=taille_tabou)
    iterations = 0

    for iteration in range(iter_max):
        choix, cout_choix = None, math.inf
        for voisin in voisinage(courante, instance):
            cout = calcul_cout(voisin, instance)
            if signature(voisin) in tabous and cout >= meilleur_cout:
                continue  # Aspiration si amelioration du meilleur cout global
            if cout < cout_choix:
                choix, cout_choix = voisin, cout
        if choix is None:
            break
        courante = choix
        tabous.append(signature(courante))
        iterations = iteration + 1
        if cout_choix < meilleur_cout:
            meilleure, meilleur_cout = [t[:] for t in courante], cout_choix
    return meilleure, meilleur_cout, iterations


# ============================================================
# 5. AFFICHAGE FINAL
# ============================================================
def hhmm(minutes):
    m = round(minutes)
    return f'{m // 60:02d}h{m % 60:02d}'


def afficher_resultats(solution, cout, instance, iterations):
    print('\n=== RESULTATS RECHERCHE TABOU ===')
    print('Solution valide :', verifier_solution(solution, instance))
    print('Iterations :', iterations)
    for k, tournee in enumerate(solution, start=1):
        s = simuler_tournee(tournee, instance)
        charge = sum(instance['demandes'][c] for c in tournee[1:-1])
        print(f'\nCamion {k} : ' + ' -> '.join(map(str, tournee)))
        print(f'  Depart : {hhmm(s["depart"])} | Retour : {hhmm(s["retour"])}')
        print(f'  Charge : {charge}/{instance["capacite"]} | Duree : {s["duree"]} min')
        for c, heure in s['livraisons']:
            print(f'    Client {c} livre a {hhmm(heure)}')
    print(f'\nCOUT TOTAL : {cout} minutes')
    print('Recherche heuristique : optimum global non garanti.')


if __name__ == '__main__':
    instance = generer_instance(nb_clients=16, nb_camions=4, seed=42)
    print(f'Instance aleatoire : {instance["nb_clients"]} clients, '
          f'{instance["nb_camions"]} camions, capacite {instance["capacite"]}')
    solution, cout, iterations = recherche_tabou(instance, iter_max=100, taille_tabou=12)
    afficher_resultats(solution, cout, instance, iterations)
