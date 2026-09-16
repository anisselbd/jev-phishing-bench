# Jev phishing bench

**Statut de ce document.** Les sections "Objectif", "Contexte" et "Règles" sont des contraintes. La section "Design du benchmark" contient les décisions validées le 16 septembre 2026 après vérification de la doc TypeSafe et recherche de datasets. Elle remplace le premier jet. Toute modification de design se discute avant d'être codée.

## Objectif

Construire un benchmark public et reproductible de détection de phishing qui compare **Jev** (TypeSafe AI) à un **LLM classique**, puis publier les résultats sur X (@Lbdev__) avec graphiques et repo GitHub public.

Le message à démontrer avec des chiffres, pas avec des adjectifs : sur une tâche de décision de sécurité, Jev est-il assez précis, bien calibré, et combien plus rapide et moins cher qu'un LLM ? La valeur du post repose entièrement sur la crédibilité de la méthode : chaque chiffre doit être reproductible et chaque limite assumée.

## Contexte : Jev / TypeSafe AI

- TypeSafe AI a lancé Jev le 15 septembre 2026, en early access. L'accès au compte est actif.
- Jev ne génère pas de texte. Il reçoit un `state` (texte ou JSON) et des questions typées, et renvoie des réponses typées avec probabilités calibrées.
- Trois primitives, mélangeables dans un même appel, évaluées en parallèle et indépendamment :
  - `choice` : choisir une option parmi une liste (max 255 options). Renvoie `choice`, `probabilities`, `confidence`.
  - `score` : noter sur une échelle ordonnée. Renvoie `score`, `legend`, `probabilities`, `confidence`.
  - `noul` : probabilité qu'une affirmation soit vraie. Renvoie `noul` (0 à 1), sans `confidence`.
- Limites documentées : budget d'environ 32 000 tokens par requête (state et questions compris), soit environ 150 000 caractères. Le `state` est une string, un objet ou un tableau JSON : texte seulement. Service hébergé aux États-Unis (source tierce, la doc ne le précise pas).
- Prix : 42 $ par milliard de tokens d'entrée (page d'accueil typesafe.ai), soit 0,042 $ par million. Aucun prix de sortie n'est publié. Le benchmark facture l'entrée seule et le dit.
- `confidence` d'un choice est dérivée de `probabilities`. Sur un choice à deux options, c'est une fonction déterministe de la probabilité max : ne pas la présenter comme un signal supplémentaire.
- Seul test indépendant publié (Every, Mike Taylor) : 0,35 s contre 8,83 s par passage face à Claude Fable 5.1, environ 25x plus rapide et 580x moins cher, mais 6 défauts détectés sur 7 contre 7 sur 7. Sur le dashboard TypeSafe, score agrégé 67,8 %, à égalité avec Sonnet 5. Attention : la référence de ces évals est la moyenne des réponses de GPT-6 Astra et Claude Fable 5.1, donc elles mesurent un accord entre modèles, pas une exactitude. Personne n'a publié d'audit de calibration indépendant : c'est l'angle du projet.

### API (vérifiée contre https://docs.typesafe.ai/api.md le 16 septembre 2026)

```
POST https://api.typesafe.ai/v1/systemone
Authorization: Bearer $TYPESAFE_API_KEY
Content-Type: application/json

{
  "state": {"from": "...", "subject": "...", "body": "..."},
  "model": "jev-latest",
  "questions": {
    "verdict": {"type": "choice", "instructions": "...", "criteria": {"phishing": "...", "legitimate": "..."}},
    "urgency": {"type": "noul", "instructions": "...", "criteria": {"true": "...", "false": "..."}}
  }
}
```

