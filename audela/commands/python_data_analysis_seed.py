"""
Seed command for the Python Data Analysis professional course.

Provides: subject, 10 modules, 2 lessons each, 2 exercises per lesson,
and 1 quiz per lesson (5 multiple-choice questions each).
"""
from __future__ import annotations

import click
from flask import Flask

from ..extensions import db


# ---------------------------------------------------------------------------
# Subject
# ---------------------------------------------------------------------------

PDA_SUBJECT = {
    "code": "python-data-analysis",
    "name_i18n": {
        "en": "Python Data Analysis — Professional Course",
        "fr": "Analyse de Données Python — Cours Professionnel",
        "pt": "Análise de Dados com Python — Curso Profissional",
        "es": "Análisis de Datos con Python — Curso Profesional",
        "it": "Analisi dei Dati con Python — Corso Professionale",
        "de": "Python-Datenanalyse — Professioneller Kurs",
    },
    "description_i18n": {
        "en": "10-module professional course: NumPy, Pandas, Matplotlib, statistical analysis, machine-learning pipelines, and real-world capstone projects.",
        "fr": "Cours professionnel en 10 modules : NumPy, Pandas, Matplotlib, analyse statistique, pipelines ML et projets concrets.",
        "pt": "Curso profissional em 10 módulos: NumPy, Pandas, Matplotlib, análise estatística, pipelines de ML e projetos reais.",
        "es": "Curso profesional de 10 módulos: NumPy, Pandas, Matplotlib, análisis estadístico, pipelines ML y proyectos reales.",
        "it": "Corso professionale in 10 moduli: NumPy, Pandas, Matplotlib, analisi statistica, pipeline ML e progetti reali.",
        "de": "Professioneller Kurs in 10 Modulen: NumPy, Pandas, Matplotlib, statistische Analyse, ML-Pipelines und Praxisprojekte.",
    },
    "icon": "analytics",
    "color": "#3776ab",
    "is_active": True,
    "sort_order": 2,
}

# ---------------------------------------------------------------------------
# Course blueprint
# ---------------------------------------------------------------------------

