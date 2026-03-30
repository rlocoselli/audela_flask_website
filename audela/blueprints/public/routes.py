import ast
from contextlib import redirect_stdout
from datetime import date, datetime
from io import StringIO
import traceback
from urllib.parse import urljoin

from flask import Response, current_app, redirect, render_template, request, session, url_for, flash, jsonify, g, make_response
from flask_login import current_user

from ...extensions import db
from ...models import Prospect
from ...models import Tenant
from ...services.subscription_service import SubscriptionService
from ...product_catalog import get_product_entry

from ...i18n import DEFAULT_LANG, SUPPORTED_LANGS, normalize_lang, tr

from . import bp


FINANCE_PLAN_CODES = {"free", "finance_starter", "finance_pro", "finance_banking", "all_in_one_pro"}
CUSTOM_CODE_MAX_CHARS = 4000
ALLOWED_PYTHON_MODULES = {"torch", "tensorflow", "math"}


ELEARNING_COPY: dict[str, dict[str, str]] = {
    "pt": {
        "title": "E-learning: IA, LLM, MCP e Tensores",
        "hero": "Conceitos práticos com exemplos Python executáveis nesta página.",
        "run": "Executar exemplo",
        "running": "Executando...",
        "output": "Saída",
        "error": "Erro",
        "no_output": "Sem saída.",
        "run_failed": "Falha ao executar o exemplo.",
        "security_note": "Os exemplos são pré-definidos e executados no servidor para manter segurança e previsibilidade.",
        "ai_title": "IA (Inteligência Artificial)",
        "ai_desc": "IA é o campo que permite que máquinas realizem tarefas que normalmente exigem inteligência humana, como classificação e previsão.",
        "llm_title": "LLM (Large Language Model)",
        "llm_desc": "Um LLM é um modelo de linguagem treinado em grande volume de texto para gerar, resumir e transformar conteúdo.",
        "mcp_title": "MCP (Model Context Protocol)",
        "mcp_desc": "MCP padroniza como ferramentas fornecem contexto para modelos, tornando integrações mais seguras e previsíveis.",
        "tensor_title": "Tensores",
        "tensor_desc": "Tensor é uma estrutura n-dimensional usada para representar dados em IA e deep learning (vetores, matrizes e volumes).",
        "pytorch_title": "PyTorch (rede neural minima)",
        "pytorch_desc": "Exemplo simples com camadas lineares para ver tensor de entrada e saida.",
        "tensorflow_title": "TensorFlow (Keras minima)",
        "tensorflow_desc": "Exemplo simples com modelo Sequential para entender inferencia em lote.",
        "tiny_llm_title": "Mini LLM pedagogico",
        "tiny_llm_desc": "Modelo de linguagem bem pequeno (bigramas) para ensinar token, logits e probabilidades.",
        "rag_title": "RAG (Retrieval-Augmented Generation)",
        "rag_desc": "RAG combina busca de conhecimento + geracao para respostas mais precisas e auditaveis.",
        "rag_step_1": "1) Indexe uma pequena base de conhecimento (docs).",
        "rag_step_2": "2) Recupere o melhor contexto para a pergunta.",
        "rag_step_3": "3) Monte o prompt final com pergunta + contexto recuperado.",
        "expected_output_label": "Saida esperada",
        "expected_ai": "Risk labels: ['low', 'high', 'low', 'high', 'low']",
        "expected_bigram": "Bigramas com pares de tokens e contagens, ex: ('ai', 'helps'): 1",
        "expected_mcp": "Context keys: ['user_intent', 'tool', 'constraints']\nTool selected: sql_query",
        "expected_tensor": "Shape: (2, 3)\nColumn sums: [5, 7, 9]",
        "expected_pytorch": "Input shape: (4, 3)\nOutput shape: (4, 1)\nFirst output: valor numerico",
        "expected_tensorflow": "Input shape: (4, 3)\nOutput shape: (4, 1)\nFirst output: valor numerico",
        "expected_tiny_llm": "Vocab: [...]\nLast input token: ...\nTop next-token probabilities: 3 linhas token-probabilidade",
        "expected_rag": "Query: ...\nTop document: ...\nPrompt preview: ...",
        "services_title": "Services AI dedies",
        "services_dedicated": "Serveurs AI dedies: GPU privee, isolation tenant, monitoring, SLA et MLOps.",
        "services_lgpd": "LGPD by design: minimizacao de dados, retention policy, trilha de auditoria, consentimento e direito ao apagamento.",
        "services_cta": "Queremos implantar seu AI server dedicado com compliance LGPD.",
        "step_by_step": "Passo a passo",
        "math_behind": "Matematica por tras",
        "open_lab": "Abrir laboratorio Python",
        "lab_title": "Laboratorio Python guiado",
        "lab_hero": "Escreva seu proprio codigo Python com editor assistido e execute com seguranca.",
        "lab_steps_title": "Como usar (passo a passo)",
        "lab_step_1": "1) Escolha um snippet guiado ou escreva seu codigo no editor.",
        "lab_step_2": "2) Clique em Executar para rodar no servidor com ambiente restrito.",
        "lab_step_3": "3) Leia a saida e ajuste seu codigo iterativamente.",
        "lab_step_4": "4) Use os blocos de matematica para conectar teoria e pratica.",
        "lab_editor_title": "Editor Python",
        "lab_snippets": "Snippets guiados",
        "lab_run": "Executar codigo",
        "lab_running": "Executando codigo...",
        "lab_placeholder": "# Escreva seu Python aqui\nprint('Hello AI Lab')",
        "lab_security": "Seguranca: apenas imports permitidos (torch, tensorflow, math) e operacoes seguras.",
        "lab_math_title": "Mini-guide mathematique",
        "lab_math_1": "Produit scalaire: y = w1*x1 + w2*x2 + b",
        "lab_math_2": "MSE: (1/n) * somme((y_pred - y_true)^2)",
        "lab_math_3": "Softmax: p_i = exp(z_i) / somme(exp(z_j))",
    },
    "en": {
        "title": "E-learning: AI, LLM, MCP and Tensors",
        "hero": "Practical concepts with runnable Python examples on this page.",
        "run": "Run example",
        "running": "Running...",
        "output": "Output",
        "error": "Error",
        "no_output": "No output.",
        "run_failed": "Failed to run the example.",
        "security_note": "Examples are predefined and executed on the server to keep execution safe and predictable.",
        "ai_title": "AI (Artificial Intelligence)",
        "ai_desc": "AI is the field that enables machines to perform tasks that usually require human intelligence, such as classification and prediction.",
        "llm_title": "LLM (Large Language Model)",
        "llm_desc": "An LLM is a language model trained on large text corpora to generate, summarize, and transform content.",
        "mcp_title": "MCP (Model Context Protocol)",
        "mcp_desc": "MCP standardizes how tools provide context to models, making integrations safer and more predictable.",
        "tensor_title": "Tensors",
        "tensor_desc": "A tensor is an n-dimensional structure used to represent data in AI and deep learning (vectors, matrices, and volumes).",
        "pytorch_title": "PyTorch (minimal neural net)",
        "pytorch_desc": "Simple example with linear layers to inspect input and output tensors.",
        "tensorflow_title": "TensorFlow (minimal Keras)",
        "tensorflow_desc": "Simple Sequential model example to understand batch inference.",
        "tiny_llm_title": "Tiny teaching LLM",
        "tiny_llm_desc": "Very small language model (bigrams) to teach tokens, logits, and probabilities.",
        "rag_title": "RAG (Retrieval-Augmented Generation)",
        "rag_desc": "RAG combines retrieval + generation to produce more grounded and auditable answers.",
        "rag_step_1": "1) Index a small knowledge base (docs).",
        "rag_step_2": "2) Retrieve the best context for the query.",
        "rag_step_3": "3) Build the final prompt with question + retrieved context.",
        "expected_output_label": "Expected output",
        "expected_ai": "Risk labels: ['low', 'high', 'low', 'high', 'low']",
        "expected_bigram": "Bigrams with token pairs and counts, e.g. ('ai', 'helps'): 1",
        "expected_mcp": "Context keys: ['user_intent', 'tool', 'constraints']\nTool selected: sql_query",
        "expected_tensor": "Shape: (2, 3)\nColumn sums: [5, 7, 9]",
        "expected_pytorch": "Input shape: (4, 3)\nOutput shape: (4, 1)\nFirst output: numeric value",
        "expected_tensorflow": "Input shape: (4, 3)\nOutput shape: (4, 1)\nFirst output: numeric value",
        "expected_tiny_llm": "Vocab: [...]\nLast input token: ...\nTop next-token probabilities: three token-probability lines",
        "expected_rag": "Query: ...\nTop document: ...\nPrompt preview: ...",
        "services_title": "Dedicated AI services",
        "services_dedicated": "Dedicated AI servers: private GPU, tenant isolation, monitoring, SLA, and MLOps.",
        "services_lgpd": "LGPD by design: data minimization, retention policy, audit trail, consent management, and right to erasure.",
        "services_cta": "We can deploy your dedicated AI server with LGPD compliance.",
        "step_by_step": "Step by step",
        "math_behind": "Math behind",
        "open_lab": "Open Python Lab",
        "lab_title": "Guided Python Lab",
        "lab_hero": "Write your own Python code with an assisted editor and run it safely.",
        "lab_steps_title": "How to use (step by step)",
        "lab_step_1": "1) Pick a guided snippet or write your own code in the editor.",
        "lab_step_2": "2) Click Run to execute on the server in a restricted environment.",
        "lab_step_3": "3) Read output and refine your code iteratively.",
        "lab_step_4": "4) Use the math blocks to connect theory and practice.",
        "lab_editor_title": "Python Editor",
        "lab_snippets": "Guided snippets",
        "lab_run": "Run code",
        "lab_running": "Running code...",
        "lab_placeholder": "# Write your Python here\nprint('Hello AI Lab')",
        "lab_security": "Security: only whitelisted imports (torch, tensorflow, math) and safe operations are allowed.",
        "lab_math_title": "Mini math guide",
        "lab_math_1": "Dot product: y = w1*x1 + w2*x2 + b",
        "lab_math_2": "MSE: (1/n) * sum((y_pred - y_true)^2)",
        "lab_math_3": "Softmax: p_i = exp(z_i) / sum(exp(z_j))",
    },
    "fr": {
        "title": "E-learning : IA, LLM, MCP et Tenseurs",
        "hero": "Concepts pratiques avec exemples Python executables dans cette page.",
        "run": "Executer l'exemple",
        "running": "Execution...",
        "output": "Sortie",
        "error": "Erreur",
        "no_output": "Aucune sortie.",
        "run_failed": "Echec de l'execution de l'exemple.",
        "security_note": "Les exemples sont predefinis et executes sur le serveur pour garder une execution sure et previsible.",
        "ai_title": "IA (Intelligence Artificielle)",
        "ai_desc": "L'IA permet aux machines d'effectuer des taches qui demandent habituellement une intelligence humaine, comme la classification et la prediction.",
        "llm_title": "LLM (Large Language Model)",
        "llm_desc": "Un LLM est un modele de langage entraine sur de grands volumes de texte pour generer, resumer et transformer du contenu.",
        "mcp_title": "MCP (Model Context Protocol)",
        "mcp_desc": "MCP standardise la facon dont les outils fournissent du contexte aux modeles, avec des integrations plus sures et previsibles.",
        "tensor_title": "Tenseurs",
        "tensor_desc": "Un tenseur est une structure n-dimensionnelle pour representer les donnees en IA et deep learning (vecteurs, matrices, volumes).",
        "pytorch_title": "PyTorch (reseau neuronal minimal)",
        "pytorch_desc": "Exemple simple avec couches lineaires pour voir les tenseurs d'entree et de sortie.",
        "tensorflow_title": "TensorFlow (Keras minimal)",
        "tensorflow_desc": "Exemple Sequential simple pour comprendre l'inference par lot.",
        "tiny_llm_title": "Mini LLM pedagogique",
        "tiny_llm_desc": "Modele de langage tres petit (bigrammes) pour enseigner tokens, logits et probabilites.",
        "rag_title": "RAG (Retrieval-Augmented Generation)",
        "rag_desc": "Le RAG combine recherche de contexte + generation pour des reponses plus fiables et auditables.",
        "rag_step_1": "1) Indexez une petite base de connaissance (documents).",
        "rag_step_2": "2) Recuperez le meilleur contexte pour la question.",
        "rag_step_3": "3) Construisez le prompt final avec question + contexte recupere.",
        "expected_output_label": "Sortie attendue",
        "expected_ai": "Risk labels: ['low', 'high', 'low', 'high', 'low']",
        "expected_bigram": "Bigrammes avec paires de tokens et comptes, ex: ('ai', 'helps'): 1",
        "expected_mcp": "Context keys: ['user_intent', 'tool', 'constraints']\nTool selected: sql_query",
        "expected_tensor": "Shape: (2, 3)\nColumn sums: [5, 7, 9]",
        "expected_pytorch": "Input shape: (4, 3)\nOutput shape: (4, 1)\nFirst output: valeur numerique",
        "expected_tensorflow": "Input shape: (4, 3)\nOutput shape: (4, 1)\nFirst output: valeur numerique",
        "expected_tiny_llm": "Vocab: [...]\nLast input token: ...\nTop next-token probabilities: 3 lignes token-probabilite",
        "expected_rag": "Query: ...\nTop document: ...\nPrompt preview: ...",
        "services_title": "Services IA dedies",
        "services_dedicated": "Serveurs IA dedies: GPU prive, isolation tenant, monitoring, SLA et MLOps.",
        "services_lgpd": "LGPD by design: minimisation des donnees, retention policy, piste d'audit, consentement et droit a l'effacement.",
        "services_cta": "Nous pouvons deployer votre AI server dedie avec conformite LGPD.",
        "step_by_step": "Pas a pas",
        "math_behind": "Mathematique derriere",
        "open_lab": "Ouvrir le labo Python",
        "lab_title": "Laboratoire Python guide",
        "lab_hero": "Ecrivez votre propre code Python avec un editeur assiste et executez en securite.",
        "lab_steps_title": "Mode d'emploi (etape par etape)",
        "lab_step_1": "1) Choisissez un snippet guide ou ecrivez votre code dans l'editeur.",
        "lab_step_2": "2) Cliquez sur Executer pour lancer sur le serveur dans un environnement restreint.",
        "lab_step_3": "3) Lisez la sortie puis ajustez votre code iterativement.",
        "lab_step_4": "4) Utilisez les blocs maths pour relier theorie et pratique.",
        "lab_editor_title": "Editeur Python",
        "lab_snippets": "Snippets guides",
        "lab_run": "Executer le code",
        "lab_running": "Execution du code...",
        "lab_placeholder": "# Ecrivez votre Python ici\nprint('Hello AI Lab')",
        "lab_security": "Securite: seuls les imports autorises (torch, tensorflow, math) et operations sures sont permis.",
        "lab_math_title": "Mini-guide mathematique",
        "lab_math_1": "Produit scalaire: y = w1*x1 + w2*x2 + b",
        "lab_math_2": "MSE: (1/n) * somme((y_pred - y_true)^2)",
        "lab_math_3": "Softmax: p_i = exp(z_i) / somme(exp(z_j))",
    },
    "es": {
        "title": "E-learning: IA, LLM, MCP y Tensores",
        "hero": "Conceptos practicos con ejemplos Python ejecutables en esta pagina.",
        "run": "Ejecutar ejemplo",
        "running": "Ejecutando...",
        "output": "Salida",
        "error": "Error",
        "no_output": "Sin salida.",
        "run_failed": "No se pudo ejecutar el ejemplo.",
        "security_note": "Los ejemplos son predefinidos y se ejecutan en el servidor para mantener seguridad y previsibilidad.",
        "ai_title": "IA (Inteligencia Artificial)",
        "ai_desc": "La IA permite que las maquinas realicen tareas que normalmente requieren inteligencia humana, como clasificacion y prediccion.",
        "llm_title": "LLM (Large Language Model)",
        "llm_desc": "Un LLM es un modelo de lenguaje entrenado con grandes volumenes de texto para generar, resumir y transformar contenido.",
        "mcp_title": "MCP (Model Context Protocol)",
        "mcp_desc": "MCP estandariza como las herramientas entregan contexto a los modelos, con integraciones mas seguras y predecibles.",
        "tensor_title": "Tensores",
        "tensor_desc": "Un tensor es una estructura n-dimensional para representar datos en IA y deep learning (vectores, matrices y volumenes).",
        "pytorch_title": "PyTorch (red neuronal minima)",
        "pytorch_desc": "Ejemplo simple con capas lineales para ver tensores de entrada y salida.",
        "tensorflow_title": "TensorFlow (Keras minimo)",
        "tensorflow_desc": "Ejemplo Sequential sencillo para entender inferencia por lotes.",
        "tiny_llm_title": "Mini LLM pedagogico",
        "tiny_llm_desc": "Modelo de lenguaje muy pequeno (bigramas) para ensenar tokens, logits y probabilidades.",
        "rag_title": "RAG (Retrieval-Augmented Generation)",
        "rag_desc": "RAG combina recuperacion de contexto + generacion para respuestas mas precisas y auditables.",
        "rag_step_1": "1) Indexa una pequena base de conocimiento (documentos).",
        "rag_step_2": "2) Recupera el mejor contexto para la consulta.",
        "rag_step_3": "3) Construye el prompt final con pregunta + contexto recuperado.",
        "expected_output_label": "Salida esperada",
        "expected_ai": "Risk labels: ['low', 'high', 'low', 'high', 'low']",
        "expected_bigram": "Bigramas con pares de tokens y conteos, ej: ('ai', 'helps'): 1",
        "expected_mcp": "Context keys: ['user_intent', 'tool', 'constraints']\nTool selected: sql_query",
        "expected_tensor": "Shape: (2, 3)\nColumn sums: [5, 7, 9]",
        "expected_pytorch": "Input shape: (4, 3)\nOutput shape: (4, 1)\nFirst output: valor numerico",
        "expected_tensorflow": "Input shape: (4, 3)\nOutput shape: (4, 1)\nFirst output: valor numerico",
        "expected_tiny_llm": "Vocab: [...]\nLast input token: ...\nTop next-token probabilities: 3 lineas token-probabilidad",
        "expected_rag": "Query: ...\nTop document: ...\nPrompt preview: ...",
        "services_title": "Servicios IA dedicados",
        "services_dedicated": "Servidores IA dedicados: GPU privada, aislamiento por tenant, monitoreo, SLA y MLOps.",
        "services_lgpd": "LGPD by design: minimizacion de datos, retention policy, auditoria, consentimiento y derecho al borrado.",
        "services_cta": "Podemos desplegar su AI server dedicado con cumplimiento LGPD.",
        "step_by_step": "Paso a paso",
        "math_behind": "Matematica detras",
        "open_lab": "Abrir laboratorio Python",
        "lab_title": "Laboratorio Python guiado",
        "lab_hero": "Escribe tu propio codigo Python con editor asistido y ejecutalo con seguridad.",
        "lab_steps_title": "Como usar (paso a paso)",
        "lab_step_1": "1) Elige un snippet guiado o escribe tu codigo en el editor.",
        "lab_step_2": "2) Haz clic en Ejecutar para correr en el servidor con entorno restringido.",
        "lab_step_3": "3) Lee la salida y mejora tu codigo de forma iterativa.",
        "lab_step_4": "4) Usa los bloques de matematica para conectar teoria y practica.",
        "lab_editor_title": "Editor Python",
        "lab_snippets": "Snippets guiados",
        "lab_run": "Ejecutar codigo",
        "lab_running": "Ejecutando codigo...",
        "lab_placeholder": "# Escribe tu Python aqui\nprint('Hello AI Lab')",
        "lab_security": "Seguridad: solo imports permitidos (torch, tensorflow, math) y operaciones seguras.",
        "lab_math_title": "Mini-guia matematica",
        "lab_math_1": "Producto punto: y = w1*x1 + w2*x2 + b",
        "lab_math_2": "MSE: (1/n) * suma((y_pred - y_true)^2)",
        "lab_math_3": "Softmax: p_i = exp(z_i) / suma(exp(z_j))",
    },
    "it": {
        "title": "E-learning: IA, LLM, MCP e Tensori",
        "hero": "Concetti pratici con esempi Python eseguibili in questa pagina.",
        "run": "Esegui esempio",
        "running": "Esecuzione...",
        "output": "Output",
        "error": "Errore",
        "no_output": "Nessun output.",
        "run_failed": "Esecuzione dell'esempio non riuscita.",
        "security_note": "Gli esempi sono predefiniti ed eseguiti sul server per mantenere sicurezza e prevedibilita.",
        "ai_title": "IA (Intelligenza Artificiale)",
        "ai_desc": "L'IA consente alle macchine di svolgere compiti che normalmente richiedono intelligenza umana, come classificazione e previsione.",
        "llm_title": "LLM (Large Language Model)",
        "llm_desc": "Un LLM e un modello linguistico addestrato su grandi volumi di testo per generare, riassumere e trasformare contenuti.",
        "mcp_title": "MCP (Model Context Protocol)",
        "mcp_desc": "MCP standardizza il modo in cui gli strumenti forniscono contesto ai modelli, con integrazioni piu sicure e prevedibili.",
        "tensor_title": "Tensori",
        "tensor_desc": "Un tensore e una struttura n-dimensionale usata per rappresentare dati in IA e deep learning (vettori, matrici e volumi).",
        "pytorch_title": "PyTorch (rete neurale minima)",
        "pytorch_desc": "Esempio semplice con layer lineari per vedere tensori di input e output.",
        "tensorflow_title": "TensorFlow (Keras minimo)",
        "tensorflow_desc": "Esempio Sequential semplice per capire l'inferenza su batch.",
        "tiny_llm_title": "Mini LLM didattico",
        "tiny_llm_desc": "Modello linguistico molto piccolo (bigrammi) per insegnare token, logits e probabilita.",
        "rag_title": "RAG (Retrieval-Augmented Generation)",
        "rag_desc": "RAG combina recupero di contesto + generazione per risposte piu accurate e verificabili.",
        "rag_step_1": "1) Indicizza una piccola base di conoscenza (documenti).",
        "rag_step_2": "2) Recupera il miglior contesto per la domanda.",
        "rag_step_3": "3) Costruisci il prompt finale con domanda + contesto recuperato.",
        "expected_output_label": "Output atteso",
        "expected_ai": "Risk labels: ['low', 'high', 'low', 'high', 'low']",
        "expected_bigram": "Bigrammi con coppie di token e conteggi, es: ('ai', 'helps'): 1",
        "expected_mcp": "Context keys: ['user_intent', 'tool', 'constraints']\nTool selected: sql_query",
        "expected_tensor": "Shape: (2, 3)\nColumn sums: [5, 7, 9]",
        "expected_pytorch": "Input shape: (4, 3)\nOutput shape: (4, 1)\nFirst output: valore numerico",
        "expected_tensorflow": "Input shape: (4, 3)\nOutput shape: (4, 1)\nFirst output: valore numerico",
        "expected_tiny_llm": "Vocab: [...]\nLast input token: ...\nTop next-token probabilities: 3 righe token-probabilita",
        "expected_rag": "Query: ...\nTop document: ...\nPrompt preview: ...",
        "services_title": "Servizi AI dedicati",
        "services_dedicated": "Server AI dedicati: GPU privata, isolamento tenant, monitoraggio, SLA e MLOps.",
        "services_lgpd": "LGPD by design: minimizzazione dati, retention policy, audit trail, consenso e diritto alla cancellazione.",
        "services_cta": "Possiamo distribuire il tuo AI server dedicato con conformita LGPD.",
        "step_by_step": "Passo dopo passo",
        "math_behind": "Matematica dietro",
        "open_lab": "Apri laboratorio Python",
        "lab_title": "Laboratorio Python guidato",
        "lab_hero": "Scrivi il tuo codice Python con editor assistito ed eseguilo in sicurezza.",
        "lab_steps_title": "Come usare (passo per passo)",
        "lab_step_1": "1) Scegli uno snippet guidato o scrivi il tuo codice nell'editor.",
        "lab_step_2": "2) Clicca Esegui per lanciare sul server in ambiente ristretto.",
        "lab_step_3": "3) Leggi l'output e migliora il codice in modo iterativo.",
        "lab_step_4": "4) Usa i blocchi matematici per collegare teoria e pratica.",
        "lab_editor_title": "Editor Python",
        "lab_snippets": "Snippet guidati",
        "lab_run": "Esegui codice",
        "lab_running": "Esecuzione codice...",
        "lab_placeholder": "# Scrivi il tuo Python qui\nprint('Hello AI Lab')",
        "lab_security": "Sicurezza: solo import consentiti (torch, tensorflow, math) e operazioni sicure.",
        "lab_math_title": "Mini-guida matematica",
        "lab_math_1": "Prodotto scalare: y = w1*x1 + w2*x2 + b",
        "lab_math_2": "MSE: (1/n) * somma((y_pred - y_true)^2)",
        "lab_math_3": "Softmax: p_i = exp(z_i) / somma(exp(z_j))",
    },
    "de": {
        "title": "E-learning: KI, LLM, MCP und Tensoren",
        "hero": "Praktische Konzepte mit ausfuhrbaren Python-Beispielen auf dieser Seite.",
        "run": "Beispiel ausfuhren",
        "running": "Wird ausgefuhrt...",
        "output": "Ausgabe",
        "error": "Fehler",
        "no_output": "Keine Ausgabe.",
        "run_failed": "Beispiel konnte nicht ausgefuhrt werden.",
        "security_note": "Die Beispiele sind vordefiniert und werden auf dem Server ausgefuhrt, um Sicherheit und Vorhersehbarkeit zu gewahrleisten.",
        "ai_title": "KI (Kunstliche Intelligenz)",
        "ai_desc": "KI ermoglicht Maschinen Aufgaben auszufuhren, die normalerweise menschliche Intelligenz erfordern, wie Klassifikation und Vorhersage.",
        "llm_title": "LLM (Large Language Model)",
        "llm_desc": "Ein LLM ist ein Sprachmodell, das mit grossen Textmengen trainiert wurde, um Inhalte zu erzeugen, zusammenzufassen und zu transformieren.",
        "mcp_title": "MCP (Model Context Protocol)",
        "mcp_desc": "MCP standardisiert, wie Werkzeuge Kontext an Modelle liefern, damit Integrationen sicherer und vorhersagbarer werden.",
        "tensor_title": "Tensoren",
        "tensor_desc": "Ein Tensor ist eine n-dimensionale Struktur zur Darstellung von Daten in KI und Deep Learning (Vektoren, Matrizen und Volumen).",
        "pytorch_title": "PyTorch (minimales neuronales Netz)",
        "pytorch_desc": "Einfaches Beispiel mit linearen Schichten fur Eingabe- und Ausgabetensoren.",
        "tensorflow_title": "TensorFlow (minimales Keras)",
        "tensorflow_desc": "Einfaches Sequential-Beispiel zum Verstehen von Batch-Inferenz.",
        "tiny_llm_title": "Kleines Lern-LLM",
        "tiny_llm_desc": "Sehr kleines Sprachmodell (Bigramme), um Tokens, Logits und Wahrscheinlichkeiten zu lehren.",
        "rag_title": "RAG (Retrieval-Augmented Generation)",
        "rag_desc": "RAG kombiniert Retrieval + Generation fur prazisere und auditierbare Antworten.",
        "rag_step_1": "1) Indexieren Sie eine kleine Wissensbasis (Dokumente).",
        "rag_step_2": "2) Holen Sie den besten Kontext fur die Anfrage.",
        "rag_step_3": "3) Bauen Sie den finalen Prompt mit Frage + abgerufenem Kontext.",
        "expected_output_label": "Erwartete Ausgabe",
        "expected_ai": "Risk labels: ['low', 'high', 'low', 'high', 'low']",
        "expected_bigram": "Bigramme mit Token-Paaren und Anzahlen, z.B. ('ai', 'helps'): 1",
        "expected_mcp": "Context keys: ['user_intent', 'tool', 'constraints']\nTool selected: sql_query",
        "expected_tensor": "Shape: (2, 3)\nColumn sums: [5, 7, 9]",
        "expected_pytorch": "Input shape: (4, 3)\nOutput shape: (4, 1)\nFirst output: numerischer Wert",
        "expected_tensorflow": "Input shape: (4, 3)\nOutput shape: (4, 1)\nFirst output: numerischer Wert",
        "expected_tiny_llm": "Vocab: [...]\nLast input token: ...\nTop next-token probabilities: 3 Token-Wahrscheinlichkeitszeilen",
        "expected_rag": "Query: ...\nTop document: ...\nPrompt preview: ...",
        "services_title": "Dedizierte KI-Services",
        "services_dedicated": "Dedizierte KI-Server: private GPU, Tenant-Isolation, Monitoring, SLA und MLOps.",
        "services_lgpd": "LGPD by design: Datenminimierung, Retention Policy, Audit-Trail, Consent und Recht auf Loschung.",
        "services_cta": "Wir konnen Ihren dedizierten AI-Server mit LGPD-Compliance bereitstellen.",
        "step_by_step": "Schritt fur Schritt",
        "math_behind": "Mathematik dahinter",
        "open_lab": "Python-Labor offnen",
        "lab_title": "Gefuhrtes Python-Labor",
        "lab_hero": "Schreiben Sie eigenen Python-Code mit assistiertem Editor und fuhren Sie ihn sicher aus.",
        "lab_steps_title": "Anleitung (Schritt fur Schritt)",
        "lab_step_1": "1) Wahlen Sie ein gefuhrtes Snippet oder schreiben Sie eigenen Code im Editor.",
        "lab_step_2": "2) Klicken Sie auf Ausfuhren, um auf dem Server in eingeschrankter Umgebung zu starten.",
        "lab_step_3": "3) Lesen Sie die Ausgabe und verbessern Sie den Code iterativ.",
        "lab_step_4": "4) Nutzen Sie die Mathe-Blocke, um Theorie und Praxis zu verbinden.",
        "lab_editor_title": "Python-Editor",
        "lab_snippets": "Gefuhrte Snippets",
        "lab_run": "Code ausfuhren",
        "lab_running": "Code wird ausgefuhrt...",
        "lab_placeholder": "# Schreiben Sie Ihr Python hier\nprint('Hello AI Lab')",
        "lab_security": "Sicherheit: nur freigegebene Imports (torch, tensorflow, math) und sichere Operationen sind erlaubt.",
        "lab_math_title": "Mini-Matheleitfaden",
        "lab_math_1": "Skalarprodukt: y = w1*x1 + w2*x2 + b",
        "lab_math_2": "MSE: (1/n) * sum((y_pred - y_true)^2)",
        "lab_math_3": "Softmax: p_i = exp(z_i) / sum(exp(z_j))",
    },
}


