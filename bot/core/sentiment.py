"""Sentiment scoring — DeepSeek (primary) ou Gemini (fallback gratuit).

Reproduit la logique du PDF Sentiment Cartography :
  - chaque article → score [0.00, 1.00]
  - agrégation moyenne par coin
  - 0.00 = peur extrême, 1.00 = euphorie
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

from .news_feed import Article

log = logging.getLogger(__name__)


@dataclass
class SentimentResult:
    coin: str
    score: float           # 0.0 - 1.0
    article_count: int
    raw_scores: list[float]


SYSTEM_PROMPT = """Tu es un analyste de sentiment crypto.
Pour chaque article de presse fourni, tu retournes UN SEUL nombre entre 0.00 et 1.00
qui mesure l'optimisme du marché vis-à-vis de la crypto mentionnée.

0.00 = peur extrême, panique, FUD, krach, exploit, hack, régulation hostile
0.50 = neutre, factuel, sans direction claire
1.00 = euphorie, parabolique, ATH, partenariat majeur, listing top exchange, narrative AI/RWA bullish

Réponds UNIQUEMENT par un nombre décimal entre 0.00 et 1.00, rien d'autre."""


def _score_with_deepseek(text: str, api_key: str, model: str = "deepseek-chat") -> Optional[float]:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.0,
            max_tokens=8,
        )
        raw = (resp.choices[0].message.content or "").strip()
        return _parse_float(raw)
    except Exception as e:
        log.warning("deepseek score err: %s", e)
        return None


def _score_with_gemini(text: str, api_key: str, model: str = "gemini-2.5-flash") -> Optional[float]:
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        m = genai.GenerativeModel(model, system_instruction=SYSTEM_PROMPT)
        resp = m.generate_content(text, generation_config={"temperature": 0.0, "max_output_tokens": 8})
        return _parse_float((resp.text or "").strip())
    except Exception as e:
        log.warning("gemini score err: %s", e)
        return None


def _parse_float(raw: str) -> Optional[float]:
    # Extrait le premier nombre décimal de la réponse
    import re
    m = re.search(r"([01]?\.\d+|[01])", raw)
    if not m:
        return None
    try:
        v = float(m.group(1))
        return max(0.0, min(1.0, v))
    except ValueError:
        return None


def score_article(article: Article) -> Optional[float]:
    text = f"Crypto: {article.coin}\nTitre: {article.title}\nRésumé: {article.summary}"
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    model_pref = os.environ.get("SENTIMENT_MODEL", "deepseek-chat")

    if "gemini" in model_pref and gemini_key:
        s = _score_with_gemini(text, gemini_key, model_pref)
        if s is not None:
            return s
    if deepseek_key:
        s = _score_with_deepseek(text, deepseek_key)
        if s is not None:
            return s
    # Fallback Gemini si DeepSeek absent
    if gemini_key:
        return _score_with_gemini(text, gemini_key)
    return None


def aggregate_sentiment(coin: str, articles: list[Article]) -> SentimentResult:
    raw: list[float] = []
    for a in articles:
        s = score_article(a)
        if s is not None:
            raw.append(s)
    score = sum(raw) / len(raw) if raw else 0.5  # neutre si aucun article
    return SentimentResult(coin=coin, score=score, article_count=len(raw), raw_scores=raw)


def aggregate_universe(articles_by_coin: dict[str, list[Article]]) -> dict[str, SentimentResult]:
    return {c: aggregate_sentiment(c, arts) for c, arts in articles_by_coin.items()}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from dotenv import load_dotenv
    from .news_feed import fetch_articles_for_coin
    load_dotenv()
    coin = "LINK"
    arts = fetch_articles_for_coin(coin, lookback_hours=24)
    print(f"{coin}: {len(arts)} articles à scorer")
    result = aggregate_sentiment(coin, arts)
    print(f"Sentiment {coin}: {result.score:.3f} (sur {result.article_count} articles)")
    print(f"Scores bruts: {result.raw_scores}")
