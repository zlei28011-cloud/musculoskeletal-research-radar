from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from html import unescape
from typing import Iterable

from .http import HttpClient
from .models import Article

LOG = logging.getLogger(__name__)


def _clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", unescape(value or "")).strip()


def build_query(terms: list[str]) -> str:
    return " OR ".join(f'"{term}"' if " " in term else term for term in terms)


def _pubmed_date(article: ET.Element) -> str:
    pub = article.find("Journal/JournalIssue/PubDate")
    if pub is None:
        return ""
    year = _clean(pub.findtext("Year"))
    medline = _clean(pub.findtext("MedlineDate"))
    if not year:
        year = medline[:4]
    if not year:
        return ""
    month_raw = _clean(pub.findtext("Month"))
    months = {name.casefold(): f"{index:02d}" for index, name in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1
    )}
    month = month_raw.zfill(2) if month_raw.isdigit() else months.get(month_raw[:3].casefold(), "")
    day = _clean(pub.findtext("Day"))
    return "-".join(filter(None, [year, month, day.zfill(2) if day.isdigit() else ""]))


class PubMedSource:
    SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    FETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    def __init__(self, email: str = "", api_key: str = ""):
        interval = 0.12 if api_key else 0.36
        self.http = HttpClient(f"MusculoskeletalResearchRadar/0.1 ({email or 'no-email'})", interval)
        self.base_params = {"tool": "msk-research-radar", "email": email, "api_key": api_key}

    def fetch(self, terms: list[str], start: date, end: date, limit: int) -> list[Article]:
        if not self.base_params.get("email"):
            raise ValueError("NCBI_EMAIL is required by the NCBI E-utilities usage policy")
        params = {
            **self.base_params, "db": "pubmed", "retmode": "json", "retmax": limit,
            "sort": "pub date", "datetype": "pdat", "mindate": start.isoformat(), "maxdate": end.isoformat(),
            "term": build_query(terms),
        }
        ids = self.http.json(self.SEARCH, params).get("esearchresult", {}).get("idlist", [])
        return self.fetch_ids(ids)

    def fetch_ids(self, ids: Iterable[str]) -> list[Article]:
        ids = list(ids)
        if not ids:
            return []
        xml = self.http.get(self.FETCH, {**self.base_params, "db": "pubmed", "retmode": "xml", "id": ",".join(ids)})
        root = ET.fromstring(xml)
        items: list[Article] = []
        for node in root.findall(".//PubmedArticle"):
            citation = node.find("MedlineCitation")
            article = node.find(".//Article")
            if citation is None or article is None:
                continue
            pmid = _clean(citation.findtext("PMID"))
            title = _clean("".join(article.find("ArticleTitle").itertext()) if article.find("ArticleTitle") is not None else "")
            abstract = " ".join(_clean("".join(x.itertext())) for x in article.findall("Abstract/AbstractText"))
            journal = _clean(article.findtext("Journal/Title"))
            published = _pubmed_date(article)
            doi = ""
            for identifier in node.findall(".//ArticleId"):
                if identifier.attrib.get("IdType") == "doi":
                    doi = _clean(identifier.text)
            authors = []
            for author in article.findall("AuthorList/Author")[:8]:
                name = _clean(" ".join(filter(None, [author.findtext("ForeName"), author.findtext("LastName")])))
                if name:
                    authors.append(name)
            items.append(Article(
                source="pubmed", title=title, abstract=abstract, journal=journal, published_date=published,
                doi=doi, pmid=pmid, url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", status="peer-reviewed",
                authors=authors,
            ))
        return items

    def search_competition(self, query: str, limit: int = 4) -> list[dict[str, str]]:
        data = self.http.json(self.SEARCH, {
            **self.base_params, "db": "pubmed", "retmode": "json", "retmax": limit,
            "sort": "relevance", "term": query,
        })
        articles = self.fetch_ids(data.get("esearchresult", {}).get("idlist", []))
        return [{"title": x.title, "journal": x.journal, "date": x.published_date, "url": x.url, "pmid": x.pmid} for x in articles]


class CrossrefSource:
    URL = "https://api.crossref.org/works"

    def __init__(self, mailto: str = ""):
        self.mailto = mailto
        self.http = HttpClient(f"MusculoskeletalResearchRadar/0.1 (mailto:{mailto or 'unknown'})", 0.11)

    def fetch(self, terms: list[str], start: date, end: date, limit: int, journals: list[str] | None = None) -> list[Article]:
        query = build_query(terms)
        params = {
            "query.bibliographic": query, "filter": f"from-pub-date:{start},until-pub-date:{end}",
            "rows": min(limit, 100), "sort": "published", "order": "desc",
            "select": "DOI,title,abstract,container-title,published,author,URL,type",
        }
        if self.mailto:
            params["mailto"] = self.mailto
        message = self.http.json(self.URL, params).get("message", {})
        allowed = {x.casefold() for x in journals or []}
        result = []
        for item in message.get("items", []):
            title = _clean(" ".join(item.get("title", [])))
            journal = _clean(" ".join(item.get("container-title", [])))
            if allowed and journal.casefold() not in allowed:
                continue
            parts = item.get("published", {}).get("date-parts", [[""]])[0]
            published = "-".join(str(x).zfill(2) for x in parts if x != "")
            abstract = _clean(re.sub(r"<[^>]+>", " ", item.get("abstract", "")))
            authors = [_clean(" ".join([a.get("given", ""), a.get("family", "")])) for a in item.get("author", [])[:8]]
            result.append(Article(
                source="crossref", title=title, abstract=abstract, journal=journal, published_date=published,
                doi=item.get("DOI", ""), url=item.get("URL", ""), status="peer-reviewed", authors=authors,
            ))
        return result


class RxivSource:
    def __init__(self, server: str):
        if server not in {"biorxiv", "medrxiv"}:
            raise ValueError("server must be biorxiv or medrxiv")
        self.server = server
        self.http = HttpClient("MusculoskeletalResearchRadar/0.1", 1.05)

    def fetch(self, start: date, end: date, limit: int) -> list[Article]:
        result: list[Article] = []
        cursor = 0
        while len(result) < limit:
            url = f"https://api.biorxiv.org/details/{self.server}/{start}/{end}/{cursor}"
            payload = self.http.json(url)
            batch = payload.get("collection", [])
            if not batch:
                break
            for item in batch:
                doi = item.get("doi", "")
                result.append(Article(
                    source=self.server, title=_clean(item.get("title")), abstract=_clean(item.get("abstract")),
                    journal=self.server, published_date=item.get("date", ""), doi=doi,
                    url=f"https://www.{self.server}.org/content/{doi}", status="preprint",
                    authors=[_clean(x) for x in item.get("authors", "").split(";") if _clean(x)],
                    raw={"category": item.get("category", ""), "published_doi": item.get("published", "")},
                ))
                if len(result) >= limit:
                    break
            cursor += len(batch)
        return result


def date_window(days: int) -> tuple[date, date]:
    today = date.today()
    return today - timedelta(days=days), today
