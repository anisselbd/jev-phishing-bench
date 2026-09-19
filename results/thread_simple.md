# Thread X grand public (@Lbdev__)

Version sans jargon, c'est le thread à poster. Mêmes chiffres que results/report.md, arrondis à une décimale comme dans les images. Un tweet par idée, 8 tweets plus un tweet de transition vers le thread technique, posté en réponse. Voix calquée sur les tweets du compte (majuscules normales, "ne" supprimé, lecteur tutoyé ou vouvoyé, phrases courtes).

Images : hero_vs_llms.png ou hero_vs_haiku.png sur le 1 (voir note en bas), simple_precision.png sur le 2, simple_speed_cost.png sur le 3, simple_signals.png sur le 6.

---

**1.**

TypeSafe a sorti il y a 2 jours une IA "400x moins chère que ChatGPT". Je l'ai testée sur 2 000 mails de phishing. Elle se trompe une fois sur trois, mais elle a quand même un vrai intérêt. Thread.

**2.** (image : simple_precision.png)

J'ai donné les mêmes 2 000 mails à Jev et à Claude Haiku, un modèle classique pas cher. La question : cet email est-il une arnaque ? Jev a bon 62,6 % du temps, une erreur sur trois. Haiku 81,3 %, une erreur sur cinq. Sur 2 000 mails c'est pas un coup de chance.

**3.** (image : simple_speed_cost.png)

Par contre sur la vitesse et le prix, la promesse tient. Jev répond en 0,24 seconde, Haiku en 0,69. Et 1 000 mails coûtent 4 centimes avec Jev contre 46 avec Haiku. 3x plus rapide, 12x moins cher.

**4.**

Là où Jev se fait avoir c'est qu'il fait confiance aux grands noms. Un phishing hébergé sur Google Docs, il le laisse passer 98 fois sur 100. Sur GitHub, 83 fois sur 100. Et un collègue qui vous envoie un lien Monday.com ou Brex, il le prend pour un pirate une fois sur deux mdr

**5.**

J'ai ensuite testé l'astuce que TypeSafe recommande. Au lieu d'une grande question ("c'est du phishing ?"), on pose 5 petites questions simples dans le même appel. "Le lien est sur un hébergeur gratuit ?", "L'expéditeur utilise un Gmail en se faisant passer pour une entreprise ?", etc. Et c'est votre code qui combine les réponses.

**6.** (image : simple_signals.png)

Là Jev passe de 62,6 % à 95,0 %. Impressionnant. Sauf que. Une bête liste d'hébergeurs gratuits, sans aucune IA, fait déjà 91,8 % sur ce jeu de mails. Et Haiku, avec exactement les 5 mêmes questions, fait 93,2 %, un écart avec Jev qui est pas significatif. Jev observe bien, mais pas mieux qu'un autre.

**7.**

Ce qui m'inquiète le plus. Jev donne un pourcentage de certitude censé être fiable. Quand il dit "sûr à 90 %", il a raison 60 % du temps. Il est vraiment fiable qu'au-dessus de 98 %, et ça concerne 7 mails sur 100. Par contre il est stable. Reposez-lui la même question 12 heures plus tard, il change d'avis sur 1 mail sur 100.

**8.**

Ma conclusion. Jev comme détecteur tout seul, non. Jev comme capteur de petits signaux que votre code assemble, oui, à condition de savoir que Haiku fait aussi bien pour 27x plus cher. Ce que vous achetez c'est le prix et la vitesse, pas l'intelligence. Tout le code, les mails et les chiffres sont publics : https://github.com/anisselbd/jev-phishing-bench

**9.** (transition, en réponse au 8, puis le thread technique de thread.md à la suite)

Pour ceux qui veulent les vrais chiffres, calibration, stabilité, intervalles de confiance, la version technique continue en dessous.

---

Notes pour la publication :
- Précautions gardées volontairement : "sur ce jeu de mails" au tweet 6, "pas un coup de chance" au tweet 2 (test statistique dans le rapport).
- Les limites (emails synthétiques, un seul prompt, latence depuis la France) sont dans le README, pas dans le thread grand public. Si quelqu'un demande, renvoyer au rapport.
- Le thread technique reste dans thread.md pour les gens qui veulent les AUROC et les intervalles.
- Image du tweet 1 : hero_vs_llms.png montre Jev face à Claude, GPT, Gemini et DeepSeek, c'est la promesse de TypeSafe ("400x moins cher que ChatGPT"), pas le protocole. Seul Claude Haiku 4.5 a été benchmarké. hero_vs_haiku.png est la version fidèle au test. Si hero_vs_llms.png est retenue, le tweet 2 doit rester tel quel (il nomme Haiku) pour que personne ne croie que GPT, Gemini ou DeepSeek ont été testés.