BLUEPRINT = [
    # ---- Module 1 --------------------------------------------------------
    {
        "code": "pda101",
        "title": "Module 1 – Python Foundations for Data Analysis",
        "level": "beginner",
        "minutes": 75,
        "concepts": ["Python data types", "Lists, tuples, dicts", "List comprehensions",
                     "Functions & lambdas", "File I/O (CSV / JSON)", "Error handling"],
        "practical": ["Parse a CSV file manually", "Build a word-frequency counter",
                      "Compute descriptive stats from a list"],
        "mini_project": "Lightweight data pipeline (CSV → dict → summary)",
        "image_url": "https://images.unsplash.com/photo-1515879218367-8466d910aaa4?auto=format&fit=crop&w=1200&q=80",
        "exercise_code": [
            "data = [10,20,30,40,50]\nprint(sum(data)/len(data))  # mean",
            "import csv\nwith open('sales.csv') as f:\n    rows = list(csv.DictReader(f))\nprint(rows[:3])",
        ],
        "quiz_questions": [
            {
                "text_i18n": {"en": "Which built-in function returns the number of items in a list?"},
                "options": [("count()", False), ("len()", True), ("size()", False), ("length()", False)],
                "explanation_i18n": {"en": "`len()` returns the number of elements in any sequence."},
            },
            {
                "text_i18n": {"en": "What does a list comprehension like `[x**2 for x in range(5)]` produce?"},
                "options": [("[0,1,4,9,16]", True), ("[1,4,9,16,25]", False), ("[0,1,2,3,4]", False), ("A generator", False)],
                "explanation_i18n": {"en": "It squares each integer from 0 to 4 inclusive."},
            },
            {
                "text_i18n": {"en": "Which mode opens a file for reading in Python?"},
                "options": [("'w'", False), ("'a'", False), ("'r'", True), ("'x'", False)],
                "explanation_i18n": {"en": "'r' is the default read mode."},
            },
            {
                "text_i18n": {"en": "What keyword is used to handle exceptions in Python?"},
                "options": [("catch", False), ("except", True), ("rescue", False), ("error", False)],
                "explanation_i18n": {"en": "Python uses `try / except` blocks."},
            },
            {
                "text_i18n": {"en": "A lambda function can contain:"},
                "options": [("Multiple statements", False), ("Only a single expression", True),
                            ("Loops only", False), ("No return value", False)],
                "explanation_i18n": {"en": "Lambda expressions are limited to a single expression."},
            },
        ],
    },
    # ---- Module 2 --------------------------------------------------------
    {
        "code": "pda102",
        "title": "Module 2 – NumPy for Numerical Computing",
        "level": "beginner",
        "minutes": 80,
        "concepts": ["ndarray creation", "Indexing & slicing", "Vectorised operations",
                     "Broadcasting", "Linear algebra basics", "Random number generation"],
        "practical": ["Compute matrix multiplication", "Generate synthetic sales data",
                      "Benchmark loop vs vectorised operation"],
        "mini_project": "Monte-Carlo π estimation",
        "image_url": "https://images.unsplash.com/photo-1509228468518-180dd4864904?auto=format&fit=crop&w=1200&q=80",
        "exercise_code": [
            "import numpy as np\na = np.array([1,2,3,4])\nprint(a * 2)  # vectorised",
            "import numpy as np\nnp.random.seed(42)\nsamples = np.random.rand(1000)\nprint(samples.mean())",
        ],
        "quiz_questions": [
            {
                "text_i18n": {"en": "What does `np.zeros((3, 4))` return?"},
                "options": [("A 3×4 matrix of zeros", True), ("A list of 3 zeros", False),
                            ("A 4×3 matrix of ones", False), ("An identity matrix", False)],
                "explanation_i18n": {"en": "It creates a 2D array with shape (3,4) filled with 0.0."},
            },
            {
                "text_i18n": {"en": "NumPy broadcasting allows operations between arrays of:"},
                "options": [("Only identical shapes", False), ("Compatible shapes according to broadcasting rules", True),
                            ("Only 1-D arrays", False), ("Lists only", False)],
                "explanation_i18n": {"en": "Broadcasting extends smaller arrays to match larger ones along compatible dimensions."},
            },
            {
                "text_i18n": {"en": "Which function computes the dot product of two arrays?"},
                "options": [("np.cross()", False), ("np.dot()", True), ("np.mul()", False), ("np.sum()", False)],
                "explanation_i18n": {"en": "np.dot() computes matrix / dot product."},
            },
            {
                "text_i18n": {"en": "What is the dtype of `np.array([1, 2, 3])`?"},
                "options": [("float64", False), ("int64", True), ("object", False), ("complex", False)],
                "explanation_i18n": {"en": "Integer literals produce an int64 array by default."},
            },
            {
                "text_i18n": {"en": "How do you select every other element from a NumPy array `a`?"},
                "options": [("a[::2]", True), ("a[0:2]", False), ("a.every(2)", False), ("a[2:]", False)],
                "explanation_i18n": {"en": "Slice notation a[::2] steps by 2."},
            },
        ],
    },
    # ---- Module 3 --------------------------------------------------------
    {
        "code": "pda103",
        "title": "Module 3 – Pandas: Data Wrangling",
        "level": "beginner",
        "minutes": 90,
        "concepts": ["Series & DataFrame", "Reading CSV/Excel/JSON", "Indexing (loc/iloc)",
                     "Filtering & boolean masks", "Missing data (dropna/fillna)", "Sorting & ranking"],
        "practical": ["Clean a messy HR dataset", "Filter top-10 customers by revenue",
                      "Detect and impute missing prices"],
        "mini_project": "E-commerce data cleaning pipeline",
        "image_url": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=1200&q=80",
        "exercise_code": [
            "import pandas as pd\ndf = pd.read_csv('sales.csv')\nprint(df.info())\nprint(df.describe())",
            "import pandas as pd\ndf = pd.read_csv('sales.csv')\ntop = df[df['amount'] > 500].sort_values('amount', ascending=False)\nprint(top.head(10))",
        ],
        "quiz_questions": [
            {
                "text_i18n": {"en": "Which Pandas method returns the first n rows of a DataFrame?"},
                "options": [("df.start(n)", False), ("df.head(n)", True), ("df.first(n)", False), ("df.top(n)", False)],
                "explanation_i18n": {"en": "df.head(n) returns the first n rows (default 5)."},
            },
            {
                "text_i18n": {"en": "How do you select rows where column 'age' > 30?"},
                "options": [("df.filter(age > 30)", False), ("df[df['age'] > 30]", True),
                            ("df.where('age > 30')", False), ("df.select(age > 30)", False)],
                "explanation_i18n": {"en": "Boolean indexing with df[condition] is the standard approach."},
            },
            {
                "text_i18n": {"en": "What does `df.fillna(0)` do?"},
                "options": [("Drops all NaN rows", False), ("Replaces NaN with 0", True),
                            ("Fills zeros with NaN", False), ("Removes zero values", False)],
                "explanation_i18n": {"en": "fillna replaces missing values with the specified scalar."},
            },
            {
                "text_i18n": {"en": "Which parameter in `pd.read_csv()` specifies the column separator?"},
                "options": [("delimiter", False), ("sep", True), ("split", False), ("col_sep", False)],
                "explanation_i18n": {"en": "sep= (or its alias delimiter=) sets the field separator."},
            },
            {
                "text_i18n": {"en": "df.iloc[2, 3] selects:"},
                "options": [("Row labeled '2', column labeled '3'", False),
                            ("Row at position 2, column at position 3", True),
                            ("Row at position 3, column at position 2", False),
                            ("Column named '2' in row '3'", False)],
                "explanation_i18n": {"en": "iloc uses integer-based positional indexing."},
            },
        ],
    },
    # ---- Module 4 --------------------------------------------------------
    {
        "code": "pda104",
        "title": "Module 4 – Pandas: Aggregation & GroupBy",
        "level": "beginner",
        "minutes": 85,
        "concepts": ["groupby()", "agg() & named aggregations", "pivot_table()",
                     "crosstab()", "apply()", "transform()"],
        "practical": ["Revenue by product category", "Monthly sales trend table",
                      "Customer cohort pivot by region"],
        "mini_project": "Sales performance dashboard queries",
        "image_url": "https://images.unsplash.com/photo-1543286386-713bdd548da4?auto=format&fit=crop&w=1200&q=80",
        "exercise_code": [
            "import pandas as pd\ndf = pd.read_csv('sales.csv')\nrevenue = df.groupby('category')['amount'].sum().sort_values(ascending=False)\nprint(revenue)",
            "import pandas as pd\ndf = pd.read_csv('sales.csv')\ntable = pd.pivot_table(df, values='amount', index='region', columns='product', aggfunc='sum', fill_value=0)\nprint(table)",
        ],
        "quiz_questions": [
            {
                "text_i18n": {"en": "What does `df.groupby('col').mean()` return?"},
                "options": [("A scalar mean of the whole DataFrame", False),
                            ("A DataFrame with mean per group", True),
                            ("A list of group keys", False),
                            ("An error if col has NaN", False)],
                "explanation_i18n": {"en": "groupby + mean aggregates each column per group."},
            },
            {
                "text_i18n": {"en": "Which Pandas function creates a spreadsheet-style pivot table?"},
                "options": [("pd.groupby()", False), ("pd.pivot_table()", True),
                            ("pd.crosstab()", False), ("pd.melt()", False)],
                "explanation_i18n": {"en": "pd.pivot_table() provides Excel-style pivot functionality."},
            },
            {
                "text_i18n": {"en": "What is the difference between `agg()` and `transform()`?"},
                "options": [("No difference", False),
                            ("agg reduces to a scalar per group; transform returns same-length result", True),
                            ("transform reduces; agg keeps original length", False),
                            ("Both always return a scalar", False)],
                "explanation_i18n": {"en": "agg collapses groups; transform broadcasts the result back to the original index."},
            },
            {
                "text_i18n": {"en": "How do you compute multiple aggregations at once in groupby?"},
                "options": [("df.groupby('g').multi()", False),
                            ("df.groupby('g')['col'].agg(['mean','sum'])", True),
                            ("df.groupby('g').aggregate_all()", False),
                            ("df.groupby('g').pivot()", False)],
                "explanation_i18n": {"en": "Passing a list to .agg() computes multiple statistics."},
            },
            {
                "text_i18n": {"en": "`df.apply(func)` applies func:"},
                "options": [("Element-wise to each cell", False),
                            ("To each column (or row) as a Series", True),
                            ("Only to numeric columns", False),
                            ("Only to the index", False)],
                "explanation_i18n": {"en": "By default apply passes each column as a Series; use axis=1 for rows."},
            },
        ],
    },
    # ---- Module 5 --------------------------------------------------------
    {
        "code": "pda105",
        "title": "Module 5 – Data Visualisation with Matplotlib & Seaborn",
        "level": "intermediate",
        "minutes": 90,
        "concepts": ["Figure & Axes API", "Line, bar, scatter, histogram",
                     "Seaborn statistical plots", "Colour palettes & themes",
                     "Subplots & layouts", "Saving figures"],
        "practical": ["Plot monthly revenue trend", "Correlation heatmap of features",
                      "Distribution plots for outlier detection"],
        "mini_project": "Executive KPI visual report (multi-panel figure)",
        "image_url": "https://images.unsplash.com/photo-1512314889357-e157c22f938d?auto=format&fit=crop&w=1200&q=80",
        "exercise_code": [
            "import matplotlib.pyplot as plt\nfig, ax = plt.subplots()\nax.bar(['Q1','Q2','Q3','Q4'], [120000,145000,132000,168000])\nax.set_title('Quarterly Revenue')\nplt.tight_layout()\nplt.savefig('revenue.png', dpi=150)",
            "import seaborn as sns, pandas as pd\ndf = pd.read_csv('sales.csv')\nsns.heatmap(df.corr(numeric_only=True), annot=True, cmap='coolwarm')",
        ],
        "quiz_questions": [
            {
                "text_i18n": {"en": "In Matplotlib, what does `plt.subplots(2, 3)` return?"},
                "options": [("A single Figure", False),
                            ("A Figure and a 2×3 array of Axes", True),
                            ("Six separate figures", False),
                            ("A 3×2 array of Axes only", False)],
                "explanation_i18n": {"en": "plt.subplots(nrows, ncols) returns (fig, axes_array)."},
            },
            {
                "text_i18n": {"en": "Which Seaborn function provides a combined scatter + marginal distribution plot?"},
                "options": [("sns.scatterplot()", False), ("sns.jointplot()", True),
                            ("sns.catplot()", False), ("sns.pairplot()", False)],
                "explanation_i18n": {"en": "sns.jointplot() shows the joint distribution with marginals."},
            },
            {
                "text_i18n": {"en": "How do you save a Matplotlib figure as a high-resolution PNG?"},
                "options": [("fig.export('file.png')", False), ("plt.savefig('file.png', dpi=300)", True),
                            ("plt.save('file.png')", False), ("fig.write_image('file.png')", False)],
                "explanation_i18n": {"en": "plt.savefig() (or fig.savefig()) accepts dpi parameter."},
            },
            {
                "text_i18n": {"en": "What does `sns.heatmap(df.corr())` visualise?"},
                "options": [("Raw data values", False), ("Pairwise correlations between numeric columns", True),
                            ("Missing value patterns", False), ("Category counts", False)],
                "explanation_i18n": {"en": "df.corr() computes the Pearson correlation matrix, which the heatmap renders."},
            },
            {
                "text_i18n": {"en": "The OOP Matplotlib interface uses `ax.plot()` instead of `plt.plot()` because:"},
                "options": [("It is faster", False),
                            ("It explicitly targets a specific Axes object, enabling multi-panel control", True),
                            ("plt.plot() is deprecated", False),
                            ("There is no functional difference", False)],
                "explanation_i18n": {"en": "The Axes-based API avoids ambiguity in figures with multiple subplots."},
            },
        ],
    },
    # ---- Module 6 --------------------------------------------------------
    {
        "code": "pda106",
        "title": "Module 6 – Exploratory Data Analysis (EDA)",
        "level": "intermediate",
        "minutes": 95,
        "concepts": ["Distribution analysis", "Outlier detection (IQR, Z-score)",
                     "Feature correlations", "Categorical profiling",
                     "Automated EDA (ydata-profiling)", "EDA storytelling"],
        "practical": ["Full EDA on a retail dataset", "Outlier report with boxplots",
                      "Correlation-driven feature selection"],
        "mini_project": "Insurance risk EDA report",
        "image_url": "https://images.unsplash.com/photo-1488229297570-58520851e868?auto=format&fit=crop&w=1200&q=80",
        "exercise_code": [
            "import pandas as pd\ndf = pd.read_csv('insurance.csv')\nprint(df.describe())\nprint(df.isnull().sum())\nprint(df.dtypes)",
            "import pandas as pd\ndf = pd.read_csv('insurance.csv')\nQ1 = df['charges'].quantile(0.25)\nQ3 = df['charges'].quantile(0.75)\nIQR = Q3 - Q1\noutliers = df[(df['charges'] < Q1 - 1.5*IQR) | (df['charges'] > Q3 + 1.5*IQR)]\nprint(f'{len(outliers)} outliers detected')",
        ],
        "quiz_questions": [
            {
                "text_i18n": {"en": "The IQR (Inter-Quartile Range) is defined as:"},
                "options": [("Q3 – Q1", True), ("Q2 – Q1", False), ("max – min", False), ("mean – median", False)],
                "explanation_i18n": {"en": "IQR = Q3 − Q1, the range of the middle 50% of data."},
            },
            {
                "text_i18n": {"en": "A Z-score greater than 3 typically indicates:"},
                "options": [("A normal observation", False), ("A potential outlier", True),
                            ("A missing value", False), ("A categorical anomaly", False)],
                "explanation_i18n": {"en": "Values beyond ±3 standard deviations are conventionally flagged as outliers."},
            },
            {
                "text_i18n": {"en": "Which Pandas method gives a summary of NaN counts per column?"},
                "options": [("df.nan_count()", False), ("df.isnull().sum()", True),
                            ("df.count_na()", False), ("df.missing()", False)],
                "explanation_i18n": {"en": "df.isnull() returns a boolean mask; .sum() counts Trues per column."},
            },
            {
                "text_i18n": {"en": "Pearson correlation measures:"},
                "options": [("Causal relationship", False), ("Linear relationship between two variables", True),
                            ("Non-linear dependence", False), ("Rank-based association", False)],
                "explanation_i18n": {"en": "Pearson r measures linear correlation; Spearman measures rank correlation."},
            },
            {
                "text_i18n": {"en": "What does a skewness value > 1 imply about a distribution?"},
                "options": [("It is symmetric", False), ("It has a long right tail (positively skewed)", True),
                            ("It has a long left tail (negatively skewed)", False), ("It is bimodal", False)],
                "explanation_i18n": {"en": "Positive skewness means the right tail is longer."},
            },
        ],
    },
    # ---- Module 7 --------------------------------------------------------
    {
        "code": "pda107",
        "title": "Module 7 – Statistical Analysis with SciPy",
        "level": "intermediate",
        "minutes": 90,
        "concepts": ["Descriptive statistics", "Hypothesis testing (t-test, chi-square)",
                     "Confidence intervals", "ANOVA", "Non-parametric tests",
                     "p-value interpretation"],
        "practical": ["A/B test significance calculator", "Chi-square test on survey data",
                      "One-way ANOVA on sales by region"],
        "mini_project": "Marketing campaign A/B test analysis",
        "image_url": "https://images.unsplash.com/photo-1434030216411-0b793f4b4173?auto=format&fit=crop&w=1200&q=80",
        "exercise_code": [
            "from scipy import stats\ngroup_a = [45,52,49,61,55]\ngroup_b = [50,58,62,57,65]\nt, p = stats.ttest_ind(group_a, group_b)\nprint(f't={t:.3f}, p={p:.3f}')",
            "import scipy.stats as stats\ncontingency = [[30,10],[20,40]]\nchi2, p, dof, expected = stats.chi2_contingency(contingency)\nprint(f'chi2={chi2:.3f}, p={p:.3f}, dof={dof}')",
        ],
        "quiz_questions": [
            {
                "text_i18n": {"en": "A p-value of 0.03 with α=0.05 means:"},
                "options": [("Fail to reject the null hypothesis", False),
                            ("Reject the null hypothesis", True),
                            ("The effect size is large", False),
                            ("The test is inconclusive", False)],
                "explanation_i18n": {"en": "p < α (0.03 < 0.05) leads to rejecting H₀."},
            },
            {
                "text_i18n": {"en": "Which SciPy function performs a two-sample independent t-test?"},
                "options": [("stats.ttest_rel()", False), ("stats.ttest_ind()", True),
                            ("stats.mannwhitneyu()", False), ("stats.f_oneway()", False)],
                "explanation_i18n": {"en": "ttest_ind tests equality of means for two independent samples."},
            },
            {
                "text_i18n": {"en": "The chi-square test of independence is used for:"},
                "options": [("Comparing two means", False),
                            ("Testing association between two categorical variables", True),
                            ("Comparing three or more means", False),
                            ("Testing normality", False)],
                "explanation_i18n": {"en": "Chi-square tests whether two categorical variables are independent."},
            },
            {
                "text_i18n": {"en": "One-way ANOVA tests:"},
                "options": [("Whether two samples have equal variance", False),
                            ("Whether means of 3+ groups are all equal", True),
                            ("Whether a variable is normally distributed", False),
                            ("Whether two categorical variables are related", False)],
                "explanation_i18n": {"en": "ANOVA (Analysis of Variance) compares means across multiple groups."},
            },
            {
                "text_i18n": {"en": "A 95% confidence interval means:"},
                "options": [("95% of data falls inside the interval", False),
                            ("If we repeat the procedure many times, 95% of such intervals contain the true parameter", True),
                            ("p-value is 0.95", False),
                            ("The null hypothesis is true with 95% probability", False)],
                "explanation_i18n": {"en": "Confidence intervals are a frequentist concept about long-run coverage."},
            },
        ],
    },
    # ---- Module 8 --------------------------------------------------------
    {
        "code": "pda108",
        "title": "Module 8 – Machine Learning with Scikit-Learn",
        "level": "intermediate",
        "minutes": 120,
        "concepts": ["Supervised vs unsupervised learning", "Train/test split & cross-validation",
                     "Linear & logistic regression", "Decision trees & random forests",
                     "Evaluation metrics (accuracy, AUC, RMSE)",
                     "Pipelines & preprocessing with ColumnTransformer"],
        "practical": ["Churn prediction model", "House price regression",
                      "Model comparison with cross-validation"],
        "mini_project": "End-to-end credit-risk classifier with Pipeline",
        "image_url": "https://images.unsplash.com/photo-1526628953301-3e589a6a8b74?auto=format&fit=crop&w=1200&q=80",
        "exercise_code": [
            "from sklearn.model_selection import train_test_split\nfrom sklearn.ensemble import RandomForestClassifier\nfrom sklearn.metrics import classification_report\nimport pandas as pd\n\ndf = pd.read_csv('churn.csv')\nX = df.drop('churn', axis=1)\ny = df['churn']\nX_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)\nclf = RandomForestClassifier(n_estimators=100, random_state=42)\nclf.fit(X_train, y_train)\nprint(classification_report(y_test, clf.predict(X_test)))",
            "from sklearn.pipeline import Pipeline\nfrom sklearn.preprocessing import StandardScaler\nfrom sklearn.linear_model import LogisticRegression\npipe = Pipeline([('scaler', StandardScaler()), ('model', LogisticRegression())])\npipe.fit(X_train, y_train)\nprint(f'Accuracy: {pipe.score(X_test, y_test):.3f}')",
        ],
        "quiz_questions": [
            {
                "text_i18n": {"en": "What is the purpose of train_test_split?"},
                "options": [("Normalise features", False),
                            ("Partition data to evaluate model generalisation", True),
                            ("Remove outliers", False),
                            ("Select important features", False)],
                "explanation_i18n": {"en": "Holding out test data prevents overfitting evaluation."},
            },
            {
                "text_i18n": {"en": "ROC-AUC measures:"},
                "options": [("Accuracy on the training set", False),
                            ("Classifier's ability to discriminate between classes across thresholds", True),
                            ("Mean squared error", False),
                            ("Precision only", False)],
                "explanation_i18n": {"en": "AUC of the ROC curve summarises classification performance across all thresholds."},
            },
            {
                "text_i18n": {"en": "Which Scikit-Learn class chains preprocessing and a model into one object?"},
                "options": [("ModelChain", False), ("Pipeline", True),
                            ("FeatureUnion", False), ("Transformer", False)],
                "explanation_i18n": {"en": "sklearn.pipeline.Pipeline assembles steps sequentially."},
            },
            {
                "text_i18n": {"en": "Cross-validation with cv=5 will:"},
                "options": [("Train 5 different models on entirely separate datasets", False),
                            ("Split data into 5 folds and evaluate on each fold in turn", True),
                            ("Train on 5% of the data", False),
                            ("Repeat training 5 times with the same split", False)],
                "explanation_i18n": {"en": "k-fold CV rotates the validation fold k times for a robust estimate."},
            },
            {
                "text_i18n": {"en": "RMSE (Root Mean Squared Error) is preferred over MAE when:"},
                "options": [("All errors should be treated equally", False),
                            ("Large errors should be penalised more heavily", True),
                            ("The target is categorical", False),
                            ("The model is a classifier", False)],
                "explanation_i18n": {"en": "Squaring errors amplifies larger residuals, hence RMSE penalises them more."},
            },
        ],
    },
    # ---- Module 9 --------------------------------------------------------
    {
        "code": "pda109",
        "title": "Module 9 – Time-Series Analysis",
        "level": "advanced",
        "minutes": 100,
        "concepts": ["DatetimeIndex & resampling", "Rolling & expanding windows",
                     "Trend and seasonality decomposition", "ACF & PACF plots",
                     "ARIMA forecasting", "Forecasting evaluation (MAPE, MAE)"],
        "practical": ["Resample daily sales to weekly", "Decompose electricity consumption",
                      "Fit ARIMA to stock prices"],
        "mini_project": "Retail demand forecasting model",
        "image_url": "https://images.unsplash.com/photo-1531297484001-80022131f5a1?auto=format&fit=crop&w=1200&q=80",
        "exercise_code": [
            "import pandas as pd\ndf = pd.read_csv('sales.csv', parse_dates=['date'], index_col='date')\nweekly = df['revenue'].resample('W').sum()\nprint(weekly.tail())",
            "from statsmodels.tsa.seasonal import seasonal_decompose\nimport pandas as pd\ndf = pd.read_csv('energy.csv', parse_dates=['date'], index_col='date')\nresult = seasonal_decompose(df['consumption'], model='additive', period=12)\nresult.plot()",
        ],
        "quiz_questions": [
            {
                "text_i18n": {"en": "Which Pandas method up/downsamples a time-series to a different frequency?"},
                "options": [("df.resample()", True), ("df.rolling()", False),
                            ("df.shift()", False), ("df.diff()", False)],
                "explanation_i18n": {"en": "resample() changes the observation frequency; rolling() computes moving windows."},
            },
            {
                "text_i18n": {"en": "ARIMA(p, d, q) — what does 'd' represent?"},
                "options": [("Degree of autoregression", False), ("Order of differencing to achieve stationarity", True),
                            ("Order of moving average", False), ("Seasonal period", False)],
                "explanation_i18n": {"en": "'d' differencing removes trends to make the series stationary."},
            },
            {
                "text_i18n": {"en": "The ACF plot is used to:"},
                "options": [("Identify autoregression order (p)", False),
                            ("Identify moving average order (q) and detect seasonality", True),
                            ("Measure prediction accuracy", False),
                            ("Decompose trend and seasonality", False)],
                "explanation_i18n": {"en": "ACF shows correlations at each lag; truncation guides the MA order."},
            },
            {
                "text_i18n": {"en": "A stationary time series has:"},
                "options": [("Increasing variance over time", False),
                            ("Constant mean and variance, and no seasonality", True),
                            ("A clear upward trend", False),
                            ("Periodically missing values", False)],
                "explanation_i18n": {"en": "Stationarity means statistical properties do not change over time."},
            },
            {
                "text_i18n": {"en": "MAPE (Mean Absolute Percentage Error) is scale-independent because:"},
                "options": [("It uses logarithms", False),
                            ("Errors are expressed as a proportion of actual values", True),
                            ("It ignores large errors", False),
                            ("It squares residuals", False)],
                "explanation_i18n": {"en": "Dividing by the actual value normalises the metric across different scales."},
            },
        ],
    },
    # ---- Module 10 -------------------------------------------------------
    {
        "code": "pda110",
        "title": "Module 10 – Capstone: End-to-End Data Analysis Project",
        "level": "advanced",
        "minutes": 150,
        "concepts": ["Project scoping & problem framing", "Data acquisition & cleaning",
                     "EDA & feature engineering", "Modelling & evaluation",
                     "Result communication (report + visuals)", "Deployment basics (Flask API)"],
        "practical": ["Define KPIs and success metrics", "Build a reproducible analysis notebook",
                      "Deliver a stakeholder-ready presentation"],
        "mini_project": "Full data analysis project: business question → insight → recommendation",
        "image_url": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1200&q=80",
        "exercise_code": [
            "# Project scaffold\nimport pandas as pd\nimport matplotlib.pyplot as plt\nfrom sklearn.pipeline import Pipeline\n\n# 1. Load\ndf = pd.read_csv('capstone_data.csv')\n# 2. EDA (summary)\nprint(df.describe())\n# 3. Clean\ndf.dropna(inplace=True)\n# 4. Feature engineering\ndf['revenue_per_unit'] = df['revenue'] / df['units']\n# 5. Visualise\ndf.groupby('category')['revenue'].sum().plot(kind='bar')\nplt.title('Revenue by Category')\nplt.tight_layout()\nplt.savefig('output/revenue_by_category.png')",
            "# Serve predictions via a minimal Flask API\nfrom flask import Flask, request, jsonify\nimport joblib\n\napp = Flask(__name__)\nmodel = joblib.load('model.pkl')\n\n@app.route('/predict', methods=['POST'])\ndef predict():\n    data = request.get_json()\n    features = [data['feature1'], data['feature2']]\n    pred = model.predict([features])[0]\n    return jsonify({'prediction': int(pred)})",
        ],
        "quiz_questions": [
            {
                "text_i18n": {"en": "The CRISP-DM framework stands for:"},
                "options": [("Cross-Industry Standard Process for Data Mining", True),
                            ("Critical Risk Inspection Standard for Data Models", False),
                            ("Comprehensive Research Integration for Statistical Data Management", False),
                            ("Cross-Indexed Statistical Process for Deep Mining", False)],
                "explanation_i18n": {"en": "CRISP-DM is the dominant end-to-end data science methodology."},
            },
            {
                "text_i18n": {"en": "Feature engineering is:"},
                "options": [("Selecting the best algorithm", False),
                            ("Creating new informative variables from raw data", True),
                            ("Tuning model hyperparameters", False),
                            ("Splitting data into train/test sets", False)],
                "explanation_i18n": {"en": "Feature engineering transforms raw inputs into representations that improve model learning."},
            },
            {
                "text_i18n": {"en": "Which Python library is commonly used to serialise (save) a trained model?"},
                "options": [("json", False), ("joblib", True), ("pickle only", False), ("csv", False)],
                "explanation_i18n": {"en": "joblib (or pickle) serialises Python objects including fitted estimators."},
            },
            {
                "text_i18n": {"en": "A confusion matrix is used to:"},
                "options": [("Visualise feature correlations", False),
                            ("Evaluate classifier performance across predicted vs actual classes", True),
                            ("Plot the learning curve", False),
                            ("Compare regression residuals", False)],
                "explanation_i18n": {"en": "A confusion matrix shows TP, TN, FP, FN counts for classifiers."},
            },
            {
                "text_i18n": {"en": "When communicating results to non-technical stakeholders, the priority should be:"},
                "options": [("Explaining model internals in detail", False),
                            ("Business impact, actionable recommendations, and visual clarity", True),
                            ("Sharing the raw notebook with all code", False),
                            ("Reporting all available accuracy metrics", False)],
                "explanation_i18n": {"en": "Effective data communication focuses on business value and clarity."},
            },
        ],
    },
]


