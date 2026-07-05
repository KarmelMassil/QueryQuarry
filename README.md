# QueryQuarry

QueryQuarry is a multi-strategy web scraping application developed for Assignment 3 in the "Idea to reality using AI" course. It explores different methodologies for extracting data from the web, ranging from traditional parsing techniques to modern, AI-driven extraction APIs.

## Features

* **Basic Scraper:** Utilizes standard HTML parsing techniques (`basic_scraper.py`) for simple, structured data extraction.
* **Firecrawl Scraper:** Integrates with the Firecrawl API (`firecrawl_scraper.py`) for robust, scalable web crawling and formatting.
* **LLM Scraper:** Employs Large Language Models (`llm_scraper.py`) to intelligently extract, interpret, and structure unstructured data from web pages.
* **Interactive Web Interface:** A lightweight frontend (`frontend.html`) allowing users to easily input target URLs, select their preferred scraping method, and view the extracted results.
* **Unified Backend:** A centralized application (`main.py`) that handles frontend requests and routes them to the appropriate scraping module.

## Files Included

* `.gitignore`
* `basic_scraper.py`
* `firecrawl_scraper.py`
* `frontend.html`
* `llm_scraper.py`
* `main.py`
* `requirements.txt`

## Prerequisites

* Python 3.8+
* Firecrawl API Key
* LLM API Key

## Installation

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Set up the required environment variables for your APIs before running the application.

For Linux/macOS:
```bash
export FIRECRAWL_API_KEY="your_firecrawl_api_key"
export OPENAI_API_KEY="your_llm_api_key"
```

For Windows:
```cmd
set FIRECRAWL_API_KEY="your_firecrawl_api_key"
set OPENAI_API_KEY="your_llm_api_key"
```

## Usage

```bash
python main.py
```
