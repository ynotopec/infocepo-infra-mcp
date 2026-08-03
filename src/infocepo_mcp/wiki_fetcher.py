"""Wiki fetcher: auto-discover infocepo.com infrastructure from wiki content."""

import re
import json
import hashlib
import time
from pathlib import Path
from typing import Optional
import httpx


class WikiFetcher:
    """Fetch and parse the infocepo.com wiki to discover services and endpoints."""

    def __init__(self, wiki_base: str = "https://infocepo.com/wiki/api.php", cache_dir: str = "/tmp/infocepo-wiki-cache"):
        self.wiki_base = wiki_base
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache = {}

    def get_page(self, title: str) -> Optional[str]:
        """Fetch a wiki page's wikitext content."""
        cache_key = hashlib.md5(f"{self.wiki_base}:{title}".encode()).hexdigest()
        cache_file = self.cache_dir / f"{cache_key}.txt"

        if cache_file.exists():
            age = Path(cache_file).stat().st_mtime
            if age > (time.time() - 3600):  # 1h cache
                return cache_file.read_text()

        url = f"{self.wiki_base}?action=query&titles={title}&prop=revisions&rvprop=content&format=json"
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.get(url, headers={"User-Agent": "infocepo-mcp/1.0"})
                if resp.status_code != 200:
                    return None
                data = resp.json()
                pages = data.get("query", {}).get("pages", {})
                if not pages:
                    return None
                for pid in pages:
                    rev = pages[pid].get("revisions", [{}])
                    if rev and rev[0]:
                        content = rev[0]
                        if "slots" in content and "main" in content["slots"]:
                            text = content["slots"]["main"]["*"]
                        else:
                            text = content.get("*", "")
                        # Cache
                        cache_file.write_text(text)
                        return text
        except Exception:
            pass
        return None

    def parse_main_page(self) -> dict:
        """Parse Main_Page and extract all service endpoints, credentials hints, and config."""
        content = self.get_page("Main_Page")
        if not content:
            return {"error": "Failed to fetch Main_Page"}

        result = {
            "sections": {},
            "services": [],
            "api_endpoints": {},
            "urls": [],
            "models": [],
            "credentials_hints": [],
            "wikitext": content,
        }

        # Extract H1 sections
        for m in re.finditer(r'^= (.*?) =$', content, re.MULTILINE):
            title = m.group(1).strip()
            # Find content until next H1 or end
            start = m.end()
            next_h1 = re.search(r'^= .? =$', content[start:], re.MULTILINE)
            if next_h1:
                section_content = content[start:start+next_h1.start()]
            else:
                section_content = content[start:]
            result["sections"][title] = section_content.strip()

        # Extract services from the "Catalogue rapide des services" table
        services_section = result.get("sections", {}).get("Catalogue rapide des services", "")
        if services_section:
            result["services"] = self._parse_services_table(services_section)

        # Extract all URLs
        result["urls"] = list(set(re.findall(r'https?://[^\s\|"\']+?/', content)))

        # Extract model names from model tables
        models_section = result.get("sections", {}).get("Modèles ouverts & endpoints internes", "")
        if not models_section:
            models_section = result.get("sections", {}).get("Liste des modèles", "")
        if models_section:
            result["models"] = self._parse_models(models_section)

        # Extract API configuration blocks
        api_section = result.get("sections", {}).get("API Realtime AI (DEV)", "")
        llm_section = result.get("sections", {}).get("API LLM (OpenAI compatible)", "")
        for section in [api_section, llm_section]:
            if section:
                config = self._parse_api_config(section)
                if config:
                    result["api_endpoints"].update(config)

        # Extract credential hints
        for m in re.finditer(r'(?:sk-|token|KEY|password|user)\s*(?::\s*)?(?:XXXX|placeholder|YOUR|...|\*\*\*)', content, re.IGNORECASE):
            result["credentials_hints"].append(m.group(0).strip())

        # Extract endpoints from table rows
        result["api_endpoints"]["catalog"] = self._extract_endpoints_from_table(content)

        return result

    def _parse_services_table(self, table_content: str) -> list:
        """Parse the service catalog table from wiki markup."""
        services = []
        # Match rows: | Category || Service || [URL] Role
        for m in re.finditer(
            r'\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(?:\[(?:https?://[^\]]+)\s*)?(.*?)(?:\|\s*$|\s*$)',
            table_content, re.MULTILINE
        ):
            cat = m.group(1).strip()
            svc = m.group(2).strip()
            role = m.group(3).strip().rstrip('|').rstrip()
            url = re.search(r'https?://[^\]]+', svc)
            services.append({
                "category": cat,
                "service": svc.replace("|", "").strip(),
                "url": url.group(0) if url else None,
                "role": role,
            })
        return services

    def _parse_models(self, content: str) -> list:
        """Extract model names from wiki model tables."""
        models = []
        for m in re.finditer(r"\b(ai-[a-z0-9\-]+)\b", content):
            models.append(m.group(1))
        return list(set(models))

    def _parse_api_config(self, section: str) -> dict:
        """Extract API config blocks (OPENAI_API_BASE, OPENAI_API_KEY, etc.)."""
        config = {}
        # Pattern: | KEY || VALUE
        for m in re.finditer(r'\|\s*(OPENAI_API_|CHROMA_|REGISTRY_|S3_|OPENAI_)\w*\s*\|\s*(.*?)\s*\|', section):
            key = m.group(1).strip()
            value = m.group(2).strip()
            config[key] = value
        return config

    def _extract_endpoints_from_table(self, content: str) -> list:
        """Extract all service endpoints from the main page table."""
        endpoints = []
        # Match any URL on a line that looks like an API endpoint
        for m in re.finditer(
            r'(api-\w+|chromadb|registry|s3|grafana|uptime-kuma|datalab|translate-rt|demos|web-stat|api)\.\w+\.infocepo\.com(?:[^s"\']*)?',
            content
        ):
            url = m.group(0)
            # Clean :wait-YYYY-MM annotations
            url = re.sub(r':wait-\d{4}-\d{2}', '', url)
            endpoints.append({
                "url": f"https://{url}",
                "raw": url,
            })
        # Deduplicate by URL string (dicts are not hashable)
        seen_urls = set()
        deduped = []
        for ep in endpoints:
            if ep["url"] not in seen_urls:
                seen_urls.add(ep["url"])
                deduped.append(ep)
        return deduped

    def get_section(self, title: str, section_name: str) -> Optional[str]:
        """Get a specific section from a wiki page."""
        content = self.get_page(title)
        if not content:
            return None
        # Find section header (== Section ==)
        pattern = f"== {section_name} =="
        start = content.find(pattern)
        if start == -1:
            return None
        start += len(pattern)
        # Find next section header or end
        end = len(content)
        for m in re.finditer(r'^={1,4} .+? =+$', content[start:], re.MULTILINE):
            # Stop at H1 or higher level
            line = content[start+m.start():start+m.end()]
            if line.startswith("=") and not line.startswith("=="):
                end = start + m.start()
                break
        return content[start:end].strip()

    def parse_sections(self, title: str) -> list:
        """Split a page into sections by heading level."""
        content = self.get_page(title)
        if not content:
            return []
        sections = []
        for m in re.finditer(r'^(={1,4}) (.*?) =+\n(.*?)(?=\1 .+? =+|$)', content, re.MULTILINE | re.DOTALL):
            level = len(m.group(1))
            name = m.group(2).strip()
            body = m.group(3).strip()
            # Only include H2 and H3 sections (level 2-3)
            if level <= 3:
                sections.append({"level": level, "title": name, "content": body})
        return sections

    def clean_url(self, url: str) -> str:
        """Strip :wait-YYYY-MM annotations."""
        return re.sub(r':wait-\d{4}-\d{2}', '', url)
