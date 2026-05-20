"""E-Learning Content Seeder

Populates the database with sample SQL training content for the e-learning platform.

Run with:
    flask seed-e-learning           # seed SQL 101 module + achievements
    flask seed-e-learning --force   # drop and re-seed
"""

import click
import sqlite3
from pathlib import Path
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
        "en": "A 12-module SQL journey built for the SQLite sandbox used in AUDELA. Master SELECT, joins, aggregations, DML, recursive CTEs, window functions and data-quality auditing with compatible hands-on labs.",
        "pt": "Uma jornada SQL em 12 modulos desenhada para o sandbox SQLite do AUDELA. Domine SELECT, joins, agregacoes, DML, CTEs recursivas, funcoes de janela e auditoria de dados com laboratorios compativeis.",
        "fr": "Un parcours SQL en 12 modules concu pour le sandbox SQLite d'AUDELA. Maitrisez SELECT, jointures, agregations, DML, CTE recursives, fonctions fenetre et audit de qualite de donnees avec des labs compatibles.",
        "es": "Un recorrido SQL de 12 modulos disenado para el sandbox SQLite de AUDELA. Domina SELECT, joins, agregaciones, DML, CTE recursivas, funciones de ventana y auditoria de calidad de datos con laboratorios compatibles.",
        "it": "Un percorso SQL in 12 moduli progettato per il sandbox SQLite di AUDELA. Padroneggia SELECT, join, aggregazioni, DML, CTE ricorsive, funzioni finestra e audit di qualita dati con laboratori compatibili.",
        "de": "Ein 12-Module-SQL-Kurs fuer die SQLite-Sandbox von AUDELA. Beherrschen Sie SELECT, Joins, Aggregationen, DML, rekursive CTEs, Window-Funktionen und Datenqualitaets-Audits mit kompatiblen Praxislabs.",
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


_EXERCISE_BRIEF_I18N = {
    "en": {
        "intro": "Professional brief: this exercise is designed to check whether you can turn a business requirement into a correct and readable SQL result.",
        "process": "Approach it methodically: inspect the schema, identify the relevant tables and keys, write the query in small steps, and keep aliases explicit.",
        "validate": "Before submitting, verify the output columns, row count, filters, and ordering so the result is deterministic and easy to review.",
        "deliverable": "Deliverable: a single SQL statement that produces the requested output without extra columns or ambiguous ordering.",
        "playbook_title": "How to approach the exercises",
        "playbook_desc": "Work like a consultant: understand the objective, map the data model, draft the query incrementally, and validate the output before you send it.",
        "playbook_1": "Read the objective and restate the expected business answer in your own words.",
        "playbook_2": "Inspect the tables and columns first, then build the query step by step.",
        "playbook_3": "Run the query, compare it with the expected shape, and only then submit.",
    },
    "pt": {
        "intro": "Resumo profissional: este exercicio foi desenhado para verificar se voce consegue transformar um requisito de negocio em um resultado SQL correto e legivel.",
        "process": "Siga de forma metódica: examine o esquema, identifique tabelas e chaves relevantes, escreva a consulta em pequenos passos e use aliases claros.",
        "validate": "Antes de enviar, confirme colunas de saida, quantidade de linhas, filtros e ordenacao para que o resultado seja deterministico e facil de revisar.",
        "deliverable": "Entregavel: uma unica instrução SQL que produza o resultado solicitado sem colunas extras ou ordenacao ambigua.",
        "playbook_title": "Como abordar os exercicios",
        "playbook_desc": "Trabalhe como um consultor: entenda o objetivo, mapeie o modelo de dados, rascunhe a query de forma incremental e valide a saida antes do envio.",
        "playbook_1": "Leia o objetivo e reformule a resposta de negocio esperada com suas palavras.",
        "playbook_2": "Inspecione primeiro tabelas e colunas, depois construa a consulta passo a passo.",
        "playbook_3": "Execute a consulta, compare com o formato esperado e so entao envie.",
    },
    "fr": {
        "intro": "Note professionnelle : cet exercice verifie votre capacite a transformer une demande metier en resultat SQL correct et lisible.",
        "process": "Procédez methodiquement : examinez le schema, identifiez les tables et cles utiles, construisez la requete par petites etapes et utilisez des alias explicites.",
        "validate": "Avant de soumettre, verifiez les colonnes, le nombre de lignes, les filtres et le tri afin d'obtenir un resultat deterministe et simple a relire.",
        "deliverable": "Livrable : une seule requete SQL qui produit le resultat demande, sans colonnes superflues ni tri ambigu.",
        "playbook_title": "Comment aborder les exercices",
        "playbook_desc": "Travaillez comme un consultant : comprenez l'objectif, cartographiez le modele de donnees, redigez la requete progressivement et validez le resultat avant l'envoi.",
        "playbook_1": "Lisez l'objectif et reformulez la reponse metier attendue avec vos propres mots.",
        "playbook_2": "Inspectez d'abord les tables et les colonnes, puis construisez la requete etape par etape.",
        "playbook_3": "Executez la requete, comparez-la au format attendu, puis soumettez seulement apres verification.",
    },
    "es": {
        "intro": "Resumen profesional: este ejercicio evalua si puedes convertir un requisito de negocio en un resultado SQL correcto y legible.",
        "process": "Afrontalo de forma metódica: revisa el esquema, identifica tablas y claves relevantes, escribe la consulta por pasos y usa alias claros.",
        "validate": "Antes de enviar, comprueba columnas de salida, numero de filas, filtros y orden para que el resultado sea determinista y facil de revisar.",
        "deliverable": "Entregable: una sola instruccion SQL que produzca el resultado solicitado sin columnas extra ni orden ambigua.",
        "playbook_title": "Como abordar los ejercicios",
        "playbook_desc": "Trabaja como un consultor: entiende el objetivo, mapea el modelo de datos, redacta la consulta de forma incremental y valida la salida antes de enviar.",
        "playbook_1": "Lee el objetivo y reformula con tus palabras la respuesta de negocio esperada.",
        "playbook_2": "Revisa primero tablas y columnas, luego construye la consulta paso a paso.",
        "playbook_3": "Ejecuta la consulta, compara el resultado con el formato esperado y solo entonces envia.",
    },
    "it": {
        "intro": "Sintesi professionale: questo esercizio verifica la tua capacita di trasformare un requisito di business in un risultato SQL corretto e leggibile.",
        "process": "Affrontalo in modo metodico: esamina lo schema, individua tabelle e chiavi rilevanti, scrivi la query per piccoli passi e usa alias espliciti.",
        "validate": "Prima dell'invio verifica colonne di output, numero di righe, filtri e ordinamento per ottenere un risultato deterministico e facile da revisionare.",
        "deliverable": "Consegna: una singola istruzione SQL che produca il risultato richiesto senza colonne extra o ordinamento ambiguo.",
        "playbook_title": "Come affrontare gli esercizi",
        "playbook_desc": "Lavora come un consulente: comprendi l'obiettivo, mappa il modello dati, prepara la query in modo incrementale e valida l'output prima dell'invio.",
        "playbook_1": "Leggi l'obiettivo e riformula con parole tue la risposta di business attesa.",
        "playbook_2": "Ispeziona prima tabelle e colonne, poi costruisci la query passo dopo passo.",
        "playbook_3": "Esegui la query, confrontala con il formato atteso e inviala solo dopo la verifica.",
    },
    "de": {
        "intro": "Professioneller Hinweis: Diese Aufgabe prueft, ob Sie eine fachliche Anforderung in ein korrektes und gut lesbares SQL-Ergebnis uebersetzen koennen.",
        "process": "Gehen Sie methodisch vor: pruefen Sie das Schema, identifizieren Sie die relevanten Tabellen und Schluessel, bauen Sie die Abfrage schrittweise auf und verwenden Sie klare Aliase.",
        "validate": "Pruefen Sie vor dem Absenden die Ausgabespalten, Zeilenanzahl, Filter und Sortierung, damit das Ergebnis deterministisch und leicht pruefbar ist.",
        "deliverable": "Lieferobjekt: eine einzelne SQL-Anweisung, die das geforderte Ergebnis ohne Zusatzspalten oder uneindeutige Sortierung liefert.",
        "playbook_title": "So gehen Sie die Uebungen an",
        "playbook_desc": "Arbeiten Sie wie ein Berater: Verstehen Sie das Ziel, kartieren Sie das Datenmodell, entwerfen Sie die Abfrage inkrementell und validieren Sie die Ausgabe vor dem Absenden.",
        "playbook_1": "Lesen Sie das Ziel und formulieren Sie die erwartete fachliche Antwort mit eigenen Worten.",
        "playbook_2": "Pruefen Sie zuerst Tabellen und Spalten und bauen Sie dann die Abfrage Schritt fuer Schritt auf.",
        "playbook_3": "Fuehren Sie die Abfrage aus, vergleichen Sie das Ergebnis mit der erwarteten Form und senden Sie erst dann ab.",
    },
}


def _professionalize_exercise_description(description_i18n: dict[str, str]) -> dict[str, str]:
    enriched: dict[str, str] = {}
    for lang in ("en", "pt", "fr", "es", "it", "de"):
        base = description_i18n.get(lang) or description_i18n.get("en") or ""
        brief = _EXERCISE_BRIEF_I18N.get(lang, _EXERCISE_BRIEF_I18N["en"])
        enriched[lang] = "\n".join([
            brief["intro"],
            base,
            brief["process"],
            brief["validate"],
            brief["deliverable"],
        ])
    return enriched


_EXERCISE_HINTS_I18N = {
    "en": [
        "Start by identifying the output grain and the driving table.",
        "Write the query in stages: filter, join, group, and sort.",
        "Check NULL handling and ordering before submitting.",
    ],
    "pt": [
        "Comece identificando o grão de saida e a tabela principal.",
        "Escreva a query em etapas: filtrar, juntar, agrupar e ordenar.",
        "Verifique tratamento de NULL e ordenacao antes de enviar.",
    ],
    "fr": [
        "Commencez par definir le niveau de detail et la table principale.",
        "Construisez la requete par etapes : filtre, jointure, aggregation, tri.",
        "Verifiez la gestion des NULL et du tri avant l'envoi.",
    ],
    "es": [
        "Empieza identificando el nivel de detalle y la tabla principal.",
        "Construye la consulta por etapas: filtro, join, agrupacion y orden.",
        "Comprueba el manejo de NULL y el orden antes de enviar.",
    ],
    "it": [
        "Inizia identificando il livello di dettaglio e la tabella guida.",
        "Costruisci la query per fasi: filtro, join, aggregazione e ordinamento.",
        "Controlla la gestione dei NULL e l'ordinamento prima dell'invio.",
    ],
    "de": [
        "Beginnen Sie mit dem Ausgabegra und der Fuehrungstabelle.",
        "Bauen Sie die Abfrage schrittweise auf: filtern, joinen, gruppieren, sortieren.",
        "Pruefen Sie NULL-Behandlung und Sortierung vor dem Absenden.",
    ],
}


def _professionalize_exercise_hints(hints_i18n: dict[str, list[str]]) -> dict[str, list[str]]:
    enriched: dict[str, list[str]] = {}
    for lang in ("en", "pt", "fr", "es", "it", "de"):
        existing = list(hints_i18n.get(lang) or hints_i18n.get("en") or [])
        extra = _EXERCISE_HINTS_I18N.get(lang, _EXERCISE_HINTS_I18N["en"])
        combined: list[str] = []
        for hint in existing + extra:
            if hint and hint not in combined:
                combined.append(hint)
        enriched[lang] = combined
    return enriched


