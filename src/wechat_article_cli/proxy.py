"""代理池管理器

通过 Cloudflare Worker 代理池获取微信公众号文章 HTML。
只有文章内容获取需要代理（绕过微信 IP 级 CAPTCHA 反爬）。
登录、搜索、文章列表等微信后台 API 直连，不需要代理。
"""

import asyncio
import time
from dataclasses import dataclass
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup
from loguru import logger

TIMEOUT = 20.0
MAX_RETRIES = 3
MAX_FAILURES = 3
COOLDOWN_PERIOD = 30.0


@dataclass
class _ProxyStatus:
    failures: int = 0
    last_used: float = 0.0
    cooldown: bool = False
    total_use: int = 0
    total_success: int = 0
    total_failures: int = 0


class ProxyManager:
    """代理池管理器：选最优代理、记录成败、冷却机制"""

    def __init__(
        self,
        proxies: list[str],
        cooldown_period: float = COOLDOWN_PERIOD,
        max_failures: int = MAX_FAILURES,
    ):
        if not proxies:
            raise ValueError(
                "代理池为空。请执行 wechat-article config set proxy.url <代理地址>，"
                "或临时设置 WECHAT_PROXY_URL（多个用逗号分隔）"
            )
        self._proxies = list(proxies)
        self._cooldown_period = cooldown_period
        self._max_failures = max_failures
        self._status: dict[str, _ProxyStatus] = {
            p: _ProxyStatus() for p in self._proxies
        }

    def get_best_proxy(self) -> str:
        now = time.monotonic()
        available = [
            (proxy, st)
            for proxy, st in self._status.items()
            if not st.cooldown or (now - st.last_used) >= self._cooldown_period
        ]
        if not available:
            return self._reset_and_get()
        available.sort(key=lambda x: (x[1].failures, x[1].last_used))
        proxy, st = available[0]
        st.last_used = now
        st.total_use += 1
        return proxy

    def record_failure(self, proxy: str) -> None:
        st = self._status.get(proxy)
        if not st:
            return
        st.failures += 1
        st.total_failures += 1
        st.cooldown = st.failures >= self._max_failures

    def record_success(self, proxy: str) -> None:
        st = self._status.get(proxy)
        if not st:
            return
        st.failures = 0
        st.cooldown = False
        st.total_success += 1

    def _reset_and_get(self) -> str:
        oldest = min(self._status, key=lambda p: self._status[p].last_used)
        st = self._status[oldest]
        st.failures = 0
        st.cooldown = False
        st.last_used = time.monotonic()
        st.total_use += 1
        return oldest


def get_proxy_urls() -> list[str]:
    """从配置读取代理 URL 列表"""
    from wechat_article_cli.config import get_proxy_urls as load_proxy_urls

    return load_proxy_urls()


def get_proxy_token() -> str:
    """从配置读取代理鉴权 token"""
    from wechat_article_cli.config import get_proxy_token as load_proxy_token

    return load_proxy_token()


def validate_html(html: str) -> tuple[str, str | None]:
    """验证文章 HTML 是否下载成功"""
    soup = BeautifulSoup(html, "lxml")
    if soup.find(id="js_article") or soup.find(id="js_content"):
        return ("success", None)
    weui_msg = soup.find(class_="weui-msg")
    if weui_msg:
        title_el = weui_msg.find(class_="weui-msg__title")
        desc_el = weui_msg.find(class_="weui-msg__desc")
        msg = title_el.get_text(strip=True) if title_el else ""
        if not msg and desc_el:
            msg = desc_el.get_text(strip=True)
        if msg in ("该内容已被发布者删除", "The content has been deleted by the author."):
            return ("deleted", None)
        return ("exception", msg or None)
    msg_block = soup.find(class_="mesg-block")
    if msg_block:
        return ("exception", msg_block.get_text(strip=True) or None)
    return ("error", None)


def _article_status_error(msg: str | None) -> ValueError:
    detail = msg or "页面未提供错误信息，可能是文章访问受限或微信风控页面"
    return ValueError(f"文章状态异常：{detail}")


async def fetch_article_html(
    link: str,
    proxy_urls: list[str] | None = None,
    proxy_manager: ProxyManager | None = None,
) -> str:
    """获取文章 HTML，通过代理池或直连

    proxy_manager: 可选，传入已有实例以复用代理统计/冷却状态。
    proxy_urls: 如未传入 proxy_manager，则用此列表创建临时实例。
    """
    if not proxy_urls and proxy_manager is None:
        return await _fetch_direct(link)

    manager = proxy_manager or ProxyManager(proxy_urls or [])
    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES):
        proxy = manager.get_best_proxy()
        try:
            html = await _fetch_via_proxy(link, proxy)
            status, msg = validate_html(html)

            if status == "success":
                manager.record_success(proxy)
                return html
            elif status == "deleted":
                raise ValueError("文章已被作者删除")
            elif status == "exception":
                raise _article_status_error(msg)
            else:
                manager.record_failure(proxy)
                last_error = ValueError(
                    f"代理返回的页面不含文章内容（可能被风控），"
                    f"代理: {proxy}，第 {attempt + 1}/{MAX_RETRIES} 次"
                )
                logger.debug("第 {} 次尝试失败，代理: {}", attempt + 1, proxy)

        except ValueError:
            raise
        except httpx.ConnectError as e:
            manager.record_failure(proxy)
            last_error = RuntimeError(f"无法连接代理 {proxy}：{e}")
        except httpx.HTTPStatusError as e:
            manager.record_failure(proxy)
            code = e.response.status_code
            if code == 403:
                last_error = RuntimeError(
                    "代理认证失败（HTTP 403），请检查 proxy.token 或 WECHAT_PROXY_TOKEN"
                )
            else:
                last_error = RuntimeError(f"代理返回 HTTP {code}")
        except Exception as e:
            manager.record_failure(proxy)
            last_error = RuntimeError(f"代理请求异常：{type(e).__name__}: {e}")

        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(2**attempt)

    raise last_error or RuntimeError(f"文章获取失败：重试 {MAX_RETRIES} 次均失败")


async def _fetch_via_proxy(link: str, proxy_url: str) -> str:
    target = f"{proxy_url}?url={quote(link, safe='')}"
    token = get_proxy_token()
    if token:
        target += f"&authorization={quote(token, safe='')}"
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(target)
        resp.raise_for_status()
        return resp.text


async def _fetch_direct(link: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/100.0.0.0 Safari/537.36"
        ),
    }
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(link, headers=headers)
        resp.raise_for_status()
        html = resp.text

    status, msg = validate_html(html)
    if status == "success":
        return html
    if status == "deleted":
        raise ValueError("文章已被作者删除")
    if status == "exception":
        raise _article_status_error(msg)
    raise RuntimeError(
        "直连请求被微信风控拦截。请执行 wechat-article config set proxy.url <代理地址> 后重试，"
        "或临时设置 WECHAT_PROXY_URL"
    )
