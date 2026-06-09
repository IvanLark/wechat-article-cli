"""文章内容解析与缓存

架构：cleaned HTML 作为元格式缓存，按需转换为 markdown/html/text。
缓存目录：wechat-article capability home 下的 `cached_articles/`
  - <link_hash>.json  元数据（title, author, date, link, cached_at）
  - <link_hash>.html  cleaned HTML（元格式）
"""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from wechat_article_cli.proxy import ProxyManager

from bs4 import BeautifulSoup, Tag
from loguru import logger
from markdownify import markdownify as md

from wechat_article_cli._toolkit.runtime.home import get_data_dir
from wechat_article_cli.proxy import fetch_article_html

# 需要清除的垃圾 DOM 元素 ID
_JUNK_IDS = [
    "js_top_ad_area",
    "js_tags_preview_toast",
    "content_bottom_area",
    "js_pc_qr_code",
    "wx_stream_article_slide_tip",
]


def _clean_dom(container: Tag) -> None:
    for elem_id in _JUNK_IDS:
        elem = container.find(id=elem_id)
        if elem:
            elem.decompose()
    for script in container.find_all("script"):
        script.decompose()
    for style in container.find_all("style"):
        style.decompose()


def _fix_lazy_images(container: Tag) -> None:
    for img in container.find_all("img"):
        src = img.get("src")
        data_src = img.get("data-src")
        if not src and data_src:
            img["src"] = data_src
        if img.get("data-src"):
            del img["data-src"]


def _handle_text_share(container: Tag, raw_html: str) -> None:
    """处理文本分享消息（TextContentNoEncode / ContentNoEncode）"""
    text_desc = container.find(id="js_text_desc")
    if not text_desc or (isinstance(text_desc, Tag) and text_desc.get_text(strip=True)):
        return

    patterns = [
        r"var\s+TextContentNoEncode\s*=\s*window\.a_value_which_never_exists\s*\|\|\s*'([^']*)'",
        r"var\s+ContentNoEncode\s*=\s*window\.a_value_which_never_exists\s*\|\|\s*'([^']*)'",
    ]

    desc = None
    for pattern in patterns:
        match = re.search(pattern, raw_html, re.DOTALL)
        if match:
            desc = match.group(1)
            desc = desc.replace("\\x0a", "\n").replace("\\x26", "&")
            desc = desc.replace("\\n", "\n").replace("\\'", "'")
            break

    if desc and isinstance(text_desc, Tag):
        desc = desc.replace("\r", "").replace("\n", "<br>")
        text_desc.clear()
        text_desc.append(BeautifulSoup(desc, "lxml"))


# --- 缓存管理 ---


def _cache_dir() -> Path:
    d = get_data_dir("wechat_article") / "cached_articles"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _link_hash(link: str) -> str:
    return hashlib.md5(link.encode()).hexdigest()[:12]


def is_article_cached(link: str) -> bool:
    """检查文章内容是否已缓存（json + html 两个文件都存在）"""
    h = _link_hash(link)
    d = _cache_dir()
    return (d / f"{h}.json").exists() and (d / f"{h}.html").exists()


def get_cached_content(
    link: str, fmt: Literal["markdown", "html", "text"] = "markdown"
) -> str | None:
    """从缓存读取文章内容并转换格式，未缓存返回 None"""
    cached = _load_cache(link)
    if not cached:
        return None
    return convert_format(cached["cleaned_html"], fmt)


def _load_cache(link: str) -> dict | None:
    """从缓存加载文章元数据和 cleaned HTML"""
    h = _link_hash(link)
    meta_path = _cache_dir() / f"{h}.json"
    html_path = _cache_dir() / f"{h}.html"
    if not meta_path.exists() or not html_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["cleaned_html"] = html_path.read_text(encoding="utf-8")
        return meta
    except (json.JSONDecodeError, OSError):
        return None