# ---------------------------------------------------------------------------
# HTML content builder
# ---------------------------------------------------------------------------

def _build_lesson_html(mod: dict, lesson_title: str, concepts: list, practicals: list, mini_project: str, exercise_code: str) -> str:
    concept_items = "".join(f"<li><code>{c}</code></li>" for c in concepts)
    practical_rows = "".join(
        f"<tr><td>{i}</td><td>{p}</td></tr>" for i, p in enumerate(practicals, 1)
    )
    code_block = f'<pre class="bg-dark text-light p-3 rounded mt-2" style="overflow-x:auto"><code>{exercise_code}</code></pre>'
    return f"""
<div class="card border-0 shadow-sm mb-3 overflow-hidden">
  <div class="card-body">
    <h4 class="mb-2">{lesson_title}</h4>
    <p class="text-muted mb-3">Professional Python data analysis lesson with real-world code examples and hands-on exercises.</p>
    <div class="alert alert-info py-2 mb-3">
      <strong>Tip:</strong> Run each code block in a Jupyter notebook and experiment with the parameters.
    </div>
    <h5>Core Concepts</h5>
    <ul>{concept_items}</ul>
    <h5>Practical Exercises</h5>
    <table class="table table-sm table-striped">
      <thead><tr><th>#</th><th>Task</th></tr></thead>
      <tbody>{practical_rows}</tbody>
    </table>
    <h5>Code Example</h5>
    {code_block}
    <h5>Mini-Project</h5>
    <p><strong>{mini_project}</strong></p>
    <div class="alert alert-warning py-2 mt-3">
      <strong>Common pitfall:</strong> Always validate data types and check for NaN before running computations.
    </div>
  </div>
</div>
"""