ELEARNING_EXAMPLES: dict[str, dict[str, str]] = {
    "ai": {
        "id": "ai",
        "code": """# Simple threshold classifier\nloans = [1200, 3400, 900, 5100, 2200]\nthreshold = 2500\nlabels = [\"high\" if x >= threshold else \"low\" for x in loans]\nprint(\"Loans:\", loans)\nprint(\"Risk labels:\", labels)\n""",
    },
    "llm": {
        "id": "llm",
        "code": """# Tiny toy language model with bigram counts\ntext = \"ai helps teams make better decisions with data\"\nwords = text.split()\nbigrams = {}\nfor i in range(len(words) - 1):\n    pair = (words[i], words[i + 1])\n    bigrams[pair] = bigrams.get(pair, 0) + 1\nprint(\"Bigrams:\")\nfor pair, count in sorted(bigrams.items()):\n    print(f\"{pair}: {count}\")\n""",
    },
    "mcp": {
        "id": "mcp",
        "code": """# MCP-like context payload (tool + request + constraints)\ncontext = {\n    \"user_intent\": \"summarize monthly sales\",\n    \"tool\": \"sql_query\",\n    \"constraints\": [\"read_only\", \"tenant_isolation\"],\n}\nprint(\"Context keys:\", list(context.keys()))\nprint(\"Tool selected:\", context[\"tool\"])\n""",
    },
    "tensor": {
        "id": "tensor",
        "code": """# Tensor basics using nested lists (2D matrix)\nmatrix = [\n    [1, 2, 3],\n    [4, 5, 6],\n]\nrows = len(matrix)\ncols = len(matrix[0])\ncol_sums = [sum(matrix[r][c] for r in range(rows)) for c in range(cols)]\nprint(\"Shape:\", (rows, cols))\nprint(\"Column sums:\", col_sums)\n""",
    },
    "pytorch": {
        "id": "pytorch",
        "code": """# Minimal PyTorch forward pass\ntry:\n    import torch\nexcept Exception as e:\n    print(\"PyTorch not available:\", e)\nelse:\n    torch.manual_seed(0)\n    x = torch.randn(4, 3)\n    model = torch.nn.Sequential(\n        torch.nn.Linear(3, 4),\n        torch.nn.ReLU(),\n        torch.nn.Linear(4, 1),\n    )\n    y = model(x)\n    print(\"Input shape:\", tuple(x.shape))\n    print(\"Output shape:\", tuple(y.shape))\n    print(\"First output:\", float(y[0, 0]))\n""",
    },
    "tensorflow": {
        "id": "tensorflow",
        "code": """# Minimal TensorFlow/Keras forward pass\ntry:\n    import tensorflow as tf\nexcept Exception as e:\n    print(\"TensorFlow not available:\", e)\nelse:\n    tf.random.set_seed(0)\n    x = tf.random.normal((4, 3))\n    model = tf.keras.Sequential([\n        tf.keras.layers.Dense(4, activation=\"relu\"),\n        tf.keras.layers.Dense(1),\n    ])\n    y = model(x)\n    print(\"Input shape:\", x.shape)\n    print(\"Output shape:\", y.shape)\n    print(\"First output:\", float(y[0, 0]))\n""",
    },
    "tiny_llm": {
        "id": "tiny_llm",
        "code": """# Tiny LLM teaching model (char-level bigram logits)\ntry:\n    import torch\nexcept Exception as e:\n    print(\"PyTorch not available:\", e)\nelse:\n    text = \"hello llm\"\n    vocab = sorted(set(text))\n    stoi = {c: i for i, c in enumerate(vocab)}\n    itos = {i: c for c, i in stoi.items()}\n\n    ids = torch.tensor([stoi[c] for c in text], dtype=torch.long)\n    model = torch.nn.Embedding(len(vocab), len(vocab))\n    logits = model(ids)\n    probs = torch.softmax(logits[-1], dim=-1)\n\n    top_p, top_i = torch.topk(probs, k=min(3, len(vocab)))\n    print(\"Vocab:\", vocab)\n    print(\"Last input token:\", repr(itos[int(ids[-1])]))\n    print(\"Top next-token probabilities:\")\n    for p, i in zip(top_p, top_i):\n        print(itos[int(i)], round(float(p), 4))\n""",
    },
    "rag": {
        "id": "rag",
        "code": """# Tiny RAG demo (keyword overlap retrieval + prompt assembly)\ndocs = [\n    \"LGPD requires lawful basis, consent management, and data subject rights.\",\n    \"Dedicated AI servers provide tenant isolation and private GPU workloads.\",\n    \"RAG improves answer grounding by injecting retrieved context into prompts.\",\n]\nquery = \"How to run AI servers with LGPD compliance?\"\n\nq_terms = set(w.strip('.,!?').lower() for w in query.split())\nscored = []\nfor d in docs:\n    d_terms = set(w.strip('.,!?').lower() for w in d.split())\n    score = len(q_terms & d_terms)\n    scored.append((score, d))\n\nscored.sort(reverse=True, key=lambda x: x[0])\ntop_doc = scored[0][1]\nprompt = f\"Question: {query}\\nContext: {top_doc}\\nAnswer:\"\n\nprint(\"Query:\", query)\nprint(\"Top document:\", top_doc)\nprint(\"Prompt preview:\", prompt[:120] + \"...\")\n""",
    },
}