def _save_cache(link: str, meta: dict, cleaned_html: str) -> None:
    """缓存文章元数据和 cleaned HTML"""
    h = _link_hash(link)
    meta_path = _cache_dir() / f"{h}.json"
    html_path = _cache_dir() / f"{h}.html"
    meta_to_save = {k: v for k, v in meta.items() if k != "cleaned_html"}
    meta_to_save["cached_at"] = datetime.now(timezone.utc).isoformat()
    meta_path.write_text(
        json.dumps(meta_to_save, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    html_path.write_text(cleaned_html, encoding="utf-8")


# --- 从原始 HTML 提取 cleaned HTML + 元数据 ---


def _extract_cleaned(raw_html: str, link: str) -> dict:
    """从原始 HTML 中提取 cleaned HTML 和元数据"""
    soup = BeautifulSoup(raw_html, "lxml")

    # 元数据
    title_elem = soup.find("h1", class_="rich_media_title")
    title = title_elem.get_text(strip=True) if title_elem else ""
    author_elem = soup.find("a", class_="rich_media_meta_link")
    author = author_elem.get_text(strip=True) if author_elem else ""
    date_elem = soup.find("em", id="publish_time")
    publish_date = date_elem.get_text(strip=True) if date_elem else ""

    # 正文
    content_elem = soup.find("div", id="js_content")
    if not content_elem:
        if "item_show_type=8" in link:
            img_elems = soup.find_all("img", class_="rich_pages")
            if img_elems:
                content_html = "".join(str(img) for img in img_elems)
                content_elem = BeautifulSoup(content_html, "lxml")
            else:
                raise ValueError("无法提取文章内容（特殊页面）")
        else:
            raise ValueError("无法提取文章内容（未找到 #js_content）")

    _clean_dom(content_elem)
    _fix_lazy_images(content_elem)
    _handle_text_share(content_elem, raw_html)

    cleaned_html = str(content_elem)

    return {
        "title": title,
        "author": author,
        "publish_date": publish_date,
        "link": link,
        "cleaned_html": cleaned_html,
    }


# --- 格式转换 ---


def convert_format(
    cleaned_html: str, fmt: Literal["markdown", "html", "text"]
) -> str:
    """从 cleaned HTML 转换为指定格式"""
    if fmt == "html":
        return cleaned_html
    elif fmt == "text":
        soup = BeautifulSoup(cleaned_html, "lxml")
        return soup.get_text(separator="\n", strip=True)
    else:  # markdown
        content = md(
            cleaned_html,
            heading_style="ATX",
            bullets="-",
            strip=["script", "style"],
        )
        return re.sub(r"\n{3,}", "\n\n", content).strip()


# --- 公开接口 ---


async def get_article_content(
    link: str,
    fmt: Literal["markdown", "html", "text"] = "markdown",
    proxy_urls: list[str] | None = None,
    proxy_manager: "ProxyManager | None" = None,
) -> dict:
    """获取文章内容（自动缓存 cleaned HTML）

    proxy_manager: 可选，传入复用的 ProxyManager 实例。
    """
    # 查缓存
    cached = _load_cache(link)
    if cached:
        logger.debug("文章缓存命中：{}", cached.get("title", ""))
        content = convert_format(cached["cleaned_html"], fmt)
        return {
            "title": cached["title"],
            "author": cached.get("author", ""),
            "publish_date": cached.get("publish_date", ""),
            "content": content,
            "format": fmt,
            "cached": True,
        }

    # 未命中，走代理获取
    logger.debug("文章缓存未命中，开始从网络获取")
    raw_html = await fetch_article_html(
        link, proxy_urls=proxy_urls, proxy_manager=proxy_manager
    )
    data = _extract_cleaned(raw_html, link)

    # 写入缓存
    _save_cache(link, data, data["cleaned_html"])
    logger.debug("文章已缓存：{}", data["title"])

    content = convert_format(data["cleaned_html"], fmt)
    return {
        "title": data["title"],
        "author": data["author"],
        "publish_date": data["publish_date"],
        "content": content,
        "format": fmt,
        "cached": False,
    }
