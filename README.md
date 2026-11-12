# Livrable final ADEME : tournées de livraison (CVRPTW)

Groupe 1 : Sandago, Emmanuel, Thomas.

## Les fichiers

| Fichier | Contenu |
| --- | --- |
| `Grp1_Livrable_Final_CVRPTW.ipynb` | Le notebook final : modélisation, méthode, réalisation, analyse de performance, résultats et interprétations |
| `cvrptw_analyse_solomon.py` | Le code final : recherche tabou à trois mouvements, instances de Solomon, études du chapitre VI |
| `cvrptw_analyse_pret.py` | La première version du code (mouvement SWAP seul) : études du chapitre V sur des instances générées |
| `tests_cvrptw.py` | Les cas de test (9 petits exemples dont on connaît la réponse) |
| `instances/solomon/25, 50, 100/` | 12 instances de Solomon (2 par classe), en 25, 50 et 100 clients |
| `resultats_cvrptw/` | Les résultats enregistrés : CSV, résumés et graphiques |
| `images/` | Les schémas du notebook |

## Installer

```
pip install vrplib matplotlib pandas jupyter
```

## Lancer

Les cas de test :

```
python tests_cvrptw.py
```

### La première version (chapitre V du notebook)

Changer la ligne `MODE = ...` de `cvrptw_analyse_pret.py`, puis lancer `python cvrptw_analyse_pret.py`. L'objectif est la durée.

| Mode | Ce qu'il fait | Résultats |
| --- | --- | --- |
| `instances` | Étude 1 : 60 instances générées (répartition, fenêtres, taille) | `resultats_cvrptw/01_instances/` |
| `parametres` | Étude 2 : effet des paramètres de la recherche tabou | `resultats_cvrptw/02_parametres/` |
| `grandes_tailles` | Étude 3 : 500, 1 000 et 2 000 clients générés | `resultats_cvrptw/03_grandes_tailles/` |
| `demo` | Une instance générée de 30 clients | affichage seul |

### Le code final (chapitre VI du notebook)

Changer la ligne `MODE = ...` en haut de la partie 5 de `cvrptw_analyse_solomon.py`, puis lancer `python cvrptw_analyse_solomon.py`.

| Mode | Ce qu'il fait | Objectif | Résultats |
| --- | --- | --- | --- |
| `demo_solomon` | 3 instances de Solomon (C101, R101, RC101 à 25 clients) | distance | affichage seul |
| `solomon` | 12 instances × 3 tailles × 3 graines, gap à l'optimum publié (environ 20 minutes) | distance | `resultats_cvrptw/04_solomon/` |
| `objectifs` | Durée ou distance : ce que l'on gagne et ce que l'on perd | les deux | `resultats_cvrptw/05_duree_ou_distance/` |

Le code final accepte aussi les modes `demo`, `instances`, `parametres` et `grandes_tailles`. Il écrit alors dans les dossiers 01 à 03 avec d'autres chiffres, puisqu'il utilise trois mouvements. Les chiffres du chapitre V et les fichiers enregistrés dans ces dossiers sont ceux de la première version.

Les temps de calcul dépendent de l'ordinateur : ils peuvent différer un peu de ceux du notebook. Les coûts et les gains, eux, sont les mêmes à chaque exécution.

## Pourquoi la distance pour Solomon

Les optimums publiés sont des distances totales. Dans les instances de Solomon, le temps de trajet `T_ij` est égal à la distance `d_ij`. Minimiser la distance revient donc à minimiser le temps de trajet. Les livraisons ont une durée fixe, et seule l'attente diffère de la durée totale. L'étude sur l'objectif (chapitre VI.3) mesure cette différence.
