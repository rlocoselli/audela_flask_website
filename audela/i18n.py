"""Very small i18n layer (no external build step).

This project is a Flask website and a lightweight BI portal.

We intentionally keep i18n *self-contained* (dictionary-based) to avoid introducing
extra build steps (.po/.mo compilation) and to make deployment simpler.

Usage:
- In Jinja templates: {{ _('Some text') }}
- In Python: tr('Some text', lang)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


DEFAULT_LANG = "pt"


@dataclass(frozen=True)
class LangInfo:
    code: str
    label: str


SUPPORTED_LANGS: dict[str, LangInfo] = {
    "pt": LangInfo("pt", "Português"),
    "en": LangInfo("en", "English"),
    "fr": LangInfo("fr", "Français"),
    "es": LangInfo("es", "Español"),
    "it": LangInfo("it", "Italiano"),
    "de": LangInfo("de", "Deutsch"),
}


# msgid -> translation
TRANSLATIONS: dict[str, dict[str, str]] = {
    "pt": {
        # Nota: As chaves em português já são os msgid, então este dicionário é principalmente
        # para referência e consistência. A função tr() retorna a chave quando lang==DEFAULT_LANG

        "Accueil": "Início",
        "À propos": "Sobre",
        "Expertise": "Expertise",
        "Solutions": "Soluções",
        "Pourquoi AUDELA": "Por que AUDELA",
        "Projets": "Projetos",
        "Plans BI": "Planos BI",
        "Contact": "Contato",
        "Tous droits réservés.": "Todos os direitos reservados.",

        # Hero / landing
        "La technologie au service de la décision.": "Tecnologia a serviço da decisão.",
        "Data, BI, ERP, LegalTech & IA — au cœur de vos opérations.": "Dados, BI, ERP, LegalTech e IA — no coração das suas operações.",
        "Illustration AUDELA": "Ilustração AUDELA",
        "Next": "Próximo",
        "Grenoble & Alpes": "Grenoble & Alpes",
        "Au-delà des données": "Além dos dados",
        "Transformer l'information en décisions — avec une ingénierie logicielle robuste et une compréhension métier réelle.": "Transforme informação em decisões — com engenharia de software robusta e compreensão real do negócio.",
        "Nous construisons des systèmes qui tiennent dans la durée : pipelines data industrialisés, APIs fiables, applications web et mobile, et des dashboards compréhensibles par les équipes terrain comme par la direction.": "Construímos sistemas duráveis: pipelines de dados industrializados, APIs confiáveis, aplicações web e mobile e dashboards compreensíveis tanto para times de campo quanto para a direção.",
        "Notre approche est pragmatique et \"production-first\" : sécurité, performance, observabilité, documentation, et transfert de compétences. L'objectif : livrer vite, sans dette technique.": "Nossa abordagem é pragmática e \"production-first\": segurança, performance, observabilidade, documentação e transferência de conhecimento. Objetivo: entregar rápido, sem dívida técnica.",

        # Blocos / seções
        "Business Intelligence": "Business Intelligence",
        "Analyse de données & Business Intelligence": "Análise de dados e Business Intelligence",
        "Ingestion, modélisation, qualité et exposition : des indicateurs fiables, traçables et actionnables.": "Ingestão, modelagem, qualidade e exposição: indicadores confiáveis, rastreáveis e acionáveis.",
        "Nous connectons vos systèmes (ERP, CRM, finance, opérations, APIs), structurons la donnée (DWH/ELT), et livrons des tableaux de bord qui répondent à des questions concrètes : marge, performance commerciale, délais, risques, conformité.": "Conectamos seus sistemas (ERP, CRM, finanças, operações, APIs), estruturamos os dados (DWH/ELT) e entregamos dashboards que respondem a perguntas concretas: margem, performance comercial, prazos, riscos e conformidade.",
        "Voir les écrans Metabase": "Ver telas do Metabase",

        "Plateformes métiers": "Plataformas de negócio",
        "Plateformes métiers, ERP & IA appliquée": "Plataformas de negócio, ERP e IA aplicada",
        "Des outils métier qui reflètent vos workflows, avec une IA utile et explicable.": "Ferramentas de negócio que refletem seus fluxos de trabalho, com IA útil e explicável.",
        "Découvrir BeLegal": "Conhecer o BeLegal",

        # Seção “Visuels”
        "Visuels & cas d’usage : Data, IA, ERP": "Visuais e casos de uso: Dados, IA, ERP",
        "Un aperçu des types de solutions que nous concevons : pilotage, automatisation et intelligence appliquée.": "Uma visão geral dos tipos de soluções que desenvolvemos: gestão, automação e inteligência aplicada.",
        "Data & BI": "Dados e BI",
        "Tableaux de bord exécutifs, KPIs, gouvernance, qualité et traçabilité de bout en bout.": "Dashboards executivos, KPIs, governança, qualidade e rastreabilidade ponta a ponta.",
        "IA appliquée": "IA aplicada",
        "Détection d'anomalies, scoring de risques, assistants métiers et analyse prédictive.": "Detecção de anomalias, scoring de risco, assistentes de negócio e análise preditiva.",
        "ERP & workflows": "ERP e workflows",
        "Workflows métiers, intégrations SI, automatisation, contrôles et auditabilité.": "Workflows de negócio, integrações de sistemas, automação, controles e auditabilidade.",
        "LegalTech": "LegalTech",
        "Gestion des dossiers, rentabilité par affaire, génération documentaire, conformité.": "Gestão de casos, rentabilidade por caso, geração de documentos e conformidade.",

        # Seção “Pourquoi”
        "Une expertise de fond, une exécution rigoureuse, et une obsession de la qualité en production.": "Expertise profunda, execução rigorosa e obsessão por qualidade em produção.",
        "Cloud-native, API-first, intégrations propres : une base solide pour durer et évoluer.": "Cloud-native, API-first, integrações limpas: uma base sólida para durar e evoluir.",
        "Conformité et gouvernance : contrôles d’accès, traçabilité, et bonnes pratiques SI.": "Conformidade e governança: controle de acesso, rastreabilidade e boas práticas de TI.",
        "Pipelines & qualité : de la source au tableau de bord, sans compromis sur les données.": "Pipelines e qualidade: da fonte ao dashboard, sem comprometer os dados.",
        "CI/CD, monitoring, logs & alerting : stabilité, performance et mises en production rapides.": "CI/CD, monitoramento, logs e alertas: estabilidade, performance e deploys rápidos.",
        "Interopérabilité : connexion ERP/CRM/outils métiers, synchronisation et automatisation.": "Interoperabilidade: conexão com ERP/CRM/ferramentas de negócio, sincronização e automação.",
        "Delivery et transfert : cadrage, documentation et montée en compétence de vos équipes.": "Entrega e transferência: alinhamento, documentação e capacitação do seu time.",
        "Découvrir nos plans BI": "Conheça nossos planos de BI",

        # CTA / contato
        "Parlons de votre projet": "Vamos falar do seu projeto",
        "Décrivez votre besoin (Data/BI, ERP, LegalTech, IA, Mobile, IoT). Nous vous recontactons rapidement.": "Descreva sua necessidade (Dados/BI, ERP, LegalTech, IA, Mobile, IoT). Entraremos em contato rapidamente.",
        "Votre adresse e-mail": "Seu e-mail",
        "Être rappelé": "Quero contato",

        # Auth messages
        "Tenant não encontrado.": "Tenant não encontrado.",
        "Credenciais inválidas.": "Credenciais inválidas.",
        "Preencha todos os campos.": "Preencha todos os campos.",
        "Slug já existe.": "Slug já existe.",
        "Tenant criado. Faça login.": "Tenant criado. Faça login.",

        # Data source messages
        "Preencha nome, tipo e URL de conexão.": "Preencha nome, tipo e URL de conexão.",
        "Fonte criada.": "Fonte criada.",
        "Fonte removida.": "Fonte removida.",
        "Falha ao introspectar: {error}": "Falha ao introspectar: {error}",
        "Selecione uma fonte válida.": "Selecione uma fonte válida.",
        "Selecione uma fonte.": "Selecione uma fonte.",
        "Fonte inválida.": "Fonte inválida.",

        # Question messages
        "Preencha nome, fonte e SQL.": "Preencha nome, fonte e SQL.",
        "Pergunta criada.": "Pergunta criada.",
        "Pergunta removida.": "Pergunta removida.",

        # Dashboard messages
        "Dashboard criado.": "Dashboard criado.",
        "Dashboard removido.": "Dashboard removido.",
        "Dashboard definido como principal.": "Dashboard definido como principal.",
        "Operação não suportada: execute as migrações do banco para habilitar essa função.": "Operação não suportada: execute as migrações do banco para habilitar essa função.",
        "Informe um nome.": "Informe um nome.",

        # Configuration messages
        "Configuração inválida.": "Configuração inválida.",

        # User messages
        "Email e senha são obrigatórios.": "Email e senha são obrigatórios.",
        "Usuário criado.": "Usuário criado.",
        "Usuário removido.": "Usuário removido.",

        # NLQ service messages
        "Não foi possível identificar uma tabela com segurança.": "Não foi possível identificar uma tabela com segurança.",
        "Selecione uma tabela no Query Builder (à direita) ou escreva o SQL manualmente.": "Selecione uma tabela no Query Builder (à direita) ou escreva o SQL manualmente.",
        "Tabela não identificada": "Tabela não identificada",
        "Texto vazio": "Texto vazio",
        "Coluna métrica escolhida por fallback": "Coluna métrica escolhida por fallback",
        "Coluna métrica não identificada": "Coluna métrica não identificada",

        # Home page
        "O que já está no MVP": "O que já está no MVP",
        "Fontes por tenant (cadastro + introspecção)": "Fontes por tenant (cadastro + introspecção)",
        "Editor SQL (execução ad-hoc com limites)": "Editor SQL (execução ad-hoc com limites)",
        "Perguntas (queries salvas) + execução": "Perguntas (queries salvas) + execução",
        "Dashboards (cards simples com perguntas)": "Dashboards (cards simples com perguntas)",
        "Auditoria + Query Runs por tenant": "Auditoria + Query Runs por tenant",
        "Começar": "Começar",
        "Crie uma fonte": "Crie uma fonte",
        "Introspecte metadados na fonte (botão 'Introspectar')": "Introspecte metadados na fonte (botão 'Introspectar')",
        "Teste uma consulta no Editor SQL": "Teste uma consulta no Editor SQL",
        "Salve uma Pergunta e crie um Dashboard": "Salve uma Pergunta e crie um Dashboard",
        "cadastro + introspecção": "cadastro + introspecção",
        "execução ad-hoc com limites": "execução ad-hoc com limites",
        "queries salvas": "queries salvas",
        "cards simples com perguntas": "cards simples com perguntas",
        "por tenant": "por tenant",
        "Nova": "Nova",
        "e crie um": "e crie um",

        # Placeholder texts
        "Ex.: DW Produção": "Ex.: DW Produção",
        "Ex.: postgresql+psycopg2://user:pass@host:5432/dbname": "Ex.: postgresql+psycopg2://user:pass@host:5432/dbname",
        "public": "public",
        "tenant_id": "tenant_id",
        "ex: total vendas por mês": "ex: total vendas por mês",
        "acme": "acme",
        "you@example.com": "you@example.com",
        "tenant slug (ex.: acme)": "tenant slug (ex.: acme)",
        "nome do tenant": "nome do tenant",
        "email do admin": "email do admin",
        "senha": "senha",
        "value": "value",
        "SELECT ...": "SELECT ...",

        # AI service prompts
        "You are a BI analyst": "Você é um analista de BI",
        "You receive metadata and data sample": "Você recebe metadados e uma amostra de dados (colunas/linhas) de uma pergunta SQL",
        "Respond with clear insights": "Responda com insights claros, hipóteses, limitações, e sugira gráficos",
        "Your output MUST be valid JSON": "Sua saída DEVE ser um JSON válido (sem markdown, sem blocos de código) com estas chaves",
        "analysis key": "analysis: string (markdown simples permitido, mas sem HTML)",
        "charts key": "charts: lista de objetos {title: string, echarts_option: object}",
        "followups key": "followups: lista de strings",
        "Use only the provided sample": "Use apenas a amostra e o perfil fornecidos; se faltar algo, diga explicitamente",
        "For charts generate safe ECharts": "Para charts, gere opções ECharts seguras, sem funções JS",
        "If insufficient data return empty": "Se não houver dados suficientes, retorne charts=[] e explique no analysis",


        # Auto-added i18n keys
        "Relatórios": "Relatórios",
        "Novo relatório": "Novo relatório",
        "Construa relatórios com drag & drop (estilo Crystal Reports).": "Construa relatórios com arraste e solte (estilo Crystal Reports).",
        "Nenhum relatório criado ainda.": "Nenhum relatório criado ainda.",
        "Abrir builder": "Abrir builder",
        "Arraste e solte": "Arraste e solte",
        "Cabeçalho": "Cabeçalho",
        "Corpo": "Corpo",
        "Rodapé": "Rodapé",
        "Editar": "Editar",
        "Remover": "Remover",
        "Título do bloco:": "Título do bloco:",
        "Pergunta salva": "Pergunta salva",
        "Falha ao salvar": "Falha ao salvar",
        "Arraste aqui...": "Arraste aqui...",
        "Salvo": "Salvo",
        "Pergunta #{n}": "Pergunta #{n}",
        "Imagem": "Imagem",
        "Figura / logotipo / screenshot": "Figura / logotipo / screenshot",
        "Adicionar imagem": "Adicionar imagem",
        "URL (https://...)": "URL (https://...)",
        "Isso cria um bloco “Imagem” no corpo do relatório.": "Isso cria um bloco “Imagem” no corpo do relatório.",
        "URL da imagem:": "URL da imagem:",
        "Texto alternativo (alt):": "Texto alternativo (alt):",
        "Legenda (opcional):": "Legenda (opcional):",
        "Largura (ex.: 300px ou 50%):": "Largura (ex.: 300px ou 50%):",
        "Alinhamento (left/center/right):": "Alinhamento (left/center/right):",
        "Cor do texto (ex.: #111 ou vazio):": "Cor do texto (ex.: #111 ou vazio):",
        "Cor de fundo (ex.: #fff ou vazio):": "Cor de fundo (ex.: #fff ou vazio):",
        "Imagem não disponível": "Imagem não disponível",
        "Texto (Markdown):": "Texto (Markdown):",
        "Texto:": "Texto:",
        "Bloco": "Bloco",
        "Sem linhas retornadas.": "Sem linhas retornadas.",
        "Erro ao executar pergunta: {error}": "Erro ao executar pergunta: {error}",
        "Editar bloco": "Editar bloco",
        "Título": "Título",
        "URL da imagem": "URL da imagem",
        "https://...": "https://...",
        "Texto alternativo (alt)": "Texto alternativo (alt)",
        "Largura": "Largura",
        "ex.: 300px ou 50%": "ex.: 300px ou 50%",
        "Pré-visualização": "Pré-visualização",
        "Estilo": "Estilo",
        "Cor do texto": "Cor do texto",
        "Cor de fundo": "Cor de fundo",
        "Sem": "Sem",
        "hex ou vazio": "hex ou vazio",
        "Aplicar": "Aplicar",
        "Esquerda": "Esquerda",
        "Centro": "Centro",
        "Direita": "Direita",
        "Padrão": "Padrão",
        "ETL Builder": "ETL Builder",
        "ETLs": "ETLs",
        "Novo workflow": "Novo workflow",
        "Workflows salvos": "Workflows salvos",
        "Salvar workflow": "Salvar workflow",
        "Nome do workflow": "Nome do workflow",
        "Salvar cria JSON + YAML quando o fluxo é válido.": "Salvar cria JSON + YAML quando o fluxo é válido.",
        "Conexões": "Conexões",
        "Use o catálogo para selecionar DB/API. Credenciais são armazenadas criptografadas.": "Use o catálogo para selecionar DB/API. Credenciais são armazenadas criptografadas.",
        "Nenhum workflow salvo.": "Nenhum workflow salvo.",
        "Carregando...": "Carregando...",
        "Erro ao carregar.": "Erro ao carregar.",
        "Abrir": "Abrir",
        "Nome": "Nome",
        "Formato": "Formato",
        "Ações": "Ações",
        "Preview": "Preview",
        "Executar": "Executar",
        "Adicionar passos": "Adicionar passos",
        "Preview (últimos resultados)": "Preview (últimos resultados)",
        "Dica: campos JSON devem ser um JSON válido (ex: {\"Authorization\":\"Bearer ...\"}).": "Dica: campos JSON devem ser um JSON válido (ex: {\"Authorization\":\"Bearer ...\"}).",
        "DB Sources": "DB Sources",
        "API Sources": "API Sources",
        "Use existing sources catalog. Click plug icon to test connection.": "Use existing sources catalog. Click plug icon to test connection.",

        # Workspaces (DuckDB + Files)
        "Novo workspace": "Novo workspace",
        "Workspace permite fazer JOIN entre arquivos (CSV/Excel/Parquet) e tabelas do banco, tudo em DuckDB.": "Workspace permite fazer JOIN entre arquivos (CSV/Excel/Parquet) e tabelas do banco, tudo em DuckDB.",
        "Configuração": "Configuração",
        "Fonte de banco (opcional)": "Fonte de banco (opcional)",
        "sem banco": "sem banco",
        "Para JOIN com banco, selecione as tabelas. Elas ficam acessíveis como db.<tabela>.": "Para JOIN com banco, selecione as tabelas. Elas ficam acessíveis como db.<tabela>.",
        "Tabelas do banco": "Tabelas do banco",
        "Selecionar tabelas": "Selecionar tabelas",
        "Dica: use o Construtor rápido de JOIN para gerar um SQL inicial.": "Dica: use o Construtor rápido de JOIN para gerar um SQL inicial.",
        "Limite de linhas": "Limite de linhas",
        "Usado para amostragem (segurança/performance).": "Usado para amostragem (segurança/performance).",
        "Abrir File Explorer": "Abrir File Explorer",
        "Nenhum arquivo uploadado ainda. Use o menu Arquivos.": "Nenhum arquivo uploadado ainda. Use o menu Arquivos.",
        "Filtrar arquivos…": "Filtrar arquivos…",
        "Alias (tabela)": "Alias (tabela)",
        "Criar workspace": "Criar workspace",
        "Construtor rápido de JOIN": "Construtor rápido de JOIN",
        "Selecione arquivos/tabelas e gere um SQL inicial com JOINs e autocomplete de colunas.": "Selecione arquivos/tabelas e gere um SQL inicial com JOINs e autocomplete de colunas.",
        "Selecione arquivos/tabelas": "Selecione arquivos/tabelas",
        "Tabela base": "Tabela base",
        "Sugestões de JOIN": "Sugestões de JOIN",
        "JOINs": "JOINs",
        "Adicionar JOIN": "Adicionar JOIN",
        "Coluna": "Coluna",
        "Gerar SQL com IA": "Gerar SQL com IA",
        "Descreva sua análise": "Descreva sua análise",
        "SQL inicial": "SQL inicial",
        "Seu SQL aparecerá aqui…": "Seu SQL aparecerá aqui…",
        "Ao criar o workspace, este SQL fica salvo como rascunho (starter_sql) para você copiar no Editor SQL.": "Ao criar o workspace, este SQL fica salvo como rascunho (starter_sql) para você copiar no Editor SQL.",
        "Filtrar tabelas…": "Filtrar tabelas…",
        "Nenhuma tabela encontrada.": "Nenhuma tabela encontrada.",
        "Selecione uma fonte de banco para listar tabelas.": "Selecione uma fonte de banco para listar tabelas.",
        "Falha ao carregar schema.": "Falha ao carregar schema.",
        "Selecione pelo menos duas tabelas para sugerir joins.": "Selecione pelo menos duas tabelas para sugerir joins.",
        "Nenhuma sugestão disponível.": "Nenhuma sugestão disponível.",
        "SQL gerado.": "SQL gerado.",
        "Falha ao gerar SQL.": "Falha ao gerar SQL.",
        "Schema: {name}": "Schema: {name}",
        "Ex.: BI - Vendas + Clientes": "Ex.: BI - Vendas + Clientes",
        "Ex.: total de vendas por mês e segmento, com ticket médio": "Ex.: total de vendas por mês e segmento, com ticket médio",
        "Workspace criado.": "Workspace criado.",
    },
    "en": {
        "Accueil": "Home",
        "À propos": "About",
        "Expertise": "Expertise",
        "Solutions": "Solutions",
        "Pourquoi AUDELA": "Why AUDELA",
        "Projets": "Projects",
        "Plans BI": "BI Plans",
        "Área BI": "BI Area",
        "Contact": "Contact",
        "Mobile": "Mobile",
        "IoT & Neuro": "IoT & Neuro",
        "BI & Metabase": "BI & Metabase",
        "BeLegal (LegalTech)": "BeLegal (LegalTech)",
        "Tous droits réservés.": "All rights reserved.",

        # Index / landing
        "La technologie au service de la décision.": "Technology powering better decisions.",
        "Data, BI, ERP, LegalTech & IA — au cœur de vos opérations.": "Data, BI, ERP, LegalTech & AI — at the heart of your operations.",
        "Illustration AUDELA": "AUDELA illustration",
        "Next": "Next",
        "Grenoble & Alpes": "Grenoble & Alps",
        "Au-delà des données": "Beyond data",
        "Transformer l'information en décisions — avec une ingénierie logicielle robuste et une compréhension métier réelle.": "Turn information into decisions — with robust software engineering and real business understanding.",
        "Nous construisons des systèmes qui tiennent dans la durée : pipelines data industrialisés, APIs fiables, applications web et mobile, et des dashboards compréhensibles par les équipes terrain comme par la direction.": "We build systems that last: industrialized data pipelines, reliable APIs, web & mobile apps, and dashboards understandable by both field teams and executives.",
        "Notre approche est pragmatique et \"production-first\" : sécurité, performance, observabilité, documentation, et transfert de compétences. L'objectif : livrer vite, sans dette technique.": "Our approach is pragmatic and production-first: security, performance, observability, documentation, and knowledge transfer. Goal: deliver fast, without technical debt.",
        "Business Intelligence": "Business Intelligence",
        "Analyse de données & Business Intelligence": "Data analysis & Business Intelligence",
        "Ingestion, modélisation, qualité et exposition : des indicateurs fiables, traçables et actionnables.": "Ingestion, modeling, quality and exposure: reliable, traceable and actionable indicators.",
        "Nous connectons vos systèmes (ERP, CRM, finance, opérations, APIs), structurons la donnée (DWH/ELT), et livrons des tableaux de bord qui répondent à des questions concrètes : marge, performance commerciale, délais, risques, conformité.": "We connect your systems (ERP, CRM, finance, operations, APIs), structure data (DWH/ELT), and deliver dashboards that answer concrete questions: margin, sales performance, lead times, risks, compliance.",
        "Voir les écrans Metabase": "See Metabase screens",
        "Plateformes métiers": "Business platforms",
        "Plateformes métiers, ERP & IA appliquée": "Business platforms, ERP & Applied AI",
        "Des outils métier qui reflètent vos workflows, avec une IA utile et explicable.": "Business tools that reflect your workflows, with useful and explainable AI.",
        "Découvrir BeLegal": "Discover BeLegal",

        # Portal
        "Portal BI": "BI Portal",
        "Usuário": "User",
        "Sair": "Logout",
        "Home": "Home",
        "Fontes": "Data sources",
        "Metadados": "Metadata",
        "Editor SQL": "SQL Editor",
        "Query Builder": "Query Builder",
        "Perguntas": "Questions",
        "Dashboards": "Dashboards",
        "Execuções": "Runs",
        "Auditoria": "Audit",
        "Voltar": "Back",
        "Cancelar": "Cancel",
        "Salvar": "Save",
        "Executar": "Run",
        "Resultado": "Result",
        "Erro": "Error",
        "Linhas": "Rows",
        "Linhas retornadas": "Returned rows",
        "Nova pergunta": "New question",
        "Nova fonte": "New data source",
        "Criar": "Create",
        "Dashboard": "Dashboard",
        "Nenhum card ainda. Crie um dashboard escolhendo perguntas.": "No cards yet. Create a dashboard by selecting questions.",
        "Exportar PDF": "Export PDF",
        "Limpar filtros": "Clear filters",
        "Filtros": "Filters",
        "Adicionar filtro": "Add filter",
        "Visualização": "Visualization",
        "Configurar visualização": "Configure visualization",
        "Prévia": "Preview",
        "Tipo": "Type",
        "Tabela": "Table",
        "Gráfico": "Chart",
        "Pivot": "Pivot",
        "Gauges": "Gauges",
        "Drill down": "Drill down",
        "Exportar": "Export",
        "Gerar SQL": "Generate SQL",
        "Linguagem humana": "Natural language",
        "Gerar": "Generate",
        "Tabelas": "Tables",
        "Colunas": "Columns",
        "Executar pergunta": "Run question",
        "Parâmetros (JSON)": "Parameters (JSON)",
        "Use :nome_param no SQL e preencha valores aqui. tenant_id é aplicado automaticamente.": "Use :param_name in SQL and fill values here. tenant_id is applied automatically.",
        "Gerar SQL no editor": "Generate SQL in editor",
        "Fonte de dados": "Data source",
        "Estrutura": "Schema",
        "Limite": "Limit",
        "montar SELECT com ajuda da estrutura": "build SELECT with schema help",
        "Escolha uma fonte para ver tabelas e colunas (autocomplete).": "Choose a source to see tables and columns (autocomplete).",
        "Execute consultas ad-hoc, com autocomplete, Query Builder e linguagem humana.": "Run ad-hoc queries with autocomplete, a query builder, and natural language.",
        "Sem linhas retornadas.": "No rows returned.",

        # UI+AI
        "Editar layout": "Edit layout",
        "Salvar layout": "Save layout",
        "Cancelar edição": "Cancel edit",
        "Layout salvo.": "Layout saved.",
        "Falha ao salvar layout.": "Failed to save layout.",
        "Modo edição": "Edit mode",
        "IA": "AI",
        "Chat IA": "AI chat",
        "Pergunte sobre os dados": "Ask about the data",
        "Selecione uma pergunta": "Select a question",
        "Enviar": "Send",
        "Mensagem": "Message",
        "Histórico": "History",
        "Limpar chat": "Clear chat",
        "Gerando resposta...": "Generating response...",
        "Análise": "Analysis",
        "Gráficos sugeridos": "Suggested charts",
        "Sugestões de follow-up": "Follow-up suggestions",
        "Chave OpenAI ausente. Defina OPENAI_API_KEY no servidor.": "Missing OpenAI key. Set OPENAI_API_KEY on the server.",
        "Erro ao chamar IA: {error}": "AI call failed: {error}",
        "Tema": "Theme",
        "Claro": "Light",
        "Escuro": "Dark",
        "Explorar": "Explore",
        "Explore dados e crie visualizações como no Superset/Metabase.": "Explore data and create visualizations like Superset/Metabase.",
        "Adicionar card": "Add card",
        "Remover card": "Remove card",
        "Buscar pergunta": "Search question",
        "Digite para filtrar...": "Type to filter...",
        "Você pode refinar depois em Configurar visualização.": "You can refine later in Configure visualization.",
        "Atualizar": "Refresh",
        "Salvar visualização": "Save visualization",
        "Visualização salva.": "Visualization saved.",
        "Adicionar ao dashboard": "Add to dashboard",
        "Cria um card no dashboard com esta visualização.": "Creates a dashboard card with this visualization.",
        "Card adicionado ao dashboard.": "Card added to dashboard.",
        "Card criado. Recarregando...": "Card created. Reloading...",
        "Criando card...": "Creating card...",
        "Remover card?": "Remove card?",
        "Sem filtros.": "No filters.",
        "Campo": "Field",
        "Dimensão": "Dimension",
        "Métrica": "Metric",
        "Drill-down": "Drill-down",
        "Clique no gráfico para filtrar por um valor.": "Click the chart to filter by a value.",
        "Pivot linhas": "Pivot rows",
        "Pivot colunas": "Pivot columns",
        "Pivot valor": "Pivot value",
        "Carregando...": "Loading...",
        "Visuels & cas d’usage : Data, IA, ERP": "Visuals & use cases: Data, AI, ERP",
        "Un aperçu des types de solutions que nous concevons : pilotage, automatisation et intelligence appliquée.": "A glimpse of the types of solutions we design: operational dashboards, automation and applied intelligence.",
        "Data & BI": "Data & BI",
        "Tableaux de bord exécutifs, KPIs, gouvernance, qualité et traçabilité de bout en bout.": "Executive dashboards, KPIs, governance, quality and end-to-end traceability.",
        "IA appliquée": "Applied AI",
        "Détection d'anomalies, scoring de risques, assistants métiers et analyse prédictive.": "Anomaly detection, risk scoring, business assistants and predictive analytics.",
        "ERP & workflows": "ERP & workflows",
        "Workflows métiers, intégrations SI, automatisation, contrôles et auditabilité.": "Business workflows, system integrations, automation, controls and auditability.",
        "LegalTech": "LegalTech",
        "Gestion des dossiers, rentabilité par affaire, génération documentaire, conformité.": "Case management, matter-level profitability, document generation, compliance.",
        "Pourquoi AUDELA": "Why AUDELA",
        "Une expertise de fond, une exécution rigoureuse, et une obsession de la qualité en production.": "Deep expertise, rigorous execution, and an obsession with production quality.",
        "Cloud-native, API-first, intégrations propres : une base solide pour durer et évoluer.": "Cloud-native, API-first, clean integrations: a solid foundation to last and scale.",
        "Conformité et gouvernance : contrôles d’accès, traçabilité, et bonnes pratiques SI.": "Compliance and governance: access controls, traceability, and IT best practices.",
        "Pipelines & qualité : de la source au tableau de bord, sans compromis sur les données.": "Pipelines & quality: from source to dashboard, without compromising data.",
        "CI/CD, monitoring, logs & alerting : stabilité, performance et mises en production rapides.": "CI/CD, monitoring, logs & alerting: stability, performance and fast production deployments.",
        "Interopérabilité : connexion ERP/CRM/outils métiers, synchronisation et automatisation.": "Interoperability: ERP/CRM/business tools connectivity, synchronization and automation.",
        "Delivery et transfert : cadrage, documentation et montée en compétence de vos équipes.": "Delivery and handover: scoping, documentation and upskilling your teams.",
        "Découvrir nos plans BI": "Discover our BI plans",
        "Default": "Default",
        "Aurora": "Aurora",
        "Nimbus": "Nimbus",
        "Onyx": "Onyx",
        "Select data source": "Select data source",
        "Load diagram": "Load diagram",
        "Refresh": "Refresh",
        "Click a node to highlight relations. Use mousewheel to zoom.": "Click a node to highlight relations. Use mousewheel to zoom.",
        "Parlons de votre projet": "Let's talk about your project",
        "Décrivez votre besoin (Data/BI, ERP, LegalTech, IA, Mobile, IoT). Nous vous recontactons rapidement.": "Describe your need (Data/BI, ERP, LegalTech, AI, Mobile, IoT). We'll get back to you quickly.",
        "Votre adresse e-mail": "Your email address",
        "Être rappelé": "Be contacted",
        "OK": "OK",
            # Source diagram module
            "Source Diagram": "Source Diagram",
            "Select data source": "Select data source",
            "Load diagram": "Load diagram",
            "Refresh": "Refresh",
            "Click a node to highlight relations. Use mousewheel to zoom.": "Click a node to highlight relations. Use mousewheel to zoom.",

            # Home page
            "O que já está no MVP": "What's already in the MVP",
            "Fontes por tenant (cadastro + introspecção)": "Data sources per tenant (registration + introspection)",
            "Editor SQL (execução ad-hoc com limites)": "SQL Editor (ad-hoc execution with limits)",
            "Perguntas (queries salvas) + execução": "Questions (saved queries) + execution",
            "Dashboards (cards simples com perguntas)": "Dashboards (simple cards with questions)",
            "Auditoria + Query Runs por tenant": "Audit + Query Runs per tenant",
            "Começar": "Getting Started",
            "Crie uma fonte": "Create a data source in Sources → New",
            "Introspecte metadados na fonte (botão 'Introspectar')": "Introspect metadata on the source (\"Introspect\" button)",
            "Teste uma consulta no Editor SQL": "Test a query in SQL Editor",
            "Salve uma Pergunta e crie um Dashboard": "Save a Question and create a Dashboard",
            "cadastro + introspecção": "registration + introspection",
            "execução ad-hoc com limites": "ad-hoc execution with limits",
            "queries salvas": "saved queries",
            "cards simples com perguntas": "simple cards with questions",
            "por tenant": "per tenant",
            "Nova": "New",
            "e crie um": "and create a",

            # Auth messages
            "Tenant não encontrado.": "Tenant not found.",
            "Credenciais inválidas.": "Invalid credentials.",
            "Preencha todos os campos.": "Fill in all fields.",
            "Slug já existe.": "Slug already exists.",
            "Tenant criado. Faça login.": "Tenant created. Please log in.",

            # Data source messages
            "Preencha nome, tipo e URL de conexão.": "Fill in name, type, and connection URL.",
            "Fonte criada.": "Data source created.",
            "Fonte removida.": "Data source removed.",
            "Falha ao introspectar: {error}": "Introspection failed: {error}",
            "Selecione uma fonte válida.": "Select a valid data source.",
            "Selecione uma fonte.": "Select a data source.",
            "Fonte inválida.": "Invalid data source.",
            "Informe uma URL de conexão.": "Provide a connection URL.",
            "Conexão OK.": "Connection OK.",
            "Falha na conexão.": "Connection failed.",
            "Falha na conexão: {error}": "Connection failed: {error}",

            # Data source form (wizard)
            "Nova fonte de dados": "New data source",
            "Configure uma nova origem de dados para consultas e relatórios.": "Configure a new data source for queries and reports.",
            "Informações básicas": "Basic information",
            "Ex.: DW Produção": "e.g.: Production DW",
            "Nome interno para identificar a fonte.": "Internal name used to identify the source.",
            "Tipo de banco": "Database type",
            "Conexão": "Connection",
            "Assistente": "Wizard",
            "URL manual": "Manual URL",
            "URL (manual)": "URL (manual)",
            "Porta": "Port",
            "Database": "Database",
            "Senha": "Password",
            "(opcional)": "(optional)",
            "(deixe vazio para manter)": "(leave empty to keep)",
            "Fica criptografado no config. Se preferir, cole uma URL pronta no modo \"URL manual\".": "Stored encrypted in config. If you prefer, paste a ready URL in \"Manual URL\" mode.",
            "Driver (SQL Server)": "Driver (SQL Server)",
            "Service Name (Oracle)": "Service Name (Oracle)",
            "SID (Oracle)": "SID (Oracle)",
            "Arquivo SQLite": "SQLite file",
            "Exemplo:": "Example:",
            "ou apenas o caminho.": "or just the path.",
            "URL gerada (SQLAlchemy)": "Generated URL (SQLAlchemy)",
            "A URL abaixo será copiada para o campo \"URL manual\" automaticamente.": "The URL below will be copied to the \"Manual URL\" field automatically.",
            "URL de conexão (SQLAlchemy)": "Connection URL (SQLAlchemy)",
            "SQLite local:": "Local SQLite:",
            "Config (descriptografado)": "Config (decrypted)",
            "Copiar": "Copy",
            "Prévia do JSON que será criptografado ao salvar.": "Preview of the JSON that will be encrypted when saving.",
            "Opções avançadas": "Advanced options",
            "Schema padrão": "Default schema",
            "Schema usado por padrão nas consultas.": "Schema used by default in queries.",
            "Coluna tenant": "Tenant column",
            "Se preenchida, o SQL deve conter": "If filled, SQL must contain",
            "Testar conexão": "Test connection",
            "Salvar fonte": "Save source",
            "Salvar alterações": "Save changes",
            "Atualize a conexão e as opções avançadas.": "Update the connection and advanced options.",
            "Por segurança, a senha não é exibida. Se deixar vazio, manteremos a atual.": "For security, the password is not shown. If you leave it blank, we will keep the current one.",
            "(padrão)": "(default)",
            "URL SQLAlchemy (gerada)": "SQLAlchemy URL (generated)",
            "A URL abaixo também será salva no campo manual.": "The URL below will also be saved into the manual field.",
            "Caminho do arquivo (SQLite)": "File path (SQLite)",
            "Pode usar um caminho absoluto, relativo, ou uma URL": "You can use an absolute path, a relative path, or a URL",

            # JS feedback
            "Copiado.": "Copied.",
            "Falha ao copiar.": "Copy failed.",
            "Testando...": "Testing...",
            "Endpoint de teste não configurado.": "Test endpoint is not configured.",

            # Question messages
            "Preencha nome, fonte e SQL.": "Fill in name, data source, and SQL.",
            "Pergunta criada.": "Question created.",
            "Pergunta removida.": "Question removed.",

            # Dashboard messages
            "Dashboard criado.": "Dashboard created.",
            "Dashboard removido.": "Dashboard removed.",
            "Dashboard definido como principal.": "Dashboard set as primary.",
            "Operação não suportada: execute as migrações do banco para habilitar essa função.": "Operation not supported: run database migrations to enable this feature.",
            "Informe um nome.": "Enter a name.",

            # Configuration messages
            "Configuração inválida.": "Invalid configuration.",

            # User messages
            "Email e senha são obrigatórios.": "Email and password are required.",
            "Usuário criado.": "User created.",
            "Usuário removido.": "User removed.",

            # NLQ service messages
            "Não foi possível identificar uma tabela com segurança.": "Could not safely identify a table.",
            "Selecione uma tabela no Query Builder (à direita) ou escreva o SQL manualmente.": "Select a table in Query Builder (on the right) or write SQL manually.",
            "Tabela não identificada": "Table not identified",
            "Texto vazio": "Empty text",
            "Coluna métrica escolhida por fallback": "Metric column chosen by fallback",
            "Coluna métrica não identificada": "Metric column not identified",

            # Home page
            "O que já está no MVP": "What's already in the MVP",
            "Fontes por tenant (cadastro + introspecção)": "Data sources per tenant (registration + introspection)",
            "Editor SQL (execução ad-hoc com limites)": "SQL Editor (ad-hoc execution with limits)",
            "Perguntas (queries salvas) + execução": "Questions (saved queries) + execution",
            "Dashboards (cards simples com perguntas)": "Dashboards (simple cards with questions)",
            "Auditoria + Query Runs por tenant": "Audit + Query Runs per tenant",
            "Começar": "Getting Started",
            "Crie uma fonte": "Create a data source in Sources → New",
            "Introspecte metadados na fonte (botão 'Introspectar')": "Introspect metadata on the source (\"Introspect\" button)",
            "Teste uma consulta no Editor SQL": "Test a query in SQL Editor",
            "Salve uma Pergunta e crie um Dashboard": "Save a Question and create a Dashboard",
            "cadastro + introspecção": "registration + introspection",
            "execução ad-hoc com limites": "ad-hoc execution with limits",
            "queries salvas": "saved queries",
            "cards simples com perguntas": "simple cards with questions",
            "por tenant": "per tenant",
            "Nova": "New",
            "e crie um": "and create a",

            # Placeholder texts
            "Ex.: DW Produção": "Ex.: DW Production",
            "Ex.: postgresql+psycopg2://user:pass@host:5432/dbname": "Ex.: postgresql+psycopg2://user:pass@host:5432/dbname",
            "public": "public",
            "tenant_id": "tenant_id",
            "ex: total vendas por mês": "ex: total sales per month",
            "acme": "acme",
            "you@example.com": "you@example.com",
            "tenant slug (ex.: acme)": "tenant slug (ex.: acme)",
            "nome do tenant": "tenant name",
            "email do admin": "admin email",
            "senha": "password",
            "value": "value",
            "SELECT ...": "SELECT ...",

            # AI service prompts
            "You are a BI analyst": "You are a BI analyst",
            "You receive metadata and data sample": "You receive metadata and a data sample (columns/rows) from a SQL question",
            "Respond with clear insights": "Respond with clear insights, hypotheses, limitations, and suggest charts",
            "Your output MUST be valid JSON": "Your output MUST be valid JSON (no markdown, no code blocks) with these keys",
            "analysis key": "analysis: string (simple markdown allowed, but no HTML)",
            "charts key": "charts: list of objects {title: string, echarts_option: object}",
            "followups key": "followups: list of strings",
            "Use only the provided sample": "Use only the provided sample and profile; if something is missing, say so explicitly",
            "For charts generate safe ECharts": "For charts, generate safe ECharts options, without JS functions",
            "If insufficient data return empty": "If there is insufficient data, return charts=[] and explain in the analysis",



        # Auto-added i18n keys
        "Info": "Info",
        "Fechar": "Close",
        "Sucesso": "Success",

        "Relatórios": "Reports",
        "Novo relatório": "New report",
        "Construa relatórios com drag & drop (estilo Crystal Reports).": "Build reports with drag & drop (Crystal Reports style).",
        "Nenhum relatório criado ainda.": "No reports created yet.",
        "Abrir builder": "Open builder",
        "Arraste e solte": "Drag & drop",
        "Cabeçalho": "Header",
        "Corpo": "Body",
        "Rodapé": "Footer",
        "Editar": "Edit",
        "Remover": "Remove",
        "Título do bloco:": "Block title:",
        "Pergunta salva": "Saved question",
        "Falha ao salvar": "Save failed",
        "Arraste aqui...": "Drop here...",
        "Salvo": "Saved",
        "Pergunta #{n}": "Question #{n}",
        "Imagem": "Image",
        "Figura / logotipo / screenshot": "Figure / logo / screenshot",
        "Adicionar imagem": "Add image",
        "URL (https://...)": "URL (https://...)",
        "Isso cria um bloco “Imagem” no corpo do relatório.": "This creates an “Image” block in the report body.",
        "URL da imagem:": "Image URL:",
        "Texto alternativo (alt):": "Alt text:",
        "Legenda (opcional):": "Caption (optional):",
        "Largura (ex.: 300px ou 50%):": "Width (e.g., 300px or 50%):",
        "Alinhamento (left/center/right):": "Alignment (left/center/right):",
        "Cor do texto (ex.: #111 ou vazio):": "Text color (e.g., #111 or empty):",
        "Cor de fundo (ex.: #fff ou vazio):": "Background color (e.g., #fff or empty):",
        "Imagem não disponível": "Image not available",
        "Texto (Markdown):": "Text (Markdown):",
        "Texto:": "Text:",
        "Bloco": "Block",
        "Erro ao executar pergunta: {error}": "Failed to run question: {error}",
        "Editar bloco": "Edit block",
        "Título": "Title",
        "URL da imagem": "Image URL",
        "https://...": "https://...",
        "Texto alternativo (alt)": "Alt text (alt)",
        "Largura": "Width",
        "ex.: 300px ou 50%": "e.g., 300px or 50%",
        "Pré-visualização": "Preview",
        "Estilo": "Style",
        "Cor do texto": "Text color",
        "Cor de fundo": "Background color",
        "Sem": "None",
        "hex ou vazio": "hex or empty",
        "Aplicar": "Apply",
        "Esquerda": "Left",
        "Centro": "Center",
        "Direita": "Right",
        "Padrão": "Default",
        "ETL Builder": "ETL Builder",
        "ETLs": "ETLs",
        "Novo workflow": "New workflow",
        "Workflows salvos": "Saved workflows",
        "Salvar workflow": "Save workflow",
        "Nome do workflow": "Workflow name",
        "Salvar cria JSON + YAML quando o fluxo é válido.": "Saving creates JSON + YAML when the flow is valid.",
        "Conexões": "Connections",
        "Use o catálogo para selecionar DB/API. Credenciais são armazenadas criptografadas.": "Use the catalog to select DB/API. Credentials are stored encrypted.",
        "Nenhum workflow salvo.": "No saved workflows.",
        "Erro ao carregar.": "Failed to load.",
        "Abrir": "Open",
        "Nome": "Name",
        "Formato": "Format",
        "Ações": "Actions",
        "Adicionar passos": "Add steps",
        "Preview (últimos resultados)": "Preview (latest results)",
        "Dica: campos JSON devem ser um JSON válido (ex: {\"Authorization\":\"Bearer ...\"}).": "Tip: JSON fields must be valid JSON (e.g. {\"Authorization\":\"Bearer ...\"}).",
        "DB Sources": "DB Sources",
        "API Sources": "API Sources",
        "Use existing sources catalog. Click plug icon to test connection.": "Use existing sources catalog. Click plug icon to test connection.",

        # Workspaces (DuckDB + Files)
        "Novo workspace": "New workspace",
        "Workspace permite fazer JOIN entre arquivos (CSV/Excel/Parquet) e tabelas do banco, tudo em DuckDB.": "Workspaces let you JOIN files (CSV/Excel/Parquet) with database tables, all inside DuckDB.",
        "Configuração": "Configuration",
        "Fonte de banco (opcional)": "Database source (optional)",
        "sem banco": "no database",
        "Para JOIN com banco, selecione as tabelas. Elas ficam acessíveis como db.<tabela>.": "For DB joins, pick the tables. They are available as db.<table>.",
        "Tabelas do banco": "Database tables",
        "Selecionar tabelas": "Select tables",
        "Dica: use o Construtor rápido de JOIN para gerar um SQL inicial.": "Tip: use the Quick JOIN Builder to generate a starter SQL.",
        "Limite de linhas": "Row limit",
        "Usado para amostragem (segurança/performance).": "Used for sampling (safety/performance).",
        "Abrir File Explorer": "Open File Explorer",
        "Nenhum arquivo uploadado ainda. Use o menu Arquivos.": "No uploaded files yet. Use the Files menu.",
        "Filtrar arquivos…": "Filter files…",
        "Alias (tabela)": "Alias (table)",
        "Criar workspace": "Create workspace",
        "Construtor rápido de JOIN": "Quick JOIN Builder",
        "Selecione arquivos/tabelas e gere um SQL inicial com JOINs e autocomplete de colunas.": "Select files/tables and generate a starter SQL with JOINs and column autocomplete.",
        "Selecione arquivos/tabelas": "Select files/tables",
        "Tabela base": "Base table",
        "Sugestões de JOIN": "JOIN suggestions",
        "JOINs": "JOINs",
        "Adicionar JOIN": "Add JOIN",
        "Coluna": "Column",
        "Gerar SQL com IA": "Generate SQL with AI",
        "Descreva sua análise": "Describe your analysis",
        "SQL inicial": "Starter SQL",
        "Seu SQL aparecerá aqui…": "Your SQL will appear here…",
        "Ao criar o workspace, este SQL fica salvo como rascunho (starter_sql) para você copiar no Editor SQL.": "When you create the workspace, this SQL is saved as a draft (starter_sql) so you can copy it into the SQL Editor.",
        "Filtrar tabelas…": "Filter tables…",
        "Nenhuma tabela encontrada.": "No tables found.",
        "Selecione uma fonte de banco para listar tabelas.": "Select a database source to list tables.",
        "Falha ao carregar schema.": "Failed to load schema.",
        "Selecione pelo menos duas tabelas para sugerir joins.": "Select at least two tables to suggest joins.",
        "Nenhuma sugestão disponível.": "No suggestions available.",
        "SQL gerado.": "SQL generated.",
        "Falha ao gerar SQL.": "Failed to generate SQL.",
        "Schema: {name}": "Schema: {name}",
        "Ex.: BI - Vendas + Clientes": "e.g. BI - Sales + Customers",
        "Ex.: total de vendas por mês e segmento, com ticket médio": "e.g. total sales by month and segment, with average ticket",
        "Workspace criado.": "Workspace created.",
    },
    "fr": {
        # Public
        "Accueil": "Accueil",
        "À propos": "À propos",
        "Expertise": "Expertise",
        "Solutions": "Solutions",
        "Pourquoi AUDELA": "Pourquoi AUDELA",
        "Projets": "Projets",
        "Plans BI": "Plans BI",
        "Área BI": "Espace BI",
        "Contact": "Contact",
        "Mobile": "Mobile",
        "IoT & Neuro": "IoT & Neuro",
        "BI & Metabase": "BI & Metabase",
        "BeLegal (LegalTech)": "BeLegal (LegalTech)",
        "Tous droits réservés.": "Tous droits réservés.",

        # Index / landing
        "La technologie au service de la décision.": "La technologie au service de la décision.",
        "Data, BI, ERP, LegalTech & IA — au cœur de vos opérations.": "Data, BI, ERP, LegalTech & IA — au cœur de vos opérations.",
        "Illustration AUDELA": "Illustration AUDELA",
        "Next": "Suivant",
        "Grenoble & Alpes": "Grenoble & Alpes",
        "Au-delà des données": "Au-delà des données",
        "Transformer l'information en décisions — avec une ingénierie logicielle robuste et une compréhension métier réelle.": "Transformer l'information en décisions — avec une ingénierie logicielle robuste et une compréhension métier réelle.",
        "Nous construisons des systèmes qui tiennent dans la durée : pipelines data industrialisés, APIs fiables, applications web et mobile, et des dashboards compréhensibles par les équipes terrain comme par la direction.": "Nous construisons des systèmes qui tiennent dans la durée : pipelines data industrialisés, APIs fiables, applications web et mobile, et des dashboards compréhensibles par les équipes terrain comme par la direction.",
        "Notre approche est pragmatique et \"production-first\" : sécurité, performance, observabilité, documentation, et transfert de compétences. L'objectif : livrer vite, sans dette technique.": "Notre approche est pragmatique et \"production-first\" : sécurité, performance, observabilité, documentation, et transfert de compétences. L'objectif : livrer vite, sans dette technique.",
        "Business Intelligence": "Business Intelligence",
        "Analyse de données & Business Intelligence": "Analyse de données & Business Intelligence",
        "Ingestion, modélisation, qualité et exposition : des indicateurs fiables, traçables et actionnables.": "Ingestion, modélisation, qualité et exposition : des indicateurs fiables, traçables et actionnables.",
        "Nous connectons vos systèmes (ERP, CRM, finance, opérations, APIs), structurons la donnée (DWH/ELT), et livrons des tableaux de bord qui répondent à des questions concrètes : marge, performance commerciale, délais, risques, conformité.": "Nous connectons vos systèmes (ERP, CRM, finance, opérations, APIs), structurons la donnée (DWH/ELT), et livrons des tableaux de bord qui répondent à des questions concrètes : marge, performance commerciale, délais, risques, conformité.",
        "Voir les écrans Metabase": "Voir les écrans Metabase",
        "Plateformes métiers": "Plateformes métiers",
        "Plateformes métiers, ERP & IA appliquée": "Plateformes métiers, ERP & IA appliquée",
        "Des outils métier qui reflètent vos workflows, avec une IA utile et explicable.": "Des outils métier qui reflètent vos workflows, avec une IA utile et explicable.",
        "Découvrir BeLegal": "Découvrir BeLegal",

        # Home page
        "O que já está no MVP": "Ce qui est déjà dans le MVP",
        "Fontes por tenant (cadastro + introspecção)": "Sources de données par locataire (enregistrement + introspection)",
        "Editor SQL (execução ad-hoc com limites)": "Éditeur SQL (exécution ad-hoc avec limites)",
        "Perguntas (queries salvas) + execução": "Questions (requêtes enregistrées) + exécution",
        "Dashboards (cards simples com perguntas)": "Tableaux de bord (cartes simples avec questions)",
        "Auditoria + Query Runs por tenant": "Audit + Exécutions de requêtes par locataire",
        "Começar": "Commencer",
        "Crie uma fonte": "Créez une source de données dans Sources → Nouvelle",
        "Introspecte metadados na fonte (botão 'Introspectar')": "Introspectez les métadonnées sur la source (bouton \"Introspect\")",
        "Teste uma consulta no Editor SQL": "Testez une requête dans l'Éditeur SQL",
        "Salve uma Pergunta e crie um Dashboard": "Enregistrez une Question et créez un Tableau de bord",
        "cadastro + introspecção": "enregistrement + introspection",
        "execução ad-hoc com limites": "exécution ad-hoc avec limites",
        "queries salvas": "requêtes enregistrées",
        "cards simples com perguntas": "cartes simples avec questions",
        "por tenant": "par locataire",
        "Nova": "Nouvelle",
        "e crie um": "et créez un",

        # Portal
        "Portal BI": "Portail BI",

        # Excel AI
        "Excel IA": "Excel IA",
        "Exportar XLSX": "Exporter XLSX",
        "Gerar XLSX": "Générer XLSX",
        "Gerando...": "Génération...",
        "Arquivo gerado.": "Fichier généré.",
        "Prompt vazio.": "Requête vide.",
        "Gere um arquivo Excel (XLSX) a partir de uma pergunta em linguagem natural.": "Générez un fichier Excel (XLSX) à partir d’une requête en langage naturel.",
        "Salvar em Arquivos": "Enregistrer dans Fichiers",
        "Raiz": "Racine",
        "Adicionar gráfico automático (se possível)": "Ajouter un graphique automatique (si possible)",
        "Pedido (linguagem natural)": "Demande (langage naturel)",
        "Título do arquivo": "Titre du fichier",
        "Limite de linhas": "Limite de lignes",
        "Observação: o arquivo é baixado no navegador e (opcionalmente) salvo no módulo Arquivos.": "Remarque : le fichier est téléchargé dans le navigateur et (optionnellement) enregistré dans le module Fichiers.",
        "Exemplos de pedidos": "Exemples de demandes",
        "Dica: especifique datas, filtros e como quer ordenar (ex.: \"top 10\").": "Astuce : précisez dates, filtres et ordre souhaité (ex. « top 10 »).",
        "Ex.: Vendas e Top Produtos": "Ex. : Ventes et Top produits",
        "Ex.: criar um Excel com uma tabela de vendas por mês e um gráfico com os 10 produtos mais vendidos": "Ex. : créer un Excel avec un tableau des ventes par mois et un graphique des 10 produits les plus vendus",
        "Usuário": "Utilisateur",
        "Sair": "Déconnexion",
        "Home": "Accueil",
        "Fontes": "Sources",
        "Metadados": "Métadonnées",
        "Editor SQL": "Éditeur SQL",
        "Query Builder": "Constructeur de requêtes",
        "Perguntas": "Questions",
        "Dashboards": "Tableaux de bord",
        "Execuções": "Exécutions",
        "Auditoria": "Audit",
        "Voltar": "Retour",
        "Cancelar": "Annuler",
        "Salvar": "Enregistrer",
        "Executar": "Exécuter",
        "Resultado": "Résultat",
        "Erro": "Erreur",
        "Linhas": "Lignes",
        "Linhas retornadas": "Lignes retournées",
        "Nova pergunta": "Nouvelle question",
        "Nova fonte": "Nouvelle source",
        "Criar": "Créer",
        "Dashboard": "Tableau de bord",
        "Nenhum card ainda. Crie um dashboard escolhendo perguntas.": "Aucune carte pour le moment. Créez un tableau de bord en choisissant des questions.",
        "Exportar PDF": "Exporter en PDF",
        "Limpar filtros": "Effacer les filtres",
        "Filtros": "Filtres",
        "Adicionar filtro": "Ajouter un filtre",
        "Visualização": "Visualisation",
        "Configurar visualização": "Configurer la visualisation",
        "Prévia": "Aperçu",
        "Tipo": "Type",
        "Tabela": "Table",
        "Gráfico": "Graphique",
        "Pivot": "Pivot",
        "Gauges": "Jauges",
        "Drill down": "Exploration",
        "Exportar": "Exporter",
        "Gerar SQL": "Générer SQL",
        "Linguagem humana": "Langage naturel",
        "Gerar": "Générer",
        "Tabelas": "Tables",
        "Colunas": "Colonnes",
        "Executar pergunta": "Exécuter la question",
        "Parâmetros (JSON)": "Paramètres (JSON)",
        "Use :nome_param no SQL e preencha valores aqui. tenant_id é aplicado automaticamente.": "Utilisez :nom_param dans le SQL et renseignez les valeurs ici. tenant_id est appliqué automatiquement.",
        "Gerar SQL no editor": "Générer SQL dans l’éditeur",
        "Fonte de dados": "Source de données",
        "Estrutura": "Schéma",
        "Limite": "Limite",
        "montar SELECT com ajuda da estrutura": "construire un SELECT avec l’aide du schéma",
        "Escolha uma fonte para ver tabelas e colunas (autocomplete).": "Choisissez une source pour voir tables et colonnes (autocomplétion).",
        "Execute consultas ad-hoc, com autocomplete, Query Builder e linguagem humana.": "Exécutez des requêtes ad hoc avec autocomplétion, constructeur de requêtes et langage naturel.",
        "Sem linhas retornadas.": "Aucune ligne retournée.",

        # UI+AI
        "Editar layout": "Éditer la mise en page",
        "Salvar layout": "Enregistrer la mise en page",
        "Cancelar edição": "Annuler l’édition",
        "Layout salvo.": "Mise en page enregistrée.",
        "Falha ao salvar layout.": "Échec de l’enregistrement de la mise en page.",
        "Modo edição": "Mode édition",
        "IA": "IA",
        "Chat IA": "Chat IA",
        "Pergunte sobre os dados": "Interroger les données",
        "Selecione uma pergunta": "Sélectionnez une question",
        "Enviar": "Envoyer",
        "Mensagem": "Message",
        "Histórico": "Historique",
        "Limpar chat": "Effacer le chat",
        "Gerando resposta...": "Génération de la réponse…",
        "Análise": "Analyse",
        "Gráficos sugeridos": "Graphiques suggérés",
        "Sugestões de follow-up": "Suggestions de suivi",
        "Chave OpenAI ausente. Defina OPENAI_API_KEY no servidor.": "Clé OpenAI manquante. Définissez OPENAI_API_KEY sur le serveur.",
        "Erro ao chamar IA: {error}": "Erreur d’appel IA : {error}",
        "Tema": "Thème",
        "Claro": "Clair",
        "Escuro": "Sombre",
        "Explorar": "Explorer",
        "Explore dados e crie visualizações como no Superset/Metabase.": "Explorez les données et créez des visualisations comme Superset/Metabase.",
        "Adicionar card": "Ajouter une carte",
        "Remover card": "Supprimer la carte",
        "Buscar pergunta": "Rechercher une question",
        "Digite para filtrar...": "Tapez pour filtrer…",
        "Você pode refinar depois em Configurar visualização.": "Vous pourrez affiner ensuite dans Configurer la visualisation.",
        "Atualizar": "Actualiser",
        "Salvar visualização": "Enregistrer la visualisation",
        "Visualização salva.": "Visualisation enregistrée.",
        "Adicionar ao dashboard": "Ajouter au dashboard",
        "Cria um card no dashboard com esta visualização.": "Crée une carte dans le dashboard avec cette visualisation.",
        "Card adicionado ao dashboard.": "Carte ajoutée au dashboard.",
        "Card criado. Recarregando...": "Carte créée. Rechargement…",
        "Criando card...": "Création de la carte…",
        "Remover card?": "Supprimer la carte ?",
        "Sem filtros.": "Aucun filtre.",
        "Campo": "Champ",
        "Dimensão": "Dimension",
        "Métrica": "Mesure",
        "Drill-down": "Drill-down",
        "Clique no gráfico para filtrar por um valor.": "Cliquez sur le graphique pour filtrer par une valeur.",
        "Pivot linhas": "Lignes pivot",
        "Pivot colunas": "Colonnes pivot",
        "Pivot valor": "Valeur pivot",
        "Visuels & cas d’usage : Data, IA, ERP": "Visuels & cas d’usage : Data, IA, ERP",
        "Un aperçu des types de solutions que nous concevons : pilotage, automatisation et intelligence appliquée.": "Un aperçu des types de solutions que nous concevons : pilotage, automatisation et intelligence appliquée.",
        "Data & BI": "Data & BI",
        "Tableaux de bord exécutifs, KPIs, gouvernance, qualité et traçabilité de bout en bout.": "Tableaux de bord exécutifs, KPIs, gouvernance, qualité et traçabilité de bout en bout.",
        "IA appliquée": "IA appliquée",
        "Détection d'anomalies, scoring de risques, assistants métiers et analyse prédictive.": "Détection d'anomalies, scoring de risques, assistants métiers et analyse prédictive.",
        "ERP & workflows": "ERP & workflows",
        "Workflows métiers, intégrations SI, automatisation, contrôles et auditabilité.": "Workflows métiers, intégrations SI, automatisation, contrôles et auditabilité.",
        "LegalTech": "LegalTech",
        "Gestion des dossiers, rentabilité par affaire, génération documentaire, conformité.": "Gestion des dossiers, rentabilité par affaire, génération documentaire, conformité.",
        "Pourquoi AUDELA": "Pourquoi AUDELA",
        "Une expertise de fond, une exécution rigoureuse, et une obsession de la qualité en production.": "Une expertise de fond, une exécution rigoureuse, et une obsession de la qualité en production.",
        "Cloud-native, API-first, intégrations propres : une base solide pour durer et évoluer.": "Cloud-native, API-first, intégrations propres : une base solide pour durer et évoluer.",
        "Conformité et gouvernance : contrôles d’accès, traçabilité, et bonnes pratiques SI.": "Conformité et gouvernance : contrôles d’accès, traçabilité, et bonnes pratiques SI.",
        "Pipelines & qualité : de la source au tableau de bord, sans compromis sur les données.": "Pipelines & qualité : de la source au tableau de bord, sans compromis sur les données.",
        "CI/CD, monitoring, logs & alerting : stabilité, performance et mises en production rapides.": "CI/CD, monitoring, logs & alerting : stabilité, performance et mises en production rapides.",
        "Interopérabilité : connexion ERP/CRM/outils métiers, synchronisation et automatisation.": "Interopérabilité : connexion ERP/CRM/outils métiers, synchronisation et automatisation.",
        "Delivery et transfert : cadrage, documentation et montée en compétence de vos équipes.": "Delivery et transfert : cadrage, documentation et montée en compétence de vos équipes.",
        "Découvrir nos plans BI": "Découvrir nos plans BI",
        "Parlons de votre projet": "Parlons de votre projet",
        "Décrivez votre besoin (Data/BI, ERP, LegalTech, IA, Mobile, IoT). Nous vous recontactons rapidement.": "Décrivez votre besoin (Data/BI, ERP, LegalTech, IA, Mobile, IoT). Nous vous recontactons rapidement.",
        "Votre adresse e-mail": "Votre adresse e-mail",
        "Être rappelé": "Être rappelé",
        "Carregando...": "Chargement…",
        "OK": "OK",

        # Source diagram module
        "Source Diagram": "Diagramme source",
        "Select data source": "Sélectionnez la source de données",
        "Load diagram": "Charger le diagramme",
        "Refresh": "Rafraîchir",
        "Click a node to highlight relations. Use mousewheel to zoom.": "Cliquez sur un nœud pour mettre en évidence les relations. Utilisez la molette pour zoomer.",

        # Auth messages
        "Tenant não encontrado.": "Tenant non trouvé.",
        "Credenciais inválidas.": "Identifiants invalides.",
        "Preencha todos os campos.": "Veuillez remplir tous les champs.",
        "Slug já existe.": "Le slug existe déjà.",
        "Tenant criado. Faça login.": "Tenant créé. Veuillez vous connecter.",

        # Data source messages
        "Preencha nome, tipo e URL de conexão.": "Veuillez remplir le nom, le type et l'URL de connexion.",
        "Fonte criada.": "Source de données créée.",
        "Fonte removida.": "Source de données supprimée.",
        "Falha ao introspectar: {error}": "Introspection échouée : {error}",
        "Selecione uma fonte válida.": "Sélectionnez une source de données valide.",
        "Selecione uma fonte.": "Sélectionnez une source de données.",
        "Fonte inválida.": "Source de données invalide.",

        # Data source test + form (wizard)
        "Informe uma URL de conexão.": "Veuillez fournir une URL de connexion.",
        "Conexão OK.": "Connexion OK.",
        "Falha na conexão.": "Échec de la connexion.",
        "Falha na conexão: {error}": "Échec de la connexion : {error}",
        "Nova fonte de dados": "Nouvelle source de données",
        "Configure uma nova origem de dados para consultas e relatórios.": "Configurez une nouvelle source de données pour les requêtes et les rapports.",
        "Informações básicas": "Informations de base",
        "Ex.: DW Produção": "Ex. : Entrepôt de production",
        "Nome interno para identificar a fonte.": "Nom interne pour identifier la source.",
        "Tipo de banco": "Type de base de données",
        "Conexão": "Connexion",
        "Assistente": "Assistant",
        "URL manual": "URL manuelle",
        "URL (manual)": "URL (manuelle)",
        "Porta": "Port",
        "Database": "Base de données",
        "Senha": "Mot de passe",
        "(opcional)": "(optionnel)",
        "(deixe vazio para manter)": "(laissez vide pour conserver)",
        "Fica criptografado no config. Se preferir, cole uma URL pronta no modo \"URL manual\".": "Stocké chiffré dans la config. Si vous préférez, collez une URL prête en mode \"URL manuelle\".",
        "Driver (SQL Server)": "Pilote (SQL Server)",
        "Service Name (Oracle)": "Service Name (Oracle)",
        "SID (Oracle)": "SID (Oracle)",
        "Arquivo SQLite": "Fichier SQLite",
        "Exemplo:": "Exemple :",
        "ou apenas o caminho.": "ou seulement le chemin.",
        "URL gerada (SQLAlchemy)": "URL générée (SQLAlchemy)",
        "A URL abaixo será copiada para o campo \"URL manual\" automaticamente.": "L'URL ci-dessous sera copiée automatiquement dans le champ \"URL manuelle\".",
        "URL de conexão (SQLAlchemy)": "URL de connexion (SQLAlchemy)",
        "SQLite local:": "SQLite local :",
        "Config (descriptografado)": "Config (déchiffrée)",
        "Copiar": "Copier",
        "Prévia do JSON que será criptografado ao salvar.": "Aperçu du JSON qui sera chiffré lors de l'enregistrement.",
        "Opções avançadas": "Options avancées",
        "Schema padrão": "Schéma par défaut",
        "Schema usado por padrão nas consultas.": "Schéma utilisé par défaut dans les requêtes.",
        "Coluna tenant": "Colonne tenant",
        "Se preenchida, o SQL deve conter": "Si renseigné, le SQL doit contenir",
        "Testar conexão": "Tester la connexion",
        "Salvar fonte": "Enregistrer la source",
        "Salvar alterações": "Enregistrer les modifications",
        "Atualize a conexão e as opções avançadas.": "Mettez à jour la connexion et les options avancées.",
        "Por segurança, a senha não é exibida. Se deixar vazio, manteremos a atual.": "Pour des raisons de sécurité, le mot de passe n'est pas affiché. Si vous laissez vide, nous conserverons l'actuel.",
        "(padrão)": "(par défaut)",
        "URL SQLAlchemy (gerada)": "URL SQLAlchemy (générée)",
        "A URL abaixo também será salva no campo manual.": "L'URL ci-dessous sera également enregistrée dans le champ manuel.",
        "Caminho do arquivo (SQLite)": "Chemin du fichier (SQLite)",
        "Pode usar um caminho absoluto, relativo, ou uma URL": "Vous pouvez utiliser un chemin absolu, relatif, ou une URL",

        # JS feedback
        "Copiado.": "Copié.",
        "Falha ao copiar.": "Échec de la copie.",
        "Testando...": "Test en cours…",
        "Endpoint de teste não configurado.": "Point de terminaison de test non configuré.",

        # Question messages
        "Preencha nome, fonte e SQL.": "Veuillez remplir le nom, la source et le SQL.",
        "Pergunta criada.": "Question créée.",
        "Pergunta removida.": "Question supprimée.",

        # Dashboard messages
        "Dashboard criado.": "Tableau de bord créé.",
        "Dashboard removido.": "Tableau de bord supprimé.",
        "Dashboard definido como principal.": "Tableau de bord défini comme principal.",
        "Operação não suportada: execute as migrações do banco para habilitar essa função.": "Opération non supportée : exécutez les migrations de la base de données pour activer cette fonction.",
        "Informe um nome.": "Veuillez entrer un nom.",

        # Configuration messages
        "Configuração inválida.": "Configuration invalide.",

        # User messages
        "Email e senha são obrigatórios.": "L'e-mail et le mot de passe sont obligatoires.",
        "Usuário criado.": "Utilisateur créé.",
        "Usuário removido.": "Utilisateur supprimé.",

        # NLQ service messages
        "Não foi possível identificar uma tabela com segurança.": "Impossible d'identifier une table en toute sécurité.",
        "Selecione uma tabela no Query Builder (à direita) ou escreva o SQL manualmente.": "Sélectionnez une table dans le Constructeur de requêtes (à droite) ou écrivez le SQL manuellement.",
        "Tabela não identificada": "Table non identifiée",
        "Texto vazio": "Texte vide",
        "Coluna métrica escolhida por fallback": "Colonne de métrique choisie par défaut",
        "Coluna métrica não identificada": "Colonne de métrique non identifiée",

        # Home page
        "O que já está no MVP": "Ce qui est déjà dans le MVP",
        "Fontes por tenant (cadastro + introspecção)": "Sources de données par locataire (enregistrement + introspection)",
        "Editor SQL (execução ad-hoc com limites)": "Éditeur SQL (exécution ad-hoc avec limites)",
        "Perguntas (queries salvas) + execução": "Questions (requêtes enregistrées) + exécution",
        "Dashboards (cards simples com perguntas)": "Tableaux de bord (cartes simples avec questions)",
        "Auditoria + Query Runs por tenant": "Audit + Exécutions de requêtes par locataire",
        "Começar": "Commencer",
        "Crie uma fonte": "Créez une source de données dans Sources → Nouvelle",
        "Introspecte metadados na fonte (botão 'Introspectar')": "Introspectez les métadonnées sur la source (bouton \"Introspect\")",
        "Teste uma consulta no Editor SQL": "Testez une requête dans l'Éditeur SQL",
        "Salve uma Pergunta e crie um Dashboard": "Enregistrez une Question et créez un Tableau de bord",

        # Placeholder texts
        "Ex.: DW Produção": "Ex. : DW Production",
        "Ex.: postgresql+psycopg2://user:pass@host:5432/dbname": "Ex. : postgresql+psycopg2://user:pass@host:5432/dbname",
        "public": "public",
        "tenant_id": "tenant_id",
        "ex: total vendas por mês": "ex : ventes totales par mois",
        "acme": "acme",
        "you@example.com": "you@example.com",
        "tenant slug (ex.: acme)": "slug du tenant (ex. : acme)",
        "nome do tenant": "nom du tenant",
        "email do admin": "e-mail de l'administrateur",
        "senha": "mot de passe",
        "value": "valeur",
        "SELECT ...": "SELECT ...",

        # AI service prompts
        "You are a BI analyst": "Vous êtes un analyste BI",
        "You receive metadata and data sample": "Vous recevez des métadonnées et un exemple de données (colonnes/lignes) d'une question SQL",
        "Respond with clear insights": "Répondez avec des aperçus clairs, des hypothèses, des limitations et suggérez des graphiques",
        "Your output MUST be valid JSON": "Votre sortie DOIT être un JSON valide (pas de markdown, pas de blocs de code) avec ces clés",
        "analysis key": "analysis: string (markdown simple autorisé, mais pas de HTML)",
        "charts key": "charts: liste d'objets {title: string, echarts_option: object}",
        "followups key": "followups: liste de strings",
        "Use only the provided sample": "Utilisez uniquement l'exemple et le profil fournis ; s'il manque quelque chose, dites-le explicitement",
        "For charts generate safe ECharts": "Pour les graphiques, générez des options ECharts sûres, sans fonctions JS",
        "If insufficient data return empty": "S'il n'y a pas assez de données, retournez charts=[] et expliquez dans l'analysis",


        "Relatórios": "Rapports",
        "Novo relatório": "Nouveau rapport",
        "Construa relatórios com drag & drop (estilo Crystal Reports).": "Construisez des rapports en glisser-déposer (style Crystal Reports).",
        "Nenhum relatório criado ainda.": "Aucun rapport créé pour le moment.",
        "Abrir builder": "Ouvrir le builder",
        "Arraste e solte": "Glisser-déposer",
        "Cabeçalho": "En-tête",
        "Corpo": "Corps",
        "Rodapé": "Pied de page",
        "Editar": "Modifier",
        "Remover": "Supprimer",
        "Título do bloco:": "Titre du bloc :",
        "Pergunta salva": "Question enregistrée",
        "Falha ao salvar": "Échec de l'enregistrement",
        "Arraste aqui...": "Déposez ici...",
        "Salvo": "Enregistré",
        "Pergunta #{n}": "Question #{n}",
        "Fechar": "Fermer",
        "Sucesso": "Succès",
        "Info": "Info",
        "Imagem": "Image",
        "Figura / logotipo / screenshot": "Figure / logo / capture d’écran",
        "Adicionar imagem": "Ajouter une image",
        "URL (https://...)": "URL (https://...)",
        "Isso cria um bloco “Imagem” no corpo do relatório.": "Cela crée un bloc « Image » dans le corps du rapport.",
        "URL da imagem:": "URL de l’image :",
        "Texto alternativo (alt):": "Texte alternatif (alt) :",
        "Legenda (opcional):": "Légende (optionnelle) :",
        "Largura (ex.: 300px ou 50%):": "Largeur (ex. : 300px ou 50%) :",
        "Alinhamento (left/center/right):": "Alignement (left/center/right) :",
        "Cor do texto (ex.: #111 ou vazio):": "Couleur du texte (ex. : #111 ou vide) :",
        "Cor de fundo (ex.: #fff ou vazio):": "Couleur de fond (ex. : #fff ou vide) :",
        "Imagem não disponível": "Image indisponible",
        "Texto (Markdown):": "Texte (Markdown) :",
        "Texto:": "Texte :",
        "Bloco": "Bloc",
        "Erro ao executar pergunta: {error}": "Erreur lors de l’exécution de la question : {error}",
        "Editar bloco": "Modifier le bloc",
        "Título": "Titre",
        "URL da imagem": "URL de l'image",
        "https://...": "https://...",
        "Texto alternativo (alt)": "Texte alternatif (alt)",
        "Largura": "Largeur",
        "ex.: 300px ou 50%": "ex. : 300px ou 50%",
        "Pré-visualização": "Aperçu",
        "Estilo": "Style",
        "Cor do texto": "Couleur du texte",
        "Cor de fundo": "Couleur de fond",
        "Sem": "Aucun",
        "hex ou vazio": "hex ou vide",
        "Aplicar": "Appliquer",
        "Esquerda": "Gauche",
        "Centro": "Centre",
        "Direita": "Droite",
        "Padrão": "Par défaut",
        "ETL Builder": "Constructeur ETL",
        "ETLs": "ETLs",
        "Novo workflow": "Nouveau workflow",
        "Workflows salvos": "Workflows sauvegardés",
        "Salvar workflow": "Sauvegarder le workflow",
        "Nome do workflow": "Nom du workflow",
        "Salvar cria JSON + YAML quando o fluxo é válido.": "La sauvegarde crée un JSON + YAML lorsque le flux est valide.",
        "Conexões": "Connexions",
        "Use o catálogo para selecionar DB/API. Credenciais são armazenadas criptografadas.": "Utilisez le catalogue pour sélectionner DB/API. Les identifiants sont stockés chiffrés.",
        "Nenhum workflow salvo.": "Aucun workflow sauvegardé.",
        "Erro ao carregar.": "Erreur de chargement.",
        "Abrir": "Ouvrir",
        "Nome": "Nom",
        "Formato": "Format",
        "Ações": "Actions",
        "Preview": "Aperçu",
        "Adicionar passos": "Ajouter des étapes",
        "Preview (últimos resultados)": "Aperçu (derniers résultats)",
        "Dica: campos JSON devem ser um JSON válido (ex: {\"Authorization\":\"Bearer ...\"}).": "Astuce : les champs JSON doivent être un JSON valide (ex : {\"Authorization\":\"Bearer ...\"}).",
        "DB Sources": "Sources DB",
        "API Sources": "Sources API",
        "Use existing sources catalog. Click plug icon to test connection.": "Utilisez les sources existantes. Cliquez sur la prise pour tester la connexion.",

        # Workspaces (DuckDB + Files)
        "Novo workspace": "Nouveau workspace",
        "Workspace permite fazer JOIN entre arquivos (CSV/Excel/Parquet) e tabelas do banco, tudo em DuckDB.": "Les workspaces permettent de faire des JOIN entre des fichiers (CSV/Excel/Parquet) et des tables de base de données, le tout dans DuckDB.",
        "Configuração": "Configuration",
        "Fonte de banco (opcional)": "Source de base (optionnelle)",
        "sem banco": "sans base",
        "Para JOIN com banco, selecione as tabelas. Elas ficam acessíveis como db.<tabela>.": "Pour joindre avec la base, sélectionnez les tables. Elles sont accessibles comme db.<table>.",
        "Tabelas do banco": "Tables de la base",
        "Selecionar tabelas": "Sélectionner des tables",
        "Dica: use o Construtor rápido de JOIN para gerar um SQL inicial.": "Astuce : utilisez le Constructeur rapide de JOIN pour générer un SQL de départ.",
        "Limite de linhas": "Limite de lignes",
        "Usado para amostragem (segurança/performance).": "Utilisé pour l'échantillonnage (sécurité/performance).",
        "Abrir File Explorer": "Ouvrir l'explorateur de fichiers",
        "Nenhum arquivo uploadado ainda. Use o menu Arquivos.": "Aucun fichier uploadé pour le moment. Utilisez le menu Fichiers.",
        "Filtrar arquivos…": "Filtrer les fichiers…",
        "Alias (tabela)": "Alias (table)",
        "Criar workspace": "Créer le workspace",
        "Construtor rápido de JOIN": "Constructeur rapide de JOIN",
        "Selecione arquivos/tabelas e gere um SQL inicial com JOINs e autocomplete de colunas.": "Sélectionnez fichiers/tables et générez un SQL de départ avec JOINs et auto-complétion des colonnes.",
        "Selecione arquivos/tabelas": "Sélectionnez fichiers/tables",
        "Tabela base": "Table de base",
        "Sugestões de JOIN": "Suggestions de JOIN",
        "JOINs": "JOINs",
        "Adicionar JOIN": "Ajouter un JOIN",
        "Coluna": "Colonne",
        "Gerar SQL com IA": "Générer du SQL avec l'IA",
        "Descreva sua análise": "Décrivez votre analyse",
        "SQL inicial": "SQL de départ",
        "Seu SQL aparecerá aqui…": "Votre SQL apparaîtra ici…",
        "Ao criar o workspace, este SQL fica salvo como rascunho (starter_sql) para você copiar no Editor SQL.": "Lors de la création du workspace, ce SQL est enregistré comme brouillon (starter_sql) afin que vous puissiez le copier dans l'Éditeur SQL.",
        "Filtrar tabelas…": "Filtrer les tables…",
        "Nenhuma tabela encontrada.": "Aucune table trouvée.",
        "Selecione uma fonte de banco para listar tabelas.": "Sélectionnez une source de base pour lister les tables.",
        "Falha ao carregar schema.": "Échec du chargement du schéma.",
        "Selecione pelo menos duas tabelas para sugerir joins.": "Sélectionnez au moins deux tables pour suggérer des JOINs.",
        "Nenhuma sugestão disponível.": "Aucune suggestion disponible.",
        "SQL gerado.": "SQL généré.",
        "Falha ao gerar SQL.": "Échec de génération du SQL.",
        "Schema: {name}": "Schéma : {name}",
        "Ex.: BI - Vendas + Clientes": "Ex. : BI - Ventes + Clients",
        "Ex.: total de vendas por mês e segmento, com ticket médio": "Ex. : total des ventes par mois et segment, avec ticket moyen",
        "Workspace criado.": "Workspace créé.",
    },
    "es": {
        "Accueil": "Inicio",
        "À propos": "Acerca de",
        "Expertise": "Experiencia",
        "Solutions": "Soluciones",
        "Pourquoi AUDELA": "Por qué AUDELA",
        "Projets": "Proyectos",
        "Plans BI": "Planes BI",
        "Área BI": "Área BI",
        "Contact": "Contacto",
        "Mobile": "Móvil",
        "IoT & Neuro": "IoT & Neuro",
        "BI & Metabase": "BI & Metabase",
        "BeLegal (LegalTech)": "BeLegal (LegalTech)",
        "Tous droits réservés.": "Todos los derechos reservados.",

        # Index / landing
        "La technologie au service de la décision.": "La tecnología al servicio de la decisión.",
        "Data, BI, ERP, LegalTech & IA — au cœur de vos opérations.": "Data, BI, ERP, LegalTech & IA — en el corazón de sus operaciones.",
        "Illustration AUDELA": "Ilustración AUDELA",
        "Next": "Siguiente",
        "Grenoble & Alpes": "Grenoble & Alpes",
        "Au-delà des données": "Más allá de los datos",
        "Transformer l'information en décisions — avec une ingénierie logicielle robuste et une compréhension métier réelle.": "Convertir la información en decisiones — con ingeniería de software robusta y comprensión real del negocio.",
        "Nous construisons des systèmes qui tiennent dans la durée : pipelines data industrialisés, APIs fiables, applications web et mobile, et des dashboards compréhensibles par les équipes terrain comme par la direction.": "Construimos sistemas que perduran: pipelines de datos industrializados, APIs fiables, aplicaciones web y móviles, y dashboards comprensibles por equipos de campo y dirección.",
        "Notre approche est pragmatique et \"production-first\" : sécurité, performance, observabilité, documentation, et transfert de compétences. L'objectif : livrer vite, sans dette technique.": "Nuestro enfoque es pragmático y production-first: seguridad, rendimiento, observabilidad, documentación y transferencia de conocimientos. Objetivo: entregar rápido, sin deuda técnica.",
        "Business Intelligence": "Inteligencia de negocios",
        "Analyse de données & Business Intelligence": "Análisis de datos e Inteligencia de negocios",
        "Ingestion, modélisation, qualité et exposition : des indicateurs fiables, traçables et actionnables.": "Ingesta, modelado, calidad y exposición: indicadores confiables, trazables y accionables.",
        "Nous connectons vos systèmes (ERP, CRM, finance, opérations, APIs), structurons la donnée (DWH/ELT), et livrons des tableaux de bord qui répondent à des questions concrètes : marge, performance commerciale, délais, risques, conformité.": "Conectamos sus sistemas (ERP, CRM, finanzas, operaciones, APIs), estructuramos los datos (DWH/ELT) y entregamos dashboards que responden a preguntas concretas: margen, rendimiento comercial, plazos, riesgos, cumplimiento.",
        "Voir les écrans Metabase": "Ver las pantallas de Metabase",
        "Plateformes métiers": "Plataformas empresariales",
        "Plateformes métiers, ERP & IA appliquée": "Plataformas empresariales, ERP e IA aplicada",
        "Des outils métier qui reflètent vos workflows, avec une IA utile et explicable.": "Herramientas empresariales que reflejan sus flujos de trabajo, con IA útil y explicable.",
        "Découvrir BeLegal": "Descubrir BeLegal",

        # Home page
        "O que já está no MVP": "Lo que ya está en el MVP",
        "Fontes por tenant (cadastro + introspecção)": "Fuentes de datos por inquilino (registro + introspección)",
        "Editor SQL (execução ad-hoc com limites)": "Editor SQL (ejecución ad-hoc con límites)",
        "Perguntas (queries salvas) + execução": "Preguntas (consultas guardadas) + ejecución",
        "Dashboards (cards simples com perguntas)": "Paneles (tarjetas simples con preguntas)",
        "Auditoria + Query Runs por tenant": "Auditoría + Ejecuciones de consultas por inquilino",
        "Começar": "Primeros pasos",
        "Crie uma fonte": "Cree una fuente de datos en Fuentes → Nueva",
        "Introspecte metadados na fonte (botão 'Introspectar')": "Introspeccione metadatos en la fuente (botón \"Introspect\")",
        "Teste uma consulta no Editor SQL": "Pruebe una consulta en el Editor SQL",
        "Salve uma Pergunta e crie um Dashboard": "Guarde una Pregunta y cree un Panel",
        "cadastro + introspecção": "registro + introspección",
        "execução ad-hoc com limites": "ejecución ad-hoc con límites",
        "queries salvas": "consultas guardadas",
        "cards simples com perguntas": "tarjetas simples con preguntas",
        "por tenant": "por inquilino",
        "Nova": "Nueva",
        "e crie um": "y cree un",

        "Portal BI": "Portal BI",
        "Usuário": "Usuario",
        "Sair": "Salir",
        "Home": "Inicio",
        "Fontes": "Fuentes",
        "Metadados": "Metadatos",
        "Editor SQL": "Editor SQL",
        "Query Builder": "Constructor de consultas",
        "Perguntas": "Preguntas",
        "Dashboards": "Tableros",
        "Execuções": "Ejecuciones",
        "Auditoria": "Auditoría",
        "Voltar": "Volver",
        "Cancelar": "Cancelar",
        "Salvar": "Guardar",
        "Executar": "Ejecutar",
        "Resultado": "Resultado",
        "Erro": "Error",
        "Linhas": "Filas",
        "Linhas retornadas": "Filas devueltas",
        "Nova pergunta": "Nueva pregunta",
        "Nova fonte": "Nueva fuente",
        "Criar": "Crear",
        "Dashboard": "Tablero",
        "Nenhum card ainda. Crie um dashboard escolhendo perguntas.": "Aún no hay tarjetas. Crea un tablero seleccionando preguntas.",
        "Exportar PDF": "Exportar PDF",
        "Limpar filtros": "Limpiar filtros",
        "Filtros": "Filtros",
        "Adicionar filtro": "Agregar filtro",
        "Visualização": "Visualización",
        "Configurar visualização": "Configurar visualización",
        "Prévia": "Vista previa",
        "Tipo": "Tipo",
        "Tabela": "Tabla",
        "Gráfico": "Gráfico",
        "Pivot": "Pivot",
        "Gauges": "Medidores",
        "Drill down": "Desglose",
        "Exportar": "Exportar",
        "Gerar SQL": "Generar SQL",
        "Linguagem humana": "Lenguaje natural",
        "Gerar": "Generar",
        "Tabelas": "Tablas",
        "Colunas": "Columnas",
        "Executar pergunta": "Ejecutar pregunta",
        "Parâmetros (JSON)": "Parámetros (JSON)",
        "Use :nome_param no SQL e preencha valores aqui. tenant_id é aplicado automaticamente.": "Use :nombre_param en el SQL y complete los valores aquí. tenant_id se aplica automáticamente.",
        "Gerar SQL no editor": "Generar SQL en el editor",
        "Fonte de dados": "Fuente de datos",
        "Estrutura": "Esquema",
        "Limite": "Límite",
        "montar SELECT com ajuda da estrutura": "construir SELECT con ayuda del esquema",
        "Escolha uma fonte para ver tabelas e colunas (autocomplete).": "Elige una fuente para ver tablas y columnas (autocompletado).",
        "Execute consultas ad-hoc, com autocomplete, Query Builder e linguagem humana.": "Ejecuta consultas ad-hoc con autocompletado, constructor de consultas y lenguaje natural.",
        "Sem linhas retornadas.": "No se devolvieron filas.",

        # UI+AI
        "Editar layout": "Editar diseño",
        "Salvar layout": "Guardar diseño",
        "Cancelar edição": "Cancelar edición",
        "Layout salvo.": "Diseño guardado.",
        "Falha ao salvar layout.": "Error al guardar el diseño.",
        "Modo edição": "Modo edición",
        "IA": "IA",
        "Chat IA": "Chat IA",
        "Pergunte sobre os dados": "Preguntar sobre los datos",
        "Selecione uma pergunta": "Seleccione una pregunta",
        "Enviar": "Enviar",
        "Mensagem": "Mensaje",
        "Histórico": "Historial",
        "Limpar chat": "Limpiar chat",
        "Gerando resposta...": "Generando respuesta...",
        "Análise": "Análisis",
        "Gráficos sugeridos": "Gráficos sugeridos",
        "Sugestões de follow-up": "Sugerencias de seguimiento",
        "Chave OpenAI ausente. Defina OPENAI_API_KEY no servidor.": "Falta la clave de OpenAI. Defina OPENAI_API_KEY en el servidor.",
        "Erro ao chamar IA: {error}": "Error al llamar a la IA: {error}",
        "Tema": "Tema",
        "Claro": "Claro",
        "Escuro": "Oscuro",
        "Explorar": "Explorar",
        "Explore dados e crie visualizações como no Superset/Metabase.": "Explora datos y crea visualizaciones como Superset/Metabase.",
        "Adicionar card": "Añadir tarjeta",
        "Remover card": "Eliminar tarjeta",
        "Buscar pergunta": "Buscar pregunta",
        "Digite para filtrar...": "Escribe para filtrar...",
        "Você pode refinar depois em Configurar visualização.": "Puedes refinar después en Configurar visualización.",
        "Atualizar": "Actualizar",
        "Salvar visualização": "Guardar visualización",
        "Visualização salva.": "Visualización guardada.",
        "Adicionar ao dashboard": "Añadir al dashboard",
        "Cria um card no dashboard com esta visualização.": "Crea una tarjeta en el dashboard con esta visualización.",
        "Card adicionado ao dashboard.": "Tarjeta añadida al dashboard.",
        "Card criado. Recarregando...": "Tarjeta creada. Recargando...",
        "Criando card...": "Creando tarjeta...",
        "Remover card?": "¿Eliminar tarjeta?",
        "Sem filtros.": "Sin filtros.",
        "Campo": "Campo",
        "Dimensão": "Dimensión",
        "Métrica": "Métrica",
        "Drill-down": "Drill-down",
        "Clique no gráfico para filtrar por um valor.": "Haz clic en el gráfico para filtrar por un valor.",
        "Pivot linhas": "Filas pivot",
        "Pivot colunas": "Columnas pivot",
        "Pivot valor": "Valor pivot",
        "Visuels & cas d’usage : Data, IA, ERP": "Visuales y casos de uso: Datos, IA, ERP",
        "Un aperçu des types de solutions que nous concevons : pilotage, automatisation et intelligence appliquée.": "Una visión de los tipos de soluciones que diseñamos: cuadros de mando, automatización e inteligencia aplicada.",
        "Data & BI": "Datos & BI",
        "Tableaux de bord exécutifs, KPIs, gouvernance, qualité et traçabilité de bout en bout.": "Cuadros de mando ejecutivos, KPIs, gobernanza, calidad y trazabilidad de extremo a extremo.",
        "IA appliquée": "IA aplicada",
        "Détection d'anomalies, scoring de risques, assistants métiers et analyse prédictive.": "Detección de anomalías, scoring de riesgos, asistentes de negocio y análisis predictivo.",
        "ERP & workflows": "ERP & flujos de trabajo",
        "Workflows métiers, intégrations SI, automatisation, contrôles et auditabilité.": "Flujos de trabajo empresariales, integraciones de sistemas, automatización, controles y auditabilidad.",
        "LegalTech": "LegalTech",
        "Gestion des dossiers, rentabilité par affaire, génération documentaire, conformité.": "Gestión de expedientes, rentabilidad por asunto, generación documental, cumplimiento.",
        "Pourquoi AUDELA": "Por qué AUDELA",
        "Une expertise de fond, une exécution rigoureuse, et une obsession de la qualité en production.": "Experiencia profunda, ejecución rigurosa y obsesión por la calidad en producción.",
        "Cloud-native, API-first, intégrations propres : une base solide pour durer et évoluer.": "Cloud-native, API-first, integraciones limpias: una base sólida para durar y escalar.",
        "Conformité et gouvernance : contrôles d’accès, traçabilité, et bonnes pratiques SI.": "Cumplimiento y gobernanza: controles de acceso, trazabilidad y buenas prácticas de TI.",
        "Pipelines & qualité : de la source au tableau de bord, sans compromis sur les données.": "Pipelines & calidad: desde la fuente hasta el cuadro de mando, sin comprometer los datos.",
        "CI/CD, monitoring, logs & alerting : stabilité, performance et mises en production rapides.": "CI/CD, monitoring, logs & alerting: estabilidad, rendimiento y despliegues rápidos.",
        "Interopérabilité : connexion ERP/CRM/outils métiers, synchronisation et automatisation.": "Interoperabilidad: conexión ERP/CRM/herramientas de negocio, sincronización y automatización.",
        "Delivery et transfert : cadrage, documentation et montée en compétence de vos équipes.": "Entrega y transferencia: alcance, documentación y capacitación de sus equipos.",
        "Découvrir nos plans BI": "Descubre nuestros planes BI",
        "Parlons de votre projet": "Hablemos de tu proyecto",
        "Décrivez votre besoin (Data/BI, ERP, LegalTech, IA, Mobile, IoT). Nous vous recontactons rapidement.": "Describe tu necesidad (Data/BI, ERP, LegalTech, IA, Móvil, IoT). Te contactamos rápidamente.",
        "Votre adresse e-mail": "Tu dirección de correo electrónico",
        "Être rappelé": "Ser contactado",
        "Carregando...": "Cargando...",
        "OK": "OK",

        # Source diagram module
        "Source Diagram": "Diagrama de fuente",
        "Select data source": "Seleccione la fuente de datos",
        "Load diagram": "Cargar diagrama",
        "Refresh": "Actualizar",
        "Click a node to highlight relations. Use mousewheel to zoom.": "Haga clic en un nodo para resaltar las relaciones. Use la rueda del ratón para acercar/alejar.",

        # Auth messages
        "Tenant não encontrado.": "Tenant no encontrado.",
        "Credenciais inválidas.": "Credenciales inválidas.",
        "Preencha todos os campos.": "Completa todos los campos.",
        "Slug já existe.": "El slug ya existe.",
        "Tenant criado. Faça login.": "Tenant creado. Por favor, inicia sesión.",

        # Data source messages
        "Preencha nome, tipo e URL de conexão.": "Completa el nombre, tipo y URL de conexión.",
        "Fonte criada.": "Fuente de datos creada.",
        "Fonte removida.": "Fuente de datos eliminada.",
        "Falha ao introspectar: {error}": "Error de introspección: {error}",
        "Selecione uma fonte válida.": "Selecciona una fuente de datos válida.",
        "Selecione uma fonte.": "Selecciona una fuente de datos.",
        "Fonte inválida.": "Fuente de datos inválida.",

        # Data source test + form (wizard)
        "Informe uma URL de conexão.": "Indica una URL de conexión.",
        "Conexão OK.": "Conexión OK.",
        "Falha na conexão.": "Fallo de conexión.",
        "Falha na conexão: {error}": "Fallo de conexión: {error}",
        "Nova fonte de dados": "Nueva fuente de datos",
        "Configure uma nova origem de dados para consultas e relatórios.": "Configura una nueva fuente de datos para consultas e informes.",
        "Informações básicas": "Información básica",
        "Nome interno para identificar a fonte.": "Nombre interno para identificar la fuente.",
        "Tipo de banco": "Tipo de base de datos",
        "Conexão": "Conexión",
        "Assistente": "Asistente",
        "URL manual": "URL manual",
        "URL (manual)": "URL (manual)",
        "Porta": "Puerto",
        "Database": "Base de datos",
        "Senha": "Contraseña",
        "(opcional)": "(opcional)",
        "(deixe vazio para manter)": "(deja vacío para mantener)",
        "Fica criptografado no config. Se preferir, cole uma URL pronta no modo \"URL manual\".": "Se guarda cifrado en la configuración. Si prefieres, pega una URL lista en el modo \"URL manual\".",
        "Driver (SQL Server)": "Driver (SQL Server)",
        "Service Name (Oracle)": "Service Name (Oracle)",
        "SID (Oracle)": "SID (Oracle)",
        "Arquivo SQLite": "Archivo SQLite",
        "Exemplo:": "Ejemplo:",
        "ou apenas o caminho.": "o solo la ruta.",
        "URL gerada (SQLAlchemy)": "URL generada (SQLAlchemy)",
        "A URL abaixo será copiada para o campo \"URL manual\" automaticamente.": "La URL de abajo se copiará automáticamente al campo \"URL manual\".",
        "URL de conexão (SQLAlchemy)": "URL de conexión (SQLAlchemy)",
        "SQLite local:": "SQLite local:",
        "Config (descriptografado)": "Config (descifrada)",
        "Copiar": "Copiar",
        "Prévia do JSON que será criptografado ao salvar.": "Vista previa del JSON que se cifrará al guardar.",
        "Opções avançadas": "Opciones avanzadas",
        "Schema padrão": "Esquema predeterminado",
        "Schema usado por padrão nas consultas.": "Esquema usado por defecto en las consultas.",
        "Coluna tenant": "Columna tenant",
        "Se preenchida, o SQL deve conter": "Si se completa, el SQL debe contener",
        "Testar conexão": "Probar conexión",
        "Salvar fonte": "Guardar fuente",
        "Salvar alterações": "Guardar cambios",
        "Atualize a conexão e as opções avançadas.": "Actualiza la conexión y las opciones avanzadas.",
        "Por segurança, a senha não é exibida. Se deixar vazio, manteremos a atual.": "Por seguridad, la contraseña no se muestra. Si lo dejas vacío, mantendremos la actual.",
        "(padrão)": "(predeterminado)",
        "URL SQLAlchemy (gerada)": "URL SQLAlchemy (generada)",
        "A URL abaixo também será salva no campo manual.": "La URL de abajo también se guardará en el campo manual.",
        "Caminho do arquivo (SQLite)": "Ruta del archivo (SQLite)",
        "Pode usar um caminho absoluto, relativo, ou uma URL": "Puedes usar una ruta absoluta, relativa o una URL",

        # JS feedback
        "Copiado.": "Copiado.",
        "Falha ao copiar.": "Error al copiar.",
        "Testando...": "Probando...",
        "Endpoint de teste não configurado.": "Endpoint de prueba no configurado.",

        # Question messages
        "Preencha nome, fonte e SQL.": "Completa el nombre, la fuente y el SQL.",
        "Pergunta criada.": "Pregunta creada.",
        "Pergunta removida.": "Pregunta eliminada.",

        # Dashboard messages
        "Dashboard criado.": "Dashboard creado.",
        "Dashboard removido.": "Dashboard eliminado.",
        "Dashboard definido como principal.": "Dashboard definido como principal.",
        "Operação não suportada: execute as migrações do banco para habilitar essa função.": "Operación no soportada: ejecuta las migraciones de base de datos para habilitar esta función.",
        "Informe um nome.": "Ingresa un nombre.",

        # Configuration messages
        "Configuração inválida.": "Configuración inválida.",

        # User messages
        "Email e senha são obrigatórios.": "El correo electrónico y la contraseña son obligatorios.",
        "Usuário criado.": "Usuario creado.",
        "Usuário removido.": "Usuario eliminado.",

        # NLQ service messages
        "Não foi possível identificar uma tabela com segurança.": "No se pudo identificar una tabla de forma segura.",
        "Selecione uma tabela no Query Builder (à direita) ou escreva o SQL manualmente.": "Selecciona una tabla en Query Builder (a la derecha) o escribe el SQL manualmente.",
        "Tabela não identificada": "Tabla no identificada",
        "Texto vazio": "Texto vacío",
        "Coluna métrica escolhida por fallback": "Columna de métrica elegida por defecto",
        "Coluna métrica não identificada": "Columna de métrica no identificada",

        # Home page
        "O que já está no MVP": "Lo que ya está en el MVP",
        "Fontes por tenant (cadastro + introspecção)": "Fuentes de datos por inquilino (registro + introspección)",
        "Editor SQL (execução ad-hoc com limites)": "Editor SQL (ejecución ad-hoc con límites)",
        "Perguntas (queries salvas) + execução": "Preguntas (consultas guardadas) + ejecución",
        "Dashboards (cards simples com perguntas)": "Paneles (tarjetas simples con preguntas)",
        "Auditoria + Query Runs por tenant": "Auditoría + Ejecuciones de consultas por inquilino",
        "Começar": "Primeros pasos",
        "Crie uma fonte": "Cree una fuente de datos en Fuentes → Nueva",
        "Introspecte metadados na fonte (botão 'Introspectar')": "Introspeccione metadatos en la fuente (botón \"Introspect\")",
        "Teste uma consulta no Editor SQL": "Pruebe una consulta en el Editor SQL",
        "Salve uma Pergunta e crie um Dashboard": "Guarde una Pregunta y cree un Panel",
        "cadastro + introspecção": "registro + introspección",
        "execução ad-hoc com limites": "ejecución ad-hoc con límites",
        "queries salvas": "consultas guardadas",
        "cards simples com perguntas": "tarjetas simples con preguntas",
        "por tenant": "por inquilino",
        "Nova": "Nueva",
        "e crie um": "y cree un",

        # Placeholder texts
        "Ex.: DW Produção": "Ej.: DW Producción",
        "Ex.: postgresql+psycopg2://user:pass@host:5432/dbname": "Ej.: postgresql+psycopg2://user:pass@host:5432/dbname",
        "public": "public",
        "tenant_id": "tenant_id",
        "ex: total vendas por mês": "ej: total de ventas por mes",
        "acme": "acme",
        "you@example.com": "you@example.com",
        "tenant slug (ex.: acme)": "slug del tenant (ej.: acme)",
        "nome do tenant": "nombre del tenant",
        "email do admin": "correo del administrador",
        "senha": "contraseña",
        "value": "valor",
        "SELECT ...": "SELECT ...",

        # AI service prompts
        "You are a BI analyst": "Eres un analista de BI",
        "You receive metadata and data sample": "Recibes metadatos y una muestra de datos (columnas/filas) de una pregunta SQL",
        "Respond with clear insights": "Responde con información clara, hipótesis, limitaciones y sugiere gráficos",
        "Your output MUST be valid JSON": "Tu salida DEBE ser JSON válido (sin markdown, sin bloques de código) con estas claves",
        "analysis key": "analysis: string (se permite markdown simple, pero sin HTML)",
        "charts key": "charts: lista de objetos {title: string, echarts_option: object}",
        "followups key": "followups: lista de strings",
        "Use only the provided sample": "Usa solo la muestra y el perfil proporcionados; si falta algo, dilo explícitamente",
        "For charts generate safe ECharts": "Para gráficos, genera opciones ECharts seguras, sin funciones JS",
        "If insufficient data return empty": "Si hay datos insuficientes, retorna charts=[] y explica en el análisis",


        "Relatórios": "Informes",
        "Novo relatório": "Nuevo informe",
        "Construa relatórios com drag & drop (estilo Crystal Reports).": "Cree informes con arrastrar y soltar (estilo Crystal Reports).",
        "Nenhum relatório criado ainda.": "Aún no se han creado informes.",
        "Abrir builder": "Abrir constructor",
        "Arraste e solte": "Arrastrar y soltar",
        "Cabeçalho": "Encabezado",
        "Corpo": "Cuerpo",
        "Rodapé": "Pie de página",
        "Editar": "Editar",
        "Remover": "Eliminar",
        "Título do bloco:": "Título del bloque:",
        "Pergunta salva": "Pregunta guardada",
        "Falha ao salvar": "Error al guardar",
        "Arraste aqui...": "Suelte aquí...",
        "Salvo": "Guardado",
        "Pergunta #{n}": "Pregunta #{n}",
        "Fechar": "Cerrar",
        "Sucesso": "Éxito",
        "Info": "Info",
        "Imagem": "Imagen",
        "Figura / logotipo / screenshot": "Figura / logotipo / captura",
        "Adicionar imagem": "Agregar imagen",
        "URL (https://...)": "URL (https://...)",
        "Isso cria um bloco “Imagem” no corpo do relatório.": "Esto crea un bloque “Imagen” en el cuerpo del informe.",
        "URL da imagem:": "URL de la imagen:",
        "Texto alternativo (alt):": "Texto alternativo (alt):",
        "Legenda (opcional):": "Pie de foto (opcional):",
        "Largura (ex.: 300px ou 50%):": "Ancho (p. ej., 300px o 50%):",
        "Alinhamento (left/center/right):": "Alineación (left/center/right):",
        "Cor do texto (ex.: #111 ou vazio):": "Color de texto (p. ej., #111 o vacío):",
        "Cor de fundo (ex.: #fff ou vazio):": "Color de fondo (p. ej., #fff o vacío):",
        "Imagem não disponível": "Imagen no disponible",
        "Texto (Markdown):": "Texto (Markdown):",
        "Texto:": "Texto:",
        "Bloco": "Bloque",
        "Erro ao executar pergunta: {error}": "Error al ejecutar la pregunta: {error}",
        "Editar bloco": "Editar bloque",
        "Título": "Título",
        "URL da imagem": "URL de la imagen",
        "https://...": "https://...",
        "Texto alternativo (alt)": "Texto alternativo (alt)",
        "Largura": "Ancho",
        "ex.: 300px ou 50%": "p. ej., 300px o 50%",
        "Pré-visualização": "Vista previa",
        "Estilo": "Estilo",
        "Cor do texto": "Color del texto",
        "Cor de fundo": "Color de fondo",
        "Sem": "Ninguno",
        "hex ou vazio": "hex o vacío",
        "Aplicar": "Aplicar",
        "Esquerda": "Izquierda",
        "Centro": "Centro",
        "Direita": "Derecha",
        "Padrão": "Predeterminado",

        # Workspaces (DuckDB + Files)
        "Novo workspace": "Nuevo workspace",
        "Workspace permite fazer JOIN entre arquivos (CSV/Excel/Parquet) e tabelas do banco, tudo em DuckDB.": "Los workspaces permiten hacer JOIN entre archivos (CSV/Excel/Parquet) y tablas de base de datos, todo dentro de DuckDB.",
        "Configuração": "Configuración",
        "Fonte de banco (opcional)": "Fuente de base de datos (opcional)",
        "sem banco": "sin base",
        "Para JOIN com banco, selecione as tabelas. Elas ficam acessíveis como db.<tabela>.": "Para JOIN con la base, seleccione las tablas. Están disponibles como db.<tabla>.",
        "Tabelas do banco": "Tablas de la base",
        "Selecionar tabelas": "Seleccionar tablas",
        "Dica: use o Construtor rápido de JOIN para gerar um SQL inicial.": "Consejo: use el Constructor rápido de JOIN para generar un SQL inicial.",
        "Limite de linhas": "Límite de filas",
        "Usado para amostragem (segurança/performance).": "Se usa para muestreo (seguridad/rendimiento).",
        "Abrir File Explorer": "Abrir Explorador de archivos",
        "Nenhum arquivo uploadado ainda. Use o menu Arquivos.": "Aún no se subieron archivos. Use el menú Archivos.",
        "Filtrar arquivos…": "Filtrar archivos…",
        "Alias (tabela)": "Alias (tabla)",
        "Criar workspace": "Crear workspace",
        "Construtor rápido de JOIN": "Constructor rápido de JOIN",
        "Selecione arquivos/tabelas e gere um SQL inicial com JOINs e autocomplete de colunas.": "Seleccione archivos/tablas y genere un SQL inicial con JOINs y autocompletado de columnas.",
        "Selecione arquivos/tabelas": "Seleccione archivos/tablas",
        "Tabela base": "Tabla base",
        "Sugestões de JOIN": "Sugerencias de JOIN",
        "JOINs": "JOINs",
        "Adicionar JOIN": "Añadir JOIN",
        "Coluna": "Columna",
        "Gerar SQL com IA": "Generar SQL con IA",
        "Descreva sua análise": "Describa su análisis",
        "SQL inicial": "SQL inicial",
        "Seu SQL aparecerá aqui…": "Su SQL aparecerá aquí…",
        "Ao criar o workspace, este SQL fica salvo como rascunho (starter_sql) para você copiar no Editor SQL.": "Al crear el workspace, este SQL se guarda como borrador (starter_sql) para que pueda copiarlo en el Editor SQL.",
        "Filtrar tabelas…": "Filtrar tablas…",
        "Nenhuma tabela encontrada.": "No se encontraron tablas.",
        "Selecione uma fonte de banco para listar tabelas.": "Seleccione una fuente de base de datos para listar tablas.",
        "Falha ao carregar schema.": "No se pudo cargar el esquema.",
        "Selecione pelo menos duas tabelas para sugerir joins.": "Seleccione al menos dos tablas para sugerir joins.",
        "Nenhuma sugestão disponível.": "No hay sugerencias disponibles.",
        "SQL gerado.": "SQL generado.",
        "Falha ao gerar SQL.": "No se pudo generar el SQL.",
        "Schema: {name}": "Esquema: {name}",
        "Ex.: BI - Vendas + Clientes": "Ej.: BI - Ventas + Clientes",
        "Ex.: total de vendas por mês e segmento, com ticket médio": "Ej.: total de ventas por mes y segmento, con ticket medio",
        "Workspace criado.": "Workspace creado.",
    },
    "it": {
        "Accueil": "Home",
        "À propos": "Chi siamo",
        "Expertise": "Competenze",
        "Solutions": "Soluzioni",
        "Pourquoi AUDELA": "Perché AUDELA",
        "Projets": "Progetti",
        "Plans BI": "Piani BI",
        "Área BI": "Area BI",
        "Contact": "Contatto",
        "Mobile": "Mobile",
        "IoT & Neuro": "IoT & Neuro",
        "BI & Metabase": "BI & Metabase",
        "BeLegal (LegalTech)": "BeLegal (LegalTech)",
        "Tous droits réservés.": "Tutti i diritti riservati.",

        # Index / landing
        "La technologie au service de la décision.": "La tecnologia al servizio della decisione.",
        "Data, BI, ERP, LegalTech & IA — au cœur de vos opérations.": "Data, BI, ERP, LegalTech & IA — al centro delle vostre operazioni.",
        "Illustration AUDELA": "Illustrazione AUDELA",
        "Next": "Avanti",
        "Grenoble & Alpes": "Grenoble & Alpi",
        "Au-delà des données": "Oltre i dati",
        "Transformer l'information en décisions — avec une ingénierie logicielle robuste et une compréhension métier réelle.": "Trasformare l'informazione in decisioni — con ingegneria del software robusta e reale comprensione del business.",
        "Nous construisons des systèmes qui tiennent dans la durée : pipelines data industrialisés, APIs fiables, applications web et mobile, et des dashboards compréhensibles par les équipes terrain comme par la direction.": "Costruiamo sistemi che durano: pipeline dati industrializzati, API affidabili, applicazioni web e mobile e dashboard comprensibili da team operativi e direzione.",
        "Notre approche est pragmatique et \"production-first\" : sécurité, performance, observabilité, documentation, et transfert de compétences. L'objectif : livrer vite, sans dette technique.": "Il nostro approccio è pragmatico e production-first: sicurezza, performance, osservabilità, documentazione e trasferimento di competenze. Obiettivo: consegnare velocemente, senza debito tecnico.",
        "Business Intelligence": "Business Intelligence",
        "Analyse de données & Business Intelligence": "Analisi dei dati & Business Intelligence",
        "Ingestion, modélisation, qualité et exposition : des indicateurs fiables, traçables et actionnables.": "Ingestione, modellazione, qualità ed esposizione: indicatori affidabili, tracciabili e azionabili.",
        "Nous connectons vos systèmes (ERP, CRM, finance, opérations, APIs), structurons la donnée (DWH/ELT), et livrons des tableaux de bord qui répondent à des questions concrètes : marge, performance commerciale, délais, risques, conformité.": "Connettiamo i vostri sistemi (ERP, CRM, finanza, operations, API), strutturiamo i dati (DWH/ELT) e consegniamo dashboard che rispondono a domande concrete: margine, performance commerciale, tempi, rischi, conformità.",
        "Voir les écrans Metabase": "Vedi le schermate Metabase",
        "Plateformes métiers": "Piattaforme di business",
        "Plateformes métiers, ERP & IA appliquée": "Piattaforme business, ERP & IA applicata",
        "Des outils métier qui reflètent vos workflows, avec une IA utile et explicable.": "Strumenti business che rispecchiano i vostri workflow, con IA utile e spiegabile.",
        "Découvrir BeLegal": "Scopri BeLegal",

        # Home page
        "O que já está no MVP": "Cosa è già nel MVP",
        "Fontes por tenant (cadastro + introspecção)": "Fonti di dati per tenant (registrazione + introspezione)",
        "Editor SQL (execução ad-hoc com limites)": "Editor SQL (esecuzione ad-hoc con limiti)",
        "Perguntas (queries salvas) + execução": "Domande (query salvate) + esecuzione",
        "Dashboards (cards simples com perguntas)": "Dashboard (schede semplici con domande)",
        "Auditoria + Query Runs por tenant": "Audit + Query Runs per tenant",
        "Começar": "Iniziare",
        "Crie uma fonte": "Crea una fonte di dati in Fonti → Nuovo",
        "Introspecte metadados na fonte (botão 'Introspectar')": "Ispeziona i metadati nella fonte (pulsante \"Introspect\")",
        "Teste uma consulta no Editor SQL": "Prova una query nell'Editor SQL",
        "Salve uma Pergunta e crie um Dashboard": "Salva una Domanda e crea un Dashboard",
        "cadastro + introspecção": "registrazione + introspezione",
        "execução ad-hoc com limites": "esecuzione ad-hoc con limiti",
        "queries salvas": "query salvate",
        "cards simples com perguntas": "schede semplici con domande",
        "por tenant": "per tenant",
        "Nova": "Nuovo",
        "e crie um": "e crea un",

        "Portal BI": "Portale BI",
        "Usuário": "Utente",
        "Sair": "Esci",
        "Home": "Home",
        "Fontes": "Fonti",
        "Metadados": "Metadati",
        "Editor SQL": "Editor SQL",
        "Query Builder": "Generatore di query",
        "Perguntas": "Domande",
        "Dashboards": "Dashboard",
        "Execuções": "Esecuzioni",
        "Auditoria": "Audit",
        "Voltar": "Indietro",
        "Cancelar": "Annulla",
        "Salvar": "Salva",
        "Executar": "Esegui",
        "Resultado": "Risultato",
        "Erro": "Errore",
        "Linhas": "Righe",
        "Linhas retornadas": "Righe restituite",
        "Nova pergunta": "Nuova domanda",
        "Nova fonte": "Nuova fonte",
        "Criar": "Crea",
        "Dashboard": "Dashboard",
        "Nenhum card ainda. Crie um dashboard escolhendo perguntas.": "Nessuna scheda ancora. Crea una dashboard scegliendo le domande.",
        "Exportar PDF": "Esporta PDF",
        "Limpar filtros": "Pulisci filtri",
        "Filtros": "Filtri",
        "Adicionar filtro": "Aggiungi filtro",
        "Visualização": "Visualizzazione",
        "Configurar visualização": "Configura visualizzazione",
        "Prévia": "Anteprima",
        "Tipo": "Tipo",
        "Tabela": "Tabella",
        "Gráfico": "Grafico",
        "Pivot": "Pivot",
        "Gauges": "Indicatori",
        "Drill down": "Dettaglio",
        "Exportar": "Esporta",
        "Gerar SQL": "Genera SQL",
        "Linguagem humana": "Linguaggio naturale",
        "Gerar": "Genera",
        "Tabelas": "Tabelle",
        "Colunas": "Colonne",
        "Executar pergunta": "Esegui domanda",
        "Parâmetros (JSON)": "Parametri (JSON)",
        "Use :nome_param no SQL e preencha valores aqui. tenant_id é aplicado automaticamente.": "Usa :nome_param nello SQL e inserisci i valori qui. tenant_id viene applicato automaticamente.",
        "Gerar SQL no editor": "Genera SQL nell'editor",
        "Fonte de dados": "Fonte dati",
        "Estrutura": "Schema",
        "Limite": "Limite",
        "montar SELECT com ajuda da estrutura": "costruire SELECT con l’aiuto dello schema",
        "Escolha uma fonte para ver tabelas e colunas (autocomplete).": "Scegli una fonte per vedere tabelle e colonne (autocompletamento).",
        "Execute consultas ad-hoc, com autocomplete, Query Builder e linguagem humana.": "Esegui query ad-hoc con autocompletamento, generatore di query e linguaggio naturale.",
        "Sem linhas retornadas.": "Nessuna riga restituita.",

        # UI+AI
        "Editar layout": "Modifica layout",
        "Salvar layout": "Salva layout",
        "Cancelar edição": "Annulla modifica",
        "Layout salvo.": "Layout salvato.",
        "Falha ao salvar layout.": "Errore nel salvare il layout.",
        "Modo edição": "Modalità modifica",
        "IA": "IA",
        "Chat IA": "Chat IA",
        "Pergunte sobre os dados": "Chiedi sui dati",
        "Selecione uma pergunta": "Seleziona una domanda",
        "Enviar": "Invia",
        "Mensagem": "Messaggio",
        "Histórico": "Cronologia",
        "Limpar chat": "Pulisci chat",
        "Gerando resposta...": "Generazione risposta...",
        "Análise": "Analisi",
        "Gráficos sugeridos": "Grafici suggeriti",
        "Sugestões de follow-up": "Suggerimenti di follow-up",
        "Chave OpenAI ausente. Defina OPENAI_API_KEY no servidor.": "Chiave OpenAI mancante. Imposta OPENAI_API_KEY sul server.",
        "Erro ao chamar IA: {error}": "Errore chiamando l'IA: {error}",
        "Tema": "Tema",
        "Claro": "Chiaro",
        "Escuro": "Scuro",
        "Explorar": "Esplora",
        "Explore dados e crie visualizações como no Superset/Metabase.": "Esplora i dati e crea visualizzazioni come Superset/Metabase.",
        "Adicionar card": "Aggiungi scheda",
        "Remover card": "Rimuovi scheda",
        "Buscar pergunta": "Cerca domanda",
        "Digite para filtrar...": "Digita per filtrare...",
        "Você pode refinar depois em Configurar visualização.": "Puoi rifinire dopo in Configura visualizzazione.",
        "Atualizar": "Aggiorna",
        "Salvar visualização": "Salva visualizzazione",
        "Visualização salva.": "Visualizzazione salvata.",
        "Adicionar ao dashboard": "Aggiungi al dashboard",
        "Cria um card no dashboard com esta visualização.": "Crea una scheda nel dashboard con questa visualizzazione.",
        "Card adicionado ao dashboard.": "Scheda aggiunta al dashboard.",
        "Card criado. Recarregando...": "Scheda creata. Ricaricamento...",
        "Criando card...": "Creazione scheda...",
        "Remover card?": "Rimuovere la scheda?",
        "Sem filtros.": "Nessun filtro.",
        "Campo": "Campo",
        "Dimensão": "Dimensione",
        "Métrica": "Metrica",
        "Drill-down": "Drill-down",
        "Clique no gráfico para filtrar por um valor.": "Clicca sul grafico per filtrare per un valore.",
        "Pivot linhas": "Righe pivot",
        "Pivot colunas": "Colonne pivot",
        "Pivot valor": "Valore pivot",
        "Visuels & cas d’usage : Data, IA, ERP": "Visivi & casi d'uso: Dati, IA, ERP",
        "Un aperçu des types de solutions que nous concevons : pilotage, automatisation et intelligence appliquée.": "Uno sguardo ai tipi di soluzioni che progettiamo: cruscotti operativi, automazione e intelligenza applicata.",
        "Data & BI": "Dati & BI",
        "Tableaux de bord exécutifs, KPIs, gouvernance, qualité et traçabilité de bout en bout.": "Cruscotti esecutivi, KPI, governance, qualità e tracciabilità end-to-end.",
        "IA appliquée": "IA applicata",
        "Détection d'anomalies, scoring de risques, assistants métiers et analyse prédictive.": "Rilevamento anomalie, scoring dei rischi, assistenti per il business e analisi predittiva.",
        "ERP & workflows": "ERP & flussi di lavoro",
        "Workflows métiers, intégrations SI, automatisation, contrôles et auditabilité.": "Flussi di lavoro aziendali, integrazioni di sistema, automazione, controlli e auditabilità.",
        "LegalTech": "LegalTech",
        "Gestion des dossiers, rentabilité par affaire, génération documentaire, conformité.": "Gestione pratiche, redditività per caso, generazione documentale, conformità.",
        "Pourquoi AUDELA": "Perché AUDELA",
        "Une expertise de fond, une exécution rigoureuse, et une obsession de la qualité en production.": "Competenza profonda, esecuzione rigorosa e ossessione per la qualità in produzione.",
        "Cloud-native, API-first, intégrations propres : une base solide pour durer et évoluer.": "Cloud-native, API-first, integrazioni pulite: una base solida per durare e crescere.",
        "Conformité et gouvernance : contrôles d’accès, traçabilité, et bonnes pratiques SI.": "Conformità e governance: controlli accessi, tracciabilità e best practice IT.",
        "Pipelines & qualité : de la source au tableau de bord, sans compromis sur les données.": "Pipeline & qualità: dalla sorgente al cruscotto, senza compromessi sui dati.",
        "CI/CD, monitoring, logs & alerting : stabilité, performance et mises en production rapides.": "CI/CD, monitoring, log & alerting: stabilità, performance e rilasci rapidi in produzione.",
        "Interopérabilité : connexion ERP/CRM/outils métiers, synchronisation et automatisation.": "Interoperabilità: connessione ERP/CRM/strumenti business, sincronizzazione e automazione.",
        "Delivery et transfert : cadrage, documentation et montée en compétence de vos équipes.": "Delivery e handover: definizione, documentazione e upskilling dei vostri team.",
        "Découvrir nos plans BI": "Scopri i nostri piani BI",
        "Parlons de votre projet": "Parliamo del tuo progetto",
        "Décrivez votre besoin (Data/BI, ERP, LegalTech, IA, Mobile, IoT). Nous vous recontactons rapidement.": "Descrivi la tua esigenza (Data/BI, ERP, LegalTech, IA, Mobile, IoT). Ti ricontatteremo rapidamente.",
        "Votre adresse e-mail": "Il tuo indirizzo e-mail",
        "Être rappelé": "Essere ricontattati",
        "Carregando...": "Caricamento...",
        "OK": "OK",

        # Source diagram module
        "Source Diagram": "Diagramma sorgente",
        "Select data source": "Seleziona sorgente dati",
        "Load diagram": "Carica diagramma",
        "Refresh": "Aggiorna",
        "Click a node to highlight relations. Use mousewheel to zoom.": "Clicca un nodo per evidenziare le relazioni. Usa la rotellina per zoomare.",

        # Auth messages
        "Tenant não encontrado.": "Tenant non trovato.",
        "Credenciais inválidas.": "Credenziali non valide.",
        "Preencha todos os campos.": "Completa tutti i campi.",
        "Slug já existe.": "Lo slug esiste già.",
        "Tenant criado. Faça login.": "Tenant creato. Accedi.",

        # Data source messages
        "Preencha nome, tipo e URL de conexão.": "Completa il nome, il tipo e l'URL di connessione.",
        "Fonte criada.": "Fonte dati creata.",
        "Fonte removida.": "Fonte dati rimossa.",
        "Falha ao introspectar: {error}": "Errore di introspezione: {error}",
        "Selecione uma fonte válida.": "Seleziona una fonte dati valida.",
        "Selecione uma fonte.": "Seleziona una fonte dati.",
        "Fonte inválida.": "Fonte dati non valida.",

        # Data source test + form (wizard)
        "Informe uma URL de conexão.": "Inserisci un URL di connessione.",
        "Conexão OK.": "Connessione OK.",
        "Falha na conexão.": "Connessione fallita.",
        "Falha na conexão: {error}": "Connessione fallita: {error}",
        "Nova fonte de dados": "Nuova fonte dati",
        "Configure uma nova origem de dados para consultas e relatórios.": "Configura una nuova fonte dati per query e report.",
        "Informações básicas": "Informazioni di base",
        "Nome interno para identificar a fonte.": "Nome interno per identificare la fonte.",
        "Tipo de banco": "Tipo di database",
        "Conexão": "Connessione",
        "Assistente": "Assistente",
        "URL manual": "URL manuale",
        "URL (manual)": "URL (manuale)",
        "Porta": "Porta",
        "Database": "Database",
        "Senha": "Password",
        "(opcional)": "(opzionale)",
        "(deixe vazio para manter)": "(lascia vuoto per mantenere)",
        "Fica criptografado no config. Se preferir, cole uma URL pronta no modo \"URL manual\".": "Viene salvato cifrato nella config. Se preferisci, incolla un URL già pronto in modalità \"URL manuale\".",
        "Driver (SQL Server)": "Driver (SQL Server)",
        "Service Name (Oracle)": "Service Name (Oracle)",
        "SID (Oracle)": "SID (Oracle)",
        "Arquivo SQLite": "File SQLite",
        "Exemplo:": "Esempio:",
        "ou apenas o caminho.": "o solo il percorso.",
        "URL gerada (SQLAlchemy)": "URL generato (SQLAlchemy)",
        "A URL abaixo será copiada para o campo \"URL manual\" automaticamente.": "L'URL qui sotto verrà copiata automaticamente nel campo \"URL manuale\".",
        "URL de conexão (SQLAlchemy)": "URL di connessione (SQLAlchemy)",
        "SQLite local:": "SQLite locale:",
        "Config (descriptografado)": "Config (decifrato)",
        "Copiar": "Copia",
        "Prévia do JSON que será criptografado ao salvar.": "Anteprima del JSON che verrà cifrato al salvataggio.",
        "Opções avançadas": "Opzioni avanzate",
        "Schema padrão": "Schema predefinito",
        "Schema usado por padrão nas consultas.": "Schema usato di default nelle query.",
        "Coluna tenant": "Colonna tenant",
        "Se preenchida, o SQL deve conter": "Se compilato, lo SQL deve contenere",
        "Testar conexão": "Test connessione",
        "Salvar fonte": "Salva fonte",
        "Salvar alterações": "Salva modifiche",
        "Atualize a conexão e as opções avançadas.": "Aggiorna la connessione e le opzioni avanzate.",
        "Por segurança, a senha não é exibida. Se deixar vazio, manteremos a atual.": "Per sicurezza, la password non viene mostrata. Se lasci vuoto, manterremo quella attuale.",
        "(padrão)": "(predefinito)",
        "URL SQLAlchemy (gerada)": "URL SQLAlchemy (generato)",
        "A URL abaixo também será salva no campo manual.": "L'URL qui sotto verrà anche salvata nel campo manuale.",
        "Caminho do arquivo (SQLite)": "Percorso del file (SQLite)",
        "Pode usar um caminho absoluto, relativo, ou uma URL": "Puoi usare un percorso assoluto, relativo o un URL",

        # JS feedback
        "Copiado.": "Copiato.",
        "Falha ao copiar.": "Copia fallita.",
        "Testando...": "Test in corso...",
        "Endpoint de teste não configurado.": "Endpoint di test non configurato.",

        # Question messages
        "Preencha nome, fonte e SQL.": "Completa il nome, la fonte e l'SQL.",
        "Pergunta criada.": "Domanda creata.",
        "Pergunta removida.": "Domanda rimossa.",

        # Dashboard messages
        "Dashboard criado.": "Dashboard creato.",
        "Dashboard removido.": "Dashboard rimosso.",
        "Dashboard definido como principal.": "Dashboard impostato come principale.",
        "Operação não suportada: execute as migrações do banco para habilitar essa função.": "Operazione non supportata: esegui le migrazioni del database per abilitare questa funzione.",
        "Informe um nome.": "Inserisci un nome.",

        # Configuration messages
        "Configuração inválida.": "Configurazione non valida.",

        # User messages
        "Email e senha são obrigatórios.": "Email e password sono obbligatori.",
        "Usuário criado.": "Utente creato.",
        "Usuário removido.": "Utente rimosso.",

        # NLQ service messages
        "Não foi possível identificar uma tabela com segurança.": "Impossibile identificare una tabella in modo sicuro.",
        "Selecione uma tabela no Query Builder (à direita) ou escreva o SQL manualmente.": "Seleziona una tabella nel Query Builder (a destra) o scrivi l'SQL manualmente.",
        "Tabela não identificada": "Tabella non identificata",
        "Texto vazio": "Testo vuoto",
        "Coluna métrica escolhida por fallback": "Colonna metrica scelta per default",
        "Coluna métrica não identificada": "Colonna metrica non identificata",

        # Home page
        "O que já está no MVP": "Cosa c'è già nell'MVP",
        "Fontes por tenant (cadastro + introspecção)": "Sorgenti dati per inquilino (registrazione + introspezione)",
        "Editor SQL (execução ad-hoc com limites)": "Editor SQL (esecuzione ad-hoc con limiti)",
        "Perguntas (queries salvas) + execução": "Domande (query salvate) + esecuzione",
        "Dashboards (cards simples com perguntas)": "Dashboard (schede semplici con domande)",
        "Auditoria + Query Runs por tenant": "Audit + Esecuzioni query per inquilino",
        "Começar": "Iniziare",
        "Crie uma fonte": "Crea una sorgente dati in Fonti → Nuova",
        "Introspecte metadados na fonte (botão 'Introspectar')": "Ispeziona i metadati sulla sorgente (pulsante \"Introspect\")",
        "Teste uma consulta no Editor SQL": "Testa una query nell'Editor SQL",
        "Salve uma Pergunta e crie um Dashboard": "Salva una Domanda e crea un Dashboard",
        "cadastro + introspecção": "registrazione + introspezione",
        "execução ad-hoc com limites": "esecuzione ad-hoc con limiti",
        "queries salvas": "query salvate",
        "cards simples com perguntas": "schede semplici con domande",
        "por tenant": "per inquilino",
        "Nova": "Nuova",
        "e crie um": "e crea un",

        # Placeholder texts
        "Ex.: DW Produção": "Es.: DW Produzione",
        "Ex.: postgresql+psycopg2://user:pass@host:5432/dbname": "Es.: postgresql+psycopg2://user:pass@host:5432/dbname",
        "public": "public",
        "tenant_id": "tenant_id",
        "ex: total vendas por mês": "es: vendite totali al mese",
        "acme": "acme",
        "you@example.com": "you@example.com",
        "tenant slug (ex.: acme)": "slug del tenant (es.: acme)",
        "nome do tenant": "nome del tenant",
        "email do admin": "email dell'amministratore",
        "senha": "password",
        "value": "valore",
        "SELECT ...": "SELECT ...",

        # AI service prompts
        "You are a BI analyst": "Sei un analista di BI",
        "You receive metadata and data sample": "Ricevi metadati e un campione di dati (colonne/righe) da una domanda SQL",
        "Respond with clear insights": "Rispondi con intuizioni chiare, ipotesi, limitazioni e suggerisci grafici",
        "Your output MUST be valid JSON": "Il tuo output DEVE essere un JSON valido (senza markdown, senza blocchi di codice) con queste chiavi",
        "analysis key": "analysis: string (markdown semplice consentito, ma senza HTML)",
        "charts key": "charts: lista di oggetti {title: string, echarts_option: object}",
        "followups key": "followups: lista di stringhe",
        "Use only the provided sample": "Usa solo il campione e il profilo forniti; se manca qualcosa, dillo esplicitamente",
        "For charts generate safe ECharts": "Per i grafici, genera opzioni ECharts sicure, senza funzioni JS",
        "If insufficient data return empty": "Se ci sono dati insufficienti, restituisci charts=[] e spiega nell'analisi",


        "Relatórios": "Report",
        "Novo relatório": "Nuovo report",
        "Construa relatórios com drag & drop (estilo Crystal Reports).": "Crea report con drag & drop (stile Crystal Reports).",
        "Nenhum relatório criado ainda.": "Nessun report creato ancora.",
        "Abrir builder": "Apri builder",
        "Arraste e solte": "Trascina e rilascia",
        "Cabeçalho": "Intestazione",
        "Corpo": "Corpo",
        "Rodapé": "Piè di pagina",
        "Editar": "Modifica",
        "Remover": "Rimuovi",
        "Título do bloco:": "Titolo del blocco:",
        "Pergunta salva": "Domanda salvata",
        "Falha ao salvar": "Salvataggio non riuscito",
        "Arraste aqui...": "Rilascia qui...",
        "Salvo": "Salvato",
        "Pergunta #{n}": "Domanda #{n}",
        "Fechar": "Chiudi",
        "Sucesso": "Successo",
        "Info": "Info",
        "Imagem": "Immagine",
        "Figura / logotipo / screenshot": "Figura / logo / screenshot",
        "Adicionar imagem": "Aggiungi immagine",
        "URL (https://...)": "URL (https://...)",
        "Isso cria um bloco “Imagem” no corpo do relatório.": "Questo crea un blocco “Immagine” nel corpo del report.",
        "URL da imagem:": "URL dell’immagine:",
        "Texto alternativo (alt):": "Testo alternativo (alt):",
        "Legenda (opcional):": "Didascalia (opzionale):",
        "Largura (ex.: 300px ou 50%):": "Larghezza (es.: 300px o 50%):",
        "Alinhamento (left/center/right):": "Allineamento (left/center/right):",
        "Cor do texto (ex.: #111 ou vazio):": "Colore testo (es.: #111 o vuoto):",
        "Cor de fundo (ex.: #fff ou vazio):": "Colore sfondo (es.: #fff o vuoto):",
        "Imagem não disponível": "Immagine non disponibile",
        "Texto (Markdown):": "Testo (Markdown):",
        "Texto:": "Testo:",
        "Bloco": "Blocco",
        "Erro ao executar pergunta: {error}": "Errore durante l’esecuzione della domanda: {error}",
        "Editar bloco": "Modifica blocco",
        "Título": "Titolo",
        "URL da imagem": "URL immagine",
        "https://...": "https://...",
        "Texto alternativo (alt)": "Testo alternativo (alt)",
        "Largura": "Larghezza",
        "ex.: 300px ou 50%": "es.: 300px o 50%",
        "Pré-visualização": "Anteprima",
        "Estilo": "Stile",
        "Cor do texto": "Colore testo",
        "Cor de fundo": "Colore di sfondo",
        "Sem": "Nessuno",
        "hex ou vazio": "hex o vuoto",
        "Aplicar": "Applica",
        "Esquerda": "Sinistra",
        "Centro": "Centro",
        "Direita": "Destra",
        "Padrão": "Predefinito",
        "Expandir": "Expand",
        "Renomear": "Rename",
        "Mover": "Move",
        "Destino": "Destination",
        "Arraste e solte para mover": "Drag & drop to move",
        "Upload e organização por pastas, com isolamento por tenant.": "Upload and organize by folders, isolated per tenant.",
        "Nova pasta": "New folder",
        "Importar URL": "Import URL",
        "Importar S3": "Import from S3",
        "Raiz": "Root",
        "Pesquisar...": "Search...",
        "Subir": "Up",
        "Pasta": "Folder",
        "Arquivo": "File",
        "Atualizado": "Updated",
        "Tamanho": "Size",
        "Baixar": "Download",
        "Excluir esta pasta e tudo dentro?": "Delete this folder and everything inside?",
        "Excluir este arquivo?": "Delete this file?",
        "Nada por aqui ainda.": "Nothing here yet.",
        "Faça upload ou importe arquivos para usar como datasource.": "Upload or import files to use as a data source.",
        "Você pode arrastar arquivos/pastas para outra pasta na árvore.": "You can drag files/folders to another folder in the tree.",
        "Itens": "Items",
        "Ex.: Financeiro": "e.g. Finance",
        "A pasta será criada dentro da pasta atual.": "The folder will be created inside the current folder.",
        "Nome (opcional)": "Name (optional)",
        "Nome amigável para o BI": "Friendly name for BI",
        "Formatos suportados": "Supported formats",
        "Nome do arquivo (opcional)": "Filename (optional)",
        "Nome amigável": "Friendly name",
        "A extensão determina o tipo (csv/xlsx/parquet).": "The extension determines the type (csv/xlsx/parquet).",
        "Bucket": "Bucket",
        "Região (opcional)": "Region (optional)",
        "Key (caminho no bucket)": "Key (path in bucket)",
        "Você também pode arrastar e soltar no painel de pastas.": "You can also drag & drop in the folders panel.",
        "Pasta criada.": "Folder created.",
        "Arquivo enviado.": "File uploaded.",
        "Arquivo importado da URL.": "File imported from URL.",
        "Arquivo importado do S3.": "File imported from S3.",
        "Arquivo removido.": "File removed.",
        "Pasta removida.": "Folder removed.",
        "Nome é obrigatório.": "Name is required.",
        "Arquivo renomeado.": "File renamed.",
        "Pasta renomeada.": "Folder renamed.",
        "Arquivo movido.": "File moved.",
        "Pasta movida.": "Folder moved.",
        "Movimento inválido.": "Invalid move.",

        # Workspaces (DuckDB + Files)
        "Novo workspace": "Nuovo workspace",
        "Workspace permite fazer JOIN entre arquivos (CSV/Excel/Parquet) e tabelas do banco, tudo em DuckDB.": "I workspace permettono di fare JOIN tra file (CSV/Excel/Parquet) e tabelle database, tutto in DuckDB.",
        "Configuração": "Configurazione",
        "Fonte de banco (opcional)": "Fonte database (opzionale)",
        "sem banco": "senza database",
        "Para JOIN com banco, selecione as tabelas. Elas ficam acessíveis como db.<tabela>.": "Per JOIN con il database, selezioni le tabelle. Sono accessibili come db.<tabella>.",
        "Tabelas do banco": "Tabelle del database",
        "Selecionar tabelas": "Seleziona tabelle",
        "Dica: use o Construtor rápido de JOIN para gerar um SQL inicial.": "Suggerimento: usa il Costruttore rapido di JOIN per generare un SQL iniziale.",
        "Limite de linhas": "Limite righe",
        "Usado para amostragem (segurança/performance).": "Usato per campionamento (sicurezza/performance).",
        "Abrir File Explorer": "Apri File Explorer",
        "Nenhum arquivo uploadado ainda. Use o menu Arquivos.": "Nessun file caricato ancora. Usa il menu File.",
        "Filtrar arquivos…": "Filtra file…",
        "Alias (tabela)": "Alias (tabella)",
        "Criar workspace": "Crea workspace",
        "Construtor rápido de JOIN": "Costruttore rapido di JOIN",
        "Selecione arquivos/tabelas e gere um SQL inicial com JOINs e autocomplete de colunas.": "Seleziona file/tabelle e genera un SQL iniziale con JOIN e autocomplete delle colonne.",
        "Selecione arquivos/tabelas": "Seleziona file/tabelle",
        "Tabela base": "Tabella base",
        "Sugestões de JOIN": "Suggerimenti JOIN",
        "JOINs": "JOIN",
        "Adicionar JOIN": "Aggiungi JOIN",
        "Coluna": "Colonna",
        "Gerar SQL com IA": "Genera SQL con IA",
        "Descreva sua análise": "Descrivi la tua analisi",
        "SQL inicial": "SQL iniziale",
        "Seu SQL aparecerá aqui…": "Il tuo SQL apparirà qui…",
        "Ao criar o workspace, este SQL fica salvo como rascunho (starter_sql) para você copiar no Editor SQL.": "Quando crei il workspace, questo SQL viene salvato come bozza (starter_sql) così puoi copiarlo nell'Editor SQL.",
        "Filtrar tabelas…": "Filtra tabelle…",
        "Nenhuma tabela encontrada.": "Nessuna tabella trovata.",
        "Selecione uma fonte de banco para listar tabelas.": "Seleziona una fonte database per elencare le tabelle.",
        "Falha ao carregar schema.": "Impossibile caricare lo schema.",
        "Selecione pelo menos duas tabelas para sugerir joins.": "Seleziona almeno due tabelle per suggerire JOIN.",
        "Nenhuma sugestão disponível.": "Nessun suggerimento disponibile.",
        "SQL gerado.": "SQL generato.",
        "Falha ao gerar SQL.": "Impossibile generare SQL.",
        "Schema: {name}": "Schema: {name}",
        "Ex.: BI - Vendas + Clientes": "Es.: BI - Vendite + Clienti",
        "Ex.: total de vendas por mês e segmento, com ticket médio": "Es.: vendite totali per mese e segmento, con ticket medio",
        "Workspace criado.": "Workspace creato.",

        "Ações": "Acciones",

    },
    "de": {
        "Accueil": "Start",
        "À propos": "Über uns",
        "Expertise": "Expertise",
        "Solutions": "Lösungen",
        "Pourquoi AUDELA": "Warum AUDELA",
        "Projets": "Projekte",
        "Plans BI": "BI-Pläne",
        "Área BI": "BI-Bereich",
        "Contact": "Kontakt",
        "Mobile": "Mobile",
        "IoT & Neuro": "IoT & Neuro",
        "BI & Metabase": "BI & Metabase",
        "BeLegal (LegalTech)": "BeLegal (LegalTech)",
        "Tous droits réservés.": "Alle Rechte vorbehalten.",

        # Index / landing
        "La technologie au service de la décision.": "Technologie zur Unterstützung von Entscheidungen.",
        "Data, BI, ERP, LegalTech & IA — au cœur de vos opérations.": "Daten, BI, ERP, LegalTech & KI — im Zentrum Ihrer Abläufe.",
        "Illustration AUDELA": "AUDELA-Illustration",
        "Next": "Weiter",
        "Grenoble & Alpes": "Grenoble & Alpen",
        "Au-delà des données": "Jenseits der Daten",
        "Transformer l'information en décisions — avec une ingénierie logicielle robuste et une compréhension métier réelle.": "Informationen in Entscheidungen verwandeln — mit robuster Softwareentwicklung und echtem Geschäftswissen.",
        "Nous construisons des systèmes qui tiennent dans la durée : pipelines data industrialisés, APIs fiables, applications web et mobile, et des dashboards compréhensibles par les équipes terrain comme par la direction.": "Wir bauen Systeme, die Bestand haben: industrialisierte Datenpipelines, zuverlässige APIs, Web- & Mobile-Apps und Dashboards, die sowohl von operativen Teams als auch von Führungskräften verstanden werden.",
        "Notre approche est pragmatique et \"production-first\" : sécurité, performance, observabilité, documentation, et transfert de compétences. L'objectif : livrer vite, sans dette technique.": "Unser Ansatz ist pragmatisch und production-first: Sicherheit, Performance, Observability, Dokumentation und Wissensübergabe. Ziel: schnell liefern, ohne technischen Schuldenberg.",
        "Business Intelligence": "Business Intelligence",
        "Analyse de données & Business Intelligence": "Datenanalyse & Business Intelligence",
        "Ingestion, modélisation, qualité et exposition : des indicateurs fiables, traçables et actionnables.": "Ingestion, Modellierung, Qualität und Bereitstellung: verlässliche, nachverfolgbare und handlungsfähige Kennzahlen.",
        "Nous connectons vos systèmes (ERP, CRM, finance, opérations, APIs), structurons la donnée (DWH/ELT), et livrons des tableaux de bord qui répondent à des questions concrètes : marge, performance commerciale, délais, risques, conformité.": "Wir verbinden Ihre Systeme (ERP, CRM, Finanzen, Operations, APIs), strukturieren die Daten (DWH/ELT) und liefern Dashboards, die konkrete Fragen beantworten: Marge, Vertriebsperformance, Durchlaufzeiten, Risiken, Compliance.",
        "Voir les écrans Metabase": "Metabase-Bildschirme anzeigen",
        "Plateformes métiers": "Fachliche Plattformen",
        "Plateformes métiers, ERP & IA appliquée": "Fachplattformen, ERP & angewandte KI",
        "Des outils métier qui reflètent vos workflows, avec une IA utile et explicable.": "Business-Tools, die Ihre Workflows abbilden, mit nützlicher und erklärbarer KI.",
        "Découvrir BeLegal": "BeLegal entdecken",

        # Home page
        "O que já está no MVP": "Was ist bereits im MVP",
        "Fontes por tenant (cadastro + introspecção)": "Datenquellen pro Mandant (Registrierung + Introspection)",
        "Editor SQL (execução ad-hoc com limites)": "SQL-Editor (Ad-hoc-Ausführung mit Limits)",
        "Perguntas (queries salvas) + execução": "Fragen (gespeicherte Abfragen) + Ausführung",
        "Dashboards (cards simples com perguntas)": "Dashboards (einfache Karten mit Fragen)",
        "Auditoria + Query Runs por tenant": "Audit + Query Runs pro Mandant",
        "Começar": "Erste Schritte",
        "Crie uma fonte": "Erstellen Sie eine Datenquelle unter Datenquellen → Neu",
        "Introspecte metadados na fonte (botão 'Introspectar')": "Metadaten in der Quelle introspizieren (Schaltfläche \"Introspect\")",
        "Teste uma consulta no Editor SQL": "Testen Sie eine Abfrage im SQL-Editor",
        "Salve uma Pergunta e crie um Dashboard": "Speichern Sie eine Frage und erstellen Sie ein Dashboard",
        "cadastro + introspecção": "Registrierung + Introspection",
        "execução ad-hoc com limites": "Ad-hoc-Ausführung mit Limits",
        "queries salvas": "gespeicherte Abfragen",
        "cards simples com perguntas": "einfache Karten mit Fragen",
        "por tenant": "pro Mandant",
        "Nova": "Neu",
        "e crie um": "und erstellen Sie ein",

        "Portal BI": "BI-Portal",
        "Usuário": "Benutzer",
        "Sair": "Abmelden",
        "Home": "Start",
        "Fontes": "Datenquellen",
        "Metadados": "Metadaten",
        "Editor SQL": "SQL-Editor",
        "Query Builder": "Query Builder",
        "Perguntas": "Fragen",
        "Dashboards": "Dashboards",
        "Execuções": "Ausführungen",
        "Auditoria": "Audit",
        "Voltar": "Zurück",
        "Cancelar": "Abbrechen",
        "Salvar": "Speichern",
        "Executar": "Ausführen",
        "Resultado": "Ergebnis",
        "Erro": "Fehler",
        "Linhas": "Zeilen",
        "Linhas retornadas": "Zurückgegebene Zeilen",
        "Nova pergunta": "Neue Frage",
        "Nova fonte": "Neue Quelle",
        "Criar": "Erstellen",
        "Dashboard": "Dashboard",
        "Nenhum card ainda. Crie um dashboard escolhendo perguntas.": "Noch keine Karten. Erstellen Sie ein Dashboard, indem Sie Fragen auswählen.",
        "Exportar PDF": "PDF exportieren",
        "Limpar filtros": "Filter löschen",
        "Filtros": "Filter",
        "Adicionar filtro": "Filter hinzufügen",
        "Visualização": "Visualisierung",
        "Configurar visualização": "Visualisierung konfigurieren",
        "Prévia": "Vorschau",
        "Tipo": "Typ",
        "Tabela": "Tabelle",
        "Gráfico": "Diagramm",
        "Pivot": "Pivot",
        "Gauges": "Anzeigen",
        "Drill down": "Drill-down",
        "Exportar": "Exportieren",
        "Gerar SQL": "SQL erzeugen",
        "Linguagem humana": "Natürliche Sprache",
        "Gerar": "Erzeugen",
        "Tabelas": "Tabellen",
        "Colunas": "Spalten",
        "Executar pergunta": "Frage ausführen",
        "Parâmetros (JSON)": "Parameter (JSON)",
        "Use :nome_param no SQL e preencha valores aqui. tenant_id é aplicado automaticamente.": "Verwenden Sie :param_name in SQL und tragen Sie hier die Werte ein. tenant_id wird automatisch angewendet.",
        "Gerar SQL no editor": "SQL im Editor erzeugen",
        "Fonte de dados": "Datenquelle",
        "Estrutura": "Schema",
        "Limite": "Limit",
        "montar SELECT com ajuda da estrutura": "SELECT mit Schema-Hilfe erstellen",
        "Escolha uma fonte para ver tabelas e colunas (autocomplete).": "Wählen Sie eine Quelle, um Tabellen und Spalten zu sehen (Autovervollständigung).",
        "Execute consultas ad-hoc, com autocomplete, Query Builder e linguagem humana.": "Führen Sie Ad-hoc-Abfragen mit Autovervollständigung, Query Builder und natürlicher Sprache aus.",
        "Sem linhas retornadas.": "Keine Zeilen zurückgegeben.",

        # UI+AI
        "Editar layout": "Layout bearbeiten",
        "Salvar layout": "Layout speichern",
        "Cancelar edição": "Bearbeitung abbrechen",
        "Layout salvo.": "Layout gespeichert.",
        "Falha ao salvar layout.": "Layout konnte nicht gespeichert werden.",
        "Modo edição": "Bearbeitungsmodus",
        "IA": "KI",
        "Chat IA": "KI-Chat",
        "Pergunte sobre os dados": "Fragen zu den Daten",
        "Selecione uma pergunta": "Wählen Sie eine Frage",
        "Enviar": "Senden",
        "Mensagem": "Nachricht",
        "Histórico": "Verlauf",
        "Limpar chat": "Chat leeren",
        "Gerando resposta...": "Antwort wird erstellt...",
        "Análise": "Analyse",
        "Gráficos sugeridos": "Vorgeschlagene Diagramme",
        "Sugestões de follow-up": "Follow-up-Vorschläge",
        "Chave OpenAI ausente. Defina OPENAI_API_KEY no servidor.": "OpenAI-Schlüssel fehlt. Setzen Sie OPENAI_API_KEY auf dem Server.",
        "Erro ao chamar IA: {error}": "KI-Aufruf fehlgeschlagen: {error}",
        "Tema": "Thema",
        "Claro": "Hell",
        "Escuro": "Dunkel",
        "Explorar": "Erkunden",
        "Explore dados e crie visualizações como no Superset/Metabase.": "Erkunden Sie Daten und erstellen Sie Visualisierungen wie in Superset/Metabase.",
        "Adicionar card": "Karte hinzufügen",
        "Remover card": "Karte entfernen",
        "Buscar pergunta": "Frage suchen",
        "Digite para filtrar...": "Zum Filtern tippen...",
        "Você pode refinar depois em Configurar visualização.": "Sie können später unter Visualisierung konfigurieren verfeinern.",
        "Atualizar": "Aktualisieren",
        "Salvar visualização": "Visualisierung speichern",
        "Visualização salva.": "Visualisierung gespeichert.",
        "Adicionar ao dashboard": "Zum Dashboard hinzufügen",
        "Cria um card no dashboard com esta visualização.": "Erstellt eine Karte im Dashboard mit dieser Visualisierung.",
        "Card adicionado ao dashboard.": "Karte zum Dashboard hinzugefügt.",
        "Card criado. Recarregando...": "Karte erstellt. Neu laden...",
        "Criando card...": "Karte wird erstellt...",
        "Remover card?": "Karte entfernen?",
        "Sem filtros.": "Keine Filter.",
        "Campo": "Feld",
        "Dimensão": "Dimension",
        "Métrica": "Metrik",
        "Drill-down": "Drill-down",
        "Clique no gráfico para filtrar por um valor.": "Klicken Sie auf das Diagramm, um nach einem Wert zu filtern.",
        "Pivot linhas": "Pivot-Zeilen",
        "Pivot colunas": "Pivot-Spalten",
        "Pivot valor": "Pivot-Wert",
        "Visuels & cas d’usage : Data, IA, ERP": "Visualisierungen & Anwendungsfälle: Data, KI, ERP",
        "Un aperçu des types de solutions que nous concevons : pilotage, automatisation et intelligence appliquée.": "Ein Einblick in die Arten von Lösungen, die wir entwickeln: operative Dashboards, Automatisierung und angewandte KI.",
        "Data & BI": "Daten & BI",
        "Tableaux de bord exécutifs, KPIs, gouvernance, qualité et traçabilité de bout en bout.": "Operative Dashboards, KPIs, Governance, Qualität und End-to-End-Traceability.",
        "IA appliquée": "Angewandte KI",
        "Détection d'anomalies, scoring de risques, assistants métiers et analyse prédictive.": "Anomalieerkennung, Risiko-Scoring, Business-Assistenten und prädiktive Analytik.",
        "ERP & workflows": "ERP & Workflows",
        "Workflows métiers, intégrations SI, automatisation, contrôles et auditabilité.": "Business-Workflows, Systemintegrationen, Automatisierung, Kontrollen und Auditierbarkeit.",
        "LegalTech": "LegalTech",
        "Gestion des dossiers, rentabilité par affaire, génération documentaire, conformité.": "Fallverwaltung, Mandatsrentabilität, Dokumentengenerierung, Compliance.",
        "Pourquoi AUDELA": "Warum AUDELA",
        "Une expertise de fond, une exécution rigoureuse, et une obsession de la qualité en production.": "Tiefe Expertise, rigorose Umsetzung und Fokus auf Produktionsqualität.",
        "Cloud-native, API-first, intégrations propres : une base solide pour durer et évoluer.": "Cloud-native, API-first, saubere Integrationen: eine solide Basis für Langlebigkeit und Skalierung.",
        "Conformité et gouvernance : contrôles d’accès, traçabilité, et bonnes pratiques SI.": "Compliance und Governance: Zugriffskontrollen, Nachvollziehbarkeit und IT-Best-Practices.",
        "Pipelines & qualité : de la source au tableau de bord, sans compromis sur les données.": "Pipelines & Qualität: Von der Quelle zum Dashboard ohne Kompromisse bei den Daten.",
        "CI/CD, monitoring, logs & alerting : stabilité, performance et mises en production rapides.": "CI/CD, Monitoring, Logs & Alerting: Stabilität, Performance und schnelle Deployments.",
        "Interopérabilité : connexion ERP/CRM/outils métiers, synchronisation et automatisation.": "Interoperabilität: ERP/CRM/Business-Tools-Anbindung, Synchronisierung und Automatisierung.",
        "Delivery et transfert : cadrage, documentation et montée en compétence de vos équipes.": "Delivery & Übergabe: Scoping, Dokumentation und Skill-Transfer an Ihre Teams.",
        "Découvrir nos plans BI": "Entdecken Sie unsere BI-Pläne",
        "Parlons de votre projet": "Sprechen wir über Ihr Projekt",
        "Décrivez votre besoin (Data/BI, ERP, LegalTech, IA, Mobile, IoT). Nous vous recontactons rapidement.": "Beschreiben Sie Ihr Anliegen (Data/BI, ERP, LegalTech, KI, Mobile, IoT). Wir melden uns schnell bei Ihnen.",
        "Votre adresse e-mail": "Ihre E-Mail-Adresse",
        "Être rappelé": "Zurückgerufen werden",
        "Carregando...": "Laden...",
        "OK": "OK",

        # Source diagram module
        "Source Diagram": "Quellendiagramm",
        "Select data source": "Datenquelle auswählen",
        "Load diagram": "Diagramm laden",
        "Refresh": "Aktualisieren",
        "Click a node to highlight relations. Use mousewheel to zoom.": "Klicken Sie auf einen Knoten, um Beziehungen hervorzuheben. Verwenden Sie das Mausrad zum Zoomen.",

        # Auth messages
        "Tenant não encontrado.": "Mandant nicht gefunden.",
        "Credenciais inválidas.": "Ungültige Anmeldedaten.",
        "Preencha todos os campos.": "Füllen Sie alle Felder aus.",
        "Slug já existe.": "Slug existiert bereits.",
        "Tenant criado. Faça login.": "Mandant erstellt. Bitte melden Sie sich an.",

        # Data source messages
        "Preencha nome, tipo e URL de conexão.": "Geben Sie Namen, Typ und Verbindungs-URL ein.",
        "Fonte criada.": "Datenquelle erstellt.",
        "Fonte removida.": "Datenquelle entfernt.",
        "Falha ao introspectar: {error}": "Introspektionsfehler: {error}",
        "Selecione uma fonte válida.": "Wählen Sie eine gültige Datenquelle.",
        "Selecione uma fonte.": "Wählen Sie eine Datenquelle.",
        "Fonte inválida.": "Ungültige Datenquelle.",

        # Data source test + form (wizard)
        "Informe uma URL de conexão.": "Geben Sie eine Verbindungs-URL an.",
        "Conexão OK.": "Verbindung OK.",
        "Falha na conexão.": "Verbindung fehlgeschlagen.",
        "Falha na conexão: {error}": "Verbindung fehlgeschlagen: {error}",
        "Nova fonte de dados": "Neue Datenquelle",
        "Configure uma nova origem de dados para consultas e relatórios.": "Konfigurieren Sie eine neue Datenquelle für Abfragen und Berichte.",
        "Informações básicas": "Grundinformationen",
        "Nome interno para identificar a fonte.": "Interner Name zur Identifikation der Quelle.",
        "Tipo de banco": "Datenbanktyp",
        "Conexão": "Verbindung",
        "Assistente": "Assistent",
        "URL manual": "Manuelle URL",
        "URL (manual)": "URL (manuell)",
        "Porta": "Port",
        "Database": "Datenbank",
        "Senha": "Passwort",
        "(opcional)": "(optional)",
        "(deixe vazio para manter)": "(leer lassen zum Beibehalten)",
        "Fica criptografado no config. Se preferir, cole uma URL pronta no modo \"URL manual\".": "Wird verschlüsselt in der Konfiguration gespeichert. Wenn Sie möchten, fügen Sie eine fertige URL im Modus \"Manuelle URL\" ein.",
        "Driver (SQL Server)": "Treiber (SQL Server)",
        "Service Name (Oracle)": "Service Name (Oracle)",
        "SID (Oracle)": "SID (Oracle)",
        "Arquivo SQLite": "SQLite-Datei",
        "Exemplo:": "Beispiel:",
        "ou apenas o caminho.": "oder nur der Pfad.",
        "URL gerada (SQLAlchemy)": "Generierte URL (SQLAlchemy)",
        "A URL abaixo será copiada para o campo \"URL manual\" automaticamente.": "Die URL unten wird automatisch in das Feld \"Manuelle URL\" kopiert.",
        "URL de conexão (SQLAlchemy)": "Verbindungs-URL (SQLAlchemy)",
        "SQLite local:": "Lokales SQLite:",
        "Config (descriptografado)": "Config (entschlüsselt)",
        "Copiar": "Kopieren",
        "Prévia do JSON que será criptografado ao salvar.": "Vorschau des JSON, das beim Speichern verschlüsselt wird.",
        "Opções avançadas": "Erweiterte Optionen",
        "Schema padrão": "Standard-Schema",
        "Schema usado por padrão nas consultas.": "Schema, das standardmäßig in Abfragen verwendet wird.",
        "Coluna tenant": "Tenant-Spalte",
        "Se preenchida, o SQL deve conter": "Wenn ausgefüllt, muss das SQL enthalten",
        "Testar conexão": "Verbindung testen",
        "Salvar fonte": "Quelle speichern",
        "Salvar alterações": "Änderungen speichern",
        "Atualize a conexão e as opções avançadas.": "Aktualisieren Sie die Verbindung und die erweiterten Optionen.",
        "Por segurança, a senha não é exibida. Se deixar vazio, manteremos a atual.": "Aus Sicherheitsgründen wird das Passwort nicht angezeigt. Wenn Sie es leer lassen, behalten wir das aktuelle.",
        "(padrão)": "(standard)",
        "URL SQLAlchemy (gerada)": "SQLAlchemy-URL (generiert)",
        "A URL abaixo também será salva no campo manual.": "Die URL unten wird auch im manuellen Feld gespeichert.",
        "Caminho do arquivo (SQLite)": "Dateipfad (SQLite)",
        "Pode usar um caminho absoluto, relativo, ou uma URL": "Sie können einen absoluten Pfad, einen relativen Pfad oder eine URL verwenden",

        # JS feedback
        "Copiado.": "Kopiert.",
        "Falha ao copiar.": "Kopieren fehlgeschlagen.",
        "Testando...": "Teste...",
        "Endpoint de teste não configurado.": "Test-Endpunkt ist nicht konfiguriert.",

        # Question messages
        "Preencha nome, fonte e SQL.": "Geben Sie Namen, Datenquelle und SQL ein.",
        "Pergunta criada.": "Frage erstellt.",
        "Pergunta removida.": "Frage entfernt.",

        # Dashboard messages
        "Dashboard criado.": "Dashboard erstellt.",
        "Dashboard removido.": "Dashboard entfernt.",
        "Dashboard definido como principal.": "Dashboard als primär festgelegt.",
        "Operação não suportada: execute as migrações do banco para habilitar essa função.": "Vorgang nicht unterstützt: Führen Sie Datenbankmigrationen durch, um diese Funktion zu aktivieren.",
        "Informe um nome.": "Geben Sie einen Namen ein.",

        # Configuration messages
        "Configuração inválida.": "Ungültige Konfiguration.",

        # User messages
        "Email e senha são obrigatórios.": "E-Mail und Passwort sind erforderlich.",
        "Usuário criado.": "Benutzer erstellt.",
        "Usuário removido.": "Benutzer entfernt.",

        # NLQ service messages
        "Não foi possível identificar uma tabela com segurança.": "Tabelle konnte nicht sicher identifiziert werden.",
        "Selecione uma tabela no Query Builder (à direita) ou escreva o SQL manualmente.": "Wählen Sie eine Tabelle im Query Builder (auf der rechten Seite) oder schreiben Sie SQL manuell.",
        "Tabela não identificada": "Tabelle nicht identifiziert",
        "Texto vazio": "Leerer Text",
        "Coluna métrica escolhida por fallback": "Metrik-Spalte als Fallback gewählt",
        "Coluna métrica não identificada": "Metrik-Spalte nicht identifiziert",

        # Home page
        "O que já está no MVP": "Was bereits im MVP vorhanden ist",
        "Fontes por tenant (cadastro + introspecção)": "Datenquellen pro Mandant (Registrierung + Introspection)",
        "Editor SQL (execução ad-hoc com limites)": "SQL-Editor (Ad-hoc-Ausführung mit Limits)",
        "Perguntas (queries salvas) + execução": "Fragen (gespeicherte Abfragen) + Ausführung",
        "Dashboards (cards simples com perguntas)": "Dashboards (einfache Karten mit Fragen)",
        "Auditoria + Query Runs por tenant": "Audit + Query-Ausführungen pro Mandant",
        "Começar": "Erste Schritte",
        "Crie uma fonte": "Erstellen Sie eine Datenquelle unter Quellen → Neu",
        "Introspecte metadados na fonte (botão 'Introspectar')": "Introspektieren Sie Metadaten auf der Quelle (Schaltfläche \"Introspect\")",
        "Teste uma consulta no Editor SQL": "Testen Sie eine Abfrage im SQL-Editor",
        "Salve uma Pergunta e crie um Dashboard": "Speichern Sie eine Frage und erstellen Sie ein Dashboard",
        "cadastro + introspecção": "Registrierung + Introspection",
        "execução ad-hoc com limites": "Ad-hoc-Ausführung mit Limits",
        "queries salvas": "gespeicherte Abfragen",
        "cards simples com perguntas": "einfache Karten mit Fragen",
        "por tenant": "pro Mandant",
        "Nova": "Neu",
        "e crie um": "und erstellen Sie ein",

        # Placeholder texts
        "Ex.: DW Produção": "Z.B.: DW Produktion",
        "Ex.: postgresql+psycopg2://user:pass@host:5432/dbname": "Z.B.: postgresql+psycopg2://user:pass@host:5432/dbname",
        "public": "public",
        "tenant_id": "tenant_id",
        "ex: total vendas por mês": "z.B.: Gesamtumsatz pro Monat",
        "acme": "acme",
        "you@example.com": "you@example.com",
        "tenant slug (ex.: acme)": "Mandanten-Slug (z.B.: acme)",
        "nome do tenant": "Name des Mandanten",
        "email do admin": "Administrator-E-Mail",
        "senha": "Passwort",
        "value": "Wert",
        "SELECT ...": "SELECT ...",

        # AI service prompts
        "You are a BI analyst": "Sie sind ein BI-Analyst",
        "You receive metadata and data sample": "Sie erhalten Metadaten und ein Datenmuster (Spalten/Zeilen) aus einer SQL-Frage",
        "Respond with clear insights": "Antworten Sie mit klaren Erkenntnissen, Hypothesen, Limitierungen und schlagen Sie Diagramme vor",
        "Your output MUST be valid JSON": "Ihre Ausgabe MUSS gültiges JSON sein (ohne Markdown, ohne Code-Blöcke) mit diesen Schlüsseln",
        "analysis key": "analysis: string (einfaches Markdown erlaubt, aber kein HTML)",
        "charts key": "charts: Liste von Objekten {title: string, echarts_option: object}",
        "followups key": "followups: Liste von Strings",
        "Use only the provided sample": "Verwenden Sie nur das bereitgestellte Muster und Profil; wenn etwas fehlt, sagen Sie es explizit",
        "For charts generate safe ECharts": "Generieren Sie für Diagramme sichere ECharts-Optionen ohne JS-Funktionen",
        "If insufficient data return empty": "Wenn nicht genügend Daten vorhanden sind, geben Sie charts=[] zurück und erklären Sie die Analyse",


        "Relatórios": "Berichte",
        "Novo relatório": "Neuer Bericht",
        "Construa relatórios com drag & drop (estilo Crystal Reports).": "Erstellen Sie Berichte per Drag & Drop (Crystal-Reports-Stil).",
        "Nenhum relatório criado ainda.": "Noch keine Berichte erstellt.",
        "Abrir builder": "Builder öffnen",
        "Arraste e solte": "Drag & Drop",
        "Cabeçalho": "Kopfzeile",
        "Corpo": "Inhalt",
        "Rodapé": "Fußzeile",
        "Editar": "Bearbeiten",
        "Remover": "Entfernen",
        "Título do bloco:": "Blocktitel:",
        "Pergunta salva": "Gespeicherte Frage",
        "Falha ao salvar": "Speichern fehlgeschlagen",
        "Arraste aqui...": "Hier ablegen...",
        "Salvo": "Gespeichert",
        "Pergunta #{n}": "Frage #{n}",
        "Fechar": "Schließen",
        "Sucesso": "Erfolg",
        "Info": "Info",
        "Imagem": "Bild",
        "Figura / logotipo / screenshot": "Abbildung / Logo / Screenshot",
        "Adicionar imagem": "Bild hinzufügen",
        "URL (https://...)": "URL (https://...)",
        "Isso cria um bloco “Imagem” no corpo do relatório.": "Dies erstellt einen „Bild“-Block im Berichtskörper.",
        "URL da imagem:": "Bild-URL:",
        "Texto alternativo (alt):": "Alternativtext (alt):",
        "Legenda (opcional):": "Bildunterschrift (optional):",
        "Largura (ex.: 300px ou 50%):": "Breite (z. B. 300px oder 50%):",
        "Alinhamento (left/center/right):": "Ausrichtung (left/center/right):",
        "Cor do texto (ex.: #111 ou vazio):": "Textfarbe (z. B. #111 oder leer):",
        "Cor de fundo (ex.: #fff ou vazio):": "Hintergrundfarbe (z. B. #fff oder leer):",
        "Imagem não disponível": "Bild nicht verfügbar",
        "Texto (Markdown):": "Text (Markdown):",
        "Texto:": "Text:",
        "Bloco": "Block",
        "Erro ao executar pergunta: {error}": "Fehler beim Ausführen der Frage: {error}",
        "Editar bloco": "Block bearbeiten",
        "Título": "Titel",
        "URL da imagem": "Bild-URL",
        "https://...": "https://...",
        "Texto alternativo (alt)": "Alternativtext (alt)",
        "Largura": "Breite",
        "ex.: 300px ou 50%": "z. B. 300px oder 50%",
        "Pré-visualização": "Vorschau",
        "Estilo": "Stil",
        "Cor do texto": "Textfarbe",
        "Cor de fundo": "Hintergrundfarbe",
        "Sem": "Keine",
        "hex ou vazio": "hex oder leer",
        "Aplicar": "Übernehmen",
        "Esquerda": "Links",
        "Centro": "Mitte",
        "Direita": "Rechts",
        "Padrão": "Standard",

        # Workspaces (DuckDB + Files)
        "Novo workspace": "Neuer Workspace",
        "Workspace permite fazer JOIN entre arquivos (CSV/Excel/Parquet) e tabelas do banco, tudo em DuckDB.": "Workspaces erlauben JOINs zwischen Dateien (CSV/Excel/Parquet) und Datenbanktabellen, alles in DuckDB.",
        "Configuração": "Konfiguration",
        "Fonte de banco (opcional)": "Datenquelle (optional)",
        "sem banco": "ohne Datenbank",
        "Para JOIN com banco, selecione as tabelas. Elas ficam acessíveis como db.<tabela>.": "Für DB-JOINs wählen Sie die Tabellen aus. Sie sind als db.<tabelle> verfügbar.",
        "Tabelas do banco": "Datenbanktabellen",
        "Selecionar tabelas": "Tabellen auswählen",
        "Dica: use o Construtor rápido de JOIN para gerar um SQL inicial.": "Tipp: Nutzen Sie den schnellen JOIN-Builder, um ein Start-SQL zu erzeugen.",
        "Limite de linhas": "Zeilenlimit",
        "Usado para amostragem (segurança/performance).": "Wird für Sampling genutzt (Sicherheit/Performance).",
        "Abrir File Explorer": "Datei-Explorer öffnen",
        "Nenhum arquivo uploadado ainda. Use o menu Arquivos.": "Noch keine Dateien hochgeladen. Nutzen Sie das Dateien-Menü.",
        "Filtrar arquivos…": "Dateien filtern…",
        "Alias (tabela)": "Alias (Tabelle)",
        "Criar workspace": "Workspace erstellen",
        "Construtor rápido de JOIN": "Schneller JOIN-Builder",
        "Selecione arquivos/tabelas e gere um SQL inicial com JOINs e autocomplete de colunas.": "Wählen Sie Dateien/Tabellen und erzeugen Sie ein Start-SQL mit JOINs und Spalten-Autocomplete.",
        "Selecione arquivos/tabelas": "Dateien/Tabellen auswählen",
        "Tabela base": "Basistabelle",
        "Sugestões de JOIN": "JOIN-Vorschläge",
        "JOINs": "JOINs",
        "Adicionar JOIN": "JOIN hinzufügen",
        "Coluna": "Spalte",
        "Gerar SQL com IA": "SQL mit KI erzeugen",
        "Descreva sua análise": "Beschreiben Sie Ihre Analyse",
        "SQL inicial": "Start-SQL",
        "Seu SQL aparecerá aqui…": "Ihr SQL erscheint hier…",
        "Ao criar o workspace, este SQL fica salvo como rascunho (starter_sql) para você copiar no Editor SQL.": "Beim Erstellen des Workspace wird dieses SQL als Entwurf (starter_sql) gespeichert, damit Sie es in den SQL-Editor kopieren können.",
        "Filtrar tabelas…": "Tabellen filtern…",
        "Nenhuma tabela encontrada.": "Keine Tabellen gefunden.",
        "Selecione uma fonte de banco para listar tabelas.": "Wählen Sie eine Datenquelle, um Tabellen aufzulisten.",
        "Falha ao carregar schema.": "Schema konnte nicht geladen werden.",
        "Selecione pelo menos duas tabelas para sugerir joins.": "Wählen Sie mindestens zwei Tabellen aus, um JOINs vorzuschlagen.",
        "Nenhuma sugestão disponível.": "Keine Vorschläge verfügbar.",
        "SQL gerado.": "SQL erzeugt.",
        "Falha ao gerar SQL.": "SQL konnte nicht erzeugt werden.",
        "Schema: {name}": "Schema: {name}",
        "Ex.: BI - Vendas + Clientes": "z. B. BI - Verkäufe + Kunden",
        "Ex.: total de vendas por mês e segmento, com ticket médio": "z. B. Gesamtumsatz pro Monat und Segment, mit durchschnittlichem Warenkorb",
        "Workspace criado.": "Workspace erstellt.",
    },
}


def normalize_lang(code: str | None) -> str:
    if not code:
        return DEFAULT_LANG
    code = (code or "").split("-")[0].lower()
    return code if code in SUPPORTED_LANGS else DEFAULT_LANG


def best_lang_from_accept_language(header: str | None) -> str:
    if not header:
        return DEFAULT_LANG
    # Very small parser: keep the first supported language in the header order.
    parts = [p.strip() for p in header.split(",") if p.strip()]
    for part in parts:
        lang = part.split(";")[0].strip()
        norm = normalize_lang(lang)
        if norm in SUPPORTED_LANGS:
            return norm
    return DEFAULT_LANG



# --- AUTO: Extra BI/ETL/Portal translations
_EXTRA_TRANSLATIONS = {'de': {'A extensão determina o tipo (csv/xlsx/parquet).': 'Die Dateiendung bestimmt den Typ (csv/xlsx/parquet).',
        'A pasta será criada dentro da pasta atual.': 'Der Ordner wird im aktuellen Ordner erstellt.',
        'Abrir': 'Öffnen',
        'Adicionar': 'Hinzufügen',
        'Adicionar passos': 'Schritte hinzufügen',
        'Adicionar pergunta': 'Frage hinzufügen',
        'Agregação': 'Aggregation',
        'Alinhamento': 'Ausrichtung',
        'Analisar': 'Analysieren',
        'Análise avançada: distribuição, correlação, regressão e Monte Carlo (amostra).': 'Erweiterte Analyse: '
                                                                                          'Verteilung, Korrelation, '
                                                                                          'Regression und Monte Carlo '
                                                                                          '(Stichprobe).',
        'Apenas na 1ª página': 'Nur auf der 1. Seite',
        'Apenas na última página': 'Nur auf der letzten Seite',
        'Area': 'Fläche',
        'Arquivo': 'Datei',
        'Arquivos': 'Dateien',
        'Arraste e solte para mover': 'Zum Verschieben ziehen und ablegen',
        'Atualizado': 'Aktualisiert',
        'Atualizado em': 'Aktualisiert am',
        'Aurora': 'Aurora',
        'Ações': 'Aktionen',
        'Baixar': 'Herunterladen',
        'Bandas tipo Crystal/DevExpress: Report Header (1ª página), Page Header (todas), Detail, Page Footer (todas), Report Footer (última). Clique no bloco para editar.': 'Crystal/DevExpress-Bänder: '
                                                                                                                                                                             'Berichtskopf '
                                                                                                                                                                             '(1. '
                                                                                                                                                                             'Seite), '
                                                                                                                                                                             'Seitenkopf '
                                                                                                                                                                             '(alle), '
                                                                                                                                                                             'Detail, '
                                                                                                                                                                             'Seitenfuß '
                                                                                                                                                                             '(alle), '
                                                                                                                                                                             'Berichtsfuß '
                                                                                                                                                                             '(letzte). '
                                                                                                                                                                             'Klicken '
                                                                                                                                                                             'Sie '
                                                                                                                                                                             'auf '
                                                                                                                                                                             'einen '
                                                                                                                                                                             'Block '
                                                                                                                                                                             'zum '
                                                                                                                                                                             'Bearbeiten.',
        'Bar': 'Balken',
        'Bucket': 'Bucket',
        'Cabeçalhos (JSON)': 'Header (JSON)',
        'Clique em um ponto/barra para filtrar o dashboard por esse valor.': 'Klicken Sie auf einen Punkt/Balken, um '
                                                                             'das Dashboard nach diesem Wert zu '
                                                                             'filtern.',
        'Colunas numéricas detectadas': 'Numerische Spalten erkannt',
        'Componentes': 'Komponenten',
        'Configurações': 'Einstellungen',
        'Conteúdo principal': 'Hauptinhalt',
        'Crie uma Pergunta e um Dashboard': 'Erstellen Sie eine Frage und ein Dashboard',
        'Dashboards recentes': 'Neueste Dashboards',
        'Data': 'Datum',
        'Data / data-hora (sistema)': 'Datum / Datum-Uhrzeit (System)',
        'Data e hora': 'Datum und Uhrzeit',
        'Decimais': 'Dezimalstellen',
        'Default': 'Standard',
        'Descrição': 'Beschreibung',
        'Destino': 'Ziel',
        'Detail': 'Detail',
        'Dica': 'Tipp',
        'Dica: campos JSON devem ser um JSON válido (ex: {"Authorization":"Bearer ..."}).': 'Tipp: JSON-Felder müssen '
                                                                                            'gültiges JSON sein (z. B. '
                                                                                            '{"Authorization":"Bearer '
                                                                                            '..."}).',
        'Dica: para pivot avançado use o tipo Pivot e personalize na tela.': 'Tipp: Für erweiterte Pivot-Ansichten den '
                                                                             'Typ Pivot verwenden und im Bildschirm '
                                                                             'anpassen.',
        'Duplo clique em um nó para editar a configuração. Conecte os nós na ordem Extract → Transform → Load. (MVP: fluxo linear)': 'Doppelklicken '
                                                                                                                                     'Sie '
                                                                                                                                     'auf '
                                                                                                                                     'einen '
                                                                                                                                     'Knoten, '
                                                                                                                                     'um '
                                                                                                                                     'die '
                                                                                                                                     'Konfiguration '
                                                                                                                                     'zu '
                                                                                                                                     'bearbeiten. '
                                                                                                                                     'Verbinden '
                                                                                                                                     'Sie '
                                                                                                                                     'die '
                                                                                                                                     'Knoten '
                                                                                                                                     'in '
                                                                                                                                     'der '
                                                                                                                                     'Reihenfolge '
                                                                                                                                     'Extract '
                                                                                                                                     '→ '
                                                                                                                                     'Transform '
                                                                                                                                     '→ '
                                                                                                                                     'Load. '
                                                                                                                                     '(MVP: '
                                                                                                                                     'linearer '
                                                                                                                                     'Ablauf)',
        'ETL': 'ETL',
        'ETL Builder': 'ETL-Builder',
        'ETLs': 'ETLs',
        'Erro ao carregar.': 'Fehler beim Laden.',
        'Escolha uma fonte de dados e depois monte o layout no builder.': 'Wählen Sie eine Datenquelle und erstellen '
                                                                          'Sie dann das Layout im Builder.',
        'Estatísticas': 'Statistiken',
        'Estatísticas descritivas': 'Deskriptive Statistiken',
        'Este é o dashboard padrão do seu tenant. Você pode alterá-lo na lista de dashboards.': 'Dies ist das '
                                                                                                'Standard-Dashboard '
                                                                                                'Ihres Tenants. Sie '
                                                                                                'können es in der '
                                                                                                'Dashboard-Liste '
                                                                                                'ändern.',
        'Ex.: API Vendas': 'z. B.: Sales-API',
        'Ex.: Financeiro': 'z. B.: Finanzen',
        'Excluir': 'Löschen',
        'Excluir esta pasta e tudo dentro?': 'Diesen Ordner und alles darin löschen?',
        'Excluir este arquivo?': 'Diese Datei löschen?',
        'Expandir': 'Erweitern',
        'Faça upload ou importe arquivos para usar como datasource.': 'Laden Sie Dateien hoch oder importieren Sie '
                                                                      'sie, um sie als Datenquelle zu verwenden.',
        'Fonte': 'Quelle',
        'Fontes API': 'API-Quellen',
        'Formato': 'Format',
        'Formatos suportados': 'Unterstützte Formate',
        'Gauge': 'Tacho',
        'Gráficos': 'Diagramme',
        'HTTP Extract': 'HTTP-Extraktion',
        'Importar': 'Importieren',
        'Importar S3': 'S3 importieren',
        'Importar URL': 'URL importieren',
        'Inserir': 'Einfügen',
        'Introspecte metadados na fonte (botão Introspectar).': 'Metadaten in der Quelle introspektieren (Schaltfläche '
                                                                '„Introspectar“).',
        'Isso cria um bloco “Imagem” no detalhe do relatório.': 'Dies erstellt einen „Bild“-Block im Detail des '
                                                                'Berichts.',
        'Isso cria um bloco “Pergunta” no detalhe do relatório.': 'Dies erstellt einen „Frage“-Block im Detail des '
                                                                  'Berichts.',
        'Itens': 'Elemente',
        'Key (caminho no bucket)': 'Key (Pfad im Bucket)',
        'Legenda (opcional)': 'Legende (optional)',
        'Line': 'Linie',
        'Linhas (amostra)': 'Zeilen (Stichprobe)',
        'Load (Warehouse)': 'Laden (Warehouse)',
        'Markdown': 'Markdown',
        'Monte Carlo': 'Monte Carlo',
        'Mover': 'Verschieben',
        'Nada por aqui ainda.': 'Hier gibt es noch nichts.',
        'Nenhum dashboard ainda.': 'Noch keine Dashboards.',
        'Nenhum workflow salvo.': 'Keine Workflows gespeichert.',
        'Nenhuma coluna numérica detectada na amostra.': 'Keine numerischen Spalten in der Stichprobe erkannt.',
        'Nenhuma fonte API cadastrada ainda.': 'Noch keine API-Quellen registriert.',
        'Nimbus': 'Nimbus',
        'Nome': 'Name',
        'Nome (opcional)': 'Name (optional)',
        'Nome amigável': 'Anzeigename',
        'Nome amigável para o BI': 'Anzeigename für BI',
        'Nome do arquivo (opcional)': 'Dateiname (optional)',
        'Nova fonte API': 'Neue API-Quelle',
        'Nova pasta': 'Neuer Ordner',
        'Novo workflow': 'Neuer Workflow',
        'Numeração de páginas no PDF': 'PDF-Seitennummerierung',
        'Observação para a IA (opcional)': 'Notiz für KI (optional)',
        'Onyx': 'Onyx',
        'Opcional': 'Optional',
        'Opcional. Exemplo: Authorization, Accept, X-API-Key, etc.': 'Optional. Beispiel: Authorization, Accept, '
                                                                     'X-API-Key, usw.',
        'Ou escolha uma pergunta': 'Oder wählen Sie eine Frage',
        'PDF': 'PDF',
        'Page Footer': 'Seitenfuß',
        'Page Header': 'Seitenkopf',
        'Parametros parametrizados devem ser passados via filtros ou definidos na Pergunta. tenant_id é aplicado automaticamente.': 'Parametrisierte '
                                                                                                                                    'Parameter '
                                                                                                                                    'müssen '
                                                                                                                                    'über '
                                                                                                                                    'Filter '
                                                                                                                                    'übergeben '
                                                                                                                                    'oder '
                                                                                                                                    'in '
                                                                                                                                    'der '
                                                                                                                                    'Frage '
                                                                                                                                    'definiert '
                                                                                                                                    'werden. '
                                                                                                                                    'tenant_id '
                                                                                                                                    'wird '
                                                                                                                                    'automatisch '
                                                                                                                                    'angewendet.',
        'Parâmetros': 'Parameter',
        'Pasta': 'Ordner',
        'Pastas': 'Ordner',
        'Pergunta': 'Frage',
        'Pesquisar...': 'Suchen...',
        'Pie': 'Torte',
        'Preview': 'Vorschau',
        'Preview (últimos resultados)': 'Vorschau (letzte Ergebnisse)',
        'Principal': 'Haupt',
        'Prob < 0': 'Prob < 0',
        'Raiz': 'Wurzel',
        'Reaproveita uma Pergunta salva': 'Gespeicherte Frage wiederverwenden',
        'Região (opcional)': 'Region (optional)',
        'Regressão linear': 'Lineare Regression',
        'Remover?': 'Entfernen?',
        'Renomear': 'Umbenennen',
        'Repete em todas as páginas': 'Auf allen Seiten wiederholen',
        'Repetir header': 'Kopfzeile wiederholen',
        'Report Builder': 'Report-Builder',
        'Report Footer': 'Berichtsfuß',
        'Report Header': 'Berichtskopf',
        'Resultados por coluna (amostra).': 'Ergebnisse nach Spalte (Stichprobe).',
        'Resumo (IA)': 'Zusammenfassung (KI)',
        'Rows / Cols / Value': 'Zeilen / Spalten / Wert',
        'SQL Extract': 'SQL-Extraktion',
        'Salvar workflow': 'Workflow speichern',
        'Scatter': 'Streuung',
        'Schema': 'Schema',
        'Se OPENAI_API_KEY estiver configurada, a IA gera um resumo executivo.': 'Wenn OPENAI_API_KEY konfiguriert '
                                                                                 'ist, erzeugt die KI eine Executive '
                                                                                 'Summary.',
        'Se a fonte exigir tenant, inclua :tenant_id no WHERE.': 'Wenn die Quelle einen Tenant erfordert, fügen Sie '
                                                                 ':tenant_id in der WHERE-Klausel hinzu.',
        'Selecione a fonte se for usar SQL manual.': 'Wählen Sie die Quelle, wenn Sie manuelles SQL verwenden.',
        'Sem gráficos para mostrar (faltam colunas numéricas).': 'Keine Diagramme anzuzeigen (keine numerischen '
                                                                 'Spalten).',
        'Simulação por coluna (amostra).': 'Simulation nach Spalte (Stichprobe).',
        'Simulações': 'Simulationen',
        'Subir': 'Hochladen',
        'Sugestões': 'Vorschläge',
        'Tabela/Gráfico de pergunta': 'Tabellen/Diagramm der Frage',
        'Tabelas e colunas da fonte (autocomplete).': 'Tabellen und Spalten der Quelle (Autovervollständigung).',
        'Tamanho': 'Größe',
        'Tema da tabela': 'Tabellenthema',
        'Texto': 'Text',
        'Texto com formatação': 'Formatierter Text',
        'Tipo de campo': 'Feldtyp',
        'Todos os dashboards': 'Alle Dashboards',
        'Transform': 'Transformieren',
        'Título / parágrafo simples': 'Titel / einfacher Absatz',
        'URL': 'URL',
        'URL base': 'Basis-URL',
        'Upload': 'Hochladen',
        'Upload e organização por pastas, com isolamento por tenant.': 'Upload und Ordnerorganisation, mit '
                                                                       'Tenant-Isolierung.',
        'Usa a fonte e o SQL salvos na pergunta.': 'Verwendet die in der Frage gespeicherte Quelle und das SQL.',
        'Use :nome_param no SQL. tenant_id é aplicado automaticamente.': 'Verwenden Sie :param_name im SQL. tenant_id '
                                                                         'wird automatisch angewendet.',
        'Use Ctrl+Space para autocomplete. Ctrl+Enter para executar.': 'Strg+Leertaste für Autovervollständigung. '
                                                                       'Strg+Enter zum Ausführen.',
        'Use {page} e {pages}.': 'Verwenden Sie {page} und {pages}.',
        'Use “Visualizar” para ver o relatório e “PDF” para exportar com cabeçalho/rodapé repetidos e número de página.': 'Verwenden '
                                                                                                                          'Sie '
                                                                                                                          '„Anzeigen“, '
                                                                                                                          'um '
                                                                                                                          'den '
                                                                                                                          'Bericht '
                                                                                                                          'zu '
                                                                                                                          'sehen, '
                                                                                                                          'und '
                                                                                                                          '„PDF“, '
                                                                                                                          'um '
                                                                                                                          'mit '
                                                                                                                          'wiederholter '
                                                                                                                          'Kopf-/Fußzeile '
                                                                                                                          'und '
                                                                                                                          'Seitennummern '
                                                                                                                          'zu '
                                                                                                                          'exportieren.',
        'Ver todos': 'Alle anzeigen',
        'Visualizar': 'Anzeigen',
        'Você pode arrastar arquivos/pastas para outra pasta na árvore.': 'Sie können Dateien/Ordner in einen anderen '
                                                                          'Ordner im Baum ziehen.',
        'Você também pode arrastar e soltar no painel de pastas.': 'Sie können auch im Ordner-Panel ziehen und '
                                                                   'ablegen.',
        'Zebra (linhas alternadas)': 'Zebra (abwechselnde Zeilen)'},
 'en': {'A extensão determina o tipo (csv/xlsx/parquet).': 'The extension determines the type (csv/xlsx/parquet).',
        'A pasta será criada dentro da pasta atual.': 'The folder will be created inside the current folder.',
        'Abrir': 'Open',
        'Adicionar': 'Add',
        'Adicionar passos': 'Add steps',
        'Adicionar pergunta': 'Add question',
        'Agregação': 'Aggregation',
        'Alinhamento': 'Alignment',
        'Analisar': 'Analyze',
        'Análise avançada: distribuição, correlação, regressão e Monte Carlo (amostra).': 'Advanced analysis: '
                                                                                          'distribution, correlation, '
                                                                                          'regression and Monte Carlo '
                                                                                          '(sample).',
        'Apenas na 1ª página': 'Only on the 1st page',
        'Apenas na última página': 'Only on the last page',
        'Area': 'Area',
        'Arquivo': 'File',
        'Arquivos': 'Files',
        'Arraste e solte para mover': 'Drag and drop to move',
        'Atualizado': 'Updated',
        'Atualizado em': 'Updated on',
        'Aurora': 'Aurora',
        'Ações': 'Actions',
        'Baixar': 'Download',
        'Bandas tipo Crystal/DevExpress: Report Header (1ª página), Page Header (todas), Detail, Page Footer (todas), Report Footer (última). Clique no bloco para editar.': 'Crystal/DevExpress-style '
                                                                                                                                                                             'bands: '
                                                                                                                                                                             'Report '
                                                                                                                                                                             'Header '
                                                                                                                                                                             '(1st '
                                                                                                                                                                             'page), '
                                                                                                                                                                             'Page '
                                                                                                                                                                             'Header '
                                                                                                                                                                             '(all '
                                                                                                                                                                             'pages), '
                                                                                                                                                                             'Detail, '
                                                                                                                                                                             'Page '
                                                                                                                                                                             'Footer '
                                                                                                                                                                             '(all '
                                                                                                                                                                             'pages), '
                                                                                                                                                                             'Report '
                                                                                                                                                                             'Footer '
                                                                                                                                                                             '(last '
                                                                                                                                                                             'page). '
                                                                                                                                                                             'Click '
                                                                                                                                                                             'a '
                                                                                                                                                                             'block '
                                                                                                                                                                             'to '
                                                                                                                                                                             'edit.',
        'Bar': 'Bar',
        'Bucket': 'Bucket',
        'Cabeçalhos (JSON)': 'Headers (JSON)',
        'Clique em um ponto/barra para filtrar o dashboard por esse valor.': 'Click a point/bar to filter the '
                                                                             'dashboard by this value.',
        'Colunas numéricas detectadas': 'Numeric columns detected',
        'Componentes': 'Components',
        'Configurações': 'Settings',
        'Conteúdo principal': 'Main content',
        'Crie uma Pergunta e um Dashboard': 'Create a Question and a Dashboard',
        'Dashboards recentes': 'Recent dashboards',
        'Data': 'Date',
        'Data / data-hora (sistema)': 'Date / date-time (system)',
        'Data e hora': 'Date and time',
        'Decimais': 'Decimals',
        'Default': 'Default',
        'Descrição': 'Description',
        'Destino': 'Destination',
        'Detail': 'Detail',
        'Dica': 'Tip',
        'Dica: campos JSON devem ser um JSON válido (ex: {"Authorization":"Bearer ..."}).': 'Tip: JSON fields must be '
                                                                                            'valid JSON (e.g. '
                                                                                            '{"Authorization":"Bearer '
                                                                                            '..."}).',
        'Dica: para pivot avançado use o tipo Pivot e personalize na tela.': 'Tip: for advanced pivot use the Pivot '
                                                                             'type and customize on the screen.',
        'Duplo clique em um nó para editar a configuração. Conecte os nós na ordem Extract → Transform → Load. (MVP: fluxo linear)': 'Double-click '
                                                                                                                                     'a '
                                                                                                                                     'node '
                                                                                                                                     'to '
                                                                                                                                     'edit '
                                                                                                                                     'its '
                                                                                                                                     'configuration. '
                                                                                                                                     'Connect '
                                                                                                                                     'nodes '
                                                                                                                                     'in '
                                                                                                                                     'order '
                                                                                                                                     'Extract '
                                                                                                                                     '→ '
                                                                                                                                     'Transform '
                                                                                                                                     '→ '
                                                                                                                                     'Load. '
                                                                                                                                     '(MVP: '
                                                                                                                                     'linear '
                                                                                                                                     'flow)',
        'ETL': 'ETL',
        'ETL Builder': 'ETL Builder',
        'ETLs': 'ETLs',
        'Erro ao carregar.': 'Error loading.',
        'Escolha uma fonte de dados e depois monte o layout no builder.': 'Choose a data source and then build the '
                                                                          'layout in the builder.',
        'Estatísticas': 'Statistics',
        'Estatísticas descritivas': 'Descriptive statistics',
        'Este é o dashboard padrão do seu tenant. Você pode alterá-lo na lista de dashboards.': "This is your tenant's "
                                                                                                'default dashboard. '
                                                                                                'You can change it in '
                                                                                                'the dashboards list.',
        'Ex.: API Vendas': 'e.g.: Sales API',
        'Ex.: Financeiro': 'e.g.: Finance',
        'Excluir': 'Delete',
        'Excluir esta pasta e tudo dentro?': 'Delete this folder and everything inside?',
        'Excluir este arquivo?': 'Delete this file?',
        'Expandir': 'Expand',
        'Faça upload ou importe arquivos para usar como datasource.': 'Upload or import files to use as a datasource.',
        'Fonte': 'Source',
        'Fontes API': 'API Sources',
        'Formato': 'Format',
        'Formatos suportados': 'Supported formats',
        'Gauge': 'Gauge',
        'Gráficos': 'Charts',
        'HTTP Extract': 'HTTP Extract',
        'Importar': 'Import',
        'Importar S3': 'Import S3',
        'Importar URL': 'Import URL',
        'Inserir': 'Insert',
        'Introspecte metadados na fonte (botão Introspectar).': 'Introspect metadata in the source ("Introspect" '
                                                                'button).',
        'Isso cria um bloco “Imagem” no detalhe do relatório.': 'This creates an “Image” block in the report detail.',
        'Isso cria um bloco “Pergunta” no detalhe do relatório.': 'This creates a “Question” block in the report '
                                                                  'detail.',
        'Itens': 'Items',
        'Key (caminho no bucket)': 'Key (path in bucket)',
        'Legenda (opcional)': 'Caption (optional)',
        'Line': 'Line',
        'Linhas (amostra)': 'Rows (sample)',
        'Load (Warehouse)': 'Load (Warehouse)',
        'Markdown': 'Markdown',
        'Monte Carlo': 'Monte Carlo',
        'Mover': 'Move',
        'Nada por aqui ainda.': 'Nothing here yet.',
        'Nenhum dashboard ainda.': 'No dashboards yet.',
        'Nenhum workflow salvo.': 'No workflows saved.',
        'Nenhuma coluna numérica detectada na amostra.': 'No numeric columns detected in the sample.',
        'Nenhuma fonte API cadastrada ainda.': 'No API sources registered yet.',
        'Nimbus': 'Nimbus',
        'Nome': 'Name',
        'Nome (opcional)': 'Name (optional)',
        'Nome amigável': 'Display name',
        'Nome amigável para o BI': 'Display name for BI',
        'Nome do arquivo (opcional)': 'File name (optional)',
        'Nova fonte API': 'New API source',
        'Nova pasta': 'New folder',
        'Novo workflow': 'New workflow',
        'Numeração de páginas no PDF': 'PDF page numbering',
        'Observação para a IA (opcional)': 'Note for AI (optional)',
        'Onyx': 'Onyx',
        'Opcional': 'Optional',
        'Opcional. Exemplo: Authorization, Accept, X-API-Key, etc.': 'Optional. Example: Authorization, Accept, '
                                                                     'X-API-Key, etc.',
        'Ou escolha uma pergunta': 'Or choose a question',
        'PDF': 'PDF',
        'Page Footer': 'Page Footer',
        'Page Header': 'Page Header',
        'Parametros parametrizados devem ser passados via filtros ou definidos na Pergunta. tenant_id é aplicado automaticamente.': 'Parameterized '
                                                                                                                                    'params '
                                                                                                                                    'must '
                                                                                                                                    'be '
                                                                                                                                    'passed '
                                                                                                                                    'via '
                                                                                                                                    'filters '
                                                                                                                                    'or '
                                                                                                                                    'defined '
                                                                                                                                    'in '
                                                                                                                                    'the '
                                                                                                                                    'Question. '
                                                                                                                                    'tenant_id '
                                                                                                                                    'is '
                                                                                                                                    'applied '
                                                                                                                                    'automatically.',
        'Parâmetros': 'Parameters',
        'Pasta': 'Folder',
        'Pastas': 'Folders',
        'Pergunta': 'Question',
        'Pesquisar...': 'Search...',
        'Pie': 'Pie',
        'Preview': 'Preview',
        'Preview (últimos resultados)': 'Preview (latest results)',
        'Principal': 'Main',
        'Prob < 0': 'Prob < 0',
        'Raiz': 'Root',
        'Reaproveita uma Pergunta salva': 'Reuse a saved Question',
        'Região (opcional)': 'Region (optional)',
        'Regressão linear': 'Linear regression',
        'Remover?': 'Remove?',
        'Renomear': 'Rename',
        'Repete em todas as páginas': 'Repeat on all pages',
        'Repetir header': 'Repeat header',
        'Report Builder': 'Report Builder',
        'Report Footer': 'Report Footer',
        'Report Header': 'Report Header',
        'Resultados por coluna (amostra).': 'Results by column (sample).',
        'Resumo (IA)': 'Summary (AI)',
        'Rows / Cols / Value': 'Rows / Cols / Value',
        'SQL Extract': 'SQL Extract',
        'Salvar workflow': 'Save workflow',
        'Scatter': 'Scatter',
        'Schema': 'Schema',
        'Se OPENAI_API_KEY estiver configurada, a IA gera um resumo executivo.': 'If OPENAI_API_KEY is configured, the '
                                                                                 'AI generates an executive summary.',
        'Se a fonte exigir tenant, inclua :tenant_id no WHERE.': 'If the source requires tenant, include :tenant_id in '
                                                                 'the WHERE.',
        'Selecione a fonte se for usar SQL manual.': 'Select the source if you will use manual SQL.',
        'Sem gráficos para mostrar (faltam colunas numéricas).': 'No charts to display (missing numeric columns).',
        'Simulação por coluna (amostra).': 'Simulation by column (sample).',
        'Simulações': 'Simulations',
        'Subir': 'Upload',
        'Sugestões': 'Suggestions',
        'Tabela/Gráfico de pergunta': 'Question table/chart',
        'Tabelas e colunas da fonte (autocomplete).': 'Tables and columns from the source (autocomplete).',
        'Tamanho': 'Size',
        'Tema da tabela': 'Table theme',
        'Texto': 'Text',
        'Texto com formatação': 'Formatted text',
        'Tipo de campo': 'Field type',
        'Todos os dashboards': 'All dashboards',
        'Transform': 'Transform',
        'Título / parágrafo simples': 'Title / simple paragraph',
        'URL': 'URL',
        'URL base': 'Base URL',
        'Upload': 'Upload',
        'Upload e organização por pastas, com isolamento por tenant.': 'Upload and folder organization, with tenant '
                                                                       'isolation.',
        'Usa a fonte e o SQL salvos na pergunta.': 'Uses the source and the SQL saved in the question.',
        'Use :nome_param no SQL. tenant_id é aplicado automaticamente.': 'Use :param_name in SQL. tenant_id is applied '
                                                                         'automatically.',
        'Use Ctrl+Space para autocomplete. Ctrl+Enter para executar.': 'Use Ctrl+Space for autocomplete. Ctrl+Enter to '
                                                                       'run.',
        'Use {page} e {pages}.': 'Use {page} and {pages}.',
        'Use “Visualizar” para ver o relatório e “PDF” para exportar com cabeçalho/rodapé repetidos e número de página.': 'Use '
                                                                                                                          '“View” '
                                                                                                                          'to '
                                                                                                                          'see '
                                                                                                                          'the '
                                                                                                                          'report '
                                                                                                                          'and '
                                                                                                                          '“PDF” '
                                                                                                                          'to '
                                                                                                                          'export '
                                                                                                                          'with '
                                                                                                                          'repeated '
                                                                                                                          'header/footer '
                                                                                                                          'and '
                                                                                                                          'page '
                                                                                                                          'numbers.',
        'Ver todos': 'View all',
        'Visualizar': 'View',
        'Você pode arrastar arquivos/pastas para outra pasta na árvore.': 'You can drag files/folders to another '
                                                                          'folder in the tree.',
        'Você também pode arrastar e soltar no painel de pastas.': 'You can also drag and drop into the folders panel.',
        'Zebra (linhas alternadas)': 'Zebra (alternating rows)'},
 'es': {'A extensão determina o tipo (csv/xlsx/parquet).': 'La extensión determina el tipo (csv/xlsx/parquet).',
        'A pasta será criada dentro da pasta atual.': 'La carpeta se creará dentro de la carpeta actual.',
        'Abrir': 'Abrir',
        'Adicionar': 'Añadir',
        'Adicionar passos': 'Añadir pasos',
        'Adicionar pergunta': 'Añadir pregunta',
        'Agregação': 'Agregación',
        'Alinhamento': 'Alineación',
        'Analisar': 'Analizar',
        'Análise avançada: distribuição, correlação, regressão e Monte Carlo (amostra).': 'Análisis avanzado: '
                                                                                          'distribución, correlación, '
                                                                                          'regresión y Monte Carlo '
                                                                                          '(muestra).',
        'Apenas na 1ª página': 'Solo en la 1.ª página',
        'Apenas na última página': 'Solo en la última página',
        'Area': 'Área',
        'Arquivo': 'Archivo',
        'Arquivos': 'Archivos',
        'Arraste e solte para mover': 'Arrastra y suelta para mover',
        'Atualizado': 'Actualizado',
        'Atualizado em': 'Actualizado el',
        'Aurora': 'Aurora',
        'Ações': 'Acciones',
        'Baixar': 'Descargar',
        'Bandas tipo Crystal/DevExpress: Report Header (1ª página), Page Header (todas), Detail, Page Footer (todas), Report Footer (última). Clique no bloco para editar.': 'Bandas '
                                                                                                                                                                             'estilo '
                                                                                                                                                                             'Crystal/DevExpress: '
                                                                                                                                                                             'Encabezado '
                                                                                                                                                                             'del '
                                                                                                                                                                             'informe '
                                                                                                                                                                             '(1.ª '
                                                                                                                                                                             'página), '
                                                                                                                                                                             'Encabezado '
                                                                                                                                                                             'de '
                                                                                                                                                                             'página '
                                                                                                                                                                             '(todas), '
                                                                                                                                                                             'Detalle, '
                                                                                                                                                                             'Pie '
                                                                                                                                                                             'de '
                                                                                                                                                                             'página '
                                                                                                                                                                             '(todas), '
                                                                                                                                                                             'Pie '
                                                                                                                                                                             'del '
                                                                                                                                                                             'informe '
                                                                                                                                                                             '(última). '
                                                                                                                                                                             'Haz '
                                                                                                                                                                             'clic '
                                                                                                                                                                             'en '
                                                                                                                                                                             'el '
                                                                                                                                                                             'bloque '
                                                                                                                                                                             'para '
                                                                                                                                                                             'editar.',
        'Bar': 'Barras',
        'Bucket': 'Bucket',
        'Cabeçalhos (JSON)': 'Encabezados (JSON)',
        'Clique em um ponto/barra para filtrar o dashboard por esse valor.': 'Haz clic en un punto/barra para filtrar '
                                                                             'el dashboard por este valor.',
        'Colunas numéricas detectadas': 'Columnas numéricas detectadas',
        'Componentes': 'Componentes',
        'Configurações': 'Configuración',
        'Conteúdo principal': 'Contenido principal',
        'Crie uma Pergunta e um Dashboard': 'Crea una Pregunta y un Dashboard',
        'Dashboards recentes': 'Dashboards recientes',
        'Data': 'Fecha',
        'Data / data-hora (sistema)': 'Fecha / fecha-hora (sistema)',
        'Data e hora': 'Fecha y hora',
        'Decimais': 'Decimales',
        'Default': 'Predeterminado',
        'Descrição': 'Descripción',
        'Destino': 'Destino',
        'Detail': 'Detalle',
        'Dica': 'Consejo',
        'Dica: campos JSON devem ser um JSON válido (ex: {"Authorization":"Bearer ..."}).': 'Consejo: los campos JSON '
                                                                                            'deben ser un JSON válido '
                                                                                            '(ej.: '
                                                                                            '{"Authorization":"Bearer '
                                                                                            '..."}).',
        'Dica: para pivot avançado use o tipo Pivot e personalize na tela.': 'Consejo: para un pivot avanzado usa el '
                                                                             'tipo Pivot y personaliza en la pantalla.',
        'Duplo clique em um nó para editar a configuração. Conecte os nós na ordem Extract → Transform → Load. (MVP: fluxo linear)': 'Doble '
                                                                                                                                     'clic '
                                                                                                                                     'en '
                                                                                                                                     'un '
                                                                                                                                     'nodo '
                                                                                                                                     'para '
                                                                                                                                     'editar '
                                                                                                                                     'su '
                                                                                                                                     'configuración. '
                                                                                                                                     'Conecta '
                                                                                                                                     'los '
                                                                                                                                     'nodos '
                                                                                                                                     'en '
                                                                                                                                     'el '
                                                                                                                                     'orden '
                                                                                                                                     'Extract '
                                                                                                                                     '→ '
                                                                                                                                     'Transform '
                                                                                                                                     '→ '
                                                                                                                                     'Load. '
                                                                                                                                     '(MVP: '
                                                                                                                                     'flujo '
                                                                                                                                     'lineal)',
        'ETL': 'ETL',
        'ETL Builder': 'Constructor ETL',
        'ETLs': 'ETLs',
        'Erro ao carregar.': 'Error al cargar.',
        'Escolha uma fonte de dados e depois monte o layout no builder.': 'Elige una fuente de datos y luego arma el '
                                                                          'diseño en el builder.',
        'Estatísticas': 'Estadísticas',
        'Estatísticas descritivas': 'Estadísticas descriptivas',
        'Este é o dashboard padrão do seu tenant. Você pode alterá-lo na lista de dashboards.': 'Este es el dashboard '
                                                                                                'predeterminado de tu '
                                                                                                'tenant. Puedes '
                                                                                                'cambiarlo en la lista '
                                                                                                'de dashboards.',
        'Ex.: API Vendas': 'Ej.: API Ventas',
        'Ex.: Financeiro': 'Ej.: Finanzas',
        'Excluir': 'Eliminar',
        'Excluir esta pasta e tudo dentro?': '¿Eliminar esta carpeta y todo lo que contiene?',
        'Excluir este arquivo?': '¿Eliminar este archivo?',
        'Expandir': 'Expandir',
        'Faça upload ou importe arquivos para usar como datasource.': 'Sube o importa archivos para usarlos como '
                                                                      'fuente de datos.',
        'Fonte': 'Fuente',
        'Fontes API': 'Fuentes API',
        'Formato': 'Formato',
        'Formatos suportados': 'Formatos compatibles',
        'Gauge': 'Indicador',
        'Gráficos': 'Gráficos',
        'HTTP Extract': 'Extracción HTTP',
        'Importar': 'Importar',
        'Importar S3': 'Importar S3',
        'Importar URL': 'Importar URL',
        'Inserir': 'Insertar',
        'Introspecte metadados na fonte (botão Introspectar).': 'Introspecta metadatos en la fuente (botón « '
                                                                'Introspectar »).',
        'Isso cria um bloco “Imagem” no detalhe do relatório.': 'Esto crea un bloque « Imagen » en el detalle del '
                                                                'informe.',
        'Isso cria um bloco “Pergunta” no detalhe do relatório.': 'Esto crea un bloque « Pregunta » en el detalle del '
                                                                  'informe.',
        'Itens': 'Ítems',
        'Key (caminho no bucket)': 'Clave (ruta en el bucket)',
        'Legenda (opcional)': 'Leyenda (opcional)',
        'Line': 'Línea',
        'Linhas (amostra)': 'Filas (muestra)',
        'Load (Warehouse)': 'Carga (Almacén)',
        'Markdown': 'Markdown',
        'Monte Carlo': 'Monte Carlo',
        'Mover': 'Mover',
        'Nada por aqui ainda.': 'Nada por aquí todavía.',
        'Nenhum dashboard ainda.': 'Aún no hay dashboards.',
        'Nenhum workflow salvo.': 'Ningún workflow guardado.',
        'Nenhuma coluna numérica detectada na amostra.': 'No se detectaron columnas numéricas en la muestra.',
        'Nenhuma fonte API cadastrada ainda.': 'Aún no hay fuentes API registradas.',
        'Nimbus': 'Nimbus',
        'Nome': 'Nombre',
        'Nome (opcional)': 'Nombre (opcional)',
        'Nome amigável': 'Nombre para mostrar',
        'Nome amigável para o BI': 'Nombre para BI',
        'Nome do arquivo (opcional)': 'Nombre de archivo (opcional)',
        'Nova fonte API': 'Nueva fuente API',
        'Nova pasta': 'Nueva carpeta',
        'Novo workflow': 'Nuevo workflow',
        'Numeração de páginas no PDF': 'Numeración de páginas en PDF',
        'Observação para a IA (opcional)': 'Nota para IA (opcional)',
        'Onyx': 'Onyx',
        'Opcional': 'Opcional',
        'Opcional. Exemplo: Authorization, Accept, X-API-Key, etc.': 'Opcional. Ejemplo: Authorization, Accept, '
                                                                     'X-API-Key, etc.',
        'Ou escolha uma pergunta': 'O elige una pregunta',
        'PDF': 'PDF',
        'Page Footer': 'Pie de página',
        'Page Header': 'Encabezado de página',
        'Parametros parametrizados devem ser passados via filtros ou definidos na Pergunta. tenant_id é aplicado automaticamente.': 'Los '
                                                                                                                                    'parámetros '
                                                                                                                                    'deben '
                                                                                                                                    'pasarse '
                                                                                                                                    'mediante '
                                                                                                                                    'filtros '
                                                                                                                                    'o '
                                                                                                                                    'definirse '
                                                                                                                                    'en '
                                                                                                                                    'la '
                                                                                                                                    'Pregunta. '
                                                                                                                                    'tenant_id '
                                                                                                                                    'se '
                                                                                                                                    'aplica '
                                                                                                                                    'automáticamente.',
        'Parâmetros': 'Parámetros',
        'Pasta': 'Carpeta',
        'Pastas': 'Carpetas',
        'Pergunta': 'Pregunta',
        'Pesquisar...': 'Buscar...',
        'Pie': 'Tarta',
        'Preview': 'Vista previa',
        'Preview (últimos resultados)': 'Vista previa (últimos resultados)',
        'Principal': 'Principal',
        'Prob < 0': 'Prob < 0',
        'Raiz': 'Raíz',
        'Reaproveita uma Pergunta salva': 'Reutiliza una Pregunta guardada',
        'Região (opcional)': 'Región (opcional)',
        'Regressão linear': 'Regresión lineal',
        'Remover?': '¿Eliminar?',
        'Renomear': 'Renombrar',
        'Repete em todas as páginas': 'Repetir en todas las páginas',
        'Repetir header': 'Repetir encabezado',
        'Report Builder': 'Constructor de informes',
        'Report Footer': 'Pie del informe',
        'Report Header': 'Encabezado del informe',
        'Resultados por coluna (amostra).': 'Resultados por columna (muestra).',
        'Resumo (IA)': 'Resumen (IA)',
        'Rows / Cols / Value': 'Filas / Columnas / Valor',
        'SQL Extract': 'Extracción SQL',
        'Salvar workflow': 'Guardar workflow',
        'Scatter': 'Dispersión',
        'Schema': 'Esquema',
        'Se OPENAI_API_KEY estiver configurada, a IA gera um resumo executivo.': 'Si OPENAI_API_KEY está configurada, '
                                                                                 'la IA genera un resumen ejecutivo.',
        'Se a fonte exigir tenant, inclua :tenant_id no WHERE.': 'Si la fuente requiere tenant, incluye :tenant_id en '
                                                                 'el WHERE.',
        'Selecione a fonte se for usar SQL manual.': 'Selecciona la fuente si vas a usar SQL manual.',
        'Sem gráficos para mostrar (faltam colunas numéricas).': 'No hay gráficos para mostrar (faltan columnas '
                                                                 'numéricas).',
        'Simulação por coluna (amostra).': 'Simulación por columna (muestra).',
        'Simulações': 'Simulaciones',
        'Subir': 'Subir',
        'Sugestões': 'Sugerencias',
        'Tabela/Gráfico de pergunta': 'Tabla/Gráfico de pregunta',
        'Tabelas e colunas da fonte (autocomplete).': 'Tablas y columnas de la fuente (autocompletar).',
        'Tamanho': 'Tamaño',
        'Tema da tabela': 'Tema de tabla',
        'Texto': 'Texto',
        'Texto com formatação': 'Texto con formato',
        'Tipo de campo': 'Tipo de campo',
        'Todos os dashboards': 'Todos los dashboards',
        'Transform': 'Transformación',
        'Título / parágrafo simples': 'Título / párrafo simple',
        'URL': 'URL',
        'URL base': 'URL base',
        'Upload': 'Subir',
        'Upload e organização por pastas, com isolamento por tenant.': 'Subida y organización por carpetas, con '
                                                                       'aislamiento por tenant.',
        'Usa a fonte e o SQL salvos na pergunta.': 'Usa la fuente y el SQL guardados en la pregunta.',
        'Use :nome_param no SQL. tenant_id é aplicado automaticamente.': 'Usa :nombre_param en el SQL. tenant_id se '
                                                                         'aplica automáticamente.',
        'Use Ctrl+Space para autocomplete. Ctrl+Enter para executar.': 'Usa Ctrl+Espacio para autocompletar. '
                                                                       'Ctrl+Enter para ejecutar.',
        'Use {page} e {pages}.': 'Usa {page} y {pages}.',
        'Use “Visualizar” para ver o relatório e “PDF” para exportar com cabeçalho/rodapé repetidos e número de página.': 'Usa '
                                                                                                                          '« '
                                                                                                                          'Ver '
                                                                                                                          '» '
                                                                                                                          'para '
                                                                                                                          'ver '
                                                                                                                          'el '
                                                                                                                          'informe '
                                                                                                                          'y '
                                                                                                                          '« '
                                                                                                                          'PDF '
                                                                                                                          '» '
                                                                                                                          'para '
                                                                                                                          'exportar '
                                                                                                                          'con '
                                                                                                                          'encabezado/pie '
                                                                                                                          'repetidos '
                                                                                                                          'y '
                                                                                                                          'número '
                                                                                                                          'de '
                                                                                                                          'página.',
        'Ver todos': 'Ver todo',
        'Visualizar': 'Ver',
        'Você pode arrastar arquivos/pastas para outra pasta na árvore.': 'Puedes arrastrar archivos/carpetas a otra '
                                                                          'carpeta en el árbol.',
        'Você também pode arrastar e soltar no painel de pastas.': 'También puedes arrastrar y soltar en el panel de '
                                                                   'carpetas.',
        'Zebra (linhas alternadas)': 'Cebra (filas alternas)'},
 'fr': {'A extensão determina o tipo (csv/xlsx/parquet).': 'L’extension détermine le type (csv/xlsx/parquet).',
        'A pasta será criada dentro da pasta atual.': 'Le dossier sera créé dans le dossier actuel.',
        'Abrir': 'Ouvrir',
        'Adicionar': 'Ajouter',
        'Adicionar passos': 'Ajouter des étapes',
        'Adicionar pergunta': 'Ajouter une question',
        'Agregação': 'Agrégation',
        'Alinhamento': 'Alignement',
        'Analisar': 'Analyser',
        'Análise avançada: distribuição, correlação, regressão e Monte Carlo (amostra).': 'Analyse avancée : '
                                                                                          'distribution, corrélation, '
                                                                                          'régression et Monte Carlo '
                                                                                          '(échantillon).',
        'Apenas na 1ª página': 'Uniquement sur la 1ʳᵉ page',
        'Apenas na última página': 'Uniquement sur la dernière page',
        'Area': 'Aire',
        'Arquivo': 'Fichier',
        'Arquivos': 'Fichiers',
        'Arraste e solte para mover': 'Glisser-déposer pour déplacer',
        'Atualizado': 'Mis à jour',
        'Atualizado em': 'Mis à jour le',
        'Aurora': 'Aurora',
        'Ações': 'Actions',
        'Baixar': 'Télécharger',
        'Bandas tipo Crystal/DevExpress: Report Header (1ª página), Page Header (todas), Detail, Page Footer (todas), Report Footer (última). Clique no bloco para editar.': 'Bandes '
                                                                                                                                                                             'type '
                                                                                                                                                                             'Crystal/DevExpress '
                                                                                                                                                                             ': '
                                                                                                                                                                             'En-tête '
                                                                                                                                                                             'de '
                                                                                                                                                                             'rapport '
                                                                                                                                                                             '(1ʳᵉ '
                                                                                                                                                                             'page), '
                                                                                                                                                                             'En-tête '
                                                                                                                                                                             'de '
                                                                                                                                                                             'page '
                                                                                                                                                                             '(toutes), '
                                                                                                                                                                             'Détail, '
                                                                                                                                                                             'Pied '
                                                                                                                                                                             'de '
                                                                                                                                                                             'page '
                                                                                                                                                                             '(toutes), '
                                                                                                                                                                             'Pied '
                                                                                                                                                                             'de '
                                                                                                                                                                             'rapport '
                                                                                                                                                                             '(dernière). '
                                                                                                                                                                             'Cliquez '
                                                                                                                                                                             'sur '
                                                                                                                                                                             'un '
                                                                                                                                                                             'bloc '
                                                                                                                                                                             'pour '
                                                                                                                                                                             'l’éditer.',
        'Bar': 'Barres',
        'Bucket': 'Bucket',
        'Cabeçalhos (JSON)': 'En-têtes (JSON)',
        'Clique em um ponto/barra para filtrar o dashboard por esse valor.': 'Cliquez sur un point/une barre pour '
                                                                             'filtrer le dashboard par cette valeur.',
        'Colunas numéricas detectadas': 'Colonnes numériques détectées',
        'Componentes': 'Composants',
        'Configurações': 'Paramètres',
        'Conteúdo principal': 'Contenu principal',
        'Crie uma Pergunta e um Dashboard': 'Créez une question et un dashboard',
        'Dashboards recentes': 'Dashboards récents',
        'Data': 'Date',
        'Data / data-hora (sistema)': 'Date / date-heure (système)',
        'Data e hora': 'Date et heure',
        'Decimais': 'Décimales',
        'Default': 'Par défaut',
        'Descrição': 'Description',
        'Destino': 'Destination',
        'Detail': 'Détail',
        'Dica': 'Astuce',
        'Dica: campos JSON devem ser um JSON válido (ex: {"Authorization":"Bearer ..."}).': 'Astuce : les champs JSON '
                                                                                            'doivent être un JSON '
                                                                                            'valide (ex : '
                                                                                            '{"Authorization":"Bearer '
                                                                                            '..."}).',
        'Dica: para pivot avançado use o tipo Pivot e personalize na tela.': 'Astuce : pour un pivot avancé, utilisez '
                                                                             'le type Pivot et personnalisez sur '
                                                                             'l’écran.',
        'Duplo clique em um nó para editar a configuração. Conecte os nós na ordem Extract → Transform → Load. (MVP: fluxo linear)': 'Double-cliquez '
                                                                                                                                     'sur '
                                                                                                                                     'un '
                                                                                                                                     'nœud '
                                                                                                                                     'pour '
                                                                                                                                     'éditer '
                                                                                                                                     'sa '
                                                                                                                                     'configuration. '
                                                                                                                                     'Connectez '
                                                                                                                                     'les '
                                                                                                                                     'nœuds '
                                                                                                                                     'dans '
                                                                                                                                     'l’ordre '
                                                                                                                                     'Extract '
                                                                                                                                     '→ '
                                                                                                                                     'Transform '
                                                                                                                                     '→ '
                                                                                                                                     'Load. '
                                                                                                                                     '(MVP '
                                                                                                                                     ': '
                                                                                                                                     'flux '
                                                                                                                                     'linéaire)',
        'ETL': 'ETL',
        'ETL Builder': 'Constructeur ETL',
        'ETLs': 'ETLs',
        'Erro ao carregar.': 'Erreur de chargement.',
        'Escolha uma fonte de dados e depois monte o layout no builder.': 'Choisissez une source de données puis '
                                                                          'composez la mise en page dans le builder.',
        'Estatísticas': 'Statistiques',
        'Estatísticas descritivas': 'Statistiques descriptives',
        'Este é o dashboard padrão do seu tenant. Você pode alterá-lo na lista de dashboards.': 'C’est le dashboard '
                                                                                                'par défaut de votre '
                                                                                                'tenant. Vous pouvez '
                                                                                                'le modifier dans la '
                                                                                                'liste des dashboards.',
        'Ex.: API Vendas': 'Ex. : API Ventes',
        'Ex.: Financeiro': 'Ex. : Finance',
        'Excluir': 'Supprimer',
        'Excluir esta pasta e tudo dentro?': 'Supprimer ce dossier et tout son contenu ?',
        'Excluir este arquivo?': 'Supprimer ce fichier ?',
        'Expandir': 'Développer',
        'Faça upload ou importe arquivos para usar como datasource.': 'Téléversez ou importez des fichiers pour les '
                                                                      'utiliser comme source de données.',
        'Fonte': 'Source',
        'Fontes API': 'Sources API',
        'Formato': 'Format',
        'Formatos suportados': 'Formats pris en charge',
        'Gauge': 'Jauge',
        'Gráficos': 'Graphiques',
        'HTTP Extract': 'Extraction HTTP',
        'Importar': 'Importer',
        'Importar S3': 'Importer S3',
        'Importar URL': 'Importer URL',
        'Inserir': 'Insérer',
        'Introspecte metadados na fonte (botão Introspectar).': 'Introspectez les métadonnées de la source (bouton « '
                                                                'Introspecter »).',
        'Isso cria um bloco “Imagem” no detalhe do relatório.': 'Cela crée un bloc « Image » dans le détail du '
                                                                'rapport.',
        'Isso cria um bloco “Pergunta” no detalhe do relatório.': 'Cela crée un bloc « Question » dans le détail du '
                                                                  'rapport.',
        'Itens': 'Éléments',
        'Key (caminho no bucket)': 'Clé (chemin dans le bucket)',
        'Legenda (opcional)': 'Légende (optionnel)',
        'Line': 'Ligne',
        'Linhas (amostra)': 'Lignes (échantillon)',
        'Load (Warehouse)': 'Chargement (Entrepôt)',
        'Markdown': 'Markdown',
        'Monte Carlo': 'Monte Carlo',
        'Mover': 'Déplacer',
        'Nada por aqui ainda.': 'Rien ici pour le moment.',
        'Nenhum dashboard ainda.': 'Aucun dashboard pour l’instant.',
        'Nenhum workflow salvo.': 'Aucun workflow enregistré.',
        'Nenhuma coluna numérica detectada na amostra.': 'Aucune colonne numérique détectée dans l’échantillon.',
        'Nenhuma fonte API cadastrada ainda.': 'Aucune source API enregistrée pour l’instant.',
        'Nimbus': 'Nimbus',
        'Nome': 'Nom',
        'Nome (opcional)': 'Nom (optionnel)',
        'Nome amigável': 'Nom d’affichage',
        'Nome amigável para o BI': 'Nom d’affichage pour le BI',
        'Nome do arquivo (opcional)': 'Nom du fichier (optionnel)',
        'Nova fonte API': 'Nouvelle source API',
        'Nova pasta': 'Nouveau dossier',
        'Novo workflow': 'Nouveau workflow',
        'Numeração de páginas no PDF': 'Numérotation des pages PDF',
        'Observação para a IA (opcional)': 'Note pour l’IA (optionnel)',
        'Onyx': 'Onyx',
        'Opcional': 'Optionnel',
        'Opcional. Exemplo: Authorization, Accept, X-API-Key, etc.': 'Optionnel. Exemple : Authorization, Accept, '
                                                                     'X-API-Key, etc.',
        'Ou escolha uma pergunta': 'Ou choisissez une question',
        'PDF': 'PDF',
        'Page Footer': 'Pied de page',
        'Page Header': 'En-tête de page',
        'Parametros parametrizados devem ser passados via filtros ou definidos na Pergunta. tenant_id é aplicado automaticamente.': 'Les '
                                                                                                                                    'paramètres '
                                                                                                                                    'doivent '
                                                                                                                                    'être '
                                                                                                                                    'passés '
                                                                                                                                    'via '
                                                                                                                                    'des '
                                                                                                                                    'filtres '
                                                                                                                                    'ou '
                                                                                                                                    'définis '
                                                                                                                                    'dans '
                                                                                                                                    'la '
                                                                                                                                    'question. '
                                                                                                                                    'tenant_id '
                                                                                                                                    'est '
                                                                                                                                    'appliqué '
                                                                                                                                    'automatiquement.',
        'Parâmetros': 'Paramètres',
        'Pasta': 'Dossier',
        'Pastas': 'Dossiers',
        'Pergunta': 'Question',
        'Pesquisar...': 'Rechercher...',
        'Pie': 'Camembert',
        'Preview': 'Aperçu',
        'Preview (últimos resultados)': 'Aperçu (derniers résultats)',
        'Principal': 'Principal',
        'Prob < 0': 'Prob < 0',
        'Raiz': 'Racine',
        'Reaproveita uma Pergunta salva': 'Réutilise une question enregistrée',
        'Região (opcional)': 'Région (optionnel)',
        'Regressão linear': 'Régression linéaire',
        'Remover?': 'Supprimer ?',
        'Renomear': 'Renommer',
        'Repete em todas as páginas': 'Répéter sur toutes les pages',
        'Repetir header': 'Répéter l’en-tête',
        'Report Builder': 'Concepteur de rapports',
        'Report Footer': 'Pied de rapport',
        'Report Header': 'En-tête de rapport',
        'Resultados por coluna (amostra).': 'Résultats par colonne (échantillon).',
        'Resumo (IA)': 'Résumé (IA)',
        'Rows / Cols / Value': 'Lignes / Colonnes / Valeur',
        'SQL Extract': 'Extraction SQL',
        'Salvar workflow': 'Enregistrer le workflow',
        'Scatter': 'Dispersion',
        'Schema': 'Schéma',
        'Se OPENAI_API_KEY estiver configurada, a IA gera um resumo executivo.': 'Si OPENAI_API_KEY est configurée, '
                                                                                 'l’IA génère un résumé exécutif.',
        'Se a fonte exigir tenant, inclua :tenant_id no WHERE.': 'Si la source exige un tenant, incluez :tenant_id '
                                                                 'dans le WHERE.',
        'Selecione a fonte se for usar SQL manual.': 'Sélectionnez la source si vous utilisez du SQL manuel.',
        'Sem gráficos para mostrar (faltam colunas numéricas).': 'Aucun graphique à afficher (colonnes numériques '
                                                                 'manquantes).',
        'Simulação por coluna (amostra).': 'Simulation par colonne (échantillon).',
        'Simulações': 'Simulations',
        'Subir': 'Téléverser',
        'Sugestões': 'Suggestions',
        'Tabela/Gráfico de pergunta': 'Tableau/graphique de question',
        'Tabelas e colunas da fonte (autocomplete).': 'Tables et colonnes de la source (auto-complétion).',
        'Tamanho': 'Taille',
        'Tema da tabela': 'Thème de tableau',
        'Texto': 'Texte',
        'Texto com formatação': 'Texte formaté',
        'Tipo de campo': 'Type de champ',
        'Todos os dashboards': 'Tous les dashboards',
        'Transform': 'Transformation',
        'Título / parágrafo simples': 'Titre / paragraphe simple',
        'URL': 'URL',
        'URL base': 'URL de base',
        'Upload': 'Téléverser',
        'Upload e organização por pastas, com isolamento por tenant.': 'Téléversement et organisation par dossiers, '
                                                                       'avec isolation par tenant.',
        'Usa a fonte e o SQL salvos na pergunta.': 'Utilise la source et le SQL enregistrés dans la question.',
        'Use :nome_param no SQL. tenant_id é aplicado automaticamente.': 'Utilisez :nom_param dans le SQL. tenant_id '
                                                                         'est appliqué automatiquement.',
        'Use Ctrl+Space para autocomplete. Ctrl+Enter para executar.': 'Utilisez Ctrl+Espace pour l’auto-complétion. '
                                                                       'Ctrl+Entrée pour exécuter.',
        'Use {page} e {pages}.': 'Utilisez {page} et {pages}.',
        'Use “Visualizar” para ver o relatório e “PDF” para exportar com cabeçalho/rodapé repetidos e número de página.': 'Utilisez '
                                                                                                                          '« '
                                                                                                                          'Voir '
                                                                                                                          '» '
                                                                                                                          'pour '
                                                                                                                          'afficher '
                                                                                                                          'le '
                                                                                                                          'rapport '
                                                                                                                          'et '
                                                                                                                          '« '
                                                                                                                          'PDF '
                                                                                                                          '» '
                                                                                                                          'pour '
                                                                                                                          'exporter '
                                                                                                                          'avec '
                                                                                                                          'en-tête/pied '
                                                                                                                          'répétés '
                                                                                                                          'et '
                                                                                                                          'numérotation '
                                                                                                                          'des '
                                                                                                                          'pages.',
        'Ver todos': 'Voir tout',
        'Visualizar': 'Voir',
        'Você pode arrastar arquivos/pastas para outra pasta na árvore.': 'Vous pouvez glisser-déposer des '
                                                                          'fichiers/dossiers vers un autre dossier '
                                                                          'dans l’arborescence.',
        'Você também pode arrastar e soltar no painel de pastas.': 'Vous pouvez aussi glisser-déposer dans le panneau '
                                                                   'des dossiers.',
        'Zebra (linhas alternadas)': 'Zébrage (lignes alternées)'},
 'it': {'A extensão determina o tipo (csv/xlsx/parquet).': 'L’estensione determina il tipo (csv/xlsx/parquet).',
        'A pasta será criada dentro da pasta atual.': 'La cartella verrà creata nella cartella corrente.',
        'Abrir': 'Apri',
        'Adicionar': 'Aggiungi',
        'Adicionar passos': 'Aggiungi passaggi',
        'Adicionar pergunta': 'Aggiungi domanda',
        'Agregação': 'Aggregazione',
        'Alinhamento': 'Allineamento',
        'Analisar': 'Analizza',
        'Análise avançada: distribuição, correlação, regressão e Monte Carlo (amostra).': 'Analisi avanzata: '
                                                                                          'distribuzione, '
                                                                                          'correlazione, regressione e '
                                                                                          'Monte Carlo (campione).',
        'Apenas na 1ª página': 'Solo nella 1ª pagina',
        'Apenas na última página': 'Solo nell’ultima pagina',
        'Area': 'Area',
        'Arquivo': 'File',
        'Arquivos': 'File',
        'Arraste e solte para mover': 'Trascina e rilascia per spostare',
        'Atualizado': 'Aggiornato',
        'Atualizado em': 'Aggiornato il',
        'Aurora': 'Aurora',
        'Ações': 'Azioni',
        'Baixar': 'Scarica',
        'Bandas tipo Crystal/DevExpress: Report Header (1ª página), Page Header (todas), Detail, Page Footer (todas), Report Footer (última). Clique no bloco para editar.': 'Bande '
                                                                                                                                                                             'stile '
                                                                                                                                                                             'Crystal/DevExpress: '
                                                                                                                                                                             'Intestazione '
                                                                                                                                                                             'report '
                                                                                                                                                                             '(1ª '
                                                                                                                                                                             'pagina), '
                                                                                                                                                                             'Intestazione '
                                                                                                                                                                             'pagina '
                                                                                                                                                                             '(tutte), '
                                                                                                                                                                             'Dettaglio, '
                                                                                                                                                                             'Piè '
                                                                                                                                                                             'di '
                                                                                                                                                                             'pagina '
                                                                                                                                                                             '(tutte), '
                                                                                                                                                                             'Piè '
                                                                                                                                                                             'del '
                                                                                                                                                                             'report '
                                                                                                                                                                             '(ultima). '
                                                                                                                                                                             'Clicca '
                                                                                                                                                                             'sul '
                                                                                                                                                                             'blocco '
                                                                                                                                                                             'per '
                                                                                                                                                                             'modificare.',
        'Bar': 'Barre',
        'Bucket': 'Bucket',
        'Cabeçalhos (JSON)': 'Intestazioni (JSON)',
        'Clique em um ponto/barra para filtrar o dashboard por esse valor.': 'Clicca su un punto/barra per filtrare la '
                                                                             'dashboard con questo valore.',
        'Colunas numéricas detectadas': 'Colonne numeriche rilevate',
        'Componentes': 'Componenti',
        'Configurações': 'Impostazioni',
        'Conteúdo principal': 'Contenuto principale',
        'Crie uma Pergunta e um Dashboard': 'Crea una Domanda e una Dashboard',
        'Dashboards recentes': 'Dashboard recenti',
        'Data': 'Data',
        'Data / data-hora (sistema)': 'Data / data-ora (sistema)',
        'Data e hora': 'Data e ora',
        'Decimais': 'Decimali',
        'Default': 'Predefinito',
        'Descrição': 'Descrizione',
        'Destino': 'Destinazione',
        'Detail': 'Dettaglio',
        'Dica': 'Suggerimento',
        'Dica: campos JSON devem ser um JSON válido (ex: {"Authorization":"Bearer ..."}).': 'Suggerimento: i campi '
                                                                                            'JSON devono essere un '
                                                                                            'JSON valido (es.: '
                                                                                            '{"Authorization":"Bearer '
                                                                                            '..."}).',
        'Dica: para pivot avançado use o tipo Pivot e personalize na tela.': 'Suggerimento: per un pivot avanzato usa '
                                                                             'il tipo Pivot e personalizza nella '
                                                                             'schermata.',
        'Duplo clique em um nó para editar a configuração. Conecte os nós na ordem Extract → Transform → Load. (MVP: fluxo linear)': 'Doppio '
                                                                                                                                     'clic '
                                                                                                                                     'su '
                                                                                                                                     'un '
                                                                                                                                     'nodo '
                                                                                                                                     'per '
                                                                                                                                     'modificare '
                                                                                                                                     'la '
                                                                                                                                     'configurazione. '
                                                                                                                                     'Collega '
                                                                                                                                     'i '
                                                                                                                                     'nodi '
                                                                                                                                     'nell’ordine '
                                                                                                                                     'Extract '
                                                                                                                                     '→ '
                                                                                                                                     'Transform '
                                                                                                                                     '→ '
                                                                                                                                     'Load. '
                                                                                                                                     '(MVP: '
                                                                                                                                     'flusso '
                                                                                                                                     'lineare)',
        'ETL': 'ETL',
        'ETL Builder': 'Builder ETL',
        'ETLs': 'ETLs',
        'Erro ao carregar.': 'Errore durante il caricamento.',
        'Escolha uma fonte de dados e depois monte o layout no builder.': 'Scegli una fonte dati e poi componi il '
                                                                          'layout nel builder.',
        'Estatísticas': 'Statistiche',
        'Estatísticas descritivas': 'Statistiche descrittive',
        'Este é o dashboard padrão do seu tenant. Você pode alterá-lo na lista de dashboards.': 'Questa è la dashboard '
                                                                                                'predefinita del tuo '
                                                                                                'tenant. Puoi '
                                                                                                'modificarla nella '
                                                                                                'lista delle '
                                                                                                'dashboard.',
        'Ex.: API Vendas': 'Es.: API Vendite',
        'Ex.: Financeiro': 'Es.: Finanza',
        'Excluir': 'Elimina',
        'Excluir esta pasta e tudo dentro?': 'Eliminare questa cartella e tutto il contenuto?',
        'Excluir este arquivo?': 'Eliminare questo file?',
        'Expandir': 'Espandi',
        'Faça upload ou importe arquivos para usar como datasource.': 'Carica o importa file per usarli come sorgente '
                                                                      'dati.',
        'Fonte': 'Fonte',
        'Fontes API': 'Sorgenti API',
        'Formato': 'Formato',
        'Formatos suportados': 'Formati supportati',
        'Gauge': 'Indicatore',
        'Gráficos': 'Grafici',
        'HTTP Extract': 'Estrazione HTTP',
        'Importar': 'Importa',
        'Importar S3': 'Importa S3',
        'Importar URL': 'Importa URL',
        'Inserir': 'Inserisci',
        'Introspecte metadados na fonte (botão Introspectar).': 'Introspeziona i metadati nella fonte (pulsante « '
                                                                'Introspectar »).',
        'Isso cria um bloco “Imagem” no detalhe do relatório.': 'Questo crea un blocco « Immagine » nel dettaglio del '
                                                                'report.',
        'Isso cria um bloco “Pergunta” no detalhe do relatório.': 'Questo crea un blocco « Domanda » nel dettaglio del '
                                                                  'report.',
        'Itens': 'Elementi',
        'Key (caminho no bucket)': 'Chiave (percorso nel bucket)',
        'Legenda (opcional)': 'Didascalia (opzionale)',
        'Line': 'Linea',
        'Linhas (amostra)': 'Righe (campione)',
        'Load (Warehouse)': 'Caricamento (Warehouse)',
        'Markdown': 'Markdown',
        'Monte Carlo': 'Monte Carlo',
        'Mover': 'Sposta',
        'Nada por aqui ainda.': 'Niente qui per ora.',
        'Nenhum dashboard ainda.': 'Nessuna dashboard ancora.',
        'Nenhum workflow salvo.': 'Nessun workflow salvato.',
        'Nenhuma coluna numérica detectada na amostra.': 'Nessuna colonna numerica rilevata nel campione.',
        'Nenhuma fonte API cadastrada ainda.': 'Nessuna sorgente API registrata.',
        'Nimbus': 'Nimbus',
        'Nome': 'Nome',
        'Nome (opcional)': 'Nome (opzionale)',
        'Nome amigável': 'Nome visualizzato',
        'Nome amigável para o BI': 'Nome per BI',
        'Nome do arquivo (opcional)': 'Nome file (opzionale)',
        'Nova fonte API': 'Nuova sorgente API',
        'Nova pasta': 'Nuova cartella',
        'Novo workflow': 'Nuovo workflow',
        'Numeração de páginas no PDF': 'Numerazione pagine PDF',
        'Observação para a IA (opcional)': 'Nota per l’IA (opzionale)',
        'Onyx': 'Onyx',
        'Opcional': 'Opzionale',
        'Opcional. Exemplo: Authorization, Accept, X-API-Key, etc.': 'Opzionale. Esempio: Authorization, Accept, '
                                                                     'X-API-Key, ecc.',
        'Ou escolha uma pergunta': 'Oppure scegli una domanda',
        'PDF': 'PDF',
        'Page Footer': 'Piè di pagina',
        'Page Header': 'Intestazione pagina',
        'Parametros parametrizados devem ser passados via filtros ou definidos na Pergunta. tenant_id é aplicado automaticamente.': 'I '
                                                                                                                                    'parametri '
                                                                                                                                    'devono '
                                                                                                                                    'essere '
                                                                                                                                    'passati '
                                                                                                                                    'tramite '
                                                                                                                                    'filtri '
                                                                                                                                    'o '
                                                                                                                                    'definiti '
                                                                                                                                    'nella '
                                                                                                                                    'Domanda. '
                                                                                                                                    'tenant_id '
                                                                                                                                    'viene '
                                                                                                                                    'applicato '
                                                                                                                                    'automaticamente.',
        'Parâmetros': 'Parametri',
        'Pasta': 'Cartella',
        'Pastas': 'Cartelle',
        'Pergunta': 'Domanda',
        'Pesquisar...': 'Cerca...',
        'Pie': 'Torta',
        'Preview': 'Anteprima',
        'Preview (últimos resultados)': 'Anteprima (ultimi risultati)',
        'Principal': 'Principale',
        'Prob < 0': 'Prob < 0',
        'Raiz': 'Radice',
        'Reaproveita uma Pergunta salva': 'Riutilizza una domanda salvata',
        'Região (opcional)': 'Regione (opzionale)',
        'Regressão linear': 'Regressione lineare',
        'Remover?': 'Rimuovere?',
        'Renomear': 'Rinomina',
        'Repete em todas as páginas': 'Ripeti su tutte le pagine',
        'Repetir header': 'Ripeti intestazione',
        'Report Builder': 'Report Builder',
        'Report Footer': 'Piè del report',
        'Report Header': 'Intestazione del report',
        'Resultados por coluna (amostra).': 'Risultati per colonna (campione).',
        'Resumo (IA)': 'Riepilogo (IA)',
        'Rows / Cols / Value': 'Righe / Colonne / Valore',
        'SQL Extract': 'Estrazione SQL',
        'Salvar workflow': 'Salva workflow',
        'Scatter': 'Dispersione',
        'Schema': 'Schema',
        'Se OPENAI_API_KEY estiver configurada, a IA gera um resumo executivo.': 'Se OPENAI_API_KEY è configurata, '
                                                                                 'l’IA genera un riepilogo esecutivo.',
        'Se a fonte exigir tenant, inclua :tenant_id no WHERE.': 'Se la fonte richiede tenant, includi :tenant_id nel '
                                                                 'WHERE.',
        'Selecione a fonte se for usar SQL manual.': 'Seleziona la fonte se userai SQL manuale.',
        'Sem gráficos para mostrar (faltam colunas numéricas).': 'Nessun grafico da mostrare (mancano colonne '
                                                                 'numeriche).',
        'Simulação por coluna (amostra).': 'Simulazione per colonna (campione).',
        'Simulações': 'Simulazioni',
        'Subir': 'Carica',
        'Sugestões': 'Suggerimenti',
        'Tabela/Gráfico de pergunta': 'Tabella/Grafico domanda',
        'Tabelas e colunas da fonte (autocomplete).': 'Tabelle e colonne della fonte (autocomplete).',
        'Tamanho': 'Dimensione',
        'Tema da tabela': 'Tema tabella',
        'Texto': 'Testo',
        'Texto com formatação': 'Testo formattato',
        'Tipo de campo': 'Tipo di campo',
        'Todos os dashboards': 'Tutte le dashboard',
        'Transform': 'Trasformazione',
        'Título / parágrafo simples': 'Titolo / paragrafo semplice',
        'URL': 'URL',
        'URL base': 'URL di base',
        'Upload': 'Carica',
        'Upload e organização por pastas, com isolamento por tenant.': 'Upload e organizzazione per cartelle, con '
                                                                       'isolamento per tenant.',
        'Usa a fonte e o SQL salvos na pergunta.': "Usa la fonte e l'SQL salvati nella domanda.",
        'Use :nome_param no SQL. tenant_id é aplicado automaticamente.': 'Usa :nome_param nello SQL. tenant_id viene '
                                                                         'applicato automaticamente.',
        'Use Ctrl+Space para autocomplete. Ctrl+Enter para executar.': 'Usa Ctrl+Spazio per l’autocomplete. Ctrl+Invio '
                                                                       'per eseguire.',
        'Use {page} e {pages}.': 'Usa {page} e {pages}.',
        'Use “Visualizar” para ver o relatório e “PDF” para exportar com cabeçalho/rodapé repetidos e número de página.': 'Usa '
                                                                                                                          '« '
                                                                                                                          'Visualizza '
                                                                                                                          '» '
                                                                                                                          'per '
                                                                                                                          'vedere '
                                                                                                                          'il '
                                                                                                                          'report '
                                                                                                                          'e '
                                                                                                                          '« '
                                                                                                                          'PDF '
                                                                                                                          '» '
                                                                                                                          'per '
                                                                                                                          'esportare '
                                                                                                                          'con '
                                                                                                                          'intestazione/piè '
                                                                                                                          'ripetuti '
                                                                                                                          'e '
                                                                                                                          'numeri '
                                                                                                                          'di '
                                                                                                                          'pagina.',
        'Ver todos': 'Vedi tutto',
        'Visualizar': 'Visualizza',
        'Você pode arrastar arquivos/pastas para outra pasta na árvore.': 'Puoi trascinare file/cartelle in un’altra '
                                                                          'cartella nell’albero.',
        'Você também pode arrastar e soltar no painel de pastas.': 'Puoi anche trascinare e rilasciare nel pannello '
                                                                   'delle cartelle.',
        'Zebra (linhas alternadas)': 'Zebratura (righe alternate)'}}

for _lang, _mp in _EXTRA_TRANSLATIONS.items():
    TRANSLATIONS.setdefault(_lang, {}).update(_mp)


def tr(msgid: str, lang: str | None = None, **kwargs: Any) -> str:
    """Translate msgid using the configured dictionary.

    kwargs can be used for basic string formatting, e.g. tr('Hello {name}', name='Rodrigo')

    Fallback order:
    - requested language (e.g. 'fr')
    - English ('en')
    - Portuguese ('pt')
    - msgid (as-is)
    """
    lang = normalize_lang(lang)

    out = (
        TRANSLATIONS.get(lang, {}).get(msgid)
        or TRANSLATIONS.get("en", {}).get(msgid)
        or TRANSLATIONS.get("pt", {}).get(msgid)
        or msgid
    )
    try:
        return str(out).format(**kwargs)
    except Exception:
        return str(out)
