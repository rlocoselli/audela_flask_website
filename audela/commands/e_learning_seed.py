"""E-Learning Content Seeder

Populates the database with sample SQL training content for the e-learning platform.

Run with:
    flask seed-e-learning           # seed SQL 101 module + achievements
    flask seed-e-learning --force   # drop and re-seed
"""

import click
from flask import Flask
from ..extensions import db


# ---------------------------------------------------------------------------
# Sample SQLite database schema for SQL 101
# ---------------------------------------------------------------------------

SAMPLE_SCHEMA_SQL101 = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT UNIQUE,
    country TEXT,
    created_at DATE
);

CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    order_date DATE NOT NULL,
    amount DECIMAL(10, 2),
    status TEXT,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY,
    product_name TEXT NOT NULL,
    category TEXT,
    price DECIMAL(10, 2),
    stock INT
);

CREATE TABLE IF NOT EXISTS order_items (
    order_item_id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INT,
    unit_price DECIMAL(10, 2),
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
"""

SAMPLE_DATA_SQL101 = """
INSERT INTO customers VALUES
(1, 'João', 'Silva', 'joao.silva@example.com', 'Brazil', '2024-01-15'),
(2, 'Maria', 'Santos', 'maria.santos@example.com', 'Brazil', '2024-02-20'),
(3, 'Pierre', 'Dupont', 'pierre.dupont@example.com', 'France', '2024-01-10'),
(4, 'Anna', 'Rossi', 'anna.rossi@example.com', 'Italy', '2024-03-05'),
(5, 'Carlos', 'Garcia', 'carlos.garcia@example.com', 'Spain', '2024-01-25'),
(6, 'Lisa', 'Müller', 'lisa.muller@example.com', 'Germany', '2024-02-14'),
(7, 'Fatima', 'Al-Hassan', 'fatima.hassan@example.com', 'Morocco', '2024-03-01');

INSERT INTO products VALUES
(1, 'Laptop', 'Electronics', 999.99, 50),
(2, 'Mouse', 'Electronics', 29.99, 200),
(3, 'Keyboard', 'Electronics', 79.99, 150),
(4, 'Monitor', 'Electronics', 299.99, 75),
(5, 'USB Cable', 'Accessories', 9.99, 500),
(6, 'Webcam', 'Electronics', 89.99, 80),
(7, 'Headset', 'Electronics', 149.99, 60);

INSERT INTO orders VALUES
(1, 1, '2024-03-01', 1009.98, 'completed'),
(2, 2, '2024-03-03', 1299.98, 'completed'),
(3, 3, '2024-03-05', 79.99, 'shipped'),
(4, 1, '2024-03-07', 299.99, 'pending'),
(5, 4, '2024-03-10', 29.99, 'completed'),
(6, 5, '2024-03-12', 379.97, 'shipped'),
(7, 6, '2024-03-14', 149.99, 'completed'),
(8, 7, '2024-03-16', 89.99, 'pending'),
(9, 2, '2024-03-18', 999.99, 'completed'),
(10, 3, '2024-03-20', 239.97, 'shipped');

INSERT INTO order_items VALUES
(1, 1, 1, 1, 999.99),
(2, 1, 2, 1, 29.99),
(3, 2, 4, 1, 299.99),
(4, 2, 3, 1, 79.99),
(5, 2, 6, 1, 89.99),
(6, 3, 3, 1, 79.99),
(7, 4, 4, 1, 299.99),
(8, 5, 2, 1, 29.99),
(9, 6, 2, 2, 29.99),
(10, 6, 5, 3, 9.99),
(11, 6, 3, 1, 79.99),
(12, 7, 7, 1, 149.99),
(13, 8, 6, 1, 89.99),
(14, 9, 1, 1, 999.99),
(15, 10, 3, 3, 79.99);
"""


# ---------------------------------------------------------------------------
# Achievement definitions
# ---------------------------------------------------------------------------

ACHIEVEMENTS = [
    {
        "code": "first_exercise",
        "name_i18n": {
            "en": "First Steps",
            "pt": "Primeiros Passos",
            "fr": "Premiers Pas",
            "es": "Primeros Pasos",
            "it": "Primi Passi",
            "de": "Erste Schritte",
        },
        "description_i18n": {
            "en": "Completed your first exercise!",
            "pt": "Completou o seu primeiro exercício!",
            "fr": "Exercice complété pour la première fois !",
            "es": "¡Completaste tu primer ejercicio!",
            "it": "Hai completato il tuo primo esercizio!",
            "de": "Erste Übung abgeschlossen!",
        },
        "icon": "star",
        "rarity": "common",
        "points_reward": 50,
    },
    {
        "code": "perfect_score",
        "name_i18n": {
            "en": "Perfect Score",
            "pt": "Pontuação Perfeita",
            "fr": "Score Parfait",
            "es": "Puntuación Perfecta",
            "it": "Punteggio Perfetto",
            "de": "Perfektes Ergebnis",
        },
        "description_i18n": {
            "en": "Got a 100% score on an exercise!",
            "pt": "Obteve 100% numa exercício!",
            "fr": "100% dans un exercice !",
            "es": "¡100% en un ejercicio!",
            "it": "100% in un esercizio!",
            "de": "100% in einer Übung!",
        },
        "icon": "grade",
        "rarity": "uncommon",
        "points_reward": 100,
    },
    {
        "code": "module_completed",
        "name_i18n": {
            "en": "Module Master",
            "pt": "Mestre do Módulo",
            "fr": "Maître du Module",
            "es": "Maestro del Módulo",
            "it": "Maestro del Modulo",
            "de": "Modul-Meister",
        },
        "description_i18n": {
            "en": "Completed a full module!",
            "pt": "Completou um módulo completo!",
            "fr": "Module entier complété !",
            "es": "¡Módulo completado!",
            "it": "Modulo completato!",
            "de": "Modul abgeschlossen!",
        },
        "icon": "workspace_premium",
        "rarity": "rare",
        "points_reward": 200,
    },
    {
        "code": "7_day_streak",
        "name_i18n": {
            "en": "Week Warrior",
            "pt": "Guerreiro da Semana",
            "fr": "Guerrier de la Semaine",
            "es": "Guerrero Semanal",
            "it": "Guerriero della Settimana",
            "de": "Wochen-Krieger",
        },
        "description_i18n": {
            "en": "Practiced for 7 consecutive days!",
            "pt": "Praticou 7 dias seguidos!",
            "fr": "7 jours consécutifs !",
            "es": "¡7 días consecutivos!",
            "it": "7 giorni consecutivi!",
            "de": "7 aufeinanderfolgende Tage!",
        },
        "icon": "local_fire_department",
        "rarity": "rare",
        "points_reward": 300,
    },
    {
        "code": "30_day_streak",
        "name_i18n": {
            "en": "Month Master",
            "pt": "Mestre do Mês",
            "fr": "Maître du Mois",
            "es": "Maestro del Mes",
            "it": "Maestro del Mese",
            "de": "Monats-Meister",
        },
        "description_i18n": {
            "en": "Practiced for 30 consecutive days!",
            "pt": "Praticou 30 dias seguidos!",
            "fr": "30 jours consécutifs !",
            "es": "¡30 días consecutivos!",
            "it": "30 giorni consecutivi!",
            "de": "30 aufeinanderfolgende Tage!",
        },
        "icon": "emoji_events",
        "rarity": "epic",
        "points_reward": 1000,
    },
    {
        "code": "sql_master",
        "name_i18n": {
            "en": "SQL Master",
            "pt": "Mestre SQL",
            "fr": "Maître SQL",
            "es": "Maestro SQL",
            "it": "Maestro SQL",
            "de": "SQL-Meister",
        },
        "description_i18n": {
            "en": "Completed all SQL modules!",
            "pt": "Completou todos os módulos SQL!",
            "fr": "Tous les modules SQL terminés !",
            "es": "¡Todos los módulos SQL completados!",
            "it": "Tutti i moduli SQL completati!",
            "de": "Alle SQL-Module abgeschlossen!",
        },
        "icon": "military_tech",
        "rarity": "legendary",
        "points_reward": 2000,
    },
    {
        "code": "speed_learner",
        "name_i18n": {
            "en": "Speed Learner",
            "pt": "Aprendiz Veloz",
            "fr": "Apprenants Rapide",
            "es": "Aprendiz Veloz",
            "it": "Apprendista Veloce",
            "de": "Schnell-Lerner",
        },
        "description_i18n": {
            "en": "Submitted an exercise under 60 seconds!",
            "pt": "Enviou uma resposta em menos de 60 segundos!",
            "fr": "Exercice résolu en moins de 60 secondes !",
            "es": "¡Ejercicio resuelto en menos de 60 segundos!",
            "it": "Esercizio completato in meno di 60 secondi!",
            "de": "Übung in unter 60 Sekunden abgeschlossen!",
        },
        "icon": "bolt",
        "rarity": "uncommon",
        "points_reward": 150,
    },
]


# ---------------------------------------------------------------------------
# Content: SQL subject + 3 modules + lessons + exercises
# ---------------------------------------------------------------------------

SQL_SUBJECT = {
    "code": "sql",
    "name_i18n": {
        "en": "SQL & Databases — Complete Course",
        "pt": "SQL e Bases de Dados — Curso Completo",
        "fr": "SQL & Bases de Données — Cours Complet",
        "es": "SQL y Bases de Datos — Curso Completo",
        "it": "SQL e Database — Corso Completo",
        "de": "SQL & Datenbanken — Vollständiger Kurs",
    },
    "description_i18n": {
        "en": "A 12-module journey from zero to SQL hero. Master SELECT, JOINs, aggregations, stored procedures, window functions and database security with real-world exercises.",
        "pt": "12 módulos do zero ao SQL avançado. Domine SELECT, JOINs, agregações, procedimentos e funções de janela com exercícios do mundo real.",
        "fr": "12 modules du zéro au SQL avancé. Maîtrisez SELECT, JOIN, agrégations, procédures stockées et fonctions de fenêtre.",
        "es": "12 módulos desde cero hasta SQL avanzado. Domina SELECT, JOINs, agregaciones, procedimientos y funciones de ventana.",
        "it": "12 moduli da zero a SQL avanzato. Padroneggia SELECT, JOIN, aggregazioni, procedure e funzioni finestra.",
        "de": "12 Module vom Anfänger zum SQL-Experten. Meistere SELECT, JOINs, Aggregationen, gespeicherte Prozeduren und Fensterfunktionen.",
    },
    "icon": "storage",
    "color": "#667eea",
    "is_active": True,
    "sort_order": 1,
}

# ---------------------------------------------------------------------------
# Shared HTML helpers embedded in lesson content
# ---------------------------------------------------------------------------

_TIP_BOX = lambda icon, text: f'<div class="alert alert-info d-flex gap-2 align-items-start py-2 mb-3"><span style="font-size:1.4rem">{icon}</span><div>{text}</div></div>'
_WARN_BOX = lambda icon, text: f'<div class="alert alert-warning d-flex gap-2 align-items-start py-2 mb-3"><span style="font-size:1.4rem">{icon}</span><div>{text}</div></div>'


_CONTENT_I18N = {
    "en": {
        "interactive_intro": "Interactive SQL learning with visuals, mini challenges and real business context.",
        "tip": "Play mode: Explore schema first, then solve one challenge at a time.",
        "core_concepts": "Core Concepts",
        "concept_deep_dive": "Concept Deep Dive",
        "concept_deep_dive_desc": "Use this section to connect syntax with business intent before solving exercises.",
        "warn": "Avoid copy-paste SQL. Read result sets and explain each query in your own words.",
        "practical_exercises": "Practical Exercises",
        "task": "Task",
        "mini_project": "Mini Project",
        "references": "References & Further Reading",
        "model_prompt": "Model Explorer Prompt",
        "model_prompt_text": "Open the Database Explorer, inspect entities and relationships, and map at least 2 join paths before writing SQL.",
        "explanation_default": "This concept strengthens SQL fluency for real production tasks. Practice with small iterations and validate each intermediate result.",
        "learning_objectives": "Learning Objectives",
        "common_pitfalls": "Common Pitfalls",
        "submission_checklist": "Submission Checklist",
        "objective_master": "Master the concept:",
        "objective_apply": "Apply it in one practical task:",
        "objective_validate": "Validate columns, row count, and ordering before submission.",
        "pitfall_1": "Avoid SELECT * unless explicitly requested.",
        "pitfall_2": "Check join keys carefully to prevent duplicate or missing rows.",
        "pitfall_3": "Use explicit ORDER BY when result order matters.",
        "check_1": "I ran the query and reviewed the preview output.",
        "check_2": "My query uses the expected tables/joins/filters.",
        "check_3": "Result columns and values match the exercise objective.",
    },
    "pt": {
        "interactive_intro": "Aprendizagem SQL interativa com recursos visuais, mini desafios e contexto real de negocio.",
        "tip": "Modo de estudo: explore o schema primeiro e depois resolva um desafio por vez.",
        "core_concepts": "Conceitos Centrais",
        "concept_deep_dive": "Aprofundamento dos Conceitos",
        "concept_deep_dive_desc": "Use esta secao para conectar sintaxe com objetivo de negocio antes dos exercicios.",
        "warn": "Evite copiar e colar SQL. Leia os resultados e explique cada consulta com suas palavras.",
        "practical_exercises": "Exercicios Praticos",
        "task": "Tarefa",
        "mini_project": "Mini Projeto",
        "references": "Referencias e Leitura Complementar",
        "model_prompt": "Prompt do Explorador de Modelo",
        "model_prompt_text": "Abra o Explorador de Banco, inspecione entidades e relacionamentos e mapeie ao menos 2 caminhos de join antes de escrever SQL.",
        "explanation_default": "Este conceito fortalece a fluencia em SQL para tarefas reais. Pratique em iteracoes curtas e valide cada resultado intermediario.",
        "learning_objectives": "Objetivos de Aprendizagem",
        "common_pitfalls": "Erros Comuns",
        "submission_checklist": "Checklist de Envio",
        "objective_master": "Domine o conceito:",
        "objective_apply": "Aplique em uma tarefa pratica:",
        "objective_validate": "Valide colunas, quantidade de linhas e ordenacao antes de enviar.",
        "pitfall_1": "Evite SELECT * a menos que seja solicitado explicitamente.",
        "pitfall_2": "Confira as chaves de join para evitar linhas duplicadas ou ausentes.",
        "pitfall_3": "Use ORDER BY explicito quando a ordem do resultado importar.",
        "check_1": "Executei a consulta e revisei o resultado da pre-visualizacao.",
        "check_2": "Minha consulta usa tabelas/joins/filtros esperados.",
        "check_3": "Colunas e valores do resultado atendem ao objetivo do exercicio.",
    },
    "fr": {
        "interactive_intro": "Apprentissage SQL interactif avec visuels, mini-defis et contexte metier reel.",
        "tip": "Mode pratique: explorez d'abord le schema, puis resolvez un defi a la fois.",
        "core_concepts": "Concepts Clés",
        "concept_deep_dive": "Approfondissement des Concepts",
        "concept_deep_dive_desc": "Utilisez cette section pour relier la syntaxe a l'objectif metier avant les exercices.",
        "warn": "Evitez le copier-coller SQL. Lisez les resultats et expliquez chaque requete avec vos mots.",
        "practical_exercises": "Exercices Pratiques",
        "task": "Tache",
        "mini_project": "Mini Projet",
        "references": "References et Lectures Completes",
        "model_prompt": "Prompt Explorateur de Modele",
        "model_prompt_text": "Ouvrez l'explorateur de base, inspectez entites et relations, puis cartographiez au moins 2 chemins de jointure avant d'ecrire du SQL.",
        "explanation_default": "Ce concept renforce la maitrise SQL pour des cas reels. Pratiquez par petites iterations et validez chaque resultat intermediaire.",
        "learning_objectives": "Objectifs d'Apprentissage",
        "common_pitfalls": "Erreurs Courantes",
        "submission_checklist": "Checklist de Soumission",
        "objective_master": "Maitrisez le concept :",
        "objective_apply": "Appliquez-le dans une tache pratique :",
        "objective_validate": "Validez colonnes, nombre de lignes et tri avant soumission.",
        "pitfall_1": "Evitez SELECT * sauf demande explicite.",
        "pitfall_2": "Verifiez les cles de jointure pour eviter doublons ou lignes manquantes.",
        "pitfall_3": "Utilisez ORDER BY explicite si l'ordre du resultat compte.",
        "check_1": "J'ai execute la requete et verifie l'aperçu.",
        "check_2": "Ma requete utilise les tables/jointures/filtres attendus.",
        "check_3": "Colonnes et valeurs correspondent a l'objectif de l'exercice.",
    },
    "es": {
        "interactive_intro": "Aprendizaje SQL interactivo con visuales, mini desafios y contexto real de negocio.",
        "tip": "Modo practico: explora primero el esquema y luego resuelve un desafio a la vez.",
        "core_concepts": "Conceptos Clave",
        "concept_deep_dive": "Profundizacion de Conceptos",
        "concept_deep_dive_desc": "Usa esta seccion para conectar sintaxis con objetivo de negocio antes de los ejercicios.",
        "warn": "Evita copiar y pegar SQL. Lee los resultados y explica cada consulta con tus palabras.",
        "practical_exercises": "Ejercicios Practicos",
        "task": "Tarea",
        "mini_project": "Mini Proyecto",
        "references": "Referencias y Lecturas Recomendadas",
        "model_prompt": "Prompt del Explorador de Modelo",
        "model_prompt_text": "Abre el explorador de base de datos, inspecciona entidades y relaciones, y mapea al menos 2 rutas de join antes de escribir SQL.",
        "explanation_default": "Este concepto fortalece la fluidez SQL para tareas reales. Practica en iteraciones pequenas y valida cada resultado intermedio.",
        "learning_objectives": "Objetivos de Aprendizaje",
        "common_pitfalls": "Errores Comunes",
        "submission_checklist": "Checklist de Envio",
        "objective_master": "Domina el concepto:",
        "objective_apply": "Aplicalo en una tarea practica:",
        "objective_validate": "Valida columnas, cantidad de filas y orden antes de enviar.",
        "pitfall_1": "Evita SELECT * salvo solicitud explicita.",
        "pitfall_2": "Verifica claves de join para evitar filas duplicadas o faltantes.",
        "pitfall_3": "Usa ORDER BY explicito cuando el orden del resultado importe.",
        "check_1": "Ejecute la consulta y revise la vista previa.",
        "check_2": "Mi consulta usa tablas/joins/filtros esperados.",
        "check_3": "Columnas y valores cumplen el objetivo del ejercicio.",
    },
    "it": {
        "interactive_intro": "Apprendimento SQL interattivo con elementi visivi, mini sfide e contesto reale di business.",
        "tip": "Modalita pratica: esplora prima lo schema, poi risolvi una sfida alla volta.",
        "core_concepts": "Concetti Chiave",
        "concept_deep_dive": "Approfondimento dei Concetti",
        "concept_deep_dive_desc": "Usa questa sezione per collegare sintassi e obiettivo di business prima degli esercizi.",
        "warn": "Evita copia-incolla SQL. Leggi i risultati e spiega ogni query con parole tue.",
        "practical_exercises": "Esercizi Pratici",
        "task": "Attivita",
        "mini_project": "Mini Progetto",
        "references": "Riferimenti e Letture Consigliate",
        "model_prompt": "Prompt Esploratore Modello",
        "model_prompt_text": "Apri l'esploratore database, ispeziona entita e relazioni e mappa almeno 2 percorsi di join prima di scrivere SQL.",
        "explanation_default": "Questo concetto rafforza la fluidita SQL per attivita reali. Esercitati con piccole iterazioni e valida ogni risultato intermedio.",
        "learning_objectives": "Obiettivi di Apprendimento",
        "common_pitfalls": "Errori Comuni",
        "submission_checklist": "Checklist di Invio",
        "objective_master": "Padroneggia il concetto:",
        "objective_apply": "Applicalo in un compito pratico:",
        "objective_validate": "Valida colonne, numero di righe e ordinamento prima dell'invio.",
        "pitfall_1": "Evita SELECT * salvo richiesta esplicita.",
        "pitfall_2": "Controlla le chiavi di join per evitare righe duplicate o mancanti.",
        "pitfall_3": "Usa ORDER BY esplicito quando l'ordine del risultato e importante.",
        "check_1": "Ho eseguito la query e verificato l'anteprima.",
        "check_2": "La mia query usa tabelle/join/filtri attesi.",
        "check_3": "Colonne e valori rispettano l'obiettivo dell'esercizio.",
    },
    "de": {
        "interactive_intro": "Interaktives SQL-Lernen mit Visuals, Mini-Challenges und realem Geschaeftskontext.",
        "tip": "Lernmodus: zuerst das Schema erkunden, dann jeweils eine Aufgabe loesen.",
        "core_concepts": "Kernkonzepte",
        "concept_deep_dive": "Konzept-Vertiefung",
        "concept_deep_dive_desc": "Nutzen Sie diesen Abschnitt, um Syntax und Geschaeftsziel vor den Uebungen zu verbinden.",
        "warn": "Vermeiden Sie Copy-Paste-SQL. Lesen Sie Ergebnismengen und erklaeren Sie jede Abfrage in eigenen Worten.",
        "practical_exercises": "Praktische Uebungen",
        "task": "Aufgabe",
        "mini_project": "Mini-Projekt",
        "references": "Referenzen und Weiterfuehrende Links",
        "model_prompt": "Model-Explorer Prompt",
        "model_prompt_text": "Oeffnen Sie den Datenbank-Explorer, pruefen Sie Entitaeten und Beziehungen und skizzieren Sie mindestens 2 Join-Pfade vor dem Schreiben von SQL.",
        "explanation_default": "Dieses Konzept staerkt SQL-Fliessfaehigkeit fuer reale Aufgaben. Ueben Sie in kleinen Iterationen und validieren Sie Zwischenergebnisse.",
        "learning_objectives": "Lernziele",
        "common_pitfalls": "Hauefige Fehler",
        "submission_checklist": "Einreichungs-Checkliste",
        "objective_master": "Beherrschen Sie das Konzept:",
        "objective_apply": "Wenden Sie es in einer praktischen Aufgabe an:",
        "objective_validate": "Pruefen Sie Spalten, Zeilenanzahl und Sortierung vor der Abgabe.",
        "pitfall_1": "Vermeiden Sie SELECT * ausser bei ausdruecklicher Anforderung.",
        "pitfall_2": "Pruefen Sie Join-Schluessel sorgfaeltig, um doppelte oder fehlende Zeilen zu vermeiden.",
        "pitfall_3": "Nutzen Sie explizites ORDER BY, wenn die Ergebnisreihenfolge wichtig ist.",
        "check_1": "Ich habe die Abfrage ausgefuehrt und die Vorschau geprueft.",
        "check_2": "Meine Abfrage nutzt erwartete Tabellen/Joins/Filter.",
        "check_3": "Spalten und Werte entsprechen dem Ziel der Uebung.",
    },
}


def _t_content(key: str, lang: str) -> str:
    return _CONTENT_I18N.get(lang, _CONTENT_I18N["en"]).get(key, _CONTENT_I18N["en"][key])


_CURRICULUM_PHRASE_I18N = {
    "What is a database": {
        "pt": "O que e um banco de dados",
        "fr": "Qu'est-ce qu'une base de donnees",
        "es": "Que es una base de datos",
        "it": "Che cos'e un database",
        "de": "Was ist eine Datenbank",
    },
    "Relational databases": {
        "pt": "Bancos de dados relacionais",
        "fr": "Bases de donnees relationnelles",
        "es": "Bases de datos relacionales",
        "it": "Database relazionali",
        "de": "Relationale Datenbanken",
    },
    "Tables, rows, columns": {
        "pt": "Tabelas, linhas, colunas",
        "fr": "Tables, lignes, colonnes",
        "es": "Tablas, filas, columnas",
        "it": "Tabelle, righe, colonne",
        "de": "Tabellen, Zeilen, Spalten",
    },
    "Primary keys and foreign keys": {
        "pt": "Chaves primarias e estrangeiras",
        "fr": "Cles primaires et etrangeres",
        "es": "Claves primarias y foraneas",
        "it": "Chiavi primarie ed esterne",
        "de": "Primaer- und Fremdschluessel",
    },
    "SQL language overview": {
        "pt": "Visao geral da linguagem SQL",
        "fr": "Vue d'ensemble du langage SQL",
        "es": "Resumen del lenguaje SQL",
        "it": "Panoramica del linguaggio SQL",
        "de": "Ueberblick ueber die SQL-Sprache",
    },
    "DBMS overview: PostgreSQL, MySQL, SQL Server, Oracle": {
        "pt": "Visao geral de SGBD: PostgreSQL, MySQL, SQL Server, Oracle",
        "fr": "Vue d'ensemble SGBD: PostgreSQL, MySQL, SQL Server, Oracle",
        "es": "Resumen SGBD: PostgreSQL, MySQL, SQL Server, Oracle",
        "it": "Panoramica DBMS: PostgreSQL, MySQL, SQL Server, Oracle",
        "de": "DBMS-Ueberblick: PostgreSQL, MySQL, SQL Server, Oracle",
    },
    "Install a database system": {
        "pt": "Instalar um sistema de banco de dados",
        "fr": "Installer un systeme de base de donnees",
        "es": "Instalar un sistema de base de datos",
        "it": "Installare un sistema di database",
        "de": "Ein Datenbanksystem installieren",
    },
    "Create a simple database": {
        "pt": "Criar um banco de dados simples",
        "fr": "Creer une base de donnees simple",
        "es": "Crear una base de datos simple",
        "it": "Creare un database semplice",
        "de": "Eine einfache Datenbank erstellen",
    },
    "Create tables": {
        "pt": "Criar tabelas",
        "fr": "Creer des tables",
        "es": "Crear tablas",
        "it": "Creare tabelle",
        "de": "Tabellen erstellen",
    },
    "Insert sample data": {
        "pt": "Inserir dados de exemplo",
        "fr": "Inserer des donnees d'exemple",
        "es": "Insertar datos de ejemplo",
        "it": "Inserire dati di esempio",
        "de": "Beispieldaten einfuegen",
    },
    "Identify relationships between tables": {
        "pt": "Identificar relacionamentos entre tabelas",
        "fr": "Identifier les relations entre tables",
        "es": "Identificar relaciones entre tablas",
        "it": "Identificare relazioni tra tabelle",
        "de": "Beziehungen zwischen Tabellen identifizieren",
    },
    "Create a small Library database": {
        "pt": "Criar um pequeno banco de dados de Biblioteca",
        "fr": "Creer une petite base de donnees de Bibliotheque",
        "es": "Crear una pequena base de datos de Biblioteca",
        "it": "Creare un piccolo database di Biblioteca",
        "de": "Eine kleine Bibliotheksdatenbank erstellen",
    },
}


def _localize_phrase(text: str, lang: str) -> str:
    if lang == "en":
        return text
    return _CURRICULUM_PHRASE_I18N.get(text, {}).get(lang, text)


_EXACT_CONCEPT_EXPLANATIONS = {
    "what is a database": {
        "en": "A database is an organized system for storing and retrieving data reliably. It helps teams keep consistent records and answer business questions quickly.",
        "pt": "Um banco de dados e um sistema organizado para armazenar e recuperar dados com confianca. Ele ajuda equipes a manter registros consistentes e responder perguntas de negocio rapidamente.",
        "fr": "Une base de donnees est un systeme organise pour stocker et recuperer des donnees de facon fiable. Elle aide les equipes a maintenir des enregistrements coherents.",
        "es": "Una base de datos es un sistema organizado para almacenar y recuperar datos de forma confiable. Ayuda a los equipos a mantener registros consistentes.",
        "it": "Un database e un sistema organizzato per archiviare e recuperare dati in modo affidabile. Aiuta i team a mantenere record coerenti.",
        "de": "Eine Datenbank ist ein organisiertes System zur zuverlaessigen Speicherung und Abfrage von Daten. Sie hilft Teams bei konsistenten Datensaetzen.",
    },
    "relational databases": {
        "en": "Relational databases model data as related tables. Relationships reduce duplication and allow precise joins between entities such as customers and orders.",
        "pt": "Bancos relacionais modelam dados como tabelas relacionadas. Relacionamentos reduzem duplicacao e permitem joins precisos entre entidades como clientes e pedidos.",
        "fr": "Les bases relationnelles modelisent les donnees sous forme de tables reliees. Les relations reduisent la duplication et permettent des jointures precises.",
        "es": "Las bases relacionales modelan datos como tablas relacionadas. Las relaciones reducen duplicacion y permiten joins precisos entre entidades.",
        "it": "I database relazionali modellano i dati come tabelle correlate. Le relazioni riducono duplicazioni e permettono join precisi tra entita.",
        "de": "Relationale Datenbanken modellieren Daten als verbundene Tabellen. Beziehungen reduzieren Duplikate und ermoeglichen praezise Joins.",
    },
    "tables, rows, columns": {
        "en": "A table stores one entity type, columns define attributes, and rows represent individual records. Clear naming makes queries easier to read and maintain.",
        "pt": "Uma tabela armazena um tipo de entidade, colunas definem atributos e linhas representam registros individuais. Nomes claros facilitam leitura e manutencao.",
        "fr": "Une table stocke un type d'entite, les colonnes definissent les attributs et les lignes representent les enregistrements. Des noms clairs facilitent les requetes.",
        "es": "Una tabla almacena un tipo de entidad, las columnas definen atributos y las filas representan registros individuales. Nombres claros facilitan las consultas.",
        "it": "Una tabella memorizza un tipo di entita, le colonne definiscono attributi e le righe rappresentano record individuali. Nomi chiari migliorano le query.",
        "de": "Eine Tabelle speichert einen Entitaetstyp, Spalten definieren Attribute und Zeilen repraesentieren einzelne Datensaetze. Klare Namen erleichtern Abfragen.",
    },
    "primary keys and foreign keys": {
        "en": "Primary keys uniquely identify each row. Foreign keys reference primary keys in another table and enforce referential integrity.",
        "pt": "Chaves primarias identificam cada linha de forma unica. Chaves estrangeiras referenciam chaves primarias de outra tabela e garantem integridade referencial.",
        "fr": "Les cles primaires identifient chaque ligne de facon unique. Les cles etrangeres referencent une autre table et garantissent l'integrite referentielle.",
        "es": "Las claves primarias identifican cada fila de forma unica. Las claves foraneas referencian otra tabla y garantizan integridad referencial.",
        "it": "Le chiavi primarie identificano ogni riga in modo univoco. Le chiavi esterne referenziano altre tabelle e garantiscono integrita referenziale.",
        "de": "Primaerschluessel identifizieren jede Zeile eindeutig. Fremdschluessel verweisen auf andere Tabellen und sichern referenzielle Integritaet.",
    },
    "sql language overview": {
        "en": "SQL combines DDL, DML and query operations. In practice, you design schema, insert/update data, then query and aggregate for insights.",
        "pt": "SQL combina operacoes DDL, DML e consultas. Na pratica, voce modela schema, insere/atualiza dados e consulta para gerar insights.",
        "fr": "SQL combine operations DDL, DML et requetes. En pratique, vous modelisez le schema, modifiez les donnees puis analysez les resultats.",
        "es": "SQL combina operaciones DDL, DML y consultas. En la practica, modelas esquema, modificas datos y consultas para obtener analisis.",
        "it": "SQL combina operazioni DDL, DML e query. In pratica, progetti lo schema, modifichi dati e interroghi per ottenere insight.",
        "de": "SQL kombiniert DDL, DML und Abfragen. In der Praxis entwerfen Sie das Schema, pflegen Daten und analysieren Ergebnisse.",
    },
    "dbms overview: postgresql, mysql, sql server, oracle": {
        "en": "DBMS platforms share SQL foundations but differ in syntax, tooling and advanced features. Knowing portability limits helps avoid vendor lock-in.",
        "pt": "Plataformas SGBD compartilham fundamentos SQL, mas diferem em sintaxe, ferramentas e recursos avancados. Conhecer portabilidade evita lock-in.",
        "fr": "Les SGBD partagent une base SQL commune mais different en syntaxe, outils et fonctions avancees. Comprendre la portabilite evite l'enfermement fournisseur.",
        "es": "Las plataformas SGBD comparten base SQL pero difieren en sintaxis, herramientas y funciones avanzadas. Entender portabilidad evita dependencia del proveedor.",
        "it": "Le piattaforme DBMS condividono basi SQL ma differiscono per sintassi, strumenti e funzionalita avanzate. Capire la portabilita evita lock-in.",
        "de": "DBMS-Plattformen teilen SQL-Grundlagen, unterscheiden sich aber in Syntax, Werkzeugen und erweiterten Funktionen. Portabilitaet reduziert Herstellerbindung.",
    },
    "select": {
        "en": "SELECT controls which columns are returned. Keep projection minimal so results are clearer and queries stay efficient.",
        "pt": "SELECT controla quais colunas serao retornadas. Mantenha a projecao minima para resultados mais claros e consultas mais eficientes.",
    },
    "where": {
        "en": "WHERE filters rows before aggregation and ordering. Write predicates that are precise and index-friendly whenever possible.",
        "pt": "WHERE filtra linhas antes da agregacao e ordenacao. Escreva predicados precisos e amigaveis a indice sempre que possivel.",
    },
    "order by": {
        "en": "ORDER BY defines deterministic sorting. Always add it when output order matters for reports or validation.",
        "pt": "ORDER BY define uma ordenacao deterministica. Use sempre quando a ordem de saida for importante para relatorios ou validacao.",
    },
    "distinct": {
        "en": "DISTINCT removes duplicate rows from the selected projection. Apply only when duplicates are truly undesired.",
        "pt": "DISTINCT remove linhas duplicadas da projecao selecionada. Use apenas quando duplicatas realmente nao forem desejadas.",
    },
    "limit / top": {
        "en": "LIMIT/TOP restricts row count returned. Combine with ORDER BY to make sampled results reproducible.",
        "pt": "LIMIT/TOP limita a quantidade de linhas retornadas. Combine com ORDER BY para resultados reproduziveis.",
    },
    "aliases": {
        "en": "Aliases rename columns or tables for readability. They are essential in joins and complex expressions.",
        "pt": "Aliases renomeiam colunas ou tabelas para melhorar legibilidade. Sao essenciais em joins e expressoes complexas.",
    },
    "arithmetic": {
        "en": "Arithmetic expressions compute derived metrics directly in SQL, such as revenue, margin, or discount.",
        "pt": "Expressoes aritmeticas calculam metricas derivadas diretamente no SQL, como receita, margem ou desconto.",
    },
    "null values": {
        "en": "NULL represents unknown or missing data. Handle it explicitly to avoid misleading comparisons and aggregates.",
        "pt": "NULL representa dado desconhecido ou ausente. Trate-o explicitamente para evitar comparacoes e agregacoes enganosas.",
    },
    "and / or / not": {
        "en": "Boolean logic combines filter conditions. Use parentheses to make precedence explicit and prevent logical mistakes.",
        "pt": "Logica booleana combina condicoes de filtro. Use parenteses para explicitar precedencia e evitar erros logicos.",
    },
    "between": {
        "en": "BETWEEN filters values in an inclusive range. It is useful for date windows and numeric intervals.",
        "pt": "BETWEEN filtra valores em um intervalo inclusivo. E util para janelas de data e intervalos numericos.",
    },
    "in": {
        "en": "IN matches values against a list or subquery, improving readability over multiple OR clauses.",
        "pt": "IN compara valores contra uma lista ou subconsulta, melhorando a legibilidade em relacao a varios OR.",
    },
    "like": {
        "en": "LIKE performs pattern matching with wildcards. It is useful for text search and data quality checks.",
        "pt": "LIKE faz correspondencia por padrao com curingas. E util para busca textual e checagem de qualidade de dados.",
    },
    "wildcards": {
        "en": "Wildcards such as % and _ define flexible text patterns in LIKE filters.",
        "pt": "Curingas como % e _ definem padroes flexiveis de texto em filtros LIKE.",
    },
    "is null / is not null": {
        "en": "IS NULL and IS NOT NULL are the correct operators to test missing values.",
        "pt": "IS NULL e IS NOT NULL sao os operadores corretos para testar valores ausentes.",
    },
    "case": {
        "en": "CASE applies conditional logic inside a query, ideal for labels, buckets, and business rules.",
        "pt": "CASE aplica logica condicional dentro da consulta, ideal para rotulos, faixas e regras de negocio.",
    },
    "count": {
        "en": "COUNT measures row volume. COUNT(*) includes all rows while COUNT(column) ignores NULLs.",
        "pt": "COUNT mede volume de linhas. COUNT(*) inclui todas as linhas e COUNT(coluna) ignora NULLs.",
    },
    "sum": {
        "en": "SUM aggregates numeric totals, such as sales, quantities, or costs.",
        "pt": "SUM agrega totais numericos, como vendas, quantidades ou custos.",
    },
    "avg": {
        "en": "AVG computes mean values and is often paired with GROUP BY for comparative analysis.",
        "pt": "AVG calcula medias e costuma ser combinado com GROUP BY para analise comparativa.",
    },
    "min / max": {
        "en": "MIN and MAX find boundary values, useful for first/last events and range checks.",
        "pt": "MIN e MAX encontram valores de fronteira, uteis para primeiro/ultimo evento e verificacao de faixas.",
    },
    "group by": {
        "en": "GROUP BY organizes rows into groups before aggregate calculations, turning row-level data into summarized metrics.",
        "pt": "GROUP BY organiza linhas em grupos antes dos calculos de agregacao, transformando dados detalhados em metricas resumidas.",
    },
    "having": {
        "en": "HAVING filters grouped results after aggregation and should be used with grouped metrics like COUNT or SUM.",
        "pt": "HAVING filtra resultados agrupados apos a agregacao e deve ser usado com metricas como COUNT ou SUM.",
    },
    "inner join": {
        "en": "INNER JOIN returns only matching rows across tables.",
        "pt": "INNER JOIN retorna apenas linhas com correspondencia entre tabelas.",
    },
    "left join": {
        "en": "LEFT JOIN preserves all rows from the left table and fills missing matches with NULLs.",
        "pt": "LEFT JOIN preserva todas as linhas da tabela esquerda e preenche sem correspondencia com NULL.",
    },
    "right join": {
        "en": "RIGHT JOIN preserves all rows from the right table and is the mirror of LEFT JOIN.",
        "pt": "RIGHT JOIN preserva todas as linhas da tabela direita e e o espelho do LEFT JOIN.",
    },
    "full outer join": {
        "en": "FULL OUTER JOIN keeps matched and unmatched rows from both sides.",
        "pt": "FULL OUTER JOIN mantem linhas correspondentes e nao correspondentes de ambos os lados.",
    },
    "self join": {
        "en": "SELF JOIN joins a table to itself, useful for hierarchies such as employee-manager relationships.",
        "pt": "SELF JOIN junta uma tabela com ela mesma, util para hierarquias como relacao empregado-gerente.",
    },
    "cross join": {
        "en": "CROSS JOIN creates a Cartesian product and should be used intentionally due to row explosion.",
        "pt": "CROSS JOIN cria produto cartesiano e deve ser usado intencionalmente por causa da explosao de linhas.",
    },
    "relationship modeling": {
        "en": "Relationship modeling defines cardinality and dependencies between entities before queries are written.",
        "pt": "Modelagem de relacionamentos define cardinalidade e dependencias entre entidades antes das consultas.",
    },
    "subqueries": {
        "en": "Subqueries embed one query inside another for filtering, projection, or derived tables.",
        "pt": "Subconsultas inserem uma consulta dentro de outra para filtro, projecao ou tabelas derivadas.",
    },
    "correlated subqueries": {
        "en": "Correlated subqueries reference outer query values and are evaluated per row.",
        "pt": "Subconsultas correlacionadas referenciam valores da consulta externa e sao avaliadas por linha.",
    },
    "cte": {
        "en": "CTE (WITH) organizes complex SQL into readable stages and supports recursion when needed.",
        "pt": "CTE (WITH) organiza SQL complexo em etapas legiveis e suporta recursao quando necessario.",
    },
    "union / union all": {
        "en": "UNION merges result sets and removes duplicates; UNION ALL keeps duplicates and is faster.",
        "pt": "UNION combina conjuntos de resultados e remove duplicatas; UNION ALL mantem duplicatas e e mais rapido.",
    },
    "exists": {
        "en": "EXISTS checks if at least one related row exists and is efficient for semi-join logic.",
        "pt": "EXISTS verifica se ao menos uma linha relacionada existe e e eficiente para logica de semi-join.",
    },
    "views": {
        "en": "Views encapsulate reusable query logic and provide a stable interface for reporting.",
        "pt": "Views encapsulam logica reutilizavel de consulta e oferecem interface estavel para relatorios.",
    },
    "insert": {
        "en": "INSERT adds new rows. Prefer explicit column lists to keep statements robust over schema changes.",
        "pt": "INSERT adiciona novas linhas. Prefira listas explicitas de colunas para robustez com mudancas de schema.",
    },
    "update": {
        "en": "UPDATE modifies existing rows. Always validate WHERE conditions to avoid unintended mass updates.",
        "pt": "UPDATE altera linhas existentes. Sempre valide o WHERE para evitar atualizacoes em massa indevidas.",
    },
    "delete": {
        "en": "DELETE removes rows and should be scoped carefully with WHERE and transaction safety.",
        "pt": "DELETE remove linhas e deve ser cuidadosamente delimitado com WHERE e seguranca transacional.",
    },
    "merge / upsert": {
        "en": "MERGE/UPSERT performs insert-or-update logic in one statement for synchronization workflows.",
        "pt": "MERGE/UPSERT executa logica de inserir-ou-atualizar em um comando para sincronizacao.",
    },
    "transactions": {
        "en": "Transactions group operations atomically so data stays consistent under failure or concurrency.",
        "pt": "Transacoes agrupam operacoes de forma atomica para manter consistencia sob falha ou concorrencia.",
    },
    "commit / rollback": {
        "en": "COMMIT confirms changes permanently; ROLLBACK reverts uncommitted changes.",
        "pt": "COMMIT confirma alteracoes de forma permanente; ROLLBACK desfaz alteracoes nao confirmadas.",
    },
    "database modeling": {
        "en": "Database modeling translates business processes into entities, attributes, and relationships.",
        "pt": "Modelagem de banco traduz processos de negocio em entidades, atributos e relacionamentos.",
    },
    "erd": {
        "en": "ERD diagrams visualize entities and relationships, helping teams align schema design.",
        "pt": "Diagramas ERD visualizam entidades e relacionamentos, ajudando equipes a alinhar o design do schema.",
    },
    "1nf, 2nf, 3nf": {
        "en": "Normalization forms reduce redundancy and anomalies by structuring data dependencies.",
        "pt": "Formas normais reduzem redundancia e anomalias ao estruturar dependencias de dados.",
    },
    "referential integrity": {
        "en": "Referential integrity ensures foreign keys always reference valid parent rows.",
        "pt": "Integridade referencial garante que chaves estrangeiras apontem sempre para linhas validas.",
    },
    "constraints": {
        "en": "Constraints enforce quality rules (PK, FK, UNIQUE, CHECK) directly at the data layer.",
        "pt": "Constraints aplicam regras de qualidade (PK, FK, UNIQUE, CHECK) diretamente na camada de dados.",
    },
    "indexes": {
        "en": "Indexes speed up lookups and joins but increase write cost and storage usage.",
        "pt": "Indices aceleram buscas e joins, mas aumentam custo de escrita e uso de armazenamento.",
    },
    "query optimization": {
        "en": "Query optimization improves performance by reducing scans, sorting, and unnecessary operations.",
        "pt": "Otimizacao de consultas melhora performance reduzindo scans, ordenacoes e operacoes desnecessarias.",
    },
    "execution plans": {
        "en": "Execution plans show how the optimizer will run a query and where bottlenecks appear.",
        "pt": "Planos de execucao mostram como o otimizador executara a consulta e onde estao gargalos.",
    },
    "performance tuning": {
        "en": "Performance tuning combines query rewrites, indexing, and data distribution strategies.",
        "pt": "Ajuste de performance combina reescrita de consultas, indexacao e estrategias de distribuicao de dados.",
    },
    "partitioning basics": {
        "en": "Partitioning splits large tables into manageable segments to improve maintenance and query speed.",
        "pt": "Particionamento divide tabelas grandes em segmentos para melhorar manutencao e velocidade de consulta.",
    },
    "stored procedures": {
        "en": "Stored procedures encapsulate business workflows in the database for reuse and governance.",
        "pt": "Procedures encapsulam fluxos de negocio no banco para reutilizacao e governanca.",
    },
    "functions": {
        "en": "Functions return computed values and can simplify repeated SQL logic.",
        "pt": "Funcoes retornam valores calculados e podem simplificar logica SQL repetida.",
    },
    "parameters": {
        "en": "Parameters make procedures and functions reusable with dynamic inputs.",
        "pt": "Parametros tornam procedures e funcoes reutilizaveis com entradas dinamicas.",
    },
    "variables": {
        "en": "Variables store intermediate values during procedural SQL execution.",
        "pt": "Variaveis armazenam valores intermediarios durante execucao procedural SQL.",
    },
    "control structures": {
        "en": "Control structures (IF, LOOP, WHILE) manage flow inside procedural SQL routines.",
        "pt": "Estruturas de controle (IF, LOOP, WHILE) gerenciam fluxo em rotinas SQL procedurais.",
    },
    "triggers": {
        "en": "Triggers run automatically on data events and enforce real-time business policies.",
        "pt": "Triggers executam automaticamente em eventos de dados e reforcam politicas de negocio em tempo real.",
    },
    "window functions": {
        "en": "Window functions compute analytics over ordered partitions without collapsing row granularity.",
        "pt": "Funcoes de janela calculam analitica sobre particoes ordenadas sem colapsar a granularidade das linhas.",
    },
    "rank / dense_rank": {
        "en": "RANK and DENSE_RANK assign ordering positions; DENSE_RANK does not leave gaps after ties.",
        "pt": "RANK e DENSE_RANK atribuem posicoes; DENSE_RANK nao deixa lacunas apos empates.",
    },
    "row_number": {
        "en": "ROW_NUMBER gives a unique sequence per partition, useful for top-N and deduping.",
        "pt": "ROW_NUMBER gera sequencia unica por particao, util para top-N e deduplicacao.",
    },
    "lead / lag": {
        "en": "LEAD and LAG compare values with next/previous rows for trend and delta analysis.",
        "pt": "LEAD e LAG comparam valores com linhas seguintes/anteriores para analise de tendencia e variacao.",
    },
    "analytical queries": {
        "en": "Analytical queries transform operational data into decision-ready metrics and insights.",
        "pt": "Consultas analiticas transformam dados operacionais em metricas e insights para decisao.",
    },
    "users and roles": {
        "en": "Users and roles define identity and access boundaries across database environments.",
        "pt": "Usuarios e papeis definem identidade e limites de acesso em ambientes de banco de dados.",
    },
    "permissions": {
        "en": "Permissions apply least-privilege access so users can perform only required actions.",
        "pt": "Permissoes aplicam acesso de menor privilegio para que usuarios executem apenas o necessario.",
    },
    "backup and restore": {
        "en": "Backup and restore strategies protect against data loss and support disaster recovery.",
        "pt": "Estrategias de backup e restore protegem contra perda de dados e suportam recuperacao de desastre.",
    },
    "database security": {
        "en": "Database security combines authentication, authorization, encryption, and auditing controls.",
        "pt": "Seguranca de banco combina autenticacao, autorizacao, criptografia e controles de auditoria.",
    },
    "auditing basics": {
        "en": "Auditing records who changed what and when, enabling traceability and compliance.",
        "pt": "Auditoria registra quem mudou o que e quando, permitindo rastreabilidade e conformidade.",
        "fr": "L'audit enregistre qui a modifie quoi et quand, assurant tracabilite et conformite.",
        "es": "La auditoria registra quien cambio que y cuando, garantizando trazabilidad y cumplimiento.",
        "it": "L'audit registra chi ha modificato cosa e quando, garantendo tracciabilita e conformita.",
        "de": "Auditierung protokolliert, wer was wann geaendert hat, und gewaehrleistet Nachvollziehbarkeit und Compliance.",
    },
    "wildcards": {
        "en": "Wildcards such as % and _ define flexible text patterns in LIKE filters.",
        "pt": "Curingas como % e _ definem padroes flexiveis de texto em filtros LIKE.",
        "fr": "Les jokers comme % et _ definissent des motifs flexibles dans les filtres LIKE.",
        "es": "Los comodines como % y _ definen patrones flexibles de texto en filtros LIKE.",
        "it": "I caratteri jolly come % e _ definiscono pattern flessibili nei filtri LIKE.",
        "de": "Wildcards wie % und _ definieren flexible Textmuster in LIKE-Filtern.",
    },
    "delete": {
        "en": "DELETE removes rows and should be scoped carefully with WHERE and transaction safety.",
        "pt": "DELETE remove linhas e deve ser cuidadosamente delimitado com WHERE e seguranca transacional.",
        "fr": "DELETE supprime des lignes et doit etre limite avec un WHERE et des transactions securisees.",
        "es": "DELETE elimina filas y debe delimitarse con WHERE y seguridad transaccional.",
        "it": "DELETE rimuove righe e deve essere delimitato con WHERE e sicurezza transazionale.",
        "de": "DELETE entfernt Zeilen und sollte mit WHERE und Transaktionssicherheit gezielt eingesetzt werden.",
    },
    "update": {
        "en": "UPDATE modifies existing rows. Always validate WHERE conditions to avoid unintended mass updates.",
        "pt": "UPDATE altera linhas existentes. Sempre valide o WHERE para evitar atualizacoes em massa indevidas.",
        "fr": "UPDATE modifie des lignes existantes. Validez toujours le WHERE pour eviter les mises a jour massives involontaires.",
        "es": "UPDATE modifica filas existentes. Valida siempre el WHERE para evitar actualizaciones masivas no deseadas.",
        "it": "UPDATE modifica righe esistenti. Verifica sempre il WHERE per evitare aggiornamenti massivi non voluti.",
        "de": "UPDATE aendert bestehende Zeilen. Pruefen Sie stets die WHERE-Bedingung, um unbeabsichtigte Massenupdates zu vermeiden.",
    },
    "query optimization": {
        "en": "Query optimization improves performance by reducing scans, sorting, and unnecessary operations.",
        "pt": "Otimizacao de consultas melhora performance reduzindo scans, ordenacoes e operacoes desnecessarias.",
        "fr": "L'optimisation des requetes ameliore les performances en reduisant scans, tris et operations inutiles.",
        "es": "La optimizacion de consultas mejora el rendimiento al reducir escaneos, ordenamientos y operaciones innecesarias.",
        "it": "L'ottimizzazione delle query migliora le prestazioni riducendo scansioni, ordinamenti e operazioni inutili.",
        "de": "Abfrageoptimierung verbessert die Leistung durch weniger Scans, Sortierungen und unnoetige Operationen.",
    },
    "execution plans": {
        "en": "Execution plans show how the optimizer will run a query and where bottlenecks appear.",
        "pt": "Planos de execucao mostram como o otimizador executara a consulta e onde estao gargalos.",
        "fr": "Les plans d'execution montrent comment l'optimiseur execute une requete et ou apparaissent les goulots d'etranglement.",
        "es": "Los planes de ejecucion muestran como el optimizador ejecutara una consulta y donde aparecen cuellos de botella.",
        "it": "I piani di esecuzione mostrano come l'ottimizzatore eseguira una query e dove emergono i colli di bottiglia.",
        "de": "Ausfuehrungsplaene zeigen, wie der Optimierer eine Abfrage ausfuehrt und wo Engpaesse entstehen.",
    },
    "variables": {
        "en": "Variables store intermediate values during procedural SQL execution.",
        "pt": "Variaveis armazenam valores intermediarios durante execucao procedural SQL.",
        "fr": "Les variables stockent des valeurs intermediaires pendant l'execution SQL procedurale.",
        "es": "Las variables almacenan valores intermedios durante la ejecucion SQL procedural.",
        "it": "Le variabili memorizzano valori intermedi durante l'esecuzione SQL procedurale.",
        "de": "Variablen speichern Zwischenwerte waehrend der prozeduralen SQL-Ausfuehrung.",
    },
    "parameters": {
        "en": "Parameters make procedures and functions reusable with dynamic inputs.",
        "pt": "Parametros tornam procedures e funcoes reutilizaveis com entradas dinamicas.",
        "fr": "Les parametres rendent procedures et fonctions reutilisables avec des entrees dynamiques.",
        "es": "Los parametros hacen reutilizables procedimientos y funciones con entradas dinamicas.",
        "it": "I parametri rendono riutilizzabili procedure e funzioni con input dinamici.",
        "de": "Parameter machen Prozeduren und Funktionen mit dynamischen Eingaben wiederverwendbar.",
    },
    "control structures": {
        "en": "Control structures (IF, LOOP, WHILE) manage flow inside procedural SQL routines.",
        "pt": "Estruturas de controle (IF, LOOP, WHILE) gerenciam fluxo em rotinas SQL procedurais.",
        "fr": "Les structures de controle (IF, LOOP, WHILE) pilotent le flux dans les routines SQL procedurales.",
        "es": "Las estructuras de control (IF, LOOP, WHILE) gestionan el flujo en rutinas SQL procedurales.",
        "it": "Le strutture di controllo (IF, LOOP, WHILE) gestiscono il flusso nelle routine SQL procedurali.",
        "de": "Kontrollstrukturen (IF, LOOP, WHILE) steuern den Ablauf in prozeduralen SQL-Routinen.",
    },
    "backup and restore": {
        "en": "Backup and restore strategies protect against data loss and support disaster recovery.",
        "pt": "Estrategias de backup e restore protegem contra perda de dados e suportam recuperacao de desastre.",
        "fr": "Les strategies de sauvegarde et restauration protegent contre la perte de donnees et soutiennent la reprise d'activite.",
        "es": "Las estrategias de respaldo y restauracion protegen contra la perdida de datos y soportan recuperacion ante desastres.",
        "it": "Le strategie di backup e ripristino proteggono dalla perdita di dati e supportano il disaster recovery.",
        "de": "Backup- und Wiederherstellungsstrategien schuetzen vor Datenverlust und unterstuetzen Disaster Recovery.",
    },
    "erd": {
        "en": "ERD diagrams visualize entities and relationships, helping teams align schema design.",
        "pt": "Diagramas ERD visualizam entidades e relacionamentos, ajudando equipes a alinhar o design do schema.",
        "fr": "Les diagrammes ERD visualisent les entites et relations, aidant les equipes a aligner la conception du schema.",
        "es": "Los diagramas ERD visualizan entidades y relaciones, ayudando a alinear el diseno del esquema.",
        "it": "I diagrammi ERD visualizzano entita e relazioni, aiutando i team ad allineare il design dello schema.",
        "de": "ERD-Diagramme visualisieren Entitaeten und Beziehungen und helfen Teams beim abgestimmten Schemadesign.",
    },
    "analytical queries": {
        "en": "Analytical queries transform operational data into decision-ready metrics and insights.",
        "pt": "Consultas analiticas transformam dados operacionais em metricas e insights para decisao.",
        "fr": "Les requetes analytiques transforment les donnees operationnelles en metriques et insights decisionnels.",
        "es": "Las consultas analiticas transforman datos operativos en metricas e insights para decision.",
        "it": "Le query analitiche trasformano dati operativi in metriche e insight utili alle decisioni.",
        "de": "Analytische Abfragen wandeln operative Daten in entscheidungsreife Kennzahlen und Erkenntnisse um.",
    },
    "merge / upsert": {
        "en": "MERGE/UPSERT performs insert-or-update logic in one statement for synchronization workflows.",
        "pt": "MERGE/UPSERT executa logica de inserir-ou-atualizar em um comando para sincronizacao.",
        "fr": "MERGE/UPSERT execute une logique insertion-ou-mise-a-jour en une seule instruction pour la synchronisation.",
        "es": "MERGE/UPSERT ejecuta logica insertar-o-actualizar en una sola instruccion para sincronizacion.",
        "it": "MERGE/UPSERT esegue logica inserisci-o-aggiorna in una singola istruzione per sincronizzazione.",
        "de": "MERGE/UPSERT fuehrt Insert-oder-Update-Logik in einer Anweisung fuer Synchronisationsprozesse aus.",
    },
    "lead / lag": {
        "en": "LEAD and LAG compare values with next/previous rows for trend and delta analysis.",
        "pt": "LEAD e LAG comparam valores com linhas seguintes/anteriores para analise de tendencia e variacao.",
        "fr": "LEAD et LAG comparent des valeurs avec les lignes suivantes/precedentes pour analyser tendances et ecarts.",
        "es": "LEAD y LAG comparan valores con filas siguientes/anteriores para analizar tendencias y variaciones.",
        "it": "LEAD e LAG confrontano valori con righe successive/precedenti per analisi di trend e variazioni.",
        "de": "LEAD und LAG vergleichen Werte mit naechsten/vorherigen Zeilen fuer Trend- und Delta-Analysen.",
    },
}


def _concept_key(concept: str) -> str:
    return " ".join(concept.strip().lower().split())


def _native_concept_fallback(concept: str, lang: str) -> str:
    c = _localize_phrase(concept, lang)
    if lang == "fr":
        return f"Ce concept ({c}) est essentiel pour construire des requetes fiables. Verifiez vos resultats pas a pas et validez la logique metier." 
    if lang == "es":
        return f"Este concepto ({c}) es clave para construir consultas SQL confiables. Valida los resultados paso a paso y confirma la logica de negocio."
    if lang == "it":
        return f"Questo concetto ({c}) e fondamentale per costruire query SQL affidabili. Verifica i risultati passo dopo passo e conferma la logica di business."
    if lang == "de":
        return f"Dieses Konzept ({c}) ist zentral fuer zuverlaessige SQL-Abfragen. Pruefen Sie Ergebnisse schrittweise und bestaetigen Sie die Geschaeftslogik."
    return _t_content("explanation_default", lang)


def _concept_explanation(concept: str, lang: str = "en") -> str:
    default_txt = _t_content("explanation_default", lang)
    concept_key = _concept_key(concept)
    exact = _EXACT_CONCEPT_EXPLANATIONS.get(concept_key)
    exact_en = None
    if exact:
        if lang in exact:
            return exact[lang]
        exact_en = exact.get("en")
    concept_upper = concept.upper()
    if "JOIN" in concept_upper:
        return {
            "en": "JOIN combines rows from multiple tables using matching keys. Use INNER JOIN for intersections and LEFT JOIN when you must keep all rows from the left table.",
            "pt": "JOIN combina linhas de varias tabelas por chaves relacionadas. Use INNER JOIN para intersecoes e LEFT JOIN quando precisar manter todas as linhas da tabela da esquerda.",
            "fr": "JOIN combine des lignes de plusieurs tables via des cles correspondantes. Utilisez INNER JOIN pour l'intersection et LEFT JOIN pour conserver toutes les lignes de gauche.",
            "es": "JOIN combina filas de varias tablas usando claves coincidentes. Usa INNER JOIN para interseccion y LEFT JOIN cuando necesites conservar todas las filas de la tabla izquierda.",
            "it": "JOIN combina righe di piu tabelle usando chiavi corrispondenti. Usa INNER JOIN per l'intersezione e LEFT JOIN quando devi mantenere tutte le righe della tabella sinistra.",
            "de": "JOIN verbindet Zeilen aus mehreren Tabellen ueber passende Schluessel. Verwenden Sie INNER JOIN fuer Schnittmengen und LEFT JOIN, wenn alle linken Zeilen erhalten bleiben sollen.",
        }.get(lang, default_txt)
    if "GROUP BY" in concept_upper:
        return {
            "en": "GROUP BY forms buckets of rows. Aggregate functions like COUNT, SUM and AVG are then computed per bucket.",
            "pt": "GROUP BY cria grupos de linhas. Funcoes de agregacao como COUNT, SUM e AVG sao calculadas por grupo.",
            "fr": "GROUP BY cree des groupes de lignes. Les fonctions d'agregation comme COUNT, SUM et AVG sont calculees par groupe.",
            "es": "GROUP BY crea grupos de filas. Las funciones de agregacion como COUNT, SUM y AVG se calculan por grupo.",
            "it": "GROUP BY crea gruppi di righe. Funzioni di aggregazione come COUNT, SUM e AVG vengono calcolate per gruppo.",
            "de": "GROUP BY bildet Gruppen von Zeilen. Aggregatfunktionen wie COUNT, SUM und AVG werden pro Gruppe berechnet.",
        }.get(lang, default_txt)
    if "HAVING" in concept_upper:
        return {
            "en": "HAVING filters grouped results after aggregation, while WHERE filters raw rows before grouping.",
            "pt": "HAVING filtra resultados agrupados apos agregacao, enquanto WHERE filtra linhas brutas antes do agrupamento.",
            "fr": "HAVING filtre les resultats groupes apres agregation, tandis que WHERE filtre les lignes avant regroupement.",
            "es": "HAVING filtra resultados agrupados despues de agregar, mientras WHERE filtra filas antes de agrupar.",
            "it": "HAVING filtra risultati aggregati dopo il raggruppamento, mentre WHERE filtra le righe prima del GROUP BY.",
            "de": "HAVING filtert gruppierte Ergebnisse nach der Aggregation, waehrend WHERE Rohzeilen vor der Gruppierung filtert.",
        }.get(lang, default_txt)
    if "WINDOW" in concept_upper or "RANK" in concept_upper or "ROW_NUMBER" in concept_upper:
        return {
            "en": "Window functions calculate metrics across related rows without collapsing them. They are ideal for ranking, running totals and time comparisons.",
            "pt": "Funcoes de janela calculam metricas entre linhas relacionadas sem colapsar o conjunto. Sao ideais para ranking, acumulados e comparacoes temporais.",
            "fr": "Les fonctions fenetre calculent des metriques sur des lignes liees sans les fusionner. Elles sont ideales pour classement, cumuls et comparaisons temporelles.",
            "es": "Las funciones de ventana calculan metricas sobre filas relacionadas sin colapsarlas. Son ideales para ranking, acumulados y comparaciones temporales.",
            "it": "Le funzioni finestra calcolano metriche su righe correlate senza collassarle. Sono ideali per ranking, cumulati e confronti temporali.",
            "de": "Window-Funktionen berechnen Kennzahlen ueber zusammenhaengende Zeilen, ohne sie zusammenzufassen. Ideal fuer Rankings, laufende Summen und Zeitvergleiche.",
        }.get(lang, default_txt)
    if "CTE" in concept_upper:
        return {
            "en": "A CTE (WITH clause) lets you break complex logic into readable steps and reuse intermediate datasets in one query.",
            "pt": "Uma CTE (clausula WITH) permite dividir logica complexa em etapas legiveis e reutilizar resultados intermediarios em uma consulta.",
            "fr": "Une CTE (clause WITH) permet de decomposer une logique complexe en etapes lisibles et de reutiliser des jeux intermediaires.",
            "es": "Una CTE (clausula WITH) permite dividir logica compleja en pasos legibles y reutilizar resultados intermedios en una sola consulta.",
            "it": "Una CTE (clausola WITH) permette di scomporre logiche complesse in passaggi leggibili e riutilizzare risultati intermedi in una query.",
            "de": "Eine CTE (WITH-Klausel) zerlegt komplexe Logik in lesbare Schritte und erlaubt die Wiederverwendung von Zwischenergebnissen.",
        }.get(lang, default_txt)
    if "SUBQUER" in concept_upper:
        return {
            "en": "Subqueries embed one query inside another. Use them for filtering, comparison, or building derived datasets.",
            "pt": "Subconsultas inserem uma consulta dentro de outra. Use para filtros, comparacoes e conjuntos derivados.",
            "fr": "Les sous-requetes integrent une requete dans une autre. Utilisez-les pour filtrer, comparer ou construire des jeux derives.",
            "es": "Las subconsultas insertan una consulta dentro de otra. Usalas para filtrar, comparar o crear conjuntos derivados.",
            "it": "Le sottoquery inseriscono una query dentro un'altra. Usale per filtri, confronti o dataset derivati.",
            "de": "Unterabfragen betten eine Abfrage in eine andere ein. Nutzen Sie sie fuer Filter, Vergleiche und abgeleitete Datensaetze.",
        }.get(lang, default_txt)
    if "INDEX" in concept_upper:
        return {
            "en": "Indexes accelerate read queries by avoiding full table scans, but they add overhead to INSERT/UPDATE/DELETE operations.",
            "pt": "Indices aceleram consultas de leitura evitando full scan, mas aumentam o custo de INSERT/UPDATE/DELETE.",
            "fr": "Les index accelerent les lectures en evitant les scans complets, mais ajoutent du cout aux INSERT/UPDATE/DELETE.",
            "es": "Los indices aceleran lecturas evitando escaneos completos, pero agregan costo a INSERT/UPDATE/DELETE.",
            "it": "Gli indici accelerano le letture evitando scansioni complete, ma aumentano il costo di INSERT/UPDATE/DELETE.",
            "de": "Indizes beschleunigen Leseabfragen durch weniger Vollscans, erhoehen aber die Kosten bei INSERT/UPDATE/DELETE.",
        }.get(lang, default_txt)
    if "TRANSACTION" in concept_upper or "COMMIT" in concept_upper or "ROLLBACK" in concept_upper:
        return {
            "en": "Transactions guarantee atomicity: either all operations succeed (COMMIT) or all are reverted (ROLLBACK).",
            "pt": "Transacoes garantem atomicidade: ou todas as operacoes sao confirmadas (COMMIT) ou todas sao desfeitas (ROLLBACK).",
            "fr": "Les transactions garantissent l'atomicite: soit tout est valide (COMMIT), soit tout est annule (ROLLBACK).",
            "es": "Las transacciones garantizan atomicidad: o todo confirma (COMMIT) o todo se revierte (ROLLBACK).",
            "it": "Le transazioni garantiscono atomicita: o tutte le operazioni vengono confermate (COMMIT) o annullate (ROLLBACK).",
            "de": "Transaktionen garantieren Atomaritaet: entweder alles wird bestaetigt (COMMIT) oder alles zurueckgesetzt (ROLLBACK).",
        }.get(lang, default_txt)
    if "NORMALIZATION" in concept_upper or "1NF" in concept_upper or "2NF" in concept_upper or "3NF" in concept_upper:
        return {
            "en": "Normalization reduces redundancy and update anomalies by structuring data into clear entities and relationships.",
            "pt": "Normalizacao reduz redundancia e anomalias de atualizacao ao estruturar dados em entidades e relacionamentos claros.",
            "fr": "La normalisation reduit la redondance et les anomalies en structurant les donnees en entites et relations claires.",
            "es": "La normalizacion reduce redundancia y anomalias al estructurar datos en entidades y relaciones claras.",
            "it": "La normalizzazione riduce ridondanza e anomalie strutturando i dati in entita e relazioni chiare.",
            "de": "Normalisierung reduziert Redundanz und Update-Anomalien durch klare Entitaeten und Beziehungen.",
        }.get(lang, default_txt)
    if "SECURITY" in concept_upper or "PERMISSION" in concept_upper or "ROLE" in concept_upper:
        return {
            "en": "Database security controls who can read or change data. Use least-privilege roles and audit critical operations.",
            "pt": "Seguranca de banco controla quem pode ler ou alterar dados. Use papeis de menor privilegio e auditoria em operacoes criticas.",
            "fr": "La securite base controle qui peut lire ou modifier les donnees. Utilisez le moindre privilege et auditez les operations critiques.",
            "es": "La seguridad de base controla quien puede leer o modificar datos. Usa minimo privilegio y auditoria en operaciones criticas.",
            "it": "La sicurezza del database controlla chi puo leggere o modificare i dati. Usa privilegi minimi e audit sulle operazioni critiche.",
            "de": "Datenbanksicherheit steuert, wer Daten lesen oder aendern darf. Nutzen Sie Least-Privilege und Audit fuer kritische Operationen.",
        }.get(lang, default_txt)
    if "ORDER BY" in concept_upper:
        return {
            "en": "ORDER BY defines deterministic sorting. Always add it when output order matters.",
            "pt": "ORDER BY define ordenacao deterministica. Use sempre quando a ordem de saida importar.",
            "fr": "ORDER BY definit un tri deterministe. Utilisez-le quand l'ordre de sortie est important.",
            "es": "ORDER BY define orden determinista. Usalo cuando el orden de salida sea importante.",
            "it": "ORDER BY definisce un ordinamento deterministico. Usalo quando l'ordine di output e importante.",
            "de": "ORDER BY definiert eine deterministische Sortierung. Nutzen Sie es, wenn die Ausgabereihenfolge wichtig ist.",
        }.get(lang, default_txt)
    if "DISTINCT" in concept_upper:
        return {
            "en": "DISTINCT removes duplicate rows from the selected projection.",
            "pt": "DISTINCT remove linhas duplicadas da projecao selecionada.",
            "fr": "DISTINCT supprime les doublons dans la projection selectionnee.",
            "es": "DISTINCT elimina filas duplicadas en la proyeccion seleccionada.",
            "it": "DISTINCT rimuove righe duplicate nella proiezione selezionata.",
            "de": "DISTINCT entfernt doppelte Zeilen in der ausgewaehlten Projektion.",
        }.get(lang, default_txt)
    if "LIMIT" in concept_upper or "TOP" in concept_upper:
        return {
            "en": "LIMIT/TOP restricts returned row count. Combine with ORDER BY for reproducible outputs.",
            "pt": "LIMIT/TOP restringe a quantidade de linhas retornadas. Combine com ORDER BY para resultados reproduziveis.",
            "fr": "LIMIT/TOP limite le nombre de lignes renvoyees. Combinez avec ORDER BY pour des sorties reproductibles.",
            "es": "LIMIT/TOP limita la cantidad de filas devueltas. Combinelo con ORDER BY para resultados reproducibles.",
            "it": "LIMIT/TOP limita il numero di righe restituite. Combinalo con ORDER BY per output riproducibili.",
            "de": "LIMIT/TOP begrenzt die Rueckgabezeilen. Kombinieren Sie es mit ORDER BY fuer reproduzierbare Ergebnisse.",
        }.get(lang, default_txt)
    if "ALIASES" in concept_upper or "ALIAS" in concept_upper:
        return {
            "en": "Aliases rename tables or columns for readability, especially in joins and analytical queries.",
            "pt": "Aliases renomeiam tabelas ou colunas para legibilidade, especialmente em joins e analises.",
            "fr": "Les alias renommment tables ou colonnes pour la lisibilite, surtout avec des jointures et analyses.",
            "es": "Los alias renombran tablas o columnas para mejorar legibilidad, especialmente en joins y analitica.",
            "it": "Gli alias rinominano tabelle o colonne per migliorare la leggibilita, specie con join e analisi.",
            "de": "Aliasse benennen Tabellen oder Spalten zur besseren Lesbarkeit um, besonders bei Joins und Analysen.",
        }.get(lang, default_txt)
    if "ARITHMETIC" in concept_upper:
        return {
            "en": "Arithmetic expressions compute derived metrics such as revenue, margin, or discount.",
            "pt": "Expressoes aritmeticas calculam metricas derivadas como receita, margem ou desconto.",
            "fr": "Les expressions arithmetiques calculent des metriques derivees comme revenu, marge ou remise.",
            "es": "Las expresiones aritmeticas calculan metricas derivadas como ingresos, margen o descuento.",
            "it": "Le espressioni aritmetiche calcolano metriche derivate come ricavi, margine o sconto.",
            "de": "Arithmetische Ausdruecke berechnen abgeleitete Kennzahlen wie Umsatz, Marge oder Rabatt.",
        }.get(lang, default_txt)
    if "AND / OR / NOT" in concept_upper:
        return {
            "en": "Boolean operators combine predicates. Use parentheses to make precedence explicit.",
            "pt": "Operadores booleanos combinam predicados. Use parenteses para explicitar a precedencia.",
            "fr": "Les operateurs booleens combinent des predicats. Utilisez des parentheses pour expliciter la priorite.",
            "es": "Los operadores booleanos combinan predicados. Usa parentesis para dejar clara la precedencia.",
            "it": "Gli operatori booleani combinano predicati. Usa parentesi per rendere esplicita la precedenza.",
            "de": "Boolesche Operatoren kombinieren Praedikate. Verwenden Sie Klammern fuer klare Prioritaet.",
        }.get(lang, default_txt)
    if "CASE" in concept_upper:
        return {
            "en": "CASE applies conditional business logic inside queries for labels and data bucketing.",
            "pt": "CASE aplica logica condicional de negocio na consulta para rotulos e agrupamentos.",
            "fr": "CASE applique une logique conditionnelle metier dans la requete pour etiquettes et regroupements.",
            "es": "CASE aplica logica condicional de negocio en la consulta para etiquetas y clasificacion.",
            "it": "CASE applica logica condizionale di business nella query per etichette e raggruppamenti.",
            "de": "CASE wendet bedingte Geschaeftslogik in Abfragen fuer Labels und Gruppierungen an.",
        }.get(lang, default_txt)
    if "COUNT" in concept_upper or "SUM" in concept_upper or "AVG" in concept_upper or "MIN" in concept_upper or "MAX" in concept_upper:
        return {
            "en": "Aggregate functions summarize many rows into business metrics such as totals, averages, and extremes.",
            "pt": "Funcoes de agregacao resumem muitas linhas em metricas de negocio como totais, medias e extremos.",
            "fr": "Les fonctions d'agregation resumment de nombreuses lignes en metriques metier: totaux, moyennes, extremes.",
            "es": "Las funciones de agregacion resumen muchas filas en metricas de negocio: totales, promedios y extremos.",
            "it": "Le funzioni di aggregazione riassumono molte righe in metriche di business: totali, medie ed estremi.",
            "de": "Aggregatfunktionen verdichten viele Zeilen zu Geschaeftskennzahlen wie Summen, Durchschnitten und Extremwerten.",
        }.get(lang, default_txt)
    if "EXISTS" in concept_upper:
        return {
            "en": "EXISTS checks whether related rows exist and is often efficient for semi-join logic.",
            "pt": "EXISTS verifica se linhas relacionadas existem e costuma ser eficiente para logica de semi-join.",
            "fr": "EXISTS verifie l'existence de lignes reliees et est souvent efficace pour une logique de semi-jointure.",
            "es": "EXISTS verifica si existen filas relacionadas y suele ser eficiente para logica de semi-join.",
            "it": "EXISTS verifica se esistono righe correlate ed e spesso efficiente per logiche di semi-join.",
            "de": "EXISTS prueft, ob verknuepfte Zeilen existieren, und ist oft effizient fuer Semi-Join-Logik.",
        }.get(lang, default_txt)
    if "UNION" in concept_upper:
        return {
            "en": "UNION combines result sets and removes duplicates; UNION ALL keeps duplicates and is faster.",
            "pt": "UNION combina conjuntos de resultados e remove duplicatas; UNION ALL mantem duplicatas e e mais rapido.",
            "fr": "UNION combine des resultats et supprime les doublons; UNION ALL conserve les doublons et est plus rapide.",
            "es": "UNION combina conjuntos y elimina duplicados; UNION ALL conserva duplicados y suele ser mas rapido.",
            "it": "UNION combina risultati e rimuove duplicati; UNION ALL mantiene duplicati ed e piu veloce.",
            "de": "UNION kombiniert Ergebnismengen und entfernt Duplikate; UNION ALL behaelt Duplikate und ist schneller.",
        }.get(lang, default_txt)
    if "SELECT" in concept_upper:
        return {
            "en": "SELECT defines which columns to return. Start with focused projections and expand only when needed.",
            "pt": "SELECT define quais colunas retornar. Comece com projecoes focadas e expanda apenas quando necessario.",
            "fr": "SELECT definit quelles colonnes retourner. Commencez avec une projection ciblee puis etendez si necessaire.",
            "es": "SELECT define que columnas devolver. Comienza con una proyeccion enfocada y amplia solo cuando haga falta.",
            "it": "SELECT definisce quali colonne restituire. Parti da una proiezione mirata ed espandi solo quando serve.",
            "de": "SELECT legt fest, welche Spalten zurueckgegeben werden. Starten Sie mit fokussierter Projektion und erweitern Sie bei Bedarf.",
        }.get(lang, default_txt)
    if "WHERE" in concept_upper or "LIKE" in concept_upper or "BETWEEN" in concept_upper or "IN" in concept_upper:
        return {
            "en": "Filtering narrows datasets to relevant rows. Combine predicates carefully to avoid accidental exclusions.",
            "pt": "Filtragem reduz o conjunto para linhas relevantes. Combine predicados com cuidado para evitar exclusoes indevidas.",
            "fr": "Le filtrage reduit le jeu de donnees aux lignes pertinentes. Combinez les predicats avec soin.",
            "es": "El filtrado reduce el conjunto a filas relevantes. Combina predicados con cuidado para evitar exclusiones indebidas.",
            "it": "Il filtraggio restringe il dataset alle righe rilevanti. Combina i predicati con attenzione.",
            "de": "Filterung reduziert Datensaetze auf relevante Zeilen. Kombinieren Sie Praedikate sorgfaeltig.",
        }.get(lang, default_txt)
    if "NULL" in concept_upper:
        return {
            "en": "NULL means unknown or missing. Use IS NULL / IS NOT NULL instead of equality operators.",
            "pt": "NULL significa desconhecido ou ausente. Use IS NULL / IS NOT NULL em vez de operadores de igualdade.",
            "fr": "NULL signifie inconnu ou manquant. Utilisez IS NULL / IS NOT NULL au lieu d'operateurs d'egalite.",
            "es": "NULL significa desconocido o ausente. Usa IS NULL / IS NOT NULL en lugar de operadores de igualdad.",
            "it": "NULL significa sconosciuto o mancante. Usa IS NULL / IS NOT NULL invece degli operatori di uguaglianza.",
            "de": "NULL bedeutet unbekannt oder fehlend. Verwenden Sie IS NULL / IS NOT NULL statt Gleichheitsoperatoren.",
        }.get(lang, default_txt)
    if "VIEW" in concept_upper:
        return {
            "en": "Views encapsulate query logic into reusable virtual tables, improving report consistency.",
            "pt": "Views encapsulam logica de consulta em tabelas virtuais reutilizaveis, melhorando consistencia de relatorios.",
            "fr": "Les vues encapsulent la logique de requete dans des tables virtuelles reutilisables, renforcant la coherence des rapports.",
            "es": "Las vistas encapsulan la logica de consulta en tablas virtuales reutilizables y mejoran la consistencia de reportes.",
            "it": "Le viste incapsulano la logica di query in tabelle virtuali riutilizzabili, migliorando la coerenza dei report.",
            "de": "Views kapseln Abfragelogik in wiederverwendbaren virtuellen Tabellen und verbessern die Berichtskonsistenz.",
        }.get(lang, default_txt)
    if "PROCEDURE" in concept_upper or "TRIGGER" in concept_upper or "FUNCTION" in concept_upper:
        return {
            "en": "Procedures, functions and triggers automate repetitive business rules close to the data layer.",
            "pt": "Procedures, funcoes e triggers automatizam regras repetitivas de negocio proximas da camada de dados.",
            "fr": "Procedures, fonctions et triggers automatisent des regles metier repetitives au plus pres des donnees.",
            "es": "Procedimientos, funciones y triggers automatizan reglas de negocio repetitivas cerca de la capa de datos.",
            "it": "Procedure, funzioni e trigger automatizzano regole di business ripetitive vicino al livello dati.",
            "de": "Prozeduren, Funktionen und Trigger automatisieren wiederkehrende Geschaeftsregeln nahe der Datenebene.",
        }.get(lang, default_txt)
    if "DATABASE" in concept_upper or "TABLE" in concept_upper or "KEY" in concept_upper:
        return {
            "en": "Relational databases organize data in tables linked by keys. Good key design is essential for quality and performance.",
            "pt": "Bancos relacionais organizam dados em tabelas ligadas por chaves. Bom desenho de chaves e essencial para qualidade e performance.",
            "fr": "Les bases relationnelles organisent les donnees en tables reliees par des cles. Un bon design de cles est essentiel.",
            "es": "Las bases relacionales organizan datos en tablas unidas por claves. Un buen diseno de claves es esencial.",
            "it": "I database relazionali organizzano i dati in tabelle collegate da chiavi. Un buon design delle chiavi e essenziale.",
            "de": "Relationale Datenbanken organisieren Daten in durch Schluessel verknuepften Tabellen. Gutes Schluesseldesign ist entscheidend.",
        }.get(lang, default_txt)

    if exact_en:
        if lang in {"fr", "es", "it", "de"}:
            return _native_concept_fallback(concept, lang)
        return exact_en
    return default_txt


def _module_reference_links(mod: dict) -> list[tuple[str, str]]:
    concepts_text = " ".join(mod.get("concepts", [])).upper()
    links = [
        ("SQLBolt Interactive Lessons", "https://sqlbolt.com/"),
        ("SQLite SELECT Documentation", "https://www.sqlite.org/lang_select.html"),
        ("PostgreSQL Tutorial", "https://www.postgresql.org/docs/current/tutorial-sql.html"),
    ]

    if "JOIN" in concepts_text:
        links.append(("PostgreSQL Joins", "https://www.postgresql.org/docs/current/tutorial-join.html"))
    if "GROUP BY" in concepts_text or "HAVING" in concepts_text:
        links.append(("SQLite Aggregate Functions", "https://www.sqlite.org/lang_aggfunc.html"))
    if "WINDOW" in concepts_text or "RANK" in concepts_text or "ROW_NUMBER" in concepts_text:
        links.append(("PostgreSQL Window Functions", "https://www.postgresql.org/docs/current/tutorial-window.html"))
    if "CTE" in concepts_text or "SUBQUER" in concepts_text:
        links.append(("PostgreSQL WITH Queries (CTE)", "https://www.postgresql.org/docs/current/queries-with.html"))
    if "INDEX" in concepts_text or "PERFORMANCE" in concepts_text:
        links.append(("SQLite Query Planner", "https://www.sqlite.org/queryplanner.html"))
    if "SECURITY" in concepts_text or "ROLE" in concepts_text or "PERMISSION" in concepts_text:
        links.append(("PostgreSQL Privileges", "https://www.postgresql.org/docs/current/ddl-priv.html"))

    return links


def _build_concept_deep_dive(mod: dict, lang: str) -> str:
    sections = []
    for concept in mod.get("concepts", []):
        sections.append(
            "<details class=\"mb-2\">"
            f"<summary><strong><code>{_localize_phrase(concept, lang)}</code></strong></summary>"
            f"<p class=\"mt-2 mb-0\">{_concept_explanation(concept, lang)}</p>"
            "</details>"
        )
    return "".join(sections)


def _build_reference_section(mod: dict, lang: str) -> str:
    links = _module_reference_links(mod)
    localized_labels = {
        "SQLBolt Interactive Lessons": {
            "pt": "Licoes Interativas SQLBolt",
            "fr": "Lecons Interactives SQLBolt",
            "es": "Lecciones Interactivas SQLBolt",
            "it": "Lezioni Interattive SQLBolt",
            "de": "Interaktive SQLBolt-Lektionen",
        },
        "SQLite SELECT Documentation": {
            "pt": "Documentacao SELECT do SQLite",
            "fr": "Documentation SELECT SQLite",
            "es": "Documentacion SELECT de SQLite",
            "it": "Documentazione SELECT di SQLite",
            "de": "SQLite SELECT Dokumentation",
        },
        "PostgreSQL Tutorial": {
            "pt": "Tutorial PostgreSQL",
            "fr": "Tutoriel PostgreSQL",
            "es": "Tutorial de PostgreSQL",
            "it": "Tutorial PostgreSQL",
            "de": "PostgreSQL Tutorial",
        },
        "PostgreSQL Joins": {
            "pt": "Joins no PostgreSQL",
            "fr": "Jointures PostgreSQL",
            "es": "Joins en PostgreSQL",
            "it": "Join in PostgreSQL",
            "de": "PostgreSQL Verknuepfungen",
        },
        "SQLite Aggregate Functions": {
            "pt": "Funcoes de Agregacao do SQLite",
            "fr": "Fonctions d'Agregation SQLite",
            "es": "Funciones de Agregacion de SQLite",
            "it": "Funzioni di Aggregazione SQLite",
            "de": "SQLite Aggregatfunktionen",
        },
        "PostgreSQL Window Functions": {
            "pt": "Funcoes de Janela no PostgreSQL",
            "fr": "Fonctions Fenetre PostgreSQL",
            "es": "Funciones de Ventana en PostgreSQL",
            "it": "Funzioni Finestra in PostgreSQL",
            "de": "PostgreSQL Fensterfunktionen",
        },
        "PostgreSQL WITH Queries (CTE)": {
            "pt": "Consultas WITH (CTE) no PostgreSQL",
            "fr": "Requetes WITH (CTE) PostgreSQL",
            "es": "Consultas WITH (CTE) en PostgreSQL",
            "it": "Query WITH (CTE) in PostgreSQL",
            "de": "PostgreSQL WITH-Abfragen (CTE)",
        },
        "SQLite Query Planner": {
            "pt": "Planejador de Consultas do SQLite",
            "fr": "Planificateur de Requetes SQLite",
            "es": "Planificador de Consultas de SQLite",
            "it": "Query Planner di SQLite",
            "de": "SQLite Abfrageplaner",
        },
        "PostgreSQL Privileges": {
            "pt": "Privilegios no PostgreSQL",
            "fr": "Privileges PostgreSQL",
            "es": "Privilegios en PostgreSQL",
            "it": "Privilegi in PostgreSQL",
            "de": "PostgreSQL Berechtigungen",
        },
    }
    link_items = "".join(
        [
            f'<li><a href="{url}" target="_blank" rel="noopener noreferrer">{localized_labels.get(label, {}).get(lang, label)}</a></li>'
            for label, url in links
        ]
    )
    return f"<ul>{link_items}</ul>"

# ---------------------------------------------------------------------------
# Additional schemas for advanced modules
# ---------------------------------------------------------------------------

SAMPLE_SCHEMA_EMPLOYEES = """
CREATE TABLE IF NOT EXISTS departments (
    dept_id INTEGER PRIMARY KEY,
    dept_name TEXT NOT NULL,
    location TEXT
);
CREATE TABLE IF NOT EXISTS employees (
    emp_id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    dept_id INTEGER,
    salary DECIMAL(10,2),
    hire_date DATE,
    manager_id INTEGER,
    FOREIGN KEY (dept_id) REFERENCES departments(dept_id),
    FOREIGN KEY (manager_id) REFERENCES employees(emp_id)
);
"""

SAMPLE_DATA_EMPLOYEES = """
INSERT INTO departments VALUES (1,'Engineering','Paris'),(2,'Sales','Lyon'),(3,'HR','Marseille'),(4,'Finance','Paris');
INSERT INTO employees VALUES
(1,'Alice','Martin',1,6500,'2020-01-10',NULL),
(2,'Bob','Dupont',2,4200,'2021-03-15',1),
(3,'Clara','Morel',1,5800,'2019-07-01',1),
(4,'David','Simon',3,3900,'2022-06-20',1),
(5,'Eva','Bernard',4,5100,'2020-11-05',1),
(6,'Frank','Petit',2,3700,'2023-01-12',2),
(7,'Grace','Thomas',1,6200,'2018-04-22',1),
(8,'Hugo','Laurent',4,4800,'2021-09-30',5);
"""

COURSE_BLUEPRINT = [
    {
        "code": "sql101",
        "title": "Module 1 - Introduction to Databases & SQL",
        "level": "beginner",
        "minutes": 60,
        "concepts": [
            "What is a database",
            "Relational databases",
            "Tables, rows, columns",
            "Primary keys and foreign keys",
            "SQL language overview",
            "DBMS overview: PostgreSQL, MySQL, SQL Server, Oracle",
        ],
        "practical": [
            "Install a database system",
            "Create a simple database",
            "Create tables",
            "Insert sample data",
            "Identify relationships between tables",
        ],
        "mini_project": "Create a small Library database",
        "image_url": "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80",
        "exercise_sql": "SELECT name FROM sqlite_master WHERE type = 'table'",
    },
    {
        "code": "sql102",
        "title": "Module 2 - Basic SQL Queries",
        "level": "beginner",
        "minutes": 70,
        "concepts": ["SELECT", "WHERE", "ORDER BY", "DISTINCT", "LIMIT / TOP", "Aliases", "Arithmetic", "NULL values"],
        "practical": ["Retrieve customer data", "Filter products by price", "Sort employees by salary", "Use aliases in reports"],
        "mini_project": "Build basic business reports",
        "image_url": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1200&q=80",
        "exercise_sql": "SELECT DISTINCT country FROM customers ORDER BY country",
    },
    {
        "code": "sql103",
        "title": "Module 3 - Data Filtering & Conditions",
        "level": "beginner",
        "minutes": 70,
        "concepts": ["AND / OR / NOT", "BETWEEN", "IN", "LIKE", "Wildcards", "IS NULL / IS NOT NULL", "CASE"],
        "practical": ["Search customers by patterns", "Create conditional labels", "Filter sales data"],
        "mini_project": "Customer segmentation report",
        "image_url": "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?auto=format&fit=crop&w=1200&q=80",
        "exercise_sql": "SELECT order_id, CASE WHEN amount >= 500 THEN 'High' ELSE 'Standard' END AS segment FROM orders",
    },
    {
        "code": "sql104",
        "title": "Module 4 - Aggregation & Grouping",
        "level": "beginner",
        "minutes": 75,
        "concepts": ["COUNT", "SUM", "AVG", "MIN / MAX", "GROUP BY", "HAVING"],
        "practical": ["Calculate total sales", "Find average salaries", "Group products by category"],
        "mini_project": "Sales dashboard queries",
        "image_url": "https://images.unsplash.com/photo-1543286386-713bdd548da4?auto=format&fit=crop&w=1200&q=80",
        "exercise_sql": "SELECT status, COUNT(*) AS total_orders, SUM(amount) AS total_amount FROM orders GROUP BY status",
    },
    {
        "code": "sql105",
        "title": "Module 5 - Joins & Relationships",
        "level": "intermediate",
        "minutes": 90,
        "concepts": ["INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL OUTER JOIN", "SELF JOIN", "CROSS JOIN", "Relationship modeling"],
        "practical": ["Join customers and orders", "Build employee-manager hierarchy", "Combine multiple tables"],
        "mini_project": "E-commerce reporting system",
        "image_url": "https://images.unsplash.com/photo-1551281044-8b9b5be9b4a9?auto=format&fit=crop&w=1200&q=80",
        "exercise_sql": "SELECT c.first_name, c.last_name, o.order_id, o.amount FROM customers c INNER JOIN orders o ON c.customer_id = o.customer_id",
    },
    {
        "code": "sql106",
        "title": "Module 6 - Advanced SQL Queries",
        "level": "intermediate",
        "minutes": 90,
        "concepts": ["Subqueries", "Correlated subqueries", "CTE", "UNION / UNION ALL", "EXISTS", "Views"],
        "practical": ["Create reusable reports", "Build nested queries", "Create analytical views"],
        "mini_project": "Business intelligence query package",
        "image_url": "https://images.unsplash.com/photo-1526628953301-3e589a6a8b74?auto=format&fit=crop&w=1200&q=80",
        "exercise_sql": "WITH high_value AS (SELECT * FROM orders WHERE amount > 300) SELECT customer_id, COUNT(*) AS orders_count FROM high_value GROUP BY customer_id",
    },
    {
        "code": "sql107",
        "title": "Module 7 - Data Modification",
        "level": "intermediate",
        "minutes": 80,
        "concepts": ["INSERT", "UPDATE", "DELETE", "MERGE / UPSERT", "Transactions", "COMMIT / ROLLBACK"],
        "practical": ["Modify customer records", "Simulate transactions", "Restore data after rollback"],
        "mini_project": "Banking transaction simulation",
        "image_url": "https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?auto=format&fit=crop&w=1200&q=80",
        "exercise_sql": "SELECT product_id, product_name, stock, CASE WHEN stock < 80 THEN 'REORDER' ELSE 'OK' END AS inventory_status FROM products ORDER BY stock ASC",
    },
    {
        "code": "sql108",
        "title": "Module 8 - Database Design & Normalization",
        "level": "intermediate",
        "minutes": 95,
        "concepts": ["Database modeling", "ERD", "1NF, 2NF, 3NF", "Referential integrity", "Constraints"],
        "practical": ["Design a school database", "Normalize a dataset", "Create ER diagrams"],
        "mini_project": "Full database architecture design",
        "image_url": "https://images.unsplash.com/photo-1516116216624-53e697fedbea?auto=format&fit=crop&w=1200&q=80",
        "exercise_sql": "SELECT name, sql FROM sqlite_master WHERE type = 'table' ORDER BY name",
    },
    {
        "code": "sql109",
        "title": "Module 9 - Indexes & Performance",
        "level": "intermediate",
        "minutes": 90,
        "concepts": ["Indexes", "Query optimization", "Execution plans", "Performance tuning", "Partitioning basics"],
        "practical": ["Compare query performance", "Create indexes", "Optimize slow queries"],
        "mini_project": "Performance optimization challenge",
        "image_url": "https://images.unsplash.com/photo-1526378722484-bd91ca387e72?auto=format&fit=crop&w=1200&q=80",
        "exercise_sql": "SELECT status, COUNT(*) AS total_orders, ROUND(AVG(amount), 2) AS avg_amount FROM orders GROUP BY status ORDER BY avg_amount DESC",
    },
    {
        "code": "sql110",
        "title": "Module 10 - Stored Procedures & Functions",
        "level": "advanced",
        "minutes": 100,
        "concepts": ["Stored procedures", "Functions", "Parameters", "Variables", "Control structures", "Triggers"],
        "practical": ["Create procedures", "Automate updates", "Validate business rules"],
        "mini_project": "Automated payroll system",
        "image_url": "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?auto=format&fit=crop&w=1200&q=80",
        "exercise_sql": "SELECT customer_id, SUM(amount) AS total_spent FROM orders GROUP BY customer_id ORDER BY total_spent DESC",
    },
    {
        "code": "sql111",
        "title": "Module 11 - SQL for Data Analysis",
        "level": "advanced",
        "minutes": 100,
        "concepts": ["Window functions", "RANK / DENSE_RANK", "ROW_NUMBER", "LEAD / LAG", "Analytical queries"],
        "practical": ["Sales trend analysis", "Ranking reports", "Time-based comparisons"],
        "mini_project": "Analytical reporting solution",
        "image_url": "https://images.unsplash.com/photo-1488229297570-58520851e868?auto=format&fit=crop&w=1200&q=80",
        "exercise_sql": "SELECT customer_id, amount, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date DESC) AS rn FROM orders",
    },
    {
        "code": "sql112",
        "title": "Module 12 - Security & Administration",
        "level": "advanced",
        "minutes": 85,
        "concepts": ["Users and roles", "Permissions", "Backup and restore", "Database security", "Auditing basics"],
        "practical": ["Create user roles", "Configure permissions", "Backup and restore database"],
        "mini_project": "Secure database deployment",
        "image_url": "https://images.unsplash.com/photo-1563986768609-322da13575f3?auto=format&fit=crop&w=1200&q=80",
        "exercise_sql": "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') ORDER BY name",
    },
]

COURSE_CODE_MAP = {
    1: "sql101",
    2: "sql102",
    3: "sql103",
    4: "sql104",
    5: "sql201",
    6: "sql202",
    7: "sql203",
    8: "sql204",
    9: "sql301",
    10: "sql302",
    11: "sql303",
    12: "sql304",
}

SECONDARY_QUERY_SQL101 = {
    "sql101": "SELECT COUNT(*) AS total_tables FROM sqlite_master WHERE type = 'table'",
    "sql102": "SELECT customer_id, first_name, last_name FROM customers ORDER BY last_name ASC",
    "sql103": "SELECT order_id, amount FROM orders WHERE amount >= 300 ORDER BY amount DESC",
    "sql104": "SELECT country, COUNT(*) AS total_customers FROM customers GROUP BY country ORDER BY total_customers DESC",
    "sql202": "SELECT product_id, product_name, price FROM products WHERE price > 80 ORDER BY price DESC",
    "sql203": "SELECT customer_id, COUNT(*) AS total_orders FROM orders GROUP BY customer_id ORDER BY total_orders DESC",
    "sql204": "SELECT o.customer_id, SUM(oi.quantity * oi.unit_price) AS sales_value FROM orders o JOIN order_items oi ON oi.order_id = o.order_id GROUP BY o.customer_id ORDER BY sales_value DESC",
    "sql301": "SELECT product_name, stock FROM products ORDER BY stock ASC",
}

SECONDARY_QUERY_EMPLOYEE = {
    "sql302": "SELECT d.dept_name, COUNT(e.emp_id) AS headcount FROM departments d LEFT JOIN employees e ON e.dept_id = d.dept_id GROUP BY d.dept_name ORDER BY headcount DESC",
    "sql303": "SELECT emp_id, first_name, salary, RANK() OVER (ORDER BY salary DESC) AS salary_rank FROM employees",
    "sql304": "SELECT manager_id, COUNT(*) AS team_size FROM employees WHERE manager_id IS NOT NULL GROUP BY manager_id ORDER BY team_size DESC",
}


def _secondary_query(module_code: str, index: int) -> str:
    if index >= 10:
        return SECONDARY_QUERY_EMPLOYEE.get(module_code, "SELECT dept_name, location FROM departments ORDER BY dept_name")
    return SECONDARY_QUERY_SQL101.get(module_code, "SELECT customer_id, first_name FROM customers ORDER BY customer_id")


def _applied_query(module_code: str, index: int) -> str:
    if module_code in {"sql101", "sql102", "sql103", "sql104"}:
        return "SELECT c.country, COUNT(o.order_id) AS orders_count, ROUND(SUM(o.amount), 2) AS total_amount FROM customers c LEFT JOIN orders o ON o.customer_id = c.customer_id GROUP BY c.country ORDER BY total_amount DESC"
    if module_code in {"sql202", "sql203", "sql204", "sql301"}:
        return "SELECT p.category, COUNT(oi.order_item_id) AS lines, ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue FROM products p LEFT JOIN order_items oi ON oi.product_id = p.product_id GROUP BY p.category ORDER BY revenue DESC"
    return "SELECT d.dept_name, ROUND(AVG(e.salary), 2) AS avg_salary, COUNT(e.emp_id) AS employees FROM departments d LEFT JOIN employees e ON e.dept_id = d.dept_id GROUP BY d.dept_name ORDER BY avg_salary DESC"


def _build_module_content(mod: dict, module_number: int, lang: str = "en") -> str:
    concept_items = "".join([f"<li><code>{_localize_phrase(c, lang)}</code></li>" for c in mod["concepts"]])
    concept_dive = _build_concept_deep_dive(mod, lang)
    references_html = _build_reference_section(mod, lang)
    practical_rows = "".join(
        [f"<tr><td>{idx}</td><td>{_localize_phrase(task, lang)}</td></tr>" for idx, task in enumerate(mod["practical"], start=1)]
    )
    mini_project = _localize_phrase(mod["mini_project"], lang)
    objectives = [
        f"{_t_content('objective_master', lang)} <code>{_localize_phrase(c, lang)}</code>"
        for c in mod["concepts"][:3]
    ]
    if mod["practical"]:
        objectives.append(f"{_t_content('objective_apply', lang)} {_localize_phrase(mod['practical'][0], lang)}")
    objectives.append(_t_content("objective_validate", lang))
    objectives_html = "".join([f"<li>{item}</li>" for item in objectives])

    pitfalls_html = "".join(
        [f"<li>{_t_content('pitfall_1', lang)}</li>", f"<li>{_t_content('pitfall_2', lang)}</li>", f"<li>{_t_content('pitfall_3', lang)}</li>"]
    )

    checklist_html = "".join(
        [f"<li>{_t_content('check_1', lang)}</li>", f"<li>{_t_content('check_2', lang)}</li>", f"<li>{_t_content('check_3', lang)}</li>"]
    )
    return f"""
<div class="card border-0 shadow-sm mb-3 overflow-hidden">
  <img src="{mod['image_url']}" alt="{mod['title']}" style="width:100%;height:220px;object-fit:cover;" loading="lazy">
  <div class="card-body">
    <h4 class="mb-2">{mod['title']}</h4>
        <p class="text-muted mb-3">{_t_content('interactive_intro', lang)}</p>
        {_TIP_BOX('>>', _t_content('tip', lang))}
        <h5>{_t_content('core_concepts', lang)}</h5>
    <ul>{concept_items}</ul>
        <h5>{_t_content('learning_objectives', lang)}</h5>
        <ul>{objectives_html}</ul>
        <h5>{_t_content('concept_deep_dive', lang)}</h5>
        <p class="text-muted">{_t_content('concept_deep_dive_desc', lang)}</p>
        {concept_dive}
        {_WARN_BOX('!!', _t_content('warn', lang))}
        <h5>{_t_content('common_pitfalls', lang)}</h5>
        <ul>{pitfalls_html}</ul>
        <h5>{_t_content('practical_exercises', lang)}</h5>
    <table class="table table-sm table-striped">
            <thead><tr><th>#</th><th>{_t_content('task', lang)}</th></tr></thead>
      <tbody>{practical_rows}</tbody>
    </table>
        <h5>{_t_content('mini_project', lang)}</h5>
    <p><strong>{mini_project}</strong></p>
        <h5>{_t_content('references', lang)}</h5>
        {references_html}
        <h5>{_t_content('submission_checklist', lang)}</h5>
        <ul>{checklist_html}</ul>
        <h5>{_t_content('model_prompt', lang)}</h5>
        <p class="mb-0">{_t_content('model_prompt_text', lang)}</p>
  </div>
</div>
"""


def _build_lesson_content(base_mod: dict, module_number: int, lang: str, title: str, concepts: list[str], practical: list[str], mini_project: str) -> str:
    lesson_mod = {
        **base_mod,
        "title": title,
        "concepts": concepts,
        "practical": practical,
        "mini_project": mini_project,
    }
    return _build_module_content(lesson_mod, module_number, lang)


def _build_modules() -> list[dict]:
    modules = []
    for index, mod in enumerate(COURSE_BLUEPRINT, start=1):
        module_code = COURSE_CODE_MAP.get(index, mod["code"])
        module_title_i18n = {
            "en": mod["title"],
            "pt": mod["title"],
            "fr": mod["title"],
            "es": mod["title"],
            "it": mod["title"],
            "de": mod["title"],
        }
        module_description_i18n = {
            "en": f"{mod['title']} with concepts, practice labs, mini-project and visual examples.",
            "pt": f"{mod['title']} com conceitos, laboratorios praticos, mini-projeto e exemplos visuais.",
            "fr": f"{mod['title']} avec concepts, laboratoires pratiques, mini-projet et exemples visuels.",
            "es": f"{mod['title']} con conceptos, practicas, mini-proyecto y ejemplos visuales.",
            "it": f"{mod['title']} con concetti, laboratori pratici, mini-progetto ed esempi visivi.",
            "de": f"{mod['title']} mit Konzepten, Praxislabors, Mini-Projekt und visuellen Beispielen.",
        }

        if module_code == "sql201":
            module_title_i18n = {
                "en": "SQL 201: Joins & Aggregations",
                "pt": "SQL 201: Joins e Agregacoes",
                "fr": "SQL 201: Jointures et Agregations",
                "es": "SQL 201: Joins y Agregaciones",
                "it": "SQL 201: Join e Aggregazioni",
                "de": "SQL 201: Joins und Aggregationen",
            }
            module_description_i18n = {
                "en": "Master INNER/LEFT joins, GROUP BY, HAVING and multi-table analytics with practical labs.",
                "pt": "Domine INNER/LEFT joins, GROUP BY, HAVING e analise multi-tabelas com laboratorios praticos.",
                "fr": "Maitrisez INNER/LEFT JOIN, GROUP BY, HAVING et l'analyse multi-tables avec des laboratoires pratiques.",
                "es": "Domina INNER/LEFT JOIN, GROUP BY, HAVING y analitica multi-tabla con laboratorios practicos.",
                "it": "Padroneggia INNER/LEFT JOIN, GROUP BY, HAVING e analitica multi-tabella con laboratori pratici.",
                "de": "Beherrsche INNER/LEFT JOIN, GROUP BY, HAVING und Mehrtabellen-Analysen mit praktischen Labs.",
            }
        schema_sql = SAMPLE_SCHEMA_SQL101 if index < 10 else SAMPLE_SCHEMA_EMPLOYEES
        seed_sql = SAMPLE_DATA_SQL101 if index < 10 else SAMPLE_DATA_EMPLOYEES

        lesson_code = f"{module_code}-les1"
        exercise_code = f"{module_code}-les1-ex1"

        lessons = [
            {
                "code": lesson_code,
                "title_i18n": {
                    "en": f"{mod['title']} - Guided Lesson",
                    "pt": f"{mod['title']} - Licao Guiada",
                    "fr": f"{mod['title']} - Lecon Guidee",
                    "es": f"{mod['title']} - Leccion Guiada",
                    "it": f"{mod['title']} - Lezione Guidata",
                    "de": f"{mod['title']} - Gefuhrte Lektion",
                },
                "content_i18n": {
                    "en": _build_module_content(mod, index, "en"),
                    "pt": _build_module_content(mod, index, "pt"),
                    "fr": _build_module_content(mod, index, "fr"),
                    "es": _build_module_content(mod, index, "es"),
                    "it": _build_module_content(mod, index, "it"),
                    "de": _build_module_content(mod, index, "de"),
                },
                "sort_order": 1,
                "is_active": True,
                "exercises": [
                    {
                        "code": exercise_code,
                        "title_i18n": {
                            "en": f"{mod['title']} - Core Lab",
                            "pt": f"{mod['title']} - Laboratorio Central",
                            "fr": f"{mod['title']} - Laboratoire Central",
                            "es": f"{mod['title']} - Laboratorio Central",
                            "it": f"{mod['title']} - Laboratorio Principale",
                            "de": f"{mod['title']} - Kernlabor",
                        },
                        "description_i18n": {
                            "en": "Complete the core SQL challenge for this module.",
                            "pt": "Complete o desafio SQL principal deste modulo.",
                            "fr": "Terminez le defi SQL principal de ce module.",
                            "es": "Completa el desafio SQL principal de este modulo.",
                            "it": "Completa la sfida SQL principale di questo modulo.",
                            "de": "Schliesse die zentrale SQL-Aufgabe dieses Moduls ab.",
                        },
                        "exercise_type": "sql_query",
                        "difficulty": "medium" if index >= 5 else "easy",
                        "points_reward": 25 + (index * 2),
                        "expected_sql": mod["exercise_sql"],
                        "validation_mode": "result_match",
                        "hints_i18n": {
                            "en": [
                                "Read the schema explorer before writing your query.",
                                "Run the query in small steps and verify each output.",
                            ],
                            "pt": [
                                "Leia o explorador de esquema antes de escrever a query.",
                                "Execute em pequenos passos e valide a saida.",
                            ],
                            "fr": [
                                "Lisez le schema avant d'ecrire la requete.",
                                "Executez en petites etapes et verifiez la sortie.",
                            ],
                        },
                        "sort_order": 1,
                        "is_active": True,
                    },
                    {
                        "code": f"{module_code}-les1-ex2",
                        "title_i18n": {
                            "en": f"{mod['title']} - Validation Lab",
                            "pt": f"{mod['title']} - Laboratorio de Validacao",
                            "fr": f"{mod['title']} - Laboratoire de Validation",
                            "es": f"{mod['title']} - Laboratorio de Validacion",
                            "it": f"{mod['title']} - Laboratorio di Validazione",
                            "de": f"{mod['title']} - Validierungslabor",
                        },
                        "description_i18n": {
                            "en": "Write an alternative query and verify ordering/filters on real data.",
                            "pt": "Escreva uma query alternativa e valide ordenacao/filtros com dados reais.",
                            "fr": "Ecrivez une requete alternative et validez tri/filtres sur des donnees reelles.",
                            "es": "Escribe una consulta alternativa y valida orden/filtros con datos reales.",
                            "it": "Scrivi una query alternativa e valida ordinamento/filtri su dati reali.",
                            "de": "Schreiben Sie eine alternative Abfrage und validieren Sie Sortierung/Filter mit echten Daten.",
                        },
                        "exercise_type": "sql_query",
                        "difficulty": "medium" if index >= 5 else "easy",
                        "points_reward": 20 + (index * 2),
                        "expected_sql": _secondary_query(module_code, index),
                        "validation_mode": "result_match",
                        "hints_i18n": {
                            "en": [
                                "Check column aliases in the expected output.",
                                "Use ORDER BY to stabilize results before submitting.",
                            ],
                            "pt": [
                                "Confira os aliases das colunas no resultado esperado.",
                                "Use ORDER BY para estabilizar o resultado antes de enviar.",
                            ],
                        },
                        "sort_order": 2,
                        "is_active": True,
                    }
                ],
            },
            {
                "code": f"{module_code}-les2",
                "title_i18n": {
                    "en": f"{mod['title']} - Applied Analytics",
                    "pt": f"{mod['title']} - Analitica Aplicada",
                    "fr": f"{mod['title']} - Analytique Appliquee",
                    "es": f"{mod['title']} - Analitica Aplicada",
                    "it": f"{mod['title']} - Analitica Applicata",
                    "de": f"{mod['title']} - Angewandte Analytik",
                },
                "content_i18n": {
                    "en": _build_module_content(mod, index, "en"),
                    "pt": _build_module_content(mod, index, "pt"),
                    "fr": _build_module_content(mod, index, "fr"),
                    "es": _build_module_content(mod, index, "es"),
                    "it": _build_module_content(mod, index, "it"),
                    "de": _build_module_content(mod, index, "de"),
                },
                "sort_order": 2,
                "is_active": True,
                "exercises": [
                    {
                        "code": f"{module_code}-les2-ex1",
                        "title_i18n": {
                            "en": f"{mod['title']} - Applied Challenge",
                            "pt": f"{mod['title']} - Desafio Aplicado",
                            "fr": f"{mod['title']} - Defi Applique",
                            "es": f"{mod['title']} - Desafio Aplicado",
                            "it": f"{mod['title']} - Sfida Applicata",
                            "de": f"{mod['title']} - Praktische Herausforderung",
                        },
                        "description_i18n": {
                            "en": "Build a business-style query combining joins, grouping and ranking logic.",
                            "pt": "Monte uma query de negocio combinando joins, agrupamentos e logica de ranking.",
                            "fr": "Construisez une requete orientee business combinant jointures, agregations et classement.",
                            "es": "Construye una consulta de negocio combinando joins, agrupacion y ranking.",
                            "it": "Costruisci una query business combinando join, aggregazioni e ranking.",
                            "de": "Erstellen Sie eine Business-Abfrage mit Joins, Gruppierung und Ranking.",
                        },
                        "exercise_type": "sql_query",
                        "difficulty": "hard" if index >= 8 else "medium",
                        "points_reward": 30 + (index * 2),
                        "expected_sql": _applied_query(module_code, index),
                        "validation_mode": "result_match",
                        "hints_i18n": {
                            "en": [
                                "Use LEFT JOIN when you need complete coverage of dimensions.",
                                "Group only by business dimensions, aggregate the metrics.",
                            ],
                            "pt": [
                                "Use LEFT JOIN quando precisar cobertura completa das dimensoes.",
                                "Agrupe apenas dimensoes de negocio e agregue as metricas.",
                            ],
                        },
                        "sort_order": 1,
                        "is_active": True,
                    }
                ],
            },
        ]

        if module_code == "sql201":
            lesson1_concepts = ["INNER JOIN", "LEFT JOIN", "Primary keys and foreign keys", "Relationship modeling"]
            lesson1_practical = [
                "Join customers and orders",
                "Show customers without orders",
                "Validate join keys and cardinality",
            ]
            lesson2_concepts = ["COUNT", "SUM", "AVG", "GROUP BY", "HAVING"]
            lesson2_practical = [
                "Aggregate revenue by customer",
                "Filter grouped results with HAVING",
                "Compare grouped metrics across segments",
            ]
            lesson3_concepts = ["INNER JOIN", "GROUP BY", "HAVING", "Relationship modeling", "Analytical queries"]
            lesson3_practical = [
                "Build multi-table product revenue report",
                "Create customer-category matrix",
                "Validate grain and avoid duplicate counting",
            ]
            lessons = [
                {
                    "code": "sql201-les1",
                    "title_i18n": {
                        "en": "SQL 201 - INNER and LEFT JOIN",
                        "pt": "SQL 201 - INNER e LEFT JOIN",
                        "fr": "SQL 201 - INNER et LEFT JOIN",
                        "es": "SQL 201 - INNER y LEFT JOIN",
                        "it": "SQL 201 - INNER e LEFT JOIN",
                        "de": "SQL 201 - INNER und LEFT JOIN",
                    },
                    "content_i18n": {
                        "en": _build_lesson_content(mod, index, "en", "SQL 201 - INNER and LEFT JOIN", lesson1_concepts, lesson1_practical, "Join-focused customer order audit"),
                        "pt": _build_lesson_content(mod, index, "pt", "SQL 201 - INNER e LEFT JOIN", lesson1_concepts, lesson1_practical, "Auditoria de pedidos com foco em joins"),
                        "fr": _build_lesson_content(mod, index, "fr", "SQL 201 - INNER et LEFT JOIN", lesson1_concepts, lesson1_practical, "Audit des commandes axe sur les jointures"),
                        "es": _build_lesson_content(mod, index, "es", "SQL 201 - INNER y LEFT JOIN", lesson1_concepts, lesson1_practical, "Auditoria de pedidos centrada en joins"),
                        "it": _build_lesson_content(mod, index, "it", "SQL 201 - INNER e LEFT JOIN", lesson1_concepts, lesson1_practical, "Audit ordini con focus sui join"),
                        "de": _build_lesson_content(mod, index, "de", "SQL 201 - INNER und LEFT JOIN", lesson1_concepts, lesson1_practical, "Bestell-Audit mit Join-Fokus"),
                    },
                    "sort_order": 1,
                    "is_active": True,
                    "exercises": [
                        {
                            "code": "sql201-les1-ex1",
                            "title_i18n": {"en": "Join customers and orders", "pt": "Juntar clientes e pedidos", "fr": "Joindre clients et commandes", "es": "Unir clientes y pedidos", "it": "Unire clienti e ordini", "de": "Kunden und Bestellungen verbinden"},
                            "description_i18n": {"en": "Use INNER JOIN to list customer names with order amounts.", "pt": "Use INNER JOIN para listar clientes com valores de pedido.", "fr": "Utilisez INNER JOIN pour lister les clients et montants.", "es": "Usa INNER JOIN para listar clientes y montos.", "it": "Usa INNER JOIN per elencare clienti e importi.", "de": "Nutze INNER JOIN fuer Kundennamen und Bestellbetraege."},
                            "exercise_type": "sql_query",
                            "difficulty": "medium",
                            "points_reward": 35,
                            "expected_sql": "SELECT c.first_name, c.last_name, o.amount FROM customers c INNER JOIN orders o ON c.customer_id = o.customer_id",
                            "validation_mode": "result_match",
                            "hints_i18n": {"en": ["Use aliases c and o", "Join on customer_id"]},
                            "sort_order": 1,
                            "is_active": True,
                        },
                        {
                            "code": "sql201-les1-ex2",
                            "title_i18n": {"en": "Show customers without orders", "pt": "Mostrar clientes sem pedidos", "fr": "Afficher clients sans commandes", "es": "Mostrar clientes sin pedidos", "it": "Mostra clienti senza ordini", "de": "Kunden ohne Bestellungen anzeigen"},
                            "description_i18n": {"en": "Use LEFT JOIN and filter NULL orders.", "pt": "Use LEFT JOIN e filtre pedidos NULL.", "fr": "Utilisez LEFT JOIN et filtrez les commandes NULL.", "es": "Usa LEFT JOIN y filtra pedidos NULL.", "it": "Usa LEFT JOIN e filtra ordini NULL.", "de": "Nutze LEFT JOIN und filtere NULL-Bestellungen."},
                            "exercise_type": "sql_query",
                            "difficulty": "medium",
                            "points_reward": 35,
                            "expected_sql": "SELECT c.customer_id, c.first_name, c.last_name FROM customers c LEFT JOIN orders o ON c.customer_id = o.customer_id WHERE o.order_id IS NULL",
                            "validation_mode": "result_match",
                            "hints_i18n": {"en": ["LEFT JOIN keeps all customers", "Use WHERE o.order_id IS NULL"]},
                            "sort_order": 2,
                            "is_active": True,
                        },
                    ],
                },
                {
                    "code": "sql201-les2",
                    "title_i18n": {"en": "SQL 201 - GROUP BY and HAVING", "pt": "SQL 201 - GROUP BY e HAVING", "fr": "SQL 201 - GROUP BY et HAVING", "es": "SQL 201 - GROUP BY y HAVING", "it": "SQL 201 - GROUP BY e HAVING", "de": "SQL 201 - GROUP BY und HAVING"},
                    "content_i18n": {"en": _build_module_content(mod, index, "en"), "pt": _build_module_content(mod, index, "pt"), "fr": _build_module_content(mod, index, "fr"), "es": _build_module_content(mod, index, "es"), "it": _build_module_content(mod, index, "it"), "de": _build_module_content(mod, index, "de")},
                    "content_i18n": {
                        "en": _build_lesson_content(mod, index, "en", "SQL 201 - GROUP BY and HAVING", lesson2_concepts, lesson2_practical, "Grouped KPI performance report"),
                        "pt": _build_lesson_content(mod, index, "pt", "SQL 201 - GROUP BY e HAVING", lesson2_concepts, lesson2_practical, "Relatorio de KPI com agrupamentos"),
                        "fr": _build_lesson_content(mod, index, "fr", "SQL 201 - GROUP BY et HAVING", lesson2_concepts, lesson2_practical, "Rapport KPI avec regroupements"),
                        "es": _build_lesson_content(mod, index, "es", "SQL 201 - GROUP BY y HAVING", lesson2_concepts, lesson2_practical, "Informe KPI con agrupaciones"),
                        "it": _build_lesson_content(mod, index, "it", "SQL 201 - GROUP BY e HAVING", lesson2_concepts, lesson2_practical, "Report KPI con raggruppamenti"),
                        "de": _build_lesson_content(mod, index, "de", "SQL 201 - GROUP BY und HAVING", lesson2_concepts, lesson2_practical, "KPI-Bericht mit Gruppierungen"),
                    },
                    "sort_order": 2,
                    "is_active": True,
                    "exercises": [
                        {
                            "code": "sql201-les2-ex1",
                            "title_i18n": {"en": "Revenue by customer", "pt": "Receita por cliente", "fr": "Revenu par client", "es": "Ingresos por cliente", "it": "Ricavi per cliente", "de": "Umsatz nach Kunde"},
                            "description_i18n": {"en": "Aggregate total amount per customer.", "pt": "Agregue o valor total por cliente.", "fr": "Agregez le montant total par client.", "es": "Agrega el monto total por cliente.", "it": "Aggrega importo totale per cliente.", "de": "Aggregiere den Gesamtbetrag pro Kunde."},
                            "exercise_type": "sql_query",
                            "difficulty": "medium",
                            "points_reward": 40,
                            "expected_sql": "SELECT customer_id, SUM(amount) AS total_amount FROM orders GROUP BY customer_id ORDER BY total_amount DESC",
                            "validation_mode": "result_match",
                            "hints_i18n": {"en": ["Use SUM(amount)", "GROUP BY customer_id"]},
                            "sort_order": 1,
                            "is_active": True,
                        },
                        {
                            "code": "sql201-les2-ex2",
                            "title_i18n": {"en": "Keep only active customers", "pt": "Manter apenas clientes ativos", "fr": "Garder les clients actifs", "es": "Mantener clientes activos", "it": "Mantieni solo clienti attivi", "de": "Nur aktive Kunden behalten"},
                            "description_i18n": {"en": "Use HAVING to keep customers with at least 2 orders.", "pt": "Use HAVING para manter clientes com ao menos 2 pedidos.", "fr": "Utilisez HAVING pour garder les clients avec au moins 2 commandes.", "es": "Usa HAVING para mantener clientes con al menos 2 pedidos.", "it": "Usa HAVING per mantenere clienti con almeno 2 ordini.", "de": "Nutze HAVING fuer Kunden mit mindestens 2 Bestellungen."},
                            "exercise_type": "sql_query",
                            "difficulty": "medium",
                            "points_reward": 40,
                            "expected_sql": "SELECT customer_id, COUNT(*) AS order_count FROM orders GROUP BY customer_id HAVING COUNT(*) >= 2 ORDER BY order_count DESC",
                            "validation_mode": "result_match",
                            "hints_i18n": {"en": ["HAVING filters grouped rows", "Use COUNT(*) >= 2"]},
                            "sort_order": 2,
                            "is_active": True,
                        },
                    ],
                },
                {
                    "code": "sql201-les3",
                    "title_i18n": {"en": "SQL 201 - Multi-table analytics", "pt": "SQL 201 - Analise multitabla", "fr": "SQL 201 - Analyse multi-tables", "es": "SQL 201 - Analitica multi-tabla", "it": "SQL 201 - Analitica multi-tabella", "de": "SQL 201 - Mehrtabellen-Analyse"},
                    "content_i18n": {
                        "en": _build_lesson_content(mod, index, "en", "SQL 201 - Multi-table analytics", lesson3_concepts, lesson3_practical, "Cross-domain profitability analytics"),
                        "pt": _build_lesson_content(mod, index, "pt", "SQL 201 - Analise multitabla", lesson3_concepts, lesson3_practical, "Analitica de rentabilidade entre dominios"),
                        "fr": _build_lesson_content(mod, index, "fr", "SQL 201 - Analyse multi-tables", lesson3_concepts, lesson3_practical, "Analytique de rentabilite inter-domaines"),
                        "es": _build_lesson_content(mod, index, "es", "SQL 201 - Analitica multi-tabla", lesson3_concepts, lesson3_practical, "Analitica de rentabilidad entre dominios"),
                        "it": _build_lesson_content(mod, index, "it", "SQL 201 - Analitica multi-tabella", lesson3_concepts, lesson3_practical, "Analitica di redditivita cross-domain"),
                        "de": _build_lesson_content(mod, index, "de", "SQL 201 - Mehrtabellen-Analyse", lesson3_concepts, lesson3_practical, "Domänenuebergreifende Profitabilitaetsanalyse"),
                    },
                    "sort_order": 3,
                    "is_active": True,
                    "exercises": [
                        {
                            "code": "sql201-les3-ex1",
                            "title_i18n": {"en": "Top product revenue", "pt": "Top receita por produto", "fr": "Top revenu par produit", "es": "Top ingresos por producto", "it": "Top ricavi per prodotto", "de": "Top Umsatz pro Produkt"},
                            "description_i18n": {"en": "Join order_items and products, then aggregate sales.", "pt": "Junte order_items e products e agregue vendas.", "fr": "Joignez order_items et products puis agregez les ventes.", "es": "Une order_items y products y agrega ventas.", "it": "Unisci order_items e products e aggrega vendite.", "de": "Verbinde order_items und products und aggregiere Umsaetze."},
                            "exercise_type": "sql_query",
                            "difficulty": "hard",
                            "points_reward": 45,
                            "expected_sql": "SELECT p.product_name, SUM(oi.quantity * oi.unit_price) AS revenue FROM order_items oi INNER JOIN products p ON p.product_id = oi.product_id GROUP BY p.product_name ORDER BY revenue DESC",
                            "validation_mode": "result_match",
                            "hints_i18n": {"en": ["Use quantity * unit_price", "Group by product_name"]},
                            "sort_order": 1,
                            "is_active": True,
                        },
                        {
                            "code": "sql201-les3-ex2",
                            "title_i18n": {"en": "Customer-category matrix", "pt": "Matriz cliente-categoria", "fr": "Matrice client-categorie", "es": "Matriz cliente-categoria", "it": "Matrice cliente-categoria", "de": "Kunden-Kategorie-Matrix"},
                            "description_i18n": {"en": "Build a report crossing customer with product categories purchased.", "pt": "Construa um relatorio cruzando cliente e categorias compradas.", "fr": "Construisez un rapport croisant client et categories achetees.", "es": "Construye un reporte cruzando cliente y categorias compradas.", "it": "Crea un report incrociando cliente e categorie acquistate.", "de": "Erstelle einen Bericht ueber Kunden und gekaufte Kategorien."},
                            "exercise_type": "sql_query",
                            "difficulty": "hard",
                            "points_reward": 45,
                            "expected_sql": "SELECT c.customer_id, c.first_name, p.category, COUNT(*) AS lines FROM customers c INNER JOIN orders o ON o.customer_id = c.customer_id INNER JOIN order_items oi ON oi.order_id = o.order_id INNER JOIN products p ON p.product_id = oi.product_id GROUP BY c.customer_id, c.first_name, p.category ORDER BY c.customer_id, lines DESC",
                            "validation_mode": "result_match",
                            "hints_i18n": {"en": ["Join 4 tables", "Group by customer and category"]},
                            "sort_order": 2,
                            "is_active": True,
                        },
                    ],
                },
            ]

        total_exercises = sum(len(lesson.get("exercises", [])) for lesson in lessons)
        modules.append(
            {
                "code": module_code,
                "title_i18n": module_title_i18n,
                "description_i18n": module_description_i18n,
                "level": mod["level"],
                "total_lessons": len(lessons),
                "total_exercises": total_exercises,
                "pass_threshold": 70,
                "points_reward": 150 + (index * 25),
                "estimated_minutes": mod["minutes"],
                "sort_order": index,
                "is_active": True,
                "is_free": index <= 2,
                "schema_sql": schema_sql,
                "seed_sql": seed_sql,
                "lessons": lessons,
            }
        )

    return modules


MODULES = _build_modules()


def _seed_achievements(force: bool = False) -> int:
    from ..models.e_learning import Achievement

    count = 0
    for ach_data in ACHIEVEMENTS:
        existing = Achievement.query.filter_by(code=ach_data["code"]).first()
        if existing:
            if force:
                for k, v in ach_data.items():
                    setattr(existing, k, v)
            continue

        ach = Achievement(
            code=ach_data["code"],
            name_i18n=ach_data["name_i18n"],
            description_i18n=ach_data["description_i18n"],
            icon_url=f"/static/assets/badges/{ach_data['icon']}.svg",
            rarity=ach_data["rarity"],
            points_reward=ach_data["points_reward"],
        )
        db.session.add(ach)
        count += 1

    db.session.commit()
    return count


def _seed_sql_subject(force: bool = False) -> dict:
    from ..models.e_learning import (
        ELearningSubject,
        ELearningModule,
        ELearningLesson,
        ELearningExercise,
    )

    stats = {"subjects": 0, "modules": 0, "lessons": 0, "exercises": 0}

    # Subject
    subject = ELearningSubject.query.filter_by(code=SQL_SUBJECT["code"]).first()
    if not subject:
        subject = ELearningSubject(
            code=SQL_SUBJECT["code"],
            name_i18n=SQL_SUBJECT["name_i18n"],
            description_i18n=SQL_SUBJECT["description_i18n"],
            icon_url=f"/static/assets/icons/{SQL_SUBJECT['icon']}.svg",
            is_active=SQL_SUBJECT["is_active"],
            order=SQL_SUBJECT["sort_order"],
        )
        db.session.add(subject)
        db.session.flush()
        stats["subjects"] += 1
    elif force:
        subject.name_i18n = SQL_SUBJECT["name_i18n"]
        subject.description_i18n = SQL_SUBJECT["description_i18n"]
        db.session.flush()

    if force:
        valid_codes = {mod_data["code"] for mod_data in MODULES}
        stale_modules = ELearningModule.query.filter(
            ELearningModule.subject_id == subject.id,
            ELearningModule.code.notin_(valid_codes),
        ).all()
        for stale_module in stale_modules:
            db.session.delete(stale_module)
        if stale_modules:
            db.session.flush()

    # Modules
    for mod_data in MODULES:
        module = ELearningModule.query.filter_by(code=mod_data["code"]).first()
        if module and not force:
            continue

        if not module:
            module = ELearningModule(
                subject_id=subject.id,
                code=mod_data["code"],
            )
            db.session.add(module)

        module.title_i18n = mod_data["title_i18n"]
        module.description_i18n = mod_data["description_i18n"]
        module.level = mod_data["level"]
        module.total_lessons = mod_data["total_lessons"]
        module.total_exercises = mod_data["total_exercises"]
        module.pass_threshold = mod_data["pass_threshold"]
        module.points_on_completion = mod_data["points_reward"]
        module.estimated_hours = round(mod_data["estimated_minutes"] / 60, 2)
        module.order = mod_data["sort_order"]
        module.is_active = mod_data["is_active"]
        module.sample_database_schema = mod_data.get("schema_sql")
        module.sample_data_sql = mod_data.get("seed_sql")
        db.session.flush()
        stats["modules"] += 1

        if force:
            valid_lesson_codes = {les_data["code"] for les_data in mod_data.get("lessons", [])}
            stale_lessons = ELearningLesson.query.filter(
                ELearningLesson.module_id == module.id,
                ELearningLesson.code.notin_(valid_lesson_codes),
            ).all()
            for stale_lesson in stale_lessons:
                db.session.delete(stale_lesson)
            if stale_lessons:
                db.session.flush()

        # Lessons
        for les_data in mod_data.get("lessons", []):
            lesson = ELearningLesson.query.filter_by(code=les_data["code"]).first()
            if lesson and not force:
                continue

            if not lesson:
                lesson = ELearningLesson(module_id=module.id, code=les_data["code"])
                db.session.add(lesson)

            lesson.title_i18n = les_data["title_i18n"]
            lesson.content_html_i18n = les_data["content_i18n"]
            lesson.order = les_data["sort_order"]
            lesson.is_active = les_data["is_active"]
            db.session.flush()
            stats["lessons"] += 1

            if force:
                valid_exercise_codes = {ex_data["code"] for ex_data in les_data.get("exercises", [])}
                stale_exercises = ELearningExercise.query.filter(
                    ELearningExercise.lesson_id == lesson.id,
                    ELearningExercise.code.notin_(valid_exercise_codes),
                ).all()
                for stale_exercise in stale_exercises:
                    db.session.delete(stale_exercise)
                if stale_exercises:
                    db.session.flush()

            # Exercises
            for ex_data in les_data.get("exercises", []):
                exercise = ELearningExercise.query.filter_by(code=ex_data["code"]).first()
                if exercise and not force:
                    continue

                if not exercise:
                    exercise = ELearningExercise(lesson_id=lesson.id, code=ex_data["code"])
                    db.session.add(exercise)

                exercise.title_i18n = ex_data["title_i18n"]
                exercise.instruction_i18n = ex_data["description_i18n"]
                exercise_type = ex_data.get("exercise_type", "sql_query")
                if exercise_type in {"select", "query", "sql_select"}:
                    exercise_type = "sql_query"
                elif exercise_type in {"dml", "sql_write"}:
                    exercise_type = "sql_dml"
                exercise.type = exercise_type
                exercise.points = ex_data["points_reward"]
                exercise.expected_sql = ex_data["expected_sql"]
                exercise.hint_i18n = ex_data.get("hints_i18n", {})
                exercise.order = ex_data["sort_order"]
                exercise.is_active = ex_data["is_active"]
                db.session.flush()
                stats["exercises"] += 1

    db.session.commit()
    return stats


def init_e_learning_seed_cli(app: Flask) -> None:
    """Register e-learning seed CLI commands."""

    @app.cli.command("seed-e-learning")
    @click.option("--force", is_flag=True, default=False, help="Re-seed existing records")
    def seed_e_learning(force: bool):
        """Seed e-learning content: SQL subject, modules, lessons, exercises, and achievements."""
        click.echo("🎓 Seeding E-Learning content...")

        ach_count = _seed_achievements(force=force)
        click.echo(f"  ✅ Achievements: {ach_count} created")

        stats = _seed_sql_subject(force=force)
        click.echo(f"  ✅ Subjects: {stats['subjects']} created")
        click.echo(f"  ✅ Modules: {stats['modules']} created")
        click.echo(f"  ✅ Lessons: {stats['lessons']} created")
        click.echo(f"  ✅ Exercises: {stats['exercises']} created")

        click.echo("\n🚀 Done! Visit /e-learning/ to browse the content.")