AI_SERVERS_COPY: dict[str, dict[str, object]] = {
    "pt": {
        "title": "AI Servers Dedicados + LGPD",
        "subtitle": "Infraestrutura privada para IA com isolamento, seguranca e governanca de dados.",
        "overview": "Oferecemos servidores dedicados para workloads de IA (LLM, RAG, ML) com operacao gerenciada e foco em compliance.",
        "offer_title": "Oferta",
        "offer_note": "Esta oferta e ideal para projetos RAG, assistentes de negocio, motores de scoring e automacao documental.",
        "architecture_alt": "Arquitetura de servidores IA dedicados",
        "image_note": "Imagem: arquitetura logica de implantacao IA dedicada.",
        "visual_1_alt": "Visual de data center para IA dedicada",
        "visual_2_alt": "Visual de seguranca e governanca de dados",
        "badges": ["LLM", "RAG", "GPU Privada", "LGPD by design", "Isolamento tenant"],
        "highlights": [
            "GPU dedicada (single-tenant)",
            "Rede privada, VPN e controle de acesso por perfis",
            "MLOps: deploy, observabilidade e versionamento de modelos",
            "Backups, DR e monitoramento 24/7",
        ],
        "architecture_title": "Arquitetura de referencia",
        "architecture_caption": "Gateway seguro -> API de inferencia -> orchestrator -> modelos/embeddings -> vector DB -> auditoria/logs.",
        "privacy_title": "Privacidade e LGPD",
        "privacy_items": [
            "Minimizacao de dados e finalidade explicita",
            "Criptografia em repouso e em transito",
            "Retention policy e descarte seguro",
            "Pista de auditoria para acessos e prompts",
            "Suporte a consentimento e direito ao apagamento",
        ],
        "contact_cta": "Fale com a equipe para desenhar seu AI server dedicado.",
    },
    "en": {
        "title": "Dedicated AI Servers + LGPD",
        "subtitle": "Private AI infrastructure with strong isolation, security, and data governance.",
        "overview": "We provide dedicated servers for AI workloads (LLM, RAG, ML) with managed operations and compliance-first delivery.",
        "offer_title": "Offer",
        "offer_note": "This offer is designed for RAG projects, business assistants, scoring engines, and document automation.",
        "architecture_alt": "Dedicated AI servers architecture",
        "image_note": "Image: logical architecture for dedicated AI deployment.",
        "visual_1_alt": "Dedicated AI data center visual",
        "visual_2_alt": "Security and data governance visual",
        "badges": ["LLM", "RAG", "Private GPU", "LGPD by design", "Tenant isolation"],
        "highlights": [
            "Dedicated GPU capacity (single tenant)",
            "Private network, VPN, and role-based access control",
            "MLOps: model deployment, observability, and versioning",
            "Backups, disaster recovery, and 24/7 monitoring",
        ],
        "architecture_title": "Reference architecture",
        "architecture_caption": "Secure gateway -> inference API -> orchestrator -> models/embeddings -> vector DB -> audit logs.",
        "privacy_title": "Privacy and LGPD",
        "privacy_items": [
            "Data minimization and explicit processing purpose",
            "Encryption at rest and in transit",
            "Retention policy and secure deletion",
            "Audit trail for prompts and access",
            "Support for consent and right to erasure",
        ],
        "contact_cta": "Contact our team to design your dedicated AI server.",
    },
    "fr": {
        "title": "AI Servers Dedies + LGPD",
        "subtitle": "Infrastructure IA privee avec isolation, securite et gouvernance des donnees.",
        "overview": "Nous proposons des serveurs dedies pour charges IA (LLM, RAG, ML), avec exploitation geree et approche compliance-by-design.",
        "offer_title": "Offre",
        "offer_note": "Cette offre est adaptee aux projets RAG, assistants metier, moteurs de scoring et automatisation documentaire.",
        "architecture_alt": "Architecture de serveurs IA dedies",
        "image_note": "Image: architecture logique de deploiement IA dedie.",
        "visual_1_alt": "Visuel data center pour IA dediee",
        "visual_2_alt": "Visuel securite et gouvernance des donnees",
        "badges": ["LLM", "RAG", "GPU privee", "LGPD by design", "Isolation tenant"],
        "highlights": [
            "GPU dediee (single-tenant)",
            "Reseau prive, VPN et controle d'acces par roles",
            "MLOps: deploiement, observabilite et versioning des modeles",
            "Sauvegardes, reprise d'activite et monitoring 24/7",
        ],
        "architecture_title": "Architecture de reference",
        "architecture_caption": "Gateway securise -> API d'inference -> orchestrateur -> modeles/embeddings -> vector DB -> journaux d'audit.",
        "privacy_title": "Privacy et LGPD",
        "privacy_items": [
            "Minimisation des donnees et finalite explicite",
            "Chiffrement au repos et en transit",
            "Retention policy et suppression securisee",
            "Piste d'audit des prompts et acces",
            "Support du consentement et droit a l'effacement",
        ],
        "contact_cta": "Contactez notre equipe pour concevoir votre AI server dedie.",
    },
    "es": {
        "title": "AI Servers Dedicados + LGPD",
        "subtitle": "Infraestructura IA privada con aislamiento, seguridad y gobernanza de datos.",
        "overview": "Ofrecemos servidores dedicados para cargas IA (LLM, RAG, ML) con operacion gestionada y enfoque compliance-by-design.",
        "offer_title": "Oferta",
        "offer_note": "Esta oferta se adapta a proyectos RAG, asistentes de negocio, motores de scoring y automatizacion documental.",
        "architecture_alt": "Arquitectura de servidores IA dedicados",
        "image_note": "Imagen: arquitectura logica de despliegue IA dedicado.",
        "visual_1_alt": "Visual de data center para IA dedicada",
        "visual_2_alt": "Visual de seguridad y gobernanza de datos",
        "badges": ["LLM", "RAG", "GPU Privada", "LGPD by design", "Aislamiento tenant"],
        "highlights": [
            "GPU dedicada (single-tenant)",
            "Red privada, VPN y control de acceso por roles",
            "MLOps: despliegue, observabilidad y versionado de modelos",
            "Backups, recuperacion ante desastres y monitoreo 24/7",
        ],
        "architecture_title": "Arquitectura de referencia",
        "architecture_caption": "Gateway seguro -> API de inferencia -> orquestador -> modelos/embeddings -> vector DB -> logs de auditoria.",
        "privacy_title": "Privacidad y LGPD",
        "privacy_items": [
            "Minimizacion de datos y finalidad explicita",
            "Cifrado en reposo y en transito",
            "Retention policy y eliminacion segura",
            "Pista de auditoria de prompts y accesos",
            "Soporte de consentimiento y derecho al borrado",
        ],
        "contact_cta": "Contacta al equipo para disenar tu AI server dedicado.",
    },
    "it": {
        "title": "AI Servers Dedicati + LGPD",
        "subtitle": "Infrastruttura IA privata con isolamento, sicurezza e governance dei dati.",
        "overview": "Forniamo server dedicati per workload IA (LLM, RAG, ML) con gestione operativa e approccio compliance-by-design.",
        "offer_title": "Offerta",
        "offer_note": "Questa offerta e adatta a progetti RAG, assistenti di business, motori di scoring e automazione documentale.",
        "architecture_alt": "Architettura server IA dedicati",
        "image_note": "Immagine: architettura logica di deploy IA dedicato.",
        "visual_1_alt": "Visual data center per IA dedicata",
        "visual_2_alt": "Visual sicurezza e governance dei dati",
        "badges": ["LLM", "RAG", "GPU Privata", "LGPD by design", "Isolamento tenant"],
        "highlights": [
            "GPU dedicata (single-tenant)",
            "Rete privata, VPN e controllo accessi per ruoli",
            "MLOps: deploy, osservabilita e versionamento modelli",
            "Backup, disaster recovery e monitoraggio 24/7",
        ],
        "architecture_title": "Architettura di riferimento",
        "architecture_caption": "Gateway sicuro -> API inferenza -> orchestratore -> modelli/embeddings -> vector DB -> audit logs.",
        "privacy_title": "Privacy e LGPD",
        "privacy_items": [
            "Minimizzazione dati e finalita esplicita",
            "Cifratura at-rest e in-transit",
            "Retention policy e cancellazione sicura",
            "Audit trail per prompt e accessi",
            "Supporto consenso e diritto alla cancellazione",
        ],
        "contact_cta": "Contatta il team per progettare il tuo AI server dedicato.",
    },
    "de": {
        "title": "Dedizierte AI-Server + LGPD",
        "subtitle": "Private KI-Infrastruktur mit Isolation, Sicherheit und Data Governance.",
        "overview": "Wir bieten dedizierte Server fur KI-Workloads (LLM, RAG, ML) mit Managed Operations und Compliance-by-Design.",
        "offer_title": "Angebot",
        "offer_note": "Dieses Angebot passt fur RAG-Projekte, Business-Assistenten, Scoring-Engines und Dokumentautomatisierung.",
        "architecture_alt": "Architektur dedizierter KI-Server",
        "image_note": "Bild: logische Architektur fur dediziertes KI-Deployment.",
        "visual_1_alt": "Visual Rechenzentrum fur dedizierte KI",
        "visual_2_alt": "Visual Sicherheit und Data Governance",
        "badges": ["LLM", "RAG", "Private GPU", "LGPD by design", "Tenant-Isolation"],
        "highlights": [
            "Dedizierte GPU (single-tenant)",
            "Privates Netzwerk, VPN und rollenbasierter Zugriff",
            "MLOps: Deployment, Observability und Modellversionierung",
            "Backups, Disaster Recovery und 24/7 Monitoring",
        ],
        "architecture_title": "Referenzarchitektur",
        "architecture_caption": "Sicheres Gateway -> Inference API -> Orchestrator -> Modelle/Embeddings -> Vector DB -> Audit Logs.",
        "privacy_title": "Datenschutz und LGPD",
        "privacy_items": [
            "Datenminimierung und expliziter Verwendungszweck",
            "Verschlusselung at-rest und in-transit",
            "Retention policy und sichere Loschung",
            "Audit-Trail fur Prompts und Zugriffe",
            "Unterstutzung fur Consent und Recht auf Loschung",
        ],
        "contact_cta": "Kontaktieren Sie unser Team fur Ihr dediziertes AI-Server-Design.",
    },
}


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/e-learning")
def e_learning():
    lang = normalize_lang(getattr(g, "lang", session.get("lang")))
    copy = ELEARNING_COPY.get(lang, ELEARNING_COPY[DEFAULT_LANG])
    response = make_response(render_template(
        "e_learning.html",
        t=copy,
        examples=list(ELEARNING_EXAMPLES.values()),
    ))
    # Ensure latest content is served after deploy (avoid stale page from browser/proxy caches).
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@bp.route("/e-learning/lab")
def e_learning_lab():
    lang = normalize_lang(getattr(g, "lang", session.get("lang")))
    copy = ELEARNING_COPY.get(lang, ELEARNING_COPY[DEFAULT_LANG])
    response = make_response(render_template("e_learning_lab.html", t=copy))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def _run_python_code(code: str, allow_imports: bool = False) -> tuple[bool, str, str]:
    # Shared dictionary avoids Python 3 comprehension scope issues with split globals/locals.
    safe_builtins = {
        "abs": abs,
        "all": all,
        "any": any,
        "enumerate": enumerate,
        "float": float,
        "int": int,
        "len": len,
        "list": list,
        "max": max,
        "min": min,
        "print": print,
        "range": range,
        "round": round,
        "sorted": sorted,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "zip": zip,
    }
    if allow_imports:

        def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            root = str(name or "").split(".")[0]
            if root not in ALLOWED_PYTHON_MODULES:
                raise ImportError(f"Import not allowed: {name}")
            return __import__(name, globals, locals, fromlist, level)

        safe_builtins["__import__"] = _safe_import

    env = {"__builtins__": safe_builtins}
    stdout = StringIO()
    try:
        with redirect_stdout(stdout):
            exec(code, env, env)
        return True, stdout.getvalue(), ""
    except Exception:
        return False, stdout.getvalue(), traceback.format_exc(limit=2)


