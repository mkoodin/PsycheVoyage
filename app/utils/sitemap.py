import xml.etree.ElementTree as ET
from typing import List
from urllib.parse import urljoin

import requests


def get_sitemap_urls(base_url: str, sitemap_filename: str = "sitemap.xml") -> List[str]:
    """Fetches and parses a sitemap XML file to extract URLs.

    Args:
        base_url: The base URL of the website
        sitemap_filename: The filename of the sitemap (default: sitemap.xml)

    Returns:
        List of URLs found in the sitemap. If sitemap is not found, returns a list
        containing only the base URL.

    Raises:
        ValueError: If there's an error fetching (except 404) or parsing the sitemap
    """

    def fetch_sitemap(url: str) -> requests.Response:
        headers = {
            "Accept": "application/xml, text/xml, application/xhtml+xml, text/html;q=0.9",
            "User-Agent": "Mozilla/5.0 (compatible; PsycheVoyageBot/1.0)",
        }
        return requests.get(url, headers=headers, timeout=10)

    def parse_sitemap(content: bytes, namespaces: dict) -> List[str]:
        root = ET.fromstring(content)
        urls = []

        # Check if this is a sitemap index
        if namespaces:
            sitemaps = root.findall(".//ns:sitemap/ns:loc", namespaces)
            if sitemaps:
                # This is a sitemap index, recursively fetch each sitemap
                for sitemap in sitemaps:
                    try:
                        sub_response = fetch_sitemap(sitemap.text)
                        sub_response.raise_for_status()
                        urls.extend(parse_sitemap(sub_response.content, namespaces))
                    except (requests.RequestException, ET.ParseError) as e:
                        print(
                            f"Warning: Failed to fetch/parse sub-sitemap {sitemap.text}: {str(e)}"
                        )
                        continue
            else:
                # Regular sitemap
                urls.extend(
                    [elem.text for elem in root.findall(".//ns:loc", namespaces)]
                )
        else:
            # Try without namespace
            sitemaps = root.findall(".//sitemap/loc")
            if sitemaps:
                for sitemap in sitemaps:
                    try:
                        sub_response = fetch_sitemap(sitemap.text)
                        sub_response.raise_for_status()
                        urls.extend(parse_sitemap(sub_response.content, namespaces))
                    except (requests.RequestException, ET.ParseError) as e:
                        print(
                            f"Warning: Failed to fetch/parse sub-sitemap {sitemap.text}: {str(e)}"
                        )
                        continue
            else:
                urls.extend([elem.text for elem in root.findall(".//loc")])

        return urls

    try:
        sitemap_url = urljoin(base_url, sitemap_filename)
        response = fetch_sitemap(sitemap_url)

        # Return just the base URL if sitemap not found
        if response.status_code == 404:
            return [base_url.rstrip("/")]

        response.raise_for_status()

        # Parse XML content
        root = ET.fromstring(response.content)

        # Handle different XML namespaces that sitemaps might use
        namespaces = (
            {"ns": root.tag.split("}")[0].strip("{")} if "}" in root.tag else None
        )

        return parse_sitemap(response.content, namespaces)

    except requests.RequestException as e:
        raise ValueError(f"Failed to fetch sitemap: {str(e)}")
    except ET.ParseError as e:
        raise ValueError(f"Failed to parse sitemap XML: {str(e)}")
    except Exception as e:
        raise ValueError(f"Unexpected error processing sitemap: {str(e)}")


if __name__ == "__main__":
    urls = get_sitemap_urls("https://psychevoyage.com")
    print(f"Found {len(urls)} URLs:")
    for url in urls:
        print(url)