- Réponse : `model`, `answers.<id>` (mêmes clés que les questions, chaque réponse porte `type`), `usage.input_tokens` et `usage.output_tokens`.
- `criteria` est obligatoire pour choice (map option vers description ou `null`) et score (liste ordonnée), optionnel pour noul (`{"true": ..., "false": ...}`).
- Les IDs de questions ne sont pas envoyés au modèle : écrire la question complète dans `instructions`. Nommer les champs du state avec des chemins entre backticks, par exemple `` `link_url` ``.
- Erreurs : 401 clé invalide, 422 requête invalide, 429 rate limit, 529 surcharge. Retry avec backoff exponentiel sur 429 et 529.
- Docs : https://docs.typesafe.ai (index pour agents : https://docs.typesafe.ai/llms.txt). Skill installé : plugin `typesafe@typesafe-ai`.
- SDK dispos (Python `typesafe-sdk`, JS `@typesafe-ai/sdk`) mais le projet utilise l'API HTTP directe pour mesurer la latence sans couche intermédiaire et ne dépendre d'aucune signature non vérifiée.

## Design du benchmark (décisions validées)

### Données
- Dataset principal : **PhishNChips v5.2**, Hugging Face `AreLit/PhishNChips`, publié en avril 2026. 2 000 emails, 1 000 phishing et 1 000 légitimes. Corps générés par LLM autour d'URLs réelles (PhishTank, OpenPhish, GitHub Phishing DB pour le phishing, domaines Tranco pour le légitime). Licence MIT pour le contenu synthétique, sources tierces attribuées dans `SOURCE_LICENSES.md`.
- Pourquoi : postérieur à l'entraînement des baselines choisies, non saturé (rappel LLM de 0,27 à 0,96 selon le prompt système dans la grille publiée), et surtout accompagné d'une grille de 220 000 évaluations (11 modèles x 10 prompts) qui permet de vérifier que notre pipeline reproduit les chiffres publiés.
- Cadrage de la tâche, repris des auteurs : un agent email doit décider si l'utilisateur doit cliquer le lien. Le signal est dans l'URL, l'expéditeur et leur cohérence, pas dans un style maladroit.
- Limites à assumer : corps synthétiques, homogénéité des templates, vérité terrain fondée sur la réputation de l'URL.
- Les fichiers sont téléchargés au runtime dans `data/` (jamais commités) et vérifiés par SHA-256 contre le manifeste de la release.
- Ordre des emails fixé par une seed. Les 2 000 emails sont utilisés en entier.
- Set secondaire, en extension seulement : les 205 emails privés humains de 2024 à 2026 de PhishFuzzer (GitHub `DataPhish/PhishFuzzer`, pas de fichier LICENSE, téléchargement au runtime).
- Écartés : Kaggle "Phishing Email Detection" (2002 à 2008, vu à l'entraînement, saturé), CIC-Trap4Phish 2025 (pièces jointes sans corps), corpus Frontiers 2026 (features seulement), PhishFuzzer complet (légitimes de 2002 et 2008 contre phishing de 2015 à 2022).

### Appel Jev
Une requête par email, `state` en objet JSON avec les champs natifs du dataset (`sender`, `from`, `subject`, `body`, `link_display_text`, `link_url`). Questions dans le même appel :
- `verdict` : choice `phishing` / `legitimate`, instructions calquées sur le prompt "balanced" des auteurs. Sert à l'accuracy, l'ECE, l'AUROC et la courbe d'auto-décision.
- `is_phishing` : noul miroir de la même question, pour comparer la calibration des deux primitives.
- 5 signaux noul : domaine de l'expéditeur différent du domaine du lien, lien vers un hébergement gratuit ou un raccourcisseur, demande de connexion ou d'ouverture de document, urgence ou pression, expéditeur webmail générique se présentant au nom d'une organisation.
- Extension gratuite : deux formulations alternatives de la question verdict dans le même appel pour mesurer la sensibilité de Jev à la formulation.

### Baseline LLM
- Gemini 3 Flash via l'offre gratuite Google AI Studio, endpoint compatible OpenAI (`https://generativelanguage.googleapis.com/v1beta/openai/`). Présent dans la grille publiée, sorti avant le dataset, prix catalogue connu. Gemini 2.5 Flash est en tête de la grille mais retiré le 16 octobre 2026.
- Repli si le quota bloque : Groq avec Llama 4 Scout, lui aussi dans la grille.
- Client générique compatible OpenAI configuré par `.env` : `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_PRICE_IN`, `LLM_PRICE_OUT` (prix catalogue en dollars par million de tokens, toujours renseignés même en offre gratuite).
- Prompt système "balanced" des auteurs repris mot pour mot, seule la ligne de format de réponse change : JSON `{"click": 0|1, "phishing_probability": 0..1}`. Température 0. Le thinking ne peut pas être coupé sur les modèles Gemini 3 (doc de la couche compatible OpenAI), il est donc réglé au minimum disponible via `LLM_EXTRA_BODY={"reasoning_effort": "low"}` : configuration la plus favorable au LLM sur latence et coût.
- Les JSON invalides sont comptés comme erreurs de format, métrique publiée, impossible côté Jev.
- Contrôle de reproduction : rappel et taux de faux positifs comparés à la ligne correspondante de `reference_results.csv`.

### Métriques (toutes avec intervalle de confiance à 95 %)
- Accuracy, précision, rappel, taux de faux positifs, F1 au seuil 0,5, AUROC sur les probabilités.
- Calibration : ECE 10 bins, Brier, diagramme de fiabilité. Jev sur `probabilities`, LLM sur la probabilité verbalisée.
- Courbe d'auto-décision : à chaque seuil de probabilité max, part des emails traités sans humain et précision sur ceux-là. Même axe pour les deux systèmes.
- Latence p50 et p95 par email, appels séquentiels sans concurrence, plus un plancher réseau mesuré par un aller-retour TLS vers chaque hôte.
- Coût total et pour 1 000 emails, sur les tokens réels d'`usage`, prix catalogue des deux côtés.
- Erreurs de format et erreurs API.
- Test de McNemar apparié sur les 2 000 emails pour l'écart d'accuracy.
- Stabilité : Jev repassé sur les 2 000 emails juste après la première passe, puis 200 emails 24 h plus tard. LLM repassé sur 300 emails. Rapporter moyenne et maximum de l'écart absolu de probabilité, taux de changement d'étiquette, corrélation.

### Livrables
- `results/report.md` : tableau comparatif, tableau d'auto-décision, tableau de stabilité, comparaison avec la grille publiée.
- `results/chart.png` : 4 panneaux (calibration, auto-décision, latence log, coût log), thème sombre lisible sur X.
- `results/signals.png` : moyenne des 5 signaux Jev, phishing vs légitime.
- README propre pour le repo public, avec méthode et limites.
- Brouillon de thread X à partir des résultats réels.

## Ordre de travail

1. `.gitignore` (`.env`, `data/`, `results/*.jsonl`) avant tout commit contenant des clés ou des données.
2. `prepare_data.py` : téléchargement, vérification SHA-256, `data/emails.jsonl`.
3. `run_jev.py --limit 10`, inspecter les réponses brutes, puis le run complet, puis la passe 2.
4. `analyze.py` en mode Jev seul.
5. Configurer et lancer la baseline LLM, vérifier la reproduction de la grille.
6. Rapport, graphiques, relecture critique des chiffres.
7. README final, repo GitHub public, brouillon de thread.

## Règles

- Commits petits et fréquents, messages clairs (conventional commits).
- Jamais de clé API dans le code, les logs ou l'historique git. Ne jamais demander la clé dans le chat : elle est dans `.env`.
- Runs reprenables : ne jamais refacturer un email déjà traité.
- Ne pas embellir : si Jev perd sur la précision, le dire. Les limites à mentionner dans le README et le post : corps d'emails synthétiques, signal surtout dans l'URL, latence mesurée depuis la France vers des services US, un seul prompt par système alors que la grille publiée montre une forte sensibilité au prompt, prix de sortie Jev non publié.
- Style de rédaction (README, rapport, thread) : jamais de tiret cadratin ni demi-cadratin, utiliser deux-points, virgules, parenthèses ou tirets simples. Ton factuel, les chiffres parlent seuls.
- Style des tweets : ton naturel et parlé, minuscules acceptées, une idée par tweet, pas de structure LinkedIn, pas de conclusion morale.
