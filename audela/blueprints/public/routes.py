import ast
import hashlib
import re
from contextlib import redirect_stdout
from datetime import date, datetime
from decimal import Decimal
from io import StringIO
import traceback
from uuid import uuid4
from urllib.parse import urljoin, urlsplit
from sqlalchemy.orm.attributes import flag_modified

from flask import Response, current_app, redirect, render_template, request, session, url_for, flash, jsonify, g, make_response
from flask_login import current_user

from ...extensions import db, csrf
from ...models import Prospect
from ...models import User
from ...models import Tenant
from ...models import PublicPageVisit
from ...models import Dashboard, DashboardCard, DataSource, QueryRun, Question, FinanceTransaction, FinanceAccount, ProjectWorkspace
from ...models import UserELearningEnrollment, ELearningModule
from ...models.e_learning import ELearningLesson, ELearningQuiz, UserQuizAttempt
from ...services.subscription_service import SubscriptionService
from ...services.email_service import EmailService
from ...services.query_service import QueryExecutionError, execute_sql
from ...services.datasource_service import introspect_source
from ...services.nlq_service import generate_sql_from_nl
from ...services.ai_service import analyze_with_ai
from ...product_catalog import get_product_catalog, get_product_entry

from ...i18n import DEFAULT_LANG, SUPPORTED_LANGS, normalize_lang, tr

from . import bp


FINANCE_PLAN_CODES = {"free", "finance_starter", "finance_pro", "finance_banking", "all_in_one_pro"}
E_LEARNING_PLAN_CODES = {"e_learning_starter"}
CUSTOM_CODE_MAX_CHARS = 4000
ALLOWED_PYTHON_MODULES = {"torch", "tensorflow", "math"}
PUBLIC_TRAFFIC_EXCLUDED_ENDPOINTS = {
    "public.e_learning_run_example",
    "public.e_learning_run_custom",
    "public.request_demo",
    "public.set_language",
}
INTERNAL_TRAFFIC_BLUEPRINTS = {
    "auth",
    "billing",
    "credit",
    "finance",
    "ifrs9",
    "ml",
    "portal",
    "project",
    "tenant",
}
INTERNAL_TRAFFIC_EXCLUDED_ENDPOINTS = {
    "auth.login",
    "auth.register",
    "tenant.login",
}
INTERNAL_TRAFFIC_EXCLUDED_PATH_PREFIXES = (
    "/api/",
    "/app/api/",
    "/project/public/",
)


def _public_visitor_id() -> str:
    visitor_id = str(session.get("public_visitor_id") or "").strip()
    if not visitor_id:
        visitor_id = uuid4().hex
        session["public_visitor_id"] = visitor_id
    return visitor_id


def _client_ip_hash() -> str | None:
    raw_ip = (request.headers.get("X-Forwarded-For") or request.remote_addr or "").split(",", 1)[0].strip()
    if not raw_ip:
        return None
    return hashlib.sha256(raw_ip.encode("utf-8")).hexdigest()[:32]


def _client_country_code() -> str | None:
    # Prefer proxy-provided country headers when available.
    candidates = (
        request.headers.get("CF-IPCountry"),
        request.headers.get("X-Country-Code"),
        request.headers.get("X-AppEngine-Country"),
    )
    for value in candidates:
        code = str(value or "").strip().upper()
        if code and code not in {"XX", "ZZ", "UNKNOWN"}:
            return code[:8]
    return None


def _request_language_code() -> str | None:
    lang = normalize_lang(getattr(g, "lang", session.get("lang")))
    if lang:
        return str(lang)[:12]
    best = normalize_lang(request.accept_languages.best or "")
    return str(best)[:12] if best else None


def _safe_redirect_target(target: str | None) -> str | None:
    value = str(target or "").strip()
    if not value:
        return None
    if value.startswith("/") and not value.startswith("//"):
        return value

    parts = urlsplit(value)
    if not parts.scheme or not parts.netloc:
        return None

    current = urlsplit(request.host_url)
    if parts.scheme.lower() == current.scheme.lower() and parts.netloc.lower() == current.netloc.lower():
        # Keep path + query + fragment while forcing local host only.
        path = parts.path or "/"
        if parts.query:
            path = f"{path}?{parts.query}"
        if parts.fragment:
            path = f"{path}#{parts.fragment}"
        return path
    return None


def _demo_request_redirect_target(default_target: str) -> str:
    return _safe_redirect_target(request.form.get("next")) or default_target


def _notify_demo_request_admin(prospect: Prospect, *, quick_mode: bool) -> None:
    body_lines = [
        "A new AUDELA demo request was received.",
        "",
        f"Email: {prospect.email}",
        f"Name: {prospect.full_name}",
        f"Company: {prospect.company or '-'}",
        f"Phone: {prospect.phone or '-'}",
        f"Solution: {prospect.solution_interest or '-'}",
        f"Quick request: {'yes' if quick_mode else 'no'}",
        f"Requested at: {prospect.created_at.isoformat() if prospect.created_at else '-'}",
        f"Meeting date: {prospect.rdv_date.isoformat() if prospect.rdv_date else '-'}",
        f"Meeting time: {prospect.rdv_time.isoformat() if prospect.rdv_time else '-'}",
        f"Timezone: {prospect.timezone or '-'}",
        f"Origin: {(request.referrer or request.url or '').strip() or '-'}",
        "",
        "Message:",
        prospect.message or "-",
    ]
    sent = EmailService.send_email(
        to="admin@audeladedonnees.fr",
        subject=f"AUDELA demo request - {prospect.email}",
        template=None,
        body_text="\n".join(body_lines),
    )
    if not sent:
        current_app.logger.warning("Failed to send demo request notification for prospect id=%s", prospect.id)


def track_public_like_page_view(path: str, endpoint: str) -> None:
    """Persist a page view for non-public blueprints (auth/tenant pages).

    Reuses the same analytics table to keep counting centralized.
    """
    normalized_path = (str(path or "").strip() or "/")[:255]
    normalized_endpoint = (str(endpoint or "").strip() or "public.synthetic")[:120]
    if normalized_path.startswith("/api/"):
        return

    referrer = (request.referrer or "").strip()[:255] or None
    user_agent = (request.user_agent.string or "").strip()[:255] or None
    visit = PublicPageVisit(
        endpoint=normalized_endpoint,
        path=normalized_path,
        visitor_id=_public_visitor_id()[:64],
        user_id=current_user.id if current_user.is_authenticated else None,
        ip_hash=_client_ip_hash(),
        country_code=_client_country_code(),
        language_code=_request_language_code(),
        referrer=referrer,
        user_agent=user_agent,
        utm_source=(request.args.get("utm_source") or "").strip()[:120] or None,
        utm_medium=(request.args.get("utm_medium") or "").strip()[:120] or None,
        utm_campaign=(request.args.get("utm_campaign") or "").strip()[:120] or None,
        is_home=(normalized_path == "/"),
    )
    try:
        db.session.add(visit)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to persist auth/tenant page view for %s", normalized_path)


def _should_track_internal_page_view(response: Response) -> bool:
    if request.method != "GET":
        return False

    endpoint = request.endpoint or ""
    if not endpoint or endpoint.endswith(".static"):
        return False
    if endpoint in INTERNAL_TRAFFIC_EXCLUDED_ENDPOINTS:
        return False
    if endpoint.split(".", 1)[0] not in INTERNAL_TRAFFIC_BLUEPRINTS:
        return False

    path = (request.path or "/").strip() or "/"
    if any(path.startswith(prefix) for prefix in INTERNAL_TRAFFIC_EXCLUDED_PATH_PREFIXES):
        return False
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return False
    if response.status_code != 200:
        return False
    return (response.mimetype or "").lower() == "text/html"


@bp.before_request
def _track_public_page_view():
    if request.method != "GET":
        return None

    endpoint = request.endpoint or ""
    if not endpoint.startswith("public.") or endpoint in PUBLIC_TRAFFIC_EXCLUDED_ENDPOINTS:
        return None

    # Track only public HTML pages and ignore static or asset-like paths.
    if endpoint.endswith(".static") or request.path.startswith("/static/"):
        return None

    path = (request.path or "/").strip() or "/"
    if path.startswith("/api/"):
        return None

    referrer = (request.referrer or "").strip()[:255] or None
    user_agent = (request.user_agent.string or "").strip()[:255] or None

    visit = PublicPageVisit(
        endpoint=endpoint[:120],
        path=path[:255],
        visitor_id=_public_visitor_id()[:64],
        user_id=current_user.id if current_user.is_authenticated else None,
        ip_hash=_client_ip_hash(),
        country_code=_client_country_code(),
        language_code=_request_language_code(),
        referrer=referrer,
        user_agent=user_agent,
        utm_source=(request.args.get("utm_source") or "").strip()[:120] or None,
        utm_medium=(request.args.get("utm_medium") or "").strip()[:120] or None,
        utm_campaign=(request.args.get("utm_campaign") or "").strip()[:120] or None,
        is_home=(path == "/"),
    )
    try:
        db.session.add(visit)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to persist public page view for %s", path)
    return None


@bp.after_app_request
def _track_internal_page_view(response: Response):
    if _should_track_internal_page_view(response):
        track_public_like_page_view(request.path, request.endpoint or "")
    return response



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

