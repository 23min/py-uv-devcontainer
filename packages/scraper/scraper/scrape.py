# ruff: noqa: G004
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup, Tag
from markdownify import markdownify as md
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from urllib3.exceptions import MaxRetryError

# G004: Logging statement uses f-string


# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.FileHandler("scrape.log"), logging.StreamHandler()],
)

# Suppress urllib3 logs
logging.getLogger("urllib3").setLevel(logging.WARNING)

# Base URL of the archived blog
base_urls = [
    "https://web.archive.org/web/20240910152712/http://reinderbruinsma.com/",
]

# Output directory for markdown files
output_dir = Path("blog_posts")
output_dir.mkdir(parents=True, exist_ok=True)

# State file to save the crawling state
state_file = "crawl_state.json"
# Stats file to save the statistics
stats_file = "crawl_stats.json"
# File to save post dates and titles
dates_titles_file = "post_dates_titles.txt"
# File to save 404 errors
errors_file = "errors_404.txt"


@dataclass
class Post:
    """Data class to store post data."""

    id: str
    title: str
    content: str
    entry_date: str
    content_html: str
    year: str


@dataclass
class Stats:
    """Data class to store statistics."""

    articles_per_year: dict[str, int] = field(default_factory=dict)
    total_articles: int = 0
    articles: list[dict[str, str]] = field(default_factory=list)


@dataclass
class CrawlState:
    """Data class to store the state of the crawling process."""

    urls_to_crawl: list[str] = field(default_factory=list)
    crawled_urls: set[str] = field(default_factory=set)
    errors_404: list[str] = field(default_factory=list)


def wait_if_retry_after(retry_state: RetryCallState) -> None:
    """Wait if the response contains a Retry-After header."""
    if retry_state.outcome is None:
        return
    exception = retry_state.outcome.exception()
    if exception and isinstance(exception, requests.RequestException):
        response = exception.response
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    wait_time = int(retry_after)
                except ValueError:
                    wait_time = (
                        time.mktime(time.strptime(retry_after, "%a, %d %b %Y %H:%M:%S %Z"))
                        - time.time()
                    )
                logging.info("Retry-After header found. Waiting for %d seconds.", wait_time)
                time.sleep(wait_time)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=5, min=30, max=300),
    before_sleep=wait_if_retry_after,
    retry=(
        retry_if_exception_type(requests.RequestException)
        & retry_if_not_exception_type(requests.HTTPError)
    ),
)
def fetch_page(url: str) -> BeautifulSoup | None:
    """Fetch a webpage and return its soup object."""
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        logging.info("Fetched %s", url)
        return BeautifulSoup(response.text, "html.parser")
    except requests.HTTPError as e:
        if e.response.status_code == 404:  # noqa: PLR2004
            logging.exception("404 Error for %s", url)
            return None
        raise
    except (requests.RequestException, MaxRetryError):
        logging.exception("Failed to fetch %s.", url)
        raise


def count_formatting_tags(html_content: str) -> dict:
    """Count the occurrences of bold and italic tags in the HTML content."""
    soup = BeautifulSoup(html_content, "html.parser")

    bold_tags = soup.find_all(["strong", "b"])
    italic_tags = soup.find_all(["em", "i"])

    return {"bold": len(bold_tags), "italic": len(italic_tags)}


def extract_posts(soup: BeautifulSoup) -> list[Post]:
    """Extract post data from a BeautifulSoup object."""
    posts = []
    content_div = soup.find("div", id="content")
    if content_div and isinstance(content_div, Tag):
        articles = content_div.find_all("article", id=True)
        for article in articles:
            post_id = article["id"]
            a_tag = article.find("a", rel="bookmark")
            title = a_tag.get_text(strip=True) if a_tag else "No Title"
            body = article.find("div", class_="entry-content")

            # Extract HTML content
            content_html = str(body) if body else ""

            # Convert HTML content to Markdown
            content_md = md(content_html)

            # Extract the date from the <time> tag within the <footer>
            footer = article.find("footer", class_="entry-meta")
            date = ""
            if footer and isinstance(footer, Tag):
                time_tag = footer.find("time", class_="entry-date")
                if time_tag and isinstance(time_tag, Tag):
                    date_value = time_tag.get("datetime", time_tag.get_text(strip=True))
                    date = date_value[0] if isinstance(date_value, list) else date_value

            year = date[:4] if date else "unknown"

            posts.append(
                Post(
                    id=post_id,
                    title=title,
                    content=content_md,
                    entry_date=date,
                    content_html=content_html,
                    year=year,
                )
            )
    return posts


