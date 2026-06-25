# Coursework Context

Source file: `Курсач Замалетдинов правленый.docx`

Status: coursework source material for the diploma workspace. The content describes the `Normalizaciya` reference project and a server deployment that is currently not connected to this workspace.

## Topic

The coursework is titled: "Система автоматической классификации обращений граждан в социальных сетях на основе методов машинного обучения".

It studies a system for automatic multi-task classification of VK comments from Nizhny Novgorod city communities.

## Goal And Object

Goal: develop and study an automatic multi-task classifier for VK comments using `rubert-tiny2`.

Object: user comments in VK city communities.

Subject: machine learning methods for multi-task Russian-language text classification.

The classification is performed along three axes:

- sentiment/tone;
- type of appeal;
- addressee.

## Data

The dataset described in the coursework contains:

- 138,680 total records;
- 137,004 comments;
- 12,668 unique posts;
- 57 unique communities;
- 122,406 comments with post context, or 88.3%;
- 16,274 comments without post context, or 11.7%;
- average comment length: 52 characters;
- average post length: 312 characters;
- CSV size: 61.8 MB.

Data came from public VK city communities about Nizhny Novgorod and the Nizhny Novgorod region. Initial exports used `barkov.net`; post context was collected with a Selenium + headless Chrome parser because direct `requests` scraping triggered VK anti-bot protection.

The parser used random delays, periodic pauses, `navigator.webdriver` removal, image blocking, and resume support. Reported parsing time: 20 hours 27 minutes; 12,232 posts collected from 12,357 unique IDs.

## Pipeline

The coursework maps directly to the scripts in `Normalizaciya`:

- `00_fetch_posts_browser.py`: parse VK posts through Selenium;
- `01_clean_data.py`: clean and normalize raw data;
- `01b_merge_posts.py`: merge posts with comments;
- `02_auto_label.py`: automatic labeling along three axes;
- `02_labeler.py`: Flask UI for manual verification;
- `03_train_model.py`: train v1 model using comment text only;
- `03_train_model_v2.py`: train v2 model using post context + comment;
- `04_server_app.py` and `04_server_app_v2.py`: server applications.

Dependencies named in the coursework: `pandas`, `rich`, `transformers`, `torch`, `scikit-learn`, `flask`, `selenium`.

## Labeling

Sentiment labeling used `seara/rubert-tiny2-russian-sentiment` through Hugging Face Transformers pipeline API. Processing was done in batches of 64 and reportedly took about 9 minutes.

Manual verification of automatic labels:

- sentiment: 92% agreement on 50 checked records;
- appeal type: 78% agreement on 50 checked records;
- addressee: 86% agreement on 50 checked records;
- "specific person" addressee was nearly error-free because of the stable "Name, text" pattern.

Estimated label quality:

- sentiment: 85-90%;
- appeal type: 65-75%;
- addressee: 75-85%.

Important consequence: label noise sets a quality ceiling for trained models.

## Model Architecture

Base model: `cointegrated/rubert-tiny2`.

Key properties from the coursework:

- 29.3M parameters;
- hidden size 312;
- 3 transformer layers;
- 12 attention heads;
- WordPiece vocabulary size 83,828.

The classifier is multi-head: one shared BERT encoder with separate classification heads for sentiment, appeal type, and addressee.

## Model Versions

Version 1:

- input: comment text only;
- max length: 128 tokens;
- training time on CPU: about 71 minutes;
- best average weighted F1: 0.879;
- sentiment F1: 0.802;
- appeal type F1: 0.876;
- addressee F1: 0.960.

Version 2:

- input: concatenated post context and comment text;
- format: `[ПОСТ] post text [КОММЕНТАРИЙ] comment text`;
- max length: 256 tokens;
- training time on CPU: about 6 hours;
- average weighted F1: 0.862;
- qualitatively better on some ambiguous cases;
- improves appeal type slightly, but does not solve addressee errors when labels were generated without context.

Main comparison: v1 is slightly better by aggregate metrics, while v2 is conceptually better for ambiguous context-dependent cases. The current v2 ceiling is limited by context-free automatic labels.

## Sarcasm Experiment

The coursework includes a separate sarcasm detection experiment:

- hypothesis: negative post + formally positive comment + excess markers can indicate sarcasm;
- model: gradient boosting;
- feature count: 28;
- self-training iterations: 4;
- training set grew from 37,969 to 122,402 examples.

Result:

- self-training F1: 0.993;
- manual check F1: 0.000;
- Cohen's Kappa: 0.000.

Interpretation: the experiment is a useful negative result demonstrating data leakage. The model learned the pseudo-label generation rule rather than sarcasm. A real sarcasm detector requires manual annotation, with a target of at least 500 sarcastic examples.

## Server Context

The coursework describes a Flask client-server web app, but the user clarified that the server is currently not connected.

Reported server/deployment details:

- Ubuntu 24.04 LTS;
- local server with AMD A10 and 8 GB RAM;
- CPU inference, no GPU;
- model size loaded into memory: about 112 MB;
- process memory around 450 MB with Gunicorn;
- interactive inference latency: 50-200 ms;
- Gunicorn used with `-w 1` due to memory constraints;
- frontend is a single-page vanilla JavaScript interface embedded into the Python file.

Reported API endpoints:

- `GET /`: main UI;
- `POST /api/classify`: classify text;
- `GET /api/random_post`: get random post from dataset;
- `GET /api/dataset_item`: get post-comment pair.

## Known Limitations

The coursework identifies these core limitations:

- sarcasm and irony are systematically misclassified as literal positive sentiment;
- addressee cannot be reliably inferred from post context because labels were generated from comment text only;
- rare classes are weak, especially "informing" with only 2 examples out of 138,680;
- regional specificity: model is trained on Nizhny Novgorod communities;
- social media comments are subjective and include noisy/destabilizing opinions;
- automatic label quality limits final model quality;
- CPU-only deployment is enough for interactive use but not high-throughput streaming.

## Diploma Development Directions

Planned development directions from the coursework:

- manually label 3,000-5,000 comments with visible post context to improve addressee classification;
- build a sarcasm corpus with at least 500 sarcastic examples;
- expand geography to Nizhny Novgorod region municipalities such as Arzamas, Dzerzhinsk, Bor, Kstovo, Pavlovo, Sarov, Vyksa, Balakhna, Gorodets, Semenov, and others;
- consider `ruBERT-base` or LoRA adaptation if GPU resources become available;
- integrate VK API for live collection;
- build an interactive dashboard for regions/topics/dynamics/sentiment;
- route appeals to responsible departments based on predicted addressee.

## Working Assumptions For Future Work

- `Normalizaciya` is the technical reference implementation and should be read-only unless the user explicitly says otherwise.
- The coursework is the main narrative source for the diploma direction.
- The current server described in the coursework is historical/not connected; do not assume a live endpoint exists.
- Future diploma work should likely preserve the core ML topic but improve data quality, context-aware labeling, sarcasm handling, regional coverage, and deployment/dashboard integration.