TIMELINE_COPY: dict[str, dict[str, object]] = {
    "fr": {
        "title": "Timeline AUDELA",
        "subtitle": "Un parcours oriente resultats, produit apres produit.",
        "video_title": "Video de presentation AUDELA",
        "aria": "Timeline de AUDELA",
        "items": [
            {"year": "2022", "title": "Fondation & vision", "text": "Lancement de AUDELA avec un positionnement clair: transformer les donnees en decisions operationnelles."},
            {"year": "2023", "title": "Premieres plateformes BI", "text": "Mise en production des premiers cas d'usage BI et automatisation des flux de reporting metiers."},
            {"year": "2024", "title": "Expansion ERP & LegalTech", "text": "Deploiement des modules Finance/ERP et de la solution BeLegal pour la performance des cabinets."},
            {"year": "2025", "title": "Industrialisation & IA appliquee", "text": "Structuration des workflows de production, monitoring renforce et integration d'IA explicable."},
            {"year": "2026", "title": "Scale multi-produits", "text": "Consolidation d'une suite Data, BI, ERP, Credit, IFRS9 et AI Servers dedies autour de la meme base technologique."},
        ],
    },
    "en": {
        "title": "AUDELA Timeline",
        "subtitle": "A results-oriented journey, product after product.",
        "video_title": "AUDELA presentation video",
        "aria": "AUDELA timeline",
        "items": [
            {"year": "2022", "title": "Foundation & vision", "text": "AUDELA launched with a clear mission: turn data into operational decisions."},
            {"year": "2023", "title": "First BI platforms", "text": "First BI use cases shipped to production with automated business reporting flows."},
            {"year": "2024", "title": "ERP & LegalTech expansion", "text": "Finance/ERP modules and BeLegal were expanded to improve law-firm performance."},
            {"year": "2025", "title": "Industrialization & applied AI", "text": "Production workflows were hardened with stronger monitoring and explainable AI integration."},
            {"year": "2026", "title": "Multi-product scale", "text": "A unified stack across Data, BI, ERP, Credit, IFRS9 and dedicated AI servers."},
        ],
    },
    "pt": {
        "title": "Linha do tempo AUDELA",
        "subtitle": "Uma jornada orientada a resultados, produto apos produto.",
        "video_title": "Video de apresentacao AUDELA",
        "aria": "Linha do tempo da AUDELA",
        "items": [
            {"year": "2022", "title": "Fundacao e visao", "text": "A AUDELA foi lancada com um objetivo claro: transformar dados em decisoes operacionais."},
            {"year": "2023", "title": "Primeiras plataformas BI", "text": "Primeiros casos de uso de BI em producao com automacao dos fluxos de reporting."},
            {"year": "2024", "title": "Expansao ERP e LegalTech", "text": "Evolucao dos modulos Finance/ERP e da solucao BeLegal para performance juridica."},
            {"year": "2025", "title": "Industrializacao e IA aplicada", "text": "Fluxos de producao estruturados, monitoramento reforcado e IA explicavel integrada."},
            {"year": "2026", "title": "Escala multi-produto", "text": "Consolidacao de uma suite Data, BI, ERP, Credit, IFRS9 e AI Servers dedicados."},
        ],
    },
    "es": {
        "title": "Linea de tiempo AUDELA",
        "subtitle": "Un recorrido orientado a resultados, producto tras producto.",
        "video_title": "Video de presentacion de AUDELA",
        "aria": "Linea de tiempo de AUDELA",
        "items": [
            {"year": "2022", "title": "Fundacion y vision", "text": "AUDELA se lanzo con una mision clara: convertir datos en decisiones operativas."},
            {"year": "2023", "title": "Primeras plataformas BI", "text": "Primeros casos de BI en produccion con automatizacion de reportes de negocio."},
            {"year": "2024", "title": "Expansion ERP y LegalTech", "text": "Despliegue de modulos Finance/ERP y de BeLegal para mejorar el rendimiento legal."},
            {"year": "2025", "title": "Industrializacion e IA aplicada", "text": "Flujos de produccion reforzados, mejor monitoreo e integracion de IA explicable."},
            {"year": "2026", "title": "Escala multiproducto", "text": "Consolidacion de una suite unificada de Data, BI, ERP, Credit, IFRS9 y AI Servers dedicados."},
        ],
    },
    "it": {
        "title": "Timeline AUDELA",
        "subtitle": "Un percorso orientato ai risultati, prodotto dopo prodotto.",
        "video_title": "Video di presentazione AUDELA",
        "aria": "Timeline di AUDELA",
        "items": [
            {"year": "2022", "title": "Fondazione e visione", "text": "AUDELA nasce con una missione chiara: trasformare i dati in decisioni operative."},
            {"year": "2023", "title": "Prime piattaforme BI", "text": "Primi use case BI in produzione con automazione dei flussi di reporting."},
            {"year": "2024", "title": "Espansione ERP e LegalTech", "text": "Estensione dei moduli Finance/ERP e della soluzione BeLegal per studi legali."},
            {"year": "2025", "title": "Industrializzazione e IA applicata", "text": "Workflow di produzione consolidati, monitoraggio avanzato e IA spiegabile."},
            {"year": "2026", "title": "Scala multi-prodotto", "text": "Suite integrata Data, BI, ERP, Credit, IFRS9 e AI Servers dedicati."},
        ],
    },
    "de": {
        "title": "AUDELA Zeitachse",
        "subtitle": "Ein ergebnisorientierter Weg, Produkt fur Produkt.",
        "video_title": "AUDELA Vorstellungsvideo",
        "aria": "AUDELA Zeitachse",
        "items": [
            {"year": "2022", "title": "Grundung und Vision", "text": "AUDELA startet mit einer klaren Mission: Daten in operative Entscheidungen umsetzen."},
            {"year": "2023", "title": "Erste BI-Plattformen", "text": "Erste BI-Anwendungen in Produktion mit automatisierten Reporting-Flussen."},
            {"year": "2024", "title": "ERP- und LegalTech-Ausbau", "text": "Ausbau der Finance/ERP-Module und BeLegal fur leistungsstarke Kanzleiablaufe."},
            {"year": "2025", "title": "Industrialisierung und angewandte KI", "text": "Produktions-Workflows verfestigt, Monitoring ausgebaut und erklarbare KI integriert."},
            {"year": "2026", "title": "Skalierung uber mehrere Produkte", "text": "Vereinheitlichte Suite fur Data, BI, ERP, Credit, IFRS9 und dedizierte AI-Server."},
        ],
    },
}


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/timeline")
def timeline():
    lang = normalize_lang(getattr(g, "lang", session.get("lang")))
    copy = TIMELINE_COPY.get(lang, TIMELINE_COPY.get(DEFAULT_LANG, TIMELINE_COPY["fr"]))
    return render_template("timeline.html", t=copy)