def save_to_files(post: Post) -> None:
    """Save a single post to both Markdown and HTML files."""
    # Format the date
    date_str = post.entry_date[:10]  # Assuming the date is in ISO format (yyyy-mm-dd)
    # Create the filenames
    filename_md = f"{date_str}-{post.id}-{post.title.replace(' ', '_').replace('/', '-')}.md"
    filename_html = f"{date_str}-{post.id}-{post.title.replace(' ', '_').replace('/', '-')}.html"
    filepath_md = output_dir / filename_md
    filepath_html = output_dir / filename_html

    # Save as Markdown
    with Path(filepath_md).open("w", encoding="utf-8") as f:
        f.write(f"# {post.title}\n\n")
        f.write(post.content)

    # Save as HTML
    with Path(filepath_html).open("w", encoding="utf-8") as f:
        f.write(f"<h1>{post.title}</h1>\n\n")
        f.write(post.content_html)


def extract_archive_links(soup: BeautifulSoup) -> list[str]:
    """Extract archive links from the 'Archives' section."""
    archive_links = []
    archive_section = soup.find("aside", id="flexo-archives-3")
    if archive_section and isinstance(archive_section, Tag):
        links = archive_section.find_all("a", href=True)
        archive_links.extend(link["href"] for link in links)
    return archive_links


def extract_unique_part(url: str) -> str:
    """Extract the unique part of the URL defined by the 'm=' variable."""
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    return query_params.get("m", [""])[0]


def save_state(state: CrawlState) -> None:
    """Save the state of the crawling process to a file."""
    state_dict = asdict(state)
    state_dict["crawled_urls"] = list(
        state.crawled_urls
    )  # Convert set to list for JSON serialization
    with Path(state_file).open("w", encoding="utf-8") as f:
        json.dump(state_dict, f)


def load_state() -> CrawlState:
    """Load the state of the crawling process from a file."""
    if Path(state_file).exists():
        with Path(state_file).open(encoding="utf-8") as f:
            state_dict = json.load(f)
            state_dict["crawled_urls"] = set(state_dict["crawled_urls"])  # Convert list back to set
            return CrawlState(**state_dict)
    return CrawlState()


def save_stats(stats: Stats) -> None:
    """Save the statistics to a file."""
    with Path(stats_file).open("w", encoding="utf-8") as f:
        json.dump(asdict(stats), f)


def load_stats() -> Stats:
    """Load the statistics from a file."""
    if Path(stats_file).exists():
        with Path(stats_file).open(encoding="utf-8") as f:
            stats_dict = json.load(f)
            return Stats(**stats_dict)
    return Stats()


def update_stats(stats: Stats, posts: list[Post]) -> None:
    """Update the statistics with new posts."""
    for post in posts:
        year = post.year
        if year not in stats.articles_per_year:
            stats.articles_per_year[year] = 0
        stats.articles_per_year[year] += 1
        stats.articles.append({"date": post.entry_date, "title": post.title})
    stats.total_articles += len(posts)


def save_dates_titles(stats: Stats) -> None:
    """Save the post dates and titles to a text file."""
    with Path(dates_titles_file).open("w", encoding="utf-8") as f:
        # Write the summary at the top
        for year, count in stats.articles_per_year.items():
            f.write(f"{year}, {count} posts\n")
        f.write("\n")

        # Write the post dates and titles
        for article in stats.articles:
            date_time = datetime.fromisoformat(article["date"])
            formatted_date = date_time.strftime("%Y-%m-%d %H:%M")
            f.write(f"{formatted_date} {article['title']}\n")


def save_errors_404(state: CrawlState) -> None:
    """Save the 404 errors to a text file."""
    with Path(errors_file).open("w", encoding="utf-8") as f:
        for error_url in state.errors_404:
            f.write(f"{error_url}\n")


def crawl_site(start_url: str) -> None:
    """Crawl the site starting from the given URL."""
    state = load_state()
    stats = load_stats()
    if not state.urls_to_crawl:
        state.urls_to_crawl = [start_url]

    while state.urls_to_crawl:
        current_url = state.urls_to_crawl.pop(0)
        unique_part = extract_unique_part(current_url)
        if unique_part in state.crawled_urls:
            continue

        try:
            soup = fetch_page(current_url)
            if soup is None:
                state.errors_404.append(current_url)
                save_errors_404(state)
                continue
        except Exception:
            logging.exception("Error fetching page %s", current_url)
            state.urls_to_crawl.append(current_url)
            save_state(state)
            save_stats(stats)
            save_dates_titles(stats)
            save_errors_404(state)
            continue

        if not soup:
            continue

        # Extract and save posts
        posts = extract_posts(soup)
        for post in posts:
            save_to_files(post)

        # Update statistics
        update_stats(stats, posts)

        # Extract new archive links and add them to the list of URLs to crawl
        new_links = extract_archive_links(soup)
        for link in new_links:
            unique_link_part = extract_unique_part(link)
            if (
                unique_link_part not in state.crawled_urls
                and unique_link_part not in state.urls_to_crawl
            ):
                state.urls_to_crawl.append(link)

        state.crawled_urls.add(unique_part)
        save_state(state)
        save_stats(stats)
        save_dates_titles(stats)
        save_errors_404(state)


if __name__ == "__main__":
    for base_url in base_urls:
        crawl_site(base_url)