def _validate_custom_python(code: str) -> str | None:
    if not code.strip():
        return "Code is empty."
    if len(code) > CUSTOM_CODE_MAX_CHARS:
        return f"Code too long (max {CUSTOM_CODE_MAX_CHARS} chars)."
    blocked_tokens = ["__", "open(", "eval(", "exec(", "compile(", "while ", "subprocess", "socket", "os.", "sys."]
    lowered = code.lower()
    for token in blocked_tokens:
        if token in lowered:
            return f"Blocked token detected: {token.strip()}"
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return f"Syntax error: {exc}"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in ALLOWED_PYTHON_MODULES:
                    return f"Import not allowed: {alias.name}"
        if isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root not in ALLOWED_PYTHON_MODULES:
                return f"Import not allowed: {node.module}"
        if isinstance(node, (ast.With, ast.AsyncFunctionDef, ast.Await)):
            return "This construct is not allowed in lab mode."
    return None


@bp.route("/e-learning/run-example", methods=["POST"])
def e_learning_run_example():
    payload = request.get_json(silent=True) or {}
    example_id = str(payload.get("example_id") or "").strip().lower()
    spec = ELEARNING_EXAMPLES.get(example_id)
    if not spec:
        return jsonify({"ok": False, "error": "Invalid example."}), 400

    ok, output, error = _run_python_code(spec["code"], allow_imports=True)
    if not ok:
        return jsonify({"ok": False, "error": error, "output": output}), 400
    return jsonify({"ok": True, "output": output})


