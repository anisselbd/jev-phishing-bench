# Brouillon de thread X (@Lbdev__)

Chiffres de results/report.md du 17 septembre 2026. Un tweet par idée.

---

**1.** (avec results/chart.png)

j'ai benchmarké jev, le "modèle de décision" de typesafe sorti il y a 2 jours, contre claude haiku 4.5 sur 2 000 emails de phishing. même emails, même consigne, un appel par email. repo public et méthode complète en fin de thread. voilà ce que ça donne

**2.**

d'abord ce que jev fait bien : 239 ms par email depuis la france, dont 163 ms de réseau. haiku : 687 ms. et 0,038 $ pour 1 000 emails contre 0,462 $. 12x moins cher, 3x plus rapide. ça, le pitch ne ment pas

**3.**

ensuite la précision, et là c'est moins joli. jev : 62,6 % d'accuracy, 43 % de rappel sur le phishing, 18 % de faux positifs. haiku : 81,3 %, 76 %, 14 %. sur 2 000 emails l'écart est énorme, test de mcnemar p < 0,0001

**4.**

où jev se plante : il fait confiance aux domaines connus. phishing hébergé sur google docs : 1,5 % détecté. sur github pages : 17 %. et à l'inverse il flague 45 % des mails légitimes qui pointent vers un outil tiers genre brex ou monday.com

**5.** (avec results/signals.png)

le truc vraiment intéressant. dans le même appel j'ai posé 5 questions plus simples : "le lien est sur un hébergement gratuit ?", "l'expéditeur est un gmail qui parle au nom d'une boîte ?", etc. ces signaux seuls sont excellents : auroc 0,96 et 0,94, contre 0,69 pour le verdict global

**6.**

attention au piège : une simple liste de raccourcisseurs et d'hébergeurs gratuits, sans aucune ia, fait déjà 91,8 % sur ce dataset. le meilleur signal jev seul fait moins bien, 89,4 %. en combinant les 5 signaux par une régression entraînée sur une moitié et mesurée sur l'autre, on arrive à 95,0 %. et haiku, à qui j'ai posé exactement les 5 mêmes questions, fait 93,2 % de la même façon, écart non significatif. jev est mauvais pour juger, correct pour observer, pas magique

**7.**

la calibration, l'angle que personne n'avait audité. jev : ece 0,154. entre 0,85 et 0,95 de proba il a raison 60 % du temps, surconfiant. au-dessus de 0,98 il a raison à 98 %, mais ça ne couvre que 7 % des emails. haiku : ece 0,097, mais il ne sort que 10 valeurs de proba différentes, 1 084 fois "0,95"

**8.**

stabilité : j'ai tout repassé une deuxième fois. jev change d'avis sur 2,2 % des emails, écart moyen de proba 0,017, écart max 0,15. haiku à température 0 : 98 % de probas strictement identiques, 0,7 % de changements d'avis, mais quand il bouge il bouge fort, écart max 0,65. jev n'est pas déterministe, il est juste stable

**9.**

les limites, parce que sinon ça vaut rien : corps d'emails synthétiques (dataset phishnchips, avril 2026, urls réelles), un seul prompt par système, latence mesurée depuis la france vers des serveurs us, haiku sans thinking. et le résumé publié du dataset a des chiffres que je n'ai pas réussi à reproduire, tout est dans le rapport

**10.**

conclusion perso : jev en classifieur "tout-en-un", non. jev en capteur de signaux atomiques, oui mais sans miracle : haiku fait des signaux aussi bons, pour 1 $ les 1 000 emails contre 0,04 $ et 5x plus lent. ce que tu achètes avec jev c'est le prix et la vitesse, pas l'intelligence. repo, rapport, code, tout est là : https://github.com/anisselbd/jev-phishing-bench

---

Notes pour la publication :
- Ne pas arrondir 62,6 en 63 ni 81,3 en 81 dans les visuels, garder les mêmes chiffres partout.
