# Thread à poster, dans l'ordre

19 tweets à la suite. Les tweets 1 à 9 forment le thread principal, les tweets 10 à 19 se postent en réponse au 9. Le nom de l'image à joindre est indiqué sous le tweet quand il y en a une (fichiers dans results/).

## Tweet 1

TypeSafe a sorti il y a 2 jours une IA "400x moins chère que ChatGPT". Je l'ai testée sur 2 000 mails de phishing. Elle se trompe une fois sur trois, mais elle a quand même un vrai intérêt. Thread.

Image : hero_vs_llms.png

## Tweet 2

J'ai donné les mêmes 2 000 mails à Jev et à Claude Haiku, un modèle classique pas cher. La question : cet email est-il une arnaque ? Jev a bon 62,6 % du temps, une erreur sur trois. Haiku 81,3 %, une erreur sur cinq. Sur 2 000 mails c'est pas un coup de chance.

Image : simple_precision.png

## Tweet 3

Par contre sur la vitesse et le prix, la promesse tient. Jev répond en 0,24 seconde, Haiku en 0,69. Et 1 000 mails coûtent 4 centimes avec Jev contre 46 avec Haiku. 3x plus rapide, 12x moins cher.

Image : simple_speed_cost.png

## Tweet 4

Là où Jev se fait avoir c'est qu'il fait confiance aux grands noms. Un phishing hébergé sur Google Docs, il le laisse passer 98 fois sur 100. Sur GitHub, 83 fois sur 100. Et un collègue qui vous envoie un lien Monday.com ou Brex, il le prend pour un pirate une fois sur deux mdr

Pas d'image

## Tweet 5

J'ai ensuite testé l'astuce que TypeSafe recommande. Au lieu d'une grande question ("c'est du phishing ?"), on pose 5 petites questions simples dans le même appel. "Le lien est sur un hébergeur gratuit ?", "L'expéditeur utilise un Gmail en se faisant passer pour une entreprise ?", etc. Et c'est votre code qui combine les réponses.

Pas d'image

## Tweet 6

Là Jev passe de 62,6 % à 95,0 %. Impressionnant. Sauf que. Une bête liste d'hébergeurs gratuits, sans aucune IA, fait déjà 91,8 % sur ce jeu de mails. Et Haiku, avec exactement les 5 mêmes questions, fait 93,2 %, un écart avec Jev qui est pas significatif. Jev observe bien, mais pas mieux qu'un autre.

Image : simple_signals.png

## Tweet 7

Ce qui m'inquiète le plus. Jev donne un pourcentage de certitude censé être fiable. Quand il dit "sûr à 90 %", il a raison 60 % du temps. Il est vraiment fiable qu'au-dessus de 98 %, et ça concerne 7 mails sur 100. Par contre il est stable. Reposez-lui la même question 12 heures plus tard, il change d'avis sur 1 mail sur 100.

Pas d'image

## Tweet 8

Ma conclusion. Jev comme détecteur tout seul, non. Jev comme capteur de petits signaux que votre code assemble, oui, à condition de savoir que Haiku fait aussi bien pour 27x plus cher. Ce que vous achetez c'est le prix et la vitesse, pas l'intelligence. Tout le code, les mails et les chiffres sont publics : https://github.com/anisselbd/jev-phishing-bench

Pas d'image

## Tweet 9

Pour ceux qui veulent les vrais chiffres, calibration, stabilité, intervalles de confiance, la version technique continue en dessous.

Pas d'image

## Tweet 10

Le protocole. Jev (TypeSafe, modèle jev-latest) contre Claude Haiku 4.5, sans thinking, sur les 2 000 mails de PhishNChips. Mêmes mails, même consigne, un appel par mail, appels séquentiels pour mesurer la latence proprement. Tout le code est dans le repo.

Image : chart.png

## Tweet 11

Ce que Jev fait bien, c'est la vitesse et le prix. 239 ms par mail depuis la France (dont 163 ms de réseau) contre 687 ms pour Haiku. Et 4 centimes les 1 000 mails contre 46. 3x plus rapide, 12x moins cher. Là-dessus le pitch tient.

Pas d'image

## Tweet 12

La précision par contre c'est une autre histoire. Jev a bon 62,6 % du temps, Haiku 81,3 %. Sur le phishing Jev en attrape 43 %, Haiku 76 %. Et Jev bloque 18 % des mails légitimes, Haiku 14 %. Sur 2 000 mails c'est pas du bruit, McNemar p < 0,0001.

Pas d'image

## Tweet 13

Où Jev se plante. Il fait confiance aux domaines connus. Phishing hébergé sur Google Docs, 1,5 % détecté. GitHub Pages, 17 %. Et dans l'autre sens il flague 45 % des mails légitimes qui pointent vers un outil tiers genre Brex ou Monday.com

Pas d'image

## Tweet 14

Le truc vraiment intéressant. Dans le même appel j'ai posé 5 questions plus simples. "Le lien est sur un hébergement gratuit ?", "L'expéditeur est un Gmail qui parle au nom d'une boîte ?", etc. Ces signaux seuls sont excellents. AUROC 0,96 et 0,94, contre 0,69 pour le verdict global.

Image : signals.png

## Tweet 15

Attention au piège. Une simple liste de raccourcisseurs et d'hébergeurs gratuits, sans aucune IA, fait déjà 91,8 % sur ce dataset. Le meilleur signal Jev seul fait moins, 89,4 %. En combinant les 5 signaux (régression entraînée sur une moitié, mesurée sur l'autre) on monte à 95,0 %. Et Haiku avec exactement les 5 mêmes questions fait 93,2 %, écart pas significatif. Jev observe bien, il juge mal, et y a rien de magique là-dedans.

Pas d'image

## Tweet 16

La calibration, ce que personne avait audité. Jev, ECE 0,154. Quand il sort une proba entre 0,85 et 0,95 il a raison 60 % du temps. Surconfiant. Au-dessus de 0,98 il a raison à 98 % mais ça couvre que 7 % des mails. Haiku, ECE 0,097, mais il sort que 10 valeurs de proba différentes. 1 084 fois "0,95" mdr

Pas d'image

## Tweet 17

Stabilité. J'ai tout repassé une deuxième fois. Jev change d'avis sur 2,2 % des mails, écart moyen de proba 0,017, max 0,15. Haiku à température 0 sort 98 % de probas strictement identiques et change d'avis sur 0,7 %, mais quand il bouge il bouge FORT, écart max 0,65. 12 h plus tard sur 200 mails, pareil. Jev est pas déterministe, il est stable.

Pas d'image

## Tweet 18

Les limites, parce que sans ça le thread vaut rien. Corps de mails synthétiques (dataset PhishNChips, avril 2026, URLs réelles). Un seul prompt par système. Latence mesurée depuis la France vers des serveurs US. Haiku sans thinking. Et le résumé publié du dataset a des chiffres que j'ai pas réussi à reproduire, tout est dans le rapport.

Pas d'image

## Tweet 19

Ma conclusion. Jev en classifieur tout-en-un, non. Jev en capteur de signaux atomiques, oui, mais Haiku fait des signaux aussi bons pour 1 $ les 1 000 mails contre 4 centimes, et 5x plus lent. Ce que vous achetez c'est le prix et la vitesse, pas l'intelligence. Repo, rapport, code, tout est là : https://github.com/anisselbd/jev-phishing-bench

Pas d'image