@bp.route("/e-learning/run-custom", methods=["POST"])
def e_learning_run_custom():
    payload = request.get_json(silent=True) or {}
    code = str(payload.get("code") or "")
    validation_error = _validate_custom_python(code)
    if validation_error:
        return jsonify({"ok": False, "error": validation_error}), 400

    ok, output, error = _run_python_code(code, allow_imports=True)
    if not ok:
        return jsonify({"ok": False, "error": error, "output": output}), 400
    return jsonify({"ok": True, "output": output})


@bp.route("/demo/request", methods=["POST"])
def request_demo():
    full_name = (request.form.get("full_name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    phone = (request.form.get("phone") or "").strip()
    company = (request.form.get("company") or "").strip()
    solution_interest = (request.form.get("solution_interest") or "").strip()
    message = (request.form.get("message") or "").strip()
    rdv_date_raw = (request.form.get("rdv_date") or "").strip()
    rdv_time_raw = (request.form.get("rdv_time") or "").strip()
    timezone = (request.form.get("timezone") or "Europe/Paris").strip() or "Europe/Paris"

    if not full_name or not email or not rdv_date_raw or not rdv_time_raw:
        flash(tr("Veuillez renseigner nom, email, date et horaire du RDV.", session.get("lang")), "error")
        return redirect(url_for("public.index") + "#five")

    try:
        rdv_date = datetime.strptime(rdv_date_raw, "%Y-%m-%d").date()
        rdv_time = datetime.strptime(rdv_time_raw, "%H:%M").time()
    except ValueError:
        flash(tr("Format de date/heure invalide.", session.get("lang")), "error")
        return redirect(url_for("public.index") + "#five")

    if rdv_date < date.today():
        flash(tr("La date de RDV doit être aujourd'hui ou future.", session.get("lang")), "error")
        return redirect(url_for("public.index") + "#five")

    prospect = Prospect(
        full_name=full_name,
        email=email,
        phone=phone,
        company=company,
        solution_interest=solution_interest,
        message=message,
        rdv_date=rdv_date,
        rdv_time=rdv_time,
        timezone=timezone,
        status="new",
    )
    db.session.add(prospect)
    db.session.commit()

    flash(tr("Merci. Votre demande de démonstration a bien été enregistrée.", session.get("lang")), "success")
    return redirect(url_for("public.index") + "#five")


@bp.route("/lang/<lang_code>")
def set_language(lang_code: str):
    """Set UI language and redirect back."""
    lang = normalize_lang(lang_code)
    if lang not in SUPPORTED_LANGS:
        lang = DEFAULT_LANG
    session["lang"] = lang

    nxt = request.args.get("next") or request.referrer or url_for("public.index")
    return redirect(nxt)


@bp.route("/projets/mobile")
def projects_mobile():
    return render_template("projects_mobile.html")


@bp.route("/projets/iot")
def projects_iot():
    return render_template("projects_iot.html")


@bp.route("/projets/belegal")
def belegal():
    return render_template("belegal.html")


@bp.route("/projets/gestion-projet")
def projects_management():
    return render_template("projects_management.html")


@bp.route("/bi/metabase")
def metabase():
    return render_template("metabase.html")


@bp.route("/plans")
def plans():
    plans = SubscriptionService.get_available_plans(include_internal=False)
    raw_product = (request.args.get("product") or "").strip()
    selected_product = raw_product.lower() or "finance"
    valid_products = {"finance", "bi", "credit", "project", "ifrs9", "all"}

    if raw_product and selected_product not in valid_products:
        return redirect(url_for("public.plans"), code=301)

    if raw_product and raw_product != selected_product:
        if selected_product == "finance":
            return redirect(url_for("public.plans"), code=301)
        return redirect(url_for("public.plans", product=selected_product), code=301)

    def _has_project(plan) -> bool:
        features = plan.features_json if isinstance(plan.features_json, dict) else {}
        return bool(features.get("has_project", plan.code == "free"))

    def _has_credit(plan) -> bool:
        features = plan.features_json if isinstance(plan.features_json, dict) else {}
        return bool(features.get("has_credit", plan.code == "free"))

    def _has_ifrs9(plan) -> bool:
        features = plan.features_json if isinstance(plan.features_json, dict) else {}
        return bool(features.get("has_ifrs9", plan.code == "free" or plan.code in SubscriptionService.IFRS9_INCLUDED_PLAN_CODES))

    if selected_product == "finance":
        plans = [plan for plan in plans if plan.code in FINANCE_PLAN_CODES]
    elif selected_product == "bi":
        plans = [plan for plan in plans if (plan.has_bi or plan.code == "free")]
    elif selected_product == "credit":
        plans = [plan for plan in plans if _has_credit(plan)]
    elif selected_product == "project":
        plans = [plan for plan in plans if _has_project(plan)]
    elif selected_product == "ifrs9":
        plans = [plan for plan in plans if _has_ifrs9(plan)]
    elif selected_product == "all":
        plans = plans
    else:
        selected_product = "finance"
        plans = [plan for plan in plans if plan.code in FINANCE_PLAN_CODES]

    current_plan = None
    if current_user.is_authenticated:
        tenant = Tenant.query.get(current_user.tenant_id)
        if tenant and tenant.subscription:
            current_plan = tenant.subscription.plan

    return render_template(
        "plans.html",
        plans=plans,
        current_plan=current_plan,
        selected_product=selected_product,
    )


@bp.route("/produits/finance")
def product_finance():
    return render_template("products/finance.html", product=get_product_entry("finance"))


@bp.route("/produits/bi")
def product_bi():
    return render_template("products/bi.html", product=get_product_entry("bi"))


@bp.route("/produits/credit")
def product_credit():
    return render_template("products/credit.html", product=get_product_entry("credit"))


@bp.route("/produits/projet")
def product_project():
    return render_template("products/project.html", product=get_product_entry("project"))


@bp.route("/produits/ifrs9")
def product_ifrs9():
    return render_template("products/ifrs9.html", product=get_product_entry("ifrs9"))


@bp.route("/produits/ai-servers")
def product_ai_servers():
    lang = normalize_lang(getattr(g, "lang", session.get("lang")))
    copy = AI_SERVERS_COPY.get(lang, AI_SERVERS_COPY[DEFAULT_LANG])
    return render_template("products/ai_servers.html", t=copy)


# -----------------
# Legal pages
# -----------------


@bp.route("/legal/terms")
def legal_terms():
    return render_template("legal/terms.html")


@bp.route("/legal/privacy")
def legal_privacy():
    return render_template("legal/privacy.html")


@bp.route("/legal/nutritracker/privacy")
def nutritracker_privacy_policy():
    return render_template("legal/nutritracker_privacy.html")


@bp.route("/legal/nutritracker/lgpd-request")
def nutritracker_lgpd_request():
    return render_template("legal/nutritracker_lgpd_request.html")


@bp.route("/legal/cookies")
def legal_cookies():
    return render_template("legal/cookies.html")


@bp.route("/legal/retention")
def legal_retention():
    return render_template("legal/retention.html")


@bp.route("/legal/notice")
def legal_notice():
    return render_template("legal/notice.html")


@bp.route("/left-sidebar")
def left_sidebar():
    return render_template("left-sidebar.html")


@bp.route("/right-sidebar")
def right_sidebar():
    return render_template("right-sidebar.html")


@bp.route("/no-sidebar")
def no_sidebar():
    return render_template("no-sidebar.html")


@bp.route("/elements")
def elements():
    return render_template("elements.html")


@bp.route("/sitemap.xml")
def sitemap_xml():
    site_url = (current_app.config.get("SITE_URL") or "").rstrip("/")

    def _abs(endpoint: str) -> str:
        path = url_for(endpoint, _external=False)
        if site_url:
            return urljoin(site_url + "/", path.lstrip("/"))
        return url_for(endpoint, _external=True)

    today = date.today().isoformat()
    entries = [
        (_abs("public.index"), "weekly", "1.0"),
        (_abs("public.plans"), "weekly", "0.9"),
        (_abs("public.plans") + "?product=bi", "weekly", "0.8"),
        (_abs("public.plans") + "?product=credit", "weekly", "0.8"),
        (_abs("public.plans") + "?product=project", "weekly", "0.8"),
        (_abs("public.plans") + "?product=ifrs9", "weekly", "0.8"),
        (_abs("public.plans") + "?product=all", "weekly", "0.7"),
        (_abs("public.product_finance"), "weekly", "0.9"),
        (_abs("public.product_bi"), "weekly", "0.9"),
        (_abs("public.product_credit"), "weekly", "0.9"),
        (_abs("public.product_project"), "weekly", "0.9"),
        (_abs("public.product_ifrs9"), "weekly", "0.9"),
        (_abs("public.product_ai_servers"), "weekly", "0.9"),
        (_abs("public.e_learning"), "weekly", "0.8"),
        (_abs("public.e_learning_lab"), "weekly", "0.7"),
        (_abs("public.metabase"), "monthly", "0.7"),
        (_abs("public.belegal"), "monthly", "0.7"),
        (_abs("public.projects_mobile"), "monthly", "0.6"),
        (_abs("public.projects_iot"), "monthly", "0.6"),
        (_abs("public.projects_management"), "monthly", "0.6"),
        (_abs("public.legal_terms"), "yearly", "0.3"),
        (_abs("public.legal_privacy"), "yearly", "0.3"),
        (_abs("public.legal_cookies"), "yearly", "0.3"),
        (_abs("public.legal_retention"), "yearly", "0.3"),
        (_abs("public.legal_notice"), "yearly", "0.3"),
    ]

    urls = "".join(
        f"<url><loc>{loc}</loc><lastmod>{today}</lastmod><changefreq>{changefreq}</changefreq><priority>{priority}</priority></url>"
        for loc, changefreq, priority in entries
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{urls}"
        "</urlset>"
    )
    return Response(xml, mimetype="application/xml")


@bp.route("/robots.txt")
def robots_txt():
    site_url = (current_app.config.get("SITE_URL") or "").rstrip("/")
    sitemap_url = f"{site_url}/sitemap.xml" if site_url else url_for("public.sitemap_xml", _external=True)
    lines = [
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {sitemap_url}",
    ]
    return Response("\n".join(lines) + "\n", mimetype="text/plain")