# ---------------------------------------------------------------------------
# Core seeding logic
# ---------------------------------------------------------------------------

def _seed_python_subject(force: bool = False) -> dict:
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

    # ---- Subject ----------------------------------------------------------
    subject = ELearningSubject.query.filter_by(code=PDA_SUBJECT["code"]).first()
    if not subject:
        subject = ELearningSubject(
            code=PDA_SUBJECT["code"],
            name_i18n=PDA_SUBJECT["name_i18n"],
            description_i18n=PDA_SUBJECT["description_i18n"],
            icon_url=f"/static/assets/icons/{PDA_SUBJECT['icon']}.svg",
            is_active=PDA_SUBJECT["is_active"],
            order=PDA_SUBJECT["sort_order"],
        )
        db.session.add(subject)
        db.session.flush()
        stats["subjects"] += 1
    elif force:
        subject.name_i18n = PDA_SUBJECT["name_i18n"]
        subject.description_i18n = PDA_SUBJECT["description_i18n"]
        db.session.flush()

    # ---- Modules ----------------------------------------------------------
    for mod_idx, mod in enumerate(BLUEPRINT, start=1):
        module = ELearningModule.query.filter_by(subject_id=subject.id, code=mod["code"]).first()
        if not module:
            module = ELearningModule(subject_id=subject.id, code=mod["code"])
            db.session.add(module)

        lesson_count = 2
        exercise_count = lesson_count * 2
        module.title_i18n = {"en": mod["title"], "fr": mod["title"], "pt": mod["title"],
                             "es": mod["title"], "it": mod["title"], "de": mod["title"]}
        module.description_i18n = {
            "en": f"{mod['title']} — concepts, hands-on exercises, quizzes, and a mini-project.",
            "fr": f"{mod['title']} — concepts, exercices pratiques, quiz et mini-projet.",
            "pt": f"{mod['title']} — conceitos, exercícios práticos, quiz e mini-projeto.",
        }
        module.level = mod["level"]
        module.total_lessons = lesson_count
        module.total_exercises = exercise_count
        module.pass_threshold = 70
        module.points_on_completion = 50 + mod_idx * 5
        module.estimated_hours = round(mod["minutes"] / 60, 2)
        module.order = mod_idx
        module.is_active = True
        module.sample_database_schema = None
        module.sample_data_sql = None
        db.session.flush()
        stats["modules"] += 1

        # ---- Lessons (2 per module) ---------------------------------------
        for les_idx in range(1, 3):
            lesson_code = f"{mod['code']}-les{les_idx}"
            is_guided = les_idx == 1
            lesson_title = f"{mod['title']} – {'Guided Lesson' if is_guided else 'Applied Practice'}"
            lesson = ELearningLesson.query.filter_by(module_id=module.id, code=lesson_code).first()
            if not lesson:
                lesson = ELearningLesson(module_id=module.id, code=lesson_code)
                db.session.add(lesson)

            lesson.title_i18n = {"en": lesson_title, "fr": lesson_title, "pt": lesson_title,
                                 "es": lesson_title, "it": lesson_title, "de": lesson_title}
            exercise_code_snippet = mod["exercise_code"][les_idx - 1] if les_idx - 1 < len(mod["exercise_code"]) else "# practice"
            lesson.content_html_i18n = {
                "en": _build_lesson_html(
                    mod, lesson_title,
                    mod["concepts"],
                    mod["practical"],
                    mod["mini_project"],
                    exercise_code_snippet,
                )
            }
            lesson.order = les_idx
            lesson.is_active = True
            db.session.flush()
            stats["lessons"] += 1

            # ---- Exercises (2 per lesson) ---------------------------------
            for ex_idx in range(1, 3):
                ex_code = f"{mod['code']}-les{les_idx}-ex{ex_idx}"
                exercise = ELearningExercise.query.filter_by(lesson_id=lesson.id, code=ex_code).first()
                if not exercise:
                    exercise = ELearningExercise(lesson_id=lesson.id, code=ex_code)
                    db.session.add(exercise)

                ex_is_guided = ex_idx == 1
                exercise.title_i18n = {
                    "en": f"{mod['title']} – {'Core Coding Challenge' if ex_is_guided else 'Applied Analytics Challenge'}",
                }
                exercise.instruction_i18n = {
                    "en": (
                        f"Complete the Python data analysis challenge for this module using the concepts covered."
                        if ex_is_guided else
                        f"Apply the techniques from this module to a new dataset and produce the required output."
                    )
                }
                exercise.type = "code_challenge"
                exercise.points = 30 + mod_idx * 2 + ex_idx * 5
                exercise.expected_sql = mod["exercise_code"][0] if mod["exercise_code"] else ""
                exercise.hint_i18n = {
                    "en": [
                        "Import the required libraries at the top of your script.",
                        "Check data types with df.dtypes before computation.",
                    ]
                }
                exercise.order = ex_idx
                exercise.is_active = True
                db.session.flush()
                stats["exercises"] += 1

            # ---- Quiz (1 per lesson, 5 questions) ------------------------
            quiz_code = f"{mod['code']}-les{les_idx}-quiz"
            quiz = ELearningQuiz.query.filter_by(lesson_id=lesson.id, code=quiz_code).first()
            if not quiz:
                quiz = ELearningQuiz(lesson_id=lesson.id, code=quiz_code)
                db.session.add(quiz)

            quiz.title_i18n = {"en": f"{mod['title']} – Knowledge Check"}
            quiz.description_i18n = {
                "en": "Test your understanding of the key concepts from this lesson."
            }
            quiz.time_limit_minutes = 10
            quiz.pass_threshold = 70
            quiz.max_attempts = None
            quiz.shuffle_questions = True
            quiz.show_correct_answers = True
            quiz.points_on_pass = 25
            quiz.order = les_idx
            quiz.is_active = True
            db.session.flush()
            stats["quizzes"] += 1

            # Only seed quiz questions on the FIRST lesson (les_idx==1) since
            # the quiz questions are module-level knowledge; for les2 we reuse
            # the same question pool but attach to that lesson's quiz for
            # placement. In practice, seed all 5 questions per quiz.
            for q_idx, q_data in enumerate(mod["quiz_questions"], start=1):
                # Find or create question by quiz + order
                existing_q = ELearningQuizQuestion.query.filter_by(
                    quiz_id=quiz.id, order=q_idx
                ).first()
                if not existing_q:
                    existing_q = ELearningQuizQuestion(quiz_id=quiz.id)
                    db.session.add(existing_q)

                existing_q.order = q_idx
                existing_q.question_type = "multiple_choice"
                existing_q.text_i18n = q_data["text_i18n"]
                existing_q.explanation_i18n = q_data.get("explanation_i18n", {})
                existing_q.points = 1
                existing_q.allow_partial_credit = False
                existing_q.penalty_points = 0
                existing_q.is_active = True
                db.session.flush()
                stats["questions"] += 1

                # Options
                for opt_idx, (opt_text, is_correct) in enumerate(q_data["options"], start=1):
                    existing_opt = ELearningQuizOption.query.filter_by(
                        question_id=existing_q.id, order=opt_idx
                    ).first()
                    if not existing_opt:
                        existing_opt = ELearningQuizOption(question_id=existing_q.id)
                        db.session.add(existing_opt)

                    existing_opt.order = opt_idx
                    existing_opt.text_i18n = {"en": opt_text}
                    existing_opt.is_correct = is_correct
                    db.session.flush()

    db.session.commit()
    return stats


# ---------------------------------------------------------------------------
# CLI registration
# ---------------------------------------------------------------------------

def init_python_data_analysis_seed_cli(app: Flask) -> None:
    """Register Python Data Analysis seed CLI command."""

    @app.cli.command("seed-python-data-analysis")
    @click.option("--force", is_flag=True, default=False, help="Re-seed / update existing records")
    def seed_python_data_analysis(force: bool):
        """Seed the Python Data Analysis professional course (modules, lessons, exercises, quizzes)."""
        click.echo("🐍 Seeding Python Data Analysis course...")
        stats = _seed_python_subject(force=force)
        click.echo(f"  ✅ Subjects  : {stats['subjects']}")
        click.echo(f"  ✅ Modules   : {stats['modules']}")
        click.echo(f"  ✅ Lessons   : {stats['lessons']}")
        click.echo(f"  ✅ Exercises : {stats['exercises']}")
        click.echo(f"  ✅ Quizzes   : {stats['quizzes']}")
        click.echo(f"  ✅ Questions : {stats['questions']}")
        click.echo("\n🚀 Done! Visit /e-learning/ to browse the Python Data Analysis course.")