@bp.route("/e-learning")
def e_learning():
    lang = normalize_lang(getattr(g, "lang", session.get("lang")))
    copy = ELEARNING_COPY.get(lang, ELEARNING_COPY[DEFAULT_LANG])
    academy_tracks = []
    try:
        from ...models.e_learning import ELearningSubject

        academy_tracks = (
            ELearningSubject.query.filter_by(is_active=True)
            .order_by(ELearningSubject.order.asc(), ELearningSubject.id.asc())
            .limit(12)
            .all()
        )
    except Exception:
        academy_tracks = []

    response = make_response(render_template(
        "e_learning.html",
        t=copy,
        examples=list(ELEARNING_EXAMPLES.values()),
        academy_tracks=academy_tracks,
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
    if str(current_app.config.get("FLASK_ENV") or "").lower() == "production":
        return jsonify({"ok": False, "error": "Custom code execution is disabled in production."}), 403

    payload = request.get_json(silent=True) or {}
    code = str(payload.get("code") or "")
    validation_error = _validate_custom_python(code)
    if validation_error:
        return jsonify({"ok": False, "error": validation_error}), 400

    ok, output, error = _run_python_code(code, allow_imports=True)
    if not ok:
        return jsonify({"ok": False, "error": error, "output": output}), 400
    return jsonify({"ok": True, "output": output})


@bp.route("/demo/request", methods=["GET", "POST"])
def request_demo():
    if request.method == "GET":
        return redirect(url_for("public.demo_request_page"))

    session_lang = session.get("lang")

    try:
        quick_mode = (request.form.get("quick_demo") or "").strip() == "1"
        full_name = (request.form.get("full_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        phone = (request.form.get("phone") or "").strip()
        company = (request.form.get("company") or "").strip()
        solution_interest = (request.form.get("solution_interest") or "").strip()
        message = (request.form.get("message") or "").strip()
        rdv_date_raw = (request.form.get("rdv_date") or "").strip()
        rdv_time_raw = (request.form.get("rdv_time") or "").strip()
        timezone = (request.form.get("timezone") or "Europe/Paris").strip() or "Europe/Paris"

        if not email or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            flash(tr("Veuillez renseigner une adresse e-mail valide.", session_lang), "error")
            return redirect(_demo_request_redirect_target(url_for("public.demo_request_page")))

        if not quick_mode and (not full_name or not rdv_date_raw or not rdv_time_raw):
            flash(tr("Veuillez renseigner nom, email, date et horaire du RDV.", session.get("lang")), "error")
            return redirect(_demo_request_redirect_target(url_for("public.index") + "#five"))

        if quick_mode:
            now = datetime.utcnow().replace(second=0, microsecond=0)
            rdv_date = now.date()
            rdv_time = now.time()
            if not full_name:
                full_name = email.split("@", 1)[0][:120] or email
            if not solution_interest:
                solution_interest = "demo"
        else:
            try:
                rdv_date = datetime.strptime(rdv_date_raw, "%Y-%m-%d").date()
                rdv_time = datetime.strptime(rdv_time_raw, "%H:%M").time()
            except ValueError:
                flash(tr("Format de date/heure invalide.", session_lang), "error")
                return redirect(_demo_request_redirect_target(url_for("public.index") + "#five"))

        if not quick_mode and rdv_date < date.today():
            flash(tr("La date de RDV doit être aujourd'hui ou future.", session.get("lang")), "error")
            return redirect(_demo_request_redirect_target(url_for("public.index") + "#five"))

        if quick_mode and not message:
            message = "Quick demo request"

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

        _notify_demo_request_admin(prospect, quick_mode=quick_mode)

        flash(tr("Merci. Votre demande de démonstration a bien été enregistrée.", session_lang), "success")
        return redirect(_demo_request_redirect_target(url_for("public.index") + "#five"))
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Demo request failed unexpectedly")
        flash(tr("Une erreur est survenue. Merci de réessayer.", session_lang), "error")
        return redirect(_demo_request_redirect_target(url_for("public.demo_request_page")))


@bp.route("/demo")
def demo_request_page():
    return render_template(
        "demo_request.html",
        site_public_url="https://audeladedonnees.fr",
    )


@bp.route("/lang/<lang_code>")
def set_language(lang_code: str):
    """Set UI language and redirect back."""
    lang = normalize_lang(lang_code)
    if lang not in SUPPORTED_LANGS:
        lang = DEFAULT_LANG
    session["lang"] = lang

    nxt = (
        _safe_redirect_target(request.args.get("next"))
        or _safe_redirect_target(request.referrer)
        or url_for("public.index")
    )
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
    valid_products = {"finance", "bi", "ml", "credit", "project", "ifrs9", "e_learning", "all"}

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

    def _has_ml(plan) -> bool:
        features = plan.features_json if isinstance(plan.features_json, dict) else {}
        return bool(features.get("has_ml", bool(plan.has_bi) or plan.code == "free"))

    def _has_e_learning(plan) -> bool:
        features = plan.features_json if isinstance(plan.features_json, dict) else {}
        return bool(features.get("has_e_learning", True))

    if selected_product == "finance":
        plans = [plan for plan in plans if plan.code in FINANCE_PLAN_CODES]
    elif selected_product == "bi":
        plans = [plan for plan in plans if (plan.has_bi or plan.code == "free")]
    elif selected_product == "ml":
        plans = [plan for plan in plans if _has_ml(plan)]
    elif selected_product == "credit":
        plans = [plan for plan in plans if _has_credit(plan)]
    elif selected_product == "project":
        plans = [plan for plan in plans if _has_project(plan)]
    elif selected_product == "ifrs9":
        plans = [plan for plan in plans if _has_ifrs9(plan)]
    elif selected_product == "e_learning":
        plans = [plan for plan in plans if _has_e_learning(plan)]
        plans.sort(key=lambda plan: (0 if plan.code in E_LEARNING_PLAN_CODES else 1, int(plan.display_order or 0), str(plan.name or "")))
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


@bp.route("/docs/ml-sdk")
def docs_ml_sdk():
    return render_template(
        "docs/ml_sdk.html",
        site_public_url="https://audeladedonnees.fr",
    )


@bp.route("/docs/vscode-plugin")
def docs_vscode_plugin():
    return render_template(
        "docs/vscode_plugin.html",
        site_public_url="https://audeladedonnees.fr",
    )


@bp.route("/produits/finance")
def product_finance():
    return render_template("products/finance.html", product=get_product_entry("finance"))


@bp.route("/produits/bi")
def product_bi():
    return render_template("products/bi.html", product=get_product_entry("bi"))


@bp.route("/produits/ml")
def product_ml():
    return render_template("products/ml.html", product=get_product_entry("ml"))


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


@bp.route("/api/mobile/products")
def mobile_products_catalog():
    """Expose a compact product catalog payload for the lightweight mobile app."""
    catalog = get_product_catalog()
    payload = []
    for key, product in catalog.items():
        raw_features = product.get("features")
        raw_outcomes = product.get("outcomes")
        features = raw_features if isinstance(raw_features, list) else []
        outcomes = raw_outcomes if isinstance(raw_outcomes, list) else []
        payload.append(
            {
                "id": key,
                "title": str(product.get("tenant_title") or product.get("public_title") or key),
                "subtitle": str(product.get("subtitle") or ""),
                "summary": str(product.get("overview") or product.get("tenant_summary") or ""),
                "audience": str(product.get("audience") or ""),
                "featureHighlights": [str(item) for item in features[:3]],
                "outcomeHighlights": [str(item) for item in outcomes[:2]],
                "tag": str(product.get("plans_slug") or key),
            }
        )

    payload.sort(key=lambda item: item["title"].lower())
    return jsonify({"products": payload, "count": len(payload)})


def _mobile_resolve_tenant_from_query() -> Tenant | None:
    tenant_slug = str(request.args.get("tenant") or "").strip().lower()
    if not tenant_slug:
        return None
    return Tenant.query.filter_by(slug=tenant_slug).first()


def _mobile_compact_source_schema(meta: dict, max_tables: int = 16, max_columns: int = 24) -> dict:
    """Reduce datasource schema payload size while keeping useful table/column context for AI."""
    if not isinstance(meta, dict):
        return {"schemas": []}

    out_schemas: list[dict] = []
    kept_tables = 0
    for schema in (meta.get("schemas") or []):
        if kept_tables >= max_tables:
            break
        if not isinstance(schema, dict):
            continue
        out_tables: list[dict] = []
        for table in (schema.get("tables") or []):
            if kept_tables >= max_tables:
                break
            if not isinstance(table, dict):
                continue
            cols: list[dict] = []
            for col in (table.get("columns") or [])[:max_columns]:
                if not isinstance(col, dict):
                    continue
                cols.append({
                    "name": str(col.get("name") or ""),
                    "type": str(col.get("type") or ""),
                })
            out_tables.append(
                {
                    "name": str(table.get("name") or ""),
                    "columns": cols,
                }
            )
            kept_tables += 1
        if out_tables:
            out_schemas.append(
                {
                    "name": str(schema.get("name") or ""),
                    "tables": out_tables,
                }
            )
    return {"schemas": out_schemas}


def _mobile_i18n_pick(value: object, lang: str = "fr", fallback: str = "") -> str:
    if isinstance(value, dict):
        preferred = normalize_lang(lang) or "fr"
        if preferred in value and value.get(preferred):
            return str(value.get(preferred) or "").strip()
        for key in ("fr", "en", "pt", "es", "it", "de"):
            if value.get(key):
                return str(value.get(key) or "").strip()
    if value is None:
        return str(fallback or "")
    return str(value or fallback or "").strip()


def _mobile_plain_text_from_html(html: object, max_chars: int = 900) -> str:
    text = str(html or "")
    if not text:
        return ""
    text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def _mobile_resolve_tenant_user(tenant: Tenant) -> User | None:
    if current_user and getattr(current_user, "is_authenticated", False):
        if int(getattr(current_user, "tenant_id", 0) or 0) == int(tenant.id):
            try:
                return User.query.filter(User.id == int(getattr(current_user, "id", 0) or 0)).first()
            except Exception:
                return None
    return User.query.filter(User.tenant_id == int(tenant.id)).order_by(User.id.asc()).first()


def _to_float(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except Exception:
        return 0.0


@bp.route("/api/mobile/dashboard")
def mobile_dashboard_data():
    """Return lightweight real dashboard metrics for native mobile cards."""
    tenant = _mobile_resolve_tenant_from_query()
    tenant_id = int(tenant.id) if tenant else None

    dashboard_count = 0
    run_count = 0
    finance_entries_count = 0
    finance_balance = 0.0
    learning_modules_count = 0
    learning_progress_avg = 0
    kanban_counts = {"backlog": 0, "todo": 0, "doing": 0, "done": 0}

    try:
        query = Dashboard.query
        if tenant_id:
            query = query.filter(Dashboard.tenant_id == tenant_id)
        dashboard_count = int(query.count())
    except Exception:
        dashboard_count = 0

    try:
        query = QueryRun.query
        if tenant_id:
            query = query.filter(QueryRun.tenant_id == tenant_id)
        run_count = int(query.count())
    except Exception:
        run_count = 0

    try:
        tx_query = FinanceTransaction.query
        if tenant_id:
            tx_query = tx_query.filter(FinanceTransaction.tenant_id == tenant_id)
        finance_entries_count = int(tx_query.count())
        finance_balance = sum(_to_float(t.amount) for t in tx_query.order_by(FinanceTransaction.id.desc()).limit(300).all())
    except Exception:
        finance_entries_count = 0
        finance_balance = 0.0

    try:
        enroll_query = UserELearningEnrollment.query
        if tenant_id:
            enroll_query = enroll_query.join(User, UserELearningEnrollment.user_id == User.id).filter(User.tenant_id == tenant_id)
        enrollments = enroll_query.all()
        learning_modules_count = len(enrollments)
        if enrollments:
            learning_progress_avg = int(sum(int(e.progress_percentage or 0) for e in enrollments) / len(enrollments))
    except Exception:
        learning_modules_count = 0
        learning_progress_avg = 0

    try:
        if tenant_id:
            ws = ProjectWorkspace.query.filter_by(tenant_id=tenant_id).first()
            state = ws.state_json if ws and isinstance(ws.state_json, dict) else {}
            cards_raw = state.get("cards")
            cards: list[dict] = []
            if isinstance(cards_raw, list):
                cards = [c for c in cards_raw if isinstance(c, dict)]
            for card in cards:
                if not isinstance(card, dict):
                    continue
                col = str(card.get("col") or "").strip().lower()
                if col in kanban_counts:
                    kanban_counts[col] += 1
    except Exception:
        pass

    return jsonify(
        {
            "tenant": str(tenant.slug) if tenant else "",
            "dashboardCount": dashboard_count,
            "queryRunCount": run_count,
            "financeEntriesCount": finance_entries_count,
            "financeNetAmount": round(finance_balance, 2),
            "learningModulesCount": learning_modules_count,
            "learningProgressAvg": learning_progress_avg,
            "kanban": kanban_counts,
        }
    )


@bp.route("/api/mobile/bi/datasources")
def mobile_bi_datasources_data():
    tenant = _mobile_resolve_tenant_from_query()
    if not tenant:
        return jsonify({"datasources": [], "count": 0})

    rows = (
        DataSource.query.filter(DataSource.tenant_id == int(tenant.id))
        .order_by(DataSource.name.asc(), DataSource.id.asc())
        .limit(80)
        .all()
    )

    payload = []
    for row in rows:
        payload.append(
            {
                "id": int(row.id),
                "name": str(row.name or f"Source {row.id}"),
                "type": str(row.type or "db"),
                "token": f"ds:{int(row.id)}",
            }
        )

    return jsonify({"datasources": payload, "count": len(payload)})


@bp.route("/api/mobile/bi/dashboards")
def mobile_bi_dashboards_data():
    tenant = _mobile_resolve_tenant_from_query()
    if not tenant:
        return jsonify({"dashboards": [], "count": 0})

    tenant_id = int(tenant.id)
    rows = (
        Dashboard.query.filter(Dashboard.tenant_id == tenant_id)
        .order_by(Dashboard.updated_at.desc(), Dashboard.id.desc())
        .limit(40)
        .all()
    )

    payload = []
    for row in rows:
        cards_query = DashboardCard.query.filter(DashboardCard.dashboard_id == int(row.id))
        if tenant_id:
            cards_query = cards_query.filter(DashboardCard.tenant_id == tenant_id)
        cards_count = cards_query.count()

        payload.append(
            {
                "id": int(row.id),
                "name": str(row.name or f"Dashboard {row.id}"),
                "cardsCount": int(cards_count),
                "isPrimary": bool(getattr(row, "is_primary", False)),
                "updatedAt": row.updated_at.isoformat() if getattr(row, "updated_at", None) else "",
            }
        )

    return jsonify({"dashboards": payload, "count": len(payload)})


def _mobile_parse_datasource_id(token: str) -> int | None:
    raw = str(token or "").strip()
    if not raw:
        return None
    if raw.startswith("ds:"):
        raw = raw[3:]
    try:
        value = int(raw)
        return value if value > 0 else None
    except Exception:
        return None


def _mobile_query_is_readonly(sql_text: str) -> bool:
    cleaned = re.sub(r"--.*?$", "", str(sql_text or ""), flags=re.M)
    cleaned = re.sub(r"/\*.*?\*/", " ", cleaned, flags=re.S)
    cleaned = cleaned.strip().lstrip("(").strip().lower()
    if not cleaned:
        return False
    first = cleaned.split(None, 1)[0]
    return first in {"select", "with", "show", "describe", "explain"}


@bp.route("/api/mobile/bi/query", methods=["POST"])
def mobile_bi_query_execute():
    tenant = _mobile_resolve_tenant_from_query()
    if not tenant:
        return jsonify({"ok": False, "message": "Tenant is required."}), 400

    data = request.get_json(silent=True) or {}
    sql_text = str(data.get("sql") or "").strip()
    if not sql_text:
        return jsonify({"ok": False, "message": "SQL is required."}), 400

    # Block multi-statement payloads from mobile clients.
    if ";" in sql_text.strip().rstrip(";"):
        return jsonify({"ok": False, "message": "Only a single SQL statement is allowed."}), 400

    if not _mobile_query_is_readonly(sql_text):
        return jsonify({"ok": False, "message": "Only read-only SQL is allowed (SELECT/WITH/SHOW/EXPLAIN)."}), 400

    ds_id = _mobile_parse_datasource_id(str(data.get("dataSource") or data.get("datasource") or ""))
    source = None
    if ds_id:
        source = DataSource.query.filter(
            DataSource.id == int(ds_id),
            DataSource.tenant_id == int(tenant.id),
        ).first()

    if source is None:
        source = (
            DataSource.query.filter(DataSource.tenant_id == int(tenant.id))
            .order_by(DataSource.id.asc())
            .first()
        )

    if source is None:
        return jsonify({"ok": False, "message": "No BI datasource available for this tenant."}), 404

    try:
        requested_limit = int(data.get("rowLimit") or 80)
    except Exception:
        requested_limit = 80
    row_limit = max(1, min(200, requested_limit))

    try:
        result = execute_sql(source, sql_text, params={"tenant_id": int(tenant.id)}, row_limit=row_limit)
        columns = result.get("columns") if isinstance(result.get("columns"), list) else []
        rows = result.get("rows") if isinstance(result.get("rows"), list) else []
        elapsed_ms = int(result.get("elapsed_ms") or 0)
        return jsonify(
            {
                "ok": True,
                "message": f"{len(rows)} row(s) returned.",
                "columns": columns,
                "rows": rows,
                "elapsedMs": elapsed_ms,
            }
        )
    except QueryExecutionError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except Exception:
        current_app.logger.exception("mobile bi query execution failed")
        return jsonify({"ok": False, "message": "Query execution failed."}), 500


@bp.route("/api/mobile/bi/query-from-nl", methods=["POST"])
def mobile_bi_query_from_nl_execute():
    tenant = _mobile_resolve_tenant_from_query()
    if not tenant:
        return jsonify({"ok": False, "message": "Tenant is required."}), 400

    data = request.get_json(silent=True) or {}
    prompt = str(data.get("prompt") or data.get("message") or "").strip()
    if not prompt:
        return jsonify({"ok": False, "message": "Natural language prompt is required."}), 400

    ds_id = _mobile_parse_datasource_id(str(data.get("dataSource") or data.get("datasource") or ""))
    source = None
    if ds_id:
        source = DataSource.query.filter(
            DataSource.id == int(ds_id),
            DataSource.tenant_id == int(tenant.id),
        ).first()

    if source is None:
        source = (
            DataSource.query.filter(DataSource.tenant_id == int(tenant.id))
            .order_by(DataSource.id.asc())
            .first()
        )

    if source is None:
        return jsonify({"ok": False, "message": "No BI datasource available for this tenant."}), 404

    lang = normalize_lang(str(data.get("lang") or "").strip()) or "fr"
    try:
        requested_limit = int(data.get("rowLimit") or 80)
    except Exception:
        requested_limit = 80
    row_limit = max(1, min(200, requested_limit))

    try:
        sql_text, nlq_warnings = generate_sql_from_nl(
            source,
            prompt,
            lang=lang,
            timeout_seconds=10,
            allow_scope_retry=False,
        )
        sql_text = str(sql_text or "").strip()
        if not sql_text:
            return jsonify({"ok": False, "message": "Unable to generate SQL from your prompt."}), 400

        if ";" in sql_text.strip().rstrip(";"):
            return jsonify({"ok": False, "message": "Generated SQL has multiple statements and was rejected."}), 400

        if not _mobile_query_is_readonly(sql_text):
            return jsonify({"ok": False, "message": "Generated SQL is not read-only."}), 400

        result = execute_sql(source, sql_text, params={"tenant_id": int(tenant.id)}, row_limit=row_limit)
        columns = result.get("columns") if isinstance(result.get("columns"), list) else []
        rows = result.get("rows") if isinstance(result.get("rows"), list) else []
        elapsed_ms = int(result.get("elapsed_ms") or 0)

        response = {
            "ok": True,
            "message": f"{len(rows)} row(s) returned.",
            "sql": sql_text,
            "columns": columns,
            "rows": rows,
            "elapsedMs": elapsed_ms,
        }
        if nlq_warnings:
            response["warnings"] = [str(w) for w in nlq_warnings if str(w).strip()]
        return jsonify(response)
    except QueryExecutionError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except Exception:
        current_app.logger.exception("mobile bi nl query execution failed")
        return jsonify({"ok": False, "message": "Natural language query execution failed."}), 500


def _mobile_is_number(value: object) -> bool:
    if value is None or isinstance(value, bool):
        return False
    try:
        float(str(value))
        return True
    except Exception:
        return False


def _mobile_dashboard_card_points(columns: list, rows: list, metric_index: int | None) -> list[dict]:
    if metric_index is None:
        return []

    label_index = 0 if columns else None
    points = []
    for row in rows[:12]:
        if not isinstance(row, (list, tuple)) or metric_index >= len(row):
            continue
        raw_value = row[metric_index]
        if not _mobile_is_number(raw_value):
            continue
        x_value = ""
        if label_index is not None and label_index < len(row):
            x_value = str(row[label_index] or "")
        points.append({"x": x_value or str(len(points) + 1), "y": float(str(raw_value))})

    if not points:
        return []

    max_y = max(abs(float(str(p.get("y") or 0.0))) for p in points) or 1.0
    for point in points:
        ratio = abs(float(str(point.get("y") or 0.0))) / max_y
        point["ratio"] = max(0.08, min(1.0, ratio))
    return points


def _mobile_fallback_points_for_chart(rows: list, metric_index: int | None) -> list[dict]:
    if metric_index is None or not rows:
        return []

    first = rows[0]
    if not isinstance(first, (list, tuple)) or metric_index >= len(first):
        return []

    raw_value = first[metric_index]
    if not _mobile_is_number(raw_value):
        return []

    return [{"x": "value", "y": float(str(raw_value)), "ratio": 1.0}]


def _mobile_viz_type_normalized(raw_type: str) -> str:
    value = str(raw_type or "").strip().lower()
    if "pie" in value or "donut" in value or "ring" in value:
        return "pie"
    if "bar" in value or "hist" in value:
        return "bar"
    if "line" in value or "area" in value or "trend" in value or "time" in value or "series" in value or "scatter" in value or "spark" in value:
        return "line"
    if "kpi" in value or "metric" in value or "gauge" in value or "number" in value or "single" in value or "scorecard" in value:
        return "kpi"
    if "table" in value or "pivot" in value:
        return "table"
    return "table"


def _mobile_extract_viz_type(cfg: dict, q_cfg: dict) -> str:
    def try_accept_type(raw: str) -> str:
        value = str(raw or "").strip()
        if not value:
            return ""

        normalized = _mobile_viz_type_normalized(value)
        low = value.lower()
        if normalized != "table":
            return value

        # Keep explicit table declarations but ignore generic words that normalize to table.
        if "table" in low or "pivot" in low:
            return value
        return ""

    def pick_type(source: dict) -> str:
        if not isinstance(source, dict):
            return ""

        seen: set[int] = set()

        def walk(node) -> str:
            node_id = id(node)
            if node_id in seen:
                return ""
            seen.add(node_id)

            if isinstance(node, dict):
                direct_keys = (
                    "type",
                    "vizType",
                    "viz_type",
                    "chartType",
                    "chart_type",
                    "visualization",
                    "renderType",
                    "kind",
                )
                for key in direct_keys:
                    raw = node.get(key)
                    if isinstance(raw, str):
                        accepted = try_accept_type(raw)
                        if accepted:
                            return accepted

                # ECharts-like schema frequently stores chart type under series[].type.
                series_node = node.get("series")
                if isinstance(series_node, list):
                    for series_item in series_node:
                        if isinstance(series_item, dict):
                            raw = series_item.get("type")
                            if isinstance(raw, str):
                                accepted = try_accept_type(raw)
                                if accepted:
                                    return accepted
                elif isinstance(series_node, dict):
                    raw = series_node.get("type")
                    if isinstance(raw, str):
                        accepted = try_accept_type(raw)
                        if accepted:
                            return accepted

                # Walk all nested values to catch deeper config trees.
                for value in node.values():
                    nested_type = walk(value)
                    if nested_type:
                        return nested_type
                return ""

            if isinstance(node, list):
                for item in node:
                    nested_type = walk(item)
                    if nested_type:
                        return nested_type

            return ""

        return walk(source)

    return pick_type(cfg) or pick_type(q_cfg) or "table"


def _mobile_infer_viz_type(columns: list, rows: list) -> str:
    if not columns or not rows:
        return "table"

    sample_rows = [r for r in rows[:200] if isinstance(r, (list, tuple))]
    if not sample_rows:
        return "table"

    numeric_idx: list[int] = []
    text_idx: list[int] = []
    time_idx: list[int] = []

    for idx, col_name in enumerate(columns):
        values = [r[idx] for r in sample_rows if idx < len(r)]
        non_null = [v for v in values if v not in (None, "")]
        if not non_null:
            continue

        numeric_hits = sum(1 for v in non_null if _mobile_is_number(v))
        ratio = numeric_hits / max(1, len(non_null))

        low_name = str(col_name or "").strip().lower()
        looks_time = any(tok in low_name for tok in ("date", "time", "month", "year", "period", "week", "day", "annee", "mois"))
        if looks_time:
            time_idx.append(idx)

        if ratio >= 0.8:
            numeric_idx.append(idx)
        else:
            text_idx.append(idx)

    dim_idx = time_idx[0] if time_idx else (text_idx[0] if text_idx else -1)
    metric_idx = next((i for i in numeric_idx if i != dim_idx), (numeric_idx[0] if numeric_idx else -1))

    if metric_idx >= 0 and dim_idx >= 0 and metric_idx != dim_idx:
        return "line" if dim_idx in time_idx else "bar"

    if metric_idx >= 0 and len(sample_rows) <= 2:
        return "kpi"

    return "table"


def _mobile_table_preview(columns: list, rows: list) -> list[str]:
    if not columns or not rows:
        return []

    preview = []
    max_cols = min(3, len(columns))
    for row in rows[:3]:
        if not isinstance(row, (list, tuple)):
            continue
        cells = []
        for idx in range(max_cols):
            col_name = str(columns[idx] or "c")
            col_value = row[idx] if idx < len(row) else ""
            cells.append(f"{col_name}: {col_value}")
        preview.append(" | ".join(cells))
    return preview


def _mobile_render_dashboard_card(tenant: Tenant, card: DashboardCard) -> dict:
    question = Question.query.filter(
        Question.id == int(card.question_id),
        Question.tenant_id == int(tenant.id),
    ).first()
    if question is None:
        return {
            "id": int(card.id),
            "title": f"Card {card.id}",
            "vizType": "unknown",
            "vizTypeNormalized": "table",
            "sourceName": "",
            "primaryValue": "n/a",
            "secondaryValue": "Question not found",
            "points": [],
            "previewRows": [],
        }

    source = DataSource.query.filter(
        DataSource.id == int(question.source_id),
        DataSource.tenant_id == int(tenant.id),
    ).first()
    if source is None:
        return {
            "id": int(card.id),
            "title": str(question.name or f"Question {question.id}"),
            "vizType": "unknown",
            "vizTypeNormalized": "table",
            "sourceName": "",
            "primaryValue": "n/a",
            "secondaryValue": "Datasource not found",
            "points": [],
            "previewRows": [],
        }

    cfg = card.viz_config_json if isinstance(card.viz_config_json, dict) else {}
    q_cfg = question.viz_config_json if isinstance(question.viz_config_json, dict) else {}
    viz_type = _mobile_extract_viz_type(cfg, q_cfg)
    viz_type_normalized = _mobile_viz_type_normalized(viz_type)

    try:
        result = execute_sql(source, question.sql_text, params={"tenant_id": int(tenant.id)}, row_limit=24)
        raw_columns = result.get("columns")
        raw_rows = result.get("rows")
        columns = raw_columns if isinstance(raw_columns, list) else []
        rows = raw_rows if isinstance(raw_rows, list) else []

        metric_index = None
        metric_tokens = (
            "amount",
            "total",
            "sum",
            "count",
            "value",
            "kpi",
            "score",
            "sales",
            "revenue",
            "gross",
            "net",
            "profit",
            "margin",
            "qty",
            "quantity",
            "price",
            "cost",
            "volume",
        )
        for idx, col in enumerate(columns):
            col_name = str(col or "").strip().lower()
            if any(token in col_name for token in metric_tokens):
                metric_index = idx
                break
        if metric_index is None and rows:
            for sample in rows[:8]:
                if not isinstance(sample, (list, tuple)):
                    continue
                for idx, value in enumerate(sample):
                    if _mobile_is_number(value):
                        metric_index = idx
                        break
                if metric_index is not None:
                    break

        primary_value = "n/a"
        if metric_index is not None and rows and isinstance(rows[0], (list, tuple)) and metric_index < len(rows[0]):
            first_val = rows[0][metric_index]
            if _mobile_is_number(first_val):
                primary_value = f"{float(first_val):,.2f}"
            else:
                primary_value = str(first_val or "n/a")

        points = _mobile_dashboard_card_points(columns, rows, metric_index)
        preview_rows = _mobile_table_preview(columns, rows)

        # Fallback to data-driven inference when viz config is absent or generic.
        if viz_type_normalized == "table":
            viz_type_normalized = _mobile_infer_viz_type(columns, rows)

        # If card is chart-like but points extraction failed, provide a single renderable point.
        if viz_type_normalized in ("bar", "line", "pie") and not points:
            points = _mobile_fallback_points_for_chart(rows, metric_index)

        secondary = f"{len(rows)} rows - {len(columns)} cols"
        return {
            "id": int(card.id),
            "title": str(question.name or f"Question {question.id}"),
            "vizType": viz_type,
            "vizTypeNormalized": viz_type_normalized,
            "sourceName": str(source.name or ""),
            "primaryValue": primary_value,
            "secondaryValue": secondary,
            "points": points,
            "previewRows": preview_rows,
        }
    except QueryExecutionError as exc:
        return {
            "id": int(card.id),
            "title": str(question.name or f"Question {question.id}"),
            "vizType": viz_type,
            "vizTypeNormalized": viz_type_normalized,
            "sourceName": str(source.name or ""),
            "primaryValue": "n/a",
            "secondaryValue": str(exc),
            "points": [],
            "previewRows": [],
        }
    except Exception:
        return {
            "id": int(card.id),
            "title": str(question.name or f"Question {question.id}"),
            "vizType": viz_type,
            "vizTypeNormalized": viz_type_normalized,
            "sourceName": str(source.name or ""),
            "primaryValue": "n/a",
            "secondaryValue": "Card preview unavailable",
            "points": [],
            "previewRows": [],
        }


@bp.route("/api/mobile/bi/dashboards/<int:dashboard_id>")
def mobile_bi_dashboard_detail_data(dashboard_id: int):
    tenant = _mobile_resolve_tenant_from_query()
    if not tenant:
        return jsonify({"ok": False, "message": "Tenant is required."}), 400

    dashboard = Dashboard.query.filter(
        Dashboard.id == int(dashboard_id),
        Dashboard.tenant_id == int(tenant.id),
    ).first()
    if dashboard is None:
        return jsonify({"ok": False, "message": "Dashboard not found."}), 404

    cards = (
        DashboardCard.query.filter(
            DashboardCard.dashboard_id == int(dashboard.id),
            DashboardCard.tenant_id == int(tenant.id),
        )
        .order_by(DashboardCard.id.asc())
        .limit(40)
        .all()
    )

    payload_cards = [_mobile_render_dashboard_card(tenant, card) for card in cards]
    return jsonify(
        {
            "ok": True,
            "dashboard": {
                "id": int(dashboard.id),
                "name": str(dashboard.name or f"Dashboard {dashboard.id}"),
                "isPrimary": bool(getattr(dashboard, "is_primary", False)),
                "updatedAt": dashboard.updated_at.isoformat() if getattr(dashboard, "updated_at", None) else "",
                "cardsCount": len(payload_cards),
                "cards": payload_cards,
            },
        }
    )


@bp.route("/api/mobile/kanban")
def mobile_kanban_data():
    tenant = _mobile_resolve_tenant_from_query()
    if not tenant:
        return jsonify({"columns": [], "count": 0})

    ws = ProjectWorkspace.query.filter_by(tenant_id=tenant.id).first()
    state = ws.state_json if ws and isinstance(ws.state_json, dict) else {}
    cards_raw = state.get("cards")
    cards: list[dict] = [c for c in cards_raw if isinstance(c, dict)] if isinstance(cards_raw, list) else []

    buckets: dict[str, list[dict]] = {"backlog": [], "todo": [], "doing": [], "done": []}
    for card in cards:
        col = str(card.get("col") or "todo").strip().lower()
        if col not in buckets:
            col = "todo"
        buckets[col].append(
            {
                "id": str(card.get("id") or ""),
                "title": str(card.get("title") or ""),
                "owner": str(card.get("owner") or ""),
                "priority": str(card.get("priority") or "medium"),
                "dueDate": str(card.get("due_date") or ""),
                "description": str(card.get("description") or ""),
                "column": col,
            }
        )

    columns = []
    order = ["backlog", "todo", "doing", "done"]
    for key in order:
        columns.append({"key": key, "items": buckets[key][:20], "count": len(buckets[key])})
    return jsonify({"columns": columns, "count": len(cards)})


@bp.route("/api/mobile/learning")
def mobile_learning_data():
    tenant = _mobile_resolve_tenant_from_query()
    tenant_id = int(tenant.id) if tenant else None

    query = UserELearningEnrollment.query.join(ELearningModule, UserELearningEnrollment.module_id == ELearningModule.id)
    if tenant_id:
        query = query.join(User, UserELearningEnrollment.user_id == User.id).filter(User.tenant_id == tenant_id)

    rows = query.order_by(UserELearningEnrollment.updated_at.desc()).limit(30).all()
    payload = []
    for row in rows:
        module = row.module
        module_title_i18n = getattr(module, "title_i18n", {}) or {}
        if not isinstance(module_title_i18n, dict):
            module_title_i18n = {}

        module_title = str(module_title_i18n.get("fr") or module_title_i18n.get("en") or getattr(module, "code", "") or "Module")
        payload.append(
            {
                "moduleCode": str(getattr(module, "code", "") or ""),
                "moduleTitle": module_title,
                "status": str(row.status or "enrolled"),
                "progress": int(row.progress_percentage or 0),
                "score": int(row.overall_score or 0),
            }
        )

    return jsonify({"enrollments": payload, "count": len(payload)})


@bp.route("/api/mobile/learning/content")
def mobile_learning_content_data():
    rows = (
        ELearningLesson.query.join(ELearningModule, ELearningLesson.module_id == ELearningModule.id)
        .filter(ELearningLesson.is_active == True, ELearningModule.is_active == True)
        .order_by(ELearningModule.order.asc(), ELearningLesson.order.asc())
        .limit(40)
        .all()
    )

    payload = []
    for lesson in rows:
        lesson_title_i18n = getattr(lesson, "title_i18n", {}) or {}
        if not isinstance(lesson_title_i18n, dict):
            lesson_title_i18n = {}

        module = getattr(lesson, "module", None)
        module_title_i18n = getattr(module, "title_i18n", {}) or {}
        if not isinstance(module_title_i18n, dict):
            module_title_i18n = {}

        lesson_desc_i18n = getattr(lesson, "description_i18n", {}) or {}
        if not isinstance(lesson_desc_i18n, dict):
            lesson_desc_i18n = {}

        lesson_title = str(lesson_title_i18n.get("fr") or lesson_title_i18n.get("en") or getattr(lesson, "code", "") or "Lecon")
        module_title = str(module_title_i18n.get("fr") or module_title_i18n.get("en") or getattr(module, "code", "") or "Module")
        summary = str(lesson_desc_i18n.get("fr") or lesson_desc_i18n.get("en") or "")
        payload.append(
            {
                "id": int(lesson.id),
                "moduleId": int(getattr(lesson, "module_id", 0) or 0),
                "moduleCode": str(getattr(module, "code", "") or ""),
                "moduleTitle": module_title,
                "lessonTitle": lesson_title,
                "summary": summary[:220],
            }
        )

    return jsonify({"lessons": payload, "count": len(payload)})


@bp.route("/api/mobile/learning/quizzes")
def mobile_learning_quizzes_data():
    rows = (
        ELearningQuiz.query.join(ELearningLesson, ELearningQuiz.lesson_id == ELearningLesson.id)
        .join(ELearningModule, ELearningLesson.module_id == ELearningModule.id)
        .filter(ELearningQuiz.is_active == True, ELearningLesson.is_active == True, ELearningModule.is_active == True)
        .order_by(ELearningModule.order.asc(), ELearningLesson.order.asc(), ELearningQuiz.order.asc(), ELearningQuiz.id.desc())
        .limit(30)
        .all()
    )

    payload = []
    for quiz in rows:
        lesson = getattr(quiz, "lesson", None)
        module = getattr(lesson, "module", None)
        module_id = int(getattr(lesson, "module_id", 0) or 0)
        module_code = str(getattr(module, "code", "") or "")
        module_title_i18n = getattr(module, "title_i18n", {}) or {}
        if not isinstance(module_title_i18n, dict):
            module_title_i18n = {}

        module_title = str(module_title_i18n.get("fr") or module_title_i18n.get("en") or module_code or "Module")
        title = str((quiz.title_i18n or {}).get("fr") or (quiz.title_i18n or {}).get("en") or quiz.code or "Quiz")
        question_count = len([q for q in (quiz.questions or []) if getattr(q, "is_active", True)])
        payload.append(
            {
                "id": int(quiz.id),
                "moduleId": module_id,
                "moduleCode": module_code,
                "moduleTitle": module_title,
                "title": title,
                "questionCount": int(question_count),
                "passingScorePct": int(getattr(quiz, "pass_threshold", 70) or 70),
            }
        )

    return jsonify({"quizzes": payload, "count": len(payload)})


@bp.route("/api/mobile/learning/subscription/intent", methods=["POST"])
@csrf.exempt
def mobile_learning_subscription_intent():
    tenant = _mobile_resolve_tenant_from_query()
    if not tenant:
        return jsonify({"ok": False, "message": "Tenant is required."}), 400

    data = request.get_json(silent=True) or {}
    plan_code = str(data.get("planCode") or "").strip().lower()
    allowed = {"e_learning_starter", "e_learning_pro", "all_in_one_pro"}
    if plan_code not in allowed:
        return jsonify({"ok": False, "message": "Invalid plan code."}), 400

    tenant_name = str(getattr(tenant, "name", "") or tenant.slug or "tenant")
    current_app.logger.info(
        "Mobile learning subscription intent tenant=%s plan=%s",
        str(getattr(tenant, "slug", "") or "unknown"),
        plan_code,
    )

    return jsonify(
        {
            "ok": True,
            "message": f"Subscription request received for {tenant_name}: {plan_code}.",
            "planCode": plan_code,
        }
    )


@bp.route("/api/mobile/learning/modules/subscribe", methods=["POST"])
@csrf.exempt
def mobile_learning_module_subscribe():
    tenant = _mobile_resolve_tenant_from_query()
    if not tenant:
        return jsonify({"ok": False, "message": "Tenant is required."}), 400

    data = request.get_json(silent=True) or {}
    module_id = int(data.get("moduleId") or 0)
    module_code = str(data.get("moduleCode") or "").strip()
    module_title = str(data.get("moduleTitle") or "").strip()

    resolved_module = None
    if module_id > 0:
        resolved_module = ELearningModule.query.filter(ELearningModule.id == module_id, ELearningModule.is_active == True).first()
    if resolved_module is None and module_code:
        resolved_module = ELearningModule.query.filter(ELearningModule.code == module_code, ELearningModule.is_active == True).first()

    if resolved_module is not None:
        module_code = str(resolved_module.code or module_code)
        module_title = str((resolved_module.title_i18n or {}).get("fr") or (resolved_module.title_i18n or {}).get("en") or resolved_module.code or module_title)

    if resolved_module is None:
        return jsonify({"ok": False, "message": "Module not found."}), 404

    if not module_code and not module_title:
        return jsonify({"ok": False, "message": "Module info is required."}), 400

    target_user = None
    if current_user and getattr(current_user, "is_authenticated", False):
        if int(getattr(current_user, "tenant_id", 0) or 0) == int(tenant.id):
            target_user = current_user

    if target_user is None:
        target_user = User.query.filter(User.tenant_id == int(tenant.id)).order_by(User.id.asc()).first()

    enrollment_message = ""
    if target_user is not None:
        enrollment = UserELearningEnrollment.query.filter(
            UserELearningEnrollment.user_id == int(target_user.id),
            UserELearningEnrollment.module_id == int(resolved_module.id),
        ).first()

        now = datetime.utcnow()
        if enrollment is None:
            enrollment = UserELearningEnrollment(
                user_id=int(target_user.id),
                module_id=int(resolved_module.id),
                status="in_progress",
                progress_percentage=0,
                overall_score=0,
                enrolled_at=now,
                started_at=now,
            )
            db.session.add(enrollment)
            enrollment_message = "Enrollment created."
        else:
            if not str(enrollment.status or "").strip():
                enrollment.status = "in_progress"
            if enrollment.started_at is None:
                enrollment.started_at = now
            enrollment_message = "Already enrolled."

        db.session.commit()
    else:
        enrollment_message = "No tenant user found for enrollment."

    current_app.logger.info(
        "Mobile learning module subscription tenant=%s module_code=%s module_title=%s",
        str(getattr(tenant, "slug", "") or "unknown"),
        module_code or "-",
        module_title or "-",
    )

    return jsonify(
        {
            "ok": True,
            "message": f"Module subscription active: {module_title or module_code}. {enrollment_message}",
            "moduleCode": module_code,
            "moduleTitle": module_title,
            "moduleId": int(resolved_module.id),
        }
    )


@bp.route("/api/mobile/ai/chat", methods=["POST"])
@csrf.exempt
def mobile_ai_chat():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message") or "").strip()
    if not message:
        return jsonify({"ok": False, "message": "Message requis."}), 400

    data_source = str(data.get("dataSource") or "").strip()
    lang = normalize_lang(str(data.get("lang") or "").strip()) or "fr"

    tenant = _mobile_resolve_tenant_from_query()
    tenant_label = str(tenant.slug) if tenant else "global"
    metrics = mobile_dashboard_data().get_json(silent=True) or {}

    selected_ds = None
    if tenant and data_source.startswith("ds:"):
        raw_id = data_source.split(":", 1)[1].strip()
        if raw_id.isdigit():
            selected_ds = DataSource.query.filter(
                DataSource.tenant_id == int(tenant.id),
                DataSource.id == int(raw_id),
            ).first()

    ds_label = str(getattr(selected_ds, "name", "") or "BI datasource")

    # Let runtime config resolve provider/model from tenant AI settings when available.
    if tenant is not None:
        g.tenant = tenant

    history = data.get("history") if isinstance(data.get("history"), list) else []

    sql_text = ""
    nlq_warnings: list[str] = []
    source_schema: dict = {"schemas": []}
    result_columns: list[str] = ["metric", "value"]
    result_rows_sample: list[list] = [
        ["dashboards", int(metrics.get("dashboardCount", 0) or 0)],
        ["query_runs", int(metrics.get("queryRunCount", 0) or 0)],
        ["finance_entries", int(metrics.get("financeEntriesCount", 0) or 0)],
        ["learning_modules", int(metrics.get("learningModulesCount", 0) or 0)],
    ]
    result_row_count = len(result_rows_sample)

    # If a datasource is selected, provide real schema + query sample for stronger AI answers.
    if tenant and selected_ds is not None:
        try:
            full_meta = introspect_source(selected_ds)
            source_schema = _mobile_compact_source_schema(full_meta)
        except Exception:
            source_schema = {"schemas": []}

        try:
            sql_text, nlq_warnings = generate_sql_from_nl(
                selected_ds,
                message,
                lang=lang,
                timeout_seconds=10,
                allow_scope_retry=False,
            )
            sql_head = str(sql_text or "").lower().lstrip()
            if sql_text and (sql_head.startswith("select") or sql_head.startswith("with")):
                res = execute_sql(selected_ds, sql_text, params={"tenant_id": int(tenant.id)}, row_limit=240)
                cols = [str(c) for c in (res.get("columns") or [])]
                rows = res.get("rows") or []
                if cols and rows:
                    result_columns = cols
                    result_rows_sample = rows[:200]
                    result_row_count = len(rows)
        except QueryExecutionError as qe:
            nlq_warnings = list(nlq_warnings or [])
            nlq_warnings.append(str(qe))
        except Exception:
            pass

    context_bundle = {
        "lang": lang,
        "question": {"id": None, "name": message},
        "source": {
            "id": int(getattr(selected_ds, "id", 0) or 0),
            "name": ds_label,
            "type": str(getattr(selected_ds, "type", "") or ""),
        },
        "source_schema": source_schema,
        "sql": sql_text,
        "nlq_warnings": nlq_warnings,
        "result": {
            "columns": result_columns,
            "rows_sample": result_rows_sample,
            "row_count": result_row_count,
        },
        "profile": {
            "tenant": tenant_label,
            "metrics": metrics,
            "selected_datasource": ds_label,
        },
    }

    ai_result = analyze_with_ai(context_bundle, message, history=history, lang=lang)
    if isinstance(ai_result, dict) and ai_result.get("error"):
        fallback = (
            f"Assistant BI indisponible pour le moment ({str(ai_result.get('error') or 'runtime')}). "
            f"Tenant={tenant_label}, source={ds_label}, dashboards={int(metrics.get('dashboardCount', 0) or 0)}, "
            f"queryRuns={int(metrics.get('queryRunCount', 0) or 0)}."
        )
        return jsonify({"ok": True, "message": fallback})

    analysis = str((ai_result or {}).get("analysis") or "").strip()
    followups = (ai_result or {}).get("followups") if isinstance((ai_result or {}).get("followups"), list) else []
    if followups:
        analysis = f"{analysis}\n\nSuggestions: " + " | ".join(str(item) for item in followups[:3] if str(item).strip())

    if not analysis:
        analysis = "AI assistant response unavailable."

    ai_model_name = str((ai_result or {}).get("model") or "gpt-4o-mini")
    ai_provider_name = str((ai_result or {}).get("provider") or "openai")

    return jsonify({"ok": True, "message": analysis, "model": ai_model_name, "provider": ai_provider_name})


@bp.route("/api/mobile/profile/ai-info")
def mobile_profile_ai_info():
    """Return the AI model configured for this tenant profile."""
    from ...services.ai_runtime_config import resolve_ai_runtime_config as _rac
    tenant = _mobile_resolve_tenant_from_query()
    if tenant is not None:
        from flask import g as _g
        _g.tenant = tenant
    runtime = _rac(default_model="gpt-4o-mini")
    return jsonify({
        "ok": True,
        "model": runtime.get("model") or "gpt-4o-mini",
        "provider": runtime.get("provider") or "openai",
        "label": f"{(runtime.get('provider') or 'openai').upper()} · {runtime.get('model') or 'gpt-4o-mini'}",
    })


@bp.route("/api/mobile/profile/ai-runtime", methods=["POST"])
@csrf.exempt
def mobile_profile_ai_runtime_update():
    """Update tenant AI provider/model from mobile configuration."""
    from ...services.ai_runtime_config import resolve_ai_runtime_config as _rac

    tenant = _mobile_resolve_tenant_from_query()
    if tenant is None:
        return jsonify({"ok": False, "message": "Tenant is required."}), 400

    data = request.get_json(silent=True) or {}
    provider = str(data.get("provider") or "openai").strip().lower()
    if provider not in {"openai", "mistral"}:
        provider = "openai"

    model = str(data.get("model") or "").strip()
    if len(model) > 120:
        model = model[:120]

    settings = tenant.settings_json if isinstance(tenant.settings_json, dict) else {}
    settings["ai"] = {
        "provider": provider,
        "model": model,
        "updated_at": datetime.utcnow().isoformat(),
    }
    tenant.settings_json = settings
    flag_modified(tenant, "settings_json")
    db.session.commit()

    from flask import g as _g
    _g.tenant = tenant
    runtime = _rac(default_model="gpt-4o-mini")

    final_provider = str(runtime.get("provider") or provider or "openai")
    final_model = str(runtime.get("model") or model or "gpt-4o-mini")
    return jsonify(
        {
            "ok": True,
            "message": "AI runtime updated.",
            "provider": final_provider,
            "model": final_model,
            "label": f"{final_provider.upper()} · {final_model}",
        }
    )


@bp.route("/api/mobile/finance/accounts")
def mobile_finance_accounts_data():
    tenant = _mobile_resolve_tenant_from_query()
    if not tenant:
        return jsonify({"accounts": [], "count": 0})

    rows = (
        FinanceAccount.query.filter(FinanceAccount.tenant_id == int(tenant.id))
        .order_by(FinanceAccount.name.asc())
        .limit(80)
        .all()
    )
    payload = []
    for row in rows:
        payload.append(
            {
                "id": int(row.id),
                "name": str(row.name or ""),
                "accountType": str(getattr(row, "account_type", "") or ""),
                "companyId": int(getattr(row, "company_id", 0) or 0),
            }
        )
    return jsonify({"accounts": payload, "count": len(payload)})


@bp.route("/api/mobile/finance/entries")
def mobile_finance_entries_data():
    tenant = _mobile_resolve_tenant_from_query()
    tenant_id = int(tenant.id) if tenant else None

    query = FinanceTransaction.query.join(FinanceAccount, FinanceTransaction.account_id == FinanceAccount.id)
    if tenant_id:
        query = query.filter(FinanceTransaction.tenant_id == tenant_id)

    rows = query.order_by(FinanceTransaction.txn_date.desc(), FinanceTransaction.id.desc()).limit(50).all()
    payload = []
    for tx in rows:
        payload.append(
            {
                "id": int(tx.id),
                "date": tx.txn_date.isoformat() if tx.txn_date else "",
                "description": str(tx.description or ""),
                "amount": round(_to_float(tx.amount), 2),
                "account": str(getattr(tx.account, "name", "") or ""),
                "category": str(tx.category or ""),
            }
        )

    return jsonify({"entries": payload, "count": len(payload)})


@bp.route("/api/mobile/finance/entries", methods=["POST"])
@csrf.exempt
def mobile_finance_entries_create():
    tenant = _mobile_resolve_tenant_from_query()
    if not tenant:
        return jsonify({"ok": False, "message": "Tenant is required."}), 400

    data = request.get_json(silent=True) or {}
    description = str(data.get("description") or "").strip()
    category = str(data.get("category") or "").strip()
    raw_amount = data.get("amount")
    account_id_raw = data.get("accountId")

    if not description:
        return jsonify({"ok": False, "message": "Description is required."}), 400
    amount = _to_float(raw_amount)
    if abs(amount) < 0.000001:
        return jsonify({"ok": False, "message": "Amount must be non-zero."}), 400

    try:
        account_id = int(account_id_raw or 0)
    except Exception:
        account_id = 0

    account = None
    if account_id > 0:
        account = FinanceAccount.query.filter(
            FinanceAccount.tenant_id == int(tenant.id),
            FinanceAccount.id == account_id,
        ).first()

    if account is None:
        account = FinanceAccount.query.filter(FinanceAccount.tenant_id == tenant.id).order_by(FinanceAccount.id.asc()).first()
    if not account:
        return jsonify({"ok": False, "message": "No finance account found for tenant."}), 400

    tx = FinanceTransaction(
        tenant_id=int(tenant.id),
        company_id=int(account.company_id),
        account_id=int(account.id),
        txn_date=date.today(),
        amount=amount,
        description=description,
        category=category or None,
    )
    db.session.add(tx)
    db.session.commit()

    return jsonify(
        {
            "ok": True,
            "message": "Entry created.",
            "entry": {
                "id": int(tx.id),
                "date": tx.txn_date.isoformat() if tx.txn_date else "",
                "description": str(tx.description or ""),
                "amount": round(_to_float(tx.amount), 2),
                "account": str(getattr(account, "name", "") or ""),
                "category": str(tx.category or ""),
            },
        }
    )


@bp.route("/api/mobile/finance/category-report")
def mobile_finance_category_report():
    tenant = _mobile_resolve_tenant_from_query()
    tenant_id = int(tenant.id) if tenant else 0
    if not tenant_id:
        return jsonify({"expenses": [], "revenues": [], "count": 0})

    month = request.args.get("month", type=int) or date.today().month
    year = request.args.get("year", type=int) or date.today().year
    month = min(max(month, 1), 12)

    month_start = date(year, month, 1)
    month_end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

    rows = (
        FinanceTransaction.query.filter(
            FinanceTransaction.tenant_id == tenant_id,
            FinanceTransaction.txn_date >= month_start,
            FinanceTransaction.txn_date < month_end,
        )
        .order_by(FinanceTransaction.txn_date.desc(), FinanceTransaction.id.desc())
        .limit(1200)
        .all()
    )

    expense_map: dict[str, dict] = {}
    revenue_map: dict[str, dict] = {}
    for row in rows:
        amount = _to_float(row.amount)
        category = str(row.category or "Uncategorized").strip() or "Uncategorized"
        target = revenue_map if amount >= 0 else expense_map
        bucket = target.get(category)
        if bucket is None:
            bucket = {"category": category, "amount": 0.0, "transactionsCount": 0}
            target[category] = bucket
        bucket["amount"] += abs(amount)
        bucket["transactionsCount"] += 1

    def _sorted_payload(source: dict[str, dict]) -> list[dict]:
        out = [
            {
                "category": str(v.get("category") or ""),
                "amount": round(_to_float(v.get("amount")), 2),
                "transactionsCount": int(v.get("transactionsCount") or 0),
            }
            for v in source.values()
        ]
        out.sort(key=lambda x: (_to_float(x.get("amount")) * -1, str(x.get("category") or "").lower()))
        return out[:12]

    expenses = _sorted_payload(expense_map)
    revenues = _sorted_payload(revenue_map)
    return jsonify({"expenses": expenses, "revenues": revenues, "count": len(expenses) + len(revenues)})


@bp.route("/api/mobile/kanban/move", methods=["POST"])
@csrf.exempt
def mobile_kanban_move_card():
    tenant = _mobile_resolve_tenant_from_query()
    if not tenant:
        return jsonify({"ok": False, "message": "Tenant is required."}), 400

    data = request.get_json(silent=True) or {}
    item_id = str(data.get("itemId") or "").strip()
    target_col = str(data.get("targetColumn") or "").strip().lower()
    allowed_cols = {"backlog", "todo", "doing", "done"}

    if not item_id:
        return jsonify({"ok": False, "message": "itemId is required."}), 400
    if target_col not in allowed_cols:
        return jsonify({"ok": False, "message": "targetColumn is invalid."}), 400

    ws = ProjectWorkspace.query.filter_by(tenant_id=tenant.id).first()
    state = ws.state_json if ws and isinstance(ws.state_json, dict) else {}
    cards_raw = state.get("cards") if isinstance(state.get("cards"), list) else []

    moved = False
    for card in cards_raw:
        if not isinstance(card, dict):
            continue
        if str(card.get("id") or "").strip() == item_id:
            card["col"] = target_col
            moved = True
            break

    if not moved:
        return jsonify({"ok": False, "message": "Card not found."}), 404

    if not ws:
        ws = ProjectWorkspace(tenant_id=tenant.id)
        db.session.add(ws)

    ws.state_json = state
    db.session.commit()
    return jsonify({"ok": True, "message": "Card moved."})


@bp.route("/api/mobile/kanban/tasks", methods=["POST"])
@csrf.exempt
def mobile_kanban_create_task():
    tenant = _mobile_resolve_tenant_from_query()
    if not tenant:
        return jsonify({"ok": False, "message": "Tenant is required."}), 400

    data = request.get_json(silent=True) or {}
    title = str(data.get("title") or "").strip()
    owner = str(data.get("owner") or "").strip()
    priority = str(data.get("priority") or "medium").strip().lower()
    due_date = str(data.get("dueDate") or "").strip()
    description = str(data.get("description") or "").strip()
    target_col = str(data.get("column") or "todo").strip().lower()
    allowed_cols = {"backlog", "todo", "doing", "done"}
    allowed_priorities = {"low", "medium", "high", "critical"}

    if not title:
        return jsonify({"ok": False, "message": "title is required."}), 400
    if target_col not in allowed_cols:
        target_col = "todo"
    if priority not in allowed_priorities:
        priority = "medium"

    ws = ProjectWorkspace.query.filter_by(tenant_id=tenant.id).first()
    if not ws:
        ws = ProjectWorkspace(tenant_id=tenant.id)
        db.session.add(ws)

    state = ws.state_json if isinstance(ws.state_json, dict) else {}
    cards_raw = state.get("cards")
    if not isinstance(cards_raw, list):
        cards_raw = []
        state["cards"] = cards_raw

    task_id = f"card-{uuid4().hex[:12]}"
    card = {
        "id": task_id,
        "title": title[:140],
        "owner": owner[:120],
        "priority": priority,
        "due_date": due_date[:40],
        "description": description[:1000],
        "col": target_col,
    }
    cards_raw.append(card)
    ws.state_json = state
    db.session.commit()

    return jsonify({"ok": True, "message": "Task created.", "task": card})


@bp.route("/api/mobile/kanban/tasks/<string:item_id>", methods=["PUT", "PATCH"])
@csrf.exempt
def mobile_kanban_update_task(item_id: str):
    tenant = _mobile_resolve_tenant_from_query()
    if not tenant:
        return jsonify({"ok": False, "message": "Tenant is required."}), 400

    item_id = str(item_id or "").strip()
    if not item_id:
        return jsonify({"ok": False, "message": "itemId is required."}), 400

    data = request.get_json(silent=True) or {}
    allowed_cols = {"backlog", "todo", "doing", "done"}
    allowed_priorities = {"low", "medium", "high", "critical"}

    ws = ProjectWorkspace.query.filter_by(tenant_id=tenant.id).first()
    state = ws.state_json if ws and isinstance(ws.state_json, dict) else {}
    cards_raw = state.get("cards") if isinstance(state.get("cards"), list) else []

    selected_card = None
    for card in cards_raw:
        if not isinstance(card, dict):
            continue
        if str(card.get("id") or "").strip() == item_id:
            selected_card = card
            break

    if selected_card is None:
        return jsonify({"ok": False, "message": "Card not found."}), 404

    if "title" in data:
        selected_card["title"] = str(data.get("title") or "").strip()[:140]
    if "owner" in data:
        selected_card["owner"] = str(data.get("owner") or "").strip()[:120]
    if "description" in data:
        selected_card["description"] = str(data.get("description") or "").strip()[:1000]
    if "dueDate" in data:
        selected_card["due_date"] = str(data.get("dueDate") or "").strip()[:40]

    if "priority" in data:
        priority = str(data.get("priority") or "").strip().lower()
        if priority in allowed_priorities:
            selected_card["priority"] = priority

    if "column" in data:
        target_col = str(data.get("column") or "").strip().lower()
        if target_col in allowed_cols:
            selected_card["col"] = target_col

    ws.state_json = state
    db.session.commit()
    return jsonify({"ok": True, "message": "Task updated.", "task": selected_card})


@bp.route("/api/mobile/finance/summary")
def mobile_finance_summary_data():
    tenant = _mobile_resolve_tenant_from_query()
    tenant_id = int(tenant.id) if tenant else None
    if not tenant_id:
        return jsonify({"daily": {"in": 0.0, "out": 0.0, "net": 0.0}, "monthly": {"in": 0.0, "out": 0.0, "net": 0.0}})

    today = date.today()
    month_start = date(today.year, today.month, 1)

    query = FinanceTransaction.query.filter(FinanceTransaction.tenant_id == tenant_id)
    daily_rows = query.filter(FinanceTransaction.txn_date == today).all()
    monthly_rows = query.filter(FinanceTransaction.txn_date >= month_start, FinanceTransaction.txn_date <= today).all()

    def _pack(rows):
        inflow = sum(_to_float(r.amount) for r in rows if _to_float(r.amount) > 0)
        outflow = sum(abs(_to_float(r.amount)) for r in rows if _to_float(r.amount) < 0)
        return {
            "in": round(inflow, 2),
            "out": round(outflow, 2),
            "net": round(inflow - outflow, 2),
        }

    return jsonify({"daily": _pack(daily_rows), "monthly": _pack(monthly_rows)})


@bp.route("/api/mobile/learning/modules/<int:module_id>")
def mobile_learning_module_detail(module_id: int):
    tenant = _mobile_resolve_tenant_from_query()
    if not tenant:
        return jsonify({"ok": False, "message": "Tenant is required."}), 400

    lang = normalize_lang(str(request.args.get("lang") or "").strip()) or "fr"
    module = ELearningModule.query.filter(ELearningModule.id == int(module_id), ELearningModule.is_active == True).first()
    if module is None:
        return jsonify({"ok": False, "message": "Module not found."}), 404

    lessons = (
        ELearningLesson.query.filter(
            ELearningLesson.module_id == int(module.id),
            ELearningLesson.is_active == True,
        )
        .order_by(ELearningLesson.order.asc(), ELearningLesson.id.asc())
        .all()
    )
    quizzes = (
        ELearningQuiz.query.join(ELearningLesson, ELearningQuiz.lesson_id == ELearningLesson.id)
        .filter(
            ELearningLesson.module_id == int(module.id),
            ELearningLesson.is_active == True,
            ELearningQuiz.is_active == True,
        )
        .order_by(ELearningLesson.order.asc(), ELearningQuiz.order.asc(), ELearningQuiz.id.asc())
        .all()
    )

    lessons_payload = []
    for lesson in lessons:
        content_i18n = lesson.content_html_i18n if isinstance(lesson.content_html_i18n, dict) else {}
        content = _mobile_i18n_pick(content_i18n, lang)
        if not content and isinstance(content_i18n, dict):
            content = _mobile_i18n_pick(content_i18n, "en")
        lessons_payload.append(
            {
                "id": int(lesson.id),
                "code": str(lesson.code or ""),
                "title": _mobile_i18n_pick(lesson.title_i18n, lang, fallback=str(lesson.code or "Lesson")),
                "summary": _mobile_i18n_pick(lesson.description_i18n, lang)[:260],
                "content": _mobile_plain_text_from_html(content, max_chars=1800),
            }
        )

    quizzes_payload = []
    for quiz in quizzes:
        active_questions = [q for q in (quiz.questions or []) if getattr(q, "is_active", True)]
        quizzes_payload.append(
            {
                "id": int(quiz.id),
                "lessonId": int(quiz.lesson_id),
                "title": _mobile_i18n_pick(quiz.title_i18n, lang, fallback=str(quiz.code or "Quiz")),
                "questionCount": len(active_questions),
                "passingScorePct": int(quiz.pass_threshold or 70),
            }
        )

    module_title = _mobile_i18n_pick(module.title_i18n, lang, fallback=str(module.code or "Module"))
    module_desc = _mobile_i18n_pick(module.description_i18n, lang)

    return jsonify(
        {
            "ok": True,
            "module": {
                "id": int(module.id),
                "code": str(module.code or ""),
                "title": module_title,
                "description": module_desc,
                "lessons": lessons_payload,
                "quizzes": quizzes_payload,
            },
        }
    )


@bp.route("/api/mobile/learning/quizzes/<int:quiz_id>")
def mobile_learning_quiz_detail(quiz_id: int):
    tenant = _mobile_resolve_tenant_from_query()
    if not tenant:
        return jsonify({"ok": False, "message": "Tenant is required."}), 400

    lang = normalize_lang(str(request.args.get("lang") or "").strip()) or "fr"
    quiz = (
        ELearningQuiz.query.join(ELearningLesson, ELearningQuiz.lesson_id == ELearningLesson.id)
        .join(ELearningModule, ELearningLesson.module_id == ELearningModule.id)
        .filter(
            ELearningQuiz.id == int(quiz_id),
            ELearningQuiz.is_active == True,
            ELearningLesson.is_active == True,
            ELearningModule.is_active == True,
        )
        .first()
    )
    if quiz is None:
        return jsonify({"ok": False, "message": "Quiz not found."}), 404

    questions_payload = []
    questions = [q for q in (quiz.questions or []) if getattr(q, "is_active", True)]

    for question in questions:
        question_type = str(question.question_type or "multiple_choice").strip().lower()
        options_payload = []
        if question_type in {"multiple_choice", "true_false"}:
            for opt in question.options or []:
                options_payload.append(
                    {
                        "id": int(opt.id),
                        "text": _mobile_i18n_pick(opt.text_i18n, lang, fallback=f"Option {opt.id}"),
                    }
                )

        questions_payload.append(
            {
                "id": int(question.id),
                "questionType": question_type,
                "text": _mobile_i18n_pick(question.text_i18n, lang, fallback="Question"),
                "explanation": _mobile_i18n_pick(question.explanation_i18n, lang),
                "points": int(question.points or 1),
                "options": options_payload,
            }
        )

    return jsonify(
        {
            "ok": True,
            "quiz": {
                "id": int(quiz.id),
                "title": _mobile_i18n_pick(quiz.title_i18n, lang, fallback=str(quiz.code or "Quiz")),
                "description": _mobile_i18n_pick(quiz.description_i18n, lang),
                "passingScorePct": int(quiz.pass_threshold or 70),
                "showCorrectAnswers": bool(quiz.show_correct_answers),
                "questions": questions_payload,
            },
        }
    )


@bp.route("/api/mobile/learning/quizzes/<int:quiz_id>/submit", methods=["POST"])
@csrf.exempt
def mobile_learning_quiz_submit(quiz_id: int):
    tenant = _mobile_resolve_tenant_from_query()
    if not tenant:
        return jsonify({"ok": False, "message": "Tenant is required."}), 400

    lang = normalize_lang(str(request.args.get("lang") or "").strip()) or "fr"
    quiz = (
        ELearningQuiz.query.join(ELearningLesson, ELearningQuiz.lesson_id == ELearningLesson.id)
        .join(ELearningModule, ELearningLesson.module_id == ELearningModule.id)
        .filter(
            ELearningQuiz.id == int(quiz_id),
            ELearningQuiz.is_active == True,
            ELearningLesson.is_active == True,
            ELearningModule.is_active == True,
        )
        .first()
    )
    if quiz is None:
        return jsonify({"ok": False, "message": "Quiz not found."}), 404

    data = request.get_json(silent=True) or {}
    answers_payload = data.get("answers") if isinstance(data.get("answers"), dict) else {}

    active_questions = [q for q in (quiz.questions or []) if getattr(q, "is_active", True)]
    total_points = 0
    earned_points = 0
    question_scores = {}
    answer_store = {}
    results = []

    for question in active_questions:
        qid = int(question.id)
        q_key = str(qid)
        question_type = str(question.question_type or "multiple_choice").strip().lower()
        max_points = max(1, int(question.points or 1))
        total_points += max_points

        raw_answer = answers_payload.get(q_key)
        if raw_answer is None:
            raw_answer = answers_payload.get(qid)

        is_correct = False
        selected_option_id = None
        free_text_answer = None

        if question_type in {"multiple_choice", "true_false"}:
            try:
                selected_option_id = int(raw_answer or 0)
            except Exception:
                selected_option_id = 0
            correct_options = [int(opt.id) for opt in (question.options or []) if bool(getattr(opt, "is_correct", False))]
            is_correct = selected_option_id in correct_options
            answer_store[q_key] = selected_option_id
        else:
            free_text_answer = str(raw_answer or "").strip()
            expected = str(question.expected_answer or "").strip()
            if expected:
                expected_choices = [part.strip().lower() for part in expected.split("|") if part.strip()]
                is_correct = free_text_answer.lower() in expected_choices
            answer_store[q_key] = free_text_answer

        earned = max_points if is_correct else max(0, int(0 - int(question.penalty_points or 0)))
        earned_points += earned
        question_scores[q_key] = {"earned": int(earned), "max": int(max_points), "correct": bool(is_correct)}

        result_row = {
            "questionId": qid,
            "correct": bool(is_correct),
            "earned": int(earned),
            "max": int(max_points),
            "explanation": _mobile_i18n_pick(question.explanation_i18n, lang),
        }
        if selected_option_id is not None:
            result_row["selectedOptionId"] = int(selected_option_id)
        if free_text_answer is not None:
            result_row["answerText"] = free_text_answer
        results.append(result_row)

    score_pct = 0
    if total_points > 0:
        score_pct = int(round((earned_points / total_points) * 100))
    pass_threshold = int(quiz.pass_threshold or 70)
    passed = score_pct >= pass_threshold

    target_user = _mobile_resolve_tenant_user(tenant)
    if target_user is not None:
        attempt = UserQuizAttempt(
            user_id=int(target_user.id),
            quiz_id=int(quiz.id),
            started_at=datetime.utcnow(),
            submitted_at=datetime.utcnow(),
            score_pct=score_pct,
            points_earned=max(0, int(earned_points)),
            passed=passed,
            answers_json=answer_store,
            question_scores_json=question_scores,
        )
        db.session.add(attempt)

        lesson = getattr(quiz, "lesson", None)
        module_id = int(getattr(lesson, "module_id", 0) or 0)
        if module_id > 0:
            enrollment = UserELearningEnrollment.query.filter(
                UserELearningEnrollment.user_id == int(target_user.id),
                UserELearningEnrollment.module_id == module_id,
            ).first()
            if enrollment is None:
                enrollment = UserELearningEnrollment(
                    user_id=int(target_user.id),
                    module_id=module_id,
                    status="in_progress",
                    progress_percentage=0,
                    overall_score=score_pct,
                    enrolled_at=datetime.utcnow(),
                    started_at=datetime.utcnow(),
                )
                db.session.add(enrollment)
            else:
                enrollment.overall_score = max(int(enrollment.overall_score or 0), int(score_pct))
                if not str(enrollment.status or "").strip():
                    enrollment.status = "in_progress"
                if enrollment.started_at is None:
                    enrollment.started_at = datetime.utcnow()

        db.session.commit()

    return jsonify(
        {
            "ok": True,
            "message": "Quiz submitted.",
            "result": {
                "scorePct": int(score_pct),
                "passed": bool(passed),
                "passingScorePct": pass_threshold,
                "pointsEarned": int(max(0, earned_points)),
                "pointsTotal": int(total_points),
                "questions": results,
            },
        }
    )


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
        (_abs("public.docs_ml_sdk"), "weekly", "0.9"),
        (_abs("public.docs_vscode_plugin"), "weekly", "0.9"),
        (_abs("public.plans") + "?product=bi", "weekly", "0.8"),
        (_abs("public.plans") + "?product=ml", "weekly", "0.8"),
        (_abs("public.plans") + "?product=credit", "weekly", "0.8"),
        (_abs("public.plans") + "?product=project", "weekly", "0.8"),
        (_abs("public.plans") + "?product=ifrs9", "weekly", "0.8"),
        (_abs("public.plans") + "?product=all", "weekly", "0.7"),
        (_abs("public.product_finance"), "weekly", "0.9"),
        (_abs("public.product_bi"), "weekly", "0.9"),
        (_abs("public.product_ml"), "weekly", "0.9"),
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
