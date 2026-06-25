from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from django.utils import timezone

from .text import (
    absolute_vk_url,
    clean_vk_text,
    parse_vk_datetime,
    reply_id_from_url,
    wall_id_from_url,
)


@dataclass
class ScrapedVkItem:
    item_type: str
    external_id: str
    source_url: str
    text: str
    post_external_id: str = ""
    post_url: str = ""
    post_text: str = ""
    author_name: str = ""
    published_at: datetime | None = None
    published_at_raw: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class VkPlaywrightScraper:
    def __init__(
        self,
        *,
        base_url: str = "https://m.vk.com",
        headless: bool = True,
        storage_state: str = "",
        user_data_dir: str = "",
        timeout_ms: int = 30000,
        slow_mo_ms: int = 0,
        scroll_rounds: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.headless = headless
        self.storage_state = storage_state
        self.user_data_dir = user_data_dir
        self.timeout_ms = timeout_ms
        self.slow_mo_ms = slow_mo_ms
        self.scroll_rounds = scroll_rounds
        self._playwright = None
        self._browser = None
        self._context = None

    def __enter__(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright is not installed. Install monitoring dependencies and run: "
                "python -m playwright install chromium"
            ) from exc

        self._playwright = sync_playwright().start()
        launch_args = ["--disable-dev-shm-usage"]
        if self.headless:
            launch_args.append("--no-sandbox")

        context_kwargs = {
            "viewport": {"width": 1280, "height": 1400},
            "locale": "ru-RU",
            "timezone_id": "Europe/Moscow",
            "user_agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
            ),
        }
        if self.storage_state and Path(self.storage_state).exists():
            context_kwargs["storage_state"] = self.storage_state

        if self.user_data_dir:
            self._context = self._playwright.chromium.launch_persistent_context(
                self.user_data_dir,
                headless=self.headless,
                slow_mo=self.slow_mo_ms,
                args=launch_args,
                **context_kwargs,
            )
        else:
            self._browser = self._playwright.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo_ms,
                args=launch_args,
            )
            self._context = self._browser.new_context(**context_kwargs)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def scrape_source(
        self,
        *,
        screen_name: str,
        since: datetime,
        max_posts: int = 5,
        max_comments_per_post: int = 50,
        include_unknown_dates: bool = False,
    ) -> list[ScrapedVkItem]:
        page = self._new_page()
        source_url = f"{self.base_url}/{screen_name}"
        page.goto(source_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
        self._settle(page)
        self._scroll(page, self.scroll_rounds)

        post_links = self._extract_post_links(page)
        page.close()

        output: list[ScrapedVkItem] = []
        for post in post_links[: max_posts or None]:
            post_items = self.scrape_post(
                post_url=post["url"],
                fallback_text=post.get("text", ""),
                fallback_date=post.get("date", ""),
                since=since,
                max_comments=max_comments_per_post,
                include_unknown_dates=include_unknown_dates,
            )
            output.extend(post_items)
        return output

    def scrape_post(
        self,
        *,
        post_url: str,
        fallback_text: str,
        fallback_date: str,
        since: datetime,
        max_comments: int,
        include_unknown_dates: bool,
    ) -> list[ScrapedVkItem]:
        page = self._new_page()
        page.goto(post_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
        self._settle(page)
        self._expand_comments(page)
        self._scroll(page, 1)

        detail = self._extract_post_detail(page)
        comments = self._extract_comments(page)
        page.close()

        post_text = clean_vk_text(detail.get("text") or fallback_text)
        post_date_raw = detail.get("date") or fallback_date
        post_date = parse_vk_datetime(post_date_raw)
        post_id = wall_id_from_url(post_url) or detail.get("external_id", "")
        output: list[ScrapedVkItem] = []

        if post_text and self._date_allowed(post_date, since, include_unknown_dates):
            output.append(
                ScrapedVkItem(
                    item_type="post",
                    external_id=post_id or post_url,
                    source_url=post_url,
                    post_url=post_url,
                    post_external_id=post_id,
                    text=post_text,
                    post_text="",
                    author_name=clean_vk_text(detail.get("author", "")),
                    published_at=post_date,
                    published_at_raw=post_date_raw,
                    raw={"post_detail": detail},
                )
            )

        for comment in comments[: max_comments or None]:
            text = clean_vk_text(comment.get("text", ""))
            if not text or text == post_text:
                continue
            raw_date = comment.get("date", "")
            published_at = parse_vk_datetime(raw_date)
            if not self._date_allowed(published_at, since, include_unknown_dates):
                continue
            comment_url = comment.get("url") or post_url
            reply_id = reply_id_from_url(comment_url) or comment.get("external_id", "")
            external_id = f"{post_id}:reply:{reply_id}" if post_id and reply_id else comment_url + ":" + text[:40]
            output.append(
                ScrapedVkItem(
                    item_type="comment",
                    external_id=external_id,
                    source_url=comment_url,
                    post_external_id=post_id,
                    post_url=post_url,
                    text=text,
                    post_text=post_text,
                    author_name=clean_vk_text(comment.get("author", "")),
                    published_at=published_at,
                    published_at_raw=raw_date,
                    raw={"comment": comment, "post_detail": detail},
                )
            )
        return output

    def _new_page(self):
        if not self._context:
            raise RuntimeError("Scraper context is not open.")
        page = self._context.new_page()
        page.set_default_timeout(self.timeout_ms)
        return page

    def _settle(self, page):
        page.wait_for_timeout(1200)

    def _scroll(self, page, rounds: int):
        for _ in range(max(rounds, 0)):
            page.mouse.wheel(0, 2200)
            page.wait_for_timeout(700)

    def _expand_comments(self, page):
        for _ in range(3):
            clicked = page.evaluate(
                """
                () => {
                  const nodes = Array.from(document.querySelectorAll('a, button'));
                  const node = nodes.find((el) => {
                    const text = (el.innerText || el.textContent || '').toLowerCase();
                    return text.includes('показать') && (text.includes('коммент') || text.includes('ответ'));
                  });
                  if (!node) return false;
                  node.click();
                  return true;
                }
                """
            )
            if not clicked:
                break
            page.wait_for_timeout(1000)

    def _extract_post_links(self, page) -> list[dict[str, str]]:
        rows = page.evaluate(
            """
            () => {
              const out = [];
              const seen = new Set();
              const anchors = Array.from(document.querySelectorAll('a[href*="wall"]'));
              for (const a of anchors) {
                const href = a.getAttribute('href') || '';
                const match = href.match(/wall-?\\d+_\\d+/);
                if (!match) continue;
                const id = match[0];
                if (seen.has(id)) continue;
                seen.add(id);
                const block = a.closest('article, .wall_item, .post, .feed_row, .wall_text, .pi_cont, div') || a.parentElement;
                const text = block ? (block.innerText || block.textContent || '') : '';
                const timeEl = block ? block.querySelector('time, .rel_date, .wi_date, .post_date, [class*="date"]') : null;
                const date = timeEl ? (timeEl.getAttribute('datetime') || timeEl.innerText || timeEl.textContent || '') : '';
                out.push({id, href, text, date});
              }
              return out;
            }
            """
        )
        out: list[dict[str, str]] = []
        for row in rows:
            url = absolute_vk_url(self.base_url, row.get("href", ""))
            text = clean_vk_text(row.get("text", ""))
            out.append(
                {
                    "external_id": row.get("id", ""),
                    "url": url,
                    "text": text,
                    "date": clean_vk_text(row.get("date", "")),
                }
            )
        return out

    def _extract_post_detail(self, page) -> dict[str, str]:
        row = page.evaluate(
            """
            () => {
              const textSelectors = [
                '.wall_post_text',
                '[class*="wall_post_text"]',
                '.pi_text',
                '.wi_body',
                '.post_content',
                '[data-testid="wall_post_text"]'
              ];
              let text = '';
              for (const selector of textSelectors) {
                const el = document.querySelector(selector);
                if (el && (el.innerText || el.textContent || '').trim().length > text.length) {
                  text = el.innerText || el.textContent || '';
                }
              }
              const root = document.querySelector('article, .wall_item, .post, .pi_cont') || document.body;
              const timeEl = root.querySelector('time, .rel_date, .wi_date, .post_date, [class*="date"]');
              const authorEl = root.querySelector('.author, .pi_author, .wi_author, [class*="author"]');
              const link = document.querySelector('a[href*="wall"]');
              return {
                text,
                date: timeEl ? (timeEl.getAttribute('datetime') || timeEl.innerText || timeEl.textContent || '') : '',
                author: authorEl ? (authorEl.innerText || authorEl.textContent || '') : '',
                href: link ? (link.getAttribute('href') || '') : ''
              };
            }
            """
        )
        row["url"] = absolute_vk_url(self.base_url, row.get("href", ""))
        row["external_id"] = wall_id_from_url(row["url"])
        return {key: clean_vk_text(value) for key, value in row.items()}

    def _extract_comments(self, page) -> list[dict[str, str]]:
        rows = page.evaluate(
            """
            () => {
              const blocks = Array.from(document.querySelectorAll(
                '.reply, .wall_reply, [id^="reply"], [class*="reply"], .comment, [class*="comment"]'
              ));
              const out = [];
              const seen = new Set();
              for (const block of blocks) {
                const textEl = block.querySelector(
                  '.wall_reply_text, .reply_text, [class*="reply_text"], [class*="comment_text"], .pi_text'
                ) || block;
                const text = textEl.innerText || textEl.textContent || '';
                if (!text || text.trim().length < 3) continue;
                const link = block.querySelector('a[href*="reply="], a[href*="_r"], a[href*="wall"]');
                const href = link ? (link.getAttribute('href') || '') : '';
                const timeEl = block.querySelector('time, .rel_date, .reply_date, [class*="date"]');
                const authorEl = block.querySelector('.author, .reply_author, [class*="author"], .pi_author');
                const key = href || text.trim().slice(0, 80);
                if (seen.has(key)) continue;
                seen.add(key);
                out.push({
                  href,
                  text,
                  date: timeEl ? (timeEl.getAttribute('datetime') || timeEl.innerText || timeEl.textContent || '') : '',
                  author: authorEl ? (authorEl.innerText || authorEl.textContent || '') : ''
                });
              }
              return out;
            }
            """
        )
        out: list[dict[str, str]] = []
        for row in rows:
            url = absolute_vk_url(self.base_url, row.get("href", ""))
            out.append(
                {
                    "url": url,
                    "external_id": reply_id_from_url(url),
                    "text": clean_vk_text(row.get("text", "")),
                    "date": clean_vk_text(row.get("date", "")),
                    "author": clean_vk_text(row.get("author", "")),
                }
            )
        return out

    @staticmethod
    def _date_allowed(published_at, since, include_unknown_dates: bool) -> bool:
        if published_at is None:
            return include_unknown_dates
        return published_at >= since and published_at <= timezone.now() + timedelta(minutes=10)
