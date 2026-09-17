# Thread X grand public (@Lbdev__)

Version sans jargon. Mêmes chiffres que results/report.md, arrondis à une décimale comme dans les images. Un tweet par idée, 8 tweets.

Images : simple_precision.png sur le 2, simple_speed_cost.png sur le 3, simple_signals.png sur le 6.

---

**1.**

une startup, typesafe, a sorti "jev" il y a 2 jours : une ia qui ne parle pas, elle répond juste oui, non, ou "à 73 % oui". promesse : 200 fois plus rapide et 400 fois moins chère que chatgpt et compagnie. j'ai voulu vérifier sur un vrai problème : repérer des emails de phishing. voilà ce que ça donne

**2.** (image : simple_precision.png)

j'ai donné les mêmes 2 000 emails à jev et à claude haiku, un modèle "classique" pas cher. la question : cet email est-il une arnaque ? jev a bon 62,6 % du temps, soit une erreur sur trois. haiku : 81,3 %, une erreur sur cinq. sur 2 000 emails, l'écart est énorme, pas un coup de chance

**3.** (image : simple_speed_cost.png)

par contre sur la vitesse et le prix, la promesse tient. jev répond en 0,24 seconde, haiku en 0,69. et 1 000 emails coûtent 4 centimes avec jev contre 46 centimes avec haiku. 3 fois plus rapide, 12 fois moins cher

**4.**

où jev se fait avoir : il fait confiance aux grands noms. un lien de phishing hébergé sur google docs ? il le laisse passer 98 fois sur 100. sur github ? 83 fois sur 100. à l'inverse, un collègue qui envoie un lien vers un outil externe comme brex ou monday.com, jev le prend pour un pirate presque une fois sur deux

**5.**

j'ai ensuite testé l'astuce que typesafe recommande : au lieu d'une grande question ("est-ce du phishing ?"), poser 5 petites questions simples dans le même appel. "le lien est-il sur un hébergeur gratuit ?", "l'expéditeur utilise-t-il un gmail en se faisant passer pour une entreprise ?", etc. puis c'est mon code qui combine les réponses

**6.** (image : simple_signals.png)

là jev passe de 62,6 % à 95,0 %. impressionnant, sauf que. une bête liste d'hébergeurs gratuits, sans aucune ia, fait déjà 91,8 % sur ce jeu d'emails. et haiku, à qui j'ai posé exactement les 5 mêmes questions, fait 93,2 %, un écart avec jev qui n'est pas significatif. jev observe bien, mais pas mieux qu'un autre

**7.**

le point le plus sérieux : jev donne un pourcentage de certitude, censé être fiable. quand il dit "sûr à 90 %", il a raison 60 % du temps. il n'est vraiment fiable qu'au-dessus de 98 %, et ça ne concerne que 7 emails sur 100. par contre il est stable : reposez-lui la même question 12 heures plus tard, il change d'avis sur 1 email sur 100

**8.**

ma conclusion : jev comme détecteur tout seul, non. jev comme capteur de petits signaux que votre code assemble, oui, à condition de savoir que haiku fait aussi bien pour 27 fois plus cher. ce qu'on achète, c'est le prix et la vitesse, pas l'intelligence. tout le code, les emails et les chiffres sont publics : https://github.com/anisselbd/jev-phishing-bench

---

Notes pour la publication :
- Précautions gardées volontairement : "sur ce jeu d'emails" au tweet 6, "pas un coup de chance" au tweet 2 (test statistique dans le rapport).
- Les limites (emails synthétiques, un seul prompt, latence depuis la France) sont dans le README, pas dans le thread grand public. Si quelqu'un demande, renvoyer au rapport.
- Le thread technique reste dans thread.md pour les gens qui veulent les AUROC et les intervalles.
