# Brouillon de thread X (@Lbdev__), version technique

Posté en réponse au tweet de transition de thread_simple.md, pas comme thread autonome. Chiffres de results/report.md du 17 septembre 2026. Un tweet par idée. Voix calquée sur les tweets du compte (majuscules normales, "ne" supprimé, lecteur tutoyé ou vouvoyé, phrases courtes, MAJUSCULES pour appuyer).

---

**1.** (avec results/chart.png)

Le protocole. Jev (TypeSafe, modèle jev-latest) contre Claude Haiku 4.5, sans thinking, sur les 2 000 mails de PhishNChips. Mêmes mails, même consigne, un appel par mail, appels séquentiels pour mesurer la latence proprement. Tout le code est dans le repo.

**2.**

Ce que Jev fait bien, c'est la vitesse et le prix. 239 ms par mail depuis la France (dont 163 ms de réseau) contre 687 ms pour Haiku. Et 4 centimes les 1 000 mails contre 46. 3x plus rapide, 12x moins cher. Là-dessus le pitch tient.

**3.**

La précision par contre c'est une autre histoire. Jev a bon 62,6 % du temps, Haiku 81,3 %. Sur le phishing Jev en attrape 43 %, Haiku 76 %. Et Jev bloque 18 % des mails légitimes, Haiku 14 %. Sur 2 000 mails c'est pas du bruit, McNemar p < 0,0001.

**4.**

Où Jev se plante. Il fait confiance aux domaines connus. Phishing hébergé sur Google Docs, 1,5 % détecté. GitHub Pages, 17 %. Et dans l'autre sens il flague 45 % des mails légitimes qui pointent vers un outil tiers genre Brex ou Monday.com

**5.** (avec results/signals.png)

Le truc vraiment intéressant. Dans le même appel j'ai posé 5 questions plus simples. "Le lien est sur un hébergement gratuit ?", "L'expéditeur est un Gmail qui parle au nom d'une boîte ?", etc. Ces signaux seuls sont excellents. AUROC 0,96 et 0,94, contre 0,69 pour le verdict global.

**6.**

Attention au piège. Une simple liste de raccourcisseurs et d'hébergeurs gratuits, sans aucune IA, fait déjà 91,8 % sur ce dataset. Le meilleur signal Jev seul fait moins, 89,4 %. En combinant les 5 signaux (régression entraînée sur une moitié, mesurée sur l'autre) on monte à 95,0 %. Et Haiku avec exactement les 5 mêmes questions fait 93,2 %, écart pas significatif. Jev observe bien, il juge mal, et y a rien de magique là-dedans.

**7.**

La calibration, ce que personne avait audité. Jev, ECE 0,154. Quand il sort une proba entre 0,85 et 0,95 il a raison 60 % du temps. Surconfiant. Au-dessus de 0,98 il a raison à 98 % mais ça couvre que 7 % des mails. Haiku, ECE 0,097, mais il sort que 10 valeurs de proba différentes. 1 084 fois "0,95" mdr

**8.**

Stabilité. J'ai tout repassé une deuxième fois. Jev change d'avis sur 2,2 % des mails, écart moyen de proba 0,017, max 0,15. Haiku à température 0 sort 98 % de probas strictement identiques et change d'avis sur 0,7 %, mais quand il bouge il bouge FORT, écart max 0,65. 12 h plus tard sur 200 mails, pareil. Jev est pas déterministe, il est stable.

**9.**

Les limites, parce que sans ça le thread vaut rien. Corps de mails synthétiques (dataset PhishNChips, avril 2026, URLs réelles). Un seul prompt par système. Latence mesurée depuis la France vers des serveurs US. Haiku sans thinking. Et le résumé publié du dataset a des chiffres que j'ai pas réussi à reproduire, tout est dans le rapport.

**10.**

Ma conclusion. Jev en classifieur tout-en-un, non. Jev en capteur de signaux atomiques, oui, mais Haiku fait des signaux aussi bons pour 1 $ les 1 000 mails contre 4 centimes, et 5x plus lent. Ce que vous achetez c'est le prix et la vitesse, pas l'intelligence. Repo, rapport, code, tout est là : https://github.com/anisselbd/jev-phishing-bench

---

Notes pour la publication :
- Ne pas arrondir 62,6 en 63 ni 81,3 en 81 dans les visuels, garder les mêmes chiffres partout.
- Les prix sont en dollars catalogue (0,038 $ et 0,462 $ pour 1 000 mails). "4 centimes" et "46 centimes" sont des arrondis, le rapport a les valeurs exactes.