def _exercise_playbook_html(lang: str) -> str:
    brief = _EXERCISE_BRIEF_I18N.get(lang, _EXERCISE_BRIEF_I18N["en"])
    return f"""
<h5>{brief['playbook_title']}</h5>
<p class="text-muted">{brief['playbook_desc']}</p>
<ol>
  <li>{brief['playbook_1']}</li>
  <li>{brief['playbook_2']}</li>
  <li>{brief['playbook_3']}</li>
</ol>
"""


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
        "title": "Module 7 - Safe Data Modification",
        "level": "intermediate",
        "minutes": 80,
        "concepts": ["INSERT", "UPDATE", "DELETE", "Idempotent updates", "Transactions", "COMMIT / ROLLBACK"],
        "practical": ["Insert a new customer safely", "Update one target row with explicit WHERE", "Delete a specific row and verify outcome"],
        "mini_project": "Operational data cleanup playbook",
        "image_url": "https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?auto=format&fit=crop&w=1200&q=80",
        "examples": [
            {
                "title": "Example: idempotent INSERT",
                "sql": "INSERT INTO customers (customer_id, first_name, last_name, email, country, created_at)\nSELECT 8, 'Nora', 'Costa', 'nora.costa@example.com', 'Portugal', '2024-03-22'\nWHERE NOT EXISTS (SELECT 1 FROM customers WHERE customer_id = 8);",
                "explanation": "This pattern remains safe if the learner reruns the same statement multiple times.",
            },
            {
                "title": "Example: deterministic UPDATE",
                "sql": "UPDATE products\nSET stock = 95\nWHERE product_id = 6;",
                "explanation": "Set a fixed value to avoid cumulative mutations across repeated attempts.",
            },
        ],
        "exercise_sql": "INSERT INTO customers (customer_id, first_name, last_name, email, country, created_at) SELECT 8, 'Nora', 'Costa', 'nora.costa@example.com', 'Portugal', '2024-03-22' WHERE NOT EXISTS (SELECT 1 FROM customers WHERE customer_id = 8)",
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
        "title": "Module 10 - Recursive Queries & Hierarchies",
        "level": "advanced",
        "minutes": 100,
        "concepts": ["Recursive CTE", "Hierarchy traversal", "Self joins", "Levels and paths", "Termination conditions"],
        "practical": ["Traverse a manager hierarchy", "Report hierarchy levels", "Compute total team sizes"],
        "mini_project": "Organisation chart explorer",
        "image_url": "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?auto=format&fit=crop&w=1200&q=80",
        "examples": [
            {
                "title": "Example: hierarchy traversal with WITH RECURSIVE",
                "sql": "WITH RECURSIVE org_chart AS (\n    SELECT emp_id, first_name || ' ' || last_name AS full_name, manager_id, 0 AS level\n    FROM employees\n    WHERE manager_id IS NULL\n    UNION ALL\n    SELECT e.emp_id, e.first_name || ' ' || e.last_name, e.manager_id, org_chart.level + 1\n    FROM employees e\n    JOIN org_chart ON e.manager_id = org_chart.emp_id\n)\nSELECT full_name, level\nFROM org_chart\nORDER BY level, full_name;",
                "explanation": "SQLite supports recursive CTEs, so this module stays executable in the AUDELA sandbox.",
            }
        ],
        "exercise_sql": "WITH RECURSIVE org_chart AS (SELECT emp_id, first_name || ' ' || last_name AS full_name, manager_id, 0 AS level FROM employees WHERE manager_id IS NULL UNION ALL SELECT e.emp_id, e.first_name || ' ' || e.last_name, e.manager_id, org_chart.level + 1 FROM employees e JOIN org_chart ON e.manager_id = org_chart.emp_id) SELECT full_name, level FROM org_chart ORDER BY level, full_name",
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
        "exercise_sql": "SELECT dept_id, first_name, salary, ROW_NUMBER() OVER (PARTITION BY dept_id ORDER BY salary DESC) AS dept_rank FROM employees ORDER BY dept_id, dept_rank",
    },
    {
        "code": "sql112",
        "title": "Module 12 - Views & Data Quality Audits",
        "level": "advanced",
        "minutes": 85,
        "concepts": ["Views", "Reusable reporting", "Audit queries", "Data quality checks", "Anomaly detection"],
        "practical": ["Create a reusable reporting view", "Inspect tables/views via sqlite_master", "Detect orphan business records"],
        "mini_project": "Operational reporting and quality audit pack",
        "image_url": "https://images.unsplash.com/photo-1563986768609-322da13575f3?auto=format&fit=crop&w=1200&q=80",
        "examples": [
            {
                "title": "Example: reusable view",
                "sql": "CREATE VIEW IF NOT EXISTS customer_order_totals AS\nSELECT c.customer_id, c.first_name, ROUND(COALESCE(SUM(o.amount), 0), 2) AS total_amount\nFROM customers c\nLEFT JOIN orders o ON o.customer_id = c.customer_id\nGROUP BY c.customer_id, c.first_name;",
                "explanation": "A view centralizes reporting logic and avoids copy-paste SQL across dashboards.",
            }
        ],
        "exercise_sql": "SELECT type, name FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' ORDER BY type, name",
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


def _build_examples_section(mod: dict, module_code: str, index: int) -> str:
    examples = mod.get("examples") or []
    if not examples:
        examples = [
            {
                "title": "Worked Example",
                "sql": mod.get("exercise_sql", ""),
                "explanation": "Run this query, inspect the output, then adapt it to the exercise objective.",
            },
            {
                "title": "Alternative Example",
                "sql": _secondary_query(module_code, index),
                "explanation": "Use this second query to compare filter logic and output ordering.",
            },
        ]

    cards = []
    for example in examples[:2]:
        cards.append(
            "<div class=\"border rounded-3 p-3 mb-3 bg-light\">"
            f"<div class=\"fw-semibold mb-2\">{example.get('title', 'Worked Example')}</div>"
            f"<pre class=\"mb-2\"><code>{example.get('sql', '')}</code></pre>"
            f"<p class=\"mb-0 text-muted\">{example.get('explanation', '')}</p>"
            "</div>"
        )
    return "<h5>Worked Examples</h5>" + "".join(cards)


def _materialize_expected_result(schema_sql: str, seed_sql: str, expected_sql: str, validation_query: str | None = None) -> list[dict] | None:
    if not expected_sql:
        return None

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        if schema_sql:
            conn.executescript(schema_sql)
        if seed_sql:
            conn.executescript(seed_sql)

        cursor = conn.cursor()
        cursor.execute(expected_sql)

        if cursor.description:
            return [dict(row) for row in cursor.fetchall()]

        conn.commit()
        if validation_query:
            cursor.execute(validation_query)
            if cursor.description:
                return [dict(row) for row in cursor.fetchall()]
            return []
        return None
    finally:
        conn.close()


def _seed_local_sqlite_file(db_path: str, force: bool = False) -> dict:
    """Create a local SQLite/DBLite file with seeded SQL training data."""
    output_path = Path(db_path).expanduser()
    if not output_path.is_absolute():
        output_path = Path.cwd() / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists() and not force:
        raise click.ClickException(
            f"File already exists: {output_path}. Use --force to recreate it."
        )

    if output_path.exists() and force:
        output_path.unlink()

    conn = sqlite3.connect(str(output_path))
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.executescript(SAMPLE_SCHEMA_SQL101)
        conn.executescript(SAMPLE_SCHEMA_EMPLOYEES)
        conn.executescript(SAMPLE_DATA_SQL101)
        conn.executescript(SAMPLE_DATA_EMPLOYEES)

        # Handy view used by advanced module exercises and BI smoke checks.
        conn.executescript(
            """
            CREATE VIEW IF NOT EXISTS customer_order_totals AS
            SELECT
                c.customer_id,
                c.first_name,
                c.last_name,
                COUNT(o.order_id) AS total_orders,
                COALESCE(SUM(o.amount), 0) AS total_amount
            FROM customers c
            LEFT JOIN orders o ON o.customer_id = c.customer_id
            GROUP BY c.customer_id, c.first_name, c.last_name;
            """
        )
        conn.commit()

        counts = {}
        for table_name in ["customers", "orders", "products", "order_items", "departments", "employees"]:
            row = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
            counts[table_name] = int(row[0]) if row else 0
    finally:
        conn.close()

    return {
        "path": str(output_path),
        "counts": counts,
    }


def _build_module_content(mod: dict, module_number: int, lang: str = "en") -> str:
    concept_items = "".join([f"<li><code>{_localize_phrase(c, lang)}</code></li>" for c in mod["concepts"]])
    concept_dive = _build_concept_deep_dive(mod, lang)
    references_html = _build_reference_section(mod, lang)
    module_code = COURSE_CODE_MAP.get(module_number) or mod.get("code") or "sql101"
    examples_html = _build_examples_section(mod, module_code, module_number)
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
        {examples_html}
        {_WARN_BOX('!!', _t_content('warn', lang))}
        <h5>{_t_content('common_pitfalls', lang)}</h5>
        <ul>{pitfalls_html}</ul>
        <h5>{_t_content('practical_exercises', lang)}</h5>
    <table class="table table-sm table-striped">
            <thead><tr><th>#</th><th>{_t_content('task', lang)}</th></tr></thead>
      <tbody>{practical_rows}</tbody>
    </table>
        {_exercise_playbook_html(lang)}
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
        module_code = COURSE_CODE_MAP.get(index) or mod["code"]
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

        # Module 12 relies on customer/order data and sqlite_master/view auditing.
        if module_code == "sql304":
            schema_sql = SAMPLE_SCHEMA_SQL101
            seed_sql = SAMPLE_DATA_SQL101

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

        # Ensure module 7 labs are true DML operations with explicit validation.
        if module_code == "sql203":
            lessons[0]["exercises"][0].update(
                {
                    "exercise_type": "sql_dml",
                    "expected_sql": "INSERT INTO customers (customer_id, first_name, last_name, email, country, created_at) SELECT 8, 'Nora', 'Costa', 'nora.costa@example.com', 'Portugal', '2024-03-22' WHERE NOT EXISTS (SELECT 1 FROM customers WHERE customer_id = 8)",
                    "validation_query": "SELECT customer_id, first_name, country FROM customers WHERE customer_id = 8",
                    "dml_operation": "INSERT",
                }
            )
            lessons[0]["exercises"][1].update(
                {
                    "exercise_type": "sql_dml",
                    "expected_sql": "UPDATE products SET stock = 95 WHERE product_id = 6",
                    "validation_query": "SELECT product_id, stock FROM products WHERE product_id = 6",
                    "dml_operation": "UPDATE",
                }
            )
            lessons[1]["exercises"][0].update(
                {
                    "exercise_type": "sql_dml",
                    "expected_sql": "DELETE FROM order_items WHERE order_item_id = 15",
                    "validation_query": "SELECT COUNT(*) AS remaining_rows FROM order_items WHERE order_item_id = 15",
                    "dml_operation": "DELETE",
                }
            )

        # Module 10 secondary lab aligned with recursion hierarchy output.
        if module_code == "sql302":
            lessons[0]["exercises"][1]["expected_sql"] = (
                "WITH RECURSIVE team_tree(root_manager, emp_id) AS ("
                "SELECT emp_id, emp_id FROM employees "
                "UNION ALL "
                "SELECT team_tree.root_manager, e.emp_id "
                "FROM employees e JOIN team_tree ON e.manager_id = team_tree.emp_id"
                ") SELECT root_manager, COUNT(*) - 1 AS team_size "
                "FROM team_tree GROUP BY root_manager HAVING COUNT(*) > 1 ORDER BY team_size DESC, root_manager"
            )

        # Module 12 applied lab aligned with data quality auditing.
        if module_code == "sql304":
            lessons[0]["exercises"][0].update(
                {
                    "exercise_type": "sql_dml",
                    "expected_sql": (
                        "CREATE VIEW IF NOT EXISTS customer_order_totals AS "
                        "SELECT c.customer_id, c.first_name, ROUND(COALESCE(SUM(o.amount), 0), 2) AS total_amount "
                        "FROM customers c LEFT JOIN orders o ON o.customer_id = c.customer_id "
                        "GROUP BY c.customer_id, c.first_name"
                    ),
                    "validation_query": "SELECT name, type FROM sqlite_master WHERE type = 'view' AND name = 'customer_order_totals'",
                    "dml_operation": "CREATE_VIEW",
                }
            )
            lessons[0]["exercises"][1]["expected_sql"] = (
                "SELECT type, name FROM sqlite_master "
                "WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' "
                "ORDER BY type, name"
            )
            lessons[1]["exercises"][0]["expected_sql"] = (
                "SELECT o.order_id FROM orders o "
                "LEFT JOIN order_items oi ON oi.order_id = o.order_id "
                "WHERE oi.order_id IS NULL ORDER BY o.order_id"
            )

        for lesson in lessons:
            for exercise in lesson.get("exercises", []):
                exercise["description_i18n"] = _professionalize_exercise_description(exercise.get("description_i18n", {}))
                exercise["hints_i18n"] = _professionalize_exercise_hints(exercise.get("hints_i18n", {}))
                exercise["expected_result_json"] = _materialize_expected_result(
                    schema_sql,
                    seed_sql,
                    exercise.get("expected_sql", ""),
                    exercise.get("validation_query"),
                )

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
            # Keep seed idempotent: refresh achievement metadata on every run.
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
        module = ELearningModule.query.filter_by(subject_id=subject.id, code=mod_data["code"]).first()

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
            lesson = ELearningLesson.query.filter_by(module_id=module.id, code=les_data["code"]).first()

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
                exercise = ELearningExercise.query.filter_by(lesson_id=lesson.id, code=ex_data["code"]).first()

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
                exercise.expected_result_json = ex_data.get("expected_result_json")
                exercise.dml_operation = ex_data.get("dml_operation")
                exercise.validation_query = ex_data.get("validation_query")
                exercise.passing_condition = ex_data.get("passing_condition")
                exercise.hint_i18n = ex_data.get("hints_i18n", {})
                exercise.order = ex_data["sort_order"]
                exercise.is_active = ex_data["is_active"]
                db.session.flush()
                stats["exercises"] += 1

    db.session.commit()
    return stats


PREMIUM_SUBJECTS = [
    {
        "code": "programming_logic",
        "name": "Programming Logic Engineering",
        "fr_name": "Ingenierie de logique de programmation",
        "description": "Algorithmic thinking, flow control, decomposition, debugging, and production-ready problem solving.",
        "fr_description": "Pensee algorithmique, controle de flux, decomposition, debogage et resolution de problemes prete pour la production.",
        "icon": "logic",
        "order": 40,
        "modules": [
            {
                "code": "prog_logic_foundations",
                "title": "Logic Foundations and Algorithmic Thinking",
                "fr_title": "Fondamentaux de logique et pensee algorithmique",
                "level": "beginner",
                "hours": 12,
                "lessons": [
                    "Problem decomposition and goal framing",
                    "Control flow patterns and decision trees",
                    "Data structures for reasoning",
                    "Algorithm complexity and trade-offs",
                    "Debugging strategies and invariants",
                    "Reading and improving legacy logic",
                ],
            },
            {
                "code": "prog_logic_patterns",
                "title": "Practical Logic Patterns and Refactoring",
                "fr_title": "Patterns logiques pratiques et refactoring",
                "level": "intermediate",
                "hours": 14,
                "lessons": [
                    "State machines and workflow modeling",
                    "Validation pipelines and guard clauses",
                    "Error handling and fallback logic",
                    "Concurrency-safe logical decisions",
                    "Refactoring nested conditionals",
                    "Building reusable decision engines",
                ],
            },
            {
                "code": "prog_logic_system_design",
                "title": "Logic for System Design and Interviews",
                "fr_title": "Logique pour system design et entretiens",
                "level": "advanced",
                "hours": 16,
                "lessons": [
                    "Domain modeling and business rules",
                    "Idempotency and consistency decisions",
                    "Scoring engines and ranking logic",
                    "Backtracking and search strategies",
                    "Constraint solving for real-world cases",
                    "Interview drills and whiteboard tactics",
                ],
            },
        ],
    },
    {
        "code": "audela_math_finance",
        "name": "Audela Math for Finance",
        "fr_name": "Audela Math pour la finance",
        "description": "Interactive financial math with graphing, parameter sliders, and scenario labs inspired by GeoGebra-style exploration.",
        "fr_description": "Mathematiques financieres interactives avec tracage de courbes, sliders de parametres et labs scenario inspires d'une approche type GeoGebra.",
        "icon": "functions",
        "order": 45,
        "modules": [
            {
                "code": "math_finance_foundations",
                "title": "Financial Math Foundations and Interactive Curves",
                "fr_title": "Fondamentaux de maths financieres et courbes interactives",
                "level": "beginner",
                "hours": 12,
                "lessons": [
                    "Time value of money and discounting intuition",
                    "Simple vs compound interest with interactive sliders",
                    "Growth curves and interpolation for finance decisions",
                    "Log scales, volatility, and return normalization",
                    "Building graph-based intuition for risk and payoff",
                    "Reading and validating financial charts",
                ],
            },
            {
                "code": "math_finance_products",
                "title": "Loans, Bonds, and Portfolio Math Studio",
                "fr_title": "Studio math prets, obligations et portefeuille",
                "level": "intermediate",
                "hours": 15,
                "lessons": [
                    "Loan amortization surfaces and payment sensitivity",
                    "Bond pricing, duration, and convexity visuals",
                    "Annuities and cash-flow timeline simulation",
                    "Yield curves and scenario stress testing",
                    "Portfolio variance and correlation geometry",
                    "Optimization trade-offs under practical constraints",
                ],
            },
            {
                "code": "math_finance_risk_ifrs9",
                "title": "Risk Modeling, What-If, and IFRS9 Analytics",
                "fr_title": "Modelisation risque, what-if et analytique IFRS9",
                "level": "advanced",
                "hours": 18,
                "lessons": [
                    "PD/LGD/EAD parameter interaction maps",
                    "IFRS9 staging thresholds with dynamic boundaries",
                    "Monte Carlo basics for portfolio loss simulation",
                    "Stress scenarios with macro-factor sliders",
                    "Sensitivity analysis and tornado charts",
                    "Model governance, validation, and explainability",
                ],
            },
        ],
    },
    {
        "code": "aws_cloud",
        "name": "AWS Architect and Builder",
        "fr_name": "Architecte et Builder AWS",
        "description": "Design, deploy, secure, and optimize cloud-native workloads on AWS with production best practices.",
        "fr_description": "Concevoir, deployer, securiser et optimiser des workloads cloud-native sur AWS avec des pratiques production.",
        "icon": "aws",
        "order": 50,
        "modules": [
            {
                "code": "aws_core_services",
                "title": "AWS Core Services and IAM",
                "fr_title": "Services coeur AWS et IAM",
                "level": "beginner",
                "hours": 12,
                "lessons": [
                    "Global infrastructure and shared responsibility",
                    "IAM users, roles, and least privilege",
                    "Compute choices: EC2, Lambda, ECS",
                    "Storage patterns: S3, EBS, EFS",
                    "Networking essentials with VPC",
                    "Observability with CloudWatch",
                ],
            },
            {
                "code": "aws_architecture",
                "title": "Resilient AWS Architecture",
                "fr_title": "Architecture AWS resiliente",
                "level": "intermediate",
                "hours": 15,
                "lessons": [
                    "High availability and multi-AZ design",
                    "Auto scaling and load balancing",
                    "Data services: RDS, DynamoDB, ElastiCache",
                    "Messaging and event-driven systems",
                    "Disaster recovery and backup strategy",
                    "Cost optimization and FinOps basics",
                ],
            },
            {
                "code": "aws_security_ops",
                "title": "AWS Security, Governance, and Operations",
                "fr_title": "Securite, gouvernance et operations AWS",
                "level": "advanced",
                "hours": 18,
                "lessons": [
                    "Security services: KMS, WAF, GuardDuty",
                    "Landing zones and account strategy",
                    "Infrastructure as Code with CloudFormation",
                    "CI/CD with CodePipeline and CodeBuild",
                    "Well-Architected Framework deep dive",
                    "Operational excellence runbooks",
                ],
            },
        ],
    },
    {
        "code": "gcp_cloud",
        "name": "Google Cloud Professional Track",
        "fr_name": "Parcours professionnel Google Cloud",
        "description": "Build scalable data and application platforms on GCP, from networking to MLOps.",
        "fr_description": "Construire des plateformes data et applicatives scalables sur GCP, du reseau au MLOps.",
        "icon": "gcp",
        "order": 60,
        "modules": [
            {
                "code": "gcp_fundamentals",
                "title": "GCP Fundamentals and Project Setup",
                "fr_title": "Fondamentaux GCP et setup projet",
                "level": "beginner",
                "hours": 12,
                "lessons": [
                    "Resource hierarchy and IAM model",
                    "Compute Engine, Cloud Run, GKE overview",
                    "Cloud Storage and data lifecycle",
                    "VPC networks and firewall rules",
                    "Monitoring and logging with Cloud Operations",
                    "Quotas, billing, and budget alerts",
                ],
            },
            {
                "code": "gcp_data_platform",
                "title": "Data Engineering on GCP",
                "fr_title": "Data engineering sur GCP",
                "level": "intermediate",
                "hours": 15,
                "lessons": [
                    "BigQuery architecture and optimization",
                    "Dataflow pipelines and stream processing",
                    "Pub/Sub event architectures",
                    "Cloud Composer orchestration",
                    "Dataproc and Spark workload strategy",
                    "Data governance with Dataplex",
                ],
            },
            {
                "code": "gcp_security_reliability",
                "title": "Security, Reliability, and SRE on GCP",
                "fr_title": "Securite, fiabilite et SRE sur GCP",
                "level": "advanced",
                "hours": 17,
                "lessons": [
                    "Identity-aware security and zero trust",
                    "Cloud Armor and security controls",
                    "SLOs, error budgets, and incident response",
                    "Multi-region and DR architectures",
                    "Terraform on GCP best practices",
                    "Production readiness reviews",
                ],
            },
        ],
    },
    {
        "code": "azure_cloud",
        "name": "Azure Solutions Engineering",
        "fr_name": "Ingenierie de solutions Azure",
        "description": "Create enterprise-ready Azure platforms with governance, security, and automation.",
        "fr_description": "Creer des plateformes Azure pretes entreprise avec gouvernance, securite et automatisation.",
        "icon": "azure",
        "order": 70,
        "modules": [
            {
                "code": "azure_core",
                "title": "Azure Core Services and Identity",
                "fr_title": "Services coeur Azure et identite",
                "level": "beginner",
                "hours": 12,
                "lessons": [
                    "Subscriptions, management groups, and RBAC",
                    "Compute with VM, App Service, Functions",
                    "Storage accounts and redundancy options",
                    "Networking with VNets and NSGs",
                    "Azure Monitor and Log Analytics",
                    "Cost management and tagging strategy",
                ],
            },
            {
                "code": "azure_architecture",
                "title": "Azure Application Architecture",
                "fr_title": "Architecture applicative Azure",
                "level": "intermediate",
                "hours": 15,
                "lessons": [
                    "API Management and integration patterns",
                    "Data services: Azure SQL, Cosmos DB, Cache",
                    "Eventing with Service Bus and Event Grid",
                    "Container strategy with AKS",
                    "Resilience and business continuity",
                    "Performance tuning and scaling",
                ],
            },
            {
                "code": "azure_governance_security",
                "title": "Azure Governance, Security, and DevOps",
                "fr_title": "Gouvernance, securite et DevOps Azure",
                "level": "advanced",
                "hours": 18,
                "lessons": [
                    "Policy, Blueprints, and landing zones",
                    "Defender for Cloud and Sentinel",
                    "Key Vault and secret rotation",
                    "IaC with Bicep and Terraform",
                    "CI/CD with Azure DevOps and GitHub Actions",
                    "Operational maturity model",
                ],
            },
        ],
    },
    {
        "code": "generative_ai",
        "name": "Generative AI Engineering",
        "fr_name": "Ingenierie IA generative",
        "description": "Design, evaluate, and operate production-grade generative AI systems with guardrails and measurable quality.",
        "fr_description": "Concevoir, evaluer et operer des systemes IA generative de niveau production avec garde-fous et qualite mesurable.",
        "icon": "ai",
        "order": 80,
        "modules": [
            {
                "code": "genai_fundamentals",
                "title": "Generative AI Foundations",
                "fr_title": "Fondamentaux IA generative",
                "level": "beginner",
                "hours": 14,
                "lessons": [
                    "Transformer intuition and tokenization",
                    "Prompting frameworks and task design",
                    "Model selection: quality, latency, cost",
                    "Embeddings and semantic retrieval",
                    "Safety basics and responsible AI",
                    "Evaluation metrics for generated outputs",
                ],
            },
            {
                "code": "genai_rag_agents",
                "title": "RAG Systems and Agent Architectures",
                "fr_title": "Systemes RAG et architectures agentiques",
                "level": "intermediate",
                "hours": 18,
                "lessons": [
                    "RAG pipeline design and chunking",
                    "Vector stores, indexing, and retrieval quality",
                    "Tool use and function calling patterns",
                    "Memory strategies and context windows",
                    "Agent orchestration and reliability",
                    "Human-in-the-loop review workflows",
                ],
            },
            {
                "code": "genai_prod_ops",
                "title": "GenAI Production, Security, and Governance",
                "fr_title": "Production, securite et gouvernance GenAI",
                "level": "advanced",
                "hours": 20,
                "lessons": [
                    "Hallucination mitigation and confidence",
                    "Prompt injection and data exfiltration defense",
                    "Observability for LLM applications",
                    "A/B testing and quality regression control",
                    "Cost controls and caching strategies",
                    "Policy, compliance, and model governance",
                ],
            },
        ],
    },
]


def _subject_i18n(subject: dict) -> tuple[dict, dict]:
    return (
        {
            "en": subject["name"],
            "fr": subject["fr_name"],
            "pt": subject["name"],
            "es": subject["name"],
            "it": subject["name"],
            "de": subject["name"],
        },
        {
            "en": subject["description"],
            "fr": subject["fr_description"],
            "pt": subject["description"],
            "es": subject["description"],
            "it": subject["description"],
            "de": subject["description"],
        },
    )


def _module_i18n(module: dict, subject_name: str) -> tuple[dict, dict]:
    title_i18n = {
        "en": module["title"],
        "fr": module["fr_title"],
        "pt": module["title"],
        "es": module["title"],
        "it": module["title"],
        "de": module["title"],
    }
    desc_en = (
        f"Comprehensive module for {subject_name}. Includes architecture principles, implementation tactics, "
        f"hands-on quizzes, and production readiness checkpoints."
    )
    desc_fr = (
        f"Module complet pour {subject_name}. Inclut principes d architecture, tactiques d implementation, "
        f"quiz pratiques et checkpoints de readiness production."
    )
    description_i18n = {
        "en": desc_en,
        "fr": desc_fr,
        "pt": desc_en,
        "es": desc_en,
        "it": desc_en,
        "de": desc_en,
    }
    return title_i18n, description_i18n


def _premium_subject_focus(subject_code: str) -> dict:
    focus_by_subject = {
        "audela_math_finance": {
            "mission": "Model financial decisions with explicit formulas, scenario assumptions, and sensitivity analysis.",
            "failure_mode": "Using incorrect discount/compounding assumptions and ignoring parameter sensitivity in decisions.",
            "metric": "NPV stability, sensitivity slope, and forecast error under stress",
            "artifacts": [
                "Formula sheet with variable definitions and units",
                "Worked examples with manual cross-check",
                "Sensitivity table for key inputs (rate, tenor, growth)",
            ],
        },
        "programming_logic": {
            "mission": "Build deterministic business logic that stays correct under edge cases and change pressure.",
            "failure_mode": "Conflicting rules and hidden branches that produce non-deterministic outcomes.",
            "metric": "branch coverage, defect escape rate, and decision latency",
            "artifacts": [
                "Decision table with explicit precedence and fallback",
                "Invariant checklist for correctness and safety",
                "Test matrix for happy path, edge cases, and regressions",
            ],
        },
        "aws_cloud": {
            "mission": "Design resilient AWS workloads with auditable security and operational readiness.",
            "failure_mode": "Single-AZ dependencies, excessive IAM permissions, and untested rollback paths.",
            "metric": "SLO attainment, IAM policy violations, and recovery time objective",
            "artifacts": [
                "Reference architecture with failure-domain boundaries",
                "IAM least-privilege matrix and trust assumptions",
                "Alarm + runbook package tied to release gates",
            ],
        },
        "gcp_cloud": {
            "mission": "Ship scalable GCP platforms with strong governance and observable reliability.",
            "failure_mode": "Service misfit, missing guardrails, and delayed detection of pipeline regressions.",
            "metric": "error budget burn, cost variance, and data freshness",
            "artifacts": [
                "Service selection memo with trade-off analysis",
                "SLO dashboard and alert policy",
                "Data governance controls for access and lifecycle",
            ],
        },
        "azure_cloud": {
            "mission": "Implement enterprise Azure solutions with policy-driven governance and safe delivery.",
            "failure_mode": "Policy drift, secret exposure, and weak network isolation between workloads.",
            "metric": "policy compliance rate, secret incident count, and deployment success rate",
            "artifacts": [
                "Landing-zone governance checklist",
                "Secret rotation and access control design",
                "CI/CD quality gates with rollback proof",
            ],
        },
        "generative_ai": {
            "mission": "Operate trustworthy GenAI systems with measurable quality, safety, and cost controls.",
            "failure_mode": "Hallucinations, prompt injection gaps, and quality regressions in production.",
            "metric": "grounded answer rate, blocked unsafe prompts, and cost-per-successful-task",
            "artifacts": [
                "Evaluation set with pass/fail criteria",
                "Guardrail policy and abuse test results",
                "Model routing and observability report",
            ],
        },
    }
    return focus_by_subject.get(subject_code, focus_by_subject["programming_logic"])


def _topic_acceptance_checks(topic: str) -> list[str]:
    topic_l = topic.lower()
    checks = [
        "Acceptance criteria are explicit and testable before release.",
        "Ownership and rollback path are documented and rehearsed.",
        "Monitoring covers leading indicators, not only failures.",
    ]
    if "security" in topic_l or "iam" in topic_l or "governance" in topic_l:
        checks.append("Access controls follow least privilege and are validated by tests.")
    elif "cost" in topic_l or "finops" in topic_l:
        checks.append("Cost guardrails and budget alerts are active in production.")
    elif "incident" in topic_l or "reliability" in topic_l or "resilien" in topic_l:
        checks.append("Failure drills demonstrate recovery within target RTO/RPO.")
    else:
        checks.append("Operational runbook includes escalation and handoff criteria.")
    return checks


def _lesson_content(subject_code: str, topic: str, module_title: str, lab_blueprint: dict) -> dict:
    if subject_code == "audela_math_finance":
        html_en = (
            f"<h3>{topic}</h3>"
            f"<p><strong>Context:</strong> In <em>{module_title}</em>, this lesson turns {topic.lower()} into measurable decisions using formulas and scenario checks.</p>"
            "<h5>Core Formulas</h5>"
            "<ul>"
            "<li><strong>Future Value:</strong> FV = PV * (1 + r)^n</li>"
            "<li><strong>Present Value:</strong> PV = FV / (1 + r)^n</li>"
            "<li><strong>Annuity Payment:</strong> PMT = P * r / (1 - (1 + r)^(-n))</li>"
            "<li><strong>Bond Price:</strong> P = Sum(C / (1 + y)^t) + FV / (1 + y)^n</li>"
            "</ul>"
            "<h5>Worked Example</h5>"
            "<p>An investment of 10,000 at 7% for 5 years gives FV = 10,000 * (1.07)^5 = 14,025.52. "
            "The same cash flow discounted at 9% gives PV = 14,025.52 / (1.09)^5 = 9,116.08.</p>"
            "<h5>Interpretation Checklist</h5>"
            "<ul>"
            "<li>Confirm units: annual vs monthly rate and tenor consistency.</li>"
            "<li>Stress test rate up/down by 100 bps and compare delta in value.</li>"
            "<li>Record assumption source before approving the decision.</li>"
            "</ul>"
            "<p><strong>Practice:</strong> Use the interactive graph calculator below to visualize curve shape and sensitivity.</p>"
        )
        html_fr = (
            f"<h3>{topic}</h3>"
            f"<p><strong>Contexte:</strong> Dans <em>{module_title}</em>, cette lecon transforme {topic.lower()} en decisions mesurables via formules et tests de scenario.</p>"
            "<h5>Formules coeur</h5>"
            "<ul>"
            "<li><strong>Valeur future:</strong> FV = PV * (1 + r)^n</li>"
            "<li><strong>Valeur presente:</strong> PV = FV / (1 + r)^n</li>"
            "<li><strong>Paiement annuite:</strong> PMT = P * r / (1 - (1 + r)^(-n))</li>"
            "<li><strong>Prix obligation:</strong> P = Somme(C / (1 + y)^t) + FV / (1 + y)^n</li>"
            "</ul>"
            "<h5>Exemple calcule</h5>"
            "<p>Un investissement de 10 000 a 7% pendant 5 ans donne FV = 10 000 * (1.07)^5 = 14 025.52. "
            "Ce meme flux actualise a 9% donne PV = 14 025.52 / (1.09)^5 = 9 116.08.</p>"
            "<h5>Checklist d interpretation</h5>"
            "<ul>"
            "<li>Verifier les unites: taux annuel vs mensuel et coherence des periodes.</li>"
            "<li>Faire un stress test du taux (+/- 100 bps) et mesurer l impact.</li>"
            "<li>Tracer les hypotheses avant validation de la decision.</li>"
            "</ul>"
            "<p><strong>Pratique:</strong> Utilisez le calculateur graphique interactif ci-dessous pour visualiser la sensibilite.</p>"
        )

        return {
            "en": html_en,
            "fr": html_fr,
            "pt": html_en,
            "es": html_en,
            "it": html_en,
            "de": html_en,
        }

    focus = _premium_subject_focus(subject_code)
    checks = _topic_acceptance_checks(topic)
    artifacts_html = "".join([f"<li>{item}</li>" for item in focus["artifacts"]])
    checks_html = "".join([f"<li>{item}</li>" for item in checks])
    deliverables_html = "".join([f"<li>{item}</li>" for item in lab_blueprint.get("deliverables", [])])

    html_en = (
        f"<h3>{topic}</h3>"
        f"<p><strong>Mission:</strong> {focus['mission']}</p>"
        f"<p><strong>Scenario:</strong> In <em>{module_title}</em>, this lesson addresses {topic.lower()} with production constraints.</p>"
        "<h5>What Can Go Wrong</h5>"
        f"<p>{focus['failure_mode']}</p>"
        "<h5>Implementation Deliverables</h5>"
        f"<ul>{deliverables_html}</ul>"
        "<h5>Engineering Artifacts</h5>"
        f"<ul>{artifacts_html}</ul>"
        "<h5>Acceptance Gates</h5>"
        f"<ul>{checks_html}</ul>"
        f"<p><strong>Primary metric family:</strong> {focus['metric']}.</p>"
    )

    html_fr = (
        f"<h3>{topic}</h3>"
        "<p><strong>Mission:</strong> Mettre en place une implementation fiable, securisee et operable en production.</p>"
        f"<p><strong>Scenario:</strong> Dans <em>{module_title}</em>, cette lecon traite {topic.lower()} avec des contraintes reelles.</p>"
        "<h5>Risques principaux</h5>"
        f"<p>{focus['failure_mode']}</p>"
        "<h5>Livrables d implementation</h5>"
        f"<ul>{deliverables_html}</ul>"
        "<h5>Artefacts d ingenierie</h5>"
        f"<ul>{artifacts_html}</ul>"
        "<h5>Gates d acceptance</h5>"
        f"<ul>{checks_html}</ul>"
        f"<p><strong>Famille de metriques prioritaire:</strong> {focus['metric']}.</p>"
    )

    return {
        "en": html_en,
        "fr": html_fr,
        "pt": html_en,
        "es": html_en,
        "it": html_en,
        "de": html_en,
    }


def _text_i18n(en_text: str, fr_text: str) -> dict:
    """Build simple i18n payload with EN/FR source and EN fallback for other locales."""
    return {
        "en": en_text,
        "fr": fr_text,
        "pt": en_text,
        "es": en_text,
        "it": en_text,
        "de": en_text,
    }


PREMIUM_TRACK_REALITY_KITS = {
    "programming_logic": {
        "quiz_a_title": "Logic Engine Design Review",
        "quiz_b_title": "Edge-case Failure Triage",
        "stack": "Python service, decision table, deterministic test suite",
        "lab": {
            "name": "Fraud Rule Decision Engine Lab",
            "context": "Design and harden a payment fraud decision engine with deterministic outputs.",
            "deliverables": [
                "Decision table covering normal, risky, and blocked outcomes",
                "Rule evaluation flowchart with fallback behavior",
                "20 automated tests including edge cases and invariants",
                "Post-incident review note documenting one prevented bug",
            ],
            "validation": [
                "No conflicting rules for the same input vector",
                "All branches are reachable via tests",
                "Median decision latency remains below agreed threshold",
            ],
        },
    },
    "aws_cloud": {
        "quiz_a_title": "AWS Architecture Trade-off",
        "quiz_b_title": "AWS Operational Readiness Gate",
        "stack": "VPC, ALB, Auto Scaling, RDS Multi-AZ, CloudWatch, IAM",
        "lab": {
            "name": "Three-Tier AWS Production Lab",
            "context": "Build a resilient web workload with auditable security and rollback safety.",
            "deliverables": [
                "Network layout with public/private subnets across 2 AZs",
                "IAM least-privilege matrix for app/runtime/deploy roles",
                "CloudWatch dashboard + alarm runbook",
                "Blue/green or canary release plan with rollback procedure",
            ],
            "validation": [
                "Single AZ failure does not break SLA",
                "Unauthorized role assumption is denied",
                "Recovery path is tested end-to-end",
            ],
        },
    },
    "gcp_cloud": {
        "quiz_a_title": "GCP Service Selection Drill",
        "quiz_b_title": "GCP Reliability Incident Drill",
        "stack": "Cloud Run, BigQuery, Pub/Sub, Dataflow, Cloud Monitoring",
        "lab": {
            "name": "Streaming Analytics on GCP Lab",
            "context": "Deliver near-real-time analytics with governed access and cost controls.",
            "deliverables": [
                "Pub/Sub to Dataflow pipeline with dead-letter strategy",
                "BigQuery schema and partitioning plan",
                "IAM boundaries for developers, operators, and auditors",
                "SLO dashboard with burn-rate alert policy",
            ],
            "validation": [
                "Pipeline recovers from malformed events",
                "BigQuery cost guardrails prevent runaway spend",
                "Alerting catches SLA degradation before user impact",
            ],
        },
    },
    "azure_cloud": {
        "quiz_a_title": "Azure Enterprise Pattern Review",
        "quiz_b_title": "Azure Governance Escalation Case",
        "stack": "Azure App Service, Azure SQL, Key Vault, VNets, Azure Monitor",
        "lab": {
            "name": "Azure Governance + DevOps Lab",
            "context": "Ship an enterprise app with policy controls and secure CI/CD.",
            "deliverables": [
                "Landing zone controls with RBAC and policy definitions",
                "Secret rotation design using Key Vault",
                "Pipeline quality gates for security, tests, and approvals",
                "Operational playbook for Sev-2 incident response",
            ],
            "validation": [
                "Policy violations are blocked before deploy",
                "Secrets never appear in build logs",
                "Runbook restores service within target recovery objective",
            ],
        },
    },
    "generative_ai": {
        "quiz_a_title": "GenAI Architecture Evaluation",
        "quiz_b_title": "Prompt Injection Response Drill",
        "stack": "RAG pipeline, vector index, policy filters, LLM observability",
        "lab": {
            "name": "RAG Reliability and Safety Lab",
            "context": "Implement a production RAG assistant with measurable quality and safety.",
            "deliverables": [
                "Retrieval evaluation set with precision and recall tracking",
                "Guardrail policy for prompt injection and data leakage",
                "Latency/cost dashboard by model and route",
                "Human-review workflow for low-confidence answers",
            ],
            "validation": [
                "Unsafe prompts are detected and blocked",
                "Grounded answer rate meets target threshold",
                "Regression suite catches output quality drift",
            ],
        },
    },
}


PREMIUM_QUIZ_THEME_BY_SUBJECT = {
    "programming_logic": [
        "deterministic decision logic",
        "branch and edge-case coverage",
        "idempotent behavior under retries",
        "complexity and maintainability",
    ],
    "aws_cloud": [
        "high availability and fault isolation",
        "least-privilege IAM design",
        "observability and incident response",
        "cost-aware architecture decisions",
    ],
    "gcp_cloud": [
        "managed service selection",
        "secure project/IAM boundaries",
        "SLO and reliability operations",
        "data platform governance",
    ],
    "azure_cloud": [
        "policy-driven governance",
        "identity and secret management",
        "network isolation strategy",
        "DevOps release controls",
    ],
    "generative_ai": [
        "prompt/context reliability",
        "RAG retrieval quality",
        "safety and abuse prevention",
        "quality/cost observability",
    ],
}


def _build_premium_quiz_questions(subject_code: str, module_title: str, lesson_topic: str) -> list[dict]:
    if subject_code == "audela_math_finance":
        return [
            {
                "text_i18n": {
                    "en": (
                        f"In '{module_title}' for '{lesson_topic}', which statement about discount rates is correct "
                        "when valuing future cash flows?"
                    ),
                    "fr": (
                        f"Dans '{module_title}' pour '{lesson_topic}', quelle affirmation sur le taux d actualisation "
                        "est correcte pour valoriser des flux futurs ?"
                    ),
                },
                "explanation_i18n": {
                    "en": "Higher discount rates reduce present value because future cash flows are discounted more aggressively.",
                    "fr": "Un taux d actualisation plus eleve reduit la valeur presente car les flux futurs sont davantage actualises.",
                },
                "options": [
                    {"text_i18n": {"en": "A higher discount rate increases present value.", "fr": "Un taux plus eleve augmente la valeur presente."}, "is_correct": False},
                    {"text_i18n": {"en": "A higher discount rate decreases present value.", "fr": "Un taux plus eleve diminue la valeur presente."}, "is_correct": True},
                    {"text_i18n": {"en": "Discount rate has no impact on valuation.", "fr": "Le taux n a pas d impact sur la valorisation."}, "is_correct": False},
                    {"text_i18n": {"en": "Only maturity matters, not discount rate.", "fr": "Seule la maturite compte, pas le taux."}, "is_correct": False},
                ],
            },
            {
                "text_i18n": {
                    "en": "A bond has fixed coupons. If yield rises, what is the expected first-order impact on price?",
                    "fr": "Une obligation a coupons fixes. Si le rendement monte, quel est l impact de premier ordre sur le prix ?",
                },
                "explanation_i18n": {
                    "en": "Bond price and yield move in opposite directions; duration captures this first-order sensitivity.",
                    "fr": "Le prix obligataire evolue en sens inverse du rendement; la duration capte cette sensibilite de premier ordre.",
                },
                "options": [
                    {"text_i18n": {"en": "Price rises.", "fr": "Le prix augmente."}, "is_correct": False},
                    {"text_i18n": {"en": "Price is unchanged.", "fr": "Le prix est inchange."}, "is_correct": False},
                    {"text_i18n": {"en": "Price falls.", "fr": "Le prix baisse."}, "is_correct": True},
                    {"text_i18n": {"en": "Price becomes random.", "fr": "Le prix devient aleatoire."}, "is_correct": False},
                ],
            },
            {
                "text_i18n": {
                    "en": "For a standard annuity, which change increases the periodic payment PMT (all else equal)?",
                    "fr": "Pour une annuite standard, quel changement augmente PMT (toutes choses egales par ailleurs) ?",
                },
                "explanation_i18n": {
                    "en": "For fixed principal and tenor, higher periodic rate implies a higher payment amount.",
                    "fr": "A principal et maturite fixes, un taux periodique plus eleve implique un paiement plus eleve.",
                },
                "options": [
                    {"text_i18n": {"en": "Lower rate with same tenor.", "fr": "Taux plus faible a maturite identique."}, "is_correct": False},
                    {"text_i18n": {"en": "Higher rate with same tenor.", "fr": "Taux plus eleve a maturite identique."}, "is_correct": True},
                    {"text_i18n": {"en": "Longer tenor at same rate.", "fr": "Maturite plus longue au meme taux."}, "is_correct": False},
                    {"text_i18n": {"en": "Zero principal.", "fr": "Principal nul."}, "is_correct": False},
                ],
            },
            {
                "text_i18n": {
                    "en": "In IFRS9 what-if analysis, why do we run sensitivity tests on PD/LGD/EAD assumptions?",
                    "fr": "Dans l analyse what-if IFRS9, pourquoi tester la sensibilite des hypotheses PD/LGD/EAD ?",
                },
                "explanation_i18n": {
                    "en": "Sensitivity testing quantifies model risk and governance impact before portfolio decisions.",
                    "fr": "Les tests de sensibilite quantifient le risque modele et l impact gouvernance avant decision portefeuille.",
                },
                "options": [
                    {"text_i18n": {"en": "To avoid documenting assumptions.", "fr": "Pour eviter de documenter les hypotheses."}, "is_correct": False},
                    {"text_i18n": {"en": "To quantify impact under alternative macro and risk assumptions.", "fr": "Pour quantifier l impact selon des hypotheses macro et risque alternatives."}, "is_correct": True},
                    {"text_i18n": {"en": "To replace all baseline scenarios.", "fr": "Pour remplacer tous les scenarios de base."}, "is_correct": False},
                    {"text_i18n": {"en": "Because accounting standards forbid base cases.", "fr": "Parce que les normes interdisent les cas de base."}, "is_correct": False},
                ],
            },
        ]

    themes = PREMIUM_QUIZ_THEME_BY_SUBJECT.get(subject_code, PREMIUM_QUIZ_THEME_BY_SUBJECT["programming_logic"])
    q_defs: list[dict] = []

    for idx, theme in enumerate(themes, start=1):
        q_defs.append(
            {
                "text_i18n": {
                    "en": (
                        f"In '{module_title}', while working on '{lesson_topic}', which action best improves {theme} "
                        "without increasing operational risk?"
                    ),
                    "fr": (
                        f"Dans '{module_title}', sur '{lesson_topic}', quelle action ameliore le mieux {theme} "
                        "sans augmenter le risque operationnel ?"
                    ),
                },
                "explanation_i18n": {
                    "en": (
                        "A staged implementation with explicit controls, measurable outcomes, and rollback readiness "
                        "is the most reliable production pattern."
                    ),
                    "fr": (
                        "Une implementation progressive avec controles explicites, mesures et rollback teste "
                        "est le pattern le plus fiable en production."
                    ),
                },
                "options": [
                    {
                        "text_i18n": {
                            "en": "Ship a fast workaround first, then design controls in a later sprint.",
                            "fr": "Livrer un contournement rapide, puis definir les controles plus tard.",
                        },
                        "is_correct": False,
                    },
                    {
                        "text_i18n": {
                            "en": (
                                "Adopt staged rollout with acceptance gates, telemetry, owner assignment, and "
                                "validated rollback."
                            ),
                            "fr": (
                                "Adopter un deploiement progressif avec gates d acceptance, telemetrie, ownership "
                                "et rollback valide."
                            ),
                        },
                        "is_correct": True,
                    },
                    {
                        "text_i18n": {
                            "en": "Consolidate critical and non-critical paths into one component for simplicity.",
                            "fr": "Fusionner chemins critiques et non critiques dans un seul composant.",
                        },
                        "is_correct": False,
                    },
                    {
                        "text_i18n": {
                            "en": "Delay observability and runbook authoring until after production launch.",
                            "fr": "Reporter observabilite et runbook apres la mise en production.",
                        },
                        "is_correct": False,
                    },
                ],
            }
        )

    return q_defs


def _build_premium_exercises(
    subject_code: str,
    subject_name: str,
    module_title: str,
    lesson_topic: str,
    lesson_code: str,
) -> list[dict]:
    """Create two scenario quizzes + one practical lab check with concrete track-specific context."""
    if subject_code == "audela_math_finance":
        return [
            {
                "code": f"{lesson_code}_quiz_a",
                "title": "Discounting Decision Drill",
                "fr_title": "Drill de decision d actualisation",
                "instruction": "Choose the best valuation decision based on formulas and numerical comparison.",
                "fr_instruction": "Choisissez la meilleure decision de valorisation a partir des formules et d une comparaison numerique.",
                "points": 14,
                "question": (
                    f"In '{module_title}', a project returns 120,000 in 3 years. At 8% and 12% discount rates, which conclusion is correct for '{lesson_topic}'?"
                ),
                "choices": [
                    "Higher rate gives higher present value, so use 12% to maximize valuation.",
                    "Present value at 12% is lower than at 8%, so valuation is more conservative at 12%.",
                    "Discount rate is irrelevant when cash flow amount is fixed.",
                    "Only maturity matters; rate choice cannot change present value.",
                ],
                "answer": 1,
                "rationale": "Higher discount rates reduce present value and produce more conservative valuation outcomes.",
                "why_not": [
                    "Rate and value are inversely related in discounted cash flow math.",
                    "Ignoring discount rate hides risk and opportunity cost.",
                    "Maturity and rate both matter in time value calculations.",
                ],
                "learning_objective": "Apply time value formulas and compare scenario outcomes numerically.",
                "subject": subject_name,
            },
            {
                "code": f"{lesson_code}_quiz_b",
                "title": "Duration and Yield Scenario",
                "fr_title": "Scenario duration et rendement",
                "instruction": "Select the most accurate interpretation of yield shocks on bond valuation.",
                "fr_instruction": "Selectionnez l interpretation la plus juste d un choc de rendement sur la valorisation obligataire.",
                "points": 16,
                "question": (
                    f"A fixed-coupon bond portfolio in '{lesson_topic}' faces a +75 bps shock. Which statement is correct before rebalancing?"
                ),
                "choices": [
                    "Price impact is positive for all fixed-coupon bonds.",
                    "Price impact is approximately negative and linked to duration.",
                    "Yield changes do not affect mark-to-market value.",
                    "Only convexity matters; duration can be ignored.",
                ],
                "answer": 1,
                "rationale": "First-order bond price sensitivity to yield is captured by duration and is negative when yield rises.",
                "why_not": [
                    "Yield up typically implies price down for fixed coupons.",
                    "Mark-to-market is directly rate-sensitive.",
                    "Convexity refines but does not replace duration for first-order effect.",
                ],
                "learning_objective": "Interpret rate shocks with duration-first logic before second-order refinements.",
                "subject": subject_name,
            },
            {
                "code": f"{lesson_code}_lab",
                "title": "What-If Finance Lab",
                "fr_title": "Lab finance what-if",
                "instruction": "Use graph and formulas to compare baseline vs stress assumptions, then pick the valid governance conclusion.",
                "fr_instruction": "Utilisez graphe et formules pour comparer scenario de base vs stress, puis choisissez la conclusion de gouvernance valide.",
                "points": 20,
                "question": (
                    f"You completed a what-if analysis for '{lesson_topic}'. Which artifact is mandatory before approving a risk decision?"
                ),
                "choices": [
                    "Single baseline output with no sensitivity traceability.",
                    "Sensitivity table (+/- shocks), documented assumptions, and decision rationale.",
                    "One screenshot of the graph without numeric checkpoints.",
                    "A verbal summary without model parameters.",
                ],
                "answer": 1,
                "rationale": "Risk decisions require reproducible sensitivity evidence and explicit assumption governance.",
                "why_not": [
                    "Baseline alone is insufficient for model risk control.",
                    "Graph visuals need numeric checkpoints to be auditable.",
                    "Verbal summaries are not reproducible evidence.",
                ],
                "learning_objective": "Produce auditable what-if evidence for finance and IFRS9 governance decisions.",
                "subject": subject_name,
            },
        ]

    kit = PREMIUM_TRACK_REALITY_KITS.get(subject_code, PREMIUM_TRACK_REALITY_KITS["programming_logic"])
    objective = f"Apply {lesson_topic.lower()} decisions under reliability, security, and delivery constraints"

    quiz_a_choices = [
        f"Ship ad-hoc changes in {kit['stack']} without baselines or rollback criteria",
        (
            "Implement staged rollout with measurable SLOs, ownership, automated checks, and a tested rollback path"
        ),
        "Merge critical and non-critical workloads into one failure domain to simplify diagrams",
        "Postpone observability and incident response design until after launch",
    ]
    quiz_b_choices = [
        "Bypass architecture/security review to preserve short-term release velocity",
        "Translate findings into release gates with explicit controls, test evidence, and sign-off criteria",
        "Stop all delivery work indefinitely without prioritizing high-risk gaps",
        "Increase infrastructure size only, leaving decision logic and controls unchanged",
    ]

    lab_blueprint = kit["lab"]
    return [
        {
            "code": f"{lesson_code}_quiz_a",
            "title": kit["quiz_a_title"],
            "fr_title": "Exercice de decision d'architecture",
            "instruction": (
                "Analyze the technical scenario and choose the option that remains secure, testable, and operable in production."
            ),
            "fr_instruction": (
                "Analysez le scenario technique et choisissez l'option qui reste securisee, testable et operable en production."
            ),
            "points": 14,
            "question": (
                f"In '{module_title}', your team is implementing '{lesson_topic}' on {kit['stack']}. "
                "Which approach is the most production-ready for the next release window?"
            ),
            "choices": quiz_a_choices,
            "answer": 1,
            "rationale": (
                "The winning option combines controlled rollout, measurable outcomes, clear ownership, and rollback safety. "
                "That is the minimum bar for production engineering."
            ),
            "why_not": [
                "Uncontrolled changes create incident risk and weak auditability.",
                "Single failure domains reduce resilience and increase blast radius.",
                "Delayed observability hides regressions until user-facing impact.",
            ],
            "learning_objective": objective,
            "subject": subject_name,
        },
        {
            "code": f"{lesson_code}_quiz_b",
            "title": kit["quiz_b_title"],
            "fr_title": "Scenario de prevention d'incident",
            "instruction": "Pick the first remediation step that closes risk quickly while preserving delivery quality.",
            "fr_instruction": "Choisissez la premiere action de remediation qui reduit le risque sans perdre la qualite de delivery.",
            "points": 16,
            "question": (
                f"A governance review failed your implementation of '{lesson_topic}' in '{module_title}'. "
                "What should the team do before go-live?"
            ),
            "choices": quiz_b_choices,
            "answer": 1,
            "rationale": (
                "Release gates tied to controls and validation evidence turn recommendations into enforceable engineering practice."
            ),
            "why_not": [
                "Skipping controls compounds reliability and compliance risk.",
                "Unbounded freeze harms value delivery and does not target the highest risks.",
                "Capacity-only changes do not fix architecture, governance, or safety gaps.",
            ],
            "learning_objective": objective,
            "subject": subject_name,
        },
        {
            "code": f"{lesson_code}_lab",
            "title": "Hands-on Production Lab",
            "fr_title": "Laboratoire pratique production",
            "instruction": (
                "Execute the lab blueprint and submit your artifacts. Then answer the gating question for release readiness."
            ),
            "fr_instruction": (
                "Executez le blueprint du lab et soumettez vos livrables. Puis repondez a la question de readiness release."
            ),
            "points": 20,
            "question": (
                f"You completed the lab '{lab_blueprint['name']}' for '{lesson_topic}'. "
                "Which artifact is mandatory before approving production promotion?"
            ),
            "choices": [
                "A slide deck describing intended architecture only",
                "A backlog item to add monitoring in a future sprint",
                "Evidence package with validation results, rollback test output, and ownership runbook",
                "A cost estimate without reliability or security acceptance criteria",
            ],
            "answer": 2,
            "rationale": (
                "Production promotion requires verifiable evidence that controls, rollback, and ownership are real and tested."
            ),
            "why_not": [
                "Design intent alone is insufficient without verification evidence.",
                "Deferred observability leaves a known blind spot at launch.",
                "Cost-only validation ignores safety and reliability obligations.",
            ],
            "learning_objective": f"Deliver a complete production lab for {lesson_topic.lower()}.",
            "subject": subject_name,
            "lab_blueprint": {
                "name": lab_blueprint["name"],
                "context": lab_blueprint["context"],
                "deliverables": lab_blueprint["deliverables"],
                "validation": lab_blueprint["validation"],
            },
        },
    ]


def _seed_premium_catalog(force: bool = False) -> dict:
    from ..models.e_learning import (
        ELearningSubject,
        ELearningModule,
        ELearningLesson,
        ELearningExercise,
        ELearningQuiz,
        ELearningQuizQuestion,
        ELearningQuizOption,
    )

    stats = {"subjects": 0, "modules": 0, "lessons": 0, "exercises": 0, "quizzes": 0, "questions": 0}

    for subject_data in PREMIUM_SUBJECTS:
        name_i18n, description_i18n = _subject_i18n(subject_data)
        subject = ELearningSubject.query.filter_by(code=subject_data["code"]).first()
        if not subject:
            subject = ELearningSubject(code=subject_data["code"])
            db.session.add(subject)
            stats["subjects"] += 1

        subject.name_i18n = name_i18n
        subject.description_i18n = description_i18n
        subject.icon_url = f"/static/assets/icons/{subject_data['icon']}.svg"
        subject.order = subject_data["order"]
        subject.is_active = True
        db.session.flush()

        valid_module_codes = {m["code"] for m in subject_data["modules"]}
        if force and valid_module_codes:
            stale_modules = ELearningModule.query.filter(
                ELearningModule.subject_id == subject.id,
                ELearningModule.code.notin_(valid_module_codes),
            ).all()
            for stale in stale_modules:
                db.session.delete(stale)
            if stale_modules:
                db.session.flush()

        for mod_index, module_data in enumerate(subject_data["modules"], start=1):
            module = ELearningModule.query.filter_by(subject_id=subject.id, code=module_data["code"]).first()
            if not module:
                module = ELearningModule(subject_id=subject.id, code=module_data["code"])
                db.session.add(module)
            stats["modules"] += 1

            title_i18n, description_i18n = _module_i18n(module_data, subject_data["name"])
            module.title_i18n = title_i18n
            module.description_i18n = description_i18n
            module.level = module_data["level"]
            module.order = mod_index
            module.is_active = True
            module.total_lessons = len(module_data["lessons"])
            module.total_exercises = 0
            module.estimated_hours = float(module_data["hours"])
            module.pass_threshold = 80
            module.points_on_completion = 220 + mod_index * 30
            db.session.flush()

            valid_lesson_codes = {f"{module_data['code']}_l{idx:02d}" for idx in range(1, len(module_data["lessons"]) + 1)}
            if force and valid_lesson_codes:
                stale_lessons = ELearningLesson.query.filter(
                    ELearningLesson.module_id == module.id,
                    ELearningLesson.code.notin_(valid_lesson_codes),
                ).all()
                for stale in stale_lessons:
                    db.session.delete(stale)
                if stale_lessons:
                    db.session.flush()

            for lesson_index, lesson_topic in enumerate(module_data["lessons"], start=1):
                lesson_code = f"{module_data['code']}_l{lesson_index:02d}"
                lesson = ELearningLesson.query.filter_by(module_id=module.id, code=lesson_code).first()
                if not lesson:
                    lesson = ELearningLesson(module_id=module.id, code=lesson_code)
                    db.session.add(lesson)
                stats["lessons"] += 1

                lesson.title_i18n = {
                    "en": lesson_topic,
                    "fr": lesson_topic,
                    "pt": lesson_topic,
                    "es": lesson_topic,
                    "it": lesson_topic,
                    "de": lesson_topic,
                }
                lesson.description_i18n = {
                    "en": (
                        f"Production lesson on {lesson_topic.lower()} with concrete scenario, "
                        "lab deliverables, and measurable acceptance gates."
                    ),
                    "fr": (
                        f"Lecon production sur {lesson_topic.lower()} avec scenario concret, "
                        "livrables de lab et gates d acceptance mesurables."
                    ),
                    "pt": (
                        f"Production lesson on {lesson_topic.lower()} with concrete scenario, "
                        "lab deliverables, and measurable acceptance gates."
                    ),
                    "es": (
                        f"Production lesson on {lesson_topic.lower()} with concrete scenario, "
                        "lab deliverables, and measurable acceptance gates."
                    ),
                    "it": (
                        f"Production lesson on {lesson_topic.lower()} with concrete scenario, "
                        "lab deliverables, and measurable acceptance gates."
                    ),
                    "de": (
                        f"Production lesson on {lesson_topic.lower()} with concrete scenario, "
                        "lab deliverables, and measurable acceptance gates."
                    ),
                }
                kit = PREMIUM_TRACK_REALITY_KITS.get(
                    subject_data["code"],
                    PREMIUM_TRACK_REALITY_KITS["programming_logic"],
                )
                lesson.content_html_i18n = _lesson_content(
                    subject_data["code"],
                    lesson_topic,
                    module_data["title"],
                    kit["lab"],
                )
                lesson.key_concepts_i18n = {
                    "en": [
                        f"{lesson_topic} implementation strategy",
                        "Real-world failure modes and mitigation",
                        "Acceptance gates and release controls",
                        "Operational ownership and rollback readiness",
                        "Metrics and audit evidence for production",
                    ],
                    "fr": [
                        f"Strategie d implementation: {lesson_topic}",
                        "Modes d echec reels et mitigations",
                        "Gates d acceptance et controles release",
                        "Ownership operationnel et rollback",
                        "Metriques et preuves pour la production",
                    ],
                }
                lesson.order = lesson_index
                lesson.is_active = True
                db.session.flush()

                if force:
                    ELearningExercise.query.filter_by(lesson_id=lesson.id).delete(synchronize_session=False)

                # Premium non-SQL/Python subjects rely on quizzes for evaluation.
                # Keep exercise count at zero so labs remain only in SQL and Python tracks.

                quiz_code = f"{lesson_code}_quiz"
                quiz = ELearningQuiz.query.filter_by(lesson_id=lesson.id, code=quiz_code).first()
                if not quiz:
                    quiz = ELearningQuiz(lesson_id=lesson.id, code=quiz_code)
                    db.session.add(quiz)
                stats["quizzes"] += 1

                quiz.title_i18n = {
                    "en": f"{lesson_topic} - Production Knowledge Check",
                    "fr": f"{lesson_topic} - Quiz de validation production",
                    "pt": f"{lesson_topic} - Production Knowledge Check",
                    "es": f"{lesson_topic} - Production Knowledge Check",
                    "it": f"{lesson_topic} - Production Knowledge Check",
                    "de": f"{lesson_topic} - Production Knowledge Check",
                }
                quiz.description_i18n = {
                    "en": (
                        "Scenario-based quiz on architecture decisions, controls, and operational readiness "
                        "for this lesson."
                    ),
                    "fr": (
                        "Quiz par scenarios sur decisions d architecture, controles et readiness operationnelle "
                        "pour cette lecon."
                    ),
                    "pt": (
                        "Scenario-based quiz on architecture decisions, controls, and operational readiness "
                        "for this lesson."
                    ),
                    "es": (
                        "Scenario-based quiz on architecture decisions, controls, and operational readiness "
                        "for this lesson."
                    ),
                    "it": (
                        "Scenario-based quiz on architecture decisions, controls, and operational readiness "
                        "for this lesson."
                    ),
                    "de": (
                        "Scenario-based quiz on architecture decisions, controls, and operational readiness "
                        "for this lesson."
                    ),
                }
                quiz.time_limit_minutes = 12
                quiz.pass_threshold = 75
                quiz.max_attempts = None
                quiz.shuffle_questions = True
                quiz.show_correct_answers = True
                quiz.points_on_pass = 30
                quiz.order = lesson_index
                quiz.is_active = True
                db.session.flush()

                question_defs = _build_premium_quiz_questions(
                    subject_data["code"],
                    module_data["title"],
                    lesson_topic,
                )

                valid_question_orders = set(range(1, len(question_defs) + 1))
                if force:
                    stale_questions = ELearningQuizQuestion.query.filter(
                        ELearningQuizQuestion.quiz_id == quiz.id,
                        ELearningQuizQuestion.order.notin_(valid_question_orders),
                    ).all()
                    for q in stale_questions:
                        db.session.delete(q)
                    if stale_questions:
                        db.session.flush()

                for q_order, q_def in enumerate(question_defs, start=1):
                    question = ELearningQuizQuestion.query.filter_by(quiz_id=quiz.id, order=q_order).first()
                    if not question:
                        question = ELearningQuizQuestion(quiz_id=quiz.id)
                        db.session.add(question)
                    stats["questions"] += 1

                    question.order = q_order
                    question.question_type = "multiple_choice"
                    question.text_i18n = {
                        "en": q_def["text_i18n"]["en"],
                        "fr": q_def["text_i18n"]["fr"],
                        "pt": q_def["text_i18n"]["en"],
                        "es": q_def["text_i18n"]["en"],
                        "it": q_def["text_i18n"]["en"],
                        "de": q_def["text_i18n"]["en"],
                    }
                    question.explanation_i18n = {
                        "en": q_def["explanation_i18n"]["en"],
                        "fr": q_def["explanation_i18n"]["fr"],
                        "pt": q_def["explanation_i18n"]["en"],
                        "es": q_def["explanation_i18n"]["en"],
                        "it": q_def["explanation_i18n"]["en"],
                        "de": q_def["explanation_i18n"]["en"],
                    }
                    question.points = 1
                    question.allow_partial_credit = False
                    question.penalty_points = 0
                    question.is_active = True
                    db.session.flush()

                    for o_order, option_def in enumerate(q_def["options"], start=1):
                        option = ELearningQuizOption.query.filter_by(question_id=question.id, order=o_order).first()
                        if not option:
                            option = ELearningQuizOption(question_id=question.id)
                            db.session.add(option)

                        option.order = o_order
                        option.text_i18n = {
                            "en": option_def["text_i18n"]["en"],
                            "fr": option_def["text_i18n"]["fr"],
                            "pt": option_def["text_i18n"]["en"],
                            "es": option_def["text_i18n"]["en"],
                            "it": option_def["text_i18n"]["en"],
                            "de": option_def["text_i18n"]["en"],
                        }
                        option.is_correct = bool(option_def["is_correct"])
                        db.session.flush()

                    if force:
                        ELearningQuizOption.query.filter(
                            ELearningQuizOption.question_id == question.id,
                            ELearningQuizOption.order > len(q_def["options"]),
                        ).delete(synchronize_session=False)

    db.session.commit()
    return stats


EXAM_BLUEPRINT_BY_SUBJECT = {
    "programming_logic": {
        "track": "Programming Logic Professional",
        "domains": [
            "Algorithm design",
            "Data structure selection",
            "Complexity trade-offs",
            "Debugging and correctness",
            "Production-safe decision logic",
            "Edge-case handling",
        ],
    },
    "audela_math_finance": {
        "track": "Financial Math and Risk Analytics",
        "domains": [
            "Time value of money decisions",
            "Compounding and discounting trade-offs",
            "Loan and annuity structuring",
            "Bond sensitivity and yield interpretation",
            "Portfolio risk decomposition",
            "IFRS9 what-if and staging governance",
        ],
    },
    "aws_cloud": {
        "track": "AWS Solutions Architect",
        "domains": [
            "Reliability and fault tolerance",
            "Security and identity",
            "Performance efficiency",
            "Cost optimization",
            "Operational excellence",
            "Disaster recovery",
        ],
    },
    "gcp_cloud": {
        "track": "Google Cloud Professional Architect",
        "domains": [
            "Secure infrastructure",
            "Service selection",
            "Scalable architecture",
            "Data platform decisions",
            "Reliability engineering",
            "Cost and governance",
        ],
    },
    "azure_cloud": {
        "track": "Microsoft Azure Solutions Architect",
        "domains": [
            "Identity and governance",
            "Compute and integration",
            "Data and storage strategy",
            "Network segmentation",
            "Security posture",
            "DevOps and operations",
        ],
    },
    "generative_ai": {
        "track": "Generative AI Production Engineer",
        "domains": [
            "Prompt and context engineering",
            "RAG design and retrieval quality",
            "Model evaluation",
            "Safety and guardrails",
            "Observability and regression control",
            "Cost-latency-quality balancing",
        ],
    },
}


EXAM_REAL_SCENARIOS = {
    "programming_logic": [
        "Refactor nested if/else payment approval flow into a deterministic rules engine",
        "Choose data structures for high-volume deduplication under strict latency",
        "Reduce algorithmic complexity in a recommendation scoring pipeline",
        "Diagnose intermittent bug caused by non-deterministic branch ordering",
        "Define idempotent command handling for retry-heavy event ingestion",
        "Handle edge-case inputs that previously caused false approvals",
    ],
    "aws_cloud": [
        "Redesign a single-AZ web stack into multi-AZ architecture with audited failover",
        "Tighten IAM and role trust boundaries after excessive permissions were found",
        "Improve p95 latency for API path using ALB + Auto Scaling policy tuning",
        "Lower monthly spend without violating reliability or security constraints",
        "Document runbook for incident response and controlled rollback",
        "Implement backup and disaster recovery targets for critical data services",
    ],
    "gcp_cloud": [
        "Select resilient services for a global API + analytics platform",
        "Secure IAM boundaries across projects and environments",
        "Design scalable architecture with managed services and failure isolation",
        "Choose BigQuery/Dataflow/PubSub topology for streaming analytics",
        "Define SLOs, error budgets, and escalation paths for operations",
        "Add governance controls to limit runaway cloud costs",
    ],
    "azure_cloud": [
        "Standardize tenant RBAC and policy inheritance across subscriptions",
        "Select compute/integration services for mixed synchronous and event workflows",
        "Design data architecture across Azure SQL, Blob, and Cosmos DB",
        "Harden network segmentation with private endpoints and NSG strategy",
        "Raise security posture with Defender, Key Vault, and audit trails",
        "Implement CI/CD gates with rollback and post-deploy verification",
    ],
    "generative_ai": [
        "Engineer prompts and context windows for deterministic support responses",
        "Improve RAG retrieval quality under noisy enterprise documents",
        "Evaluate model quality with offline and online test datasets",
        "Implement safety filters against prompt injection and data leakage",
        "Set up observability for hallucination rate and quality regressions",
        "Balance model routing for cost, latency, and answer quality",
    ],
}


def _exam_title_i18n(module_title: str, track: str) -> dict:
    en = f"Exam Lab: {track} for {module_title}"
    fr = f"Lab examen: {track} pour {module_title}"
    return {"en": en, "fr": fr, "pt": en, "es": en, "it": en, "de": en}


def _exam_content_i18n(track: str, module_title: str) -> dict:
    en = (
        f"<h3>{track} - Exam Readiness</h3>"
        f"<p>This lab prepares you for scenario-based assessments in <strong>{module_title}</strong>.</p>"
        "<ul>"
        "<li>Timed decision-making under constraints.</li>"
        "<li>Architecture trade-offs with measurable outcomes.</li>"
        "<li>Security, reliability, and cost balancing.</li>"
        "<li>Production-grade answer rationale.</li>"
        "</ul>"
    )
    fr = (
        f"<h3>{track} - Preparation examen</h3>"
        f"<p>Ce lab vous prepare aux evaluations par scenarios sur <strong>{module_title}</strong>.</p>"
        "<ul>"
        "<li>Prise de decision sous contraintes.</li>"
        "<li>Compromis d architecture avec resultats mesurables.</li>"
        "<li>Equilibre securite, fiabilite et cout.</li>"
        "<li>Justification orientee production.</li>"
        "</ul>"
    )
    return {"en": en, "fr": fr, "pt": en, "es": en, "it": en, "de": en}


def _build_exam_question_pack(subject_code: str, module_title: str) -> list[dict]:
    bp = EXAM_BLUEPRINT_BY_SUBJECT[subject_code]
    domains = bp["domains"]
    scenarios = EXAM_REAL_SCENARIOS.get(subject_code, [])
    questions: list[dict] = []

    for idx, domain in enumerate(domains, start=1):
        scenario = scenarios[idx - 1] if idx - 1 < len(scenarios) else f"Improve {domain.lower()}"
        questions.append(
            {
                "code": f"q{idx:02d}",
                "title": f"Certification Quiz {idx}",
                "fr_title": f"Quiz certification {idx}",
                "instruction": (
                    "Select the option that best satisfies reliability, security, operational, and cost constraints "
                    "for this scenario."
                ),
                "fr_instruction": (
                    "Selectionnez l option qui satisfait le mieux les contraintes de fiabilite, securite, operations "
                    "et cout pour ce scenario."
                ),
                "points": 20,
                "question": (
                    f"In module '{module_title}', your team must solve this real scenario: {scenario}. "
                    "Which approach is the most production-ready?"
                ),
                "choices": [
                    "Implement immediate changes without baseline metrics, threat model, or rollback rehearsal",
                    "Use staged rollout with acceptance criteria, test evidence, ownership, and least-privilege controls",
                    "Postpone controls and tune only after recurring incidents appear in production",
                    "Collapse critical and non-critical workloads into one component to simplify maintenance",
                ],
                "answer": 1,
                "rationale": (
                    "A staged plan with measurable controls and validated rollback provides safe delivery with audit-ready evidence."
                ),
                "why_not": [
                    "Uncontrolled changes increase long-term incident probability and audit exposure.",
                    "Postponed controls create unmanaged architecture debt and unstable operations.",
                    "High-risk consolidation increases blast radius and weakens fault isolation.",
                ],
                "domain": domain,
                "evaluation_checklist": [
                    "Risk reduction is measurable with service-level indicators.",
                    "Security controls are explicit and testable.",
                    "Operational rollback path is documented and rehearsed.",
                    "Runbooks define ownership and escalation for incident scenarios.",
                ],
            }
        )

    return questions


def _seed_exam_ready_catalog(force: bool = False) -> dict:
    from ..models.e_learning import (
        ELearningSubject,
        ELearningModule,
        ELearningLesson,
        ELearningExercise,
    )

    stats = {"subjects": 0, "modules": 0, "lessons": 0, "exercises": 0}

    for subject_code, blueprint in EXAM_BLUEPRINT_BY_SUBJECT.items():
        subject = ELearningSubject.query.filter_by(code=subject_code).first()
        if not subject:
            continue
        stats["subjects"] += 1

        modules = ELearningModule.query.filter_by(subject_id=subject.id, is_active=True).order_by(ELearningModule.order.asc()).all()
        for module in modules:
            stats["modules"] += 1
            lesson_code = f"{module.code}_exam_ready"
            lesson = ELearningLesson.query.filter_by(module_id=module.id, code=lesson_code).first()
            if not lesson:
                lesson = ELearningLesson(module_id=module.id, code=lesson_code)
                db.session.add(lesson)
            stats["lessons"] += 1

            lesson.title_i18n = _exam_title_i18n(module.title_i18n.get("en") or module.code, blueprint["track"])
            lesson.description_i18n = {
                "en": f"Certification-style assessment lab for {module.title_i18n.get('en') or module.code}.",
                "fr": f"Lab d evaluation type certification pour {module.title_i18n.get('en') or module.code}.",
                "pt": f"Certification-style assessment lab for {module.title_i18n.get('en') or module.code}.",
                "es": f"Certification-style assessment lab for {module.title_i18n.get('en') or module.code}.",
                "it": f"Certification-style assessment lab for {module.title_i18n.get('en') or module.code}.",
                "de": f"Certification-style assessment lab for {module.title_i18n.get('en') or module.code}.",
            }
            lesson.content_html_i18n = _exam_content_i18n(blueprint["track"], module.title_i18n.get("en") or module.code)
            lesson.key_concepts_i18n = {
                "en": blueprint["domains"],
                "fr": blueprint["domains"],
            }
            lesson.order = max(module.total_lessons, 1) + 1
            lesson.is_active = True
            db.session.flush()

            question_pack = _build_exam_question_pack(subject_code, module.title_i18n.get("en") or module.code)
            valid_codes = {f"{lesson_code}_{q['code']}" for q in question_pack}
            if force and valid_codes:
                stale = ELearningExercise.query.filter(
                    ELearningExercise.lesson_id == lesson.id,
                    ELearningExercise.code.notin_(valid_codes),
                ).all()
                for ex in stale:
                    db.session.delete(ex)
                if stale:
                    db.session.flush()

            for order, q in enumerate(question_pack, start=1):
                ex_code = f"{lesson_code}_{q['code']}"
                exercise = ELearningExercise.query.filter_by(lesson_id=lesson.id, code=ex_code).first()
                if not exercise:
                    exercise = ELearningExercise(lesson_id=lesson.id, code=ex_code)
                    db.session.add(exercise)
                stats["exercises"] += 1

                exercise.type = "multiple_choice"
                exercise.title_i18n = {
                    "en": q["title"],
                    "fr": q["fr_title"],
                    "pt": q["title"],
                    "es": q["title"],
                    "it": q["title"],
                    "de": q["title"],
                }
                exercise.instruction_i18n = {
                    "en": q["instruction"],
                    "fr": q["fr_instruction"],
                    "pt": q["instruction"],
                    "es": q["instruction"],
                    "it": q["instruction"],
                    "de": q["instruction"],
                }
                exercise.hint_i18n = _text_i18n(
                    "Use a decision matrix: control coverage, failure impact, rollback effort, and implementation speed.",
                    "Utilisez une matrice de decision: couverture des controles, impact d'echec, effort de rollback et vitesse d'implementation.",
                )
                exercise.points = q["points"]
                exercise.order = order
                exercise.is_active = True
                exercise.expected_sql = None
                exercise.expected_result_json = {
                    "question": q["question"],
                    "choices": q["choices"],
                    "correct_choice_index": q["answer"],
                    "rationale": q["rationale"],
                    "why_not": q["why_not"],
                    "domain": q["domain"],
                    "track": blueprint["track"],
                    "evaluation_checklist": q["evaluation_checklist"],
                }
                exercise.validation_query = None
                exercise.passing_condition = None
                exercise.dml_operation = None
                db.session.flush()

            module.total_lessons = ELearningLesson.query.filter_by(module_id=module.id).count()
            module.total_exercises = db.session.query(ELearningExercise).join(
                ELearningLesson, ELearningExercise.lesson_id == ELearningLesson.id
            ).filter(ELearningLesson.module_id == module.id).count()

    db.session.commit()
    return stats


def _repair_non_sql_exercises() -> int:
    """Repair legacy exercises where non-SQL subjects still use SQL exercise types."""
    from ..models.e_learning import ELearningExercise, ELearningLesson, ELearningModule, ELearningSubject

    repaired = 0
    broken = (
        db.session.query(ELearningExercise)
        .join(ELearningLesson, ELearningExercise.lesson_id == ELearningLesson.id)
        .join(ELearningModule, ELearningLesson.module_id == ELearningModule.id)
        .join(ELearningSubject, ELearningModule.subject_id == ELearningSubject.id)
        .filter(ELearningSubject.code != "sql")
        .filter(ELearningExercise.type.in_(["sql_query", "sql_dml"]))
        .all()
    )

    for exercise in broken:
        module = exercise.lesson.module if exercise.lesson else None
        subject_code = (module.subject.code or "") if module and module.subject else ""
        payload = exercise.expected_result_json or {}
        has_choice_payload = isinstance(payload, dict) and "correct_choice_index" in payload

        if has_choice_payload:
            exercise.type = "multiple_choice"
            exercise.expected_sql = None
            exercise.validation_query = None
            exercise.passing_condition = None
            exercise.dml_operation = None
        elif "python" in subject_code or subject_code.startswith("django-"):
            exercise.type = "code_challenge"
            if not exercise.expected_sql:
                exercise.expected_sql = "# Write your Python solution here"
            exercise.validation_query = None
            exercise.passing_condition = None
            exercise.dml_operation = None
        else:
            exercise.type = "multiple_choice"
            question = (
                (exercise.instruction_i18n or {}).get("en")
                or (exercise.title_i18n or {}).get("en")
                or "Select the best answer for this lesson objective."
            )
            exercise.expected_sql = None
            exercise.validation_query = None
            exercise.passing_condition = None
            exercise.dml_operation = None
            exercise.expected_result_json = {
                "question": question,
                "choices": [
                    "Apply the lesson objective with explicit checks and measurable outcomes.",
                    "Skip verification and rely only on assumptions.",
                    "Ignore constraints and choose the fastest shortcut.",
                    "Delay feedback and validation until after release.",
                ],
                "correct_choice_index": 0,
                "rationale": "The best answer is the one aligned with the lesson objective and validated decisions.",
                "why_not": [
                    "Unverified assumptions increase error risk.",
                    "Ignoring constraints breaks reliability and quality.",
                    "Delayed validation creates avoidable regressions.",
                ],
            }

        repaired += 1

    if repaired:
        db.session.commit()

    return repaired


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

    @app.cli.command("seed-e-learning-sqlite-local")
    @click.option(
        "--path",
        "db_path",
        default="instance/e_learning_seed_test.sqlite3",
        show_default=True,
        help="Output SQLite/DBLite file path (for example: instance/test.seed.dblite)",
    )
    @click.option("--force", is_flag=True, default=False, help="Overwrite existing SQLite file")
    def seed_e_learning_sqlite_local(db_path: str, force: bool):
        """Create a local SQLite/DBLite database seeded for e-learning testing."""
        click.echo("🧪 Seeding local SQLite test database...")
        result = _seed_local_sqlite_file(db_path=db_path, force=force)

        click.echo(f"  ✅ SQLite file: {result['path']}")
        for table_name, total in result["counts"].items():
            click.echo(f"  ✅ {table_name}: {total} rows")
        click.echo("\nDone. You can use this file for local SQL testing and demos.")

    @app.cli.command("seed-e-learning-premium")
    @click.option("--force", is_flag=True, default=False, help="Re-seed premium records")
    def seed_e_learning_premium(force: bool):
        """Seed premium multi-track catalog: programming logic, AWS, GCP, Azure, and Generative AI."""
        click.echo("🎯 Seeding premium E-Learning catalog...")

        stats = _seed_premium_catalog(force=force)
        click.echo(f"  ✅ Subjects: {stats['subjects']} created")
        click.echo(f"  ✅ Modules: {stats['modules']} created/updated")
        click.echo(f"  ✅ Lessons: {stats['lessons']} created/updated")
        click.echo(f"  ✅ Exercises: {stats['exercises']} created/updated")
        click.echo(f"  ✅ Quizzes: {stats['quizzes']} created/updated")
        click.echo(f"  ✅ Quiz questions: {stats['questions']} created/updated")
        repaired = _repair_non_sql_exercises()
        click.echo(f"  ✅ Legacy exercise repairs: {repaired}")

        click.echo("\n🚀 Done! Premium tracks are available in /e-learning/.")

    @app.cli.command("seed-e-learning-exam-ready")
    @click.option("--force", is_flag=True, default=False, help="Re-seed exam-ready records")
    def seed_e_learning_exam_ready(force: bool):
        """Seed certification-oriented quiz banks for premium tracks."""
        click.echo("🧠 Seeding exam-ready quiz banks...")

        stats = _seed_exam_ready_catalog(force=force)
        click.echo(f"  ✅ Subjects covered: {stats['subjects']}")
        click.echo(f"  ✅ Modules covered: {stats['modules']}")
        click.echo(f"  ✅ Exam lessons created/updated: {stats['lessons']}")
        click.echo(f"  ✅ Certification quizzes created/updated: {stats['exercises']}")
        repaired = _repair_non_sql_exercises()
        click.echo(f"  ✅ Legacy exercise repairs: {repaired}")

        click.echo("\n🚀 Done! Exam-ready content is available in /e-learning/.")

    @app.cli.command("repair-e-learning-exercises")
    def repair_e_learning_exercises():
        """Repair legacy non-SQL exercises incorrectly configured as SQL tasks."""
        repaired = _repair_non_sql_exercises()
        click.echo(f"🛠️ Repaired exercises: {repaired}")

        click.echo("\n🚀 Done! Exercise types are now aligned to their subjects.")

    @app.cli.command("seed-e-learning-mega-pack")
    @click.option("--force", is_flag=True, default=False, help="Re-seed all records")
    def seed_e_learning_mega_pack(force: bool):
        """Run all e-learning seeds: base SQL, premium catalog, and exam-ready quizzes."""
        click.echo("📦 Seeding full E-Learning mega pack...")

        ach_count = _seed_achievements(force=force)
        sql_stats = _seed_sql_subject(force=force)
        premium_stats = _seed_premium_catalog(force=force)
        exam_stats = _seed_exam_ready_catalog(force=force)
        repaired = _repair_non_sql_exercises()

        click.echo("\nBase SQL track:")
        click.echo(f"  ✅ Achievements: {ach_count} created/updated")
        click.echo(f"  ✅ Subjects: {sql_stats['subjects']} created/updated")
        click.echo(f"  ✅ Modules: {sql_stats['modules']} created/updated")
        click.echo(f"  ✅ Lessons: {sql_stats['lessons']} created/updated")
        click.echo(f"  ✅ Exercises: {sql_stats['exercises']} created/updated")

        click.echo("\nPremium tracks:")
        click.echo(f"  ✅ Subjects: {premium_stats['subjects']} created/updated")
        click.echo(f"  ✅ Modules: {premium_stats['modules']} created/updated")
        click.echo(f"  ✅ Lessons: {premium_stats['lessons']} created/updated")
        click.echo(f"  ✅ Exercises: {premium_stats['exercises']} created/updated")
        click.echo(f"  ✅ Quizzes: {premium_stats['quizzes']} created/updated")
        click.echo(f"  ✅ Quiz questions: {premium_stats['questions']} created/updated")

        click.echo("\nExam-ready quizzes:")
        click.echo(f"  ✅ Subjects covered: {exam_stats['subjects']}")
        click.echo(f"  ✅ Modules covered: {exam_stats['modules']}")
        click.echo(f"  ✅ Exam lessons created/updated: {exam_stats['lessons']}")
        click.echo(f"  ✅ Certification quizzes created/updated: {exam_stats['exercises']}")
        click.echo(f"  ✅ Legacy exercise repairs: {repaired}")

        click.echo("\n🚀 Mega pack complete! Browse /e-learning/ for full catalog.")
